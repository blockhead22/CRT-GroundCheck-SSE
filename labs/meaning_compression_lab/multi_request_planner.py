"""Clause-covered, multi-slot request planning for Holden."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from labs.meaning_compression_lab.slot_request_inference import (
    SlotInference,
    infer_slot_request,
)


MAX_REQUESTS = 8
SemanticParser = Callable[[list[dict[str, Any]], list[str]], Any]

_SLOT_DESCRIPTIONS = {
    "employer": "the company or organization the user works for; workplace, employment, paycheck source",
    "camera_system": "the user's camera body, photography setup, cinema rig, or prior camera system",
    "media.production_delete_without_confirmation": "locked policy governing deletion or destruction of production media without user confirmation",
    "current_project": "the project the user is actively working on now",
    "store_platform": "the software platform, backend, service, or commerce stack running the user's store",
    "name": "the user's personal name or identity",
    "file_naming": "rules for filenames, generated file names, export names, or naming conventions",
}


@dataclass(frozen=True)
class PlannedRequest:
    clause_id: str
    slot: str
    mode: str
    confidence: float
    source: str


@dataclass(frozen=True)
class PlannedClause:
    clause_id: str
    text: str
    status: str
    candidate_slots: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True)
class RequestPlan:
    status: str
    requests: tuple[PlannedRequest, ...]
    clauses: tuple[PlannedClause, ...]
    coverage: float
    unresolved_clauses: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "requests": [asdict(request) for request in self.requests],
            "clauses": [asdict(clause) for clause in self.clauses],
            "coverage": self.coverage,
            "unresolved_clauses": list(self.unresolved_clauses),
        }


def split_clauses(text: str) -> list[str]:
    """Split coordinated questions without treating every conjunction as a boundary."""
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized:
        return []
    normalized = re.sub(
        r"([?;])\s*(?:also|plus)\s*,?\s*",
        r"\1 ",
        normalized,
        flags=re.IGNORECASE,
    )
    pieces = re.split(
        r"(?:[?;]\s*|"
        r",\s+(?=(?:(?:and|also|plus)\s+)?(?:what|where|which|who|when|"
        r"did|do|does|can|could|may|should|was|were|is|are)\b)|"
        r"\s+\b(?:and|also|plus)\b\s+(?=(?:what|where|which|who|when|"
        r"did|do|does|can|could|may|should|was|were|is|are)\b))",
        normalized,
        flags=re.IGNORECASE,
    )
    return [piece.strip(" ,.?;") for piece in pieces if piece and piece.strip(" ,.?;")]


def plan_requests(
    query: str,
    available_slots: Iterable[str],
    *,
    semantic_parser: SemanticParser | None = None,
) -> RequestPlan:
    slots = sorted(set(str(slot) for slot in available_slots if slot))
    clause_texts = split_clauses(query)
    clauses: list[PlannedClause] = []
    requests: list[PlannedRequest] = []
    unresolved_payload: list[dict[str, Any]] = []

    for index, clause_text in enumerate(clause_texts, start=1):
        clause_id = f"c{index}"
        inference = infer_slot_request(clause_text, slots)
        if inference.status == "resolved":
            for slot in inference.requested_slots:
                requests.append(
                    PlannedRequest(
                        clause_id,
                        slot,
                        inference.contract_kind,
                        inference.confidence,
                        "deterministic",
                    )
                )
            clauses.append(
                PlannedClause(
                    clause_id,
                    clause_text,
                    "resolved",
                    inference.requested_slots,
                    inference.reason_code,
                )
            )
        else:
            candidate_slots = tuple(candidate.slot for candidate in inference.candidates)
            clauses.append(
                PlannedClause(
                    clause_id,
                    clause_text,
                    inference.status,
                    candidate_slots,
                    inference.reason_code,
                )
            )
            unresolved_payload.append(
                {
                    "clause_id": clause_id,
                    "text": clause_text,
                    "contract_hint": inference.contract_kind,
                    "candidate_slots": list(candidate_slots),
                }
            )

    if unresolved_payload and semantic_parser is not None:
        parser_output = _call_semantic_parser(
            semantic_parser,
            unresolved_payload,
            slots,
        )
        parsed_requests = _validate_parser_output(
            parser_output,
            unresolved_payload=unresolved_payload,
            available_slots=set(slots),
        )
        if parsed_requests:
            parsed_clause_ids = {request.clause_id for request in parsed_requests}
            requests.extend(parsed_requests)
            clauses = [
                PlannedClause(
                    clause.clause_id,
                    clause.text,
                    "resolved" if clause.clause_id in parsed_clause_ids else clause.status,
                    tuple(
                        request.slot
                        for request in parsed_requests
                        if request.clause_id == clause.clause_id
                    ) or clause.candidate_slots,
                    "semantic_parser_resolved"
                    if clause.clause_id in parsed_clause_ids
                    else clause.reason_code,
                )
                for clause in clauses
            ]

    requests = _merge_requests(requests)[:MAX_REQUESTS]
    unresolved_ids = tuple(
        clause.clause_id
        for clause in clauses
        if clause.status != "resolved"
    )
    coverage = round(
        (len(clauses) - len(unresolved_ids)) / len(clauses),
        3,
    ) if clauses else 0.0

    if clauses and not unresolved_ids:
        status = "resolved"
    elif requests:
        status = "partial"
    elif clauses and any(clause.status == "ambiguous" for clause in clauses):
        status = "ambiguous"
    else:
        status = "unknown"

    return RequestPlan(
        status,
        tuple(requests),
        tuple(clauses),
        coverage,
        unresolved_ids,
    )


def build_retrieval_plan(plan: RequestPlan, *, per_request_k: int = 4) -> list[dict[str, Any]]:
    """Translate resolved requests into independent bounded retrieval operations."""
    return [
        {
            "request_id": f"r{index}",
            "clause_id": request.clause_id,
            "slot": request.slot,
            "mode": request.mode,
            "top_k": per_request_k,
            "required_authority": (
                "locked" if request.mode == "policy" else
                "confirmed_or_locked" if request.mode == "current" else
                "any_with_provenance"
            ),
        }
        for index, request in enumerate(plan.requests, start=1)
    ]


def semantic_parser_prompt(
    unresolved_clauses: list[dict[str, Any]],
    available_slots: list[str],
) -> str:
    schema = {
        "requests": [
            {
                "clause_id": "c1",
                "slot": "one available slot",
                "mode": "current|history|policy|withhold|general",
                "confidence": 0.0,
            }
        ]
    }
    catalog = [
        {
            "slot": slot,
            "description": _SLOT_DESCRIPTIONS.get(
                slot,
                slot.replace("_", " ").replace(".", " "),
            ),
        }
        for slot in available_slots
    ]
    return (
        "Map each unresolved clause to zero or more governed memory slots.\n"
        "Use only slots from the catalog. Do not invent slots.\n"
        "Use the descriptions to resolve indirect wording and paraphrases.\n"
        "Return JSON only. Omit a clause when it cannot be resolved.\n\n"
        f"Slot catalog:\n{json.dumps(catalog, indent=2)}\n\n"
        f"Unresolved clauses:\n{json.dumps(unresolved_clauses, indent=2)}\n\n"
        f"Output schema example:\n{json.dumps(schema, indent=2)}"
    )


def ollama_semantic_parser(
    unresolved_clauses: list[dict[str, Any]],
    available_slots: list[str],
    *,
    model: str = "qwen2.5:7b-instruct",
    timeout: int = 90,
) -> Any:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": semantic_parser_prompt(unresolved_clauses, available_slots),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 300},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def _call_semantic_parser(
    parser: SemanticParser,
    unresolved_payload: list[dict[str, Any]],
    slots: list[str],
) -> Any:
    return parser(unresolved_payload, slots)


def _validate_parser_output(
    output: Any,
    *,
    unresolved_payload: list[dict[str, Any]],
    available_slots: set[str],
) -> list[PlannedRequest]:
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return []
    if not isinstance(output, dict) or not isinstance(output.get("requests"), list):
        return []

    valid_clause_ids = {row["clause_id"] for row in unresolved_payload}
    contract_hints = {
        row["clause_id"]: row.get("contract_hint", "general")
        for row in unresolved_payload
    }
    allowed_modes = {"current", "history", "policy", "withhold", "general"}
    requests = []
    for row in output["requests"]:
        if not isinstance(row, dict):
            continue
        clause_id = str(row.get("clause_id") or "")
        slot = str(row.get("slot") or "")
        mode = str(row.get("mode") or "")
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError):
            continue
        if (
            clause_id not in valid_clause_ids
            or slot not in available_slots
            or mode not in allowed_modes
            or not 0.0 <= confidence <= 1.0
            or confidence < 0.58
        ):
            continue
        hint = contract_hints.get(clause_id, "general")
        if mode == "general" and hint in allowed_modes - {"general"}:
            mode = hint
        requests.append(
            PlannedRequest(
                clause_id,
                slot,
                mode,
                round(confidence, 3),
                "semantic_parser",
            )
        )
    return requests


def _merge_requests(requests: list[PlannedRequest]) -> list[PlannedRequest]:
    mode_rank = {"general": 0, "current": 1, "withhold": 2, "history": 3, "policy": 4}
    merged: dict[tuple[str, str], PlannedRequest] = {}
    for request in requests:
        key = (request.clause_id, request.slot)
        existing = merged.get(key)
        if existing is None or (
            mode_rank[request.mode],
            request.confidence,
        ) > (
            mode_rank[existing.mode],
            existing.confidence,
        ):
            merged[key] = request
    return sorted(
        merged.values(),
        key=lambda request: (
            int(request.clause_id[1:])
            if request.clause_id.startswith("c") and request.clause_id[1:].isdigit()
            else 10**9,
            request.slot,
        ),
    )
