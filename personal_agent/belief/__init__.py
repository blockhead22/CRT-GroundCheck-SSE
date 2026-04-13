"""personal_agent.belief — belief subsystem package.

Re-exports all public symbols from the five constituent modules so that
``from personal_agent.belief import <name>`` keeps working after the move.
"""

from .synthesis import (
    TrajectoryPoint,
    BeliefTrajectory,
    BeliefCluster,
    SynthesisResult,
    classify_synthesis_query,
    cluster_beliefs,
    build_belief_trajectory,
    find_trajectory_slots,
    detect_unresolved_tensions,
    compute_representativeness,
    synthesize,
)

from .topology import (
    cosine_distance_matrix,
    confidence_weighted_distance,
    uncertainty_augmented_distance,
    TopologicalFeature,
    BeliefTopology,
    compute_topology,
    interpret_topology,
    TopologySnapshot,
    track_topology_evolution,
    detect_restructuring_events,
    simulate_belief_topology,
)

from .speech_engine import (
    BelnapState,
    Belief,
    BeliefStore,
    DisclosureLevel,
    DisclosureRule,
    DEFAULT_POLICY,
    SpeechPolicy,
    DisclosureGap,
    GapAuditLog,
    GAP_MAGNITUDES,
    generate_speech,
    demo_belief_speech_separation,
)

from .compaction import (
    VERBATIM_TRUST_THRESHOLD,
    SUMMARY_TRUST_THRESHOLD,
    DEFAULT_TOKEN_BUDGET,
    MIN_TOKENS_PER_BELIEF,
    PRIORITY_LOCKED,
    PRIORITY_HIGH_TRUST,
    PRIORITY_CONTRADICTION,
    PRIORITY_MEDIUM_TRUST,
    PRIORITY_LOW_TRUST,
    PRIORITY_SESSION_HOT,
    CompactedBelief,
    BeliefSnapshot,
    estimate_tokens,
    compact_context,
    render_belief_snapshot,
    record_compaction_event,
)

from .classifier import (
    BeliefState,
    BeliefClassifier,
    classify_assertion_kind,
    is_user_belief,
    init_belief_classifier,
    get_belief_classifier,
    classify_query,
)

__all__ = [
    # synthesis
    "TrajectoryPoint",
    "BeliefTrajectory",
    "BeliefCluster",
    "SynthesisResult",
    "classify_synthesis_query",
    "cluster_beliefs",
    "build_belief_trajectory",
    "find_trajectory_slots",
    "detect_unresolved_tensions",
    "compute_representativeness",
    "synthesize",
    # topology
    "cosine_distance_matrix",
    "confidence_weighted_distance",
    "uncertainty_augmented_distance",
    "TopologicalFeature",
    "BeliefTopology",
    "compute_topology",
    "interpret_topology",
    "TopologySnapshot",
    "track_topology_evolution",
    "detect_restructuring_events",
    "simulate_belief_topology",
    # speech_engine
    "BelnapState",
    "Belief",
    "BeliefStore",
    "DisclosureLevel",
    "DisclosureRule",
    "DEFAULT_POLICY",
    "SpeechPolicy",
    "DisclosureGap",
    "GapAuditLog",
    "GAP_MAGNITUDES",
    "generate_speech",
    "demo_belief_speech_separation",
    # compaction
    "VERBATIM_TRUST_THRESHOLD",
    "SUMMARY_TRUST_THRESHOLD",
    "DEFAULT_TOKEN_BUDGET",
    "MIN_TOKENS_PER_BELIEF",
    "PRIORITY_LOCKED",
    "PRIORITY_HIGH_TRUST",
    "PRIORITY_CONTRADICTION",
    "PRIORITY_MEDIUM_TRUST",
    "PRIORITY_LOW_TRUST",
    "PRIORITY_SESSION_HOT",
    "CompactedBelief",
    "BeliefSnapshot",
    "estimate_tokens",
    "compact_context",
    "render_belief_snapshot",
    "record_compaction_event",
    # classifier
    "BeliefState",
    "BeliefClassifier",
    "classify_assertion_kind",
    "is_user_belief",
    "init_belief_classifier",
    "get_belief_classifier",
    "classify_query",
]
