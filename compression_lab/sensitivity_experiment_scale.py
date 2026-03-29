"""
Sensitivity-Aware Compression @ Scale

Same experiment as sensitivity_experiment.py but using 5,000 GPT corpus
vectors instead of 556 CRT memories. At this scale, compression quality
differences should be visible.

We simulate epistemic signals by assigning synthetic sensitivity scores
based on vector properties (variance, norm, cluster membership) since
GPT responses don't have CRT governance signals. This tests whether
the ALLOCATION STRATEGY works independently of signal source.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from personal_agent.memory_compression import quantize_vector, dequantize_vector


def compute_bytes(bits: int, dim: int = 384) -> int:
    if bits == 0:
        return dim * 4  # float32
    return dim * bits // 8 + 8  # quantized + metadata overhead


def run_experiment():
    print("=" * 70)
    print("  SENSITIVITY-AWARE COMPRESSION @ SCALE (5K vectors)")
    print("=" * 70)

    # Load vectors
    vec_path = Path(__file__).parent / "vectors_gpt_5k.npy"
    if not vec_path.exists():
        print("ERROR: Run the embedding step first")
        sys.exit(1)

    vectors = np.load(str(vec_path))
    N, D = vectors.shape
    print(f"\n  Loaded: {N} vectors, {D} dimensions")

    # Load metadata
    meta_path = Path(__file__).parent / "vectors_gpt_5k_meta.json"
    with open(meta_path) as f:
        meta = json.load(f)

    # ── Compute synthetic sensitivity scores ──────────────────────
    # Since these are GPT responses (no CRT governance), we simulate
    # sensitivity using vector properties:
    #   - L2 norm variance (unusual vectors = more sensitive)
    #   - Response length (longer = more detailed = more important)
    #   - Model recency (newer models = more relevant)

    norms = np.linalg.norm(vectors, axis=1)
    norm_z = (norms - norms.mean()) / (norms.std() + 1e-8)

    lengths = np.array([m.get("length", 100) for m in meta], dtype=np.float32)
    length_norm = np.clip(lengths / 2000.0, 0, 1)  # normalize

    timestamps = np.array([m.get("timestamp", 0) for m in meta], dtype=np.float64)
    ts_min, ts_max = timestamps.min(), timestamps.max()
    recency = (timestamps - ts_min) / (ts_max - ts_min + 1e-8)

    # Sensitivity = weighted combination
    sensitivity = (
        0.3 * np.abs(norm_z).clip(0, 1)   # unusual norm = sensitive
        + 0.4 * length_norm                 # longer = more important
        + 0.3 * recency                     # newer = more relevant
    )
    sensitivity = sensitivity.clip(0, 1)

    print(f"  Sensitivity: min={sensitivity.min():.3f}, max={sensitivity.max():.3f}, "
          f"mean={sensitivity.mean():.3f}, std={sensitivity.std():.3f}")

    # ── Define strategies ─────────────────────────────────────────

    def assign_uniform(bits: int) -> np.ndarray:
        return np.full(N, bits, dtype=np.int32)

    def assign_sensitivity_ranked() -> np.ndarray:
        """Top 20% -> 4-bit, middle 60% -> 3-bit, bottom 20% -> 2-bit"""
        order = np.argsort(-sensitivity)
        bits = np.full(N, 3, dtype=np.int32)
        cut_high = int(N * 0.20)
        cut_low = int(N * 0.80)
        bits[order[:cut_high]] = 4
        bits[order[cut_low:]] = 2
        return bits

    def assign_aggressive() -> np.ndarray:
        """Top 10% -> uncompressed, 40% -> 4-bit, 30% -> 3-bit, 20% -> 2-bit"""
        order = np.argsort(-sensitivity)
        bits = np.full(N, 3, dtype=np.int32)
        c1, c2, c3 = int(N * 0.10), int(N * 0.50), int(N * 0.80)
        bits[order[:c1]] = 0   # uncompressed
        bits[order[c1:c2]] = 4
        bits[order[c3:]] = 2
        return bits

    def assign_budget_matched() -> np.ndarray:
        """Same total bytes as uniform 3-bit, but redistributed by sensitivity."""
        target_bytes = N * compute_bytes(3)
        order = np.argsort(-sensitivity)
        bits = np.full(N, 2, dtype=np.int32)  # start at 2-bit for all

        # Upgrade from top until budget exhausted
        current_bytes = N * compute_bytes(2)
        upgrade_cost_2to3 = compute_bytes(3) - compute_bytes(2)
        upgrade_cost_3to4 = compute_bytes(4) - compute_bytes(3)

        for idx in order:
            if current_bytes >= target_bytes:
                break
            if bits[idx] == 2:
                bits[idx] = 3
                current_bytes += upgrade_cost_2to3
            elif bits[idx] == 3 and current_bytes + upgrade_cost_3to4 <= target_bytes:
                bits[idx] = 4
                current_bytes += upgrade_cost_3to4

        return bits

    strategies = {
        "A: Uniform 2-bit": assign_uniform(2),
        "B: Uniform 3-bit (baseline)": assign_uniform(3),
        "C: Uniform 4-bit": assign_uniform(4),
        "D: Sensitivity-ranked (20/60/20)": assign_sensitivity_ranked(),
        "E: Aggressive (10/40/30/20)": assign_aggressive(),
        "F: Budget-matched (same bytes as 3-bit)": assign_budget_matched(),
    }

    # ── Compress all vectors per strategy ─────────────────────────
    print("\n  Compressing vectors per strategy...")

    compressed_vecs: Dict[str, np.ndarray] = {}

    for name, bit_assignments in strategies.items():
        t0 = time.time()
        reconstructed = np.zeros_like(vectors)

        for i in range(N):
            b = int(bit_assignments[i])
            if b == 0:
                reconstructed[i] = vectors[i]
            else:
                try:
                    indices, meta_q = quantize_vector(vectors[i], b)
                    reconstructed[i] = dequantize_vector(indices, meta_q)
                except Exception:
                    reconstructed[i] = vectors[i]

        elapsed = time.time() - t0
        compressed_vecs[name] = reconstructed

        total_bytes = sum(compute_bytes(int(b)) for b in bit_assignments)
        bit_dist = {}
        for b in bit_assignments:
            bit_dist[int(b)] = bit_dist.get(int(b), 0) + 1

        print(f"    {name}: {elapsed:.1f}s, {total_bytes:,} bytes, bits={bit_dist}")

    # ── Benchmark retrieval ───────────────────────────────────────
    print("\n  Benchmarking retrieval quality...")

    # Use a random subset as queries
    rng = np.random.RandomState(123)
    query_indices = rng.choice(N, size=min(500, N), replace=False)

    # Normalize all vectors
    def normalize(v):
        n = np.linalg.norm(v, axis=1, keepdims=True)
        return v / (n + 1e-8)

    queries_norm = normalize(vectors[query_indices])
    K = 10

    # Ground truth: full 384D
    all_norm = normalize(vectors)
    gt_sims = queries_norm @ all_norm.T  # (500, 5000)
    gt_top_k = np.argsort(-gt_sims, axis=1)[:, :K]

    # Per-strategy retrieval
    print(f"\n  {'Strategy':<45s} {'Top-10':>7s} {'Top-10 HiS':>10s} {'Cos Err':>9s} {'Rank Corr':>10s} {'Bytes':>12s}")
    print(f"  {'-'*45} {'-'*7} {'-'*10} {'-'*9} {'-'*10} {'-'*12}")

    results = []
    baseline_bytes = None

    # Identify high-sensitivity queries (top 30% by sensitivity)
    query_sensitivities = sensitivity[query_indices]
    high_sens_mask = query_sensitivities >= np.percentile(query_sensitivities, 70)

    for name, recon in compressed_vecs.items():
        recon_norm = normalize(recon)
        pred_sims = queries_norm @ recon_norm.T
        pred_top_k = np.argsort(-pred_sims, axis=1)[:, :K]

        # Top-K recall
        recalls = []
        recalls_high_sens = []
        for qi in range(len(query_indices)):
            gt_set = set(gt_top_k[qi])
            pred_set = set(pred_top_k[qi])
            recall = len(gt_set & pred_set) / K
            recalls.append(recall)
            if high_sens_mask[qi]:
                recalls_high_sens.append(recall)

        mean_recall = np.mean(recalls)
        mean_recall_hs = np.mean(recalls_high_sens) if recalls_high_sens else 0.0

        # Mean cosine error
        cosine_errors = np.abs(gt_sims - pred_sims).mean()

        # Rank correlation (average Spearman over queries)
        from scipy.stats import spearmanr
        rank_corrs = []
        for qi in range(min(100, len(query_indices))):
            gt_order = np.argsort(-gt_sims[qi])[:50]
            pred_scores = pred_sims[qi][gt_order]
            gt_scores = gt_sims[qi][gt_order]
            corr, _ = spearmanr(gt_scores, pred_scores)
            if not np.isnan(corr):
                rank_corrs.append(corr)
        mean_rank_corr = np.mean(rank_corrs) if rank_corrs else 0.0

        bit_assignments = strategies[name]
        total_bytes = sum(compute_bytes(int(b)) for b in bit_assignments)
        if baseline_bytes is None and "baseline" in name.lower():
            baseline_bytes = total_bytes

        print(f"  {name:<45s} {mean_recall:>7.3f} {mean_recall_hs:>10.3f} {cosine_errors:>9.6f} {mean_rank_corr:>10.4f} {total_bytes:>12,}")

        results.append({
            "name": name,
            "top10_recall": float(mean_recall),
            "top10_recall_high_sensitivity": float(mean_recall_hs),
            "mean_cosine_error": float(cosine_errors),
            "rank_correlation": float(mean_rank_corr),
            "total_bytes": total_bytes,
            "bit_distribution": {str(k): v for k, v in sorted(
                {int(b): int((bit_assignments == b).sum()) for b in np.unique(bit_assignments)}.items()
            )},
        })

    # ── Comparison vs baseline ────────────────────────────────────
    if baseline_bytes:
        print(f"\n  === Comparison vs Uniform 3-bit baseline ===")
        baseline_result = [r for r in results if "baseline" in r["name"].lower()][0]
        for r in results:
            if r == baseline_result:
                continue
            dr = r["top10_recall"] - baseline_result["top10_recall"]
            dhs = r["top10_recall_high_sensitivity"] - baseline_result["top10_recall_high_sensitivity"]
            db = (r["total_bytes"] - baseline_bytes) / baseline_bytes * 100
            print(f"\n  {r['name']}:")
            print(f"    Recall:      {dr:+.4f} ({'better' if dr > 0 else 'worse' if dr < 0 else 'same'})")
            print(f"    HiSens:      {dhs:+.4f} ({'better' if dhs > 0 else 'worse' if dhs < 0 else 'same'})")
            print(f"    Storage:     {db:+.1f}%")

    # Save
    output = {
        "timestamp": time.time(),
        "num_vectors": N,
        "num_queries": len(query_indices),
        "sensitivity_stats": {
            "min": float(sensitivity.min()),
            "max": float(sensitivity.max()),
            "mean": float(sensitivity.mean()),
        },
        "results": results,
    }
    out_path = Path(__file__).parent / "sensitivity_scale_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    run_experiment()
