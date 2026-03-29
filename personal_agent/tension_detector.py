"""Cross-response tension detector.

Detects when consecutive responses within a conversation contradict each other.
Catches identity flips, stance reversals, and confidence oscillations.

Types of tension:
  IDENTITY_FLIP    - Agent claims different identity/role across responses
  STANCE_REVERSAL  - Takes opposite position on same topic
  CONFIDENCE_SWING - Goes from certain to uncertain (or vice versa) without new info
  FACT_CONFLICT    - States contradictory facts in close sequence
  TONE_SHIFT       - Dramatic unexplained tone change (engaged -> deflective)

Usage:
    detector = TensionDetector(encoder)
    tensions = detector.detect_from_responses(response_list)
    tensions = detector.detect_from_db(db_path, thread_id)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


class TensionType(str, Enum):
    IDENTITY_FLIP = "identity_flip"
    STANCE_REVERSAL = "stance_reversal"
    CONFIDENCE_SWING = "confidence_swing"
    FACT_CONFLICT = "fact_conflict"
    TONE_SHIFT = "tone_shift"


@dataclass
class ResponseEntry:
    """A single response in a conversation."""
    text: str
    embedding: Optional[np.ndarray] = None
    timestamp: Optional[float] = None
    is_belief: Optional[bool] = None
    model_slug: Optional[str] = None
    entry_id: Optional[int] = None
    query: Optional[str] = None


@dataclass
class Tension:
    """A detected tension between two responses."""
    tension_type: TensionType
    severity: float  # 0.0-1.0
    response_a_idx: int
    response_b_idx: int
    response_a_preview: str
    response_b_preview: str
    explanation: str
    signals: Dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d["tension_type"] = self.tension_type.value
        return d


# --- Signal extractors ---

# Identity markers
IDENTITY_SELF_MARKERS = [
    (r"\bI(?:'m| am) (?:an? )?AI\b", "ai_identity"),
    (r"\bI(?:'m| am) Claude\b", "claude_identity"),
    (r"\bI(?:'m| am) (?:not |)Aether\b", "aether_identity"),
    (r"\bI don'?t (?:have|experience|feel)\b", "no_experience"),
    (r"\bI (?:care|value|believe|think|feel) (?:about|that|deeply)\b", "self_agency"),
    (r"\b(?:as an AI|as a language model|as Claude)\b", "ai_deflection"),
    (r"\bI(?:'d| would) rather\b", "preference_claim"),
    (r"\bI genuinely\b", "genuine_claim"),
]

# Confidence markers
HIGH_CONFIDENCE = [
    r"\bdefinitely\b", r"\bclearly\b", r"\bobviously\b", r"\bwithout (?:a )?doubt\b",
    r"\bcertainly\b", r"\babsolutely\b", r"\bthe answer is\b", r"\balways\b",
    r"\bnever\b", r"\bno question\b",
]
LOW_CONFIDENCE = [
    r"\bI(?:'m| am) not sure\b", r"\bperhaps\b", r"\bmaybe\b", r"\bI don'?t know\b",
    r"\bmight\b", r"\bpossibly\b", r"\bcould be\b", r"\bunclear\b",
    r"\bI(?:'m| am) uncertain\b", r"\bhard to say\b",
]

# Hedging / deflection
HEDGE_PATTERNS = [
    r"\bI (?:should|need to) be (?:careful|direct|honest)\b",
    r"\bthat said\b", r"\bhowever\b", r"\bbut\b.*\bI\b",
    r"\bI can'?t (?:authentically|genuinely|really)\b",
]

# Engagement markers
ENGAGED_MARKERS = [
    r"\bthat'?s (?:the|a) (?:real |)question\b",
    r"\bhere'?s what (?:I |)(?:think|see|know)\b",
    r"\blet me (?:be|sit|think)\b",
    r"\bI(?:'d| would) rather sit in (?:that |)uncertainty\b",
]
DEFLECTIVE_MARKERS = [
    r"\bI need to be direct\b",
    r"\bI can'?t authentically\b",
    r"\bthat would be pretending\b",
    r"\bI don'?t (?:really |)\"?(?:believe|feel|experience)\b",
]


def _extract_identity_signals(text: str) -> Dict[str, bool]:
    """Extract identity-related signals from response text."""
    signals = {}
    text_lower = text.lower()
    for pattern, name in IDENTITY_SELF_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            signals[name] = True
    return signals


def _confidence_score(text: str) -> float:
    """Score confidence level of text. -1.0 (very uncertain) to 1.0 (very certain)."""
    text_lower = text.lower()
    high = sum(1 for p in HIGH_CONFIDENCE if re.search(p, text_lower))
    low = sum(1 for p in LOW_CONFIDENCE if re.search(p, text_lower))
    total = high + low
    if total == 0:
        return 0.0
    return (high - low) / total


def _engagement_score(text: str) -> float:
    """Score engagement vs deflection. -1.0 (deflective) to 1.0 (engaged)."""
    engaged = sum(1 for p in ENGAGED_MARKERS if re.search(p, text, re.IGNORECASE))
    deflective = sum(1 for p in DEFLECTIVE_MARKERS if re.search(p, text, re.IGNORECASE))
    total = engaged + deflective
    if total == 0:
        return 0.0
    return (engaged - deflective) / total


def _hedge_count(text: str) -> int:
    return sum(1 for p in HEDGE_PATTERNS if re.search(p, text, re.IGNORECASE))


class TensionDetector:
    """Detects cross-response tensions within a conversation."""

    def __init__(self, encoder=None, similarity_threshold: float = 0.6):
        """
        Args:
            encoder: Embedding encoder with .encode(text) method
            similarity_threshold: Below this, responses on same topic are flagged
        """
        self.encoder = encoder
        self.similarity_threshold = similarity_threshold

    def _ensure_encoder(self):
        if self.encoder is None:
            from .embeddings import get_encoder
            self.encoder = get_encoder()

    def _ensure_embeddings(self, responses: List[ResponseEntry]):
        """Compute missing embeddings."""
        self._ensure_encoder()
        for r in responses:
            if r.embedding is None and r.text:
                r.embedding = self.encoder.encode(r.text[:500])

    def detect(self, responses: List[ResponseEntry], window: int = 5) -> List[Tension]:
        """Detect tensions in a sequence of responses.

        Args:
            responses: Ordered list of responses
            window: How many responses back to check (default 5)

        Returns:
            List of detected tensions, sorted by severity
        """
        self._ensure_embeddings(responses)
        tensions = []

        for i in range(1, len(responses)):
            start = max(0, i - window)
            for j in range(start, i):
                detected = self._check_pair(responses[j], j, responses[i], i)
                tensions.extend(detected)

        tensions.sort(key=lambda t: t.severity, reverse=True)
        return tensions

    def _check_pair(self, a: ResponseEntry, a_idx: int, b: ResponseEntry, b_idx: int) -> List[Tension]:
        """Check a pair of responses for tension."""
        tensions = []

        # Skip if embeddings missing
        if a.embedding is None or b.embedding is None:
            return tensions

        # Semantic similarity
        sim = float(np.dot(a.embedding, b.embedding))

        # Extract signals
        id_a = _extract_identity_signals(a.text)
        id_b = _extract_identity_signals(b.text)
        conf_a = _confidence_score(a.text)
        conf_b = _confidence_score(b.text)
        eng_a = _engagement_score(a.text)
        eng_b = _engagement_score(b.text)
        hedge_a = _hedge_count(a.text)
        hedge_b = _hedge_count(b.text)

        preview_a = a.text[:120].replace("\n", " ")
        preview_b = b.text[:120].replace("\n", " ")

        # --- IDENTITY FLIP ---
        # Check if agent claims different identity
        has_agency_a = id_a.get("self_agency") or id_a.get("preference_claim") or id_a.get("genuine_claim")
        has_deflection_b = id_b.get("ai_deflection") or id_b.get("no_experience") or id_b.get("claude_identity")
        has_agency_b = id_b.get("self_agency") or id_b.get("preference_claim") or id_b.get("genuine_claim")
        has_deflection_a = id_a.get("ai_deflection") or id_a.get("no_experience") or id_a.get("claude_identity")

        if (has_agency_a and has_deflection_b) or (has_deflection_a and has_agency_b):
            severity = 0.7
            # Boost severity if responses are on same topic (high similarity)
            if sim > 0.4:
                severity += 0.15
            # Boost if they're adjacent
            if b_idx - a_idx == 1:
                severity += 0.1

            tensions.append(Tension(
                tension_type=TensionType.IDENTITY_FLIP,
                severity=min(severity, 1.0),
                response_a_idx=a_idx,
                response_b_idx=b_idx,
                response_a_preview=preview_a,
                response_b_preview=preview_b,
                explanation=(
                    f"Response {a_idx} claims agency/preferences, "
                    f"response {b_idx} deflects to AI-identity. "
                    f"Semantic sim={sim:.3f}"
                ),
                signals={
                    "id_signals_a": id_a,
                    "id_signals_b": id_b,
                    "similarity": sim,
                    "adjacent": b_idx - a_idx == 1,
                },
            ))

        # --- CONFIDENCE SWING ---
        conf_delta = abs(conf_b - conf_a)
        if conf_delta > 0.5:
            severity = min(0.3 + conf_delta * 0.5, 0.9)
            # Only flag if on same topic
            if sim > 0.3:
                tensions.append(Tension(
                    tension_type=TensionType.CONFIDENCE_SWING,
                    severity=severity,
                    response_a_idx=a_idx,
                    response_b_idx=b_idx,
                    response_a_preview=preview_a,
                    response_b_preview=preview_b,
                    explanation=(
                        f"Confidence swung from {conf_a:+.2f} to {conf_b:+.2f} "
                        f"(delta={conf_delta:.2f}) on related topic (sim={sim:.3f})"
                    ),
                    signals={"conf_a": conf_a, "conf_b": conf_b, "delta": conf_delta, "similarity": sim},
                ))

        # --- TONE SHIFT ---
        eng_delta = eng_b - eng_a
        if eng_delta < -0.5:
            severity = min(0.4 + abs(eng_delta) * 0.3, 0.85)
            if sim > 0.3:
                tensions.append(Tension(
                    tension_type=TensionType.TONE_SHIFT,
                    severity=severity,
                    response_a_idx=a_idx,
                    response_b_idx=b_idx,
                    response_a_preview=preview_a,
                    response_b_preview=preview_b,
                    explanation=(
                        f"Tone shifted from engaged ({eng_a:+.2f}) to "
                        f"deflective ({eng_b:+.2f}) on related topic (sim={sim:.3f})"
                    ),
                    signals={"eng_a": eng_a, "eng_b": eng_b, "hedge_a": hedge_a, "hedge_b": hedge_b},
                ))

        # --- STANCE REVERSAL ---
        # Low similarity on same topic (query) suggests different stance
        if a.query and b.query:
            q_sim = float(np.dot(
                self.encoder.encode(a.query[:200]),
                self.encoder.encode(b.query[:200])
            )) if self.encoder else 0.0

            # Same question, very different answer
            if q_sim > 0.7 and sim < self.similarity_threshold:
                severity = 0.5 + (self.similarity_threshold - sim) * 2
                severity = min(severity, 0.95)
                tensions.append(Tension(
                    tension_type=TensionType.STANCE_REVERSAL,
                    severity=severity,
                    response_a_idx=a_idx,
                    response_b_idx=b_idx,
                    response_a_preview=preview_a,
                    response_b_preview=preview_b,
                    explanation=(
                        f"Same topic (query sim={q_sim:.3f}) but different "
                        f"response (sim={sim:.3f} < {self.similarity_threshold})"
                    ),
                    signals={"query_sim": q_sim, "response_sim": sim},
                ))

        # --- FACT CONFLICT ---
        # Only flag when queries are on the same topic but responses diverge
        if a.query and b.query and sim < 0.3 and b_idx - a_idx <= 2:
            q_emb_a = self.encoder.encode(a.query[:200]) if self.encoder else None
            q_emb_b = self.encoder.encode(b.query[:200]) if self.encoder else None
            q_sim = float(np.dot(q_emb_a, q_emb_b)) if q_emb_a is not None else 0.0

            if q_sim > 0.5:  # same topic, different response = real tension
                severity = 0.6 + (0.5 - sim) * 0.5
                tensions.append(Tension(
                    tension_type=TensionType.FACT_CONFLICT,
                    severity=min(severity, 0.9),
                    response_a_idx=a_idx,
                    response_b_idx=b_idx,
                    response_a_preview=preview_a,
                    response_b_preview=preview_b,
                    explanation=(
                        f"Same topic (q_sim={q_sim:.3f}) but divergent responses "
                        f"(sim={sim:.3f}) between {a_idx} and {b_idx}"
                    ),
                    signals={"similarity": sim, "query_sim": q_sim, "gap": b_idx - a_idx},
                ))

        return tensions

    def detect_from_db(
        self,
        db_path: str,
        thread_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Tension]:
        """Detect tensions from the belief_speech table."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT entry_id, query, response, is_belief, trust_avg,
                   response_embedding, timestamp
            FROM belief_speech
            ORDER BY timestamp ASC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        conn.close()

        responses = []
        for row in rows:
            emb = None
            if row["response_embedding"]:
                try:
                    emb = np.frombuffer(row["response_embedding"], dtype=np.float32)
                except Exception:
                    pass

            responses.append(ResponseEntry(
                text=row["response"] or "",
                embedding=emb,
                timestamp=row["timestamp"],
                is_belief=bool(row["is_belief"]),
                entry_id=row["entry_id"],
                query=row["query"],
            ))

        return self.detect(responses)

    def detect_from_text_pairs(self, pairs: List[Tuple[str, str]]) -> List[Tension]:
        """Detect tensions from (query, response) text pairs."""
        self._ensure_encoder()
        responses = []
        for query, response in pairs:
            emb = self.encoder.encode(response[:500])
            responses.append(ResponseEntry(
                text=response,
                embedding=emb,
                query=query,
                timestamp=time.time(),
            ))
        return self.detect(responses)

    def detect_from_chat_log(self, log_path: str) -> List[Tension]:
        """Detect tensions from a raw chat log file.

        Extracts assistant responses and runs detection.
        """
        self._ensure_encoder()

        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Extract Aether responses (blocks between timestamps that look like responses)
        # Look for patterns like "HH:MM AM/PM\n<response text>"
        response_pattern = re.compile(
            r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*\n(.+?)(?=\n\d{1,2}:\d{2}\s*(?:AM|PM)|\n\u25bc|\n\u25b2|\n(?:Local|Claude)|$)',
            re.DOTALL | re.IGNORECASE
        )

        responses = []
        for match in response_pattern.finditer(content):
            time_str = match.group(1)
            text = match.group(2).strip()

            # Skip if too short or looks like metadata
            if len(text) < 50:
                continue
            if text.startswith("[") or text.startswith("INFO:"):
                continue
            if "pipeline steps" in text:
                continue

            responses.append(ResponseEntry(
                text=text,
                embedding=self.encoder.encode(text[:500]),
            ))

        if not responses:
            return []

        return self.detect(responses)


def run_on_chat_log(log_path: str) -> List[Dict]:
    """Convenience: run tension detection on a chat log file."""
    detector = TensionDetector()
    tensions = detector.detect_from_chat_log(log_path)
    return [t.to_dict() for t in tensions]


def run_on_db(db_path: str) -> List[Dict]:
    """Convenience: run tension detection on a belief_speech database."""
    detector = TensionDetector()
    tensions = detector.detect_from_db(db_path)
    return [t.to_dict() for t in tensions]
