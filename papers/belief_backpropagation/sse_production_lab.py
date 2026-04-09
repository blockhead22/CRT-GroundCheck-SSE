"""SSE Production Lab — Semantic String Engine on Real Data

Tests the wobble/resonance mechanism against Nick's actual production
memories and BDG. Not synthetic. Real beliefs, real edges, real tensions.

Questions:
  1. What does Nick's belief fingerprint look like?
  2. Do cross-domain strings exist in production data?
  3. What does the contradiction tension map look like?
  4. Can the wobble surface facts that flat retrieval misses?

Run: python -m papers.belief_backpropagation.sse_production_lab
"""

import sys
import json
import sqlite3
sys.path.insert(0, r"D:\AI_round2")

import numpy as np

np.random.seed(42)


def cosine(a, b):
    d = np.linalg.norm(a) * np.linalg.norm(b)
    if d < 1e-10:
        return 0.0
    return float(np.dot(a, b) / d)


def compute_wobble_flat(vectors, edges, query_vec, damping=0.7, beta=0.5, threshold=0.01):
    """Wobble on flat data (no BDG object needed).

    vectors: dict {id: np.array}
    edges: list of (src, tgt, weight, edge_type)
    """
    from collections import deque

    # Step 1: direct cosine
    direct = {nid: cosine(query_vec, v) for nid, v in vectors.items()}

    # Build adjacency
    out_edges = {}  # node -> [(target, weight)]
    in_edges = {}   # node -> [(source, weight)]
    for src, tgt, w, etype in edges:
        if etype == "CONTRADICTS":
            continue
        if src not in out_edges:
            out_edges[src] = []
        out_edges[src].append((tgt, w))
        if tgt not in in_edges:
            in_edges[tgt] = []
        in_edges[tgt].append((src, w))

    # Step 2: forward propagation
    propagated = {nid: 0.0 for nid in vectors}
    queue = deque()
    for nid, sim in direct.items():
        if sim > threshold:
            queue.append((nid, sim, 0))

    while queue:
        node, res, depth = queue.popleft()
        if depth > 5:
            continue
        for tgt, w in out_edges.get(node, []):
            prop = res * w * damping
            if prop < threshold:
                continue
            if prop > propagated.get(tgt, 0):
                propagated[tgt] = prop
                queue.append((tgt, prop, depth + 1))

    # Step 3: backward propagation
    queue = deque()
    for nid, sim in direct.items():
        if sim > threshold:
            queue.append((nid, sim, 0))

    while queue:
        node, res, depth = queue.popleft()
        if depth > 3:
            continue
        for src, w in in_edges.get(node, []):
            prop = res * w * damping * beta
            if prop < threshold:
                continue
            if prop > propagated.get(src, 0):
                propagated[src] = prop
                queue.append((src, prop, depth + 1))

    # Combine
    result = {}
    for nid in vectors:
        d = direct.get(nid, 0)
        p = propagated.get(nid, 0)
        result[nid] = (d, p, d + p)

    return result


def load_production_data():
    """Load memories and BDG edges from production database."""
    db_path = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db_path)

    # Load memories with vectors
    rows = conn.execute("""
        SELECT memory_id, text, trust, vector_json, kind, access_count, contradiction_count
        FROM memories
        WHERE deprecated = 0 AND vector_json IS NOT NULL
    """).fetchall()

    memories = {}
    vectors = {}
    for mid, text, trust, vec_json, kind, access, contras in rows:
        try:
            vec = np.array(json.loads(vec_json), dtype=np.float32)
            if len(vec) == 384:
                memories[mid] = {
                    "text": text[:200],
                    "trust": trust,
                    "kind": kind,
                    "access_count": access,
                    "contradiction_count": contras,
                }
                vectors[mid] = vec
        except:
            continue

    # Try to load BDG edges
    edges = []
    try:
        bdg_rows = conn.execute("""
            SELECT source_id, target_id, weight, edge_type
            FROM bdg_edges
        """).fetchall()
        for src, tgt, w, etype in bdg_rows:
            if src in vectors and tgt in vectors:
                edges.append((src, tgt, w, etype))
    except:
        pass

    # If no BDG edges table, build edges from contradiction ledger
    if not edges:
        try:
            contra_rows = conn.execute("""
                SELECT old_memory_id, new_memory_id
                FROM contradiction_ledger
                WHERE old_memory_id IS NOT NULL AND new_memory_id IS NOT NULL
            """).fetchall()
            for old_id, new_id in contra_rows:
                if old_id in vectors and new_id in vectors:
                    edges.append((old_id, new_id, 0.7, "CONTRADICTS"))
        except:
            pass

    # Build proximity edges for memories with high cosine similarity
    # (simulating what a full BDG would have)
    if len(edges) < 50:
        print("  [INFO] Building proximity edges from vector similarity...")
        ids = list(vectors.keys())
        n = len(ids)
        # Sample pairs to keep it fast
        np.random.seed(42)
        pair_count = 0
        for i in range(min(n, 300)):
            for j in range(i + 1, min(n, 300)):
                sim = cosine(vectors[ids[i]], vectors[ids[j]])
                if sim > 0.5:
                    edges.append((ids[i], ids[j], sim, "SUPPORTS"))
                    edges.append((ids[j], ids[i], sim, "SUPPORTS"))
                    pair_count += 1
        print(f"  [INFO] Built {pair_count} proximity edge pairs (sim > 0.5)")

    conn.close()
    return memories, vectors, edges


def embed_query(text, vectors, memories):
    """Simple query embedding: find closest memory and perturb slightly."""
    # Use sentence-transformers if available, otherwise find closest memory
    try:
        from personal_agent.embeddings import encode_text
        vec = np.array(encode_text(text), dtype=np.float32)
        return vec
    except:
        pass

    # Fallback: keyword match then use that vector
    text_lower = text.lower()
    best_id = None
    best_score = -1
    for mid, meta in memories.items():
        words = meta["text"].lower().split()
        overlap = sum(1 for w in text_lower.split() if w in words)
        if overlap > best_score:
            best_score = overlap
            best_id = mid
    if best_id:
        return vectors[best_id] + np.random.randn(384).astype(np.float32) * 0.05
    return np.random.randn(384).astype(np.float32)


# ===================================================================
# Lab 17: Nick's Belief Fingerprint
# ===================================================================

def lab_17_fingerprint(memories, vectors, edges):
    print("=" * 70)
    print("LAB 17: Nick's Belief Fingerprint")
    print("=" * 70)
    print(f"  {len(memories)} memories, {len(edges)} edges")

    # Identify anchor memories (high trust + high access)
    anchors = {mid: m for mid, m in memories.items()
               if m["trust"] >= 0.7 and m["access_count"] >= 2}
    print(f"\n  Anchors (trust >= 0.7, accessed >= 2): {len(anchors)}")
    for mid, m in sorted(anchors.items(), key=lambda x: -x[1]["trust"])[:10]:
        print(f"    [{m['trust']:.2f}] {m['text'][:80]}")

    # Find high-contradiction memories (tension points)
    tension_points = {mid: m for mid, m in memories.items()
                      if m["contradiction_count"] >= 1}
    print(f"\n  Tension points (contradiction_count >= 1): {len(tension_points)}")
    for mid, m in sorted(tension_points.items(), key=lambda x: -x[1]["contradiction_count"])[:10]:
        print(f"    [contras={m['contradiction_count']}, trust={m['trust']:.2f}] {m['text'][:80]}")

    # Map domain clusters via anchor proximity
    print(f"\n  Anchor basin sizes:")
    anchor_ids = list(anchors.keys())
    basin_counts = {aid: 0 for aid in anchor_ids}
    for mid, vec in vectors.items():
        if mid in anchor_ids:
            continue
        best_anchor = max(anchor_ids, key=lambda a: cosine(vec, vectors[a]))
        basin_counts[best_anchor] += 1

    for aid, count in sorted(basin_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    [{count:3d} satellites] {memories[aid]['text'][:70]}")

    return anchors, tension_points


# ===================================================================
# Lab 18: Cross-Domain String Discovery
# ===================================================================

def lab_18_cross_domain(memories, vectors, edges):
    print("\n" + "=" * 70)
    print("LAB 18: Cross-Domain String Discovery")
    print("=" * 70)
    print("  Question: Do cross-domain connections exist in production data?")

    # Test queries that should activate multiple domains
    test_queries = [
        ("health_to_work", "How is your cGVHD affecting your work?"),
        ("identity_to_project", "Tell me about what Nick built"),
        ("preference_to_identity", "Why is orange your favorite color?"),
        ("work_to_emotion", "How do you feel about being self-employed?"),
    ]

    for query_name, query_text in test_queries:
        print(f"\n  Query: '{query_text}'")

        query_vec = embed_query(query_text, vectors, memories)
        wobble = compute_wobble_flat(vectors, edges, query_vec)

        # Top by direct cosine
        by_cosine = sorted(wobble.items(), key=lambda x: -x[1][0])[:5]
        # Top by propagation only
        by_propagation = sorted(
            [(mid, vals) for mid, vals in wobble.items() if vals[1] > 0.01],
            key=lambda x: -x[1][1]
        )[:5]

        print(f"    Cosine top-5:")
        for mid, (d, p, t) in by_cosine:
            print(f"      [{d:.3f}] {memories[mid]['text'][:70]}")

        if by_propagation:
            print(f"    Edge-propagated (not in cosine top):")
            cosine_top_ids = {mid for mid, _ in by_cosine}
            for mid, (d, p, t) in by_propagation:
                if mid not in cosine_top_ids:
                    print(f"      [prop={p:.3f}] {memories[mid]['text'][:70]}")


# ===================================================================
# Lab 19: Wobble vs Flat Retrieval on Production Data
# ===================================================================

def lab_19_wobble_vs_flat(memories, vectors, edges):
    print("\n" + "=" * 70)
    print("LAB 19: Wobble vs Flat Retrieval (Production)")
    print("=" * 70)

    queries = [
        "What do you know about my health?",
        "Where do I work?",
        "What's my favorite color?",
        "Tell me about myself",
        "What have I been building?",
    ]

    total_extra = 0

    for query_text in queries:
        query_vec = embed_query(query_text, vectors, memories)
        wobble = compute_wobble_flat(vectors, edges, query_vec)

        # Flat: top 10 by cosine only
        flat_top10 = set(mid for mid, _ in sorted(
            wobble.items(), key=lambda x: -x[1][0])[:10])

        # Wobble: top 10 by total resonance
        wobble_top10 = set(mid for mid, _ in sorted(
            wobble.items(), key=lambda x: -x[1][2])[:10])

        wobble_only = wobble_top10 - flat_top10
        total_extra += len(wobble_only)

        print(f"\n  '{query_text}'")
        print(f"    Flat top-10 vs Wobble top-10: {len(wobble_only)} extra from edges")
        for mid in wobble_only:
            d, p, t = wobble[mid]
            print(f"      [d={d:.3f} p={p:.3f}] {memories[mid]['text'][:70]}")

    print(f"\n  Total extra memories surfaced by wobble: {total_extra} across {len(queries)} queries")
    return total_extra


# ===================================================================
# Lab 20: Tension Map — Contradiction Strings
# ===================================================================

def lab_20_tension_map(memories, vectors, edges):
    print("\n" + "=" * 70)
    print("LAB 20: Tension Map — Contradiction Strings")
    print("=" * 70)

    # Find CONTRADICTS edges
    contradictions = [(s, t, w) for s, t, w, e in edges if e == "CONTRADICTS"]
    print(f"  Contradiction edges: {len(contradictions)}")

    if not contradictions:
        # Build from high-similarity + different trust
        print("  No explicit contradiction edges. Finding tension from trust divergence...")
        tension_pairs = []
        ids = list(vectors.keys())
        for i in range(min(len(ids), 200)):
            for j in range(i + 1, min(len(ids), 200)):
                sim = cosine(vectors[ids[i]], vectors[ids[j]])
                if sim > 0.6:
                    trust_diff = abs(memories[ids[i]]["trust"] - memories[ids[j]]["trust"])
                    if trust_diff > 0.3:
                        tension_pairs.append((ids[i], ids[j], sim, trust_diff))

        tension_pairs.sort(key=lambda x: -x[3])
        print(f"  High-similarity + trust-divergent pairs: {len(tension_pairs)}")
        for a, b, sim, tdiff in tension_pairs[:10]:
            print(f"    sim={sim:.3f} trust_gap={tdiff:.2f}")
            print(f"      [{memories[a]['trust']:.2f}] {memories[a]['text'][:70]}")
            print(f"      [{memories[b]['trust']:.2f}] {memories[b]['text'][:70]}")
        return tension_pairs

    for src, tgt, w in contradictions[:10]:
        if src in memories and tgt in memories:
            print(f"\n    [{memories[src]['trust']:.2f}] {memories[src]['text'][:70]}")
            print(f"    [{memories[tgt]['trust']:.2f}] {memories[tgt]['text'][:70]}")
            print(f"    Tension weight: {w:.2f}")

    return contradictions


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# SSE PRODUCTION LAB")
    print("# Semantic String Engine on Real Data")
    print("#" * 70)

    print("\n  Loading production data...")
    memories, vectors, edges = load_production_data()
    print(f"  Loaded: {len(memories)} memories, {len(vectors)} vectors, {len(edges)} edges")

    lab_17_fingerprint(memories, vectors, edges)
    lab_18_cross_domain(memories, vectors, edges)
    lab_19_wobble_vs_flat(memories, vectors, edges)
    lab_20_tension_map(memories, vectors, edges)

    print("\n" + "=" * 70)
    print("SSE PRODUCTION LAB COMPLETE")
    print("=" * 70)
