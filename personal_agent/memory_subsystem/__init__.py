"""personal_agent.memory_subsystem — unified memory subpackage.

Re-exports public symbols from all memory modules so callers can do:
    from personal_agent.memory_subsystem import MemoryGraph, BeliefLocus, ...

Note: Named memory_subsystem to avoid collision with personal_agent/memory.py
(the legacy MemorySystem module).
"""

from .graph import (
    MemoryType,
    BelnapState,
    EdgeType,
    Disposition,
    MemoryNode,
    ContradictionEdge,
    MemoryGraph,
    CascadeResult,
    BeliefDependencyGraph,
    LiveBDG,
    get_live_bdg,
    build_test_graph,
)

from .compression import (
    lloyd_max_codebook,
    QuantizedMemory,
    MemQuantizer,
    quantize_vector,
    dequantize_vector,
    quantized_inner_product,
    CogniSeed,
    fold_vector,
    unfold_vector,
    compute_volatility,
    compute_volatility_from_item,
    compute_throttle,
    is_protected,
    minimum_tier,
    should_promote,
    should_demote,
    run_compression_pass,
)

from .consolidation import (
    ConsolidationResult,
    run_consolidation_pass,
)

from .splats import (
    BeliefLocus,
    create_locus,
    create_locus_from_type,
    bhattacharyya_distance,
    bhattacharyya_coefficient,
    overlap_integral,
    kl_divergence,
    cosine_similarity,
    GeometricContradictionResult,
    detect_geometric_contradiction,
    update_locus_confirming,
    update_locus_contradicting,
    update_locus_with_evidence,
    predict_trajectory,
    predict_overlap_trend,
    covariance_velocity,
    # Backward-compat aliases
    MemorySplat,
    create_splat,
    create_splat_from_type,
    update_splat_confirming,
    update_splat_contradicting,
    update_splat_with_evidence,
)

from .bridge import (
    find_groundcheck_db,
    sync_groundcheck_to_memory,
)

__all__ = [
    # graph
    "MemoryType",
    "BelnapState",
    "EdgeType",
    "Disposition",
    "MemoryNode",
    "ContradictionEdge",
    "MemoryGraph",
    "CascadeResult",
    "BeliefDependencyGraph",
    "LiveBDG",
    "get_live_bdg",
    "build_test_graph",
    # compression
    "lloyd_max_codebook",
    "QuantizedMemory",
    "MemQuantizer",
    "quantize_vector",
    "dequantize_vector",
    "quantized_inner_product",
    "CogniSeed",
    "fold_vector",
    "unfold_vector",
    "compute_volatility",
    "compute_volatility_from_item",
    "compute_throttle",
    "is_protected",
    "minimum_tier",
    "should_promote",
    "should_demote",
    "run_compression_pass",
    # consolidation
    "ConsolidationResult",
    "run_consolidation_pass",
    # splats
    "BeliefLocus",
    "create_locus",
    "create_locus_from_type",
    "bhattacharyya_distance",
    "bhattacharyya_coefficient",
    "overlap_integral",
    "kl_divergence",
    "cosine_similarity",
    "GeometricContradictionResult",
    "detect_geometric_contradiction",
    "update_locus_confirming",
    "update_locus_contradicting",
    "update_locus_with_evidence",
    "predict_trajectory",
    "predict_overlap_trend",
    "covariance_velocity",
    "MemorySplat",
    "create_splat",
    "create_splat_from_type",
    "update_splat_confirming",
    "update_splat_contradicting",
    "update_splat_with_evidence",
    # bridge
    "find_groundcheck_db",
    "sync_groundcheck_to_memory",
]
