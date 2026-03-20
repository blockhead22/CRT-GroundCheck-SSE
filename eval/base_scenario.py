"""Core types for the eval harness.

TurnSpec      — instruction for one turn (message + optional ground-truth scorer)
TurnRecord    — everything captured after a turn executes
EvalSystem    — Protocol: any system that can answer a message
BaseScenario  — ABC: generates a sequence of TurnSpecs
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Turn data types
# ---------------------------------------------------------------------------

@dataclass
class TurnSpec:
    """One turn in the scenario script.

    Attributes
    ----------
    message:
        The user message sent to the system.
    ground_truth:
        Optional canonical answer string (used for string-match scoring).
    score_fn:
        Optional callable ``(response: str) -> Optional[bool]``.
        Returns True (thumbs-up), False (thumbs-down), or None (skip).
        Takes priority over ground_truth if both are provided.
    slot_key:
        Semantic slot name (e.g. "project_deadline") — used by
        CorrectionRecovery to match which slot is being corrected.
    inject_feedback:
        If True, the runner records simulated feedback after the turn.
    metadata:
        Free-form dict for scenario-specific bookkeeping.
    """
    message: str
    ground_truth: Optional[str] = None
    score_fn: Optional[Callable[[str], Optional[bool]]] = None
    slot_key: Optional[str] = None
    inject_feedback: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def score(self, response: str) -> Optional[bool]:
        """Compute simulated thumbs signal from a response string."""
        if self.score_fn is not None:
            return self.score_fn(response)
        if self.ground_truth is not None:
            return self.ground_truth.lower() in response.lower()
        return None


@dataclass
class TurnRecord:
    """Everything captured for one executed turn.

    This is the unit of data consumed by all metric functions.
    """
    # Provenance
    turn_idx: int
    scenario_name: str
    system_name: str
    seed: int

    # Input
    user_message: str
    slot_key: Optional[str]

    # CRT response fields
    response: str
    response_type: str           # 'belief' | 'speech'
    gates_passed: bool
    gate_reason: str
    contradiction_detected: bool
    confidence: float
    intent_alignment: float
    memory_alignment: float
    best_prior_trust: Optional[float]

    # Simulated feedback
    thumbs_up: Optional[bool]    # None = no feedback on this turn

    # Timing
    wall_time_s: float = 0.0

    # Extra — scenario metadata carried through
    turn_metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# EvalSystem Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class EvalSystem(Protocol):
    """Any system under evaluation must satisfy this Protocol.

    The ``name`` attribute is used in reports and metric tables.
    ``query`` mirrors the CRTEnhancedRAG.query() return contract.
    ``reset`` clears all state for the next seed.
    """

    name: str

    def query(
        self,
        message: str,
        thread_id: str = "eval",
    ) -> Dict[str, Any]:
        """Process one turn; return a CRT-compatible response dict.

        Required keys: answer, response_type, gates_passed, gate_reason,
        contradiction_detected, confidence, intent_alignment,
        memory_alignment, best_prior_trust.
        """
        ...

    def reset(self) -> None:
        """Discard all state (called between seeds)."""
        ...


def _blank_response(answer: str = "", **overrides) -> Dict[str, Any]:
    """Return a minimal valid EvalSystem response dict."""
    base = {
        "answer": answer,
        "response_type": "speech",
        "gates_passed": False,
        "gate_reason": "not_implemented",
        "contradiction_detected": False,
        "confidence": 0.0,
        "intent_alignment": 0.0,
        "memory_alignment": 0.0,
        "best_prior_trust": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# BaseScenario ABC
# ---------------------------------------------------------------------------

class BaseScenario(ABC):
    """Abstract scenario.

    Subclasses implement ``generate_turns`` to yield a sequence of
    ``TurnSpec`` objects.  The runner iterates over them and passes each
    message to the system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in tables and file names."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-sentence description for the report."""
        ...

    @abstractmethod
    def generate_turns(self, n_turns: int, seed: int) -> Iterator[TurnSpec]:
        """Yield exactly ``n_turns`` TurnSpec objects.

        The scenario may use ``seed`` for reproducible randomness.
        """
        ...

    def on_turn_complete(self, record: TurnRecord) -> None:
        """Optional hook called after each turn completes."""
        pass
