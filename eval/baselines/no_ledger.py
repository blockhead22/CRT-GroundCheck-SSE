"""NoLedgerSystem — trust-weighted memory, no contradiction ledger.

Represents CRT minus the contradiction ledger component.
Contradictions update trust directly (old memory trust decreases,
new memory trust starts fresh) but are never recorded, queued for
reflection, or surfaced to the user.

This isolates the ledger's contribution: if CRT outperforms NoLedger,
the ledger's audit trail and reflection loop are demonstrably valuable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eval.baselines._base import blank_response


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Dot product as a crude similarity proxy (vectors already normalised)."""
    return sum(x * y for x, y in zip(a, b))


def _word_vec(text: str, vocab_size: int = 200) -> List[float]:
    """Very cheap bag-of-words pseudo-embedding for similarity."""
    import hashlib
    vec = [0.0] * vocab_size
    words = text.lower().split()
    for w in words:
        idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % vocab_size
        vec[idx] += 1.0
    total = sum(abs(v) for v in vec) or 1.0
    return [v / total for v in vec]


class _MemEntry:
    __slots__ = ("text", "trust", "vec", "idx")
    _counter = 0

    def __init__(self, text: str, trust: float) -> None:
        self.text = text
        self.trust = trust
        self.vec = _word_vec(text)
        _MemEntry._counter += 1
        self.idx = _MemEntry._counter


class NoLedgerSystem:
    name = "NoLedger"

    def __init__(self, trust_decay: float = 0.15) -> None:
        self._memories: List[_MemEntry] = []
        self._trust_decay = trust_decay  # how much trust drops on contradiction

    def reset(self) -> None:
        self._memories = []

    def _find_similar(self, text: str, threshold: float = 0.4) -> Optional[_MemEntry]:
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
            similar = self._find_similar(message, threshold=0.35)
            if similar:
                # Contradiction: decay old trust, add new memory — no ledger entry
                similar.trust = max(0.1, similar.trust - self._trust_decay)
                contradiction_flag = False  # no detection, no ledger
            self._memories.append(_MemEntry(text=message, trust=0.6))

        # Retrieval: trust-weighted
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
            answer = "I'm not confident about that."
            gates_passed = False
            response_type = "speech"
            confidence = 0.2

        return blank_response(
            answer=answer,
            response_type=response_type,
            gates_passed=gates_passed,
            gate_reason="trust_weighted_retrieval" if gates_passed else "low_confidence",
            contradiction_detected=contradiction_flag,
            confidence=confidence,
            intent_alignment=best_score,
            memory_alignment=prior_trust,
            best_prior_trust=prior_trust,
        )
