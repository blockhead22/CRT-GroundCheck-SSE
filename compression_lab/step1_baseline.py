"""Step 1: Setup and Baseline — load 1000 real memory vectors, compute ground truth metrics."""

import json
import sqlite3
import sys
import time

import numpy as np

DB_PATH = "personal_agent/crt_memory_shared.db"
OUT_PATH = "compression_lab/baseline_metrics.json"
N_SAMPLES = 600  # DB has ~556 valid 384D vectors
N_QUERIES = 100
K_VALUES = [5, 10]


def load_vectors(db_path: str, n: int) -> tuple:
    """Load n random memory vectors from the production DB."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT vector_json FROM memories WHERE vector_json IS NOT NULL AND LENGTH(vector_json) > 5000 ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()

    vectors = []
    for (vj,) in rows:
        v = np.array(json.loads(vj), dtype=np.float32)
        if len(v) == 384:
            vectors.append(v)
    return np.array(vectors)


def cosine_sim_matrix(vecs: np.ndarray) -> np.ndarray:
    """Compute full pairwise cosine similarity matrix."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    normed = vecs / norms
    return normed @ normed.T


def topk_retrieval(sim_matrix: np.ndarray, query_idxs: np.ndarray, k: int) -> np.ndarray:
    """For each query index, return the top-k most similar indices (excluding self)."""
    results = []
    for qi in query_idxs:
        sims = sim_matrix[qi].copy()
        sims[qi] = -np.inf  # exclude self
        topk = np.argsort(sims)[::-1][:k]
        results.append(topk)
    return np.array(results)


def main():
    print(f"Loading {N_SAMPLES} vectors from {DB_PATH}...")
    t0 = time.time()
    vectors = load_vectors(DB_PATH, N_SAMPLES)
    print(f"  Loaded {len(vectors)} valid 384D vectors in {time.time()-t0:.2f}s")

    if len(vectors) < N_SAMPLES:
        print(f"  WARNING: Only {len(vectors)} vectors available (requested {N_SAMPLES})")
    N = len(vectors)

    # Save vectors for reuse in later steps
    np.save("compression_lab/vectors_1000.npy", vectors)
    print(f"  Saved vectors to compression_lab/vectors_1000.npy")

    # Vector norm statistics
    norms = np.linalg.norm(vectors, axis=1)
    print(f"\nVector norms: mean={norms.mean():.4f} std={norms.std():.4f} "
          f"min={norms.min():.4f} max={norms.max():.4f}")

    # Full pairwise cosine similarity matrix
    print(f"\nComputing {N}x{N} cosine similarity matrix...")
    t0 = time.time()
    sim_matrix = cosine_sim_matrix(vectors)
    print(f"  Done in {time.time()-t0:.2f}s")

    # Similarity distribution (off-diagonal)
    mask = ~np.eye(N, dtype=bool)
    off_diag = sim_matrix[mask]
    print(f"  Pairwise cosine sim: mean={off_diag.mean():.4f} std={off_diag.std():.4f} "
          f"min={off_diag.min():.4f} max={off_diag.max():.4f}")

    # Top-k retrieval ground truth
    rng = np.random.default_rng(42)
    query_idxs = rng.choice(N, size=min(N_QUERIES, N), replace=False)

    topk_results = {}
    for k in K_VALUES:
        print(f"\nComputing top-{k} retrieval for {len(query_idxs)} queries...")
        topk = topk_retrieval(sim_matrix, query_idxs, k)
        topk_results[k] = topk.tolist()

    # Save everything
    results = {
        "n_vectors": N,
        "n_queries": len(query_idxs),
        "query_indices": query_idxs.tolist(),
        "norm_stats": {
            "mean": float(norms.mean()),
            "std": float(norms.std()),
            "min": float(norms.min()),
            "max": float(norms.max()),
        },
        "pairwise_cosine_stats": {
            "mean": float(off_diag.mean()),
            "std": float(off_diag.std()),
            "min": float(off_diag.min()),
            "max": float(off_diag.max()),
        },
        "topk_ground_truth": {str(k): v for k, v in topk_results.items()},
    }

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved baseline metrics to {OUT_PATH}")
    print("Step 1 complete.")


if __name__ == "__main__":
    main()
