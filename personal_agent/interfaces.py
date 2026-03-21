"""Sub-agent Protocol interfaces for CRT/Aether.

These Protocols draw the seam lines between the five logical sub-systems so
they can evolve independently — and eventually live in separate repos —
without requiring inheritance.  No behaviour is changed here; the only
contract is structural (duck-typing via typing.Protocol).

Agents
------
MemoryAgent     — trust-weighted memory store (crt_memory.py)
LedgerAgent     — contradiction ledger (crt_ledger.py)
LearningAgent   — DNNT background learning (dnnt/background_learning.py)
ReflectionAgent — active-learning coordinator (active_learning.py)
ResearchAgent   — web/local research (research_engine.py / researcher.py)

Usage pattern (no wiring yet — import guard prevents circular import):

    from personal_agent.interfaces import MemoryAgent
    def do_something(memory: MemoryAgent) -> None: ...
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Shared lightweight types (avoid importing heavy dataclasses across repos)
# ---------------------------------------------------------------------------

MemoryID = str
LedgerID = str
TrustScore = float  # 0.0 – 1.0


# ---------------------------------------------------------------------------
# 1. MemoryAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class MemoryAgent(Protocol):
    """Trust-weighted, append-only memory store.

    Implementations: CRTMemorySystem (crt_memory.py)
    """

    def store_memory(
        self,
        text: str,
        confidence: float,
        source: Any,
        *,
        thread_id: Optional[str] = None,
        kind: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_marked_important: bool = False,
        contradiction_signal: float = 0.0,
    ) -> Any:
        """Persist a new memory; return the MemoryItem."""
        ...

    def retrieve_memories(
        self,
        query: str,
        k: int = 5,
        *,
        min_trust: float = 0.0,
        exclude_deprecated: bool = True,
        kinds: Optional[Set[str]] = None,
        exclude_kinds: Optional[Set[str]] = None,
        excluded_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[Any, float]]:
        """Return top-k (MemoryItem, score) pairs for query."""
        ...

    def update_trust(
        self,
        memory_id: MemoryID,
        new_trust: TrustScore,
        reason: str,
        drift: Optional[float] = None,
    ) -> None:
        """Adjust trust score for a specific memory."""
        ...

    def deprecate_memory(self, memory_id: MemoryID, reason: str = "") -> None:
        """Soft-delete a memory (sets deprecated=True)."""
        ...

    def is_memory_contested(self, memory_id: MemoryID) -> bool:
        """True if memory has an open contradiction entry."""
        ...

    def count_memories(self, include_deprecated: bool = False) -> int:
        """Total memory count for this store."""
        ...


# ---------------------------------------------------------------------------
# 2. LedgerAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class LedgerAgent(Protocol):
    """Append-only contradiction ledger.

    Implementations: CRTLedger (crt_ledger.py)
    """

    def record_contradiction(
        self,
        old_memory_id: MemoryID,
        new_memory_id: MemoryID,
        drift_mean: float,
        confidence_delta: float,
        *,
        query: Optional[str] = None,
        summary: Optional[str] = None,
        contradiction_type: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Any:
        """Log a new contradiction; return the ContradictionEntry."""
        ...

    def get_open_contradictions(
        self,
        limit: int = 10,
        thread_id: Optional[str] = None,
    ) -> List[Any]:
        """Return unresolved ContradictionEntry objects."""
        ...

    def has_open_contradiction(self, memory_id: MemoryID) -> bool:
        """True if memory_id is a party to any open contradiction."""
        ...

    def resolve_contradiction(
        self,
        ledger_id: LedgerID,
        method: str,
        *,
        merged_memory_id: Optional[MemoryID] = None,
        new_status: str = "resolved",
    ) -> None:
        """Mark a contradiction as resolved with a given method."""
        ...

    def queue_reflection(
        self,
        ledger_id: LedgerID,
        volatility: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enqueue a contradiction for reflection processing."""
        ...

    def get_reflection_queue(
        self, priority: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return pending reflection queue items."""
        ...

    def get_contradiction_stats(
        self, days: int = 7, thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate contradiction metrics for a time window."""
        ...


# ---------------------------------------------------------------------------
# 3. LearningAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class LearningAgent(Protocol):
    """DNNT background fine-tuning loop.

    Implementations: BackgroundLearner (dnnt/background_learning.py)
    """

    def run_once(self) -> Dict[str, Any]:
        """Execute one training cycle; return a stats dict."""
        ...

    def run_forever(self) -> None:
        """Block indefinitely, running cycles on a schedule."""
        ...


# ---------------------------------------------------------------------------
# 4. ReflectionAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class ReflectionAgent(Protocol):
    """Active-learning coordinator: telemetry, feedback, corrections.

    Implementations: ActiveLearningCoordinator (active_learning.py)
    """

    def emit_turn_event(
        self,
        event_type: str,
        *,
        thread_id: Optional[str] = None,
        interaction_id: Optional[str] = None,
        severity: float = 0.0,
        memory_ids: Optional[List[MemoryID]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write a telemetry event to turn_telemetry; never raises."""
        ...

    def record_interaction(
        self,
        thread_id: str,
        query: str,
        response: str,
        response_type: str,
        confidence: float,
        gates_passed: bool,
        *,
        facts_injected: Optional[List[Dict[str, Any]]] = None,
        interaction_id: Optional[str] = None,
    ) -> str:
        """Persist a completed turn; return interaction_id."""
        ...

    def record_feedback_thumbs(
        self,
        interaction_id: str,
        thumbs_up: bool,
        *,
        comment: Optional[str] = None,
        feedback_priority: float = 0.0,
    ) -> bool:
        """Record thumbs-up/down signal; return success bool."""
        ...

    def record_feedback_correction(
        self,
        interaction_id: str,
        correction_type: str,
        *,
        field_name: Optional[str] = None,
        incorrect_value: Optional[str] = None,
        correct_value: Optional[str] = None,
        user_comment: Optional[str] = None,
    ) -> str:
        """Record a structured correction; return correction_id."""
        ...

    def get_recent_corrections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return most recent user corrections across all threads."""
        ...

    def get_interaction_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Aggregate interaction metrics for a rolling window."""
        ...


# ---------------------------------------------------------------------------
# 5. ResearchAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class ResearchAgent(Protocol):
    """Web and local research / evidence gathering.

    Implementations: ResearchEngine (research_engine.py),
                     ResearchAgent (researcher.py),
                     WebSearchTool (web_search.py)
    """

    def research(
        self,
        query: str,
        *,
        max_sources: int = 3,
        search_local: bool = True,
        search_web: bool = False,
    ) -> Any:
        """Run a research pass; return an EvidencePacket or equivalent."""
        ...

    def search_web(
        self, query: str, num_results: int = 5
    ) -> List[Dict[str, str]]:
        """Raw web search; return list of {title, url, snippet} dicts."""
        ...


# ---------------------------------------------------------------------------
# 6. TaskAgent
# ---------------------------------------------------------------------------

@runtime_checkable
class TaskAgent(Protocol):
    """Clean execution route for task/agentic queries.

    Handles URL fetches, instruction execution, and tool use without
    running through the full CRT gating pipeline.  After execution,
    learned facts are written back through the normal CRT memory path.

    Implementations: CRTTaskAgent (task_agent.py)
    """

    def run_stream(
        self,
        message: str,
        thread_id: str,
        intent: Optional[Any] = None,
    ):
        """Execute the task, yielding SSE-compatible event dicts.

        Each yielded dict has at minimum ``{"type": str, "content": str}``.
        Event types emitted: intent_classified, plan_ready, tool_start,
        tool_result, validate_result, status, task_done.
        """
        ...


# ---------------------------------------------------------------------------
# Registry helper (optional — lets runtime code verify conformance)
# ---------------------------------------------------------------------------

def assert_implements(obj: object, protocol: type, label: str = "") -> None:
    """Raise TypeError if obj does not structurally satisfy protocol.

    Call during startup to get early, readable errors before any
    actual cross-agent call is made.

    Example::

        from personal_agent.interfaces import assert_implements, MemoryAgent
        assert_implements(engine.memory, MemoryAgent, "CRTMemorySystem")
    """
    if not isinstance(obj, protocol):
        name = label or type(obj).__name__
        raise TypeError(
            f"{name!r} does not satisfy {protocol.__name__} protocol. "
            f"Missing methods: "
            + str(
                [
                    m
                    for m in protocol.__protocol_attrs__  # type: ignore[attr-defined]
                    if not hasattr(obj, m)
                ]
            )
        )
