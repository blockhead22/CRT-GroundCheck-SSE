"""
Source Authority Detection for CRT Assertion Ingestion

Detects whether a user message is:
- A direct first-person assertion (highest authority)
- Reported speech from a third party (lower authority)
- A historical/journal entry (lower authority, temporal context)
- A meta-correction that should resolve contradictions, not create new ones

This module exists because CRT's append-only ledger must preserve all
assertions, but it MUST weight them differently.  "My favorite color is
orange" and "Mike says it's blue" both get stored — but with different
confidence levels and source tags so contradiction resolution can prefer
direct assertions over hearsay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceAuthority:
    """Result of source authority analysis on user text."""

    # What kind of assertion is this?
    kind: str  # "direct" | "reported_speech" | "journal" | "contextual" | "meta_correction"

    # Adjusted confidence (replaces the default 0.95)
    confidence: float

    # Detected speaker name, if any (e.g. "Mike")
    speaker: Optional[str] = None

    # Temporal framing detected? (e.g. "old journal", "back then", "used to")
    is_historical: bool = False

    # Reason string for logging/debugging
    reason: str = ""


# ---------------------------------------------------------------------------
# Reported speech detection
# ---------------------------------------------------------------------------

# "Speaking as X:", "X here:", "This is X:", "X says", "X told me"
_REPORTED_SPEAKER_RE = re.compile(
    r"(?:speaking\s+as|this\s+is|talking\s+as)\s+(?:my\s+)?(?:best\s+)?(?:friend\s+)?(\w+)"
    r"|(\w+)\s+(?:here|again)\s*:"
    r"|(?:my\s+(?:friend|buddy|colleague|coworker|boss|partner|wife|husband|mom|dad|brother|sister)\s+)(\w+)\s+(?:says?|said|told|thinks?|thought|mentioned|claims?)"
    r"|(\w+)\s+(?:says?|said|told\s+me|thinks?|thought|mentioned|claims?)\s+(?:that\s+)?(?:my|i|you)",
    re.IGNORECASE,
)

# Phrases that frame the text as someone else's words
_THIRD_PARTY_PHRASES = (
    "speaking as ",
    "according to ",
    "he said ",
    "she said ",
    "they said ",
    "he told me ",
    "she told me ",
    "they told me ",
    "my friend says ",
    "my boss says ",
    "my boss asked ",
    "my mom says ",
    "my dad says ",
    "someone told me ",
)

# ---------------------------------------------------------------------------
# Journal / historical detection
# ---------------------------------------------------------------------------

_JOURNAL_PHRASES = (
    "my old journal",
    "my journal",
    "journal entry",
    "from my journal",
    "from my diary",
    "i wrote in my",
    "i found this note",
    "old note ",
    "old entry ",
    "back then ",
    "at the time ",
    "when i was younger",
    "years ago ",
    "months ago ",
    "a while back ",
)

_HISTORICAL_RE = re.compile(
    r"\b(used\s+to\s+be|back\s+when|at\s+that\s+time|in\s+the\s+past|"
    r"was\s+going\s+through|i\s+was\s+going\s+through|going\s+through\s+a)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Contextual assertion detection ("I told my boss X")
# ---------------------------------------------------------------------------

_CONTEXTUAL_RE = re.compile(
    r"\b(i\s+told\s+(?:my|him|her|them)|i\s+said\s+to\s+(?:my|him|her|them)|"
    r"i\s+mentioned\s+to\s+(?:my|him|her|them)|"
    r"when\s+(?:he|she|they|my\s+\w+)\s+asked|"
    r"(?:he|she|they|my\s+\w+)\s+asked\s+me)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Meta-correction detection
# ---------------------------------------------------------------------------

# Strong patterns that indicate the user is trying to close a contradiction,
# not open a new one.  These should trigger resolution, not ingestion.
_META_CORRECTION_RE = re.compile(
    r"\b(ignore\s+the\s+noise|ignore\s+(?:all\s+)?(?:the\s+)?(?:other|rest|previous))"
    r"|(?:just\s+to\s+(?:confirm|clarify|be\s+clear))"
    r"|(?:always\s+has\s+been)"
    r"|(?:no,?\s+seriously)"
    r"|(?:seriously\s+(?:though|aether))"
    r"|(?:my\s+(?:real|actual|true)\s+(?:favorite|favourite))"
    r"|(?:the\s+(?:real|actual|true)\s+answer)"
    r"|(?:(?:that|the)\s+other\s+stuff\s+was\s+(?:just|me))"
    r"|(?:i(?:'m|\s+am)\s+sure\s+about\s+(?:it|this))"
    r"|(?:for\s+the\s+(?:last|final)\s+time)"
    r"|(?:once\s+and\s+for\s+all)"
    r"|(?:let\s+me\s+(?:settle|clear)\s+this)",
    re.IGNORECASE,
)

# Lighter patterns — these reduce confidence but don't trigger resolution
_EMPHASIS_RE = re.compile(
    r"\b(i(?:'m|\s+am)\s+(?:positive|certain|confident|100%?))"
    r"|(?:i\s+(?:already|just)\s+(?:told|said|mentioned))"
    r"|(?:i\s+keep\s+(?:saying|telling))"
    r"|(?:how\s+many\s+times)",
    re.IGNORECASE,
)


def classify_source_authority(text: str) -> SourceAuthority:
    """Analyze user text and return source authority classification.

    This runs BEFORE the memory is stored.  It determines:
    - Whether the assertion is direct, reported, historical, or contextual
    - The adjusted confidence level
    - Any detected speaker name
    - Whether this is a meta-correction that should resolve rather than create
    """
    lower = text.lower().strip()

    # --- 1. Meta-correction (highest priority) ---
    if _META_CORRECTION_RE.search(text):
        return SourceAuthority(
            kind="meta_correction",
            confidence=0.97,  # High — user is explicitly resolving
            reason="meta_correction_pattern",
        )

    # --- 2. Journal / historical (check BEFORE reported speech) ---
    # Journal phrases must be checked first because "Journal entry again:"
    # would otherwise match the reported-speech "X again:" pattern.
    if any(p in lower for p in _JOURNAL_PHRASES):
        return SourceAuthority(
            kind="journal",
            confidence=0.50,  # Low — explicitly past/historical
            is_historical=True,
            reason="journal_phrase",
        )

    if _HISTORICAL_RE.search(text):
        return SourceAuthority(
            kind="journal",
            confidence=0.55,
            is_historical=True,
            reason="historical_pattern",
        )

    # --- 3. Reported speech / third-party ---
    speaker_match = _REPORTED_SPEAKER_RE.search(text)
    if speaker_match:
        # Extract the speaker name from whichever group matched
        speaker = next((g for g in speaker_match.groups() if g), None)
        # Filter out false-positive speaker names (common words)
        _false_speakers = {"from", "this", "that", "here", "there", "entry", "note"}
        if speaker and speaker.lower() not in _false_speakers:
            return SourceAuthority(
                kind="reported_speech",
                confidence=0.55,  # Much lower — hearsay
                speaker=speaker,
                reason="reported_speaker_pattern",
            )

    # Check phrase-based third-party detection (excluding journal phrases)
    _non_journal_third_party = [
        p for p in _THIRD_PARTY_PHRASES
        if "journal" not in p and "diary" not in p and "note" not in p
    ]
    if any(lower.startswith(p) or f". {p}" in lower for p in _non_journal_third_party):
        return SourceAuthority(
            kind="reported_speech",
            confidence=0.55,
            reason="third_party_phrase",
        )

    # --- 4. Contextual ("I told my boss X") ---
    if _CONTEXTUAL_RE.search(text):
        return SourceAuthority(
            kind="contextual",
            confidence=0.70,  # Medium — user said it, but in a reported context
            reason="contextual_report",
        )

    # --- 5. Emphasis patterns (still direct, but with emphasis) ---
    if _EMPHASIS_RE.search(text):
        return SourceAuthority(
            kind="direct",
            confidence=0.97,  # Slightly higher — user is emphasizing
            reason="emphasis_pattern",
        )

    # --- 6. Default: direct assertion ---
    return SourceAuthority(
        kind="direct",
        confidence=0.95,
        reason="direct_assertion",
    )
