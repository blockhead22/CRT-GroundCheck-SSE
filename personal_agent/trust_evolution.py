"""
Trust Evolution Module

Extracted from crt_rag.py - handles grounding score computation,
uncertainty determination, and uncertainty response generation.

These are the trust-related evaluation functions that determine
how confident the system should be in its responses.
"""

import re
import logging
from typing import List, Dict, Optional, Any, Tuple

from .crt_core import MemorySource
from .crt_memory import MemoryItem
from .fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)


def compute_grounding_score(
    answer: str,
    retrieved_memories: List[Tuple[MemoryItem, float]],
) -> float:
    """Compute grounding score (0-1) for an answer based on memory overlap."""
    if not retrieved_memories or not answer:
        return 0.0

    answer_lower = answer.lower().strip()
    memory_text = " ".join(mem.text.lower() for mem, _ in retrieved_memories[:3])

    # Slot-match shortcut: structured answers like
    #   name: sarah
    #   masters school: mit
    # should score 1.0 if they exactly match the retrieved slot values.
    try:
        slot_label_map = {
            "name": "name",
            "employer": "employer",
            "work": "employer",
            "company": "employer",
            "job": "title",
            "title": "title",
            "location": "location",
            "city": "location",
            "first language": "first_language",
            "first_language": "first_language",
            "masters school": "masters_school",
            "master's school": "masters_school",
            "masters_school": "masters_school",
            "undergrad school": "undergrad_school",
            "undergraduate school": "undergrad_school",
            "undergrad_school": "undergrad_school",
            "programming years": "programming_years",
            "years programming": "programming_years",
            "programming_years": "programming_years",
            "remote preference": "remote_preference",
            "remote_preference": "remote_preference",
        }

        structured: List[Tuple[str, str]] = []
        for ln in (answer or "").splitlines():
            m = re.match(r"^\s*([A-Za-z_ ][A-Za-z_ ]{0,40})\s*:\s*(.+?)\s*$", ln)
            if not m:
                continue
            raw_label = (m.group(1) or "").strip().lower()
            raw_value = (m.group(2) or "").strip()
            if not raw_label or not raw_value:
                continue
            slot = slot_label_map.get(raw_label) or slot_label_map.get(raw_label.replace("_", " "))
            if not slot:
                continue
            structured.append((slot, raw_value))

        if structured:
            # Build best-effort retrieved slot values.
            retrieved_slot_norms: Dict[str, set] = {}
            for mem, _s in retrieved_memories[:5]:
                if getattr(mem, 'source', None) in (MemorySource.SYSTEM, MemorySource.FALLBACK):
                    continue
                facts = extract_fact_slots(getattr(mem, "text", "") or "") or {}
                for slot, f in facts.items():
                    s = str(slot).strip().lower()
                    norm = str(getattr(f, "normalized", "") or "").strip().lower()
                    if not s or not norm:
                        continue
                    retrieved_slot_norms.setdefault(s, set()).add(norm)

            def _norm_answer_value(slot: str, v: str) -> str:
                vv = re.sub(r"\s+", " ", (v or "").strip().lower())
                if slot == "remote_preference":
                    if "remote" in vv:
                        return "remote"
                    if "office" in vv or "in the office" in vv:
                        return "office"
                return vv

            matches = 0
            for slot, raw_value in structured:
                want = _norm_answer_value(slot, raw_value)
                have = retrieved_slot_norms.get(slot, set())
                if want and want in have:
                    matches += 1

            if matches == len(structured) and matches > 0:
                return 1.0
    except Exception:
        # Non-fatal: fall back to word-overlap grounding.
        pass

    # EXACT MATCH gets 1.0 immediately - fixes brevity penalty
    for mem, _ in retrieved_memories[:3]:
        mem_text_lower = mem.text.lower().strip()
        if answer_lower == mem_text_lower:
            return 1.0
        if answer_lower in mem_text_lower and len(answer_lower) > 2:
            if mem_text_lower not in answer_lower or answer_lower == mem_text_lower:
                return 1.0

    # Short answers: check substring match
    if len(answer) < 30:
        if answer_lower in memory_text:
            return 1.0
        answer_words = set(answer_lower.split())
        memory_words = set(memory_text.split())
        if answer_words and len(answer_words & memory_words) == len(answer_words):
            return 0.95

    # Longer answers: check if MEMORY appears in ANSWER (core fact present)
    for mem, score in retrieved_memories[:3]:
        mem_text_lower = mem.text.lower().strip()
        mem_words = set(w for w in mem_text_lower.split() if len(w) > 3)
        answer_words_set = set(answer_lower.split())
        if mem_words:
            mem_in_answer_ratio = len(mem_words & answer_words_set) / len(mem_words)
            if mem_in_answer_ratio >= 0.6:
                return 0.85

    answer_words = set(answer_lower.split())
    memory_words = set(memory_text.split())

    if not answer_words:
        return 0.0

    overlap = len(answer_words & memory_words)
    overlap_ratio = overlap / len(answer_words)

    has_quotes = '"' in answer or "'" in answer
    quote_bonus = 0.15 if has_quotes else 0.0

    if overlap_ratio >= 0.4:
        grounding_score = min(1.0, overlap_ratio + 0.2)
    else:
        grounding_score = overlap_ratio + quote_bonus

    return max(0.0, min(1.0, grounding_score))


def should_express_uncertainty(
    retrieved: List[Tuple[MemoryItem, float]],
    contradictions_count: int = 0,
    gates_passed: bool = False,
) -> Tuple[bool, str]:
    """
    Determine if system should express explicit uncertainty.

    Returns: (should_express_uncertainty, reason)

    Express uncertainty when:
    1. Multiple high-trust memories conflict (unresolved contradictions)
    2. Trust scores are too close (no clear winner) - DISABLED
    3. Gates failed AND unresolved contradictions exist
    4. Max trust below threshold (no confident belief)
    """
    if not retrieved:
        return False, ""

    # Check 1: Unresolved contradictions
    if contradictions_count > 0:
        return True, f"I have {contradictions_count} unresolved contradictions about this"

    # Check 2: DISABLED - was triggering too early

    # Check 3: Max trust below confidence threshold
    max_trust = max(mem.trust for mem, _ in retrieved)
    if max_trust < 0.6:
        return True, f"My confidence in this information is low (trust={max_trust:.2f})"

    # Check 4: Gates failed with moderate contradiction
    if not gates_passed and contradictions_count > 0:
        return True, "I cannot confidently reconstruct a coherent answer from my memories"

    return False, ""


def generate_uncertain_response(
    user_query: str,
    retrieved: List[Tuple[MemoryItem, float]],
    reason: str,
    runtime_config: Optional[Dict[str, Any]] = None,
    recommended_next_action: Optional[Dict[str, Any]] = None,
    conflict_beliefs: Optional[List[str]] = None,
) -> str:
    """
    Generate explicit uncertainty response.

    This is a FIRST-CLASS response state, not a fallback.
    """
    beliefs: List[str] = []

    if conflict_beliefs:
        beliefs.extend([b.strip() for b in conflict_beliefs[:6] if (b or "").strip()])
    else:
        for mem, _score in retrieved[:3]:
            t = (mem.text or "").strip()
            if t:
                beliefs.append(f"- {t}")

    beliefs_text = "\n".join(beliefs) if beliefs else "- (no clear memories)"

    ask = "Can you help clarify?"
    if recommended_next_action and recommended_next_action.get("action_type") == "ask_user":
        q = (recommended_next_action.get("question") or "").strip()
        if q:
            ask = q

    conflict_warning_enabled = True
    try:
        conflict_warning_enabled = bool(((runtime_config or {}).get("conflict_warning") or {}).get("enabled", True))
    except Exception:
        conflict_warning_enabled = True

    if conflict_warning_enabled:
        header = (
            "I need to be honest about my uncertainty here.\n\n"
            "I might be wrong because I have conflicting information in our chat history.\n\n"
        )
        notes_label = "Here are the conflicting notes I have:"
    else:
        header = "I need to be honest about my uncertainty here.\n\n"
        notes_label = "What I have in memory:"

    continue_line = (
        "\nIf you want, I can still help with other parts of your question that don't depend on that fact - "
        "tell me what you'd like to focus on.\n"
    )

    return (
        header
        + f"{reason}\n\n"
        + f"{notes_label}\n{beliefs_text}\n\n"
        + "I cannot give you a confident answer until we resolve this.\n"
        + continue_line
        + f"{ask}"
    )
