"""
Sensitivity-Aware Compression Experiment

Tests whether epistemic governance signals (trust, contradiction count,
access frequency, memory kind, stability) can improve retrieval quality
when used to allocate variable bit budgets across memories.

Hypothesis: Same total bit budget, smarter allocation -> better retrieval
for the queries that matter (personal facts, contested beliefs).

Inspired by FKeras (Weng et al., ACM JATS 2024) which uses Hessian
sensitivity to rank neural network weight bits for selective protection.
This experiment applies the same principle to episodic memory embeddings,
using CRT governance signals instead of gradient information.
"""

import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from personal_agent.memory_compression import quantize_vector, dequantize_vector


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MemoryRecord:
    """A memory with its epistemic signals."""
    memory_id: str
    text: str
    vector: np.ndarray          # full 384D
    trust: float
    confidence: float
    kind: str
    source: str
    authority: str
    contradiction_count: int
    stable_cycles: int
    access_count: int
    timestamp: float
    sensitivity: float = 0.0    # computed
    assigned_bits: int = 3      # default


@dataclass
class StrategyResult:
    """Benchmark result for one allocation strategy."""
    name: str
    total_bytes: int
    mean_cosine_error: float
    top10_recall: float
    top10_recall_user_facts: float   # recall specifically for user_fact queries
    rank_correlation: float
    bit_distribution: Dict[int, int]  # {bits: count}


# ---------------------------------------------------------------------------
# Sensitivity scoring
# ---------------------------------------------------------------------------

# Kind weights: how important is this category of memory?
KIND_WEIGHT = {
    "identity_constant": 1.0,
    "user_fact": 0.8,
    "preference": 0.7,
    "narrative_note": 0.6,
    "hypothesis": 0.4,
    "observation": 0.3,
    "ops": 0.2,
    "self_model": 0.1,
}

# Sensitivity formula weights
W_CONTRADICTION = 0.30   # contested memories need protection
W_TRUST = 0.25           # high-trust = high value
W_ACCESS = 0.15          # frequently retrieved = important
W_KIND = 0.20            # structural importance by category
W_STABILITY = 0.10       # penalty for stable (compressible) memories


def compute_sensitivity(m: MemoryRecord) -> float:
    """Compute epistemic sensitivity score for a memory.

    Higher = more sensitive = deserves more bits.
    Range: approximately [0, 1].
    """
    # Contradiction density: how often has this been challenged per retrieval?
    contradiction_density = m.contradiction_count / max(m.access_count, 1)
    contradiction_signal = min(1.0, contradiction_density * 2)  # cap at 1.0

    # Trust signal: high trust = valuable
    trust_signal = m.trust

    # Access frequency: normalize to [0, 1] range (will be normalized globally later)
    access_signal = min(1.0, m.access_count / 20.0)  # 20+ accesses = max

    # Kind weight
    kind_signal = KIND_WEIGHT.get(m.kind, 0.3)

    # Stability penalty: stable memories can tolerate compression
    stability_signal = min(1.0, m.stable_cycles / 50.0)  # 50+ cycles = fully stable

    sensitivity = (
        W_CONTRADICTION * contradiction_signal
        + W_TRUST * trust_signal
        + W_ACCESS * access_signal
        + W_KIND * kind_signal
        - W_STABILITY * stability_signal
    )

    return max(0.0, min(1.0, sensitivity))


# ---------------------------------------------------------------------------
# Allocation strategies
# ---------------------------------------------------------------------------

def strategy_uniform(memories: List[MemoryRecord], bits: int = 3) -> List[MemoryRecord]:
    """Strategy A: Uniform bit allocation (current production)."""
    for m in memories:
        m.assigned_bits = bits
    return memories


def strategy_sensitivity_ranked(memories: List[MemoryRecord]) -> List[MemoryRecord]:
    """Strategy B: Top 20% -> 4-bit, middle 60% -> 3-bit, bottom 20% -> 2-bit."""
    ranked = sorted(memories, key=lambda m: m.sensitivity, reverse=True)
    n = len(ranked)
    cut_high = int(n * 0.20)
    cut_low = int(n * 0.80)

    for i, m in enumerate(ranked):
        if i < cut_high:
            m.assigned_bits = 4
        elif i < cut_low:
            m.assigned_bits = 3
        else:
            m.assigned_bits = 2
    return memories


def strategy_aggressive(memories: List[MemoryRecord]) -> List[MemoryRecord]:
    """Strategy C: Top 10% -> uncompressed, 40% -> 4-bit, 30% -> 3-bit, 20% -> 2-bit."""
    ranked = sorted(memories, key=lambda m: m.sensitivity, reverse=True)
    n = len(ranked)
    cuts = [int(n * 0.10), int(n * 0.50), int(n * 0.80)]

    for i, m in enumerate(ranked):
        if i < cuts[0]:
            m.assigned_bits = 0   # 0 = uncompressed
        elif i < cuts[1]:
            m.assigned_bits = 4
        elif i < cuts[2]:
            m.assigned_bits = 3
        else:
            m.assigned_bits = 2
    return memories


def strategy_kind_based(memories: List[MemoryRecord]) -> List[MemoryRecord]:
    """Strategy D: Allocate bits by memory kind."""
    kind_bits = {
        "identity_constant": 4,
        "user_fact": 4,
        "preference": 3,
        "narrative_note": 3,
        "hypothesis": 3,
        "observation": 2,
        "ops": 2,
        "self_model": 2,
    }
    for m in memories:
        m.assigned_bits = kind_bits.get(m.kind, 3)
    return memories


# ---------------------------------------------------------------------------
# Compression + retrieval benchmark
# ---------------------------------------------------------------------------

BYTES_PER_VECTOR = {
    0: 384 * 4,  # uncompressed float32
    2: 384 // 4 + 8,   # 2-bit: ~104 bytes
    3: 384 * 3 // 8 + 8,  # 3-bit: ~152 bytes
    4: 384 // 2 + 8,   # 4-bit: ~200 bytes
}


def compress_memory(vector: np.ndarray, bits: int) -> Tuple[Optional[np.ndarray], Optional[dict]]:
    """Compress a vector at the specified bit depth."""
    if bits == 0:
        return None, None  # keep uncompressed
    try:
        indices, metadata = quantize_vector(vector, bits)
        return indices, metadata
    except Exception as e:
        print(f"  [WARN] Compression failed at {bits}-bit: {e}")
        return None, None


def reconstruct_memory(
    original: np.ndarray,
    indices: Optional[np.ndarray],
    metadata: Optional[dict],
    bits: int,
) -> np.ndarray:
    """Reconstruct a vector from compressed form."""
    if bits == 0 or indices is None:
        return original
    try:
        return dequantize_vector(indices, metadata)
    except Exception:
        return original


def benchmark_strategy(
    memories: List[MemoryRecord],
    queries: List[np.ndarray],
    query_kinds: List[str],
    ground_truth_top10: List[List[str]],
) -> StrategyResult:
    """Benchmark a strategy against ground truth retrieval."""
    # Compress all memories per their assigned bits
    compressed = {}
    total_bytes = 0
    bit_dist: Dict[int, int] = {}

    for m in memories:
        bits = m.assigned_bits
        bit_dist[bits] = bit_dist.get(bits, 0) + 1
        total_bytes += BYTES_PER_VECTOR.get(bits, 384 * 4)

        if bits == 0:
            compressed[m.memory_id] = m.vector
        else:
            indices, meta = compress_memory(m.vector, bits)
            if indices is not None:
                compressed[m.memory_id] = reconstruct_memory(m.vector, indices, meta, bits)
            else:
                compressed[m.memory_id] = m.vector

    # Retrieve top-10 for each query using compressed vectors
    cosine_errors = []
    recalls = []
    recalls_user_facts = []
    rank_correlations = []

    for qi, query in enumerate(queries):
        q_norm = query / (np.linalg.norm(query) + 1e-8)

        # Score all memories with compressed vectors
        scores = []
        for m in memories:
            c_vec = compressed[m.memory_id]
            c_norm = c_vec / (np.linalg.norm(c_vec) + 1e-8)
            sim = float(np.dot(q_norm, c_norm))
            scores.append((m.memory_id, sim))

        scores.sort(key=lambda x: -x[1])
        predicted_top10 = [mid for mid, _ in scores[:10]]
        gt_top10 = ground_truth_top10[qi]

        # Top-10 recall
        overlap = len(set(predicted_top10) & set(gt_top10))
        recall = overlap / max(len(gt_top10), 1)
        recalls.append(recall)

        if query_kinds[qi] in ("user_fact", "preference", "narrative_note"):
            recalls_user_facts.append(recall)

        # Mean cosine error (compressed vs original for top-10 memories)
        for m in memories:
            c_vec = compressed[m.memory_id]
            orig_sim = float(np.dot(q_norm, m.vector / (np.linalg.norm(m.vector) + 1e-8)))
            comp_sim = float(np.dot(q_norm, c_vec / (np.linalg.norm(c_vec) + 1e-8)))
            cosine_errors.append(abs(orig_sim - comp_sim))

        # Rank correlation (Spearman)
        gt_ranks = {mid: i for i, mid in enumerate(gt_top10)}
        pred_ranks = {mid: i for i, mid in enumerate(predicted_top10)}
        common = set(gt_ranks.keys()) & set(pred_ranks.keys())
        if len(common) >= 3:
            gt_r = [gt_ranks[mid] for mid in common]
            pred_r = [pred_ranks[mid] for mid in common]
            try:
                from scipy.stats import spearmanr
                corr, _ = spearmanr(gt_r, pred_r)
                rank_correlations.append(corr if not np.isnan(corr) else 0.0)
            except ImportError:
                # Fallback: simple rank correlation
                rank_correlations.append(recall)

    strategy_name = ""  # will be set by caller
    return StrategyResult(
        name=strategy_name,
        total_bytes=total_bytes,
        mean_cosine_error=float(np.mean(cosine_errors)) if cosine_errors else 0.0,
        top10_recall=float(np.mean(recalls)) if recalls else 0.0,
        top10_recall_user_facts=float(np.mean(recalls_user_facts)) if recalls_user_facts else 0.0,
        rank_correlation=float(np.mean(rank_correlations)) if rank_correlations else 0.0,
        bit_distribution=bit_dist,
    )


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def load_memories(db_path: str) -> List[MemoryRecord]:
    """Load all active memories with epistemic signals."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT memory_id, text, vector_json, trust, confidence, kind, source,
               authority, contradiction_count, stable_cycles, access_count, timestamp
        FROM memories
        WHERE deprecated = 0 AND vector_json IS NOT NULL
        ORDER BY trust DESC
    """).fetchall()
    conn.close()

    memories = []
    for row in rows:
        mid, text, vj, trust, conf, kind, source, auth, cc, sc, ac, ts = row
        try:
            vec = np.array(json.loads(vj), dtype=np.float32)
            if np.linalg.norm(vec) == 0:
                continue
            memories.append(MemoryRecord(
                memory_id=mid,
                text=text or "",
                vector=vec,
                trust=trust or 0.0,
                confidence=conf or 0.5,
                kind=(kind or "observation").strip().lower(),
                source=(source or "system").strip().lower(),
                authority=(auth or "provisional").strip().lower(),
                contradiction_count=int(cc or 0),
                stable_cycles=int(sc or 0),
                access_count=int(ac or 0),
                timestamp=ts or 0.0,
            ))
        except Exception:
            continue

    return memories


def load_queries(db_path: str, limit: int = 100) -> Tuple[List[np.ndarray], List[str]]:
    """Load query embeddings from belief_speech for benchmarking."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT query_embedding, query FROM belief_speech
        WHERE query_embedding IS NOT NULL
        ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    queries = []
    query_texts = []
    for qe_blob, query_text in rows:
        try:
            vec = np.frombuffer(qe_blob, dtype=np.float32)
            if len(vec) == 384 and np.linalg.norm(vec) > 0:
                queries.append(vec)
                query_texts.append(query_text or "")
        except Exception:
            continue

    return queries, query_texts


def compute_ground_truth(
    memories: List[MemoryRecord],
    queries: List[np.ndarray],
    k: int = 10,
) -> Tuple[List[List[str]], List[str]]:
    """Compute ground truth top-k using full 384D vectors."""
    gt_top_k = []
    query_kinds = []

    for query in queries:
        q_norm = query / (np.linalg.norm(query) + 1e-8)
        scores = []
        for m in memories:
            m_norm = m.vector / (np.linalg.norm(m.vector) + 1e-8)
            sim = float(np.dot(q_norm, m_norm))
            scores.append((m.memory_id, sim, m.kind))
        scores.sort(key=lambda x: -x[1])
        gt_top_k.append([mid for mid, _, _ in scores[:k]])

        # Classify query by what kind of memory it best matches
        top_kind = scores[0][2] if scores else "observation"
        query_kinds.append(top_kind)

    return gt_top_k, query_kinds


def main():
    print("=" * 70)
    print("  SENSITIVITY-AWARE COMPRESSION EXPERIMENT")
    print("  Epistemic signals -> bit budget allocation")
    print("=" * 70)

    db_path = str(PROJECT_ROOT / "personal_agent" / "crt_memory_shared.db")
    if not os.path.exists(db_path):
        print(f"\n  ERROR: Memory DB not found: {db_path}")
        sys.exit(1)

    # 1. Load memories
    print("\n  Loading memories...")
    memories = load_memories(db_path)
    print(f"  Loaded {len(memories)} active memories")

    if len(memories) < 20:
        print("  ERROR: Not enough memories for meaningful experiment")
        sys.exit(1)

    # 2. Compute sensitivity scores
    print("\n  Computing sensitivity scores...")
    for m in memories:
        m.sensitivity = compute_sensitivity(m)

    # Show sensitivity distribution
    sensitivities = [m.sensitivity for m in memories]
    print(f"  Sensitivity: min={min(sensitivities):.3f}, max={max(sensitivities):.3f}, "
          f"mean={np.mean(sensitivities):.3f}, std={np.std(sensitivities):.3f}")

    # Show top-10 most sensitive
    ranked = sorted(memories, key=lambda m: m.sensitivity, reverse=True)
    print(f"\n  Top 10 most sensitive memories:")
    for m in ranked[:10]:
        print(f"    S={m.sensitivity:.3f} trust={m.trust:.2f} cc={m.contradiction_count} "
              f"ac={m.access_count} kind={m.kind:20s} | {m.text[:60]}")

    print(f"\n  Bottom 5 least sensitive:")
    for m in ranked[-5:]:
        print(f"    S={m.sensitivity:.3f} trust={m.trust:.2f} cc={m.contradiction_count} "
              f"ac={m.access_count} kind={m.kind:20s} | {m.text[:60]}")

    # 3. Load queries
    print("\n  Loading query embeddings from belief_speech...")
    queries, query_texts = load_queries(db_path, limit=100)

    if len(queries) < 5:
        print(f"  Only {len(queries)} queries available. Generating synthetic queries...")
        # Use memory vectors as synthetic queries
        rng = np.random.RandomState(42)
        sample_indices = rng.choice(len(memories), size=min(50, len(memories)), replace=False)
        queries = [memories[i].vector + rng.randn(384).astype(np.float32) * 0.1 for i in sample_indices]
        query_texts = [memories[i].text[:50] for i in sample_indices]

    print(f"  Using {len(queries)} queries for benchmark")

    # 4. Compute ground truth
    print("\n  Computing ground truth (full 384D retrieval)...")
    gt_top10, query_kinds = compute_ground_truth(memories, queries)

    # 5. Run strategies
    print("\n  Running allocation strategies...")
    strategies = [
        ("A: Uniform 3-bit", strategy_uniform, {"bits": 3}),
        ("B: Sensitivity-ranked (20/60/20)", strategy_sensitivity_ranked, {}),
        ("C: Aggressive (10/40/30/20)", strategy_aggressive, {}),
        ("D: Kind-based", strategy_kind_based, {}),
        ("E: Uniform 2-bit (lower bound)", strategy_uniform, {"bits": 2}),
        ("F: Uniform 4-bit (upper bound)", strategy_uniform, {"bits": 4}),
    ]

    results: List[StrategyResult] = []

    for name, strategy_fn, kwargs in strategies:
        # Reset assignments
        for m in memories:
            m.assigned_bits = 3

        # Apply strategy
        strategy_fn(memories, **kwargs)

        # Benchmark
        result = benchmark_strategy(memories, queries, query_kinds, gt_top10)
        result.name = name
        results.append(result)
        print(f"    {name}: recall={result.top10_recall:.3f}, "
              f"user_fact_recall={result.top10_recall_user_facts:.3f}, "
              f"bytes={result.total_bytes:,}")

    # 6. Results table
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(f"\n  {'Strategy':<40s} {'Recall':>8s} {'UF Recall':>10s} {'Cosine Err':>11s} {'Bytes':>10s} {'Bits':>20s}")
    print(f"  {'-'*40} {'-'*8} {'-'*10} {'-'*11} {'-'*10} {'-'*20}")

    baseline_bytes = results[0].total_bytes

    for r in results:
        savings = (1.0 - r.total_bytes / baseline_bytes) * 100 if baseline_bytes > 0 else 0
        bits_str = ", ".join(f"{b}b:{c}" for b, c in sorted(r.bit_distribution.items()))
        print(f"  {r.name:<40s} {r.top10_recall:>8.3f} {r.top10_recall_user_facts:>10.3f} "
              f"{r.mean_cosine_error:>11.6f} {r.total_bytes:>10,} {bits_str:>20s}")

    # 7. Analysis
    print("\n" + "=" * 70)
    print("  ANALYSIS")
    print("=" * 70)

    baseline = results[0]  # Strategy A
    for r in results[1:]:
        delta_recall = r.top10_recall - baseline.top10_recall
        delta_uf = r.top10_recall_user_facts - baseline.top10_recall_user_facts
        delta_bytes = r.total_bytes - baseline.total_bytes
        byte_pct = (delta_bytes / baseline.total_bytes * 100) if baseline.total_bytes > 0 else 0

        print(f"\n  {r.name} vs baseline:")
        print(f"    Recall:           {delta_recall:+.3f} ({'better' if delta_recall > 0 else 'worse' if delta_recall < 0 else 'same'})")
        print(f"    User-fact recall: {delta_uf:+.3f} ({'better' if delta_uf > 0 else 'worse' if delta_uf < 0 else 'same'})")
        print(f"    Storage:          {byte_pct:+.1f}% ({delta_bytes:+,} bytes)")

    # 8. Kind distribution
    print(f"\n  Memory kind distribution:")
    kind_counts: Dict[str, int] = {}
    for m in memories:
        kind_counts[m.kind] = kind_counts.get(m.kind, 0) + 1
    for kind, count in sorted(kind_counts.items(), key=lambda x: -x[1]):
        print(f"    {kind:25s}: {count:4d} ({count/len(memories)*100:.1f}%)")

    # 9. Save results
    output = {
        "timestamp": time.time(),
        "num_memories": len(memories),
        "num_queries": len(queries),
        "sensitivity_stats": {
            "min": float(min(sensitivities)),
            "max": float(max(sensitivities)),
            "mean": float(np.mean(sensitivities)),
            "std": float(np.std(sensitivities)),
        },
        "strategies": [
            {
                "name": r.name,
                "total_bytes": r.total_bytes,
                "top10_recall": r.top10_recall,
                "top10_recall_user_facts": r.top10_recall_user_facts,
                "mean_cosine_error": r.mean_cosine_error,
                "rank_correlation": r.rank_correlation,
                "bit_distribution": r.bit_distribution,
            }
            for r in results
        ],
        "kind_distribution": kind_counts,
    }

    output_path = Path(__file__).parent / "sensitivity_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
