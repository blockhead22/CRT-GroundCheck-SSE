"""NoBackgroundLearningSystem — full CRT pipeline, DNNT disabled.

Same as CRTSystem but the DNNT training loop never runs.  Feedback
signals (thumbs-up/down) are recorded but never act on trust via the
learning queue.  This shows the contribution of the background learner
to long-horizon improvement.

Implementation: reuses the NoLedger trust-weighted retrieval logic but
WITH contradiction detection logged (approximating CRT minus DNNT).
The key difference from NoLedgerSystem: contradiction_detected is True
when a conflict is found; it just never gets learned from.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eval.baselines._base import blank_response
from eval.baselines.no_ledger import _word_vec, _cosine_sim, _MemEntry


class NoBackgroundLearningSystem:
    name = "NoBackgroundLearning"

    def __init__(self, trust_decay: float = 0.15) -> None:
        self._memories: List[_MemEntry] = []
        self._trust_decay = trust_decay
        # Feedback buffer — never consumed (DNNT disabled)
        self._feedback_buffer: List[Dict] = []

    def reset(self) -> None:
        self._memories = []
        self._feedback_buffer = []

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

    def record_feedback(self, response: str, thumbs_up: bool) -> None:
        """Record feedback but never process it (DNNT disabled)."""
        self._feedback_buffer.append({"response": response, "thumbs_up": thumbs_up})

    def query(self, message: str, thread_id: str = "eval") -> Dict[str, Any]:
        is_question = message.rstrip().endswith("?")
        contradiction_flag = False

        if not is_question:
            similar = self._find_similar(message)
            if similar:
                # Detected but trust only decays — no feedback loop acts on it
                similar.trust = max(0.1, similar.trust - self._trust_decay)
                contradiction_flag = True
            self._memories.append(_MemEntry(text=message, trust=0.6))

        if not self._memories:
            return blank_response(
                answer="I don't have information about that.",
                gates_passed=False,
                gate_reason="no_memory",
            )

        qvec = _word_vec(message)
        scored: List[Tuple[float, int, _MemEntry]] = []
        for m in self._memories:
            sim = _cosine_sim(qvec, m.vec)
            scored.append((sim * m.trust, m.idx, m))
        scored.sort(reverse=True)

        best_score, _, best_mem = scored[0]
        prior_trust = best_mem.trust

        if best_score >= 0.15:
            answer = best_mem.text
            gates_passed = True
            response_type = "belief"
            confidence = min(0.95, best_score * 1.5)
        else:
            answer = "I'm not certain about that."
            gates_passed = False
            response_type = "speech"
            confidence = 0.2

        return blank_response(
            answer=answer,
            response_type=response_type,
            gates_passed=gates_passed,
            gate_reason="trust_weighted" if gates_passed else "low_confidence",
            contradiction_detected=contradiction_flag,
            confidence=confidence,
            intent_alignment=best_score,
            memory_alignment=prior_trust,
            best_prior_trust=prior_trust,
        )
