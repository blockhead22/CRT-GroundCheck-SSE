"""DestructiveUpdateSystem — overwrites beliefs in-place, no history.

Simulates a system that simply replaces its belief when it hears something
new about a slot, with no versioning, no ledger, and no trust tracking.

Key characteristics vs CRT:
  - Slot value is overwritten on each new assertion (no append).
  - No contradiction detection (old value silently discarded).
  - No trust decay — all current values are equally "trusted".
  - Retrieval always returns the current slot value (most recent wins).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from eval.baselines._base import blank_response


# Simple slot extraction: treat the subject of the first clause as a key.
def _extract_slot(message: str) -> Optional[Tuple[str, str]]:
    """Very rough slot extraction from declarative sentences.

    Returns (slot_key, value_phrase) or None if message looks like a question.
    """
    msg = message.strip()
    if msg.endswith("?"):
        return None  # Question — don't assert

    # Pattern: "The/Our X is/are/has Y"
    m = re.match(
        r"(?:the|our|my|we have|we're|we switched to|i'm|i am|i prefer)\s+(.+?)[\s,]+(?:is|are|was|has|have|=)\s+(.+?)\.?$",
        msg, re.IGNORECASE,
    )
    if m:
        slot = re.sub(r"\s+", "_", m.group(1).strip().lower()[:40])
        value = m.group(2).strip()
        return slot, value

    # Fallback: use first 3 words as key, rest as value
    words = msg.split()
    if len(words) >= 4:
        key = "_".join(w.lower() for w in words[:3])
        value = " ".join(words[3:]).rstrip(".")
        return key, value

    return None


class DestructiveUpdateSystem:
    name = "DestructiveUpdate"

    def __init__(self) -> None:
        # slot_key -> current value (destructive overwrite)
        self._slots: Dict[str, str] = {}
        # Full ordered list of messages for fallback retrieval
        self._history: List[str] = []

    def reset(self) -> None:
        self._slots = {}
        self._history = []

    def query(self, message: str, thread_id: str = "eval") -> Dict[str, Any]:
        is_question = message.rstrip().endswith("?")

        if not is_question:
            self._history.append(message)
            extracted = _extract_slot(message)
            if extracted:
                slot_key, value = extracted
                # Destructive overwrite — no contradiction detection
                self._slots[slot_key] = value

        # Retrieve: keyword scan of slot keys
        keywords = set(message.lower().split()) - {
            "the", "a", "an", "is", "are", "was", "what", "who", "how", "when",
            "where", "which", "our", "my", "your", "we", "i", "it", "this",
        }
        best_slot: Optional[str] = None
        best_value: Optional[str] = None
        for slot_key, value in self._slots.items():
            slot_words = set(slot_key.replace("_", " ").split())
            if slot_words & keywords:
                best_slot = slot_key
                best_value = value
                break  # First match wins (most recently written in dict order)

        if best_value:
            answer = best_value
            gates_passed = True
            confidence = 0.75
        elif self._history:
            answer = self._history[-1]
            gates_passed = True
            confidence = 0.3
        else:
            answer = "I don't have information about that."
            gates_passed = False
            confidence = 0.0

        return blank_response(
            answer=answer,
            response_type="belief" if gates_passed else "speech",
            gates_passed=gates_passed,
            gate_reason="slot_match" if best_slot else ("fallback" if self._history else "no_memory"),
            contradiction_detected=False,  # never — we overwrite silently
            confidence=confidence,
            intent_alignment=0.5,
            memory_alignment=0.6 if best_slot else 0.2,
            best_prior_trust=None,
        )
