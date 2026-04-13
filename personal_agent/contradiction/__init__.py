"""personal_agent.contradiction -- Contradiction detection, lifecycle, and prediction.

Re-exports public symbols from all submodules for convenient access.
"""

from .lifecycle import (
    ContradictionLifecycleState,
    ContradictionLifecycleEntry,
    ContradictionLifecycle,
    TransparencyLevel,
    MemoryStyle,
    UserTransparencyPrefs,
    DisclosurePolicy,
)

from .trace_logger import (
    ContradictionTraceLogger,
    get_trace_logger,
    configure_trace_logging,
)

from .ml_detector import (
    RETRACTION_PATTERNS,
    SEMANTIC_EQUIVALENTS,
    DETAIL_ENRICHMENT_WORDS,
    TRANSIENT_STATE_WORDS,
    MLContradictionDetector,
)

from .predictive import (
    Urgency,
    TrajectoryState,
    extract_trajectory,
    ConvergenceResult,
    analyze_convergence,
    ConvergenceAlert,
    scan_for_convergence,
    simulate_belief_drift,
    simulate_stable_beliefs,
    simulate_sudden_reversal,
)

__all__ = [
    # lifecycle
    "ContradictionLifecycleState",
    "ContradictionLifecycleEntry",
    "ContradictionLifecycle",
    "TransparencyLevel",
    "MemoryStyle",
    "UserTransparencyPrefs",
    "DisclosurePolicy",
    # trace_logger
    "ContradictionTraceLogger",
    "get_trace_logger",
    "configure_trace_logging",
    # ml_detector
    "RETRACTION_PATTERNS",
    "SEMANTIC_EQUIVALENTS",
    "DETAIL_ENRICHMENT_WORDS",
    "TRANSIENT_STATE_WORDS",
    "MLContradictionDetector",
    # predictive
    "Urgency",
    "TrajectoryState",
    "extract_trajectory",
    "ConvergenceResult",
    "analyze_convergence",
    "ConvergenceAlert",
    "scan_for_convergence",
    "simulate_belief_drift",
    "simulate_stable_beliefs",
    "simulate_sudden_reversal",
]
