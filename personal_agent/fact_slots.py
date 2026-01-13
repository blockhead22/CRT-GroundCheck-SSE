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
    """Extract a small set of personal-profile fact slots from free text."""
    facts: Dict[str, ExtractedFact] = {}

    if not text or not text.strip():
        return facts

    # Structured facts/preferences (useful for onboarding and explicit corrections).
    # Examples:
    # - "FACT: name = Nick"
    # - "PREF: communication_style = concise"
    structured = re.search(
        r"\b(?:FACT|PREF):\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if structured:
        slot = structured.group(1).strip().lower()
        value_raw = structured.group(2).strip()
        # Keep this conservative: whitelist the slots we intentionally support.
        allowed = {
            "name",
            "employer",
            "title",
            "location",
            "pronouns",
            "communication_style",
            "goals",
            "favorite_color",
        }
        if slot in allowed and value_raw:
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
    name_pat = r"([A-Za-z][A-Za-z'-]{1,40}(?:\s+[A-Za-z][A-Za-z'-]{1,40}){0,2})"
    name_pat_title = r"([A-Z][A-Za-z'-]{1,40}(?:\s+[A-Z][A-Za-z'-]{1,40}){0,2})"

    # Very explicit "call me" pattern.
    m = re.search(r"\bcall me\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
    if m:
        name = m.group(1).strip()
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

    m = re.search(r"\bmy name is\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
    if not m:
        # Prefer TitleCase names for the generic "I'm X" pattern.
        m = re.search(r"\bi\s*'?m\s+" + name_pat_title + r"\b", text)
        if not m:
            # Allow a single-token lowercase name, but only when it appears as a direct
            # name declaration (no extra trailing content).
            m = re.search(r"^\s*i\s*'?m\s+([a-z][a-z'-]{1,40})\s*[\.!?]?\s*$", text, flags=re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        tokens = [t for t in re.split(r"\s+", name) if t]
        token_lowers = [t.lower() for t in tokens]

        # Filter obvious non-name phrases like "I'm trying to build ...".
        trailing = (text[m.end():] or "").lstrip().lower()
        looks_like_infinitive = trailing.startswith("to ")
        has_stopword = any(t in _NAME_STOPWORDS for t in token_lowers)

        # Reject common non-name tokens and infinitive phrases.
        if tokens and not has_stopword and not looks_like_infinitive:
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

    # Education (very rough; enough for Stanford vs MIT undergrad contradictions)
    m = re.search(r"\bundergraduate (?:degree )?was from\s+([A-Z][A-Za-z .'-]{2,60})\b", text, flags=re.IGNORECASE)
    if m:
        school = m.group(1).strip()
        facts["undergrad_school"] = ExtractedFact("undergrad_school", school, _norm_text(school))

    m = re.search(r"\bmaster'?s (?:degree )?.*?from\s+([A-Z][A-Za-z .'-]{2,60})\b", text, flags=re.IGNORECASE)
    if m:
        school = m.group(1).strip()
        facts["masters_school"] = ExtractedFact("masters_school", school, _norm_text(school))

    return facts
