"""Step 4: Benchmark uniform TurboQuant at 2/3/4/8-bit with and without QJL.

Same metrics as Step 2 for direct comparison.
"""

import json
import sys
import time

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, ".")
from compression_lab.turboquant_memory import MemoryQuantizer

VEC_PATH = "compression_lab/vectors_real.npy"
GT_PATH = "compression_lab/step1_ground_truth.json"
OUT_PATH = "compression_lab/step4_turboquant_uniform.json"

BIT_LEVELS = [2, 3, 4, 8]
N_IP_PAIRS = 500


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cosine_sim_matrix_from_ip(vectors, compressed_db, quantizer):
    """Build similarity matrix using corrected inner products."""
    N = len(vectors)
    sim = np.zeros((N, N), dtype=np.float32)
    for i in range(N):
        for j in range(i, N):
            ip = quantizer.inner_product(vectors[i], compressed_db[j])
            # For unit vectors, inner product = cosine similarity
            sim[i, j] = ip
            sim[j, i] = ip
    return sim


def topk_from_ip_matrix(sim_matrix, query_idxs, k):
    results = []
    for qi in query_idxs:
        sims = sim_matrix[qi].copy()
        sims[qi] = -np.inf
        topk = np.argsort(sims)[::-1][:k]
        results.append(set(topk.tolist()))
    return results


def topk_recall(predicted_sets, ground_truth_lists):
    recalls = []
    for pred, gt in zip(predicted_sets, ground_truth_lists):
        gt_set = set(gt)
        if len(gt_set) == 0:
            continue
        recalls.append(len(pred & gt_set) / len(gt_set))
    return float(np.mean(recalls))


def main():
    print("=" * 60)
    print("STEP 4: TURBOQUANT UNIFORM BENCHMARK")
    print("=" * 60)

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

    for bits in BIT_LEVELS:
        for use_qjl in [False, True]:
            config_name = f"{bits}bit_{'qjl' if use_qjl else 'noqjl'}"
            label = f"{bits}-bit {'+ QJL' if use_qjl else '(no QJL)'}"
            print(f"\n  --- {label} ---")

            mq = MemoryQuantizer(dim=384, bits=bits, use_qjl=use_qjl, seed=42)

            # Compress all vectors
            t0 = time.time()
            compressed_db = [mq.compress(v) for v in vectors]
            compress_time = time.time() - t0
            print(f"  Compressed {N} vectors in {compress_time:.3f}s")

            # Decompress and measure cosine similarity
            cos_sims = []
            for i in range(N):
                recon = mq.decompress(compressed_db[i])
                cos_sims.append(cosine_sim(vectors[i], recon))
            cos_sims = np.array(cos_sims)
            print(f"  Cosine sim (recon): mean={cos_sims.mean():.6f} "
                  f"std={cos_sims.std():.6f} min={cos_sims.min():.6f} "
                  f"p5={np.percentile(cos_sims, 5):.6f} p95={np.percentile(cos_sims, 95):.6f}")

            # Inner product correlation using corrected IP
            orig_dots = []
            est_dots = []
            for i, j in ip_pairs:
                orig_dots.append(float(np.dot(vectors[i], vectors[j])))
                est_dots.append(mq.inner_product(vectors[i], compressed_db[j]))
            orig_dots = np.array(orig_dots)
            est_dots = np.array(est_dots)

            pearson_r = float(np.corrcoef(orig_dots, est_dots)[0, 1])
            sp_rho = float(spearmanr(orig_dots, est_dots).correlation)
            ip_mae = float(np.mean(np.abs(orig_dots - est_dots)))
            print(f"  IP correlation: Pearson r={pearson_r:.6f}, Spearman rho={sp_rho:.6f}, MAE={ip_mae:.6f}")

            # Top-k retrieval using corrected inner products
            # This is O(N^2) but N=556 so manageable
            print(f"  Computing {N}x{N} IP matrix for top-k...")
            t0 = time.time()
            ip_matrix = cosine_sim_matrix_from_ip(vectors, compressed_db, mq)
            print(f"  Done in {time.time()-t0:.1f}s")

            pred_top5 = topk_from_ip_matrix(ip_matrix, query_idxs, 5)
            pred_top10 = topk_from_ip_matrix(ip_matrix, query_idxs, 10)
            recall_5 = topk_recall(pred_top5, gt_top5)
            recall_10 = topk_recall(pred_top10, gt_top10)
            print(f"  Top-5 recall: {recall_5:.4f} ({recall_5*100:.1f}%)")
            print(f"  Top-10 recall: {recall_10:.4f} ({recall_10*100:.1f}%)")

            storage = compressed_db[0].storage_bytes
            print(f"  Storage: {storage} bytes/vector")

            results[config_name] = {
                "bits": bits,
                "use_qjl": use_qjl,
                "bytes_per_vector": storage,
                "cosine_sim": {
                    "mean": float(cos_sims.mean()),
                    "std": float(cos_sims.std()),
                    "min": float(cos_sims.min()),
                    "p5": float(np.percentile(cos_sims, 5)),
                    "p95": float(np.percentile(cos_sims, 95)),
                },
                "inner_product_correlation": {
                    "pearson_r": pearson_r,
                    "spearman_rho": sp_rho,
                    "mae": ip_mae,
                },
                "topk_recall": {
                    "top5": recall_5,
                    "top10": recall_10,
                },
                "compress_time_sec": compress_time,
            }

    # Summary table
    print(f"\n{'='*70}")
    print("SUMMARY: TURBOQUANT UNIFORM")
    print(f"{'='*70}")
    print(f"{'Config':<22} {'Bytes':>6} {'CosSim':>8} {'IP r':>7} {'IP rho':>7} {'Top-5':>7} {'Top-10':>7}")
    print(f"{'-'*70}")
    for bits in BIT_LEVELS:
        for use_qjl in [False, True]:
            k = f"{bits}bit_{'qjl' if use_qjl else 'noqjl'}"
            r = results[k]
            qjl_str = "+QJL" if use_qjl else "    "
            print(f"{bits}-bit {qjl_str:<16} "
                  f"{r['bytes_per_vector']:>6} "
                  f"{r['cosine_sim']['mean']:>8.4f} "
                  f"{r['inner_product_correlation']['pearson_r']:>7.4f} "
                  f"{r['inner_product_correlation']['spearman_rho']:>7.4f} "
                  f"{r['topk_recall']['top5']*100:>6.1f}% "
                  f"{r['topk_recall']['top10']*100:>6.1f}%")

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {OUT_PATH}")
    print(f"\n{'='*60}")
    print("STEP 4 COMPLETE.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
