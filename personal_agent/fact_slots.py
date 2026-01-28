"""Lightweight fact-slot extraction for CRT.

Goal: reduce false contradiction triggers from generic semantic similarity by
comparing only facts that refer to the same attribute ("slot").

This is intentionally heuristic (no ML) and is tuned to the kinds of personal
profile facts used in CRT stress tests.

Phase 2.0 Updates:
- Extended ExtractedFact with temporal_status, period_text, and domains
- Added temporal pattern extraction for past/active/future status
- Integrated with domain_detector for domain tagging
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List


# ============================================================================
# TEMPORAL STATUS CONSTANTS
# ============================================================================

class TemporalStatus:
    """Temporal status constants for facts."""
    PAST = "past"           # No longer true (e.g., "I used to work at X")
    ACTIVE = "active"       # Currently true (default)
    FUTURE = "future"       # Will be true (e.g., "I'm starting at X next month")
    POTENTIAL = "potential" # Might be true (e.g., "I might take the job")


# ============================================================================
# TEMPORAL PATTERN EXTRACTION
# ============================================================================

# Patterns that indicate temporal status with their corresponding status
TEMPORAL_PATTERNS: List[Tuple[re.Pattern, str, Optional[str]]] = [
    # Past indicators
    (re.compile(r"(?:i\s+)?(?:used to|formerly|previously)\s+", re.IGNORECASE), TemporalStatus.PAST, None),
    (re.compile(r"(?:i\s+)?(?:no longer|don't|do not|stopped|quit|left)\s+", re.IGNORECASE), TemporalStatus.PAST, None),
    (re.compile(r"\b(?:back when|when i was|in the past)\b", re.IGNORECASE), TemporalStatus.PAST, None),
    (re.compile(r"\bformer\s+", re.IGNORECASE), TemporalStatus.PAST, None),
    (re.compile(r"\bex-", re.IGNORECASE), TemporalStatus.PAST, None),
    (re.compile(r"\banymore\b", re.IGNORECASE), TemporalStatus.PAST, None),
    
    # Active indicators
    (re.compile(r"(?:i\s+)?(?:currently|now|presently|still)\s+", re.IGNORECASE), TemporalStatus.ACTIVE, None),
    (re.compile(r"\b(?:i am|i'm)\s+(?:currently|still)\s+", re.IGNORECASE), TemporalStatus.ACTIVE, None),
    (re.compile(r"\bthese days\b", re.IGNORECASE), TemporalStatus.ACTIVE, None),
    
    # Future indicators
    (re.compile(r"(?:i\s+)?(?:will|plan to|going to|about to)\s+", re.IGNORECASE), TemporalStatus.FUTURE, None),
    (re.compile(r"\b(?:starting|beginning|joining)\s+(?:next|soon|in)\s+", re.IGNORECASE), TemporalStatus.FUTURE, None),
    (re.compile(r"\bnext (?:week|month|year)\b", re.IGNORECASE), TemporalStatus.FUTURE, None),
    
    # Potential indicators
    (re.compile(r"(?:i\s+)?(?:might|may|could|considering)\s+", re.IGNORECASE), TemporalStatus.POTENTIAL, None),
    (re.compile(r"\bthinking about\b", re.IGNORECASE), TemporalStatus.POTENTIAL, None),
]

# Period extraction patterns (capture date ranges)
PERIOD_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # "from 2020 to 2024" or "from 2020-2024"
    (re.compile(r"from\s+(\d{4})\s*(?:to|-)\s*(\d{4}|present)", re.IGNORECASE), "period"),
    # "2020-2024" or "2020 - 2024"
    (re.compile(r"\b(\d{4})\s*-\s*(\d{4}|present)\b", re.IGNORECASE), "period"),
    # "since 2020" or "since last year"
    (re.compile(r"since\s+(\d{4}|\w+\s+(?:year|month))", re.IGNORECASE), "since"),
    # "until 2024" or "till 2024"
    (re.compile(r"(?:until|till)\s+(\d{4})", re.IGNORECASE), "until"),
    # "in 2020"
    (re.compile(r"\bin\s+(\d{4})\b", re.IGNORECASE), "year"),
]


# ============================================================================
# DIRECT CORRECTION PATTERNS
# ============================================================================
# Patterns that detect explicit corrections like "I'm actually 34, not 32"
# Returns: (new_value, old_value) where new_value is what's being corrected TO

DIRECT_CORRECTION_PATTERNS: List[re.Pattern] = [
    # "I'm actually X, not Y" - extracts (X, Y) - handles numbers and words
    re.compile(r"(?:i'm|i am)\s+actually\s+(\d+|\w+),?\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "Actually it's X, not Y"
    re.compile(r"actually\s+(?:it's|it is)\s+(\d+|\w+),?\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "No, I'm X not Y"
    re.compile(r"no,?\s+(?:i'm|i am)\s+(\d+|\w+)\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "Correction: X not Y"
    re.compile(r"correction:?\s+(\d+|\w+)\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "Actually X, not Y" (shorter form)
    re.compile(r"actually\s+(\d+|\w+),?\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "Wait, it's X, not Y"
    re.compile(r"wait,?\s+(?:it's|it is)\s+(\d+|\w+),?\s+not\s+(\d+|\w+)", re.IGNORECASE),
    # "Wait, I'm actually X" (without explicit "not Y")
    re.compile(r"wait,?\s+(?:i'm|i am)\s+actually\s+(\d+)", re.IGNORECASE),
]


# ============================================================================
# HEDGED CORRECTION PATTERNS  
# ============================================================================
# Patterns that detect soft corrections like "I said 10 years but it's closer to 12"
# Returns: (old_value, new_value) where old_value is what was previously said

HEDGED_CORRECTION_PATTERNS: List[re.Pattern] = [
    # "I think I said X [years of programming] but it's closer to Y" - handles numbers with multiple words after
    re.compile(r"(?:i think\s+)?i\s+said\s+(\d+)(?:\s+\w+)*?\s+but\s+(?:it's|it is)\s+(?:closer to\s+)?(\d+)", re.IGNORECASE),
    # "I may have said X, but actually Y"
    re.compile(r"i\s+(?:may have|might have)\s+said\s+(\d+|\w+),?\s+but\s+(?:actually\s+)?(\d+|\w+)", re.IGNORECASE),
    # "Earlier I mentioned X, it's really Y"
    re.compile(r"earlier\s+i\s+(?:mentioned|said)\s+(\d+|\w+),?\s+(?:it's|it is)\s+really\s+(\d+|\w+)", re.IGNORECASE),
    # "I said X but it's more like Y"
    re.compile(r"i\s+said\s+(\d+)(?:\s+\w+)*?\s+but\s+(?:it's|it is)\s+more\s+like\s+(\d+)", re.IGNORECASE),
    # "I mentioned X earlier but Y is more accurate"
    re.compile(r"i\s+(?:mentioned|said)\s+(\d+|\w+)\s+(?:earlier\s+)?but\s+(\d+|\w+)\s+is\s+(?:more\s+)?accurate", re.IGNORECASE),
    # "Actually closer to X" (simple hedged with number) - fallback pattern
    re.compile(r"(?:it's|it is)\s+(?:actually\s+)?(?:closer to|more like)\s+(\d+)", re.IGNORECASE),
]


def extract_temporal_status(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract temporal status and period from text.
    
    Args:
        text: The text to analyze
        
    Returns:
        Tuple of (temporal_status, period_text).
        - temporal_status: "past", "active", "future", or "potential"
        - period_text: Human-readable period like "2020-2024" or None
    """
    if not text:
        return (TemporalStatus.ACTIVE, None)
    
    text_lower = text.lower()
    detected_status = TemporalStatus.ACTIVE  # Default
    period_text = None
    
    # Check temporal status patterns
    for pattern, status, _ in TEMPORAL_PATTERNS:
        if pattern.search(text):
            detected_status = status
            break
    
    # Check period patterns
    for pattern, pattern_type in PERIOD_PATTERNS:
        match = pattern.search(text)
        if match:
            if pattern_type == "period":
                start = match.group(1)
                end = match.group(2) if match.lastindex >= 2 else "present"
                period_text = f"{start}-{end}"
            elif pattern_type == "since":
                period_text = f"{match.group(1)}-present"
            elif pattern_type == "until":
                period_text = f"?-{match.group(1)}"
            elif pattern_type == "year":
                period_text = match.group(1)
            break
    
    return (detected_status, period_text)


def extract_direct_correction(text: str) -> Optional[Tuple[str, str]]:
    """
    Extract a direct correction pattern from text.
    
    Detects patterns like:
    - "I'm actually 34, not 32" → (corrected_to="34", corrected_from="32")
    - "Actually it's Google, not Microsoft" → (corrected_to="Google", corrected_from="Microsoft")
    - "No, I'm Sarah not Susan" → (corrected_to="Sarah", corrected_from="Susan")
    
    Args:
        text: The text to analyze
        
    Returns:
        Tuple of (new_value, old_value) if correction detected, None otherwise.
        Note: new_value is what's being corrected TO, old_value is what's being corrected FROM.
    """
    if not text:
        return None
    
    for pattern in DIRECT_CORRECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            new_value = match.group(1).strip()
            # Some patterns only capture the new value (e.g., "Wait, I'm actually X")
            if match.lastindex >= 2:
                old_value = match.group(2).strip()
            else:
                old_value = None  # Old value not specified in this pattern
            return (new_value, old_value)
    
    return None


def extract_hedged_correction(text: str) -> Optional[Tuple[str, str]]:
    """
    Extract a hedged/soft correction pattern from text.
    
    Detects patterns like:
    - "I said 10 years but it's closer to 12" → (old="10", new="12")
    - "I may have said Microsoft, but actually Google" → (old="Microsoft", new="Google")
    - "Earlier I mentioned Python, it's really JavaScript" → (old="Python", new="JavaScript")
    
    Args:
        text: The text to analyze
        
    Returns:
        Tuple of (old_value, new_value) if correction detected, None otherwise.
        Note: Returns (old, new) - what was said vs what is correct.
    """
    if not text:
        return None
    
    for pattern in HEDGED_CORRECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            # Some patterns only capture new value (e.g., "closer to X")
            if match.lastindex == 1:
                # Only one group - this is the new value, old value unknown
                new_value = match.group(1).strip()
                return (None, new_value)  # Return None for old_value
            else:
                old_value = match.group(1).strip()
                new_value = match.group(2).strip()
                return (old_value, new_value)
            return (old_value, new_value)
    
    return None


def detect_correction_type(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Detect any correction pattern (direct or hedged) in text.
    
    This is the main entry point for correction detection. It checks both
    direct corrections ("I'm X, not Y") and hedged corrections ("I said X but Y").
    
    Args:
        text: The text to analyze
        
    Returns:
        Tuple of (correction_type, old_value, new_value) or None
        - correction_type: "direct_correction" or "hedged_correction"
        - old_value: The value being corrected FROM
        - new_value: The value being corrected TO
    """
    # Check for direct correction first (more explicit)
    direct = extract_direct_correction(text)
    if direct:
        new_val, old_val = direct  # direct returns (new, old)
        return ("direct_correction", old_val, new_val)
    
    # Check for hedged correction
    hedged = extract_hedged_correction(text)
    if hedged:
        old_val, new_val = hedged  # hedged returns (old, new)
        return ("hedged_correction", old_val, new_val)
    
    return None


@dataclass(frozen=True)
class ExtractedFact:
    """
    A single extracted fact with temporal and domain metadata.
    
    Phase 2.0 Extension: Added temporal_status, period_text, and domains
    to support context-aware memory and smarter contradiction detection.
    """
    slot: str
    value: Any
    normalized: str
    
    # Phase 2.0: Temporal metadata
    temporal_status: str = TemporalStatus.ACTIVE  # past | active | future | potential
    period_text: Optional[str] = None             # Human-readable: "2020-2024"
    
    # Phase 2.0: Domain context (tuple for frozen dataclass)
    domains: Tuple[str, ...] = ()                 # e.g., ("print_shop", "freelance")
    
    # Source tracking
    confidence: float = 0.9


def create_simple_fact(value: Any, temporal_status: str = TemporalStatus.ACTIVE, 
                       domains: Tuple[str, ...] = ()) -> ExtractedFact:
    """
    Create a simple ExtractedFact from a value.
    
    Useful for converting LLM-extracted tuples to ExtractedFact format
    for compatibility with existing code.
    
    Phase 2.0: Now supports temporal_status and domains parameters.
    
    Args:
        value: The fact value
        temporal_status: Temporal status (past/active/future/potential)
        domains: Tuple of domain names for context
        
    Returns:
        ExtractedFact with slot="", value=value, normalized=str(value).lower()
    """
    return ExtractedFact(
        slot="",
        value=value,
        normalized=str(value).lower().strip(),
        temporal_status=temporal_status,
        domains=domains
    )


def create_contextual_fact(
    slot: str,
    value: Any,
    text: str,
    confidence: float = 0.9
) -> ExtractedFact:
    """
    Create an ExtractedFact with automatic temporal and domain detection.
    
    Phase 2.0: This is the preferred way to create facts as it automatically
    extracts temporal status and domains from the source text.
    
    Args:
        slot: The fact slot name (e.g., "employer", "name")
        value: The fact value
        text: The source text (used for temporal/domain detection)
        confidence: Confidence score (0-1)
        
    Returns:
        ExtractedFact with temporal_status and domains auto-detected
    """
    from .domain_detector import detect_domains
    
    # Extract temporal status from text
    temporal_status, period_text = extract_temporal_status(text)
    
    # Detect domains from text
    domains = tuple(detect_domains(text))
    
    return ExtractedFact(
        slot=slot,
        value=value,
        normalized=str(value).lower().strip(),
        temporal_status=temporal_status,
        period_text=period_text,
        domains=domains,
        confidence=confidence
    )


_WS_RE = re.compile(r"\s+")


# ============================================================================
# NICKNAME MAPPINGS - Used to recognize name relationships
# ============================================================================

NICKNAME_MAPPINGS = {
    # Common English nicknames
    "alex": {"alexander", "alexandra", "alexis", "alejandro", "alessandra"},
    "bob": {"robert", "bobby", "rob", "robbie"},
    "bill": {"william", "billy", "will", "willy"},
    "mike": {"michael", "mickey", "mick"},
    "nick": {"nicholas", "nicolas", "nicky", "nico"},
    "kate": {"katherine", "catherine", "kathryn", "kathy", "katie"},
    "liz": {"elizabeth", "elisabeth", "beth", "betty", "eliza"},
    "tom": {"thomas", "tommy"},
    "jim": {"james", "jimmy", "jamie"},
    "joe": {"joseph", "joey"},
    "dan": {"daniel", "danny"},
    "sam": {"samuel", "samantha", "sammy"},
    "chris": {"christopher", "christine", "christina", "christian"},
    "matt": {"matthew", "matty"},
    "dave": {"david", "davy"},
    "steve": {"steven", "stephen"},
    "ben": {"benjamin", "benny"},
    "jen": {"jennifer", "jenny", "jenna"},
    "meg": {"megan", "margaret", "maggie"},
    "ed": {"edward", "eddie", "ted", "teddy"},
    "rick": {"richard", "ricky", "dick"},
    "tony": {"anthony"},
    "andy": {"andrew", "drew"},
    "pat": {"patrick", "patricia", "patty"},
}


def names_are_related(name1: str, name2: str) -> bool:
    """
    Check if two names could refer to the same person.
    
    Examples that return True:
    - "Alex" vs "Alexandra" (nickname)
    - "Alex Chen" vs "Alexandra Chen" (full name with nickname)
    - "Bob" vs "Robert" (nickname mapping)
    """
    n1 = str(name1).lower().strip()
    n2 = str(name2).lower().strip()
    
    # Exact match
    if n1 == n2:
        return True
    
    # One is substring of other (Alex Chen vs Alexandra Chen)
    if n1 in n2 or n2 in n1:
        return True
    
    # Extract first names for comparison
    n1_first = n1.split()[0] if n1 else ""
    n2_first = n2.split()[0] if n2 else ""
    
    # Check nickname mappings
    for nickname, full_names in NICKNAME_MAPPINGS.items():
        all_names = {nickname} | full_names
        n1_match = n1_first in all_names or any(name in n1_first for name in all_names)
        n2_match = n2_first in all_names or any(name in n2_first for name in all_names)
        if n1_match and n2_match:
            return True
    
    return False


_NAME_STOPWORDS = {
    # Common non-name tokens that appear after "I'm ..." in normal sentences.
    "a",
    "an",
    "the",
    "ai",
    "back",
    "building",
    "build",
    "busy",
    "fine",
    "good",
    "great",
    "here",
    "help",
    "okay",
    "ok",
    "ready",
    "sorry",
    "sure",
    "tired",
    "trying",
    "working",
    "going",
    "to",
}


def _norm_text(value: str) -> str:
    value = _WS_RE.sub(" ", value.strip())
    return value.lower()


def is_question(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if "?" in text:
        return True
    lowered = text.lower()
    return lowered.startswith((
        "what ", "where ", "when ", "why ", "how ", "who ", "which ",
        "do ", "does ", "did ", "can ", "could ", "should ", "would ",
        "is ", "are ", "am ", "was ", "were ", "tell me ",
    ))


def extract_fact_slots(text: str) -> Dict[str, ExtractedFact]:
    """
    Extract a small set of personal-profile fact slots from free text.
    
    Note: Regex parsing is relatively expensive. Consider caching results
    at the call site if the same text is processed multiple times.
    """
    facts: Dict[str, ExtractedFact] = {}

    if not text or not text.strip():
        return facts

    # Structured facts/preferences (useful for onboarding and explicit corrections).
    # Examples:
    # - "FACT: name = Nick"
    # - "PREF: communication_style = concise"
    # - "FACT: favorite_snack = popcorn" (dynamic category)
    structured = re.search(
        r"\b(?:FACT|PREF):\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if structured:
        slot = structured.group(1).strip().lower()
        value_raw = structured.group(2).strip()
        
        # Core slots (always allowed)
        core_slots = {
            "name",
            "employer",
            "title",
            "location",
            "pronouns",
            "communication_style",
            "goals",
            "favorite_color",
        }
        
        # Dynamic fact support: Allow any slot name that starts with "favorite_"
        # or matches common preference patterns, enabling unlimited fact categories
        is_core_slot = slot in core_slots
        is_favorite = slot.startswith("favorite_")
        is_preference = slot.endswith("_preference") or slot.startswith("pref_")
        # More specific dynamic patterns to avoid false positives
        is_my_prefix = slot.startswith("my_") and len(slot) > 3
        is_name_suffix = slot.endswith("_name") and len(slot) > 5
        is_type_suffix = slot.endswith("_type") and len(slot) > 5
        is_status_suffix = slot.endswith("_status") and len(slot) > 7
        is_count_suffix = slot.endswith("_count") and len(slot) > 6
        
        # Accept if it's a core slot OR a recognized dynamic pattern
        if (is_core_slot or is_favorite or is_preference or 
            is_my_prefix or is_name_suffix or is_type_suffix or 
            is_status_suffix or is_count_suffix) and value_raw:
            facts[slot] = ExtractedFact(slot, value_raw, _norm_text(value_raw))
            return facts

    # Name
    # Examples:
    # - "My name is Sarah."
    # - "Yes, I'm Sarah"
    # - "Call me Sarah"
    # - "Nick not Ben" (short correction)
    # Allow multi-token names (e.g., "Nick Block"), but keep it conservative.
    # For "I'm ..." specifically, require a name-like token to avoid false positives
    # like "I'm glad you asked".
    # CRITICAL: Name patterns should NOT greedily consume conjunctions + pronouns.
    # "My name is nick but you said sarah" should extract "nick", not "nick but you".
    name_pat = r"([A-Za-z][A-Za-z'-]{1,40}(?:\s+[A-Za-z][A-Za-z'-]{1,40}){0,2})"
    name_pat_title = r"([A-Z][A-Za-z'-]{1,40}(?:\s+[A-Z][A-Za-z'-]{1,40}){0,2})"
    
    # Conjunctions/words that should NOT be part of a name when followed by pronouns/verbs
    _NAME_BOUNDARY_WORDS = {"but", "and", "or", "so", "yet", "for", "nor", "said", "says", "told", "you", "i", "he", "she", "they", "we", "it"}
    
    def _clean_name_value(raw_name: str) -> str:
        """Remove trailing conjunctions and pronouns from name matches."""
        tokens = raw_name.split()
        # Walk backwards and remove boundary words
        while len(tokens) > 1 and tokens[-1].lower() in _NAME_BOUNDARY_WORDS:
            tokens.pop()
        # Also check for "X but Y" or "X and Y" patterns in the middle
        cleaned = []
        for i, tok in enumerate(tokens):
            if tok.lower() in _NAME_BOUNDARY_WORDS and i > 0:
                # Stop here - everything before is the name
                break
            cleaned.append(tok)
        return " ".join(cleaned) if cleaned else raw_name

    # Very explicit "call me" pattern.
    m = re.search(r"\bcall me\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
    if m:
        name = _clean_name_value(m.group(1).strip())
        tokens = [t for t in re.split(r"\s+", name) if t]
        token_lowers = [t.lower() for t in tokens]
        if tokens and not any(t in _NAME_STOPWORDS for t in token_lowers):
            facts["name"] = ExtractedFact("name", name, _norm_text(name))

    # Short correction pattern: "Nick not Ben".
    if "name" not in facts:
        m = re.match(
            r"^\s*([A-Z][A-Za-z'-]{1,40})\s+not\s+([A-Z][A-Za-z'-]{1,40})\s*[\.!?]?\s*$",
            text,
        )
        if m:
            cand = m.group(1).strip()
            if cand and cand.lower() not in _NAME_STOPWORDS:
                facts["name"] = ExtractedFact("name", cand, _norm_text(cand))

    # "my name is X" pattern - apply _clean_name_value to handle "my name is nick but you..."
    m = re.search(r"\bmy name is\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
    if m:
        name = _clean_name_value(m.group(1).strip())
        tokens = [t for t in re.split(r"\s+", name) if t]
        token_lowers = [t.lower() for t in tokens]
        if tokens and not any(t in _NAME_STOPWORDS for t in token_lowers):
            facts["name"] = ExtractedFact("name", name, _norm_text(name))
    
    if "name" not in facts:
        # Prefer TitleCase names for the generic "I'm X" pattern.
        # Match various apostrophe types: ' (straight), ' (curly open), ' (curly close), ʼ (modifier letter)
        m = re.search(r"\bi\s*['''ʼ]?m\s+" + name_pat_title, text)
        if not m:
            # Also try "I am" pattern
            m = re.search(r"\bi\s+am\s+" + name_pat_title, text, flags=re.IGNORECASE)
        if not m:
            # Allow a single-token lowercase name, but only when it appears as a direct
            # name declaration (no extra trailing content).
            m = re.search(r"^\s*i\s*['''ʼ]?m\s+([a-z][a-z'-]{1,40})\s*[\.!?]?\s*$", text, flags=re.IGNORECASE)
    if m:
        name = _clean_name_value(m.group(1).strip())
        tokens = [t for t in re.split(r"\s+", name) if t]
        token_lowers = [t.lower() for t in tokens]

        # Filter obvious non-name phrases like "I'm trying to build ...".
        trailing = (text[m.end():] or "").lstrip().lower()
        looks_like_infinitive = trailing.startswith("to ")
        has_stopword = any(t in _NAME_STOPWORDS for t in token_lowers)

        # Reject common non-name tokens and infinitive phrases.
        if tokens and not has_stopword and not looks_like_infinitive:
            facts["name"] = ExtractedFact("name", name, _norm_text(name))

    # Compound introduction: "I am a Web Developer from Milwaukee Wisconsin"
    compound_intro = re.search(
        r"\bI (?:am|'m) (?:a |an )?(?P<occupation>[^,]+?)\s+(?:from|in)\s+(?P<location>.+?)(?:\.|$|,)",
        text,
        re.IGNORECASE
    )
    if compound_intro:
        occ = compound_intro.group("occupation").strip()
        loc = compound_intro.group("location").strip()
        # Only extract if occupation looks like a job title (not a state of being)
        if occ and len(occ) > 2 and not any(word in occ.lower() for word in ["going", "coming", "person", "student", "happy", "sad"]):
            facts["occupation"] = ExtractedFact("occupation", occ, occ.lower())
        if loc and len(loc) > 2:
            facts["location"] = ExtractedFact("location", loc, loc.lower())

    # Employer
    # Examples:
    # - "I work at Microsoft as a senior developer."
    # - "I work as a data scientist at Vertex Analytics."
    # - "I work at Amazon, not Microsoft."
    # - "I run a sticker shop called The Printing Lair"
    # - "I work for myself" / "I'm self-employed"
    # - "I don't work at Google anymore" (negation/correction)
    # - "I'm still at Microsoft" (confirmation)
    
    # Check for employer negations first ("I don't work at X anymore")
    # Also look for "I left X" patterns
    m = re.search(
        r"\bi (?:don't|do not|no longer) work (?:at|for)\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+anymore|\s+now)?(?:\s*[,\.;]|\s*$)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"\bi left\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+last|\s+this|\s+a|\s*[,\.;]|\s*$)",
            text,
            flags=re.IGNORECASE,
        )
    if m:
        old_employer = m.group(1).strip()
        # Store in employer slot with "LEFT:" prefix - this allows contradiction detection
        # against previous employer values
        facts["employer"] = ExtractedFact("employer", f"LEFT:{old_employer}", f"left {_norm_text(old_employer)}")
    
    # Check for employer confirmations ("I'm still at X")
    m = re.search(
        r"\bi(?:'m| am) still (?:at|with)\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s*[,\.;]|\s*$)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        employer = m.group(1).strip()
        facts["employer"] = ExtractedFact("employer", employer, _norm_text(employer))
    
    # Check for self-employment first
    if re.search(r"\b(?:i work for myself|i'm self[- ]?employed|i am self[- ]?employed)", text, flags=re.IGNORECASE):
        facts["employer"] = ExtractedFact("employer", "self-employed", "self-employed")
    
    # Check for "I run [business]" pattern
    m = re.search(r"\bi run (?:a |an )?([^\n\r\.;,]+?)(?:\s+(?:called|and|but|,|\.|;)|\s*$)", text, flags=re.IGNORECASE)
    if m and "employer" not in facts:
        business = m.group(1).strip()
        # Extract business name if "called X" follows
        m2 = re.search(r"called\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+(?:and|but|,|\.|;\()|\s*$)", text)
        if m2:
            business = m2.group(1).strip()
        if business:
            facts["employer"] = ExtractedFact("employer", f"self-employed ({business})", _norm_text(business))
    
    # Try "I work at/for X" pattern
    if "employer" not in facts:
        m = re.search(
            r"\b(?:i work at|i work for)\s+([^\n\r\.;,]+)",
            text,
            flags=re.IGNORECASE,
        )
        if not m:
            # Fallback: look for "at [company]" anywhere (for "I work as X at Y" patterns)
            m = re.search(r"\bat\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+(?:as|and|but|in|on|for|with|where|,|\.|;)|\s*$)", text)
        if m:
            employer_raw = m.group(1)
            # Trim at common continuations
            employer_raw = re.split(r"\b(?:as|and|but|though|however|,|\.|;|\(|\))\b", employer_raw, maxsplit=1, flags=re.IGNORECASE)[0]
            employer_raw = employer_raw.strip()
            if employer_raw:
                facts["employer"] = ExtractedFact("employer", employer_raw, _norm_text(employer_raw))

    # Job title / role / occupation
    m = re.search(r"\bmy (?:role|job title|title) is\s+([^\n\r\.;,]+)", text, flags=re.IGNORECASE)
    if not m:
        # Match "I am a [title]" or "[title] by degree/trade/profession"
        m = re.search(r"\b(?:i am a|i'm a)\s+([A-Z][A-Za-z\s]+?)(?:\s+(?:by|at|for|and)|\s*$)", text)
        if not m:
            m = re.search(r"\b([A-Z][A-Za-z\s]+?)\s+by\s+(?:degree|trade|profession)", text)
    if m:
        title_raw = m.group(1).strip()
        title_raw = re.split(r"\b(?:at|for|in|by)\b", title_raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if title_raw and len(title_raw.split()) <= 4:  # Keep it reasonable (1-4 words)
            facts["title"] = ExtractedFact("title", title_raw, _norm_text(title_raw))

    # Location
    # Examples:
    # - "I live in Seattle, Washington."
    # - "I live in the Seattle metro area, specifically in Bellevue."
    # - "I moved to Denver last month"
    m = re.search(r"\bi live in\s+([^\n\r\.;]+)", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bi moved to\s+([A-Z][a-zA-Z .'-]{2,60})", text, flags=re.IGNORECASE)
    if m:
        loc_raw = m.group(1).strip()
        # Prefer the last "in X" if present ("specifically in Bellevue")
        m2 = re.search(r"\bin\s+([A-Z][a-zA-Z .'-]{2,60})\b", loc_raw)
        if m2:
            loc_value = m2.group(1).strip()
        else:
            # Split on temporal markers or punctuation
            loc_value = re.split(r"\s+(?:last|this|in|on|during)\s+|\.|,", loc_raw, maxsplit=1)[0].strip()
        if loc_value:
            facts["location"] = ExtractedFact("location", loc_value, _norm_text(loc_value))

    # Years programming experience
    # Examples:
    # - "I've been programming for 10 years"
    # - "it's closer to 12 years" (correction)
    # - "actually 12 years of experience" (correction)
    # - "more like 12 years" (correction)
    m = re.search(
        r"\b(?:i'?ve been programming for|i have been programming for)\s+(\d{1,3})\s+years\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        # Try correction patterns
        m = re.search(
            r"(?:it'?s\s+)?(?:closer to|actually|more like|really)\s+(\d{1,3})(?:\s+years)?(?:\s+(?:of\s+)?(?:experience|programming))?",
            text,
            flags=re.IGNORECASE,
        )
    if m:
        years = int(m.group(1))
        facts["programming_years"] = ExtractedFact("programming_years", years, str(years))

    # Age
    # Examples:
    # - "I am 25 years old"
    # - "I'm 30 years old"
    # - "I'm 28"
    # - "I just turned 29 today"
    # - "I am twenty-five years old"
    # - "I'm actually 34, not 32" (correction)
    # - "Wait, I'm actually 34" (correction)
    # - "My age is actually 34" (correction)
    
    # Try correction patterns first (they're more specific)
    m = re.search(
        r"\b(?:i'?m|i am)\s+actually\s+(\d{1,3})(?:\s*,?\s*not\s+\d+)?(?:\s+years old)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"\b(?:wait|actually)[,\s]+(?:i'?m|i am)\s+(?:actually\s+)?(\d{1,3})(?:\s+years old)?\b",
            text,
            flags=re.IGNORECASE,
        )
    if not m:
        m = re.search(
            r"\bmy age is (?:actually\s+)?(\d{1,3})\b",
            text,
            flags=re.IGNORECASE,
        )
    if not m:
        # Standard patterns
        m = re.search(
            r"\bi(?:'m| am)\s+(\d{1,3})(?:\s+years old)?\b",
            text,
            flags=re.IGNORECASE,
        )
    if not m:
        m = re.search(
            r"\bi (?:just )?turned\s+(\d{1,3})\b",
            text,
            flags=re.IGNORECASE,
        )
    if m:
        age = int(m.group(1))
        # Sanity check: age should be between 1 and 120
        if 1 <= age <= 120:
            facts["age"] = ExtractedFact("age", age, str(age))

    # First programming language
    # Examples:
    # - "I've been programming for 8 years, starting with Python."
    # - "I started with Python."
    # - "My first programming language was Python."
    m = re.search(
        r"\b(?:starting with|started with|my first (?:programming )?language was)\s+([A-Z][A-Za-z0-9+_.#-]{1,40})\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        lang = m.group(1).strip()
        facts["first_language"] = ExtractedFact("first_language", lang, _norm_text(lang))

    # Team size
    m = re.search(r"\bteam of\s+(\d{1,3})\b", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bteam is\s+(\d{1,3})\b", text, flags=re.IGNORECASE)
    if m:
        size = int(m.group(1))
        facts["team_size"] = ExtractedFact("team_size", size, str(size))

    # Remote vs office preference
    pref: Optional[bool] = None
    lowered = text.lower()
    if "prefer working remotely" in lowered or "prefer remote" in lowered:
        pref = True
    elif "hate working remotely" in lowered or "prefer being in the office" in lowered or "prefer the office" in lowered:
        pref = False

    if pref is not None:
        facts["remote_preference"] = ExtractedFact("remote_preference", pref, "remote" if pref else "office")

    # Favorite color
    # Examples:
    # - "My favorite color is orange."
    # - "My favourite colour is light blue."
    m = re.search(
        r"\bmy\s+favou?rite\s+colou?r\s+is\s+([^\n\r\.;,!\?]{2,60})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        color_raw = m.group(1).strip()
        # Trim at common continuations.
        color_raw = re.split(r"\b(?:and|but|though|however)\b", color_raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if color_raw:
            facts["favorite_color"] = ExtractedFact("favorite_color", color_raw, _norm_text(color_raw))
    
    # Skip if category is too generic or already handled
    # Common words that don't make good fact categories
    # Can be extended as needed for specific use cases
    _SKIP_FAVORITE_CATEGORIES = {"thing", "one", "part", "time", "way", "place"}
    
    # Generic favorite X pattern (dynamic fact categories)
    # Examples:
    # - "My favorite snack is popcorn"
    # - "My favorite movie is The Matrix"
    # - "My favourite book is 1984"
    if "favorite_color" not in facts:  # Don't override specific patterns
        m = re.search(
            r"\bmy\s+favou?rite\s+([a-z_]+)\s+is\s+([^\n\r\.;,!\?]{2,60})",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            category = m.group(1).strip().lower()
            value_raw = m.group(2).strip()
            # Trim at common continuations
            value_raw = re.split(r"\b(?:and|but|though|however)\b", value_raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            
            if category not in _SKIP_FAVORITE_CATEGORIES and value_raw:
                slot_name = f"favorite_{category}"
                facts[slot_name] = ExtractedFact(slot_name, value_raw, _norm_text(value_raw))

    # Education (very rough; enough for Stanford vs MIT undergrad contradictions)
    # Combined pattern: "both my undergrad and Master's were from MIT"
    m = re.search(
        r"\bboth\s+my\s+(?:undergrad|undergraduate)(?:\s+degree)?\s+and\s+(?:my\s+)?master'?s(?:\s+degree)?\s+(?:were|was)?\s*(?:from|at)\s+([A-Z][A-Za-z .'-]{2,60})\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        school = m.group(1).strip()
        if school:
            facts["undergrad_school"] = ExtractedFact("undergrad_school", school, _norm_text(school))
            facts["masters_school"] = ExtractedFact("masters_school", school, _norm_text(school))

    m = re.search(r"\bundergraduate (?:degree )?was from\s+([A-Z][A-Za-z .'-]{2,60})\b", text, flags=re.IGNORECASE)
    if m:
        school = m.group(1).strip()
        facts["undergrad_school"] = ExtractedFact("undergrad_school", school, _norm_text(school))

    m = re.search(r"\bmaster'?s (?:degree )?.*?from\s+([A-Z][A-Za-z .'-]{2,60})\b", text, flags=re.IGNORECASE)
    if m:
        school = m.group(1).strip()
        facts["masters_school"] = ExtractedFact("masters_school", school, _norm_text(school))
    
    # Siblings
    # Examples:
    # - "I have two siblings"
    # - "I have 3 siblings"
    m = re.search(r"\bi have\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+sibling", text, flags=re.IGNORECASE)
    if m:
        count_str = m.group(1).strip()
        # Convert words to numbers
        word_to_num = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                       "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
        count_normalized = word_to_num.get(count_str.lower(), count_str)
        facts["siblings"] = ExtractedFact("siblings", count_normalized, count_normalized)
    
    # Languages spoken
    # Examples:
    # - "I speak three languages"
    # - "I speak 5 languages"
    m = re.search(r"\bi speak\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+language", text, flags=re.IGNORECASE)
    if m:
        count_str = m.group(1).strip()
        word_to_num = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                       "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
        count_normalized = word_to_num.get(count_str.lower(), count_str)
        facts["languages_spoken"] = ExtractedFact("languages_spoken", count_normalized, count_normalized)
    
    # Graduation year
    # Examples:
    # - "I graduated in 2020"
    # - "I graduated from Stanford in 2018"
    m = re.search(r"\bi graduated\s+(?:in|from.*in)\s+(19\d{2}|20\d{2})\b", text, flags=re.IGNORECASE)
    if m:
        year = m.group(1).strip()
        facts["graduation_year"] = ExtractedFact("graduation_year", year, year)
    
    # Degree type (PhD vs Master's vs Bachelor's)
    # Examples:
    # - "I have a PhD"
    # - "I have a Master's degree"
    # - "I have a PhD in Machine Learning"
    # - "I never said I had a PhD. I have a Master's degree."
    # - "I do have a PhD"
    degree_patterns = [
        (r"\bi have a\s+(phd|ph\.d\.?|doctorate)\b", "PhD"),
        (r"\bi have a\s+(master'?s?\s*(?:degree)?)", "Masters"),
        (r"\bi have a\s+(bachelor'?s?\s*(?:degree)?)", "Bachelors"),
        (r"\bi do have a\s+(phd|ph\.d\.?|doctorate)\b", "PhD"),
        (r"\bi do have a\s+(master'?s?\s*(?:degree)?)", "Masters"),
        (r"\bi do have a\s+(bachelor'?s?\s*(?:degree)?)", "Bachelors"),
        (r"\bcompleted my\s+(doctorate|phd|ph\.d\.?)", "PhD"),
        (r"\bcompleted my\s+(master'?s)", "Masters"),
    ]
    for pattern, degree_type in degree_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            facts["degree_type"] = ExtractedFact("degree_type", degree_type, degree_type.lower())
            break
    
    # Project name/description
    # Examples:
    # - "My project is called CRT"
    # - "My current project is building a recommendation engine"
    # - "My project focus has shifted to real-time anomaly detection"
    m = re.search(r"\bmy (?:current )?project\s+(?:is\s+called|'?s\s+name\s+is|name\s+is|is\s+building)\s+(?:a\s+)?([A-Za-z][A-Za-z0-9+_.#\s-]{1,60}?)(?:\.|,|;|\s+for|\s+that|\s+to|\s*$)", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bmy project focus\s+(?:has\s+)?shifted to\s+([A-Za-z][A-Za-z0-9+_.#\s-]{1,60}?)(?:\.|,|;|\s*$)", text, flags=re.IGNORECASE)
    if m:
        project = m.group(1).strip()
        facts["project"] = ExtractedFact("project", project, _norm_text(project))

    # School (standalone "graduated from X" without year)
    # Examples:
    # - "I graduated from MIT"
    # - "I graduated from Stanford in 2018" (captured by graduation_year above, also here)
    m = re.search(r"\bi graduated from\s+([A-Z][A-Za-z\s.'-]{1,50}?)(?:\s+in\s+\d{4}|\.|,|;|\s*$)", text, flags=re.IGNORECASE)
    if m:
        school = m.group(1).strip()
        facts["school"] = ExtractedFact("school", school, _norm_text(school))
    
    # Favorite programming language
    # Examples:
    # - "My favorite programming language is Rust"
    # - "Python is my favorite language"
    # - "Python is actually my favorite language now"
    # - "I prefer Python" (only if Python is a known programming language)
    #
    # Known programming languages to avoid false positives like "I prefer working"
    _KNOWN_PROG_LANGS = {
        "python", "javascript", "typescript", "java", "rust", "go", "golang",
        "c", "cpp", "c++", "csharp", "c#", "ruby", "php", "swift", "kotlin",
        "scala", "haskell", "perl", "r", "matlab", "julia", "elixir", "erlang",
        "clojure", "lua", "dart", "fortran", "cobol", "assembly", "sql", "bash",
        "powershell", "groovy", "f#", "ocaml", "lisp", "scheme", "prolog",
        "objective-c", "objectivec", "zig", "nim", "crystal", "elm"
    }
    
    m = re.search(r"\bmy favorite (?:programming )?language is\s+([A-Z][A-Za-z0-9+#]{1,20})\b", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\b([A-Z][A-Za-z0-9+#]{1,20})\s+is (?:actually )?my favorite (?:programming )?language", text, flags=re.IGNORECASE)
    if not m:
        # "I prefer X" pattern - only match if X is a known programming language
        m = re.search(r"\bi prefer\s+([A-Z][A-Za-z0-9+#]{1,20})\b", text, flags=re.IGNORECASE)
        if m and m.group(1).lower().strip() not in _KNOWN_PROG_LANGS:
            m = None  # Not a known programming language, skip
    if m:
        lang = m.group(1).strip()
        facts["programming_language"] = ExtractedFact("programming_language", lang, _norm_text(lang))
    
    # Pet (type and name)
    # Examples:
    # - "I have a golden retriever named Murphy"
    # - "My dog is a labrador"
    # - "Murphy is a labrador, not a golden retriever"
    m = re.search(r"\bi have a\s+([a-z]+(?:\s+[a-z]+)?)\s+named\s+([A-Z][a-z]+)", text, flags=re.IGNORECASE)
    if m:
        pet_type = m.group(1).strip()
        pet_name = m.group(2).strip()
        facts["pet"] = ExtractedFact("pet", pet_type, _norm_text(pet_type))
        facts["pet_name"] = ExtractedFact("pet_name", pet_name, _norm_text(pet_name))
    else:
        # Try just pet type
        m = re.search(r"\bmy (?:dog|cat|pet) is a\s+([a-z]+(?:\s+[a-z]+)?)", text, flags=re.IGNORECASE)
        if not m:
            # Try "[name] is a [breed]" pattern
            m = re.search(r"\b([A-Z][a-z]+)\s+is a\s+([a-z]+(?:\s+[a-z]+)?)", text, flags=re.IGNORECASE)
            if m:
                pet_name = m.group(1).strip()
                pet_type = m.group(2).strip()
                facts["pet"] = ExtractedFact("pet", pet_type, _norm_text(pet_type))
                facts["pet_name"] = ExtractedFact("pet_name", pet_name, _norm_text(pet_name))
        if m and not facts.get("pet"):
            pet_type = m.group(1).strip()
            facts["pet"] = ExtractedFact("pet", pet_type, _norm_text(pet_type))
    
    # Coffee preference
    # Examples:
    # - "I prefer dark roast coffee"
    # - "My coffee preference is light roast"
    # - "I've switched to light roast lately"
    m = re.search(r"\bi prefer\s+(dark|light|medium)\s+roast", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bmy coffee preference is\s+(dark|light|medium)\s+roast", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bswitched to\s+(dark|light|medium)\s+roast", text, flags=re.IGNORECASE)
    if m:
        coffee = m.group(1).strip() + " roast"
        facts["coffee"] = ExtractedFact("coffee", coffee, _norm_text(coffee))
    
    # Hobby
    # Examples:
    # - "My weekend hobby is rock climbing"
    # - "I enjoy trail running"
    # - "I've taken up trail running instead of climbing"
    m = re.search(r"\bmy (?:weekend )?hobby is\s+([a-z][a-z\s-]{2,40}?)(?:\.|,|;|\s*$)", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bi enjoy\s+([a-z][a-z\s-]{2,40}?)(?:\.|,|;|\s*$)", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\btaken up\s+([a-z][a-z\s-]{2,40}?)(?:\s+instead|\.|,|;|\s*$)", text, flags=re.IGNORECASE)
    if m:
        hobby = m.group(1).strip()
        facts["hobby"] = ExtractedFact("hobby", hobby, _norm_text(hobby))
    
    # Book currently reading
    # Examples:
    # - "I'm reading 'Designing Data-Intensive Applications'"
    # - "Now reading 'The Pragmatic Programmer'"
    m = re.search(r"\bi'?m reading ['\"]([^'\"]{5,80})['\"]", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bnow reading ['\"]([^'\"]{5,80})['\"]", text, flags=re.IGNORECASE)
    if m:
        book = m.group(1).strip()
        facts["book"] = ExtractedFact("book", book, _norm_text(book))

    return facts


def extract_fact_slots_contextual(text: str) -> Dict[str, ExtractedFact]:
    """
    Extract fact slots with Phase 2.0 temporal and domain metadata.
    
    This is the enhanced version of extract_fact_slots() that automatically
    adds temporal status and domain context to each extracted fact.
    
    Use this when you need full context-aware facts for:
    - Contradiction detection (same slot + same domain + same time = conflict)
    - Multi-value storage (different domains = can coexist)
    - Temporal reasoning ("I don't work at X anymore" = status: past)
    
    Args:
        text: The text to analyze
        
    Returns:
        Dictionary of slot -> ExtractedFact with temporal/domain metadata
    """
    from .domain_detector import detect_domains
    
    # First, get basic fact extraction
    basic_facts = extract_fact_slots(text)
    
    if not basic_facts:
        return basic_facts
    
    # Extract global temporal status and domains from source text
    text_temporal_status, text_period = extract_temporal_status(text)
    text_domains = tuple(detect_domains(text))
    
    # Enhance each fact with temporal/domain metadata
    enhanced_facts: Dict[str, ExtractedFact] = {}
    
    for slot, fact in basic_facts.items():
        # For employer slot, check for specific temporal indicators
        slot_temporal_status = text_temporal_status
        slot_period = text_period
        
        # Special handling for employer "LEFT:" prefix
        if slot == "employer" and str(fact.value).startswith("LEFT:"):
            slot_temporal_status = TemporalStatus.PAST
        
        # Create enhanced fact with metadata
        enhanced_facts[slot] = ExtractedFact(
            slot=fact.slot,
            value=fact.value,
            normalized=fact.normalized,
            temporal_status=slot_temporal_status,
            period_text=slot_period,
            domains=text_domains,
            confidence=0.9
        )
    
    return enhanced_facts


def is_temporal_update(old_fact: ExtractedFact, new_fact: ExtractedFact) -> bool:
    """
    Check if a new fact represents a temporal update (not a contradiction).
    
    Examples of temporal updates:
    - "I work at Google" → "I don't work at Google anymore" (status change)
    - Same value, new status = temporal update
    - "used to work at X" + "now work at Y" = both valid (different times)
    
    Args:
        old_fact: The existing fact
        new_fact: The incoming fact
        
    Returns:
        True if this is a temporal update, False if it might be a contradiction
    """
    # Different slots = not related
    if old_fact.slot != new_fact.slot:
        return False
    
    # Same value, different status = temporal update
    if old_fact.normalized == new_fact.normalized:
        if old_fact.temporal_status != new_fact.temporal_status:
            return True
    
    # New fact says old value is now "past" = temporal update
    if new_fact.temporal_status == TemporalStatus.PAST:
        # Check if new fact references the old value
        old_value_lower = str(old_fact.value).lower()
        new_value_lower = str(new_fact.value).lower()
        
        # "LEFT:Google" normalizes to "left google" or similar
        if old_value_lower in new_value_lower or new_value_lower.replace("left:", "").strip() == old_value_lower:
            return True
    
    # Both are "past" = historical, not current contradiction
    if old_fact.temporal_status == TemporalStatus.PAST and new_fact.temporal_status == TemporalStatus.PAST:
        return True
    
    return False


def domains_overlap(fact1: ExtractedFact, fact2: ExtractedFact) -> bool:
    """
    Check if two facts have overlapping domains.
    
    Used for contradiction detection: facts in different domains can coexist.
    e.g., "I'm a programmer" (tech domain) and "I'm a photographer" (creative domain)
    
    Args:
        fact1: First fact
        fact2: Second fact
        
    Returns:
        True if domains overlap (potential conflict), False if disjoint (can coexist)
    """
    domains1 = set(fact1.domains) if fact1.domains else {"general"}
    domains2 = set(fact2.domains) if fact2.domains else {"general"}
    
    # "general" overlaps with everything
    if domains1 == {"general"} or domains2 == {"general"}:
        return True
    
    # Check for actual overlap
    return bool(domains1 & domains2)

