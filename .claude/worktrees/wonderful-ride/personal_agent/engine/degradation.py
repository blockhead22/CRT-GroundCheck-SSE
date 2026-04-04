"""Output degradation detection hook (Holden quarantine integration point)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List


@dataclass
class DegradationAssessment:
    is_degraded: bool
    score: float
    reasons: List[str] = field(default_factory=list)


class DegradationDetector:
    """Heuristic detector for low-quality output.

    It catches repetitive, low-information, or malformed output and exposes a
    stable interface for future learned detectors.
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = float(max(0.0, min(1.0, threshold)))

    @staticmethod
    def _repetition_ratio(text: str) -> float:
        tokens = [t for t in re.split(r"\s+", (text or "").strip().lower()) if t]
        if len(tokens) < 6:
            return 0.0
        bigrams = list(zip(tokens, tokens[1:]))
        if not bigrams:
            return 0.0
        unique = len(set(bigrams))
        return 1.0 - (float(unique) / float(len(bigrams)))

    def assess(self, text: str, reasoning: str = "") -> DegradationAssessment:
        value = (text or "").strip()
        reasons: List[str] = []
        score = 0.0

        if not value:
            return DegradationAssessment(is_degraded=True, score=1.0, reasons=["empty_output"])

        if len(value) < 12:
            reasons.append("too_short")
            score += 0.25

        repetition = self._repetition_ratio(value)
        if repetition > 0.45:
            reasons.append("high_repetition")
            score += min(0.45, repetition)

        punct = len(re.findall(r"[^\w\s]", value))
        punct_ratio = float(punct) / float(max(1, len(value)))
        if punct_ratio > 0.28:
            reasons.append("punctuation_noise")
            score += min(0.25, punct_ratio)

        alpha = len(re.findall(r"[A-Za-z]", value))
        alpha_ratio = float(alpha) / float(max(1, len(value)))
        if alpha_ratio < 0.45:
            reasons.append("low_information_density")
            score += 0.2

        if "lorem ipsum" in value.lower():
            reasons.append("placeholder_text")
            score += 0.3

        # If the answer is empty but reasoning is large, likely stream parsing drift.
        if len(reasoning or "") > 400 and len(value) < 20:
            reasons.append("reasoning_answer_mismatch")
            score += 0.2

        score = max(0.0, min(1.0, score))
        return DegradationAssessment(
            is_degraded=(score >= self.threshold),
            score=score,
            reasons=reasons,
        )

