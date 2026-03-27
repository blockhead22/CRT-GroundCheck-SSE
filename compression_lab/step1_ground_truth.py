"""Step 1: Load real memory vectors, compute ground truth metrics + volatility distribution.

Uses crt_memory_shared.db (556 real 384D L2-normalized vectors).
Computes V(t) for each memory using the production volatility formula.
"""

import json
import sqlite3
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from personal_agent.memory_compression import fold_vector, unfold_vector, compute_volatility

DB_PATH = "personal_agent/crt_memory_shared.db"
OUT_PATH = "compression_lab/step1_ground_truth.json"
VEC_PATH = "compression_lab/vectors_real.npy"
N_QUERIES = 100
K_VALUES = [5, 10]


def load_memories(db_path: str) -> dict:
    """Load all memories with 384D vectors and governance metadata."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT memory_id, vector_json, trust, confidence,
               compression_tier, contradiction_count, access_count,
               compressed_vector_json, cogni_seed_json
        FROM memories
        WHERE vector_json IS NOT NULL AND LENGTH(vector_json) > 5000
    """).fetchall()
    conn.close()

    memories = []
    for row in rows:
        try:
            vec = np.array(json.loads(row[1]), dtype=np.float32)
            if len(vec) != 384:
                continue
        except Exception:
            continue

        # Parse compressed vector and cogni_seed if they exist
        compressed_vector = None
        cogni_seed_dict = None
        if row[7]:
            try:
                compressed_vector = np.array(json.loads(row[7]), dtype=np.float32)
            except Exception:
                pass
        if row[8]:
            try:
                cogni_seed_dict = json.loads(row[8])
            except Exception:
                pass

        memories.append({
            "memory_id": row[0],
            "vector": vec,
            "trust": float(row[2]) if row[2] is not None else 0.5,
            "confidence": float(row[3]) if row[3] is not None else 0.5,
            "compression_tier": int(row[4]) if row[4] is not None else 2,
            "contradiction_count": int(row[5]) if row[5] is not None else 0,
            "access_count": max(int(row[6]) if row[6] is not None else 1, 1),
            "compressed_vector": compressed_vector,
            "cogni_seed_dict": cogni_seed_dict,
        })
    return memories


def compute_volatility_for_memory(mem: dict) -> float:
    """Compute V(t) using the production formula."""
    from personal_agent.memory_compression import CogniSeed

    cogni_seed = None
    if mem["cogni_seed_dict"]:
        try:
            cogni_seed = CogniSeed.from_dict(mem["cogni_seed_dict"])
        except Exception:
            pass

    return compute_volatility(
        original_vector=mem["vector"],
        compressed_vector=mem["compressed_vector"],
        cogni_seed=cogni_seed,
        contradiction_count=mem["contradiction_count"],
        access_count=mem["access_count"],
    )


def cosine_sim_matrix(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    normed = vecs / norms
    return normed @ normed.T


def topk_retrieval(sim_matrix: np.ndarray, query_idxs: np.ndarray, k: int) -> np.ndarray:
    results = []
    for qi in query_idxs:
        sims = sim_matrix[qi].copy()
        sims[qi] = -np.inf
        topk = np.argsort(sims)[::-1][:k]
        results.append(topk)
    return np.array(results)


def main():
    print("=" * 60)
    print("STEP 1: GROUND TRUTH + VOLATILITY DISTRIBUTION")
    print("=" * 60)

    # Load memories
    print(f"\nLoading memories from {DB_PATH}...")
    t0 = time.time()
    memories = load_memories(DB_PATH)
    N = len(memories)
    print(f"  Loaded {N} memories with 384D vectors in {time.time()-t0:.2f}s")

    # Extract vector matrix
    vectors = np.array([m["vector"] for m in memories])
    np.save(VEC_PATH, vectors)
    print(f"  Saved vectors to {VEC_PATH}")

    # Norm stats
    norms = np.linalg.norm(vectors, axis=1)
    print(f"\n  Norms: mean={norms.mean():.6f} std={norms.std():.6f} "
          f"min={norms.min():.6f} max={norms.max():.6f}")

    # Trust/contradiction/access distributions
    trusts = np.array([m["trust"] for m in memories])
    contradictions = np.array([m["contradiction_count"] for m in memories])
    accesses = np.array([m["access_count"] for m in memories])
    tiers = np.array([m["compression_tier"] for m in memories])

    print(f"\n  Trust:         mean={trusts.mean():.3f} std={trusts.std():.3f} "
          f"min={trusts.min():.3f} max={trusts.max():.3f}")
    print(f"  Contradictions: mean={contradictions.mean():.2f} max={contradictions.max()}")
    print(f"  Access count:   mean={accesses.mean():.1f} max={accesses.max()}")
    print(f"  Tiers:          {dict(zip(*np.unique(tiers, return_counts=True)))}")

    # Compute volatility for each memory
    print(f"\n  Computing V(t) for {N} memories...")
    volatilities = np.array([compute_volatility_for_memory(m) for m in memories])

    # Volatility distribution
    print(f"\n  Volatility V(t): mean={volatilities.mean():.4f} std={volatilities.std():.4f} "
          f"min={volatilities.min():.4f} max={volatilities.max():.4f}")

    # Volatility band histogram
    bands = [
        ("V(t) > 0.6  [volatile -> 8-bit]", volatilities > 0.6),
        ("V(t) 0.3-0.6 [active -> 4-bit]", (volatilities > 0.3) & (volatilities <= 0.6)),
        ("V(t) 0.1-0.3 [stable -> 3-bit]", (volatilities > 0.1) & (volatilities <= 0.3)),
        ("V(t) <= 0.1  [cold -> 2-bit]", volatilities <= 0.1),
    ]
    print(f"\n  Volatility Distribution (bit allocation preview):")
    print(f"  {'Band':<38} {'Count':>6} {'%':>7}")
    print(f"  {'-'*53}")
    for label, mask in bands:
        count = mask.sum()
        pct = 100 * count / N
        bar = "#" * int(pct / 2)
        print(f"  {label:<38} {count:>6} {pct:>6.1f}% {bar}")

    # Full pairwise cosine similarity matrix
    print(f"\n  Computing {N}x{N} cosine similarity matrix...")
    t0 = time.time()
    sim_matrix = cosine_sim_matrix(vectors)
    print(f"  Done in {time.time()-t0:.2f}s")

    mask = ~np.eye(N, dtype=bool)
    off_diag = sim_matrix[mask]
    print(f"  Pairwise cosine: mean={off_diag.mean():.4f} std={off_diag.std():.4f} "
          f"min={off_diag.min():.4f} max={off_diag.max():.4f}")

    # Top-k ground truth
    rng = np.random.default_rng(42)
    query_idxs = rng.choice(N, size=min(N_QUERIES, N), replace=False)

    topk_results = {}
    for k in K_VALUES:
        topk = topk_retrieval(sim_matrix, query_idxs, k)
        topk_results[str(k)] = topk.tolist()
        print(f"  Top-{k} ground truth computed for {len(query_idxs)} queries")

    # Save everything
    results = {
        "n_vectors": N,
        "n_queries": len(query_idxs),
        "query_indices": query_idxs.tolist(),
        "norm_stats": {
            "mean": float(norms.mean()), "std": float(norms.std()),
            "min": float(norms.min()), "max": float(norms.max()),
        },
        "trust_stats": {
            "mean": float(trusts.mean()), "std": float(trusts.std()),
            "min": float(trusts.min()), "max": float(trusts.max()),
        },
        "contradiction_stats": {
            "mean": float(contradictions.mean()), "max": int(contradictions.max()),
            "total": int(contradictions.sum()),
        },
        "access_stats": {
            "mean": float(accesses.mean()), "max": int(accesses.max()),
        },
        "tier_distribution": {str(k): int(v) for k, v in zip(*np.unique(tiers, return_counts=True))},
        "volatility_stats": {
            "mean": float(volatilities.mean()), "std": float(volatilities.std()),
            "min": float(volatilities.min()), "max": float(volatilities.max()),
            "p5": float(np.percentile(volatilities, 5)),
            "p25": float(np.percentile(volatilities, 25)),
            "p50": float(np.percentile(volatilities, 50)),
            "p75": float(np.percentile(volatilities, 75)),
            "p95": float(np.percentile(volatilities, 95)),
        },
        "volatility_bands": {
            "volatile_8bit": int((volatilities > 0.6).sum()),
            "active_4bit": int(((volatilities > 0.3) & (volatilities <= 0.6)).sum()),
            "stable_3bit": int(((volatilities > 0.1) & (volatilities <= 0.3)).sum()),
            "cold_2bit": int((volatilities <= 0.1).sum()),
        },
        "volatility_per_memory": volatilities.tolist(),
        "pairwise_cosine_stats": {
            "mean": float(off_diag.mean()), "std": float(off_diag.std()),
            "min": float(off_diag.min()), "max": float(off_diag.max()),
        },
        "topk_ground_truth": topk_results,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to {OUT_PATH}")
    print(f"\n{'='*60}")
    print("STEP 1 COMPLETE.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
