"""Lightweight fact-slot extraction for CRT.

Goal: reduce false contradiction triggers from generic semantic similarity by
comparing only facts that refer to the same attribute ("slot").

This is intentionally heuristic (no ML) and is tuned to the kinds of personal
profile facts used in CRT stress tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExtractedFact:
    slot: str
    value: Any
    normalized: str


_WS_RE = re.compile(r"\s+")


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
    """Extract a small set of personal-profile fact slots from free text."""
    facts: Dict[str, ExtractedFact] = {}

    if not text or not text.strip():
        return facts

    # Name
    # Examples:
    # - "My name is Sarah."
    # - "Yes, I'm Sarah"
    m = re.search(r"\bmy name is\s+([A-Z][a-zA-Z'-]{1,40})\b", text)
    if not m:
        m = re.search(r"\bi\s*'?m\s+([A-Z][a-zA-Z'-]{1,40})\b", text)
    if m:
        name = m.group(1)
        facts["name"] = ExtractedFact("name", name, _norm_text(name))

    # Employer
    # Examples:
    # - "I work at Microsoft as a senior developer."
    # - "I work at Amazon, not Microsoft."
    m = re.search(
        r"\b(?:i work at|i work for)\s+([^\n\r\.;,]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        employer_raw = m.group(1)
        # Trim at common continuations
        employer_raw = re.split(r"\b(?:as|and|but|though|however|,|\.|;|\(|\))\b", employer_raw, maxsplit=1, flags=re.IGNORECASE)[0]
        employer_raw = employer_raw.strip()
        if employer_raw:
            facts["employer"] = ExtractedFact("employer", employer_raw, _norm_text(employer_raw))

    # Job title / role
    m = re.search(r"\bmy (?:role|job title|title) is\s+([^\n\r\.;,]+)", text, flags=re.IGNORECASE)
    if m:
        title_raw = m.group(1).strip()
        title_raw = re.split(r"\b(?:at|for|in)\b", title_raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if title_raw:
            facts["title"] = ExtractedFact("title", title_raw, _norm_text(title_raw))

    # Location
    # Examples:
    # - "I live in Seattle, Washington."
    # - "I live in the Seattle metro area, specifically in Bellevue."
    m = re.search(r"\bi live in\s+([^\n\r\.;]+)", text, flags=re.IGNORECASE)
    if m:
        loc_raw = m.group(1).strip()
        # Prefer the last "in X" if present ("specifically in Bellevue")
        m2 = re.search(r"\bin\s+([A-Z][a-zA-Z .'-]{2,60})\b", loc_raw)
        if m2:
            loc_value = m2.group(1).strip()
        else:
            loc_value = re.split(r"[,\.]", loc_raw, maxsplit=1)[0].strip()
        if loc_value:
            facts["location"] = ExtractedFact("location", loc_value, _norm_text(loc_value))

    # Years programming experience
    m = re.search(
        r"\b(?:i'?ve been programming for|i have been programming for)\s+(\d{1,3})\s+years\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        years = int(m.group(1))
        facts["programming_years"] = ExtractedFact("programming_years", years, str(years))

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

    # Education (very rough; enough for Stanford vs MIT undergrad contradictions)
    m = re.search(r"\bundergraduate (?:degree )?was from\s+([A-Z][A-Za-z .'-]{2,60})\b", text)
    if m:
        school = m.group(1).strip()
        facts["undergrad_school"] = ExtractedFact("undergrad_school", school, _norm_text(school))

    m = re.search(r"\bmaster'?s (?:degree )?.*?from\s+([A-Z][A-Za-z .'-]{2,60})\b", text)
    if m:
        school = m.group(1).strip()
        facts["masters_school"] = ExtractedFact("masters_school", school, _norm_text(school))

    return facts
