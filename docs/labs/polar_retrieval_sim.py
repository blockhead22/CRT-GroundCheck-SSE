"""
Polar-Space Memory Retrieval Simulation
========================================
Standalone experiment — zero imports from personal_agent.
Tests whether polar-decomposed retrieval (angle × magnitude) outperforms
plain cosine similarity + trust reranking.

Two modes:
  --synthetic   Generate fake memories with controlled trust/topic structure (default)
  --db PATH     Load real memories from a crt_memory.db file

Usage:
  python docs/labs/polar_retrieval_sim.py
  python docs/labs/polar_retrieval_sim.py --db personal_agent/crt_memory.db
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Memory:
    id: str
    text: str
    vector: np.ndarray          # raw embedding (384-d for MiniLM)
    trust: float                # 0..1
    confidence: float           # 0..1
    timestamp: float = 0.0
    is_contradiction_anchor: bool = False  # known contradiction flag

@dataclass
class Contradiction:
    """A known contradiction pair from the ledger."""
    id: str
    mem_a_id: str
    mem_b_id: str
    is_real: bool               # True = genuine conflict, False = noise/low-trust

@dataclass
class Query:
    text: str
    vector: np.ndarray
    expected_top_ids: list       # memory IDs that should rank highest
    label: str = ""


# ---------------------------------------------------------------------------
# Polar decomposition
# ---------------------------------------------------------------------------

def polar_decompose(vector: np.ndarray) -> tuple[np.ndarray, float]:
    """Decompose vector into (unit direction, magnitude)."""
    mag = np.linalg.norm(vector)
    if mag < 1e-12:
        return vector, 0.0
    return vector / mag, float(mag)


def encode_magnitude(trust: float, confidence: float, recency: float = 1.0,
                     formula: str = "trust") -> float:
    """
    Encode epistemic weight as magnitude.

    Formulas:
      trust:       magnitude = trust
      trust_conf:  magnitude = trust * confidence
      composite:   magnitude = trust * confidence * recency_decay
    """
    if formula == "trust":
        return max(trust, 0.01)  # floor to avoid zero-magnitude
    elif formula == "trust_conf":
        return max(trust * confidence, 0.01)
    elif formula == "composite":
        return max(trust * confidence * recency, 0.01)
    else:
        raise ValueError(f"Unknown formula: {formula}")


def to_polar_space(memory: Memory, formula: str = "trust") -> tuple[np.ndarray, float]:
    """Transform a memory embedding into polar space."""
    direction, _original_mag = polar_decompose(memory.vector)
    magnitude = encode_magnitude(memory.trust, memory.confidence, formula=formula)
    return direction, magnitude


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Standard cosine similarity."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def polar_similarity(query_dir: np.ndarray, mem_dir: np.ndarray,
                     mem_magnitude: float,
                     alpha: float = 0.5) -> float:
    """
    Similarity in polar space.

    score = angular_sim * (1 - alpha + alpha * magnitude)

    alpha=0 -> pure angular (equivalent to cosine)
    alpha=1 -> magnitude fully weights the result
    alpha=0.5 -> balanced
    """
    ang_sim = cosine_similarity(query_dir, mem_dir)
    # Magnitude boost: scale [0,1] magnitude into a weight
    weight = (1.0 - alpha) + alpha * mem_magnitude
    return ang_sim * weight


# ---------------------------------------------------------------------------
# Retrieval engines
# ---------------------------------------------------------------------------

def retrieve_cosine(query: Query, memories: list[Memory], top_k: int = 10
                    ) -> list[tuple[str, float]]:
    """Baseline: rank by cosine similarity only."""
    scores = []
    for mem in memories:
        sim = cosine_similarity(query.vector, mem.vector)
        scores.append((mem.id, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def retrieve_cosine_rerank(query: Query, memories: list[Memory],
                           top_k: int = 10, rerank_weight: float = 0.3
                           ) -> list[tuple[str, float]]:
    """Current CRT approach: cosine retrieve then trust-rerank."""
    scores = []
    for mem in memories:
        sim = cosine_similarity(query.vector, mem.vector)
        # Rerank: blend similarity with trust
        reranked = (1 - rerank_weight) * sim + rerank_weight * mem.trust
        scores.append((mem.id, reranked))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def retrieve_polar(query: Query, memories: list[Memory],
                   top_k: int = 10, alpha: float = 0.5,
                   formula: str = "trust"
                   ) -> list[tuple[str, float]]:
    """Polar space retrieval: angular similarity × magnitude weight."""
    query_dir, _ = polar_decompose(query.vector)
    scores = []
    for mem in memories:
        mem_dir, mem_mag = to_polar_space(mem, formula=formula)
        sim = polar_similarity(query_dir, mem_dir, mem_mag, alpha=alpha)
        scores.append((mem.id, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def detect_contradictions_cosine(memories: list[Memory],
                                 sim_threshold: float = 0.7
                                 ) -> list[tuple[str, str, float]]:
    """Baseline: flag pairs with high cosine similarity as potential contradictions."""
    flagged = []
    for i, a in enumerate(memories):
        for j, b in enumerate(memories):
            if j <= i:
                continue
            sim = cosine_similarity(a.vector, b.vector)
            if sim > sim_threshold:
                flagged.append((a.id, b.id, sim))
    return flagged


def detect_contradictions_polar(memories: list[Memory],
                                sim_threshold: float = 0.7,
                                magnitude_threshold: float = 0.4,
                                formula: str = "trust"
                                ) -> list[tuple[str, str, float, float, float]]:
    """
    Polar contradiction detection: flag only when both memories have high
    magnitude (trust) AND high angular similarity.

    Returns: (id_a, id_b, angular_sim, mag_a, mag_b)
    """
    flagged = []
    for i, a in enumerate(memories):
        dir_a, mag_a = to_polar_space(a, formula=formula)
        for j, b in enumerate(memories):
            if j <= i:
                continue
            dir_b, mag_b = to_polar_space(b, formula=formula)
            ang_sim = cosine_similarity(dir_a, dir_b)
            if (ang_sim > sim_threshold
                    and mag_a > magnitude_threshold
                    and mag_b > magnitude_threshold):
                flagged.append((a.id, b.id, ang_sim, mag_a, mag_b))
    return flagged


# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------

def generate_synthetic_data(
    n_memories: int = 100,
    n_topics: int = 5,
    embedding_dim: int = 384,
    seed: int = 42,
) -> tuple[list[Memory], list[Contradiction], list[Query]]:
    """
    Generate synthetic memories with controlled structure:
    - n_topics clusters in embedding space
    - Trust varies within each cluster (some high, some low)
    - Known contradictions: pairs within same topic with opposing trust levels
    - Noise contradictions: high-sim pairs where one side is low-trust
    """
    rng = np.random.default_rng(seed)

    # Generate topic centroids
    centroids = []
    for _ in range(n_topics):
        c = rng.standard_normal(embedding_dim)
        c = c / np.linalg.norm(c)
        centroids.append(c)

    memories = []
    contradictions = []
    topic_labels = [
        "weather_preferences", "work_schedule", "food_likes",
        "travel_history", "tech_opinions",
    ]

    for topic_idx in range(n_topics):
        centroid = centroids[topic_idx]
        per_topic = n_memories // n_topics

        for j in range(per_topic):
            # Add noise to centroid for within-topic variation
            noise = rng.standard_normal(embedding_dim) * 0.15
            vec = centroid + noise
            vec = vec / np.linalg.norm(vec)

            # Trust distribution: mostly mid-high, some low
            if j < 3:
                trust = rng.uniform(0.05, 0.25)   # low-trust noise
            elif j < 6:
                trust = rng.uniform(0.80, 0.98)   # high-trust anchors
            else:
                trust = rng.uniform(0.35, 0.75)   # mid-range

            confidence = rng.uniform(0.5, 1.0)
            mem_id = f"mem_{topic_labels[topic_idx]}_{j:03d}"

            memories.append(Memory(
                id=mem_id,
                text=f"{topic_labels[topic_idx]} item {j}",
                vector=vec,
                trust=trust,
                confidence=confidence,
                timestamp=float(1000 + topic_idx * 100 + j),
                is_contradiction_anchor=(j in [3, 4]),  # anchors
            ))

        # Create known contradiction pairs within this topic:
        # Real contradiction: both high-trust anchors (indices 3, 4)
        real_a = f"mem_{topic_labels[topic_idx]}_003"
        real_b = f"mem_{topic_labels[topic_idx]}_004"
        contradictions.append(Contradiction(
            id=f"contra_real_{topic_idx}",
            mem_a_id=real_a,
            mem_b_id=real_b,
            is_real=True,
        ))
        # Noise contradiction: one high-trust, one low-trust (indices 0, 3)
        noise_a = f"mem_{topic_labels[topic_idx]}_000"
        noise_b = f"mem_{topic_labels[topic_idx]}_003"
        contradictions.append(Contradiction(
            id=f"contra_noise_{topic_idx}",
            mem_a_id=noise_a,
            mem_b_id=noise_b,
            is_real=False,  # should NOT be flagged as real conflict
        ))

    # Generate queries (one per topic, targeting high-trust anchors)
    queries = []
    for topic_idx in range(n_topics):
        centroid = centroids[topic_idx]
        noise = rng.standard_normal(embedding_dim) * 0.05
        qvec = centroid + noise
        qvec = qvec / np.linalg.norm(qvec)

        # Expected: high-trust memories in this topic should rank first
        expected = [
            f"mem_{topic_labels[topic_idx]}_{j:03d}"
            for j in [3, 4, 5]  # the high-trust anchors
        ]

        queries.append(Query(
            text=f"query about {topic_labels[topic_idx]}",
            vector=qvec,
            expected_top_ids=expected,
            label=topic_labels[topic_idx],
        ))

    return memories, contradictions, queries


# ---------------------------------------------------------------------------
# Load real data from DB
# ---------------------------------------------------------------------------

def load_from_db(db_path: str) -> tuple[list[Memory], list[Contradiction], list[Query]]:
    """Load memories from a real crt_memory.db."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT memory_id, text, vector_json, trust, confidence, timestamp
        FROM memories
        WHERE deprecated = 0
          AND vector_json IS NOT NULL
          AND LENGTH(vector_json) > 10
    """)

    memories = []
    for row in cursor.fetchall():
        try:
            vec = np.array(json.loads(row["vector_json"]), dtype=np.float32)
            if vec.shape[0] < 10:  # skip degenerate vectors
                continue
        except (json.JSONDecodeError, ValueError):
            continue

        memories.append(Memory(
            id=row["memory_id"],
            text=row["text"],
            vector=vec,
            trust=row["trust"],
            confidence=row["confidence"],
            timestamp=row["timestamp"],
        ))

    conn.close()

    if not memories:
        print(f"ERROR: No valid memories with embeddings found in {db_path}")
        sys.exit(1)

    print(f"Loaded {len(memories)} memories from {db_path}")

    # Try loading contradictions from ledger
    ledger_path = str(Path(db_path).parent / "crt_ledger.db")
    contradictions = []
    if Path(ledger_path).exists():
        lconn = sqlite3.connect(ledger_path)
        lconn.row_factory = sqlite3.Row
        lcursor = lconn.cursor()
        try:
            lcursor.execute("""
                SELECT ledger_id, old_memory_id, new_memory_id, status
                FROM contradictions
            """)
            for row in lcursor.fetchall():
                contradictions.append(Contradiction(
                    id=row["ledger_id"],
                    mem_a_id=row["old_memory_id"],
                    mem_b_id=row["new_memory_id"],
                    is_real=(row["status"] in ("open", "resolved")),
                ))
        except Exception:
            pass
        lconn.close()
        print(f"Loaded {len(contradictions)} contradictions from ledger")

    # No predefined queries for real data — generate from random memories
    rng = np.random.default_rng(99)
    sample_size = min(5, len(memories))
    sampled = rng.choice(len(memories), size=sample_size, replace=False)
    queries = []
    for idx in sampled:
        mem = memories[idx]
        noise = rng.standard_normal(mem.vector.shape[0]) * 0.05
        qvec = mem.vector + noise
        qvec = qvec / np.linalg.norm(qvec)
        queries.append(Query(
            text=f"query near '{mem.text[:40]}'",
            vector=qvec,
            expected_top_ids=[mem.id],
            label=mem.id,
        ))

    return memories, contradictions, queries


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------

def mean_reciprocal_rank(ranked_ids: list[str], expected_ids: list[str]) -> float:
    """MRR: 1/rank of first expected hit."""
    for rank, mid in enumerate(ranked_ids, 1):
        if mid in expected_ids:
            return 1.0 / rank
    return 0.0


def precision_at_k(ranked_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """P@k: fraction of top-k that are expected."""
    top_k = ranked_ids[:k]
    hits = sum(1 for mid in top_k if mid in expected_ids)
    return hits / k


def trust_rank_correlation(ranked_ids: list[str], memories_by_id: dict,
                           top_k: int = 10) -> float:
    """
    Do high-trust memories rank higher?
    Returns Spearman-like metric: average trust of top-k vs. average trust overall.
    """
    top_k_ids = ranked_ids[:top_k]
    top_trusts = [memories_by_id[mid].trust for mid in top_k_ids if mid in memories_by_id]
    all_trusts = [m.trust for m in memories_by_id.values()]
    if not top_trusts or not all_trusts:
        return 0.0
    return float(np.mean(top_trusts) - np.mean(all_trusts))


# ---------------------------------------------------------------------------
# Preconditioning (PolarQuant inspired)
# ---------------------------------------------------------------------------

def random_precondition(vectors: np.ndarray, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply random orthogonal preconditioning (PolarQuant §3.1).

    After preconditioning, angle distributions should tighten.
    Returns (preconditioned_vectors, rotation_matrix) so we can apply
    the same rotation to queries.
    """
    rng = np.random.default_rng(seed)
    d = vectors.shape[1]
    # Random orthogonal matrix via QR decomposition
    H = rng.standard_normal((d, d))
    Q, _ = np.linalg.qr(H)
    preconditioned = vectors @ Q
    return preconditioned, Q


def measure_angle_distribution(vectors: np.ndarray, sample_size: int = 500) -> dict:
    """
    Measure angular distribution statistics.
    PolarQuant predicts tight clustering after preconditioning.
    """
    rng = np.random.default_rng(123)
    n = vectors.shape[0]
    if n < 2:
        return {"mean": 0, "std": 0, "min": 0, "max": 0}

    pairs = min(sample_size, n * (n - 1) // 2)
    angles = []
    for _ in range(pairs):
        i, j = rng.choice(n, size=2, replace=False)
        cos_sim = cosine_similarity(vectors[i], vectors[j])
        angle = np.arccos(np.clip(cos_sim, -1, 1))
        angles.append(angle)

    angles = np.array(angles)
    return {
        "mean_deg": float(np.degrees(np.mean(angles))),
        "std_deg": float(np.degrees(np.std(angles))),
        "min_deg": float(np.degrees(np.min(angles))),
        "max_deg": float(np.degrees(np.max(angles))),
    }


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_experiment(memories: list[Memory],
                   contradictions: list[Contradiction],
                   queries: list[Query],
                   alphas: list[float] = None,
                   formulas: list[str] = None):
    """Run the full comparison experiment."""

    if alphas is None:
        alphas = [0.0, 0.25, 0.5, 0.75, 1.0]
    if formulas is None:
        formulas = ["trust", "trust_conf"]

    memories_by_id = {m.id: m for m in memories}
    top_k = min(10, len(memories))

    # ── Phase 1: Retrieval comparison ──────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 1: RETRIEVAL COMPARISON")
    print("=" * 70)

    results = {}

    # Baseline: cosine only
    mrrs, p5s, trust_lifts = [], [], []
    for q in queries:
        ranked = retrieve_cosine(q, memories, top_k)
        ids = [r[0] for r in ranked]
        mrrs.append(mean_reciprocal_rank(ids, q.expected_top_ids))
        p5s.append(precision_at_k(ids, q.expected_top_ids, k=5))
        trust_lifts.append(trust_rank_correlation(ids, memories_by_id, top_k))
    results["cosine"] = {
        "MRR": np.mean(mrrs), "P@5": np.mean(p5s), "trust_lift": np.mean(trust_lifts)
    }

    # Baseline: cosine + trust rerank
    for rw in [0.2, 0.3, 0.5]:
        mrrs, p5s, trust_lifts = [], [], []
        for q in queries:
            ranked = retrieve_cosine_rerank(q, memories, top_k, rerank_weight=rw)
            ids = [r[0] for r in ranked]
            mrrs.append(mean_reciprocal_rank(ids, q.expected_top_ids))
            p5s.append(precision_at_k(ids, q.expected_top_ids, k=5))
            trust_lifts.append(trust_rank_correlation(ids, memories_by_id, top_k))
        results[f"cosine+rerank(w={rw})"] = {
            "MRR": np.mean(mrrs), "P@5": np.mean(p5s), "trust_lift": np.mean(trust_lifts)
        }

    # Polar retrieval: sweep alpha × formula
    for formula in formulas:
        for alpha in alphas:
            mrrs, p5s, trust_lifts = [], [], []
            for q in queries:
                ranked = retrieve_polar(q, memories, top_k, alpha=alpha, formula=formula)
                ids = [r[0] for r in ranked]
                mrrs.append(mean_reciprocal_rank(ids, q.expected_top_ids))
                p5s.append(precision_at_k(ids, q.expected_top_ids, k=5))
                trust_lifts.append(trust_rank_correlation(ids, memories_by_id, top_k))
            results[f"polar(a={alpha}, f={formula})"] = {
                "MRR": np.mean(mrrs), "P@5": np.mean(p5s), "trust_lift": np.mean(trust_lifts)
            }

    # Print results table
    print(f"\n{'Method':<35} {'MRR':>8} {'P@5':>8} {'Trust+':>8}")
    print("-" * 63)
    for method, metrics in results.items():
        print(f"{method:<35} {metrics['MRR']:>8.4f} {metrics['P@5']:>8.4f} {metrics['trust_lift']:>+8.4f}")

    # ── Phase 2: Contradiction detection comparison ────────────────
    print("\n" + "=" * 70)
    print("PHASE 2: CONTRADICTION DETECTION")
    print("=" * 70)

    if contradictions:
        real_pairs = {(c.mem_a_id, c.mem_b_id) for c in contradictions if c.is_real}
        noise_pairs = {(c.mem_a_id, c.mem_b_id) for c in contradictions if not c.is_real}

        for sim_thresh in [0.6, 0.7, 0.8]:
            # Cosine detection
            cos_flags = detect_contradictions_cosine(memories, sim_threshold=sim_thresh)
            cos_pairs = {(a, b) for a, b, _ in cos_flags}
            cos_real_hits = len(real_pairs & cos_pairs)
            cos_noise_hits = len(noise_pairs & cos_pairs)

            # Polar detection
            for mag_thresh in [0.3, 0.5, 0.7]:
                pol_flags = detect_contradictions_polar(
                    memories, sim_threshold=sim_thresh,
                    magnitude_threshold=mag_thresh
                )
                pol_pairs = {(a, b) for a, b, *_ in pol_flags}
                pol_real_hits = len(real_pairs & pol_pairs)
                pol_noise_hits = len(noise_pairs & pol_pairs)

                print(f"  sim>{sim_thresh} | cosine: real={cos_real_hits}/{len(real_pairs)} "
                      f"noise={cos_noise_hits}/{len(noise_pairs)} total={len(cos_flags)}")
                print(f"  sim>{sim_thresh} mag>{mag_thresh} | polar:  real={pol_real_hits}/{len(real_pairs)} "
                      f"noise={pol_noise_hits}/{len(noise_pairs)} total={len(pol_flags)}")
                print()
    else:
        print("  No contradiction data available — skipping")

    # ── Phase 3: Preconditioning analysis ──────────────────────────
    print("=" * 70)
    print("PHASE 3: PRECONDITIONING (PolarQuant)")
    print("=" * 70)

    all_vecs = np.stack([m.vector for m in memories])

    # Raw angle distribution
    raw_dist = measure_angle_distribution(all_vecs)
    print(f"\n  Raw angles:            mean={raw_dist['mean_deg']:.1f}° "
          f"std={raw_dist['std_deg']:.1f}° "
          f"range=[{raw_dist['min_deg']:.1f}°, {raw_dist['max_deg']:.1f}°]")

    # Preconditioned angle distribution
    pre_vecs, Q = random_precondition(all_vecs)
    pre_dist = measure_angle_distribution(pre_vecs)
    print(f"  Preconditioned angles: mean={pre_dist['mean_deg']:.1f}° "
          f"std={pre_dist['std_deg']:.1f}° "
          f"range=[{pre_dist['min_deg']:.1f}°, {pre_dist['max_deg']:.1f}°]")

    # Does preconditioning tighten the distribution?
    tightened = pre_dist["std_deg"] < raw_dist["std_deg"]
    print(f"\n  Distribution tightened: {'YES' if tightened else 'NO'} "
          f"(d_std = {pre_dist['std_deg'] - raw_dist['std_deg']:+.2f}°)")

    # Test retrieval with preconditioned vectors
    print("\n  Retrieval with preconditioned vectors:")
    pre_memories = []
    for i, mem in enumerate(memories):
        pre_memories.append(Memory(
            id=mem.id, text=mem.text,
            vector=pre_vecs[i],
            trust=mem.trust, confidence=mem.confidence,
            timestamp=mem.timestamp,
        ))

    pre_queries = []
    for q in queries:
        pq_vec = q.vector @ Q  # apply same rotation
        pre_queries.append(Query(
            text=q.text, vector=pq_vec,
            expected_top_ids=q.expected_top_ids, label=q.label
        ))

    # Compare best polar config with and without preconditioning
    for label, mems, qs in [("original", memories, queries),
                             ("preconditioned", pre_memories, pre_queries)]:
        mrrs = []
        for q in qs:
            ranked = retrieve_polar(q, mems, top_k, alpha=0.5, formula="trust")
            ids = [r[0] for r in ranked]
            mrrs.append(mean_reciprocal_rank(ids, q.expected_top_ids))
        print(f"    polar(a=0.5) {label:<18} MRR={np.mean(mrrs):.4f}")

    # ── Phase 4: Storage estimation ────────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 4: STORAGE COMPARISON")
    print("=" * 70)

    n_mems = len(memories)
    dim = memories[0].vector.shape[0]
    raw_bytes = n_mems * dim * 4  # float32

    # Polar: angles as float16 + magnitude as float16
    polar_bytes_f16 = n_mems * (dim * 2 + 2)  # float16 angles + float16 magnitude
    # Polar + quantize angles to int8 (PolarQuant style)
    polar_bytes_q8 = n_mems * (dim * 1 + 2)  # int8 angles + float16 magnitude

    print(f"\n  Memories: {n_mems}, Embedding dim: {dim}")
    print(f"  Raw float32:         {raw_bytes:>10,} bytes ({raw_bytes / 1024:.1f} KB)")
    print(f"  Polar float16:       {polar_bytes_f16:>10,} bytes ({polar_bytes_f16 / 1024:.1f} KB) "
          f"— {raw_bytes / polar_bytes_f16:.1f}x compression")
    print(f"  Polar int8 (quant):  {polar_bytes_q8:>10,} bytes ({polar_bytes_q8 / 1024:.1f} KB) "
          f"— {raw_bytes / polar_bytes_q8:.1f}x compression")

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Find best polar config
    best_polar = max(
        [(k, v) for k, v in results.items() if k.startswith("polar")],
        key=lambda x: x[1]["MRR"]
    )
    cosine_mrr = results["cosine"]["MRR"]
    best_rerank = max(
        [(k, v) for k, v in results.items() if "rerank" in k],
        key=lambda x: x[1]["MRR"]
    )

    print(f"\n  Cosine baseline MRR:    {cosine_mrr:.4f}")
    print(f"  Best rerank MRR:        {best_rerank[1]['MRR']:.4f}  ({best_rerank[0]})")
    print(f"  Best polar MRR:         {best_polar[1]['MRR']:.4f}  ({best_polar[0]})")

    delta = best_polar[1]["MRR"] - best_rerank[1]["MRR"]
    if delta > 0.01:
        print(f"\n  -> Polar WINS by {delta:+.4f} MRR — worth integrating")
    elif delta > -0.01:
        print(f"\n  -> Polar ~= rerank (d={delta:+.4f}) — marginal, check trust_lift")
        if best_polar[1]["trust_lift"] > best_rerank[1]["trust_lift"] + 0.02:
            print(f"    But trust_lift is better: {best_polar[1]['trust_lift']:+.4f} "
                  f"vs {best_rerank[1]['trust_lift']:+.4f} — may still be worth it")
    else:
        print(f"\n  -> Rerank WINS by {-delta:+.4f} MRR — polar not justified for retrieval")

    print(f"\n  Compression: {raw_bytes / polar_bytes_q8:.1f}x with int8 polar quantization")
    print(f"  Preconditioning tightened angles: {tightened}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Polar-Space Memory Retrieval Simulation")
    parser.add_argument("--db", type=str, help="Path to crt_memory.db (use real data)")
    parser.add_argument("--synthetic", action="store_true", default=True,
                        help="Use synthetic data (default)")
    parser.add_argument("--n-memories", type=int, default=100,
                        help="Number of synthetic memories")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.db:
        memories, contradictions, queries = load_from_db(args.db)
    else:
        print("Generating synthetic data...")
        memories, contradictions, queries = generate_synthetic_data(
            n_memories=args.n_memories,
            seed=args.seed,
        )
        print(f"  {len(memories)} memories, {len(contradictions)} contradictions, "
              f"{len(queries)} queries")

    run_experiment(memories, contradictions, queries)


if __name__ == "__main__":
    main()
