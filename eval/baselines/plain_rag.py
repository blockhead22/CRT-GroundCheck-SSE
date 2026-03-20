"""PlainRAGSystem — flat list retrieval, no trust, no ledger.

Represents the simplest possible RAG baseline:
  - Stores every asserted statement as a string.
  - Retrieves the most recently stored statement containing any query word.
  - No trust scores, no decay, no contradiction detection.
  - Gate always "passes" if any memory matches (no calibration).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eval.baselines._base import blank_response


class PlainRAGSystem:
    name = "PlainRAG"

    def __init__(self) -> None:
        self._memories: List[str] = []

    def reset(self) -> None:
        self._memories = []

    def query(self, message: str, thread_id: str = "eval") -> Dict[str, Any]:
        # Treat short declarative sentences as assertions
        is_question = message.rstrip().endswith("?")

        if not is_question:
            self._memories.append(message)

        # Retrieve: scan backwards for any memory containing a query word
        keywords = set(message.lower().split()) - {
            "the", "a", "an", "is", "are", "was", "what", "who", "how", "when",
            "where", "which", "our", "my", "your", "we", "i", "it", "this",
        }
        best: Optional[str] = None
        for mem in reversed(self._memories):
            if any(kw in mem.lower() for kw in keywords):
                best = mem
                break

        if best:
            answer = best
            gates_passed = True
            confidence = 0.7
            memory_alignment = 0.7
        elif self._memories:
            answer = self._memories[-1]
            gates_passed = True
            confidence = 0.4
            memory_alignment = 0.3
        else:
            answer = "I don't have information about that."
            gates_passed = False
            confidence = 0.0
            memory_alignment = 0.0

        return blank_response(
            answer=answer,
            response_type="belief" if gates_passed else "speech",
            gates_passed=gates_passed,
            gate_reason="keyword_match" if gates_passed else "no_memory",
            contradiction_detected=False,  # no contradiction detection
            confidence=confidence,
            intent_alignment=0.5,
            memory_alignment=memory_alignment,
            best_prior_trust=None,
        )
