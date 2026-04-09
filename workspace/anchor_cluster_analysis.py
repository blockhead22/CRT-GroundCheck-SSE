import sqlite3
import json
import numpy as np
from sklearn.decomposition import PCA
from collections import defaultdict
import textwrap
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = r"D:\AI_round2\personal_agent\crt_memory_shared.db"

# -- 1. Load data --
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
    SELECT memory_id, text, trust, access_count, contradiction_count, vector_json, kind, authority
    FROM memories
    WHERE deprecated = 0
      AND temporal_status = 'active'
""")
rows = cur.fetchall()
conn.close()

print(f"Raw rows from DB: {len(rows)}")

# Parse vectors
memories = []
skipped = 0
for mid, text, trust, acc, contra, vec_json, kind, authority in rows:
    if not vec_json:
        skipped += 1
        continue
    try:
        vec = json.loads(vec_json)
        if not vec or len(vec) < 10:
            skipped += 1
            continue
        memories.append({
            "id": mid,
            "text": text,
            "trust": trust,
            "access_count": acc or 0,
            "contradiction_count": contra or 0,
            "vector": np.array(vec, dtype=np.float32),
            "kind": kind,
            "authority": authority,
        })
    except (json.JSONDecodeError, TypeError):
        skipped += 1

print(f"Valid memories with vectors: {len(memories)}")
print(f"Skipped (null/bad vector): {skipped}")

# -- 2. Classify anchors vs non-anchors --
ANCHOR_TRUST = 0.8
ANCHOR_ACCESS = 3

anchors = [m for m in memories if m["trust"] >= ANCHOR_TRUST and m["access_count"] >= ANCHOR_ACCESS]
non_anchors = [m for m in memories if not (m["trust"] >= ANCHOR_TRUST and m["access_count"] >= ANCHOR_ACCESS)]

print(f"\n{'='*70}")
print(f"ANCHOR CLASSIFICATION")
print(f"{'='*70}")
print(f"Anchors (trust >= {ANCHOR_TRUST} AND access >= {ANCHOR_ACCESS}): {len(anchors)}")
print(f"Non-anchors: {len(non_anchors)}")
print(f"Anchor ratio: {len(anchors)/len(memories)*100:.1f}%")

# Trust distribution of anchors
if anchors:
    a_trusts = [a["trust"] for a in anchors]
    a_access = [a["access_count"] for a in anchors]
    print(f"Anchor trust range: [{min(a_trusts):.3f}, {max(a_trusts):.3f}], mean={np.mean(a_trusts):.3f}")
    print(f"Anchor access range: [{min(a_access)}, {max(a_access)}], mean={np.mean(a_access):.1f}")

# -- 3. Cosine similarity helpers --
def cosine_sim(a, b):
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

def cosine_sim_matrix(vecs):
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = vecs / norms
    return normed @ normed.T

# -- 4. Intra-anchor similarity --
print(f"\n{'='*70}")
print(f"INTRA-ANCHOR SIMILARITY (do anchors cluster together?)")
print(f"{'='*70}")

if len(anchors) >= 2:
    anchor_vecs = np.array([a["vector"] for a in anchors])
    sim_matrix = cosine_sim_matrix(anchor_vecs)
    n = len(anchors)
    upper = []
    for i in range(n):
        for j in range(i+1, n):
            upper.append(sim_matrix[i, j])
    upper = np.array(upper)
    print(f"Pairwise similarities among {n} anchors: {len(upper)} pairs")
    print(f"  Mean: {np.mean(upper):.4f}")
    print(f"  Median: {np.median(upper):.4f}")
    print(f"  Std: {np.std(upper):.4f}")
    print(f"  Min: {np.min(upper):.4f}")
    print(f"  Max: {np.max(upper):.4f}")
    print(f"  Pairs with sim > 0.5: {np.sum(upper > 0.5)} ({np.sum(upper > 0.5)/len(upper)*100:.1f}%)")
    print(f"  Pairs with sim > 0.7: {np.sum(upper > 0.7)} ({np.sum(upper > 0.7)/len(upper)*100:.1f}%)")
else:
    print("Not enough anchors for pairwise analysis.")

# -- 5. Random baseline: all-pairs similarity --
print(f"\n{'='*70}")
print(f"RANDOM BASELINE (all-pairs similarity)")
print(f"{'='*70}")

all_vecs = np.array([m["vector"] for m in memories])
np.random.seed(42)
N_SAMPLE = min(5000, len(memories) * (len(memories) - 1) // 2)
rand_sims = []
for _ in range(N_SAMPLE):
    i, j = np.random.choice(len(memories), 2, replace=False)
    rand_sims.append(cosine_sim(all_vecs[i], all_vecs[j]))
rand_sims = np.array(rand_sims)
print(f"Sampled {N_SAMPLE} random pairs")
print(f"  Mean random similarity: {np.mean(rand_sims):.4f}")
print(f"  Median: {np.median(rand_sims):.4f}")
print(f"  Std: {np.std(rand_sims):.4f}")

# -- 6. Non-anchor to nearest anchor --
print(f"\n{'='*70}")
print(f"NON-ANCHOR -> NEAREST ANCHOR (gravitational pull)")
print(f"{'='*70}")

if anchors and non_anchors:
    anchor_vecs = np.array([a["vector"] for a in anchors])
    anchor_norms = np.linalg.norm(anchor_vecs, axis=1, keepdims=True)
    anchor_norms[anchor_norms == 0] = 1.0
    anchor_normed = anchor_vecs / anchor_norms

    nearest_sims = []
    nearest_anchor_idx = []
    for m in non_anchors:
        v = m["vector"]
        norm = np.linalg.norm(v)
        if norm == 0:
            nearest_sims.append(0.0)
            nearest_anchor_idx.append(0)
            continue
        v_normed = v / norm
        sims = anchor_normed @ v_normed
        best_idx = np.argmax(sims)
        nearest_sims.append(float(sims[best_idx]))
        nearest_anchor_idx.append(best_idx)

    nearest_sims = np.array(nearest_sims)
    print(f"  Mean nearest-anchor similarity: {np.mean(nearest_sims):.4f}")
    print(f"  Median: {np.median(nearest_sims):.4f}")
    print(f"  Std: {np.std(nearest_sims):.4f}")
    print(f"  Non-anchors with sim > 0.5 to nearest anchor: {np.sum(nearest_sims > 0.5)} ({np.sum(nearest_sims > 0.5)/len(nearest_sims)*100:.1f}%)")
    print(f"  Non-anchors with sim > 0.7 to nearest anchor: {np.sum(nearest_sims > 0.7)} ({np.sum(nearest_sims > 0.7)/len(nearest_sims)*100:.1f}%)")

    delta = np.mean(nearest_sims) - np.mean(rand_sims)
    print(f"\n  ** Gravitational pull delta: {delta:+.4f} **")
    print(f"     (nearest-anchor mean - random baseline mean)")
    if delta > 0.05:
        print(f"     RESULT: Non-anchors DO cluster toward anchors (delta > 0.05)")
    elif delta > 0.02:
        print(f"     RESULT: Weak gravitational pull detected")
    else:
        print(f"     RESULT: No clear gravitational pull")

# -- 7. Densest anchor clusters --
print(f"\n{'='*70}")
print(f"TOP ANCHOR CLUSTERS (anchors with most non-anchors within cosine > 0.3)")
print(f"{'='*70}")

if anchors and non_anchors:
    SIM_THRESHOLD = 0.3
    anchor_clusters = defaultdict(list)

    for ni, m in enumerate(non_anchors):
        v = m["vector"]
        norm = np.linalg.norm(v)
        if norm == 0:
            continue
        v_normed = v / norm
        sims = anchor_normed @ v_normed
        best_idx = np.argmax(sims)
        if sims[best_idx] >= SIM_THRESHOLD:
            anchor_clusters[best_idx].append((ni, float(sims[best_idx])))

    cluster_sizes = [(aidx, len(members)) for aidx, members in anchor_clusters.items()]
    cluster_sizes.sort(key=lambda x: -x[1])

    for rank, (aidx, size) in enumerate(cluster_sizes[:5]):
        a = anchors[aidx]
        members = anchor_clusters[aidx]
        members.sort(key=lambda x: -x[1])
        avg_sim = np.mean([s for _, s in members])

        print(f"\n--- Cluster #{rank+1}: {size} non-anchors (avg sim={avg_sim:.3f}) ---")
        print(f"  ANCHOR [trust={a['trust']:.3f}, access={a['access_count']}, contra={a['contradiction_count']}]:")
        print(f"    {textwrap.shorten(a['text'], width=120)}")
        print(f"  Top 5 closest non-anchors:")
        for ni, sim in members[:5]:
            nm = non_anchors[ni]
            print(f"    sim={sim:.3f} [trust={nm['trust']:.3f}, access={nm['access_count']}]: {textwrap.shorten(nm['text'], width=100)}")

    captured = sum(len(v) for v in anchor_clusters.values())
    print(f"\n  Total non-anchors within sim>0.3 of ANY anchor: {captured}/{len(non_anchors)} ({captured/len(non_anchors)*100:.1f}%)")

# -- 8. PCA visualization data --
print(f"\n{'='*70}")
print(f"PCA ANALYSIS (2D projection)")
print(f"{'='*70}")

if len(memories) > 3:
    all_vecs = np.array([m["vector"] for m in memories])
    pca = PCA(n_components=2)
    coords_2d = pca.fit_transform(all_vecs)
    print(f"  Explained variance: PC1={pca.explained_variance_ratio_[0]:.3f}, PC2={pca.explained_variance_ratio_[1]:.3f}")
    print(f"  Total explained: {sum(pca.explained_variance_ratio_):.3f}")

    anchor_set = set(id(a) for a in anchors)
    anchor_coords = []
    non_anchor_coords = []
    for i, m in enumerate(memories):
        if id(m) in anchor_set:
            anchor_coords.append(coords_2d[i])
        else:
            non_anchor_coords.append(coords_2d[i])

    anchor_coords = np.array(anchor_coords) if anchor_coords else np.empty((0, 2))
    non_anchor_coords = np.array(non_anchor_coords) if non_anchor_coords else np.empty((0, 2))

    if len(anchor_coords) > 0:
        anchor_centroid = np.mean(anchor_coords, axis=0)
        anchor_spread = np.mean(np.linalg.norm(anchor_coords - anchor_centroid, axis=1))
        print(f"  Anchor centroid: ({anchor_centroid[0]:.3f}, {anchor_centroid[1]:.3f})")
        print(f"  Anchor spread (mean dist to centroid): {anchor_spread:.4f}")

    if len(non_anchor_coords) > 0:
        na_centroid = np.mean(non_anchor_coords, axis=0)
        na_spread = np.mean(np.linalg.norm(non_anchor_coords - na_centroid, axis=1))
        print(f"  Non-anchor centroid: ({na_centroid[0]:.3f}, {na_centroid[1]:.3f})")
        print(f"  Non-anchor spread: {na_spread:.4f}")

    if len(anchor_coords) > 0 and len(non_anchor_coords) > 0:
        centroid_dist = np.linalg.norm(anchor_centroid - na_centroid)
        print(f"  Centroid separation: {centroid_dist:.4f}")
        if anchor_spread < na_spread:
            print(f"  ** Anchors are MORE tightly clustered than non-anchors in PCA space **")
        else:
            print(f"  ** Anchors are MORE spread out than non-anchors in PCA space **")

# -- 9. Trust-band analysis --
print(f"\n{'='*70}")
print(f"TRUST-BAND ANALYSIS (similarity by trust tier)")
print(f"{'='*70}")

trust_bands = [
    ("ultra-high (>= 0.9)", 0.9, 1.01),
    ("high (0.7-0.9)", 0.7, 0.9),
    ("medium (0.4-0.7)", 0.4, 0.7),
    ("low (< 0.4)", 0.0, 0.4),
]

for label, lo, hi in trust_bands:
    band = [m for m in memories if lo <= m["trust"] < hi]
    if len(band) < 2:
        print(f"  {label}: {len(band)} memories (too few for analysis)")
        continue
    band_vecs = np.array([m["vector"] for m in band])
    sim_mat = cosine_sim_matrix(band_vecs)
    n = len(band)
    pairs = []
    for i in range(n):
        for j in range(i+1, n):
            pairs.append(sim_mat[i, j])
    pairs = np.array(pairs)
    print(f"  {label}: {n} memories, mean intra-sim={np.mean(pairs):.4f}, median={np.median(pairs):.4f}")

# -- 10. Kind distribution among anchors --
print(f"\n{'='*70}")
print(f"ANCHOR KIND DISTRIBUTION")
print(f"{'='*70}")
kind_counts = defaultdict(int)
for a in anchors:
    kind_counts[a["kind"] or "null"] += 1
for k, v in sorted(kind_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print(f"\n{'='*70}")
print(f"ALL ANCHOR MEMORIES (full list)")
print(f"{'='*70}")
for i, a in enumerate(sorted(anchors, key=lambda x: -x["access_count"])):
    print(f"  [{i+1}] trust={a['trust']:.3f} access={a['access_count']} contra={a['contradiction_count']} kind={a['kind']}")
    print(f"      {textwrap.shorten(a['text'], width=130)}")

print("\n\nDONE.")
