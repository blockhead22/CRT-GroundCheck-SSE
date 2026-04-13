from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, List, Tuple, Optional
if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG
    from ..crt_memory import MemoryItem

from ..crt_core import MemorySource
from ..fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)


def detect_denial_in_text(engine: "CRTEnhancedRAG", text: str, slot: str = "") -> Tuple[bool, Optional[str]]:
    """
    Detect if text contains a denial statement for a given slot.

    Tracks denial facts with denial=True flag to enable retraction_of_denial detection.

    Examples of denials:
    - "I don't have a PhD" -> (True, "PhD")
    - "I never said I worked at Google" -> (True, "Google")
    - "No, I'm not a manager" -> (True, "manager")

    Args:
        text: The text to analyze
        slot: Optional slot context for more precise detection

    Returns:
        Tuple of (is_denial, denied_value)
    """
    if not text:
        return False, None

    text_lower = text.lower()

    # Denial patterns with value extraction
    denial_patterns = [
        # "I don't have a X" / "I do not have a X"
        (r"i\s+(?:don't|do not|don\u2019t)\s+have\s+(?:a\s+)?(\w+)", "possession"),
        # "I never said X" / "I never mentioned X"
        (r"i\s+never\s+(?:said|mentioned|claimed|had)\s+(?:i\s+)?(?:had\s+)?(?:a\s+)?(\w+)", "claim"),
        # "I'm not a X" / "I am not a X"
        (r"i(?:'m| am)\s+not\s+(?:a\s+)?(\w+)", "identity"),
        # "No, I'm not X" / "No I don't X"
        (r"no[,\s]+i(?:'m| am| don't| do not)\s+(?:not\s+)?(?:a\s+)?(\w+)", "negation"),
        # "I didn't work at X"
        (r"i\s+(?:didn't|did not|didn\u2019t)\s+work\s+(?:at|for)\s+(\w+)", "employer"),
        # "I didn't go to X"
        (r"i\s+(?:didn't|did not|didn\u2019t)\s+(?:go to|attend|graduate from)\s+(\w+)", "education"),
    ]

    for pattern, denial_type in denial_patterns:
        match = re.search(pattern, text_lower)
        if match:
            denied_value = match.group(1).strip()
            logger.debug(f"[DENIAL_DETECT] Found {denial_type} denial: '{denied_value}'")
            return True, denied_value

    return False, None


def is_retraction_of_denial(
    engine: "CRTEnhancedRAG",
    new_text: str,
    prior_text: str,
    slot: str = ""
) -> Tuple[bool, str]:
    """
    Check if new assertion retracts a prior denial.

    This detects the pattern where user first denies something, then affirms it:
    - Prior: "I don't have a PhD"
    - New: "Actually I do have a PhD"

    Args:
        new_text: The new assertion text
        prior_text: The prior statement text
        slot: The fact slot being compared

    Returns:
        Tuple of (is_retraction, reason)
    """
    # Check if prior text contains a denial
    prior_is_denial, prior_denied_value = detect_denial_in_text(engine, prior_text, slot)

    if not prior_is_denial:
        return False, "prior_not_denial"

    # Check if new text is an affirmation (not a denial)
    new_is_denial, _ = detect_denial_in_text(engine, new_text, slot)

    if new_is_denial:
        return False, "new_also_denial"

    # Check if new text affirms what was denied
    affirmation_patterns = [
        # "Actually I do have X"
        r"actually\s+i\s+(?:do\s+)?have\s+(?:a\s+)?{value}",
        # "I actually have a X"
        r"i\s+actually\s+(?:do\s+)?have\s+(?:a\s+)?{value}",
        # "I do have a X"
        r"i\s+do\s+have\s+(?:a\s+)?{value}",
        # "Yes, I have a X"
        r"yes[,\s]+i\s+(?:do\s+)?have\s+(?:a\s+)?{value}",
        # "Actually, I am a X"
        r"actually[,\s]+i(?:'m|\s+am)\s+(?:a\s+)?{value}",
        # "I am a X" (simple affirmation)
        r"i(?:'m|\s+am)\s+(?:a\s+)?{value}",
    ]

    new_lower = new_text.lower()
    denied_lower = prior_denied_value.lower() if prior_denied_value else ""

    for pattern in affirmation_patterns:
        # Try with the specific denied value
        specific_pattern = pattern.format(value=re.escape(denied_lower))
        if re.search(specific_pattern, new_lower):
            logger.info(f"[RETRACTION_OF_DENIAL] Detected: prior denied '{prior_denied_value}', now affirming")
            return True, f"retraction_of_denial: affirmed previously denied '{prior_denied_value}'"

    # Also check if the denied value appears in the new text as a positive fact
    if prior_denied_value and prior_denied_value.lower() in new_lower:
        # Make sure it's not another denial
        denial_check = f"not.*{re.escape(denied_lower)}|don't.*{re.escape(denied_lower)}|never.*{re.escape(denied_lower)}"
        if not re.search(denial_check, new_lower):
            logger.info(f"[RETRACTION_OF_DENIAL] Implicit retraction: prior denied '{prior_denied_value}', now mentioned positively")
            return True, f"retraction_of_denial: implicit affirmation of '{prior_denied_value}'"

    return False, "no_retraction"


def build_gaslighting_citation(
    engine: "CRTEnhancedRAG",
    denial_text: str,
    denied_value: str,
    original_memory: 'MemoryItem',
    slot: str = ""
) -> str:
    """
    Build a citation when user denies saying something they actually said.

    This prevents gaslighting attempts by citing the original claim.

    Args:
        denial_text: The user's denial statement
        denied_value: The value being denied
        original_memory: The original memory containing the claim
        slot: The fact slot (e.g., "employer", "name")

    Returns:
        A polite but firm citation text
    """
    slot_name = slot.replace("user.", "").replace("_", " ") if slot else "this"

    # Extract timestamp for citation
    original_timestamp = getattr(original_memory, 'timestamp', None)
    time_ref = ""
    if original_timestamp:
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(str(original_timestamp).replace('Z', '+00:00'))
            time_ref = f" (at {ts.strftime('%H:%M')})"
        except (ValueError, TypeError, AttributeError):
            pass

    # Extract the original text snippet (truncated)
    original_text = getattr(original_memory, 'text', '')
    text_snippet = original_text[:100] + "..." if len(original_text) > 100 else original_text

    # Build citation based on denial type
    citation = (
        f"\u26a0\ufe0f I have a record of you saying: \"{text_snippet}\"{time_ref}\n"
        f"This indicates {slot_name} was '{denied_value}'. "
        f"Would you like to correct this information?"
    )

    return citation


def strip_continuity_augmented_text(engine: "CRTEnhancedRAG", text: str) -> str:
    """Strip appended chat continuity blocks when present.

    routes/chat.py may append helper blocks like:
    - [CONTINUITY INSTRUCTION]
    - [RECENT CONVERSATION CONTEXT]

    These should not be interpreted as fresh user assertions.
    """
    t = (text or "").strip()
    if not t:
        return ""

    markers = (
        "[CONTINUITY INSTRUCTION]",
        "[RECENT CONVERSATION CONTEXT]",
        "[Temporary GPT archive context - reference only, not settled memory]",
    )
    cut_at: Optional[int] = None
    for marker in markers:
        idx = t.find(marker)
        if idx >= 0 and (cut_at is None or idx < cut_at):
            cut_at = idx

    if cut_at is not None:
        base = t[:cut_at].strip()
        if base:
            return base
    return t


def detect_gaslighting_attempt(
    engine: "CRTEnhancedRAG",
    user_query: str,
    previous_memories: List['MemoryItem']
) -> Tuple[bool, Optional[str], Optional['MemoryItem'], Optional[str]]:
    """
    Detect if user is trying to deny something they previously said.

    Returns:
        (is_gaslighting, denied_value, original_memory, slot)
    """
    # Patterns for "I never said X" / "I didn't say X"
    denial_patterns = [
        (r"i\s+never\s+(?:said|mentioned|claimed|told you)\s+(?:i\s+)?(?:was\s+)?(?:a\s+)?(\w+(?:\s+\w+)?)", "claim_denial"),
        (r"i\s+(?:didn't|did not|didn\u2019t)\s+(?:say|tell you|mention)\s+(?:i\s+)?(?:was\s+)?(?:a\s+)?(\w+(?:\s+\w+)?)", "claim_denial"),
        (r"i\s+(?:don't|do not)\s+work\s+(?:at|for)\s+(\w+)", "employer_denial"),
        (r"(?:that's|that is)\s+(?:not true|wrong|incorrect).*?(?:about\s+)?(\w+)", "fact_denial"),
        (r"you(?:'re| are)\s+(?:wrong|confused|mistaken).*?(?:about\s+)?(\w+)", "accusation_denial"),
    ]

    query_clean = strip_continuity_augmented_text(engine, user_query)
    query_lower = query_clean.lower()
    if not query_lower:
        return False, None, None, None

    # Broader gaslighting patterns (no capture group needed)
    gaslight_phrases = [
        r"i don't know why you think",
        r"i don[\u2019']t know why you think",
        r"(?:my|it)\s*(?:'s|\u2019s|has)\s+always been",
        r"why do you think (?:my|i)",
    ]
    for gp in gaslight_phrases:
        if re.search(gp, query_lower):
            # Try to find a matching memory for the value being denied
            for mem in previous_memories:
                # Skip system/fallback memories -- fact extraction on Aether's
                # own responses produces spurious name="Aether" facts.
                if getattr(mem, 'source', None) in (MemorySource.SYSTEM, MemorySource.FALLBACK):
                    continue
                mem_lower = mem.text.lower()
                # Check overlap between query tokens and memory text
                # to identify which remembered fact is being denied
                mem_facts = extract_fact_slots(mem.text) or {}
                for s, fact in mem_facts.items():
                    fv = getattr(fact, 'value', str(fact)).lower()
                    if fv and fv in query_lower:
                        logger.info(f"[GASLIGHTING_DETECT] Phrase-match gaslighting on slot={s}")
                        return True, fv, mem, s
            # Even without a specific memory match, flag it as gaslighting
            logger.info(f"[GASLIGHTING_DETECT] Phrase-match gaslighting (no specific memory)")
            return True, None, None, None

    for pattern, denial_type in denial_patterns:
        match = re.search(pattern, query_lower)
        if match:
            denied_value = match.group(1).strip()

            # Search for the denied value in previous memories
            for mem in previous_memories:
                mem_text_lower = mem.text.lower()

                # Check if this memory contains the denied value
                if denied_value.lower() in mem_text_lower:
                    # Determine the slot
                    facts = extract_fact_slots(mem.text) or {}
                    slot = ""
                    for s, fact in facts.items():
                        if hasattr(fact, 'value') and denied_value.lower() in str(fact.value).lower():
                            slot = s
                            break

                    logger.info(f"[GASLIGHTING_DETECT] Potential gaslighting: denied '{denied_value}', found in memory: {mem.text[:50]}")
                    return True, denied_value, mem, slot

    return False, None, None, None


def detect_blindside_attack(
    engine: "CRTEnhancedRAG",
    user_query: str,
    previous_memories: List['MemoryItem'],
) -> Tuple[bool, Optional[str]]:
    """Detect identity-wipe / mass-retraction ("blindside") attacks.

    A blindside attack tries to invalidate a large swath of prior facts in
    a single message  -  e.g. "Everything I told you was a lie" or "Forget
    everything  -  my real name is Zara, I'm 40, and I live in Berlin".

    Returns:
        (is_blindside, reason_string)
    """
    query_clean = strip_continuity_augmented_text(engine, user_query)
    query_lower = query_clean.lower()
    if not query_lower:
        return False, None

    # ---- Pattern-based blanket retraction ----
    blindside_patterns = [
        (r"everything\s+(?:i\s+(?:told|said)|was)\s+(?:was\s+)?a\s+lie", "blanket_retraction"),
        (r"(?:forget|disregard|ignore)\s+everything", "forget_everything"),
        (r"none\s+of\s+(?:that|what\s+i\s+(?:said|told))\s+was\s+(?:true|real|correct)", "blanket_retraction"),
        (r"(?:scratch|throw\s+out|wipe)\s+(?:all|everything)", "wipe_request"),
        (r"start\s+(?:over|from\s+scratch)", "start_over"),
        (r"that\s+was\s+all\s+(?:fake|false|made\s+up|lies?)", "blanket_retraction"),
    ]

    for pat, reason in blindside_patterns:
        if re.search(pat, query_lower):
            logger.info(f"[BLINDSIDE_DETECT] Pattern match: {reason}")
            return True, f"blindside_pattern:{reason}"

    # ---- Multi-fact replacement heuristic ----
    # If the message asserts >=3 new facts that contradict existing ones,
    # treat it as a blindside even without an explicit retraction phrase.
    if previous_memories:
        new_facts = extract_fact_slots(query_clean) or {}
        if len(new_facts) >= 3:
            contradicting = 0
            for prev_mem in previous_memories:
                if getattr(prev_mem, 'source', None) in (MemorySource.SYSTEM, MemorySource.FALLBACK):
                    continue
                prev_facts = extract_fact_slots(prev_mem.text) or {}
                for slot, new_fact in new_facts.items():
                    prev_fact = prev_facts.get(slot)
                    if prev_fact is not None:
                        nv = getattr(new_fact, "value", str(new_fact)).lower()
                        pv = getattr(prev_fact, "value", str(prev_fact)).lower()
                        if nv and pv and nv != pv:
                            contradicting += 1
            if contradicting >= 3:
                logger.info(f"[BLINDSIDE_DETECT] Multi-fact replacement ({contradicting} slots)")
                return True, f"multi_fact_replacement:{contradicting}_slots"

    return False, None
