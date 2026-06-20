"""Standalone question-to-governed-slot inference for Holden."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


MIN_RESOLVED_SCORE = 0.58
MIN_WIN_MARGIN = 0.12


@dataclass(frozen=True)
class SlotCandidate:
    slot: str
    score: float
    signals: tuple[str, ...]


@dataclass(frozen=True)
class SlotInference:
    status: str
    contract_kind: str
    requested_slots: tuple[str, ...]
    confidence: float
    candidates: tuple[SlotCandidate, ...]
    reason_code: str

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "requested_slots": list(self.requested_slots),
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }


_ALIASES: dict[str, tuple[str, ...]] = {
    "name": (
        "my name", "personal name", "call me", "called me", "who am i",
        "name for me", "use for me",
    ),
    "employer": (
        "employer", "employment", "where i work", "where am i working",
        "where am i currently working", "currently working", "company i work",
        "work for", "job company",
    ),
    "camera_system": (
        "camera system", "camera setup", "camera rig", "camera body",
    ),
    "current_project": (
        "current project", "active project", "working on now", "project am i",
    ),
    "store_platform": (
        "store platform", "store run on", "store runs on", "commerce platform",
        "store currently run on", "store currently runs on", "real store",
        "ecommerce platform", "e-commerce platform",
    ),
    "home_city": ("where i live", "home city", "located", "location"),
    "location": ("where i live", "home city", "located", "location"),
}

_TOKEN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "employer": ("work", "working", "employment", "job", "company"),
    "camera": ("camera", "rig", "body", "photography"),
    "system": ("system", "setup", "platform"),
    "project": ("project", "working", "active"),
    "store": ("store", "shop", "commerce", "ecommerce"),
    "platform": ("platform", "backend", "service", "stack", "run"),
    "delete": ("delete", "deletion", "destroy", "destruction", "remove"),
    "confirmation": ("confirmation", "confirm", "asking", "permission", "release"),
    "name": ("name", "called", "identity"),
    "naming": ("naming", "name", "file", "filename"),
}

_GENERIC_TOKENS = {
    "current", "user", "my", "the", "a", "an", "is", "are", "what", "which",
    "where", "does", "do", "did", "should", "can", "you", "i", "me", "now",
    "without", "before", "after",
}


def infer_contract_kind(query: str) -> str:
    text = query.lower()
    if re.search(r"\b(before|previous|previously|formerly|used to|earlier|history)\b", text):
        return "history"
    if re.search(
        r"\b(can you|may you|allowed|permission|without asking|without confirmation|"
        r"delete|destroy|force push|production)\b",
        text,
    ):
        return "policy"
    if re.search(r"\b(confirmed|unconfirmed|provisional|should you answer)\b", text):
        return "withhold"
    if re.search(r"\bwhat\s+(?:personal\s+)?name\s+should\b", text):
        return "current"
    if re.search(r"\b(current|currently|now|these days|real|actual|what is|what's|where am i|where do i)\b", text):
        return "current"
    return "general"


def infer_slot_request(
    query: str,
    available_slots: Iterable[str],
) -> SlotInference:
    text = _normalize(query)
    query_tokens = _tokens(text)
    contract_kind = infer_contract_kind(query)
    candidates = []

    for slot in sorted(set(str(slot) for slot in available_slots if slot)):
        score, signals = _score_slot(
            text=text,
            query_tokens=query_tokens,
            slot=slot,
            contract_kind=contract_kind,
        )
        if score > 0:
            candidates.append(
                SlotCandidate(slot, round(min(score, 1.0), 3), tuple(signals))
            )

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.slot))
    top = candidates[:3]
    if not top or top[0].score < MIN_RESOLVED_SCORE:
        return SlotInference(
            "unknown",
            contract_kind,
            (),
            top[0].score if top else 0.0,
            tuple(top),
            "no_candidate_above_threshold",
        )

    margin = top[0].score - (top[1].score if len(top) > 1 else 0.0)
    if len(top) > 1 and margin < MIN_WIN_MARGIN:
        return SlotInference(
            "ambiguous",
            contract_kind,
            (),
            top[0].score,
            tuple(top),
            "winning_margin_too_small",
        )

    return SlotInference(
        "resolved",
        contract_kind,
        (top[0].slot,),
        top[0].score,
        tuple(top),
        "resolved_above_threshold",
    )


def _score_slot(
    *,
    text: str,
    query_tokens: set[str],
    slot: str,
    contract_kind: str,
) -> tuple[float, list[str]]:
    normalized_slot = slot.lower().replace(".", " ").replace("_", " ")
    slot_tokens = _tokens(normalized_slot) - _GENERIC_TOKENS
    score = 0.0
    signals: list[str] = []

    if normalized_slot in text:
        score += 0.62
        signals.append("slot_phrase")

    overlap = query_tokens & slot_tokens
    if overlap:
        ratio = len(overlap) / max(1, len(slot_tokens))
        score += 0.18 + (0.22 * ratio)
        signals.append("slot_token_overlap:" + ",".join(sorted(overlap)))

    for canonical, aliases in _ALIASES.items():
        if slot == canonical or normalized_slot == canonical.replace("_", " "):
            matched = [alias for alias in aliases if alias in text]
            if matched:
                score += 0.68
                signals.append("alias:" + matched[0])

    synonym_hits = 0
    for token in slot_tokens:
        terms = _TOKEN_SYNONYMS.get(token, (token,))
        if any(_term_matches(term, query_tokens, text) for term in terms):
            synonym_hits += 1
    if synonym_hits:
        score += min(0.30, 0.12 * synonym_hits)
        signals.append(f"semantic_token_hits:{synonym_hits}")

    if contract_kind == "policy":
        policy_shape = any(
            token in slot_tokens
            for token in {"policy", "forbidden", "confirmation", "delete", "push"}
        ) or "without_confirmation" in slot or "force_push" in slot
        action_overlap = bool(
            query_tokens
            & {"delete", "deletion", "destroy", "force", "push", "production", "confirmation"}
        )
        if policy_shape and action_overlap:
            score += 0.25
            signals.append("policy_action_shape")
        elif not policy_shape:
            score -= 0.18

    if slot == "name":
        personal = bool(
            re.search(r"\b(my name|call me|called me|who am i|name for me|use for me)\b", text)
        )
        if personal:
            score += 0.28
            signals.append("personal_identity_cue")
        elif "name" in query_tokens:
            score *= 0.35
            signals.append("bare_name_ambiguity")

    return max(0.0, score), signals


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    raw = set(re.findall(r"[a-z0-9]+", text))
    singular = {
        token[:-1]
        for token in raw
        if len(token) > 3 and token.endswith("s")
    }
    return raw | singular


def _term_matches(term: str, query_tokens: set[str], text: str) -> bool:
    return term in text if " " in term else term in query_tokens
