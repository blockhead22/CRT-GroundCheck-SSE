"""CRT RAG — contradiction detection and resolution.

Delegate functions extracted from CRTEnhancedRAG; each takes
``engine`` as its first argument in place of ``self``.
"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports used by the bodies (non-lazy)
# ---------------------------------------------------------------------------
import numpy as np

from personal_agent.exceptions import log_swallowed_exception
from personal_agent.crt_core import MemorySource, SSEMode, encode_vector
from personal_agent.crt_memory import MemoryItem
from personal_agent.crt_ledger import (
    ContradictionEntry,
    ContradictionStatus,
    ContradictionType,
)
from personal_agent.fact_slots import (
    extract_fact_slots,
    detect_correction_type,
    is_explicit_name_declaration_text,
    names_look_equivalent,
)
from personal_agent.disclosure_policy import DisclosureAction
from personal_agent.resolution_patterns import has_resolution_intent, get_matched_patterns
from personal_agent.contradiction_trace_logger import get_trace_logger
from sse.contradictions import heuristic_contradiction

# Module-level constants (mirrored from crt_rag.py)
_NL_RESOLUTION_STOPWORDS = {
    'i', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'my', 'the', 'a', 'an', 'at', 'in', 'on', 'to',
}
_UNSTRUCTURED_SLOT_NAME = '_unstructured_'
RESOLVED_CONTRADICTION_CONFIDENCE = 0.85
SSE_CONTRADICTION_RESULT = 'contradiction'
_EXTRACTION_STOPWORDS = [
    "a", "an", "the", "as", "is", "was", "at", "in", "on", "for",
]


# ======================================================================
# _classify_contradiction_severity
# ======================================================================

def _classify_contradiction_severity(
    engine: "CRTEnhancedRAG",
    open_contradictions: List,
    query_slots: Set[str],
) -> str:
    """Classify contradiction severity: blocking/note/none."""
    if not open_contradictions:
        return "none"

    # Check if any contradictions affect the query slots
    for contra in open_contradictions:
        affects_slots_str = getattr(contra, "affects_slots", None)
        if affects_slots_str and query_slots:
            affects_slots = set(affects_slots_str.split(","))
            if affects_slots & query_slots:
                return "blocking"

    return "note"


# ======================================================================
# _infer_contradiction_goals_for_query
# ======================================================================

def _infer_contradiction_goals_for_query(
    engine: "CRTEnhancedRAG",
    user_query: str,
    retrieved: List[Tuple[MemoryItem, float]],
    inferred_slots: Optional[List[str]] = None,
    limit: int = 5,
) -> Tuple[List[Dict[str, Any]], Optional[List[str]]]:
    """Infer actionable "next steps" from open hard conflicts.

    For Milestone M2, we keep this intentionally minimal and deterministic:
    - Only hard CONFLICT contradictions become goals.
    - The default action is to ask the user a targeted clarifying question.

    Returns: (goals, conflict_beliefs)
    """
    if not retrieved:
        retrieved_ids: set[str] = set()
    else:
        retrieved_ids = {mem.memory_id for mem, _ in retrieved}

    goals: List[Dict[str, Any]] = []
    conflict_beliefs: List[str] = []

    def _same_identity_value(slot: str, a: str, b: str) -> bool:
        a_norm = re.sub(r"\s+", " ", str(a or "").strip().lower())
        b_norm = re.sub(r"\s+", " ", str(b or "").strip().lower())
        if not a_norm or not b_norm:
            return False
        if a_norm == b_norm:
            return True
        if slot != "name":
            return False
        # Name alias handling: "nick" vs "nick block", or first-name prefix with same last name.
        if a_norm.startswith(b_norm) or b_norm.startswith(a_norm):
            return True
        a_parts = [p for p in a_norm.split(" ") if p]
        b_parts = [p for p in b_norm.split(" ") if p]
        if len(a_parts) >= 2 and len(b_parts) >= 2:
            a_first, a_last = a_parts[0], a_parts[-1]
            b_first, b_last = b_parts[0], b_parts[-1]
            if a_last == b_last and (a_first.startswith(b_first) or b_first.startswith(a_first)):
                return True
        return False

    open_contras = engine.ledger.get_open_contradictions(limit=50)
    for contra in open_contras:
        ctype = str(getattr(contra, "contradiction_type", "")).strip().lower()
        if ctype not in {ContradictionType.CONFLICT, ContradictionType.REVISION}:
            continue

        # Check affects_slots for fast filtering
        affects_slots_str = getattr(contra, "affects_slots", None)
        if affects_slots_str and inferred_slots:
            affects_slots_set = set(affects_slots_str.split(","))
            if not (affects_slots_set & set(inferred_slots)):
                # Contradiction doesn't affect slots relevant to this query
                continue

        old_mem = engine.memory.get_memory_by_id(contra.old_memory_id)
        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
        if old_mem is None or new_mem is None:
            continue

        # Relevance: either overlaps retrieved, or overlaps the slots we think the user asked about.
        is_related_by_retrieval = bool({contra.old_memory_id, contra.new_memory_id} & retrieved_ids)

        old_facts = extract_fact_slots(old_mem.text) or {}
        new_facts = extract_fact_slots(new_mem.text) or {}
        shared_slots = set(old_facts.keys()) & set(new_facts.keys())

        for slot in sorted(shared_slots):
            old_fact = old_facts.get(slot)
            new_fact = new_facts.get(slot)
            if old_fact is None or new_fact is None:
                continue

            if _same_identity_value(slot, str(getattr(old_fact, "value", "")), str(getattr(new_fact, "value", ""))):
                continue

            is_related_by_slot = bool(inferred_slots) and slot in set(inferred_slots or [])
            if not (is_related_by_retrieval or is_related_by_slot):
                continue

            # Provide both sides as explicit beliefs (user-facing; no internal scores).
            conflict_beliefs.append(f"- {old_mem.text}")
            conflict_beliefs.append(f"- {new_mem.text}")

            slot_name = slot.replace("_", " ")
            old_val = str(old_fact.value)
            new_val = str(new_fact.value)
            option_values: List[str] = []
            for candidate in (new_val, old_val):
                if candidate and not any(_same_identity_value(slot, candidate, v) for v in option_values):
                    option_values.append(candidate)
            if len(option_values) <= 1:
                continue

            goals.append(
                {
                    "action_type": "ask_user",
                    "slot": slot,
                    "ledger_id": contra.ledger_id,
                    "options": option_values,
                    "question": (
                        f"I have conflicting memories about your {slot_name}. "
                        f"Which is correct now: {' or '.join(option_values)}?"
                    ),
                    "reason": "open_conflict",
                }
            )

            if len(goals) >= limit:
                break

        if len(goals) >= limit:
            break

    # De-dup conflict belief lines while preserving order.
    seen = set()
    dedup_beliefs: List[str] = []
    for b in conflict_beliefs:
        if b not in seen:
            dedup_beliefs.append(b)
            seen.add(b)

    return goals, dedup_beliefs


# ======================================================================
# _extract_value_from_memory_text
# ======================================================================

def _extract_value_from_memory_text(engine: "CRTEnhancedRAG", text: str) -> Optional[str]:
    """
    Extract the factual value from a memory text.

    Examples:
        "FACT: name = Nick Block" -> "Nick Block"
        "FACT: employer = Microsoft" -> "Microsoft"
        "I work at Microsoft" -> "Microsoft"
        "I work at Microsoft as a senior developer" -> "Microsoft"
        "I work at Amazon Web Services" -> "Amazon Web Services"
        "My name is Sarah" -> "Sarah"
        "I've been programming for 8 years" -> "8 years"

    Args:
        text: Memory text

    Returns:
        Extracted value or None
    """
    # PRIORITY 1: Handle structured FACT/PREF format
    # Pattern: "FACT: slot = value" or "PREF: slot = value"
    fact_match = re.search(r"(?:FACT|PREF):\s*\w+\s*=\s*(.+)", text, re.IGNORECASE)
    if fact_match:
        return fact_match.group(1).strip()

    # PRIORITY 2: Use fact_slots extraction for structured data
    try:
        facts = extract_fact_slots(text)
        if facts:
            # Return the first extracted value
            for slot, fact in facts.items():
                if hasattr(fact, 'value') and fact.value is not None:
                    value = fact.value
                    # For duration/year slots, format as "X years" if numeric
                    if slot in ('programming_years', 'age') and isinstance(value, (int, float)):
                        return f"{int(value)} years"
                    return value
    except Exception as e:
        log_swallowed_exception("crt_rag._extract_value_from_memory_text.fact_slots", e)

    # PRIORITY 3: Common natural language patterns
    patterns = [
        # Employer - match company name (1-3 words), stop at role indicators
        r"(?:work|working) (?:at|for) ((?:\w+(?:\s+\w+){0,2}))(?:\s+(?:as|in|on|for|with|doing)|[,.]|$)",
        # Name - match full name (1-3 words)
        r"(?:my )?name is ((?:\w+(?:\s+\w+){0,2}))(?:[,.]|$)",
        # "I am <name>" pattern
        r"(?:I am|I'm)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}))(?:[,.]|$)",
        # Experience - match the duration
        r"(?:programming|coding) for (\d+\s+\w+)",  # e.g., "8 years"
        # Location - match city/place (1-3 words) using character class for case flexibility
        r"live in ((?:[A-Za-z]+(?:\s+[A-Za-z]+){0,2}))(?:[,.]|$)",
        # Origin - same pattern as location
        r"from ((?:[A-Za-z]+(?:\s+[A-Za-z]+){0,2}))(?:[,.]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: return last capitalized word or number
    words = text.split()
    for word in reversed(words):
        if word and (word[0].isupper() or word.isdigit()):
            # Skip common stop words
            if word.lower() in _EXTRACTION_STOPWORDS:
                continue
            return word

    return None


# ======================================================================
# _build_caveat_disclosure
# ======================================================================

def _build_caveat_disclosure(
    engine: "CRTEnhancedRAG",
    resolved_memory: MemoryItem,
    contradictions: List[ContradictionEntry],
) -> str:
    """
    Build caveat text acknowledging the contradiction.

    Args:
        resolved_memory: The memory we're asserting as true
        contradictions: List of contradictions involved

    Returns:
        Caveat string like "(changed from X)" or "(most recent update)"
    """
    # Extract old values with deduplication
    old_values = []
    seen = set()  # Track seen values to avoid duplicates

    for contra in contradictions:
        old_mem = _get_memory_by_id(engine, contra.old_memory_id)
        if old_mem and old_mem.memory_id != resolved_memory.memory_id:
            # Extract just the value part from the memory text
            old_value = _extract_value_from_memory_text(engine, old_mem.text)
            if old_value and old_value not in seen:
                seen.add(old_value)
                old_values.append(old_value)

    if not old_values:
        return "(most recent update)"

    if len(old_values) == 1:
        return f"(changed from {old_values[0]})"
    else:
        return f"(changed from {', '.join(old_values)})"


# ======================================================================
# _build_mandatory_caveat
# ======================================================================

def _build_mandatory_caveat(
    engine: "CRTEnhancedRAG",
    user_input_kind: str,
    reintroduced_count: int,
    relevant_contradictions: Optional[List] = None,
) -> str:
    """
    Build a specific caveat based on contradiction context.

    Handles both dict-based and object-based contradiction representations.
    """
    is_question = user_input_kind in ("question", "instruction")

    # For questions, use simpler temporal caveat
    if is_question:
        return "(most recent update)"

    # For assertions, try to be specific about what changed
    if relevant_contradictions and len(relevant_contradictions) > 0:
        contra = relevant_contradictions[0]

        # Support both dict and object access patterns
        if isinstance(contra, dict):
            old_val = contra.get('old_value', '') or contra.get('old_text', '')
            new_val = contra.get('new_value', '') or contra.get('new_text', '')
        else:
            old_val = getattr(contra, 'old_value', '') or getattr(contra, 'old_text', '')
            new_val = getattr(contra, 'new_value', '') or getattr(contra, 'new_text', '')

        if old_val and new_val:
            # Truncate for readability
            old_short = str(old_val)[:30] + '...' if len(str(old_val)) > 30 else str(old_val)
            new_short = str(new_val)[:30] + '...' if len(str(new_val)) > 30 else str(new_val)
            return f"(changed from {old_short} to {new_short})"

    # Fallback: generic but clear
    if reintroduced_count == 1:
        return "(note: conflicting information exists)"
    else:
        return f"(note: {reintroduced_count} conflicting claims exist)"


# ======================================================================
# _answer_has_caveat
# ======================================================================

def _answer_has_caveat(engine: "CRTEnhancedRAG", answer: str) -> bool:
    """Check if an answer already includes contradiction caveat language.

    Uses same patterns as stress test to ensure consistency.
    """
    if not answer:
        return False
    # Match patterns from crt_stress_test.py for consistency
    caveat_patterns = [
        # Original exact matches
        r"\b(most recent|latest|conflicting|though|however|according to)\b",
        # Update/correction family
        r"\b(updat(e|ed|ing)|correct(ed|ing|ion)?|clarif(y|ied|ying))\b",
        # Temporal references
        r"\b(earlier|previously|before|prior|former)\b",
        # Acknowledgment/confirmation
        r"\b(mentioned|noted|stated|said|established)\b",
        # Change/revision family
        r"\b(chang(e|ed|ing)|revis(e|ed|ing)|adjust(ed|ing)?|modif(y|ied|ying))\b",
        # Contradiction signals
        r"\b(actually|instead|rather|in fact)\b",
        # Explicit caveat formats
        r"\(changed from",
        r"\(most recent",
        r"\(updated",
        # Additional natural disclosure patterns
        r"\bnow\b.*\b(was|were)\b",
        r"\b(versus|vs|compared to)\b",
        r"\bno longer\b",
        r"\bas of\b",
    ]
    return bool(re.search("|".join(caveat_patterns), answer, flags=re.IGNORECASE))


# ======================================================================
# _resolve_contradiction_assertively
# ======================================================================

def _resolve_contradiction_assertively(
    engine: "CRTEnhancedRAG",
    contradictions: List[ContradictionEntry],
    blocking_data: Optional[List[Dict[str, Any]]] = None,
) -> Optional[MemoryItem]:
    """
    Automatically resolve contradiction by picking highest trust + most recent claim.

    Resolution strategy:
    1. Sort by trust score (primary)
    2. Break ties with timestamp (secondary)
    3. Return winner

    Args:
        contradictions: List of contradicting memory items
        blocking_data: Optional list of dicts with old_value/new_value for fallback

    Returns:
        The winning memory item to assert
    """
    if not contradictions:
        return None

    # Get all involved memories
    all_memories = []
    for contra in contradictions:
        # Each contradiction has old_memory_id and new_memory_id
        old_mem = _get_memory_by_id(engine, contra.old_memory_id)
        new_mem = _get_memory_by_id(engine, contra.new_memory_id)
        if old_mem:
            all_memories.append(old_mem)
        if new_mem:
            all_memories.append(new_mem)

    # Remove duplicates
    seen = set()
    unique_memories = []
    for mem in all_memories:
        if mem.memory_id not in seen:
            seen.add(mem.memory_id)
            unique_memories.append(mem)

    unique_memories = [
        mem for mem in unique_memories
        if engine.memory.can_affect_contradiction_resolution(mem)
    ]

    if not unique_memories:
        # Fallback: Use blocking_data if memory lookup failed
        if blocking_data:
            logger.info("[CONTRADICTION_RESOLVED] Memory lookup failed, using blocking_data fallback")
            # Pick newest value (most recent is preferred)
            # blocking_data has structure: {'slot': str, 'old_value': str, 'new_value': str, ...}
            newest = next(
                (
                    item for item in (blocking_data or [])
                    if bool(item.get("new_memory_authoritative"))
                ),
                None,
            )
            if newest and 'new_value' in newest:
                # Create synthetic memory item from new_value
                synthetic_mem = MemoryItem(
                    memory_id=f"synthetic_resolved_{int(time.time())}",
                    vector=encode_vector(newest['new_value']),
                    text=newest['new_value'],
                    timestamp=time.time(),
                    confidence=RESOLVED_CONTRADICTION_CONFIDENCE,
                    trust=0.85,
                    source=MemorySource.USER,
                    sse_mode=SSEMode.LOSSLESS,
                )
                return synthetic_mem
        return None

    # Sort by trust (primary), then timestamp (secondary)
    sorted_memories = sorted(
        unique_memories,
        key=lambda m: (m.trust, m.timestamp),
        reverse=True,  # Highest trust + most recent first
    )

    winner = sorted_memories[0]

    # Add diagnostic logging
    logger.info(f"[CONTRADICTION_RESOLVED] Asserting: {winner.text[:60]}")
    logger.info(f"  Trust: {winner.trust}, Timestamp: {winner.timestamp}")
    logger.info(f"  Superseded {len(sorted_memories) - 1} other claim(s)")

    return winner


# ======================================================================
# _check_contradiction_gates
# ======================================================================

def _check_contradiction_gates(
    engine: "CRTEnhancedRAG",
    user_query: str,
    inferred_slots: List[str],
    user_input_kind: Optional[str] = None,
) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
    """
    Bug 2 Fix: Check for unresolved contradictions that should block response.

    This implements gate blocking - preventing confident answers when
    contradictions exist in the queried facts.

    Args:
        user_query: User's query text
        inferred_slots: Slots the query is asking about
        user_input_kind: High-level classification of the user input

    Returns:
        (gates_passed, clarification_message, contradictions_list)
    """
    if not inferred_slots:
        # No specific slots mentioned, don't block
        return True, None, []

    # Get open contradictions from ledger
    try:
        open_contradictions = engine.ledger.get_open_contradictions(limit=100)
    except Exception as e:
        logger.warning(f"[GATE_CHECK] Failed to get open contradictions: {e}")
        return True, None, []

    if not open_contradictions:
        return True, None, []

    # Check if any open contradictions affect the queried slots
    blocking_contradictions = []

    for contra in open_contradictions:
        # Get affected slots from contradiction
        affects_slots = getattr(contra, 'affects_slots', None)
        if not affects_slots:
            continue

        affected_slot_list = [s.strip() for s in affects_slots.split(',')]

        # Check if any affected slot matches queried slots
        for affected_slot in affected_slot_list:
            if affected_slot in inferred_slots:
                # Load memory texts to build clarification
                try:
                    old_mem = _get_memory_by_id(engine, contra.old_memory_id)
                    new_mem = _get_memory_by_id(engine, contra.new_memory_id)

                    if old_mem and new_mem:
                        old_authoritative = engine.memory.can_answer_user_fact(old_mem)
                        new_authoritative = engine.memory.can_answer_user_fact(new_mem)
                        if old_authoritative ^ new_authoritative:
                            continue
                        blocking_contradictions.append({
                            'ledger_id': contra.ledger_id,
                            'old_memory_id': contra.old_memory_id,
                            'new_memory_id': contra.new_memory_id,
                            'slot': affected_slot,
                            'old_value': old_mem.text,
                            'new_value': new_mem.text,
                            'category': contra.contradiction_type,
                            'disposition': getattr(contra, 'disposition', None),
                            'old_memory_authoritative': old_authoritative,
                            'new_memory_authoritative': new_authoritative,
                        })
                except Exception as e:
                    logger.warning(f"[GATE_CHECK] Failed to load contradiction memories: {e}")
                    continue

    if not blocking_contradictions:
        return True, None, []

    # Check if any contradiction is a hard CONFLICT type (mutually exclusive facts)
    # Hard CONFLICTs should NOT be auto-resolved - we should ask the user for clarification
    has_hard_conflict = any(
        bc.get('category') == ContradictionType.CONFLICT or bc.get('category') == 'conflict'
        for bc in blocking_contradictions
    )

    if has_hard_conflict:
        # Don't auto-resolve CONFLICT contradictions - fall through to uncertainty response
        # Return gates NOT passed so the uncertainty response path is triggered
        logger.info(f"[GATE_CHECK] Hard CONFLICT detected - not auto-resolving, will ask user for clarification")
        return False, None, blocking_contradictions

    # Phase G1: disposition-aware gate -- held/evolving contradictions should NOT
    # be assertively resolved. They represent genuine complexity.
    has_held_or_evolving = any(
        bc.get('disposition') in ('held', 'evolving')
        for bc in blocking_contradictions
    )
    if has_held_or_evolving:
        logger.info("[GATE_CHECK] Held/evolving disposition -- presenting both sides")
        return False, None, blocking_contradictions

    # SPRINT 1: Assertive contradiction resolution instead of passive questioning
    # Only for non-CONFLICT contradictions (REVISION, REFINEMENT, TEMPORAL)
    # Convert blocking_contradictions back to ContradictionEntry objects
    relevant_contras = []
    for contra in open_contradictions:
        affects_slots = getattr(contra, 'affects_slots', None)
        if affects_slots:
            affected_slot_list = [s.strip() for s in affects_slots.split(',')]
            for affected_slot in affected_slot_list:
                if affected_slot in inferred_slots:
                    relevant_contras.append(contra)
                    break

    # Resolve automatically instead of asking
    resolved_memory = _resolve_contradiction_assertively(engine, relevant_contras, blocking_contradictions)

    if resolved_memory:
        # Extract the answer value
        answer_value = _extract_value_from_memory_text(engine, resolved_memory.text)
        is_question = user_input_kind in ("question", "instruction")

        # Build caveat disclosure from blocking_contradictions if we have it
        if blocking_contradictions:
            # Extract old values with deduplication
            old_values = []
            seen = set()
            for contra in blocking_contradictions:
                old_val = _extract_value_from_memory_text(engine, contra.get('old_value', ''))
                if old_val and old_val not in seen:
                    seen.add(old_val)
                    old_values.append(old_val)

            if is_question:
                caveat = "(most recent update)"
            elif old_values:
                if len(old_values) == 1:
                    caveat = f"(changed from {old_values[0]})"
                else:
                    caveat = f"(changed from {', '.join(old_values)})"
            else:
                caveat = "(most recent update)"
        else:
            # Fallback to building caveat from ledger entries
            caveat = _build_caveat_disclosure(engine, resolved_memory, relevant_contras)

        # Return assertive answer with caveat as clarification
        assertive_answer = f"{answer_value} {caveat}" if answer_value else f"{resolved_memory.text} {caveat}"

        logger.info(f"[GATE_CHECK] OK: Assertively resolved {len(relevant_contras)} contradiction(s): {assertive_answer}")

        # FIX: Return True because contradiction was RESOLVED (not blocked)
        # Gates pass when we successfully resolve with caveat disclosure
        return True, assertive_answer, blocking_contradictions

    # Fallback: Use blocking_contradictions dict data directly
    # Pick new_value (more recent) with caveat disclosure
    if blocking_contradictions:
        first_contra = next(
            (
                contra for contra in blocking_contradictions
                if bool(contra.get('new_memory_authoritative'))
            ),
            None,
        )
        if first_contra is None:
            first_contra = blocking_contradictions[0]
        new_value = _extract_value_from_memory_text(engine, first_contra.get('new_value', ''))
        old_value = _extract_value_from_memory_text(engine, first_contra.get('old_value', ''))

        if new_value and bool(first_contra.get('new_memory_authoritative')):
            is_question = user_input_kind in ("question", "instruction")
            caveat = "(most recent update)"
            if not is_question and old_value:
                caveat = f"(changed from {old_value})"
            assertive_answer = f"{new_value} {caveat}"

            logger.info(f"[GATE_CHECK] OK: Resolved using blocking_data fallback: {assertive_answer}")
            return True, assertive_answer, blocking_contradictions

    # Final fallback to old questioning behavior if all else fails
    messages = []
    for contra in blocking_contradictions[:3]:  # Limit to 3 for readability
        slot = contra['slot']
        old_val = contra['old_value'][:100]  # Truncate for clarity
        new_val = contra['new_value'][:100]

        messages.append(
            f"I have conflicting information about your {slot}:\n"
            f"  - {old_val}\n"
            f"  - {new_val}\n"
            f"Which one is correct?"
        )

    clarification = "\n\n".join(messages)

    logger.info(f"[GATE_CHECK] \u2717  Gates blocked: {len(blocking_contradictions)} contradictions")

    return False, clarification, blocking_contradictions


# ======================================================================
# _get_memory_by_id
# ======================================================================

def _get_memory_by_id(engine: "CRTEnhancedRAG", memory_id: str) -> Optional[MemoryItem]:
    """Get a specific memory by ID."""
    cached = getattr(engine.memory, "_memories_cache", None)
    if isinstance(cached, list) and cached:
        for mem in cached:
            if mem.memory_id == memory_id:
                return mem

    all_memories = engine.memory._load_all_memories()
    for mem in all_memories:
        if mem.memory_id == memory_id:
            return mem
    return None


# ======================================================================
# _trigger_cascade_propagation
# ======================================================================

def _trigger_cascade_propagation(engine: "CRTEnhancedRAG", entry, old_vector, new_vector, pipeline_queue=None):
    """Run cascade propagation after a contradiction is recorded.

    Called on a daemon thread -- does NOT block the response path.
    Updates trust scores on affected downstream memories.
    pipeline_queue: optional Queue for emitting SSE pipeline events from this thread.
    """
    try:
        from personal_agent.memory_graph import get_live_bdg, CASCADE_TRUST_FACTOR

        bdg = get_live_bdg()
        if bdg is None:
            print("[BDG_CASCADE] No LiveBDG available, skipping cascade")
            return

        # Add the contradiction edge to the live graph
        bdg.add_contradiction(entry.old_memory_id, entry.new_memory_id, entry.drift_mean)

        # Run cascade from the OLD memory (the one being revised)
        delta_0 = entry.drift_mean if entry.drift_mean > 0 else 0.5
        result = bdg.run_cascade(entry.old_memory_id, delta_0)

        if result is None or result.total_nodes <= 1:
            print(f"[BDG_CASCADE] No propagation beyond source for {entry.ledger_id}")
            return

        # Apply trust reductions to affected nodes
        skip_ids = {entry.old_memory_id, entry.new_memory_id}
        trust_updates = 0

        # Upgrade #4: Import typed-edge damping coefficients
        try:
            from personal_agent.memory_subsystem.graph import EdgeType, DAMPING_BY_EDGE_TYPE
            _has_typed_damping = True
        except ImportError:
            _has_typed_damping = False

        for node_id, impact in result.impacts.items():
            if node_id in skip_ids:
                continue

            depth = result.depth_map.get(node_id, 0)

            # Upgrade #4: Per-edge-type damping instead of flat CASCADE_TRUST_FACTOR
            edge_type_name = "UNKNOWN"
            if _has_typed_damping:
                # Find the edge connecting to this node in the cascade path
                edge_alpha = CASCADE_TRUST_FACTOR  # fallback
                try:
                    edge_data = bdg.bdg.graph.edges.get((entry.old_memory_id, node_id), {})
                    if not edge_data:
                        # Check reverse direction or path edges
                        for pred in bdg.bdg.graph.predecessors(node_id):
                            edge_data = bdg.bdg.graph.edges.get((pred, node_id), {})
                            if edge_data:
                                break
                    etype_str = edge_data.get("edge_type", "")
                    if etype_str:
                        etype = EdgeType(etype_str) if isinstance(etype_str, str) else etype_str
                        edge_alpha = DAMPING_BY_EDGE_TYPE.get(etype, CASCADE_TRUST_FACTOR)
                        edge_type_name = etype.name if hasattr(etype, 'name') else str(etype)
                except Exception:
                    edge_alpha = CASCADE_TRUST_FACTOR
                trust_delta = impact * edge_alpha
            else:
                edge_alpha = CASCADE_TRUST_FACTOR
                trust_delta = impact * CASCADE_TRUST_FACTOR

            print(f"[CRT_MATH] cascade: {entry.old_memory_id[:8]}->{node_id[:8]}, "
                  f"edge={edge_type_name}, alpha={edge_alpha:.2f}, "
                  f"impact={impact:.3f}, delta_trust={trust_delta:.4f}")

            # Get current trust
            try:
                node_data = bdg.bdg.graph.nodes.get(node_id, {})
                current_trust = node_data.get("trust", 0.5)
                new_trust = max(0.0, current_trust - trust_delta)

                if trust_delta > 0.001:  # only update if meaningful
                    engine.memory.update_trust(
                        node_id,
                        new_trust,
                        reason=f"cascade(depth={depth}, impact={impact:.3f}, edge={edge_type_name}, source={entry.ledger_id[:20]})",
                        drift=impact,
                    )
                    # Update the BDG's cached trust too
                    bdg.bdg.graph.nodes[node_id]["trust"] = new_trust
                    trust_updates += 1
                    print(f"[BDG_CASCADE_TRUST] {node_id}: {current_trust:.3f} -> {new_trust:.3f} "
                          f"(depth={depth}, impact={impact:.3f}, edge={edge_type_name})")
            except Exception as _tu_err:
                print(f"[BDG_CASCADE_TRUST] ERROR updating {node_id}: {_tu_err}")

        # Store cascade metadata on the ledger entry (includes pressure)
        try:
            engine.ledger.update_contradiction_metadata(entry.ledger_id, {
                "cascade_affected_count": result.total_nodes - 1,
                "cascade_depth": result.depth,
                "cascade_total_impact": round(result.total_impact, 4),
                "cascade_trust_updates": trust_updates,
                "cascade_converged": result.converged,
                "cascade_blocked_firewalls": len(result.blocked_by_firewall),
                "cascade_max_pressure": round(result.max_pressure, 4),
                "cascade_avg_pressure": round(result.avg_pressure, 4),
            })
        except Exception as _meta_err:
            print(f"[BDG_CASCADE] WARNING: failed to store cascade metadata: {_meta_err}")

        # Emit SSE pipeline status event so the frontend shows cascade info
        if pipeline_queue is not None:
            try:
                from personal_agent.stream_events import normalize_stream_event
                pipeline_queue.put_nowait(normalize_stream_event({
                    "type": "status",
                    "content": (
                        f"cascade: {result.total_nodes - 1} affected, "
                        f"depth={result.depth}, "
                        f"pressure={result.max_pressure:.2f}"
                    ),
                }))
            except Exception as _sse_err:
                print(f"[BDG_CASCADE] WARNING: failed to emit SSE event: {_sse_err}")

        print(f"[BDG_CASCADE_COMPLETE] {entry.ledger_id}: "
              f"affected={result.total_nodes - 1}, depth={result.depth}, "
              f"impact={result.total_impact:.3f}, pressure={result.max_pressure:.3f}, "
              f"trust_updates={trust_updates}")

    except Exception as e:
        print(f"[BDG_CASCADE] ERROR in cascade propagation: {e}")
        import traceback
        traceback.print_exc()


# ======================================================================
# _record_and_cascade
# ======================================================================

def _record_and_cascade(engine: "CRTEnhancedRAG", **kwargs):
    """Record a contradiction AND trigger cascade propagation on a background thread.

    Drop-in replacement for engine.ledger.record_contradiction(**kwargs).
    Extracts old_vector/new_vector for cascade use, passes all kwargs to ledger.
    Returns the ContradictionEntry (same as record_contradiction).
    """
    # Extract vectors for cascade use (record_contradiction also accepts them)
    old_vector = kwargs.get("old_vector")
    new_vector = kwargs.get("new_vector")
    entry = engine.ledger.record_contradiction(**kwargs)

    if entry is not None:
        # Capture the pipeline event queue from the current thread's contextvar
        # so the cascade background thread can emit SSE events.
        pipeline_queue = None
        try:
            import contextvars as _cv
            # The queue is set by routes/chat.py on the pipeline thread
            from routes.chat import _pipeline_event_queue
            pipeline_queue = _pipeline_event_queue.get(None)
        except Exception:
            pass  # Not in a request context or import unavailable

        import threading as _cascade_t
        _cascade_t.Thread(
            target=_trigger_cascade_propagation,
            args=(engine, entry, old_vector, new_vector, pipeline_queue),
            daemon=True,
            name=f"cascade_{entry.ledger_id[:20]}",
        ).start()
        print(f"[BDG] Cascade thread spawned for {entry.ledger_id}")

    return entry


# ======================================================================
# _check_all_fact_contradictions_ml
# ======================================================================

def _check_all_fact_contradictions_ml(
    engine: "CRTEnhancedRAG",
    new_memory: MemoryItem,
    user_query: str,
    thread_id: Optional[str] = None,
) -> Tuple[bool, Optional[ContradictionEntry]]:
    """
    Check for contradictions using ML detector (replaces hardcoded slot list).

    This is the Bug 1 fix: Uses Phase 2/3 ML models to detect contradictions
    across ALL facts, not just hardcoded slots like employer/location.

    Phase 2.5: Added pattern-based detection (direct_correction, hedged_correction,
    numeric_drift, retraction_of_denial) that runs even without ML detector.

    Args:
        new_memory: Newly stored memory item
        user_query: User's input text
        thread_id: Reserved for future thread-level filtering (not yet used)

    Returns:
        (contradiction_detected, contradiction_entry)
    """
    # Flag to track if ML detector is available (affects which checks we can run)
    # NOTE: MLContradictionDetector() inits without error even if model files are missing.
    # We must check belief_classifier to know if actual ML inference is possible.
    ml_available = (engine.ml_detector is not None and
                    getattr(engine.ml_detector, 'belief_classifier', None) is not None)
    if not ml_available:
        logger.debug("[ML_CONTRADICTION] ML detector not available, using pattern-based detection only")

    # Phase 2.0: Extract facts with temporal and domain context
    new_facts = engine._extract_facts_contextual(user_query)
    if not new_facts:
        # Fallback to basic extraction
        new_facts = extract_fact_slots(user_query) or {}
    if not new_facts:
        # -- SEMANTIC CONTRADICTION PATH --
        # No structured facts extracted -- but the message may still
        # semantically contradict an existing memory. Compare the new
        # memory's embedding against recent USER memories and check
        # for negation/opposition patterns in the text.
        return _check_semantic_contradiction(
            engine, new_memory, user_query, thread_id=thread_id
        )

    previous_user_memories = engine._load_thread_user_memories(
        thread_id=thread_id,
        exclude_memory_id=new_memory.memory_id,
    )

    # Check each new fact against previous memories
    for slot, new_fact in new_facts.items():
        new_value = getattr(new_fact, "value", str(new_fact))
        if not new_value:
            continue

        # Phase 2.0: Extract temporal and domain context from new fact
        new_temporal_status = getattr(new_fact, "temporal_status", "active")
        new_domains = list(getattr(new_fact, "domains", ())) or ["general"]

        # Find previous memories with the same slot
        for prev_mem in previous_user_memories:
            if slot == "name" and not is_explicit_name_declaration_text(prev_mem.text):
                continue
            # Phase 2.0: Extract contextual facts from prior memory
            prev_facts = engine._extract_facts_contextual(prev_mem.text) or extract_fact_slots(prev_mem.text) or {}
            prev_fact = prev_facts.get(slot)

            if prev_fact is None:
                continue

            # Phase 2.0: Extract temporal and domain context from prior fact
            prev_temporal_status = getattr(prev_fact, "temporal_status", "active")
            # Get domains from fact or memory
            if hasattr(prev_fact, "domains") and prev_fact.domains:
                prev_domains = list(prev_fact.domains)
            elif hasattr(prev_mem, "get_domains"):
                prev_domains = prev_mem.get_domains()
            else:
                prev_domains = ["general"]

            prev_value = getattr(prev_fact, "value", str(prev_fact))
            if not prev_value:
                continue

            # Ensure string conversion for comparison (handles int values like programming_years)
            prev_value_str = str(prev_value).lower().strip()
            new_value_str = str(new_value).lower().strip()

            # Check if values are similar enough to skip (avoid nickname issues)
            if prev_value_str == new_value_str:
                continue
            if slot == "name":
                user_query_lower = (user_query or "").lower()
                if names_look_equivalent(prev_value_str, new_value_str) or any(
                    cue in user_query_lower for cue in ("nickname", "full name", "just my nickname")
                ):
                    logger.info(
                        "[ML_CONTRADICTION] Name refinement detected (%s vs %s); skipping contradiction",
                        prev_value_str,
                        new_value_str,
                    )
                    continue

            # Calculate drift for all checks
            drift = engine.crt_math.drift_meaning(new_memory.vector, prev_mem.vector)

            # ==============================================================
            # Phase 2.5 PRIORITY: Check for explicit corrections FIRST
            # These should ALWAYS be detected regardless of other checks
            # ==============================================================
            user_query_lower = (user_query or "").lower()
            explicit_revision_cue = any(
                cue in user_query_lower
                for cue in (
                    "actually",
                    "i meant",
                    "correction",
                    "to be clear",
                    "my real name is",
                    "my actual name is",
                    "i should clarify",
                )
            )
            correction_result = detect_correction_type(user_query)
            if correction_result:
                correction_type, old_val, new_val = correction_result
                logger.info(f"[CORRECTION_DETECTED] {correction_type}: {old_val} -> {new_val}")

                # Verify the correction relates to this slot's values
                old_val_lower = (old_val or "").lower()
                new_val_lower = (new_val or "").lower()

                # For corrections like "I'm actually 34, not 32":
                # - old_val (32) should match prev_value_str (what was stored before)
                # - new_val (34) should match new_value_str (what's in current statement)
                # We need BOTH to match for this to be the correct slot
                old_matches = (
                    (old_val_lower and (old_val_lower == prev_value_str or old_val_lower in prev_value_str or prev_value_str in old_val_lower))
                )
                new_matches = (
                    (new_val_lower and (new_val_lower == new_value_str or new_val_lower in new_value_str or new_value_str in new_val_lower))
                )

                # Both values must match for this to be the right slot
                slot_matches = old_matches and new_matches

                if slot_matches:
                    # This is an explicit correction - record as REVISION
                    contradiction_entry = _record_and_cascade(
                        engine,
                        old_vector=getattr(prev_mem, 'vector', None),
                        new_vector=getattr(new_memory, 'vector', None),
                        old_memory_id=prev_mem.memory_id,
                        new_memory_id=new_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                        query=user_query,
                        summary=f"{slot}: {correction_type} - {old_val} -> {new_val}",
                        old_text=prev_mem.text,
                        new_text=user_query,
                        contradiction_type=ContradictionType.REVISION,
                        suggested_policy="accept_new",
                        thread_id=thread_id,
                    )
                    return True, contradiction_entry
                else:
                    # Correction pattern found but doesn't match this slot's values.
                    # IMPORTANT: Do NOT 'continue' here  -  we must still fall through
                    # to the value-mismatch / NO_ML_FALLBACK checks below.
                    # Previously this was 'continue' which caused 89% of soft corrections
                    # (e.g. "Actually, my real name is Jordan Blake") to be silently dropped.
                    logger.debug(f"[CORRECTION_SKIP] Correction pattern found but slot {slot} doesn't match (old_val={old_val_lower}, prev_value={prev_value_str}), falling through to value checks")

            # ==============================================================
            # Phase 2.5: Check for numeric_drift (e.g., 32 vs 34 age)
            # This should also bypass contextual checks for clear numeric differences
            # ==============================================================
            is_numeric_contra, numeric_reason = engine.crt_math._is_numeric_contradiction(
                new_value_str, prev_value_str
            )
            if is_numeric_contra:
                logger.info(f"[NUMERIC_DRIFT] {numeric_reason}: {prev_value_str} vs {new_value_str}")

                # Record numeric drift as a CONFLICT (user should clarify)
                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                    query=user_query,
                    summary=f"{slot}: {numeric_reason} ({prev_value_str} vs {new_value_str})",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=prev_mem.vector,
                    new_vector=new_memory.vector,
                    contradiction_type=ContradictionType.CONFLICT,
                    suggested_policy="ask_user",
                    thread_id=thread_id,
                )
                return True, contradiction_entry

            # Phase 2.0: Use context-aware contradiction check
            is_contextual_contradiction, ctx_reason = engine.crt_math.is_true_contradiction_contextual(
                slot=slot,
                value_new=new_value_str,
                value_prior=prev_value_str,
                temporal_status_new=new_temporal_status,
                temporal_status_prior=prev_temporal_status,
                domains_new=new_domains,
                domains_prior=prev_domains,
                drift=drift,
            )

            if not is_contextual_contradiction:
                continue

            # Check if values are semantically equivalent (paraphrase, not contradiction)
            sem_match = engine._is_semantic_match(str(prev_value), str(new_value), slot)
            if sem_match:
                logger.debug(f"[SEMANTIC_MATCH] Skipping contradiction - semantic match: {prev_value} \u2248 {new_value}")
                continue

            # ==============================================================
            # NO_ML_FALLBACK: If ML is unavailable and we've confirmed:
            # - Values differ
            # - Contextual check passes (true contradiction)
            # - Not a semantic match (not a paraphrase)
            # Then record the contradiction immediately rather than risking
            # the negation/CRT paraphrase gate suppressing it.
            # ==============================================================
            if not ml_available:
                if slot == "name":
                    nickname_expansion_cue = any(
                        cue in user_query_lower
                        for cue in ("nickname", "full name", "just my nickname")
                    )
                    if names_look_equivalent(prev_value_str, new_value_str) or nickname_expansion_cue:
                        logger.info(
                            "[NO_ML_FALLBACK] Name refinement detected (%s vs %s); skipping contradiction",
                            prev_value_str,
                            new_value_str,
                        )
                        continue
                logger.info(f"[NO_ML_FALLBACK] Different values detected: {slot}={prev_value_str} vs {new_value_str}")
                fallback_type = ContradictionType.REVISION if explicit_revision_cue else ContradictionType.CONFLICT
                fallback_policy = "accept_new" if fallback_type == ContradictionType.REVISION else "ask_user"

                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                    query=user_query,
                    summary=f"{slot}: value_mismatch ({prev_value_str} vs {new_value_str})",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=prev_mem.vector,
                    new_vector=new_memory.vector,
                    contradiction_type=fallback_type,
                    suggested_policy=fallback_policy,
                    thread_id=thread_id,
                )
                return True, contradiction_entry

            # ==============================================================
            # Phase 2.4: Check for denial (Turn 23)
            # ==============================================================
            is_denial, denied_value = engine._detect_denial_in_text(user_query, slot)
            if is_denial and denied_value:
                # Search for the denied fact in previous memories
                for prev_mem_search in previous_user_memories:
                    prev_facts = extract_fact_slots(prev_mem_search.text) or {}
                    prev_fact = prev_facts.get(slot)

                    if prev_fact is None:
                        continue

                    # Check if denied value matches previous value
                    prev_value_str_search = str(prev_fact.value).lower().strip()
                    if denied_value.lower() in prev_value_str_search:
                        # Found matching prior statement - this is a denial contradiction
                        contradiction_entry = _record_and_cascade(
                            engine,
                            old_memory_id=prev_mem_search.memory_id,
                            new_memory_id=new_memory.memory_id,
                            drift_mean=drift,
                            confidence_delta=float(prev_mem_search.confidence) - float(new_memory.confidence),
                            query=user_query,
                            summary=f"{slot}: denial - User denied '{denied_value}' but prior statement shows '{prev_value_str_search}'",
                            old_text=prev_mem_search.text,
                            new_text=user_query,
                            old_vector=prev_mem_search.vector,
                            new_vector=new_memory.vector,
                            contradiction_type=ContradictionType.DENIAL,
                            suggested_policy="ask_user",
                            thread_id=thread_id,
                        )
                        logger.info(f"[DENIAL] Turn {new_memory.memory_id}: Denial of '{denied_value}' detected")
                        return True, contradiction_entry

            # ==============================================================
            # Phase 2.5: Check for retraction_of_denial
            # ==============================================================
            is_retraction, retraction_reason = engine._is_retraction_of_denial(
                new_text=user_query,
                prior_text=prev_mem.text,
                slot=slot,
            )
            if is_retraction:
                logger.info(f"[RETRACTION_OF_DENIAL] {retraction_reason}")

                # Record as REVISION - user is retracting their prior denial
                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                    query=user_query,
                    summary=f"{slot}: retraction_of_denial - {retraction_reason}",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=prev_mem.vector,
                    new_vector=new_memory.vector,
                    contradiction_type=ContradictionType.REVISION,
                    suggested_policy="accept_new",
                    thread_id=thread_id,
                )
                return True, contradiction_entry

            # Check for negation-based contradiction (retractions, denials)
            negation_result = heuristic_contradiction(prev_mem.text, user_query)
            if negation_result == SSE_CONTRADICTION_RESULT:
                # This is likely a retraction or negation - classify as REVISION
                logger.info(f"[NEGATION_DETECTED] Negation pattern found: {prev_mem.text[:50]} vs {user_query[:50]}")

                # Phase 1.1: Use CRTMath paraphrase check as final gate
                is_real_contradiction, crt_reason = engine.crt_math.detect_contradiction(
                    drift=drift,
                    confidence_new=float(new_memory.confidence),
                    confidence_prior=float(prev_mem.confidence),
                    source=new_memory.source,
                    text_new=user_query,
                    text_prior=prev_mem.text,
                    slot=slot,
                    value_new=new_value_str,
                    value_prior=prev_value_str,
                )
                if not is_real_contradiction:
                    logger.info(f"[CRT_PARAPHRASE] Skipped negation - {crt_reason}")
                    continue

                # Record as REVISION type, not CONFLICT
                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                    query=user_query,
                    summary=f"{slot}: negation/retraction detected",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=prev_mem.vector,
                    new_vector=new_memory.vector,
                    contradiction_type=ContradictionType.REVISION,
                    thread_id=thread_id,
                )
                return True, contradiction_entry

            # ==============================================================
            # ML-based contradiction detection (only if ML detector available)
            # ==============================================================

            # Use ML detector to check for contradiction
            context = {
                "query": user_query,
                "old_timestamp": prev_mem.timestamp,
                "new_timestamp": new_memory.timestamp,
                "memory_confidence": prev_mem.confidence,
                "trust_score": prev_mem.trust,
                "slot": slot,
            }

            result = engine.ml_detector.check_contradiction(
                old_value=prev_value,
                new_value=new_value,
                slot=slot,
                context=context,
            )

            logger.info(
                f"[ML_CONTRADICTION] Slot={slot}, Old={prev_value}, New={new_value}, "
                f"Category={result['category']}, Policy={result['policy']}, "
                f"Confidence={result['confidence']:.3f}"
            )

            # Use disclosure policy to decide action based on confidence
            p_valid = result['confidence']
            disclosure_decision = engine.disclosure_policy.should_disclose(
                p_valid=p_valid,
                slot=slot,
                old_value=str(prev_value),
                new_value=str(new_value),
                context={"category": result['category'], "policy": result['policy']},
            )

            logger.info(
                f"[DISCLOSURE_POLICY] Slot={slot}, P={p_valid:.3f}, "
                f"Action={disclosure_decision.action.value}, Zone={disclosure_decision.metadata.get('zone', 'unknown')}"
            )

            # Route based on disclosure decision:
            # - Green zone (high confidence): Skip recording as contradiction (accept as normal update)
            # - Yellow zone (medium): Record but flag for clarification
            # - Red zone (low confidence): Record and reject
            if disclosure_decision.action == DisclosureAction.ACCEPT and not result["is_contradiction"]:
                # High confidence AND ML says no contradiction - skip
                logger.info(f"[DISCLOSURE_POLICY] OK: Green zone acceptance for {slot}")
                continue

            # Record contradiction if detected (yellow or red zone, or ML flagged it)
            if result["is_contradiction"]:
                drift = engine.crt_math.drift_meaning(new_memory.vector, prev_mem.vector)

                # Phase 1.1: Use CRTMath paraphrase check as final gate
                is_real_contradiction, crt_reason = engine.crt_math.detect_contradiction(
                    drift=drift,
                    confidence_new=float(new_memory.confidence),
                    confidence_prior=float(prev_mem.confidence),
                    source=new_memory.source,
                    text_new=user_query,
                    text_prior=prev_mem.text,
                    slot=slot,
                    value_new=new_value_str,
                    value_prior=prev_value_str,
                )
                if not is_real_contradiction:
                    logger.info(f"[CRT_PARAPHRASE] Skipped ML detection - {crt_reason}")
                    continue

                # Add clarification context if in yellow zone
                suggested_policy_final = result["policy"]
                if disclosure_decision.action == DisclosureAction.CLARIFY:
                    suggested_policy_final = "clarify"  # Override to clarification
                    logger.info(
                        f"[DISCLOSURE_POLICY] \u26a0 Yellow zone - routing to clarification for {slot}"
                    )

                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                    query=user_query,
                    summary=f"{slot}: {prev_value} -> {new_value} ({result['category']})",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=prev_mem.vector,
                    new_vector=new_memory.vector,
                    contradiction_type=result["category"],
                    thread_id=thread_id,
                    suggested_policy=suggested_policy_final,
                )

                # Store clarification prompt if available
                if disclosure_decision.clarification_prompt:
                    try:
                        engine.ledger.update_contradiction_metadata(
                            contradiction_entry.ledger_id,
                            {"clarification_prompt": disclosure_decision.clarification_prompt},
                        )
                    except Exception as e:
                        logger.debug(f"[DISCLOSURE_POLICY] Could not store clarification prompt: {e}")

                logger.info(
                    f"[ML_CONTRADICTION] OK: Detected: {slot} contradiction "
                    f"({result['category']}, policy={suggested_policy_final})"
                )

                return True, contradiction_entry

    return False, None


# ======================================================================
# _check_semantic_contradiction
# ======================================================================

def _check_semantic_contradiction(
    engine: "CRTEnhancedRAG",
    new_memory: MemoryItem,
    user_query: str,
    thread_id: Optional[str] = None,
) -> Tuple[bool, Optional[ContradictionEntry]]:
    """Semantic contradiction detection -- catches opinion-level contradictions
    that don't extract structured fact slots.

    Compares the new memory's embedding against existing USER memories.
    High cosine similarity + opposing sentiment/negation = contradiction.

    This is the path that catches:
    - "CRT should use multiple models" vs "CRT works best with a single model"
    - "I love working on compression" vs "Compression is a waste of time"
    - "The belief system is the most important part" vs "The belief system is overengineered"

    These never extract fact slots, so the slot-based detector misses them entirely.
    """
    if new_memory is None or new_memory.vector is None:
        return False, None

    # Skip very short messages (greetings, acknowledgments)
    if len(user_query.strip()) < 15:
        return False, None

    # Skip questions -- they aren't assertions
    q_stripped = user_query.strip()
    if q_stripped.endswith("?") or q_stripped.lower().startswith(("what ", "how ", "why ", "when ", "where ", "who ", "do ", "does ", "is ", "are ", "can ", "could ")):
        return False, None

    try:
        # Retrieve similar user memories by embedding
        previous_memories = engine._load_thread_user_memories(
            thread_id=thread_id,
            exclude_memory_id=new_memory.memory_id,
        )

        # Fallback: if thread-scoped search found nothing, try unscoped
        if not previous_memories:
            previous_memories = engine._load_thread_user_memories(
                thread_id=None,
                exclude_memory_id=new_memory.memory_id,
            )

        if not previous_memories:
            return False, None

        new_vec = np.array(new_memory.vector, dtype=np.float32)
        new_norm = np.linalg.norm(new_vec)
        if new_norm == 0:
            return False, None
        new_vec_normed = new_vec / new_norm

        # Score all previous memories by cosine similarity
        candidates = []
        for prev_mem in previous_memories:
            if prev_mem.vector is None:
                continue
            # Skip very old low-trust memories
            if prev_mem.trust < 0.1:
                continue
            prev_vec = np.array(prev_mem.vector, dtype=np.float32)
            prev_norm = np.linalg.norm(prev_vec)
            if prev_norm == 0:
                continue
            sim = float(np.dot(new_vec_normed, prev_vec / prev_norm))
            if sim >= 0.50:  # Same topic threshold
                candidates.append((prev_mem, sim))

        # Sort by similarity descending, check top candidates
        candidates.sort(key=lambda x: x[1], reverse=True)

        for prev_mem, sim in candidates[:10]:
            # Run heuristic contradiction check on the text pair
            heuristic_result = heuristic_contradiction(user_query, prev_mem.text)

            if heuristic_result == "contradiction":
                drift = engine.crt_math.drift_meaning(new_memory.vector, prev_mem.vector)

                logger.info(
                    "[SEMANTIC_CONTRADICTION] Detected: '%s' vs '%s' "
                    "(sim=%.3f, drift=%.3f, heuristic=%s)",
                    user_query[:60], prev_mem.text[:60],
                    sim, drift, heuristic_result,
                )

                # Record as CONFLICT with held disposition -- don't auto-resolve
                contradiction_entry = _record_and_cascade(
                    engine,
                    old_memory_id=prev_mem.memory_id,
                    new_memory_id=new_memory.memory_id,
                    drift_mean=drift,
                    confidence_delta=abs(new_memory.confidence - prev_mem.confidence),
                    query=user_query,
                    summary=f"Semantic contradiction: '{user_query[:80]}' vs '{prev_mem.text[:80]}'",
                    old_text=prev_mem.text,
                    new_text=user_query,
                    old_vector=np.array(prev_mem.vector, dtype=np.float32),
                    new_vector=new_vec,
                    contradiction_type="conflict",
                    suggested_policy="ASK_USER",
                    thread_id=thread_id,
                )

                # Set disposition to 'held' so it doesn't auto-resolve
                if contradiction_entry is not None:
                    try:
                        conn = engine.ledger._get_connection()
                        conn.execute(
                            "UPDATE contradictions SET disposition = 'held', "
                            "disposition_confidence = 0.80 WHERE ledger_id = ?",
                            (contradiction_entry.ledger_id,),
                        )
                        conn.commit()
                        conn.close()
                        logger.info(
                            "[SEMANTIC_CONTRADICTION] Recorded as held: %s",
                            contradiction_entry.ledger_id,
                        )
                    except Exception as _disp_err:
                        logger.warning("[SEMANTIC_CONTRADICTION] Failed to set disposition: %s", _disp_err)

                return True, contradiction_entry

        return False, None

    except Exception as e:
        logger.warning("[SEMANTIC_CONTRADICTION] Failed: %s", e, exc_info=True)
        return False, None


# ======================================================================
# _track_implicit_confirmations
# ======================================================================

def _track_implicit_confirmations(engine: "CRTEnhancedRAG", user_text: str) -> int:
    """Track implicit confirmations when user repeats facts from open contradictions.

    When a user asserts a fact that matches the "new" side of an open contradiction,
    this is an implicit confirmation. After enough confirmations, the contradiction
    transitions from ACTIVE -> SETTLING -> SETTLED automatically.

    Returns: number of contradictions that received a confirmation increment.
    """
    facts = extract_fact_slots(user_text) or {}
    if not facts:
        return 0

    confirmed = 0
    open_contras = engine.ledger.get_open_contradictions(limit=200)

    for contra in open_contras:
        # Get lifecycle state (default to 'active')
        lifecycle_info = engine.ledger.get_lifecycle_info(contra.ledger_id)
        lifecycle_state = lifecycle_info.get("lifecycle_state", "active") if lifecycle_info else "active"

        # Skip archived contradictions
        if lifecycle_state == "archived":
            continue

        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
        if new_mem is None:
            continue

        new_facts = extract_fact_slots(new_mem.text) or {}
        shared_slots = set(new_facts.keys()) & set(facts.keys())

        if not shared_slots:
            continue

        # Check if user's assertion matches the "new" value (confirming the change)
        for slot in shared_slots:
            user_fact = facts.get(slot)
            new_fact = new_facts.get(slot)

            if user_fact is None or new_fact is None:
                continue

            user_norm = getattr(user_fact, "normalized", str(user_fact).lower())
            new_norm = getattr(new_fact, "normalized", str(new_fact).lower())

            if user_norm == new_norm:
                # User confirmed the new value - increment counter
                new_count = engine.ledger.increment_confirmation(contra.ledger_id)
                confirmed += 1
                logger.info(
                    f"[LIFECYCLE] Implicit confirmation for {contra.ledger_id}: "
                    f"slot={slot}, count={new_count}"
                )
                break  # Only count once per contradiction

    return confirmed


# ======================================================================
# _resolve_open_conflicts_from_assertion
# ======================================================================

def _resolve_open_conflicts_from_assertion(engine: "CRTEnhancedRAG", user_text: str) -> int:
    """Resolve open hard CONFLICT contradictions when the user clarifies.

    If the user makes a new assertion that sets a fact slot to a specific value
    (e.g., employer=Amazon) and we have an OPEN hard CONFLICT about that slot,
    mark those contradictions RESOLVED.

    This prevents an infinite "ask_user" loop where CRT keeps asking the same
    clarification question but never records that the user answered it.

    Returns: number of ledger entries resolved.
    """
    facts = extract_fact_slots(user_text) or {}

    # Support explicit "slot = value" clarifications used by stress harnesses.
    if not facts:

        def _norm(v: str) -> str:
            return re.sub(r"\s+", " ", (v or "").strip()).lower()

        text = (user_text or "").strip()
        slot_patterns = {
            "employer": r"\bemployer\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "name": r"\bname\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "location": r"\blocation\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "title": r"\btitle\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "first_language": r"\bfirst_language\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "masters_school": r"\bmasters_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "undergrad_school": r"\bundergrad_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
            "programming_years": r"\bprogramming_years\s*=\s*(\d{1,3})\b",
            "team_size": r"\bteam_size\s*=\s*(\d{1,3})\b",
        }

        class _Tmp:
            def __init__(self, value, normalized):
                self.value = value
                self.normalized = normalized

        for slot, pat in slot_patterns.items():
            m = re.search(pat, text, flags=re.IGNORECASE)
            if not m:
                continue
            raw = (m.group(1) or "").strip()
            if not raw:
                continue
            if slot in {"programming_years", "team_size"}:
                try:
                    val = int(raw)
                except Exception:
                    continue
                facts[slot] = _Tmp(val, str(val))
            else:
                facts[slot] = _Tmp(raw, _norm(raw))

    if not facts:
        return 0

    resolved = 0
    open_contras = engine.ledger.get_open_contradictions(limit=200)
    for contra in open_contras:
        ctype = str(getattr(contra, "contradiction_type", "")).strip().lower()
        if ctype not in {ContradictionType.CONFLICT, ContradictionType.REVISION}:
            continue

        old_mem = engine.memory.get_memory_by_id(contra.old_memory_id)
        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
        if old_mem is None or new_mem is None:
            continue

        old_facts = extract_fact_slots(old_mem.text) or {}
        new_facts = extract_fact_slots(new_mem.text) or {}
        shared = set(old_facts.keys()) & set(new_facts.keys()) & set(facts.keys())
        if not shared:
            continue

        should_resolve = False
        for slot in shared:
            user_fact = facts.get(slot)
            if user_fact is None:
                continue
            ov = old_facts.get(slot)
            nv = new_facts.get(slot)
            if ov is None or nv is None:
                continue

            # If the user asserts either side's value, we treat that as a clarification.
            if user_fact.normalized in {ov.normalized, nv.normalized}:
                should_resolve = True
                break

        if should_resolve:
            engine.ledger.resolve_contradiction(
                contra.ledger_id,
                method="user_clarified",
                merged_memory_id=None,
                new_status=ContradictionStatus.RESOLVED,
            )
            resolved += 1

    return resolved


# ======================================================================
# _detect_and_resolve_nl_resolution
# ======================================================================

def _detect_and_resolve_nl_resolution(engine: "CRTEnhancedRAG", user_text: str) -> bool:
    """Detect and resolve contradictions via natural language resolution statements.

    Detects patterns like:
    - "Google is correct, I switched jobs"
    - "Actually, it's Google now"
    - "I meant Google, not Microsoft"
    - "I changed jobs to Google"
    - "That's the correct status now"
    - "Blue was right, ignore the red"

    Handles CONFLICT, REVISION, and TEMPORAL contradiction types.

    Returns: True if a contradiction was resolved, False otherwise.
    """
    # Get trace logger
    trace_logger = get_trace_logger()
    start_time = time.time()

    # Check if user text contains any resolution intent pattern
    if not has_resolution_intent(user_text):
        return False

    # Get matched patterns for logging
    matched_patterns = get_matched_patterns(user_text)

    # Detect meta-correction override: strong patterns where the user is
    # re-asserting a value to close a contradiction -- they may be asserting
    # a THIRD value that doesn't match either existing side.
    _META_OVERRIDE_PATTERNS = {
        r'\bignore\s+the\s+noise\b',
        r'\balways\s+has\s+been\b',
        r'\bmy\s+(real|actual|true)\s+(favorite|favourite)\b',
        r'\bthe\s+(real|actual|true)\s+answer\b',
        r'\bfor\s+the\s+(last|final)\s+time\b',
        r'\bonce\s+and\s+for\s+all\b',
        r'\blet\s+me\s+(settle|clear)\s+this\b',
        r'\bno,?\s+seriously\b',
        r'\bstill\s+(?:is|my)\b',
    }
    is_meta_override = any(
        m['pattern'] in _META_OVERRIDE_PATTERNS for m in matched_patterns
    )

    # Extract facts from the user's statement
    facts = extract_fact_slots(user_text) or {}

    # Get open contradictions
    open_contras = engine.ledger.get_open_contradictions(limit=200)
    if not open_contras:
        return False

    # Log resolution attempt
    trace_logger.log_resolution_attempt(
        user_text=user_text,
        matched_patterns=matched_patterns,
        open_contradictions_count=len(open_contras),
    )

    resolved_count = 0
    total_open_before = len(open_contras)

    # Try to find a matching contradiction and determine which value to keep
    for contra in open_contras:
        # Handle CONFLICT, REVISION, TEMPORAL, REFINEMENT, and profile_update contradictions
        contradiction_type = getattr(contra, "contradiction_type", None)
        # Accept both enum types and the "profile_update" string type
        allowed_types = {
            ContradictionType.CONFLICT,
            ContradictionType.REVISION,
            ContradictionType.TEMPORAL,
            ContradictionType.REFINEMENT,
            "profile_update",
        }
        if contradiction_type not in allowed_types:
            continue

        # Handle profile_update contradictions specially - they have synthetic memory IDs
        # and the old/new values are encoded in the summary field
        if contradiction_type == "profile_update":
            # Parse the slot and values from summary (format: "Profile update: slot changed from 'old' to 'new'")
            summary = getattr(contra, "summary", "") or ""
            affects_slots = getattr(contra, "affects_slots", "") or ""

            profile_slot = affects_slots if affects_slots else None
            profile_old_value = None
            profile_new_value = None

            # Parse values from summary: "Profile update: name changed from 'Sarah' to 'Emily'"
            summary_match = re.search(r"changed from '([^']+)' to '([^']+)'", summary)
            if summary_match:
                profile_old_value = summary_match.group(1)
                profile_new_value = summary_match.group(2)

            if profile_slot and profile_old_value and profile_new_value:
                # Check if user's clarification mentions either value
                user_text_lower = user_text.lower()
                old_in_text = profile_old_value.lower() in user_text_lower
                new_in_text = profile_new_value.lower() in user_text_lower

                if old_in_text or new_in_text:
                    # Determine which value the user chose
                    if old_in_text and not new_in_text:
                        chosen_value = profile_old_value
                        resolution_method = "user_chose_old"
                    elif new_in_text and not old_in_text:
                        chosen_value = profile_new_value
                        resolution_method = "user_chose_new"
                    else:
                        # Both values in text - use position
                        old_pos = user_text_lower.find(profile_old_value.lower())
                        new_pos = user_text_lower.find(profile_new_value.lower())
                        if old_pos < new_pos:
                            chosen_value = profile_old_value
                            resolution_method = "user_chose_old"
                        else:
                            chosen_value = profile_new_value
                            resolution_method = "user_chose_new"

                    # Log the resolution
                    trace_logger.log_resolution_matched(
                        ledger_id=contra.ledger_id,
                        contradiction_type=str(contradiction_type),
                        slot_name=profile_slot,
                        old_value=profile_old_value,
                        new_value=profile_new_value,
                        chosen_value=chosen_value,
                        resolution_method=resolution_method,
                    )

                    # Mark the contradiction as resolved
                    engine.ledger.resolve_contradiction(
                        contra.ledger_id,
                        method="nl_resolution",
                    )

                    # Update user profile to the chosen value
                    try:
                        engine.user_profile.set_fact(profile_slot, chosen_value)
                    except Exception as profile_err:
                        logger.warning(f"[NL_RESOLUTION] Failed to update profile: {profile_err}")

                    trace_logger.log_ledger_update(
                        ledger_id=contra.ledger_id,
                        before_status="open",
                        after_status="resolved",
                        resolution_method="nl_resolution",
                        chosen_memory_id=f"profile_{profile_slot}_{chosen_value}",
                    )

                    trace_logger.log_resolution_complete(
                        ledger_id=contra.ledger_id,
                        success=True,
                        details=f"Profile {profile_slot} set to {chosen_value}",
                    )

                    resolved_count += 1
                    continue

            # Could not resolve this profile_update contradiction
            continue

        old_mem = engine.memory.get_memory_by_id(contra.old_memory_id)
        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
        if old_mem is None or new_mem is None:
            continue

        old_facts = extract_fact_slots(old_mem.text) or {}
        new_facts = extract_fact_slots(new_mem.text) or {}

        # Normalize values helper function (used throughout this loop)
        def normalize(val):
            if hasattr(val, 'normalized'):
                return val.normalized
            return str(val).lower().strip()

        # Find slots that are in both old and new (contradiction slots)
        contra_slots = set(old_facts.keys()) & set(new_facts.keys())

        # Try to match user's facts with contradiction slots
        # First check if user provided explicit facts that match
        shared = contra_slots & set(facts.keys())

        # If no common slots or no explicit facts extracted, try fuzzy matching against values
        # This handles cases where extract_fact_slots doesn't support the slot type
        if not shared:
            # Fallback: check if any value from the contradiction appears in the user text
            # This handles cases like "Google is correct" where extract_fact_slots doesn't catch it
            user_text_lower = user_text.lower()

            # If we have extracted slots, use them for precise matching
            if contra_slots:
                for slot in contra_slots:
                    old_value = old_facts.get(slot)
                    new_value = new_facts.get(slot)
                    if old_value is None or new_value is None:
                        continue

                    old_normalized = normalize(old_value)
                    new_normalized = normalize(new_value)

                    # Use word boundary matching to avoid false positives
                    # e.g., "Go" shouldn't match "Google"
                    old_pattern = re.compile(r'\b' + re.escape(old_normalized) + r'\b')
                    new_pattern = re.compile(r'\b' + re.escape(new_normalized) + r'\b')

                    old_match = old_pattern.search(user_text_lower)
                    new_match = new_pattern.search(user_text_lower)

                    # Check if either value appears in the user's text
                    # If both match, prefer the one that appears first in the text
                    if old_match or new_match:
                        # Found a match - add to shared so we process it below
                        shared = {slot}
                        # Create a synthetic fact for matching
                        # If both match, prefer the one that appears first
                        if old_match and new_match:
                            # Both values appear - choose based on position
                            if old_match.start() < new_match.start():
                                facts[slot] = old_value
                            else:
                                facts[slot] = new_value
                        elif old_match:
                            facts[slot] = old_value
                        else:
                            facts[slot] = new_value
                        break
            else:
                # No extracted slots - try direct keyword matching against memory texts
                # This handles cases like "I prefer coffee" vs "I prefer tea"
                # Extract key words from old and new memories (ignore common words)
                old_words = set(w.lower() for w in re.findall(r'\b\w+\b', old_mem.text) if w.lower() not in _NL_RESOLUTION_STOPWORDS)
                new_words = set(w.lower() for w in re.findall(r'\b\w+\b', new_mem.text) if w.lower() not in _NL_RESOLUTION_STOPWORDS)

                # Find words that differ between old and new
                old_unique = old_words - new_words
                new_unique = new_words - old_words

                # Check if any of these unique words appear in the resolution text
                # Use re.search to ensure word is actually found
                old_matches = [w for w in old_unique if re.search(r'\b' + re.escape(w) + r'\b', user_text_lower)]
                new_matches = [w for w in new_unique if re.search(r'\b' + re.escape(w) + r'\b', user_text_lower)]

                if old_matches or new_matches:
                    # Use a synthetic slot name for unstructured matching
                    shared = {_UNSTRUCTURED_SLOT_NAME}

                    # Determine which memory to keep based on which words appear
                    if old_matches and new_matches:
                        # Both appear - check which appears first
                        # Find positions, filtering out -1 (not found) for safety
                        old_positions = [user_text_lower.find(w) for w in old_matches]
                        new_positions = [user_text_lower.find(w) for w in new_matches]
                        old_positions = [p for p in old_positions if p >= 0]
                        new_positions = [p for p in new_positions if p >= 0]

                        if old_positions and new_positions:
                            first_old_pos = min(old_positions)
                            first_new_pos = min(new_positions)
                            if first_old_pos < first_new_pos:
                                facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                            else:
                                facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text
                        elif old_positions:
                            facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                        else:
                            facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text
                    elif old_matches:
                        facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                    else:
                        facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text

        if not shared:
            # -- Meta-override fallback (affects_slots) --
            # When memory text is malformed, fact extraction fails and
            # contra_slots is empty.  Fall back to the contradiction's
            # affects_slots field to see if it covers the same slot the
            # user is asserting about.  Only fire for meta-corrections.
            if is_meta_override and facts:
                _affects = getattr(contra, "affects_slots", None) or ""
                _affects_set = set(s.strip() for s in _affects.split(",") if s.strip())
                _slot_overlap = _affects_set & set(facts.keys())
                if _slot_overlap:
                    logger.info(
                        "[NL_RESOLUTION] Meta-override fallback: affects_slots %s matches user facts %s",
                        _affects_set, set(facts.keys()),
                    )
                    # Resolve by deprecating both memories and letting the
                    # new assertion (stored downstream) be the winner.
                    engine.ledger.resolve_contradiction(
                        contra.ledger_id,
                        method="nl_resolution",
                        new_status=ContradictionStatus.RESOLVED,
                    )
                    try:
                        engine.memory.deprecate_memory(
                            contra.old_memory_id,
                            reason=f"Meta-override resolution: '{user_text[:80]}'"
                        )
                        engine.memory.deprecate_memory(
                            contra.new_memory_id,
                            reason=f"Meta-override resolution: '{user_text[:80]}'"
                        )
                    except Exception as _dep_err:
                        logger.warning("[NL_RESOLUTION] Failed to deprecate memories: %s", _dep_err)
                    # Update profile to the user's stated value
                    for _slot in _slot_overlap:
                        try:
                            _val = facts[_slot]
                            _val_str = _val if isinstance(_val, str) else str(_val)
                            engine.user_profile.set_fact(_slot, _val_str)
                        except Exception:
                            pass
                    trace_logger.log_resolution_complete(
                        ledger_id=contra.ledger_id,
                        success=True,
                        details=f"Meta-override: deprecated both sides, user asserts {dict((s, facts[s]) for s in _slot_overlap)}",
                    )
                    resolved_count += 1
                    continue
            continue

        # Check if user's fact matches either old or new value
        for slot in shared:
            user_fact = facts.get(slot)
            if user_fact is None:
                continue

            chosen_memory_id = None
            deprecated_memory_id = None
            resolution_method = "nl_resolution"  # Default resolution method

            # Handle synthetic slot from unstructured matching
            if slot == _UNSTRUCTURED_SLOT_NAME:
                # User fact contains the full memory text that should be kept
                if user_fact == old_mem.text:
                    chosen_memory_id = contra.old_memory_id
                    deprecated_memory_id = contra.new_memory_id
                    resolution_method = "user_chose_old"
                elif user_fact == new_mem.text:
                    chosen_memory_id = contra.new_memory_id
                    deprecated_memory_id = contra.old_memory_id
                    resolution_method = "user_chose_new"
                else:
                    # Shouldn't happen, but skip if we can't determine
                    continue
            else:
                # Handle normal slots with extracted facts
                old_value = old_facts.get(slot)
                new_value = new_facts.get(slot)
                if old_value is None or new_value is None:
                    continue

                user_normalized = normalize(user_fact)
                old_normalized = normalize(old_value)
                new_normalized = normalize(new_value)

                # Determine which memory to keep based on matching values
                if user_normalized == new_normalized:
                    chosen_memory_id = contra.new_memory_id
                    deprecated_memory_id = contra.old_memory_id
                    resolution_method = "user_chose_new"
                elif user_normalized == old_normalized:
                    chosen_memory_id = contra.old_memory_id
                    deprecated_memory_id = contra.new_memory_id
                    resolution_method = "user_chose_old"
                else:
                    # User's value doesn't match either side.
                    # For meta-corrections this is expected -- the user is
                    # asserting a THIRD value (e.g. "orange" when the
                    # contradiction is "blue" vs "purple").  Resolve by
                    # deprecating both sides.
                    if is_meta_override:
                        logger.info(
                            "[NL_RESOLUTION] Meta-override: user value '%s' != old '%s' or new '%s' -- deprecating both",
                            user_normalized, old_normalized, new_normalized,
                        )
                        engine.ledger.resolve_contradiction(
                            contra.ledger_id,
                            method="nl_resolution",
                            new_status=ContradictionStatus.RESOLVED,
                        )
                        try:
                            engine.memory.deprecate_memory(
                                contra.old_memory_id,
                                reason=f"Meta-override resolution: '{user_text[:80]}'"
                            )
                            engine.memory.deprecate_memory(
                                contra.new_memory_id,
                                reason=f"Meta-override resolution: '{user_text[:80]}'"
                            )
                        except Exception as _dep_err:
                            logger.warning("[NL_RESOLUTION] Failed to deprecate: %s", _dep_err)
                        try:
                            _val = user_fact if isinstance(user_fact, str) else str(user_fact)
                            engine.user_profile.set_fact(slot, _val)
                        except Exception:
                            pass
                        trace_logger.log_resolution_complete(
                            ledger_id=contra.ledger_id,
                            success=True,
                            details=f"Meta-override: {slot}={user_fact}, deprecated both sides",
                        )
                        resolved_count += 1
                        break  # Done with this contradiction
                    continue

            # Log the matched resolution
            trace_logger.log_resolution_matched(
                ledger_id=contra.ledger_id,
                contradiction_type=contradiction_type or "CONFLICT",
                slot_name=slot if slot != _UNSTRUCTURED_SLOT_NAME else None,
                old_value=old_value if slot != _UNSTRUCTURED_SLOT_NAME and 'old_value' in locals() else old_mem.text[:50],
                new_value=new_value if slot != _UNSTRUCTURED_SLOT_NAME and 'new_value' in locals() else new_mem.text[:50],
                chosen_value=user_fact if slot != _UNSTRUCTURED_SLOT_NAME else "matched text",
                resolution_method=resolution_method,
            )

            # Resolve the contradiction in the ledger FIRST
            # This ensures we don't end up with deprecated memories but unresolved contradictions
            before_status = ContradictionStatus.OPEN
            after_status = ContradictionStatus.RESOLVED

            engine.ledger.resolve_contradiction(
                contra.ledger_id,
                method="nl_resolution",
                merged_memory_id=None,
                new_status=after_status,
            )

            # Log ledger update
            trace_logger.log_ledger_update(
                ledger_id=contra.ledger_id,
                before_status=before_status,
                after_status=after_status,
                resolution_method="nl_resolution",
                chosen_memory_id=chosen_memory_id,
            )

            # Deprecate the non-chosen memory via the memory object's API
            # (avoids raw sqlite3.connect which can bypass connection management).
            try:
                engine.memory.deprecate_memory(
                    deprecated_memory_id,
                    reason=f"User resolved via natural language: '{user_text[:100]}'"
                )
                # Boost trust of chosen memory slightly
                chosen_mem = _get_memory_by_id(engine, chosen_memory_id)
                if chosen_mem:
                    engine.memory.update_trust(
                        chosen_memory_id,
                        min(chosen_mem.trust + 0.1, 1.0),
                        reason="nl_resolution_boost",
                        drift=0.0,
                    )
            except Exception as e:
                logger.error(
                    f"[NL_RESOLUTION] Failed to update memories after resolving contradiction {contra.ledger_id}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"[NL_RESOLUTION] Resolved contradiction {contra.ledger_id} via natural language. "
                f"Chose {chosen_memory_id}, deprecated {deprecated_memory_id}. "
                f"User said: '{user_text[:100]}'"
            )

            # Log completion
            trace_logger.log_resolution_complete(
                ledger_id=contra.ledger_id,
                success=True,
                details=f"Chose {chosen_memory_id}, deprecated {deprecated_memory_id}",
            )

            resolved_count += 1

            # Note: We continue to check for more contradictions instead of returning
            # This allows resolving multiple contradictions in one statement

    # Log summary if any contradictions were resolved
    if resolved_count > 0:
        elapsed_time = time.time() - start_time
        total_open_after = len(engine.ledger.get_open_contradictions(limit=200))

        trace_logger.log_resolution_summary(
            total_open_before=total_open_before,
            total_open_after=total_open_after,
            resolved_count=resolved_count,
            elapsed_time=elapsed_time,
        )

    return resolved_count > 0


# ======================================================================
# _detect_sentiment_contradiction
# ======================================================================

def _detect_sentiment_contradiction(
    engine: "CRTEnhancedRAG",
    user_query: str,
    retrieved: List[Tuple[MemoryItem, float]],
) -> Optional[str]:
    """Detect implicit contradictions in sentiment/intent within retrieved memories.

    For example:
    - Query: "Am I happy at TechCorp?"
    - Memories: ["I just got promoted at TechCorp", "I'm thinking about changing jobs"]
    - Result: "You seem to have mixed feelings - you got promoted but are considering leaving"
    """
    if not retrieved:
        return None

    query_lower = user_query.lower()

    # Detect queries asking about sentiment/happiness/satisfaction
    if not any(word in query_lower for word in ["happy", "satisfied", "feel", "enjoy", "like"]):
        return None

    # Look for contradictory signals in retrieved memories
    positive_signals = []
    negative_signals = []

    for mem, _score in retrieved[:10]:
        text = mem.text.lower()

        # Positive signals
        if any(word in text for word in ["promoted", "promotion", "excited", "love", "great", "happy", "enjoy"]):
            positive_signals.append(mem.text)

        # Negative signals
        if any(phrase in text for phrase in ["changing jobs", "looking for", "thinking about leaving", "quit", "frustrated", "unhappy"]):
            negative_signals.append(mem.text)

    # If we have both positive and negative signals, surface the contradiction
    if positive_signals and negative_signals:
        answer_parts = ["I notice some mixed signals:"]
        if positive_signals:
            answer_parts.append(f"  Positive: {positive_signals[0]}")
        if negative_signals:
            answer_parts.append(f"  Concerning: {negative_signals[0]}")
        answer_parts.append("\nCan you help me understand what's really going on?")
        return "\n".join(answer_parts)

    return None


# ======================================================================
# _is_contradiction_status_request
# ======================================================================

def _is_contradiction_status_request(engine: "CRTEnhancedRAG", text: str) -> bool:
    """True if the user is asking to list/inspect open contradictions.

    IMPORTANT: Only trigger on QUERIES about contradictions, not assertions
    that mention "contradiction" as a topic (e.g., "I work on contradiction detection").
    """
    t = (text or "").strip().lower()
    if not t:
        return False

    # Explicit ledger queries
    if "contradiction ledger" in t:
        return True

    # Explicit status queries
    if "open contradictions" in t or "unresolved contradictions" in t:
        return True

    # Plural "contradictions" + interrogative keywords
    # Note: Use "contradictions" (plural) to avoid matching "contradiction detection", "contradiction tracking", etc.
    if "contradictions" in t and any(k in t for k in ("list", "show", "any", "open", "unresolved", "do you have", "are there")):
        return True

    # Singular contradiction phrasing used as a follow-up question:
    # "what was the contradiction you detected?"
    if "contradiction" in t and any(
        k in t for k in (
            "what was",
            "which contradiction",
            "what contradiction",
            "you detected",
            "did you detect",
            "that contradiction",
        )
    ):
        return True

    # User phrasing about self
    if "contradictions" in t and any(k in t for k in ("about me", "about myself", "about my", "about my self")):
        return True

    # CLI-style short commands (exact match only)
    if t in {"contradictions", "show contradictions", "list contradictions"}:
        return True

    return False


# ======================================================================
# _build_contradiction_status_answer
# ======================================================================

def _build_contradiction_status_answer(
    engine: "CRTEnhancedRAG",
    *,
    user_query: str,
    inferred_slots: Optional[List[str]] = None,
    limit: int = 8,
) -> Tuple[str, Dict[str, Any]]:
    """Build a deterministic answer listing OPEN contradictions from the ledger.

    This is intentionally ledger-grounded to prevent hallucinated contradictions.
    """
    ql = (user_query or "").strip().lower()

    scope_slots = set(inferred_slots or [])
    if not scope_slots and "identity" in ql:
        scope_slots = {
            "name",
            "employer",
            "location",
            "title",
            "first_language",
            "masters_school",
            "undergrad_school",
            "programming_years",
            "team_size",
        }

    open_contras = engine.ledger.get_open_contradictions(limit=200)
    unresolved_total = len(open_contras)

    rows: List[Dict[str, Any]] = []
    hard_conflicts = 0

    for contra in open_contras:
        old_mem = engine.memory.get_memory_by_id(contra.old_memory_id)
        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
        if old_mem is None or new_mem is None:
            continue

        old_facts = extract_fact_slots(old_mem.text) or {}
        new_facts = extract_fact_slots(new_mem.text) or {}
        shared = set(old_facts.keys()) & set(new_facts.keys())
        if scope_slots:
            shared = shared & scope_slots
        if not shared:
            continue

        for slot in sorted(shared):
            of = old_facts.get(slot)
            nf = new_facts.get(slot)
            if of is None or nf is None:
                continue
            if getattr(of, "normalized", None) == getattr(nf, "normalized", None):
                continue

            ctype = getattr(contra, "contradiction_type", None) or ContradictionType.CONFLICT
            if ctype == ContradictionType.CONFLICT:
                hard_conflicts += 1

            rows.append(
                {
                    "timestamp": getattr(contra, "timestamp", 0.0) or 0.0,
                    "ledger_id": contra.ledger_id,
                    "slot": slot,
                    "old": str(getattr(of, "value", "")),
                    "new": str(getattr(nf, "value", "")),
                    "type": ctype,
                }
            )

    # De-dup by (ledger_id, slot).
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in sorted(rows, key=lambda x: x.get("timestamp", 0.0), reverse=True):
        key = (r.get("ledger_id"), r.get("slot"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
        if len(deduped) >= limit:
            break

    meta = {
        "unresolved_contradictions_total": unresolved_total,
        "unresolved_hard_conflicts": hard_conflicts,
    }

    if not deduped:
        if "identity" in ql:
            return "No open contradictions about your identity in my contradiction ledger.", meta
        return "No open contradictions in my contradiction ledger.", meta

    header = "Here are the open contradictions I have recorded"
    if "identity" in ql:
        header += " about your identity"
    header += ":"

    out_lines = [header]
    for r in deduped:
        slot_name = str(r.get("slot") or "").replace("_", " ")
        old_v = (r.get("old") or "").strip()
        new_v = (r.get("new") or "").strip()
        ctype = (r.get("type") or "conflict").strip()
        if old_v and new_v:
            out_lines.append(f"- {slot_name}: {new_v} vs {old_v} (type: {ctype})")

    # Add a single concrete next action for the first listed entry.
    first = deduped[0] if deduped else None
    if first is not None:
        slot_name = str(first.get("slot") or "").replace("_", " ")
        old_v = (first.get("old") or "").strip()
        new_v = (first.get("new") or "").strip()
        ctype = (first.get("type") or "").strip()
        if old_v and new_v:
            out_lines.append("")
            if ctype == ContradictionType.CONFLICT:
                out_lines.append(f"To resolve the {slot_name} conflict: which is correct now: {new_v} or {old_v}?")
            elif ctype == ContradictionType.REVISION:
                out_lines.append(
                    f"To resolve this: should I treat {new_v} as your current {slot_name} and mark {old_v} as superseded?"
                )
            else:
                out_lines.append(
                    f"To resolve this: is {new_v} the more accurate/current {slot_name} to keep?"
                )

    return "\n".join(out_lines), meta


# ======================================================================
# get_open_contradictions
# ======================================================================

def get_open_contradictions(engine: "CRTEnhancedRAG") -> List[Dict]:
    """Get unresolved contradictions requiring reflection."""
    entries = engine.ledger.get_open_contradictions()
    return [e.to_dict() for e in entries]
