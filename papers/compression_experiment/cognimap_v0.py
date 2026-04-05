"""CogniMap v0 — Trust-Weighted Non-Uniform Compression Experiment

Tests whether retrieval quality survives when memories are compressed
at different precision levels based on trust scores:
  - High trust (0.8+): full precision (384 dims, float32)
  - Medium trust (0.4-0.8): half precision (float16) + PCA to 192 dims
  - Low trust (<0.4): quarter precision (uint8 quantized) + PCA to 96 dims

The CogniMap is the mapping: memory_id → {compression_level, codebook, fold_record}

Success criteria:
  1. Top-5 retrieval recall: same memories retrieved as full-precision baseline
  2. Trust ordering preserved: rank order within results unchanged
  3. Compression ratio: significant storage reduction without criteria 1-2 failing

Run: .venv/Scripts/python papers/compression_experiment/cognimap_v0.py
"""

import sys
import json
import sqlite3
import time
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# -- Load memories ------------------------------------------------------

DB_PATH = Path(__file__).resolve().parents[2] / "personal_agent" / "crt_memory_shared.db"

def load_memories():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT memory_id, text, trust, vector_json, kind, confidence
        FROM memories
        WHERE deprecated=0 AND vector_json IS NOT NULL
    """).fetchall()
    db.close()

    memories = []
    for r in rows:
        vec = np.array(json.loads(r["vector_json"]), dtype=np.float32)
        memories.append({
            "id": r["memory_id"],
            "text": r["text"][:200],
            "trust": float(r["trust"] or 0),
            "kind": r["kind"] or "unknown",
            "vector": vec,
        })
    return memories

# -- Compression functions ----------------------------------------------

def compress_full(vec):
    """Full precision — no compression. 384 x float32 = 1536 bytes."""
    return vec.astype(np.float32)

def compress_half(vec):
    """Half precision — float16. 384 x float16 = 768 bytes."""
    return vec.astype(np.float16)

def compress_pca_half(vec, pca_model):
    """PCA to 192 dims + float16. 192 x float16 = 384 bytes."""
    reduced = pca_model.transform(vec.reshape(1, -1))[0]
    return reduced.astype(np.float16)

def compress_pca_quarter(vec, pca_model):
    """PCA to 96 dims + uint8 quantization. 96 x uint8 = 96 bytes."""
    reduced = pca_model.transform(vec.reshape(1, -1))[0]
    # Quantize to uint8 (0-255)
    vmin, vmax = reduced.min(), reduced.max()
    if vmax - vmin < 1e-8:
        return np.zeros(len(reduced), dtype=np.uint8), vmin, vmax
    quantized = ((reduced - vmin) / (vmax - vmin) * 255).astype(np.uint8)
    return quantized, vmin, vmax

def decompress_pca_quarter(quantized, vmin, vmax):
    """Dequantize uint8 back to float32."""
    return (quantized.astype(np.float32) / 255.0) * (vmax - vmin) + vmin

def compress_pca_192(vec, pca_model):
    """PCA to 192 dims, keep float32. 192 x float32 = 768 bytes."""
    return pca_model.transform(vec.reshape(1, -1))[0].astype(np.float32)

# -- Similarity search --------------------------------------------------

def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(dot / (na * nb))

def search_topk(query_vec, corpus_vecs, k=5):
    """Return indices of top-k most similar vectors."""
    sims = [cosine_sim(query_vec, v) for v in corpus_vecs]
    ranked = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
    return ranked[:k], [sims[i] for i in ranked[:k]]

# -- GGUF-style mixed quantization --------------------------------------

def trust_to_compression_level(trust):
    """Map trust score to compression level (CogniMap core logic)."""
    if trust >= 0.8:
        return "full"      # Q32 — no compression
    elif trust >= 0.4:
        return "half"      # Q16 — half precision
    else:
        return "quarter"   # Q8+PCA96 — aggressive compression

# -- Main experiment ----------------------------------------------------

def run_experiment():
    print("=" * 70)
    print("CogniMap v0 — Trust-Weighted Non-Uniform Compression Experiment")
    print("=" * 70)

    # Load data
    memories = load_memories()
    print(f"\nLoaded {len(memories)} memories from production DB")

    # Filter to consistent 384-dim vectors only
    memories = [m for m in memories if len(m["vector"]) == 384]
    print(f"After filtering to 384-dim: {len(memories)} memories")

    # Trust distribution
    high = [m for m in memories if m["trust"] >= 0.8]
    mid = [m for m in memories if 0.4 <= m["trust"] < 0.8]
    low = [m for m in memories if m["trust"] < 0.4]
    print(f"Trust distribution: {len(high)} high, {len(mid)} medium, {len(low)} low")

    # Full precision baseline
    all_vecs = np.array([m["vector"] for m in memories])
    print(f"Full precision storage: {all_vecs.nbytes / 1024:.0f} KB ({all_vecs.shape})")

    # Fit PCA models
    print("\nFitting PCA models...")
    pca_192 = PCA(n_components=192).fit(all_vecs)
    pca_96 = PCA(n_components=96).fit(all_vecs)
    print(f"  PCA-192 explained variance: {pca_192.explained_variance_ratio_.sum():.4f}")
    print(f"  PCA-96 explained variance:  {pca_96.explained_variance_ratio_.sum():.4f}")

    # -- Experiment 1: Uniform compression baselines ------------------

    print("\n" + "-" * 70)
    print("EXPERIMENT 1: Uniform Compression Baselines")
    print("-" * 70)

    # Test queries — use 20 random high-trust memories as queries
    np.random.seed(42)
    query_indices = np.random.choice(len(memories), min(30, len(memories)), replace=False)

    configs = [
        ("Full (384 x f32)", lambda m: m["vector"]),
        ("Half (384 x f16)", lambda m: compress_half(m["vector"]).astype(np.float32)),
        ("PCA-192 (f32)", lambda m: compress_pca_192(m["vector"], pca_192)),
        ("PCA-96 (f32)", lambda m: pca_96.transform(m["vector"].reshape(1, -1))[0]),
    ]

    # Baseline: full precision retrieval
    baseline_results = {}
    for qi in query_indices:
        query = memories[qi]["vector"]
        idxs, sims = search_topk(query, [m["vector"] for m in memories], k=5)
        baseline_results[qi] = set(idxs)

    for name, compress_fn in configs:
        # Compress all vectors
        compressed = []
        total_bytes = 0
        for m in memories:
            c = compress_fn(m)
            compressed.append(c)
            total_bytes += c.nbytes

        # Run retrieval
        recall_scores = []
        order_preserved = 0
        for qi in query_indices:
            # Query in same space as corpus
            q_compressed = compress_fn(memories[qi])
            idxs, sims = search_topk(q_compressed, compressed, k=5)
            retrieved = set(idxs)
            baseline = baseline_results[qi]
            recall = len(retrieved & baseline) / len(baseline)
            recall_scores.append(recall)

            # Check trust ordering
            trust_order = [memories[i]["trust"] for i in idxs]
            if trust_order == sorted(trust_order, reverse=True):
                order_preserved += 1

        avg_recall = np.mean(recall_scores)
        compression_ratio = all_vecs.nbytes / total_bytes
        print(f"  {name:25s} | recall@5: {avg_recall:.3f} | order: {order_preserved}/{len(query_indices)} | "
              f"size: {total_bytes/1024:.0f} KB | ratio: {compression_ratio:.1f}x")

    # -- Experiment 2: Trust-weighted non-uniform (CogniMap) ----------

    print("\n" + "-" * 70)
    print("EXPERIMENT 2: Trust-Weighted Non-Uniform Compression (CogniMap)")
    print("-" * 70)

    # Compress each memory based on trust level
    cognimap = {}  # The fold registry
    compressed_vecs = []
    total_bytes_cogni = 0

    for i, m in enumerate(memories):
        level = trust_to_compression_level(m["trust"])

        if level == "full":
            c = compress_full(m["vector"])
            search_vec = c
            cognimap[m["id"]] = {"level": level, "dims": 384, "dtype": "f32"}
        elif level == "half":
            c = compress_half(m["vector"])
            search_vec = c.astype(np.float32)
            cognimap[m["id"]] = {"level": level, "dims": 384, "dtype": "f16"}
        else:
            # Quarter: PCA-96 + uint8
            q, vmin, vmax = compress_pca_quarter(m["vector"], pca_96)
            c = q
            search_vec = decompress_pca_quarter(q, vmin, vmax)
            cognimap[m["id"]] = {
                "level": level, "dims": 96, "dtype": "u8",
                "vmin": float(vmin), "vmax": float(vmax),
            }

        compressed_vecs.append(search_vec)
        total_bytes_cogni += c.nbytes

    # For search, we need all vectors in the same space
    # Problem: PCA-96 vectors are in a different space than full vectors
    # Solution: decompress PCA vectors back to approximate 384-dim for search
    # This is where the CogniMap's fold record matters

    # Reconstruct all to 384-dim for search (using PCA inverse_transform for compressed ones)
    search_corpus_384 = []
    for i, m in enumerate(memories):
        level = trust_to_compression_level(m["trust"])
        if level in ("full", "half"):
            search_corpus_384.append(compressed_vecs[i])
        else:
            # Inverse PCA: 96-dim → approximate 384-dim
            approx_384 = pca_96.inverse_transform(compressed_vecs[i].reshape(1, -1))[0]
            search_corpus_384.append(approx_384.astype(np.float32))

    # Run retrieval with CogniMap compressed corpus
    recall_scores_cogni = []
    order_preserved_cogni = 0
    gap_flips = 0

    for qi in query_indices:
        # Query at full precision (queries are always full)
        query = memories[qi]["vector"]
        idxs, sims = search_topk(query, search_corpus_384, k=5)
        retrieved = set(idxs)
        baseline = baseline_results[qi]
        recall = len(retrieved & baseline) / len(baseline)
        recall_scores_cogni.append(recall)

        # Check trust ordering — THE gap-flip test
        trust_order = [memories[i]["trust"] for i in idxs]
        if trust_order == sorted(trust_order, reverse=True):
            order_preserved_cogni += 1

        # Check for gap-flips: high-trust memory ranked below low-trust in results
        for j in range(len(idxs) - 1):
            if memories[idxs[j]]["trust"] < memories[idxs[j+1]]["trust"] and \
               memories[idxs[j]]["trust"] < 0.4 and memories[idxs[j+1]]["trust"] >= 0.8:
                gap_flips += 1

    avg_recall_cogni = np.mean(recall_scores_cogni)
    compression_ratio_cogni = all_vecs.nbytes / total_bytes_cogni

    print(f"  CogniMap (trust-weighted) | recall@5: {avg_recall_cogni:.3f} | "
          f"order: {order_preserved_cogni}/{len(query_indices)} | "
          f"size: {total_bytes_cogni/1024:.0f} KB | ratio: {compression_ratio_cogni:.1f}x")
    print(f"  Gap-flips detected: {gap_flips}")
    print(f"\n  Compression breakdown:")
    levels = {"full": 0, "half": 0, "quarter": 0}
    for v in cognimap.values():
        levels[v["level"]] += 1
    for level, count in levels.items():
        print(f"    {level:10s}: {count} memories")

    # -- Experiment 3: Per-query analysis ------------------------------

    print("\n" + "-" * 70)
    print("EXPERIMENT 3: Per-Query Recall Analysis")
    print("-" * 70)

    perfect = sum(1 for r in recall_scores_cogni if r == 1.0)
    degraded = sum(1 for r in recall_scores_cogni if 0.6 <= r < 1.0)
    failed = sum(1 for r in recall_scores_cogni if r < 0.6)
    print(f"  Perfect recall (1.0):  {perfect}/{len(query_indices)}")
    print(f"  Degraded (0.6-0.99):   {degraded}/{len(query_indices)}")
    print(f"  Failed (<0.6):         {failed}/{len(query_indices)}")

    # Show worst cases
    worst = sorted(range(len(recall_scores_cogni)), key=lambda i: recall_scores_cogni[i])[:5]
    if any(recall_scores_cogni[w] < 1.0 for w in worst):
        print(f"\n  Worst retrievals:")
        for w in worst:
            qi = query_indices[w]
            print(f"    recall={recall_scores_cogni[w]:.2f} trust={memories[qi]['trust']:.2f} "
                  f"kind={memories[qi]['kind']:15s} text={memories[qi]['text'][:60]}...")

    # -- Summary ------------------------------------------------------

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Full precision:     {all_vecs.nbytes/1024:.0f} KB")
    print(f"  CogniMap compressed: {total_bytes_cogni/1024:.0f} KB")
    print(f"  Compression ratio:   {compression_ratio_cogni:.1f}x")
    print(f"  Recall@5:            {avg_recall_cogni:.3f}")
    print(f"  Gap-flips:           {gap_flips}")
    print(f"  CogniMap entries:    {len(cognimap)}")
    cognimap_size = len(json.dumps(cognimap))
    print(f"  CogniMap registry:   {cognimap_size/1024:.1f} KB")
    print(f"  Total with registry: {(total_bytes_cogni + cognimap_size)/1024:.0f} KB")

    if avg_recall_cogni >= 0.9 and gap_flips == 0:
        print(f"\n  OK PASS: Trust-weighted compression preserves retrieval quality")
    elif avg_recall_cogni >= 0.8:
        print(f"\n  WARN PARTIAL: Some retrieval degradation, investigate worst cases")
    else:
        print(f"\n  FAIL FAIL: Compression too aggressive, retrieval quality degraded")

    return cognimap, compression_ratio_cogni, avg_recall_cogni

if __name__ == "__main__":
    run_experiment()
