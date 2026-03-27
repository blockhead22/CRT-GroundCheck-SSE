"""Belief Topology -- Step 6

Persistent homology on collections of memory splats.

The premise: the topology of your belief space tells you things
that individual memories and pairwise comparisons cannot.

- H0 (connected components): clusters of related beliefs. When components
  merge over time, beliefs are integrating. When they split, beliefs are
  fragmenting.

- H1 (loops/holes): gaps in your belief space. A 1-cycle means there's a
  topic you circle around but never occupy directly. Avoidance patterns.
  Or: beliefs that are connected in a ring without a unifying center.

- Persistence: how "real" a topological feature is. Short-lived features
  are noise. Long-lived features are structural. The persistence diagram
  IS the signature of your belief topology.

Key insight from Step 4: in 384D, use cosine distance between centers
(not Bhattacharyya) for the distance matrix. The covariance information
enters through filtration weighting, not the base metric.

This is the first application of TDA to a single person's belief history.
"""

import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np
from ripser import ripser
from persim import plot_diagrams

from .memory_splats import (
    MemorySplat, create_splat, create_splat_from_type,
    cosine_similarity, bhattacharyya_coefficient,
)


# ---------------------------------------------------------------------------
# Distance matrices for TDA
# ---------------------------------------------------------------------------

def cosine_distance_matrix(splats: List[MemorySplat]) -> np.ndarray:
    """Pairwise cosine distance between splat centers.

    distance = 1 - cosine_similarity. Range [0, 2].
    This is the right metric for 384D -- covariance is too sparse
    for Bhattacharyya to be meaningful statically.
    """
    n = len(splats)
    D = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            cos = cosine_similarity(splats[i], splats[j])
            d = 1.0 - cos
            D[i, j] = d
            D[j, i] = d
    return D


def confidence_weighted_distance(splats: List[MemorySplat]) -> np.ndarray:
    """Cosine distance weighted by inverse confidence.

    Low-confidence memories are "further away" -- they contribute
    less structure. High-confidence memories anchor the topology.

    d_weighted(a, b) = d_cosine(a, b) / (alpha_a * alpha_b)

    Effect: uncertain memories get pushed to the periphery.
    Confident memories form the core skeleton.
    """
    n = len(splats)
    D = cosine_distance_matrix(splats)
    for i in range(n):
        for j in range(i + 1, n):
            weight = splats[i].alpha * splats[j].alpha
            if weight > 1e-8:
                D[i, j] /= weight
                D[j, i] /= weight
            else:
                D[i, j] = 2.0  # max distance
                D[j, i] = 2.0
    return D


def uncertainty_augmented_distance(splats: List[MemorySplat]) -> np.ndarray:
    """Distance that incorporates both center distance and uncertainty overlap.

    d(a, b) = cosine_dist(a, b) * (1 + uncertainty_mismatch(a, b))

    If two beliefs are close but one is very uncertain and the other
    is tight, inflate the distance -- they're not really "the same belief."
    """
    n = len(splats)
    D = cosine_distance_matrix(splats)
    for i in range(n):
        for j in range(i + 1, n):
            # Uncertainty mismatch: ratio of total uncertainties
            ua = splats[i].total_uncertainty
            ub = splats[j].total_uncertainty
            if min(ua, ub) > 1e-8:
                mismatch = max(ua, ub) / min(ua, ub) - 1.0
            else:
                mismatch = 0.0
            # Cap the inflation
            inflation = 1.0 + min(1.0, mismatch * 0.3)
            D[i, j] *= inflation
            D[j, i] *= inflation
    return D


# ---------------------------------------------------------------------------
# Topological features
# ---------------------------------------------------------------------------

@dataclass
class TopologicalFeature:
    """A single topological feature (birth, death) from persistence."""
    dimension: int      # 0 = component, 1 = loop, 2 = void
    birth: float        # filtration value where feature appears
    death: float        # filtration value where feature dies (inf = never)
    persistence: float  # death - birth (longer = more significant)
    generators: Optional[List[int]] = None  # indices of splats involved


@dataclass
class BeliefTopology:
    """Full topological analysis of a belief space."""
    n_memories: int
    features: List[TopologicalFeature]

    # Betti numbers at a chosen filtration threshold
    betti_0: int  # connected components
    betti_1: int  # loops/holes
    betti_2: int  # voids (rare in practice)

    # Persistence statistics
    max_persistence_h0: float  # longest-lived component gap
    max_persistence_h1: float  # longest-lived loop
    total_persistence_h0: float
    total_persistence_h1: float
    n_significant_h0: int  # components with persistence > threshold
    n_significant_h1: int  # loops with persistence > threshold

    # The raw persistence diagrams
    diagrams: list  # ripser output

    # Interpretation
    interpretation: str


def compute_topology(
    splats: List[MemorySplat],
    distance_fn: str = "cosine",
    max_dim: int = 1,
    significance_threshold: float = 0.05,
    betti_filtration: float = 0.35,
) -> BeliefTopology:
    """Compute persistent homology of a collection of memory splats.

    Args:
        splats: the memories to analyze
        distance_fn: "cosine", "confidence_weighted", or "uncertainty_augmented"
        max_dim: max homology dimension (1 = components + loops)
        significance_threshold: persistence below this is noise
        betti_filtration: distance threshold for Betti number computation
    """
    if len(splats) < 3:
        return BeliefTopology(
            n_memories=len(splats), features=[], betti_0=len(splats),
            betti_1=0, betti_2=0, max_persistence_h0=0, max_persistence_h1=0,
            total_persistence_h0=0, total_persistence_h1=0,
            n_significant_h0=0, n_significant_h1=0, diagrams=[],
            interpretation="Too few memories for topology."
        )

    # Compute distance matrix
    if distance_fn == "confidence_weighted":
        D = confidence_weighted_distance(splats)
    elif distance_fn == "uncertainty_augmented":
        D = uncertainty_augmented_distance(splats)
    else:
        D = cosine_distance_matrix(splats)

    # Run ripser
    result = ripser(D, maxdim=max_dim, distance_matrix=True)
    diagrams = result['dgms']

    # Extract features
    features = []
    for dim, dgm in enumerate(diagrams):
        for birth, death in dgm:
            if np.isinf(death):
                persistence = float('inf')
            else:
                persistence = death - birth
            features.append(TopologicalFeature(
                dimension=dim,
                birth=float(birth),
                death=float(death),
                persistence=float(persistence),
            ))

    # Compute Betti numbers at chosen filtration
    betti = [0] * (max_dim + 1)
    for f in features:
        if f.birth <= betti_filtration and (f.death > betti_filtration or np.isinf(f.persistence)):
            betti[f.dimension] += 1

    # Persistence stats
    h0_persist = [f.persistence for f in features
                  if f.dimension == 0 and not np.isinf(f.persistence)]
    h1_persist = [f.persistence for f in features
                  if f.dimension == 1 and not np.isinf(f.persistence)]

    max_p_h0 = max(h0_persist) if h0_persist else 0.0
    max_p_h1 = max(h1_persist) if h1_persist else 0.0
    total_p_h0 = sum(h0_persist)
    total_p_h1 = sum(h1_persist)
    n_sig_h0 = sum(1 for p in h0_persist if p > significance_threshold)
    n_sig_h1 = sum(1 for p in h1_persist if p > significance_threshold)

    # Interpretation
    interp = interpret_topology(
        betti[0], betti[1], betti[2] if len(betti) > 2 else 0,
        n_sig_h0, n_sig_h1, max_p_h0, max_p_h1,
        len(splats),
    )

    return BeliefTopology(
        n_memories=len(splats),
        features=features,
        betti_0=betti[0],
        betti_1=betti[1],
        betti_2=betti[2] if len(betti) > 2 else 0,
        max_persistence_h0=max_p_h0,
        max_persistence_h1=max_p_h1,
        total_persistence_h0=total_p_h0,
        total_persistence_h1=total_p_h1,
        n_significant_h0=n_sig_h0,
        n_significant_h1=n_sig_h1,
        diagrams=diagrams,
        interpretation=interp,
    )


def interpret_topology(
    b0: int, b1: int, b2: int,
    n_sig_h0: int, n_sig_h1: int,
    max_p_h0: float, max_p_h1: float,
    n_total: int,
) -> str:
    """Human-readable interpretation of topological features.

    This is the speculative part -- mapping topology to psychology.
    These interpretations need empirical validation.
    """
    parts = []

    # H0: Connected components
    if b0 == 1:
        parts.append("Beliefs form a single connected cluster (integrated worldview).")
    elif b0 <= 3:
        parts.append(f"Beliefs split into {b0} distinct clusters (compartmentalized thinking).")
    else:
        parts.append(f"Beliefs fragmented into {b0} clusters (highly compartmentalized or diverse interests).")

    if n_sig_h0 > 0 and max_p_h0 > 0.3:
        parts.append(f"Strong cluster separation (max gap persistence={max_p_h0:.2f}) -- "
                     "some belief domains are genuinely isolated from each other.")

    # H1: Loops/holes
    if b1 == 0:
        parts.append("No topological holes detected (beliefs fill their space without gaps).")
    elif b1 <= 2:
        parts.append(f"{b1} hole(s) in belief space -- topic(s) that are circled around "
                     "but not directly addressed.")
    else:
        parts.append(f"{b1} holes in belief space -- multiple avoidance patterns or "
                     "circular reasoning structures.")

    if n_sig_h1 > 0 and max_p_h1 > 0.2:
        parts.append(f"Persistent hole (persistence={max_p_h1:.2f}) -- this is a stable gap, "
                     "not noise. Something is being consistently avoided or left unresolved.")

    # Density assessment
    if n_total > 0:
        components_per_memory = b0 / n_total
        if components_per_memory < 0.1:
            parts.append("High belief density -- memories are well-connected.")
        elif components_per_memory > 0.5:
            parts.append("Low belief density -- many isolated memories.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Temporal topology: track how topology changes over time
# ---------------------------------------------------------------------------

@dataclass
class TopologySnapshot:
    """Topology at a point in time."""
    timestamp: float
    betti_0: int
    betti_1: int
    max_persistence_h0: float
    max_persistence_h1: float
    total_persistence_h1: float
    n_memories: int


def track_topology_evolution(
    splat_timeline: List[Tuple[float, List[MemorySplat]]],
    **kwargs,
) -> List[TopologySnapshot]:
    """Compute topology at each point in a timeline.

    splat_timeline: list of (timestamp, splats_at_that_time)

    Returns snapshots showing how topology evolves.
    Betti number changes = belief restructuring events.
    """
    snapshots = []
    for ts, splats in splat_timeline:
        topo = compute_topology(splats, **kwargs)
        snapshots.append(TopologySnapshot(
            timestamp=ts,
            betti_0=topo.betti_0,
            betti_1=topo.betti_1,
            max_persistence_h0=topo.max_persistence_h0,
            max_persistence_h1=topo.max_persistence_h1,
            total_persistence_h1=topo.total_persistence_h1,
            n_memories=topo.n_memories,
        ))
    return snapshots


def detect_restructuring_events(
    snapshots: List[TopologySnapshot],
) -> List[Dict]:
    """Detect moments where the topology changes significantly.

    A restructuring event is when Betti numbers change --
    components merging/splitting or holes appearing/disappearing.
    """
    events = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]

        db0 = curr.betti_0 - prev.betti_0
        db1 = curr.betti_1 - prev.betti_1

        if db0 != 0 or db1 != 0:
            event = {
                'timestamp': curr.timestamp,
                'step': i,
                'delta_b0': db0,
                'delta_b1': db1,
                'description': [],
            }
            if db0 < 0:
                event['description'].append(
                    f"Beliefs integrating: {abs(db0)} cluster(s) merged")
            elif db0 > 0:
                event['description'].append(
                    f"Beliefs fragmenting: {db0} new cluster(s) emerged")
            if db1 > 0:
                event['description'].append(
                    f"New hole(s) opened: {db1} avoidance pattern(s) appeared")
            elif db1 < 0:
                event['description'].append(
                    f"Hole(s) closed: {abs(db1)} gap(s) filled")

            event['description'] = "; ".join(event['description'])
            events.append(event)

    return events


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_belief_topology():
    """Simulate a belief space evolving over time.

    Scenario:
    - Start with 3 belief clusters (work, relationships, health)
    - Over time, work stress bleeds into relationships
    - A gap appears around "self-worth" (circled but not addressed)
    - Eventually clusters merge as person integrates their experience
    """
    print("=" * 70)
    print("BELIEF TOPOLOGY -- Persistent Homology on Memory Splats")
    print("=" * 70)

    np.random.seed(42)
    d = 384

    # Create three distinct topic directions
    work_dir = np.random.randn(d).astype(np.float32)
    work_dir /= np.linalg.norm(work_dir)

    rel_dir = np.random.randn(d).astype(np.float32)
    rel_dir /= np.linalg.norm(rel_dir)

    health_dir = np.random.randn(d).astype(np.float32)
    health_dir /= np.linalg.norm(health_dir)

    print(f"\n  Topic cosines:")
    print(f"    work-relationships: {float(np.dot(work_dir, rel_dir)):.4f}")
    print(f"    work-health:        {float(np.dot(work_dir, health_dir)):.4f}")
    print(f"    relationships-health:{float(np.dot(rel_dir, health_dir)):.4f}")

    def make_cluster(center, n, spread=0.15):
        splats = []
        for i in range(n):
            noise = np.random.randn(d).astype(np.float32) * spread
            vec = center + noise
            vec /= np.linalg.norm(vec)
            splats.append(create_splat_from_type(
                f"mem_{len(splats)}_{i}", vec,
                f"memory in cluster", "belief", 0.7 + np.random.random() * 0.3
            ))
        return splats

    # --- Phase 1: Three separate clusters ---
    print(f"\n  --- PHASE 1: Three separate belief clusters ---")
    work_mems = make_cluster(work_dir, 8, 0.12)
    rel_mems = make_cluster(rel_dir, 6, 0.12)
    health_mems = make_cluster(health_dir, 5, 0.12)

    all_splats = work_mems + rel_mems + health_mems
    topo1 = compute_topology(all_splats)
    print(f"  Memories: {topo1.n_memories}")
    print(f"  Betti numbers: b0={topo1.betti_0}, b1={topo1.betti_1}")
    print(f"  Max persistence H0: {topo1.max_persistence_h0:.4f}")
    print(f"  Max persistence H1: {topo1.max_persistence_h1:.4f}")
    print(f"  Interpretation: {topo1.interpretation}")

    # --- Phase 2: Work stress bleeds into relationships ---
    print(f"\n  --- PHASE 2: Work stress bleeding into relationships ---")
    # Add memories that bridge work and relationships
    bridge_dir = (work_dir + rel_dir)
    bridge_dir /= np.linalg.norm(bridge_dir)
    bridge_mems = make_cluster(bridge_dir, 4, 0.15)

    all_splats_2 = work_mems + rel_mems + health_mems + bridge_mems
    topo2 = compute_topology(all_splats_2)
    print(f"  Memories: {topo2.n_memories}")
    print(f"  Betti numbers: b0={topo2.betti_0}, b1={topo2.betti_1}")
    print(f"  Max persistence H0: {topo2.max_persistence_h0:.4f}")
    print(f"  Max persistence H1: {topo2.max_persistence_h1:.4f}")
    print(f"  Interpretation: {topo2.interpretation}")

    # --- Phase 3: Add "self-worth" gap (ring of beliefs around a hole) ---
    print(f"\n  --- PHASE 3: Self-worth gap (beliefs circling an empty center) ---")
    # Create a ring of beliefs around a direction without filling the center
    worth_center = np.random.randn(d).astype(np.float32)
    worth_center /= np.linalg.norm(worth_center)

    ring_mems = []
    n_ring = 8
    # Build ring by creating points that are equidistant from center
    # and from each other -- like vertices of a regular polygon in a 2D plane
    # embedded in 384D. Pick two orthogonal directions in the space.
    orth1 = np.random.randn(d).astype(np.float32)
    orth1 -= np.dot(orth1, worth_center) * worth_center
    orth1 /= np.linalg.norm(orth1)
    orth2 = np.random.randn(d).astype(np.float32)
    orth2 -= np.dot(orth2, worth_center) * worth_center
    orth2 -= np.dot(orth2, orth1) * orth1
    orth2 /= np.linalg.norm(orth2)

    ring_radius = 0.5  # controls how far ring points are from center
    for i in range(n_ring):
        angle = 2 * math.pi * i / n_ring
        vec = worth_center + ring_radius * (math.cos(angle) * orth1 +
                                             math.sin(angle) * orth2)
        vec /= np.linalg.norm(vec)
        ring_mems.append(create_splat_from_type(
            f"worth_ring_{i}", vec,
            "self-worth adjacent belief", "belief", 0.5
        ))

    all_splats_3 = all_splats_2 + ring_mems
    topo3 = compute_topology(all_splats_3)
    print(f"  Memories: {topo3.n_memories}")
    print(f"  Betti numbers: b0={topo3.betti_0}, b1={topo3.betti_1}")
    print(f"  Max persistence H0: {topo3.max_persistence_h0:.4f}")
    print(f"  Max persistence H1: {topo3.max_persistence_h1:.4f}")
    print(f"  Significant H1 features: {topo3.n_significant_h1}")
    print(f"  Interpretation: {topo3.interpretation}")

    # --- Temporal evolution ---
    print(f"\n  --- TEMPORAL TOPOLOGY EVOLUTION ---")
    timeline = [
        (1.0, work_mems + rel_mems + health_mems),
        (2.0, work_mems + rel_mems + health_mems + bridge_mems[:1]),
        (3.0, work_mems + rel_mems + health_mems + bridge_mems[:2]),
        (4.0, work_mems + rel_mems + health_mems + bridge_mems[:3]),
        (5.0, all_splats_2),
        (6.0, all_splats_2 + ring_mems[:2]),
        (7.0, all_splats_2 + ring_mems[:4]),
        (8.0, all_splats_3),
    ]

    snapshots = track_topology_evolution(timeline)
    print(f"  {'Step':>4} | {'n_mem':>5} | {'b0':>3} | {'b1':>3} | {'max_p_H0':>9} | {'max_p_H1':>9}")
    print(f"  {'-'*4}-+-{'-'*5}-+-{'-'*3}-+-{'-'*3}-+-{'-'*9}-+-{'-'*9}")
    for i, snap in enumerate(snapshots):
        print(f"  {i:4d} | {snap.n_memories:5d} | {snap.betti_0:3d} | "
              f"{snap.betti_1:3d} | {snap.max_persistence_h0:9.4f} | "
              f"{snap.max_persistence_h1:9.4f}")

    # Detect restructuring events
    events = detect_restructuring_events(snapshots)
    if events:
        print(f"\n  --- RESTRUCTURING EVENTS ---")
        for e in events:
            print(f"  Step {e['step']}: {e['description']}")
    else:
        print(f"\n  No restructuring events detected.")

    # --- Compare distance metrics ---
    print(f"\n  --- DISTANCE METRIC COMPARISON ---")
    for metric_name in ["cosine", "confidence_weighted", "uncertainty_augmented"]:
        topo = compute_topology(all_splats_3, distance_fn=metric_name)
        print(f"  {metric_name:>25}: b0={topo.betti_0} b1={topo.betti_1} "
              f"max_p_H0={topo.max_persistence_h0:.4f} "
              f"max_p_H1={topo.max_persistence_h1:.4f}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"D:\CRT\compression_lab")
    simulate_belief_topology()
    print(f"\n{'='*70}")
    print("BELIEF TOPOLOGY -- COMPLETE")
    print(f"{'='*70}")
