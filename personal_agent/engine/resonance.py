"""Resonance scoring hook (Mirus integration point)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from personal_agent.crt_core import encode_vector
from .anchors import AnchorSystem


@dataclass
class ResonanceSignal:
    resonance: float
    similarity: float
    anchor_overlap: float
    anchor_matches: List[str]


class ResonanceScorer:
    """Computes resonance beyond raw cosine similarity.

    The score blends semantic similarity with anchor overlap and is intended to be
    replaced or augmented by DNNT later.
    """

    def __init__(self, anchor_system: Optional[AnchorSystem] = None):
        self.anchor_system = anchor_system or AnchorSystem()

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 1e-12:
            return 0.0
        return float(np.dot(a, b) / denom)

    def score(
        self,
        *,
        query: str,
        memory_text: str,
        query_vector: Optional[np.ndarray] = None,
        memory_vector: Optional[np.ndarray] = None,
    ) -> ResonanceSignal:
        q_vec = query_vector if query_vector is not None else encode_vector(query or "")
        m_vec = memory_vector if memory_vector is not None else encode_vector(memory_text or "")

        similarity = self._cosine(q_vec, m_vec)
        similarity = max(0.0, min(1.0, (similarity + 1.0) / 2.0))

        anchor_overlap = self.anchor_system.overlap_score(query, memory_text)
        shared_anchors = sorted(
            set(self.anchor_system.matched_anchors(query))
            & set(self.anchor_system.matched_anchors(memory_text))
        )

        resonance = (0.85 * similarity) + (0.15 * anchor_overlap)
        resonance = max(0.0, min(1.0, resonance))

        return ResonanceSignal(
            resonance=resonance,
            similarity=similarity,
            anchor_overlap=anchor_overlap,
            anchor_matches=shared_anchors,
        )

