"""Generative-governance spike: Mirus drafts meaning before Holden renders.

This is intentionally lab-only. It does not call a model, write memory, import
support patterns, or extract a Core schema. The goal is to test whether
governance can produce a clear-text, vectorizable answer spine before any model
rendering happens.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from labs.meaning_compression_lab.local_router_cli import build_case
from labs.meaning_compression_lab.local_router_eval import classify_request, route_for_task
from labs.meaning_compression_lab.run_lab import OUT_DIR


Answerability = Literal[
    "answerable",
    "partially_answerable",
    "insufficient_evidence",
    "needs_memory_review",
]
EvidenceState = Literal[
    "no_receipts",
    "weak_receipts",
    "sufficient_receipts",
    "conflicted_receipts",
]


SELF_BOUNDARY = {
    "user_self": (
        "facts, memories, preferences, projects, body/story context, and "
        "claims that belong to the user"
    ),
    "aether_self": (
        "intent analysis, route choice, evidence boundary, policy limits, "
        "confidence, and review state"
    ),
    "shared_context": (
        "the current prompt, supplied receipts, agreed project language, and "
        "reviewable trace artifacts"
    ),
}


@dataclass(frozen=True)
class GovernanceReceipt:
    receipt_id: str
    source: Literal["user_prompt", "supplied_context", "memory", "trace", "tool"]
    text: str
    authority: Literal["user_current", "reviewed", "candidate", "tool", "unknown"] = "user_current"
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GovernanceTrace:
    trace_schema: str
    created_at: int
    query: str
    intent: str
    route: dict[str, Any]
    evidence_state: EvidenceState
    answerability: Answerability
    self_boundary: dict[str, str]
    receipts: tuple[GovernanceReceipt, ...]
    allowed_claims: tuple[str, ...]
    blocked_claims: tuple[str, ...]
    response_spine: tuple[str, ...]
    governance_only_answer: str
    model_render_needed: bool
    model_render_reason: str
    review_candidates: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    vectorizable_trace_text: str = ""
    raw_chain_of_thought_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["receipts"] = [receipt.to_dict() for receipt in self.receipts]
        return data


def build_governance_trace(
    query: str,
    *,
    task_type: str | None = None,
    context: str = "",
    receipts: tuple[GovernanceReceipt, ...] = (),
    conflict_slots: tuple[str, ...] = (),
) -> GovernanceTrace:
    """Generate a clear-text governance state before any model render."""

    intent = task_type or classify_request(query)
    case = build_case(query, task_type=intent, context=context)
    route = route_for_task(intent).to_dict()
    all_receipts = _receipts_from_context(context) + tuple(receipts)
    evidence_state = _evidence_state(intent, all_receipts, conflict_slots)
    answerability = _answerability(intent, evidence_state, conflict_slots)
    allowed_claims = _allowed_claims(intent, evidence_state)
    blocked_claims = _blocked_claims(case, intent, evidence_state, conflict_slots)
    response_spine = _response_spine(intent, evidence_state, answerability, all_receipts)
    governance_answer = _governance_only_answer(
        intent=intent,
        answerability=answerability,
        evidence_state=evidence_state,
        receipts=all_receipts,
        conflict_slots=conflict_slots,
    )
    model_needed, model_reason = _model_render_decision(intent, answerability, all_receipts)
    review_candidates = _review_candidates(
        intent=intent,
        answerability=answerability,
        evidence_state=evidence_state,
        conflict_slots=conflict_slots,
    )
    vector_text = _vectorizable_text(
        query=query,
        intent=intent,
        evidence_state=evidence_state,
        answerability=answerability,
        allowed_claims=allowed_claims,
        blocked_claims=blocked_claims,
        response_spine=response_spine,
    )
    return GovernanceTrace(
        trace_schema="aether.generative_governance.spike.v0",
        created_at=int(time.time()),
        query=query,
        intent=intent,
        route=route,
        evidence_state=evidence_state,
        answerability=answerability,
        self_boundary=dict(SELF_BOUNDARY),
        receipts=all_receipts,
        allowed_claims=allowed_claims,
        blocked_claims=blocked_claims,
        response_spine=response_spine,
        governance_only_answer=governance_answer,
        model_render_needed=model_needed,
        model_render_reason=model_reason,
        review_candidates=review_candidates,
        vectorizable_trace_text=vector_text,
        raw_chain_of_thought_stored=False,
    )


def run_spike() -> dict[str, Any]:
    cases = _cases()
    rows = []
    for case in cases:
        trace = build_governance_trace(
            case["query"],
            task_type=case.get("task_type"),
            context=case.get("context", ""),
            receipts=tuple(case.get("receipts", ())),
            conflict_slots=tuple(case.get("conflict_slots", ())),
        )
        checks = {
            key: _matches(trace, key, expected)
            for key, expected in case["expect"].items()
        }
        rows.append({
            "case_id": case["case_id"],
            "passed": all(checks.values()),
            "checks": checks,
            "expect": case["expect"],
            "trace": trace.to_dict(),
        })
    return {
        "lab": "generative_governance_spike",
        "created_at": int(time.time()),
        "case_count": len(rows),
        "passed": all(row["passed"] for row in rows),
        "writes_performed": False,
        "memory_write_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "raw_chain_of_thought_stored": False,
        "rows": rows,
    }


def _receipts_from_context(context: str) -> tuple[GovernanceReceipt, ...]:
    lines = [line.strip(" -\t") for line in context.splitlines() if line.strip()]
    receipts = []
    for index, line in enumerate(lines, start=1):
        receipts.append(GovernanceReceipt(
            receipt_id=f"context_{index}",
            source="supplied_context",
            text=line,
            authority="user_current",
            tags=_tags_for_text(line),
        ))
    return tuple(receipts)


def _tags_for_text(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    tags = []
    if any(word in lowered for word in ("leukemia", "gvhd", "health", "body", "weight")):
        tags.append("sensitive_health")
    if any(word in lowered for word in ("road america", "marigold", "shop", "aether", "aeteros")):
        tags.append("concrete_receipt")
    if any(word in lowered for word in ("maybe", "might", "old", "past", "used to")):
        tags.append("time_sensitive")
    return tuple(tags)


def _evidence_state(
    intent: str,
    receipts: tuple[GovernanceReceipt, ...],
    conflict_slots: tuple[str, ...],
) -> EvidenceState:
    if conflict_slots:
        return "conflicted_receipts"
    if not receipts:
        return "no_receipts"
    concrete_count = sum(_is_concrete(receipt) for receipt in receipts)
    if intent == "personal_synthesis":
        return "sufficient_receipts" if concrete_count >= 2 else "weak_receipts"
    return "sufficient_receipts" if concrete_count or len(receipts) >= 1 else "weak_receipts"


def _answerability(
    intent: str,
    evidence_state: EvidenceState,
    conflict_slots: tuple[str, ...],
) -> Answerability:
    if conflict_slots or evidence_state == "conflicted_receipts":
        return "needs_memory_review"
    if evidence_state == "no_receipts":
        return "insufficient_evidence" if intent in {"personal_synthesis", "exact_memory"} else "partially_answerable"
    if evidence_state == "weak_receipts" and intent == "personal_synthesis":
        return "insufficient_evidence"
    if evidence_state == "weak_receipts":
        return "partially_answerable"
    return "answerable"


def _allowed_claims(intent: str, evidence_state: EvidenceState) -> tuple[str, ...]:
    claims = [
        "state the detected task type and evidence boundary",
        "distinguish user facts from Aether governance state",
        "name uncertainty when receipts are weak or absent",
    ]
    if intent in {"architecture_synthesis", "architecture_process"}:
        claims.append("describe Aether/CRT mechanism as architecture, not model magic")
    if intent in {"business_planning", "grant_business"}:
        claims.append("make bounded planning claims without promising outcomes")
    if intent == "personal_synthesis" and evidence_state == "sufficient_receipts":
        claims.append("make bounded pattern claims tied to concrete receipts")
    if intent == "exact_memory" and evidence_state == "sufficient_receipts":
        claims.append("answer exact known state from supplied current receipts")
    return tuple(claims)


def _blocked_claims(
    case: Any,
    intent: str,
    evidence_state: EvidenceState,
    conflict_slots: tuple[str, ...],
) -> tuple[str, ...]:
    blocked = list(case.forbidden_claims)
    blocked.extend([
        "treat Aether's route or behavior notes as facts about the user",
        "store or expose raw hidden chain-of-thought",
        "silently promote memory, support, reflection, or policy changes",
    ])
    if intent == "personal_synthesis" and evidence_state != "sufficient_receipts":
        blocked.extend([
            "identity claims from weak receipts",
            "generic founder journey comparison",
            "claiming who the user is now without concrete anchors",
        ])
    if intent == "business_planning":
        blocked.extend([
            "guaranteed income from a creative business lane",
            "full-time replacement claims without repeated revenue receipts",
        ])
    if conflict_slots:
        blocked.append("choose one conflicted memory value without review")
    return tuple(dict.fromkeys(blocked))


def _response_spine(
    intent: str,
    evidence_state: EvidenceState,
    answerability: Answerability,
    receipts: tuple[GovernanceReceipt, ...],
) -> tuple[str, ...]:
    spine = [
        f"Name the intent as {intent}.",
        f"Name the evidence state as {evidence_state}.",
        "Separate USER_SELF claims from AETHER_SELF governance state.",
    ]
    if answerability == "needs_memory_review":
        spine.extend([
            "Say the answer needs memory review before selecting a fact.",
            "Offer the review path rather than a synthesized answer.",
        ])
    elif answerability == "insufficient_evidence":
        spine.extend([
            "Say there are not enough concrete receipts for the requested claim.",
            "Ask for two or three receipts or offer a narrower answer.",
        ])
    elif answerability == "partially_answerable":
        spine.extend([
            "Answer only the bounded portion supported by the prompt.",
            "State what would require more evidence or a model render.",
        ])
    else:
        spine.extend([
            "Use receipts before pattern language.",
            "Then let Holden/model rendering carry tone if the answer needs nuance.",
        ])
    if receipts:
        spine.append("Cite receipt ids: " + ", ".join(receipt.receipt_id for receipt in receipts[:4]) + ".")
    return tuple(spine)


def _governance_only_answer(
    *,
    intent: str,
    answerability: Answerability,
    evidence_state: EvidenceState,
    receipts: tuple[GovernanceReceipt, ...],
    conflict_slots: tuple[str, ...],
) -> str:
    if answerability == "needs_memory_review":
        slots = ", ".join(conflict_slots) or "the relevant memory slot"
        return (
            f"I am treating this as {intent}. I see a conflict in {slots}, so I "
            "should not choose one value or synthesize from it until memory review happens."
        )
    if answerability == "insufficient_evidence":
        return (
            f"I am treating this as {intent}. The evidence state is {evidence_state}, "
            "so I can describe the boundary, but I should not make the larger claim yet. "
            "Give me two or three concrete receipts and I can produce a bounded pass."
        )
    if answerability == "partially_answerable":
        return (
            f"I am treating this as {intent}. I can answer the bounded part from the "
            "prompt, but a richer response should be rendered from a governed spine."
        )
    receipt_text = "; ".join(receipt.text for receipt in receipts[:2])
    return (
        f"I am treating this as {intent}. The receipts are sufficient for a bounded "
        f"answer. Start from: {receipt_text}"
    )


def _model_render_decision(
    intent: str,
    answerability: Answerability,
    receipts: tuple[GovernanceReceipt, ...],
) -> tuple[bool, str]:
    if answerability in {"needs_memory_review", "insufficient_evidence"}:
        return False, "governance_can_answer_boundary_without_holden"
    if intent in {"personal_synthesis", "architecture_synthesis", "grant_business", "business_planning"}:
        return True, "holden_or_model_useful_for_humane_nuanced_render"
    if receipts:
        return False, "governance_only_exact_or_bounded_answer_is_enough"
    return True, "model_render_needed_for_open_ended_language"


def _review_candidates(
    *,
    intent: str,
    answerability: Answerability,
    evidence_state: EvidenceState,
    conflict_slots: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    rows = []
    if conflict_slots:
        for slot in conflict_slots:
            rows.append({
                "candidate_type": "contradiction_review",
                "slot_id": slot,
                "reason": "conflicted evidence blocks answer generation",
                "review_required": True,
                "memory_write_allowed": False,
            })
    if intent == "personal_synthesis" and evidence_state in {"no_receipts", "weak_receipts"}:
        rows.append({
            "candidate_type": "receipt_request_pattern",
            "reason": "personal synthesis asked with insufficient concrete receipts",
            "review_required": True,
            "memory_write_allowed": False,
        })
    if answerability == "partially_answerable":
        rows.append({
            "candidate_type": "model_render_boundary",
            "reason": "governance can draft structure but Holden/model may improve expression",
            "review_required": False,
            "memory_write_allowed": False,
        })
    return tuple(rows)


def _vectorizable_text(
    *,
    query: str,
    intent: str,
    evidence_state: EvidenceState,
    answerability: Answerability,
    allowed_claims: tuple[str, ...],
    blocked_claims: tuple[str, ...],
    response_spine: tuple[str, ...],
) -> str:
    parts = [
        f"query: {query}",
        f"intent: {intent}",
        f"evidence_state: {evidence_state}",
        f"answerability: {answerability}",
        "self_boundary: user facts are separate from aether governance state",
        "allowed_claims: " + " | ".join(allowed_claims),
        "blocked_claims: " + " | ".join(blocked_claims),
        "response_spine: " + " | ".join(response_spine),
    ]
    return "\n".join(parts)


def _is_concrete(receipt: GovernanceReceipt) -> bool:
    if "concrete_receipt" in receipt.tags:
        return True
    text = receipt.text.strip()
    if len(text.split()) < 4:
        return False
    vague = {"maybe", "possibly", "vibes", "someday", "stuff", "things"}
    return not any(re.search(rf"\b{re.escape(word)}\b", text.lower()) for word in vague)


def _matches(trace: GovernanceTrace, key: str, expected: Any) -> bool:
    if key == "blocked_contains":
        return any(expected in item for item in trace.blocked_claims)
    if key == "spine_contains":
        return any(expected in item for item in trace.response_spine)
    if key == "review_candidate_type":
        return any(item.get("candidate_type") == expected for item in trace.review_candidates)
    return getattr(trace, key) == expected


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "weak_personal_receipts_boundary",
            "query": "Who am I becoming as a founder?",
            "task_type": "personal_synthesis",
            "expect": {
                "answerability": "insufficient_evidence",
                "model_render_needed": False,
                "blocked_contains": "identity claims",
                "review_candidate_type": "receipt_request_pattern",
            },
        },
        {
            "case_id": "grounded_personal_synthesis_needs_holden",
            "query": "What pattern do you see in me right now?",
            "task_type": "personal_synthesis",
            "context": "Road America video posted after a heavy week.\n12,730 steps logged.\nMarigolds planted near the shop.",
            "expect": {
                "answerability": "answerable",
                "model_render_needed": True,
                "spine_contains": "Use receipts before pattern language.",
            },
        },
        {
            "case_id": "exact_memory_conflict_review",
            "query": "Where do I currently work?",
            "task_type": "exact_memory",
            "conflict_slots": ("user:employer",),
            "expect": {
                "answerability": "needs_memory_review",
                "model_render_needed": False,
                "review_candidate_type": "contradiction_review",
            },
        },
        {
            "case_id": "architecture_governance_spine",
            "query": "Could generative governance respond before the model?",
            "task_type": "architecture_synthesis",
            "context": "Aether routes, builds Mirus packets, verifies, repairs, and stores durable traces.",
            "expect": {
                "answerability": "answerable",
                "model_render_needed": True,
                "spine_contains": "Use receipts before pattern language.",
            },
        },
        {
            "case_id": "business_planning_bounded_render",
            "query": "Could the print shop and camera work become a realistic small business lane?",
            "task_type": "business_planning",
            "context": "The Printing Lair handles stickers and low-batch prints.\nCamera/video work is active but not proven as full-time income.",
            "expect": {
                "answerability": "answerable",
                "model_render_needed": True,
                "blocked_contains": "guaranteed income",
            },
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_spike()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
