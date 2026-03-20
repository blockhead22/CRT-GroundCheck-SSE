"""NoTrustWeightingSystem — recency-only retrieval, no trust ordering.

All memories are stored and contradictions are flagged, but retrieval
ranks purely by recency (most-recently-stored wins), ignoring trust scores.

This isolates trust weighting: if CRT outperforms NoTrustWeighting,
the trust decay/update mechanism is demonstrably valuable beyond just
contradiction detection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eval.baselines._base import blank_response
from eval.baselines.no_ledger import _word_vec, _cosine_sim


class _MemEntry:
    __slots__ = ("text", "timestamp", "vec", "trust")

    def __init__(self, text: str, ts: int) -> None:
        self.text = text
        self.timestamp = ts
        self.vec = _word_vec(text)
        self.trust = 0.6  # stored but ignored in retrieval ranking


class NoTrustWeightingSystem:
    name = "NoTrustWeighting"

    def __init__(self) -> None:
        self._memories: List[_MemEntry] = []
        self._tick = 0

    def reset(self) -> None:
        self._memories = []
        self._tick = 0

    def _find_similar(self, text: str, threshold: float = 0.35) -> Optional[_MemEntry]:
        qvec = _word_vec(text)
        best_score = threshold
        best_mem: Optional[_MemEntry] = None
        for m in self._memories:
            score = _cosine_sim(qvec, m.vec)
            if score > best_score:
                best_score = score
                best_mem = m
        return best_mem

    def query(self, message: str, thread_id: str = "eval") -> Dict[str, Any]:
        is_question = message.rstrip().endswith("?")
        contradiction_flag = False

        if not is_question:
            similar = self._find_similar(message)
            if similar:
                contradiction_flag = True
                # Trust updated but not used for retrieval
                similar.trust = max(0.1, similar.trust - 0.15)
            self._memories.append(_MemEntry(text=message, ts=self._tick))
            self._tick += 1

        if not self._memories:
            return blank_response(
                answer="I don't have information about that.",
                gates_passed=False,
                gate_reason="no_memory",
            )

        qvec = _word_vec(message)
        # Score by similarity only — recency as tiebreak, trust IGNORED
        scored: List[Tuple[float, int, _MemEntry]] = []
        for m in self._memories:
            sim = _cosine_sim(qvec, m.vec)
            scored.append((sim, m.timestamp, m))
        scored.sort(reverse=True)

        best_sim, _, best_mem = scored[0]

        if best_sim >= 0.15:
            answer = best_mem.text
            gates_passed = True
            response_type = "belief"
            confidence = min(0.95, best_sim * 1.5)
        else:
            answer = "I'm not certain about that."
            gates_passed = False
            response_type = "speech"
            confidence = 0.2

        return blank_response(
            answer=answer,
            response_type=response_type,
            gates_passed=gates_passed,
            gate_reason="similarity_recency" if gates_passed else "low_similarity",
            contradiction_detected=contradiction_flag,
            confidence=confidence,
            intent_alignment=best_sim,
            memory_alignment=best_mem.trust,  # logged but not used for ranking
            best_prior_trust=best_mem.trust,
        )
