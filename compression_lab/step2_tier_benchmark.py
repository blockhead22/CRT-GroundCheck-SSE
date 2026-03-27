"""Step 2: Benchmark current tier system (fold_vector / unfold_vector) at all tiers.

Measures cosine similarity preservation, inner product correlation,
top-k retrieval accuracy, and storage per vector.
"""

import json
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from personal_agent.memory_compression import fold_vector, unfold_vector

VEC_PATH = "compression_lab/vectors_real.npy"
GT_PATH = "compression_lab/step1_ground_truth.json"
OUT_PATH = "compression_lab/step2_tier_benchmark.json"

TIERS = {0: 10, 1: 64, 2: 384}
N_IP_PAIRS = 500  # random pairs for inner product correlation


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cosine_sim_matrix(vecs):
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    normed = vecs / norms
    return normed @ normed.T


def topk_retrieval(sim_matrix, query_idxs, k):
    results = []
    for qi in query_idxs:
        sims = sim_matrix[qi].copy()
        sims[qi] = -np.inf
        topk = np.argsort(sims)[::-1][:k]
        results.append(set(topk.tolist()))
    return results


def topk_recall(predicted_sets, ground_truth_lists):
    """Compute mean recall: what fraction of true top-k appears in predicted top-k."""
    recalls = []
    for pred, gt in zip(predicted_sets, ground_truth_lists):
        gt_set = set(gt)
        if len(gt_set) == 0:
            continue
        recalls.append(len(pred & gt_set) / len(gt_set))
    return float(np.mean(recalls))


def main():
    print("=" * 60)
    print("STEP 2: TIER SYSTEM BENCHMARK")
    print("=" * 60)

    # Load vectors and ground truth
    vectors = np.load(VEC_PATH)
    N = len(vectors)
    with open(GT_PATH) as f:
        gt = json.load(f)
    query_idxs = np.array(gt["query_indices"])
    gt_top5 = gt["topk_ground_truth"]["5"]
    gt_top10 = gt["topk_ground_truth"]["10"]

    rng = np.random.default_rng(42)
    ip_pairs = [(rng.integers(N), rng.integers(N)) for _ in range(N_IP_PAIRS)]

    results = {}

    for tier, target_dim in TIERS.items():
        tier_name = f"Tier {tier} ({target_dim}D)"
        print(f"\n  --- {tier_name} ---")

        # Compress + reconstruct all vectors
        t0 = time.time()
        compressed = []
        reconstructed = []
        for vec in vectors:
            comp, seed = fold_vector(vec, target_dim)
            compressed.append(comp)
            recon = unfold_vector(comp, seed)
            reconstructed.append(recon)
        elapsed = time.time() - t0
        compressed = np.array(compressed)
        reconstructed = np.array(reconstructed)
        print(f"  Compressed {N} vectors in {elapsed:.3f}s")

        # Per-vector cosine similarity (original vs reconstructed)
        cos_sims = np.array([cosine_sim(vectors[i], reconstructed[i]) for i in range(N)])
        print(f"  Cosine sim (orig vs recon): mean={cos_sims.mean():.6f} "
              f"std={cos_sims.std():.6f} min={cos_sims.min():.6f} "
              f"p5={np.percentile(cos_sims, 5):.6f} p95={np.percentile(cos_sims, 95):.6f}")

        # Inner product correlation: compare dot(q, k) original vs dot(q_recon, k_recon)
        orig_dots = []
        recon_dots = []
        for i, j in ip_pairs:
            orig_dots.append(float(np.dot(vectors[i], vectors[j])))
            recon_dots.append(float(np.dot(reconstructed[i], reconstructed[j])))
        orig_dots = np.array(orig_dots)
        recon_dots = np.array(recon_dots)

        pearson_r = float(np.corrcoef(orig_dots, recon_dots)[0, 1])
        from scipy.stats import spearmanr
        spearman_rho = float(spearmanr(orig_dots, recon_dots).correlation)
        print(f"  Inner product correlation: Pearson r={pearson_r:.6f}, Spearman rho={spearman_rho:.6f}")

        # Top-k retrieval accuracy
        # Build sim matrix from reconstructed vectors
        recon_sim = cosine_sim_matrix(reconstructed)
        pred_top5 = topk_retrieval(recon_sim, query_idxs, 5)
        pred_top10 = topk_retrieval(recon_sim, query_idxs, 10)
        recall_5 = topk_recall(pred_top5, gt_top5)
        recall_10 = topk_recall(pred_top10, gt_top10)
        print(f"  Top-5 recall: {recall_5:.4f} ({recall_5*100:.1f}%)")
        print(f"  Top-10 recall: {recall_10:.4f} ({recall_10*100:.1f}%)")

        # Storage
        bytes_per_vec = target_dim * 4  # float32
        print(f"  Storage: {bytes_per_vec} bytes/vector")

        results[f"tier_{tier}"] = {
            "tier": tier,
            "target_dim": target_dim,
            "bytes_per_vector": bytes_per_vec,
            "cosine_sim": {
                "mean": float(cos_sims.mean()),
                "std": float(cos_sims.std()),
                "min": float(cos_sims.min()),
                "p5": float(np.percentile(cos_sims, 5)),
                "p95": float(np.percentile(cos_sims, 95)),
            },
            "inner_product_correlation": {
                "pearson_r": pearson_r,
                "spearman_rho": spearman_rho,
            },
            "topk_recall": {
                "top5": recall_5,
                "top10": recall_10,
            },
            "compress_time_sec": elapsed,
        }

    # Summary table
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Method':<22} {'Bytes':>6} {'Cos Sim':>8} {'IP r':>7} {'Top-5':>7} {'Top-10':>7}")
    print(f"{'-'*60}")
    for tier, target_dim in TIERS.items():
        r = results[f"tier_{tier}"]
        print(f"Tier {tier} ({target_dim:>3}D fold)    "
              f"{r['bytes_per_vector']:>6} "
              f"{r['cosine_sim']['mean']:>8.4f} "
              f"{r['inner_product_correlation']['pearson_r']:>7.4f} "
              f"{r['topk_recall']['top5']*100:>6.1f}% "
              f"{r['topk_recall']['top10']*100:>6.1f}%")

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {OUT_PATH}")
    print(f"\n{'='*60}")
    print("STEP 2 COMPLETE.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
