"""Personal fact helpers — extracted from routes/chat.py.

Functions for meta-provenance follow-ups, personal-fact slot detection,
and bundled personal-fact answering.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Meta-provenance follow-up helpers
# ---------------------------------------------------------------------------


def _is_meta_provenance_followup(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    return any(
        phrase in text
        for phrase in (
            "how do you know",
            "how are you sure",
            "how did you know",
            "how do you remember",
            "how did you learn",
            "where did you learn",
            "where did you learn that",
            "how does your memory",
            "how does that work",
            "explain your process",
            "why are you sure",
        )
    )


def _answer_recent_slot_provenance(*, engine: Any, session_db: Any, thread_id: str) -> Optional[str]:
    if session_db is None:
        return None
    try:
        recent = session_db.get_recent_queries(thread_id, window=6)
    except Exception:
        recent = []
    if not recent:
        return None

    target_slot = None
    for row in recent:
        slot = str((row or {}).get("detected_slot") or "").strip()
        if slot:
            target_slot = slot
            break
    if not target_slot:
        return None

    try:
        memories = engine.memory._load_all_memories()
    except Exception:
        return None

    candidates: List[Tuple[Any, Any]] = []
    for mem in memories:
        if getattr(mem, "source", None) is None:
            continue
        if bool(getattr(mem, "deprecated", False)):
            continue
        try:
            facts = extract_fact_slots(str(getattr(mem, "text", "") or ""))
        except Exception:
            continue
        if target_slot in facts:
            candidates.append((mem, facts[target_slot]))

    if not candidates:
        return None

    best_mem, best_fact = max(
        candidates,
        key=lambda item: (
            float(getattr(item[0], "timestamp", 0.0) or 0.0),
            float(getattr(item[0], "trust", 0.0) or 0.0),
        ),
    )
    slot_label = target_slot.replace("_", " ")
    fact_value = str(getattr(best_fact, "value", "") or "").strip()
    fact_text = str(getattr(best_mem, "text", "") or "").strip()
    trust = float(getattr(best_mem, "trust", 0.0) or 0.0)

    if not fact_value or not fact_text:
        return None
    return (
        f"I know that because you told me your {slot_label} is {fact_value}. "
        f"I have that stored from: \"{fact_text}\" (trust: {trust:.2f})."
    )


def _generic_meta_provenance_answer() -> str:
    return (
        "I remember this by storing your confirmed facts in memory and retrieving them when they're relevant. "
        "Facts about you come from what you've told me, while my assistant identity comes from my configured system role. "
        "If those records conflict, I disclose the conflict instead of silently picking a winner."
    )


# ---------------------------------------------------------------------------
# Personal-fact bundle helpers
# ---------------------------------------------------------------------------


def _extract_personal_fact_bundle_slots(text: str) -> List[str]:
    """Detect bundled user-fact questions that ask for multiple personal slots."""
    t = (text or "").strip().lower()
    if not t or len(t) > 500:
        return []

    slots: List[str] = []
    if re.search(r"\b(what('?s| is) my name|my name|who am i)\b", t):
        slots.append("name")
    if ("favorite" in t or "favourite" in t) and ("color" in t or "colour" in t):
        slots.append("favorite_color")
    if ("favorite" in t or "favourite" in t) and ("drink" in t or "beverage" in t):
        slots.append("favorite_drink")

    deduped = list(dict.fromkeys(slots))
    return deduped if len(deduped) >= 2 else []


def _personal_fact_slot_label(slot: str) -> str:
    labels = {
        "name": "Name",
        "favorite_color": "Favorite color",
        "favorite_drink": "Favorite drink",
    }
    return labels.get(slot, slot.replace("_", " ").title())


def _normalize_fact_value(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _answer_personal_fact_bundle(text: str, engine: "Any", thread_id: str) -> str:
    """Answer bundled personal-fact questions field-by-field with conflict handling."""
    requested_slots = _extract_personal_fact_bundle_slots(text)
    if not requested_slots:
        return ""

    effective_facts: Dict[str, Dict[str, Any]] = {}
    try:
        if hasattr(engine, "get_effective_user_facts"):
            effective_facts = engine.get_effective_user_facts(thread_id=thread_id) or {}
    except Exception as e:
        logger.warning("[PERSONAL_FACT_BUNDLE] effective fact lookup failed: %s", e)

    lines = ["Here's what I can answer from memory, field by field:"]

    for slot in requested_slots:
        label = _personal_fact_slot_label(slot)
        current_fact = effective_facts.get(slot) or {}
        current_value = _normalize_fact_value(current_fact.get("value"))

        history_values: List[str] = []
        try:
            history_rows = engine.get_fact_history(slot, thread_id=thread_id) if hasattr(engine, "get_fact_history") else []
        except Exception as e:
            logger.debug("[PERSONAL_FACT_BUNDLE] history lookup failed for %s: %s", slot, e)
            history_rows = []

        seen_values: set[str] = set()
        if current_value:
            seen_values.add(current_value.lower())
            history_values.append(current_value)

        for row in history_rows or []:
            hist_value = _normalize_fact_value((row or {}).get("value"))
            if not hist_value:
                continue
            hist_norm = hist_value.lower()
            if hist_norm in seen_values:
                continue
            seen_values.add(hist_norm)
            history_values.append(hist_value)

        if current_value and len(history_values) <= 1:
            lines.append(f"- {label}: {current_value}")
            continue

        if current_value and len(history_values) > 1:
            others = [v for v in history_values if v.lower() != current_value.lower()]
            if others:
                lines.append(
                    f"- {label}: conflicted. Current strongest value is {current_value}, "
                    f"but I also have {', '.join(others[:4])} on record."
                )
            else:
                lines.append(f"- {label}: {current_value}")
            continue

        if len(history_values) > 1:
            lines.append(
                f"- {label}: conflicted. I have multiple values on record: "
                f"{', '.join(history_values[:5])}."
            )
            continue

        if len(history_values) == 1:
            lines.append(f"- {label}: {history_values[0]}")
            continue

        lines.append(f"- {label}: I don't have a grounded value for that yet.")

    lines.append("")
    lines.append("I'm answering each field independently so one conflict doesn't wipe out the rest.")
    return "\n".join(lines)
