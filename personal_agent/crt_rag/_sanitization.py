from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Dict, List, Any, Optional
if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

from ..fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)


def sanitize_memory_denial(engine: "CRTEnhancedRAG", *, answer: str, has_memory_context: bool) -> str:
    """If memory context exists, avoid self-contradictory 'no memories/first chat' claims.

    This is a lightweight post-processing step to keep the assistant's surface text
    consistent with the CRT metadata we return (retrieved/prompt memories).
    """
    a = (answer or "")
    if not a or not has_memory_context:
        return a

    # Normalize some frequent denial patterns.
    repl = [
        ("this is our first conversation", "in this conversation so far"),
        ("this is the start of our conversation", "so far in this conversation"),
        ("since this is our first conversation", "so far in this conversation"),
        ("we just started the conversation", "so far in this conversation"),
        ("we just started talking", "so far in this conversation"),
        ("my memory is empty", "my stored memory is limited so far"),
        ("my trust-weighted memory is empty", "my trust-weighted memory is limited so far"),
        ("i don't have any memories", "i don't have much stored yet"),
        ("i do not have any memories", "i don't have much stored yet"),
        ("i have no memories", "i don't have much stored yet"),
    ]

    out = a
    low = out.lower()
    for old, new in repl:
        if old in low:
            # Case-insensitive replace (simple, conservative).
            out = re.sub(re.escape(old), new, out, flags=re.I)
            low = out.lower()

    return out


def sanitize_unsupported_memory_claims(
    engine: "CRTEnhancedRAG",
    *,
    answer: str,
    prompt_docs: List[Dict[str, Any]],
    user_query: str = "",
    inferred_slots: Optional[List[str]] = None,
) -> str:
    """Remove unsupported personal-fact claims framed as memory.

    Goal: avoid outputs like "I remember ... I work at X" when X is not actually
    present in the retrieved/resolved memory facts.

    This is intentionally conservative and only activates when the answer contains
    a strong memory-claim phrase.
    """
    if not answer or not answer.strip():
        return answer

    # Keep deterministic contradiction-status answers intact.
    if user_query and engine._is_contradiction_status_request(user_query):
        return answer

    t = answer.lower()
    memory_claim = any(
        p in t
        for p in (
            "i remember",
            "i recall",
            "i have a memory",
            "i have it noted",
            "i have you down",
            "i have stored",
            "in my memory",
            "in my notes",
            "i've got it stored",
            "i've got you stored",
            "i've got it noted",
            "i've got you down",
        )
    )
    if not memory_claim:
        return answer

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    # Parse supported FACT values from resolved prompt docs.
    supported_by_slot: Dict[str, set] = {}
    fact_re = re.compile(r"^\s*fact:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$", re.I)
    for d in (prompt_docs or []):
        txt = str((d or {}).get("text") or "")
        m = fact_re.match(txt)
        if not m:
            continue
        slot = m.group(1).strip().lower()
        val = m.group(2).strip()
        if not slot or not val:
            continue
        supported_by_slot.setdefault(slot, set()).add(_norm(val))

    # Extract fact claims from the answer (first-person patterns).
    claimed = extract_fact_slots(answer) or {}
    if not claimed:
        return answer

    # Identify unsupported claimed slot-values.
    unsupported: Dict[str, str] = {}
    for slot, fact in claimed.items():
        slot_l = str(slot).lower()
        supported = supported_by_slot.get(slot_l) or set()
        if fact is None:
            continue
        if not supported or str(getattr(fact, "normalized", "")) not in supported:
            unsupported[slot_l] = str(getattr(fact, "value", ""))

    if not unsupported:
        return answer

    # Drop lines that contain memory-claim language or the unsupported values.
    bad_value_res = [re.compile(re.escape(v), re.I) for v in unsupported.values() if v]
    memory_line_re = re.compile(
        r"\b(i\s+(remember|recall)|i\s+have\s+(a\s+)?memory|i\s+have\s+it\s+noted|i\s+have\s+you\s+down|i\s+have\s+stored|in\s+my\s+(memory|notes)|i'?ve\s+got\s+(it|you)\s+(stored|noted|down))\b",
        re.I,
    )

    kept_lines: List[str] = []
    for line in answer.splitlines():
        if memory_line_re.search(line):
            continue
        if any(r.search(line) for r in bad_value_res):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines).strip()
    first_slot = next(iter(unsupported.keys()))
    first_slot_label = first_slot.replace("_", " ")
    if cleaned:
        return cleaned

    inferred = {str(s).strip().lower() for s in (inferred_slots or []) if str(s).strip()}
    ql = (user_query or "").strip().lower()
    slot_aliases: Dict[str, List[str]] = {
        "employer": ["employer", "work", "job", "company"],
        "name": ["name", "called"],
        "location": ["location", "live", "city", "state", "country"],
        "title": ["title", "role", "position"],
    }
    aliases = slot_aliases.get(first_slot, [first_slot_label, first_slot])
    explicit_slot_request = (first_slot in inferred) or any(a in ql for a in aliases)

    if explicit_slot_request:
        return (
            f"I don't have a reliable stored memory for your {first_slot_label} yet  -  "
            "if you tell me, I can remember it going forward."
        )

    return "I can't verify that detail from stored memory yet."
