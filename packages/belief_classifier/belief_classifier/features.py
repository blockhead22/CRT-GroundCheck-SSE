"""Feature extraction from ContradictionPair for XGBoost input."""

from __future__ import annotations

import math
import re
from typing import Dict, List

from .types import ContradictionPair

# ── Language detection patterns ──────────────────────────────────────────────

_CORRECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bactually\b", re.IGNORECASE),
    re.compile(r"\bno[,.]?\s", re.IGNORECASE),
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bwrong\b", re.IGNORECASE),
    re.compile(r"\bcorrection\b", re.IGNORECASE),
    re.compile(r"\bwait\b", re.IGNORECASE),
    re.compile(r"\bI meant\b", re.IGNORECASE),
    re.compile(r"\blet me correct\b", re.IGNORECASE),
]

_TEMPORAL_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bused to\b", re.IGNORECASE),
    re.compile(r"\bwas\b", re.IGNORECASE),
    re.compile(r"\bformerly\b", re.IGNORECASE),
    re.compile(r"\bnow\b", re.IGNORECASE),
    re.compile(r"\bcurrently\b", re.IGNORECASE),
    re.compile(r"\bchanged\b", re.IGNORECASE),
    re.compile(r"\bmoved\b", re.IGNORECASE),
    re.compile(r"\bleft\b", re.IGNORECASE),
    re.compile(r"\bquit\b", re.IGNORECASE),
    re.compile(r"\bstarted\b", re.IGNORECASE),
]

_NEGATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\b", re.IGNORECASE),
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\bstopped\b", re.IGNORECASE),
]

# Canonical ordered list of feature names (used by classifiers for consistency)
FEATURE_NAMES: List[str] = [
    "trust_delta",
    "trust_max",
    "trust_min",
    "time_gap_hours",
    "time_gap_log",
    "similarity",
    "is_exclusive",
    "has_correction_language",
    "has_temporal_language",
    "has_negation",
    "old_text_length",
    "new_text_length",
    "length_ratio",
    "has_slot",
    "is_fact_format",
]


def _any_match(text: str, patterns: List[re.Pattern]) -> float:
    """Return 1.0 if any pattern matches, 0.0 otherwise."""
    return 1.0 if any(p.search(text) for p in patterns) else 0.0


def extract_features(pair: ContradictionPair) -> Dict[str, float]:
    """Extract a flat feature dict from a ContradictionPair.

    Returns a dict with string keys (matching FEATURE_NAMES) and float values,
    suitable for feeding into an XGBoost model.
    """
    time_gap_hours = (pair.new_timestamp - pair.old_timestamp) / 3600.0
    old_len = float(len(pair.old_text))
    new_len = float(len(pair.new_text))

    return {
        "trust_delta": pair.new_trust - pair.old_trust,
        "trust_max": max(pair.old_trust, pair.new_trust),
        "trust_min": min(pair.old_trust, pair.new_trust),
        "time_gap_hours": time_gap_hours,
        "time_gap_log": math.log1p(abs(time_gap_hours)),
        "similarity": pair.similarity_score,
        "is_exclusive": 1.0 if pair.is_exclusive_slot else 0.0,
        "has_correction_language": _any_match(pair.new_text, _CORRECTION_PATTERNS),
        "has_temporal_language": _any_match(pair.new_text, _TEMPORAL_PATTERNS),
        "has_negation": _any_match(pair.new_text, _NEGATION_PATTERNS),
        "old_text_length": old_len,
        "new_text_length": new_len,
        "length_ratio": new_len / max(old_len, 1.0),
        "has_slot": 1.0 if pair.slot_name is not None else 0.0,
        "is_fact_format": 1.0 if (
            pair.old_text.startswith("FACT:") or pair.new_text.startswith("FACT:")
        ) else 0.0,
    }
