"""Real BDG Analysis — Build a Belief Dependency Graph from production data.

Loads 606 active memories from crt_memory_shared.db, computes similarity edges,
detects geometric contradictions, builds a NetworkX graph, reports topology,
and runs cascade propagation on real data.

Run: python papers/cascade_complexity/real_bdg.py
"""

import sys
import json
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from personal_agent.memory_splats import (
    MemorySplat, create_splat, create_splat_from_type,
    cosine_similarity, overlap_integral, detect_geometric_contradiction,
)
from personal_agent.info_geometry import fisher_rao_distance

import sys as _sys
if _sys.stdout.encoding and _sys.stdout.encoding.lower() != 'utf-8':
    import io
    _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import networkx as nx
except ImportError:
    print("ERROR: networkx required. pip install networkx")
    sys.exit(1)


# ===================================================================
# Step 1: Load memories from production DB
# ===================================================================

def load_memories(db_path: str) -> dict[str, MemorySplat]:
    """Load all active memories as MemorySplats."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.execute("""
        SELECT memory_id, text, vector_json, trust, confidence,
               memory_type, sigma, belnap_state, domain_tags, kind, timestamp
        FROM memories
        WHERE deprecated = 0 AND vector_json IS NOT NULL
    """)

    splats = {}
    meta = {}  # memory_id -> {trust, domain_tags, kind, timestamp, belnap}

    for row in cur.fetchall():
        mid, text, vec_json, trust, conf, mtype, sigma_blob, belnap, dtags, kind, ts = row

        embedding = np.array(json.loads(vec_json), dtype=np.float32)

        if len(embedding) == 0:
            continue  # skip empty embeddings

        # Build sigma
        if sigma_blob is not None and len(sigma_blob) == 384 * 4:
            sigma = np.frombuffer(sigma_blob, dtype=np.float32).copy()
        else:
            sigma = None  # will use default

        # Map memory_type to splat types
        mtype_clean = mtype if mtype in ("fact", "preference", "event", "belief", "identity") else "belief"

        if sigma is not None:
            splat = MemorySplat(
                memory_id=mid,
                mu=embedding,
                sigma=sigma,
                alpha=conf,
                text=text[:200] if text else "",
                memory_type=mtype_clean,
                created_at=ts or 0.0,
                last_updated=ts or 0.0,
            )
        else:
            splat = create_splat_from_type(
                memory_id=mid,
                embedding=embedding,
                text=text[:200] if text else "",
                memory_type=mtype_clean,
                confidence=conf,
            )

        splats[mid] = splat
        meta[mid] = {
            "trust": trust,
            "domain_tags": json.loads(dtags) if dtags else [],
            "kind": kind or "observation",
            "timestamp": ts or 0.0,
            "belnap": belnap or "true",
            "text": text[:120] if text else "",
        }

    db.close()
    return splats, meta


def load_ledger_contradictions(db_path: str) -> list[tuple]:
    """Load contradiction pairs from ledger."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.execute("""
        SELECT old_memory_id, new_memory_id, drift_mean,
               contradiction_type, disposition, status
        FROM contradictions
    """)
    rows = cur.fetchall()
    db.close()
    return rows


# ===================================================================
# Step 2: Compute edges
# ===================================================================

def compute_similarity_matrix(splats: dict[str, MemorySplat]) -> tuple:
    """Vectorized pairwise cosine similarity."""
    ids = list(splats.keys())
    n = len(ids)

    # Stack all embeddings into matrix
    mat = np.stack([splats[mid].mu for mid in ids])  # (n, 384)
    # Normalize
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-8, None)
    mat_norm = mat / norms

    # Pairwise cosine sim
    sim_matrix = mat_norm @ mat_norm.T  # (n, n)

    return ids, sim_matrix


def build_edges(ids, sim_matrix, splats, meta,
                sim_threshold=0.5, contradiction_sim_threshold=0.7,
                ledger_contradictions=None):
    """Build edge list from similarity + geometric contradiction detection."""

    n = len(ids)
    id_to_idx = {mid: i for i, mid in enumerate(ids)}

    edges = []  # (src, tgt, type, weight, metadata)

    # Similarity edges (RELATED_TO / directed by timestamp: older -> newer)
    related_count = 0
    contradict_count = 0

    print(f"  Scanning {n*(n-1)//2:,} pairs...")
    t0 = time.time()

    # Get upper triangle indices where sim > threshold
    mask = np.triu(sim_matrix > sim_threshold, k=1)
    pairs = np.argwhere(mask)

    print(f"  Found {len(pairs):,} pairs above sim={sim_threshold} ({time.time()-t0:.1f}s)")

    # Check geometric contradictions for high-sim pairs
    high_sim_mask = np.triu(sim_matrix > contradiction_sim_threshold, k=1)
    high_pairs = np.argwhere(high_sim_mask)

    print(f"  Checking {len(high_pairs):,} high-sim pairs for geometric contradiction...")

    geo_contradictions = set()
    for i, j in high_pairs:
        mid_i, mid_j = ids[i], ids[j]
        result = detect_geometric_contradiction(splats[mid_i], splats[mid_j])
        if result.is_potential_contradiction:
            geo_contradictions.add((min(i, j), max(i, j)))

    print(f"  Geometric contradictions detected: {len(geo_contradictions)}")

    # Build edge list
    for i, j in pairs:
        mid_i, mid_j = ids[i], ids[j]
        sim = float(sim_matrix[i, j])

        pair_key = (min(i, j), max(i, j))

        if pair_key in geo_contradictions:
            # Bidirectional contradiction
            edges.append((mid_i, mid_j, "CONTRADICTS", sim, {}))
            edges.append((mid_j, mid_i, "CONTRADICTS", sim, {}))
            contradict_count += 1
        else:
            # Directed: older -> newer (older supports/grounds newer)
            ts_i = meta[mid_i]["timestamp"]
            ts_j = meta[mid_j]["timestamp"]
            if ts_i <= ts_j:
                edges.append((mid_i, mid_j, "RELATED_TO", sim, {}))
            else:
                edges.append((mid_j, mid_i, "RELATED_TO", sim, {}))
            related_count += 1

    # Layer in ledger contradictions
    ledger_added = 0
    if ledger_contradictions:
        for old_id, new_id, drift, ctype, disp, status in ledger_contradictions:
            if old_id in id_to_idx and new_id in id_to_idx:
                edges.append((old_id, new_id, "CONTRADICTS", drift, {"ledger": True}))
                edges.append((new_id, old_id, "CONTRADICTS", drift, {"ledger": True}))
                ledger_added += 1

    print(f"  Edges: {related_count} RELATED_TO, {contradict_count} CONTRADICTS (geometric), {ledger_added} CONTRADICTS (ledger)")

    return edges


# ===================================================================
# Step 3: Build graph and report topology
# ===================================================================

def build_graph(ids, edges, meta):
    """Build NetworkX digraph and report topology."""
    G = nx.DiGraph()

    for mid in ids:
        G.add_node(mid, **meta[mid])

    for src, tgt, etype, weight, emeta in edges:
        G.add_edge(src, tgt, edge_type=etype, weight=weight, **emeta)

    return G


def report_topology(G):
    """Print topology statistics."""
    print("\n" + "=" * 70)
    print("TOPOLOGY REPORT")
    print("=" * 70)

    n = G.number_of_nodes()
    m = G.number_of_edges()
    print(f"\n  Nodes: {n}")
    print(f"  Edges: {m}")
    print(f"  Density: {nx.density(G):.4f}")

    # Edge type counts
    etypes = defaultdict(int)
    for u, v, d in G.edges(data=True):
        etypes[d.get("edge_type", "unknown")] += 1
    print(f"  Edge types: {dict(etypes)}")

    # Degree distribution
    out_degrees = [d for _, d in G.out_degree()]
    in_degrees = [d for _, d in G.in_degree()]
    print(f"\n  Out-degree: min={min(out_degrees)}, max={max(out_degrees)}, "
          f"mean={np.mean(out_degrees):.1f}, median={np.median(out_degrees):.0f}")
    print(f"  In-degree:  min={min(in_degrees)}, max={max(in_degrees)}, "
          f"mean={np.mean(in_degrees):.1f}, median={np.median(in_degrees):.0f}")

    # Degree histogram (top buckets)
    from collections import Counter
    out_hist = Counter(out_degrees)
    print(f"\n  Out-degree distribution (top 10):")
    for deg, count in sorted(out_hist.items(), key=lambda x: -x[1])[:10]:
        print(f"    degree {deg}: {count} nodes")

    # Connected components (undirected view)
    G_undirected = G.to_undirected()
    components = list(nx.connected_components(G_undirected))
    comp_sizes = sorted([len(c) for c in components], reverse=True)
    print(f"\n  Connected components: {len(components)}")
    print(f"  Largest: {comp_sizes[0]} nodes")
    if len(comp_sizes) > 1:
        print(f"  Top 5 sizes: {comp_sizes[:5]}")
        print(f"  Isolated nodes: {sum(1 for s in comp_sizes if s == 1)}")

    # DAG check
    is_dag = nx.is_directed_acyclic_graph(G)
    print(f"\n  Is DAG: {is_dag}")

    if not is_dag:
        # Count cycles with a limit to avoid combinatorial explosion
        cycle_count = 0
        cycle_lengths = Counter()
        sample_cycles = []
        for c in nx.simple_cycles(G):
            cycle_count += 1
            cycle_lengths[len(c)] += 1
            if len(sample_cycles) < 5:
                sample_cycles.append(c)
            if cycle_count >= 500:
                break
        print(f"  Cycles found: {'500+' if cycle_count >= 500 else cycle_count}")
        print(f"  Cycle length distribution: {dict(sorted(cycle_lengths.items()))}")
        for c in sample_cycles[:3]:
            labels = [G.nodes[n].get('text', n)[:40] for n in c[:3]]
            print(f"    Sample: {' -> '.join(labels)}{'...' if len(c) > 3 else ''}")

    # Longest path (only for DAG or DAG subgraph)
    if is_dag:
        longest = nx.dag_longest_path_length(G)
        print(f"  Longest directed path: {longest}")
    else:
        # Remove cycles (keep only RELATED_TO edges which are directed older->newer)
        G_dag = nx.DiGraph()
        for u, v, d in G.edges(data=True):
            if d.get("edge_type") != "CONTRADICTS":
                G_dag.add_edge(u, v, **d)
        if nx.is_directed_acyclic_graph(G_dag):
            longest = nx.dag_longest_path_length(G_dag)
            print(f"  Longest directed path (RELATED_TO only, DAG): {longest}")
        else:
            print(f"  WARNING: Even RELATED_TO-only subgraph has cycles")

    # Fan-in analysis
    fan_in = defaultdict(int)
    for node in G.nodes():
        fi = G.in_degree(node)
        fan_in[fi] += 1
    print(f"\n  Fan-in distribution:")
    for fi_val in sorted(fan_in.keys())[:10]:
        print(f"    fan-in {fi_val}: {fan_in[fi_val]} nodes")
    if max(fan_in.keys()) > 9:
        high_fi = [(n, G.in_degree(n)) for n in G.nodes() if G.in_degree(n) > 10]
        high_fi.sort(key=lambda x: -x[1])
        print(f"  High fan-in nodes (>10):")
        for mid, fi in high_fi[:5]:
            print(f"    {mid}: fan-in={fi}, text=\"{G.nodes[mid].get('text', '')[:60]}\"")

    # Top out-degree nodes (cascade sources)
    top_out = sorted(G.nodes(), key=lambda n: G.out_degree(n), reverse=True)[:5]
    print(f"\n  Top 5 out-degree nodes (potential cascade sources):")
    for mid in top_out:
        print(f"    {mid}: out={G.out_degree(mid)}, in={G.in_degree(mid)}, "
              f"text=\"{G.nodes[mid].get('text', '')[:60]}\"")

    return G


# ===================================================================
# Step 4: Cascade propagation engine
# ===================================================================

def propagate_cascade(G, splats, source_id, delta_0=1.0,
                      lipschitz=0.9, tau=0.01, max_depth=50,
                      held_nodes=None):
    """BFS cascade propagation with geometric damping.

    Multi-parent aggregation: MAX of incoming impacts (Definition 3.5).
    held_nodes: set of node IDs that block propagation (Proposition 5.3).
    """
    held_nodes = held_nodes or set()

    affected = {}  # node_id -> impact
    affected[source_id] = delta_0

    depth_map = {source_id: 0}
    width_per_level = defaultdict(int)
    width_per_level[0] = 1
    blocked_by_firewall = set()

    queue = deque([(source_id, delta_0, 0)])  # (node, impact, depth)

    total_impact = delta_0
    max_depth_reached = 0

    while queue:
        node, impact, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Held nodes absorb impact but don't propagate
        if node in held_nodes and node != source_id:
            continue

        for _, successor, edge_data in G.out_edges(node, data=True):
            w = edge_data.get("weight", 0.5)

            # Damped impact: w * L * parent_impact
            propagated = w * lipschitz * impact

            if propagated <= tau:
                continue

            # Check if successor is held — it gets affected but won't propagate
            if successor in held_nodes:
                if successor not in affected:
                    blocked_by_firewall.add(successor)

            # Multi-parent: take MAX
            if successor in affected:
                if propagated <= affected[successor]:
                    continue  # already had a bigger hit

            affected[successor] = propagated
            new_depth = depth + 1
            depth_map[successor] = new_depth
            width_per_level[new_depth] += 1
            max_depth_reached = max(max_depth_reached, new_depth)
            total_impact += propagated

            queue.append((successor, propagated, new_depth))

    # Compute width = max nodes at any single depth level
    max_width = max(width_per_level.values()) if width_per_level else 0

    return {
        "source": source_id,
        "affected": affected,
        "depth": max_depth_reached,
        "width": max_width,
        "total_nodes": len(affected),
        "total_impact": total_impact,
        "depth_map": depth_map,
        "width_per_level": dict(width_per_level),
        "blocked_by_firewall": blocked_by_firewall,
    }


def print_cascade_result(result, meta, splats):
    """Pretty-print a cascade result."""
    src = result["source"]
    print(f"\n  Source: {src}")
    print(f"    \"{meta[src]['text'][:80]}\"")
    print(f"  Depth: {result['depth']}")
    print(f"  Max width (single level): {result['width']}")
    print(f"  Total affected: {result['total_nodes']}")
    print(f"  Total impact: {result['total_impact']:.3f}")

    # Width per level
    print(f"  Width per depth level:")
    for d in sorted(result["width_per_level"].keys()):
        print(f"    depth {d}: {result['width_per_level'][d]} nodes")

    # Damping curve (impact by depth)
    depth_impacts = defaultdict(list)
    for nid, impact in result["affected"].items():
        d = result["depth_map"][nid]
        depth_impacts[d].append(impact)

    print(f"  Damping curve (avg impact per depth):")
    for d in sorted(depth_impacts.keys()):
        impacts = depth_impacts[d]
        print(f"    depth {d}: avg={np.mean(impacts):.4f}, max={max(impacts):.4f}, "
              f"min={min(impacts):.4f}, n={len(impacts)}")

    # Theorem 4.3 predictions
    rho = 0.9 * 0.5  # L * w_avg (rough)
    if rho < 1:
        predicted_depth = np.ceil(np.log(1.0 / 0.01) / np.log(1.0 / rho))
        predicted_total = 1.0 / (1.0 - rho)
        print(f"\n  Theorem 4.3 predictions (rho=L*w_avg={rho:.2f}):")
        print(f"    Predicted max depth: {predicted_depth:.0f}")
        print(f"    Predicted total impact bound: {predicted_total:.3f}")
        print(f"    Actual depth: {result['depth']}")
        print(f"    Actual total impact: {result['total_impact']:.3f}")

    # Top 10 most-affected nodes
    sorted_affected = sorted(result["affected"].items(), key=lambda x: -x[1])[:10]
    print(f"\n  Top 10 most-affected nodes:")
    for nid, impact in sorted_affected:
        d = result["depth_map"][nid]
        print(f"    [{d}] impact={impact:.4f} \"{meta[nid]['text'][:60]}\"")


# ===================================================================
# Step 5: Run everything
# ===================================================================

def main():
    base = Path(__file__).resolve().parents[2] / "personal_agent"
    mem_db = str(base / "crt_memory_shared.db")
    ledger_db = str(base / "crt_ledger_shared.db")

    print("=" * 70)
    print("REAL BDG ANALYSIS — Production Memory Database")
    print("=" * 70)

    # Load memories
    print("\n[1/5] Loading memories...")
    splats, meta = load_memories(mem_db)
    print(f"  Loaded {len(splats)} active memories as MemorySplats")

    sigma_count = sum(1 for s in splats.values() if not np.allclose(s.sigma, s.sigma[0]))
    print(f"  With real sigma (non-uniform): {sigma_count}")
    print(f"  With default sigma: {len(splats) - sigma_count}")

    # Type distribution
    type_dist = defaultdict(int)
    for s in splats.values():
        type_dist[s.memory_type] += 1
    print(f"  Types: {dict(type_dist)}")

    # Load ledger
    print("\n[2/5] Loading contradiction ledger...")
    ledger = load_ledger_contradictions(ledger_db)
    print(f"  Ledger entries: {len(ledger)}")

    # Compute similarity
    print("\n[3/5] Computing pairwise similarity and building edges...")
    ids, sim_matrix = compute_similarity_matrix(splats)

    # Stats on similarity distribution
    upper_tri = sim_matrix[np.triu_indices(len(ids), k=1)]
    print(f"  Similarity stats: min={upper_tri.min():.3f}, max={upper_tri.max():.3f}, "
          f"mean={upper_tri.mean():.3f}, median={np.median(upper_tri):.3f}")

    # Histogram
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    hist, _ = np.histogram(upper_tri, bins=bins)
    print(f"  Similarity distribution:")
    for i, count in enumerate(hist):
        pct = count / len(upper_tri) * 100
        print(f"    [{bins[i]:.1f}, {bins[i+1]:.1f}): {count:>6,} ({pct:>5.1f}%)")

    # Build edges with a few thresholds to understand
    for thresh in [0.7, 0.6, 0.5]:
        count = np.sum(upper_tri > thresh)
        print(f"  Pairs above {thresh}: {count:,}")

    # Use 0.5 threshold for analysis
    edges = build_edges(ids, sim_matrix, splats, meta,
                       sim_threshold=0.5,
                       contradiction_sim_threshold=0.7,
                       ledger_contradictions=ledger)

    # Build graph
    print("\n[4/5] Building graph...")
    G = build_graph(ids, edges, meta)
    report_topology(G)

    # Run cascades
    print("\n" + "=" * 70)
    print("[5/5] CASCADE PROPAGATION")
    print("=" * 70)

    # Pick interesting sources: top out-degree nodes
    top_out = sorted(G.nodes(), key=lambda n: G.out_degree(n), reverse=True)[:3]

    # Also find contradiction-involved memories
    contra_nodes = set()
    for u, v, d in G.edges(data=True):
        if d.get("edge_type") == "CONTRADICTS":
            contra_nodes.add(u)
            contra_nodes.add(v)
    contra_list = sorted(contra_nodes, key=lambda n: G.out_degree(n), reverse=True)[:2]

    # Combine, deduplicate
    cascade_sources = list(dict.fromkeys(top_out + contra_list))

    print(f"\n  Running cascades from {len(cascade_sources)} source nodes...")
    print(f"  Parameters: L=0.9, tau=0.01")

    for src in cascade_sources:
        print("\n" + "-" * 60)
        # Use Fisher-Rao distance from a synthetic "revised" version as delta_0
        # For now, use delta_0 = 1.0 (unit impact)
        result = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9, tau=0.01)
        print_cascade_result(result, meta, splats)

    # ===================================================================
    # FIREWALL EXPERIMENT (Proposition 5.3)
    # ===================================================================
    print("\n" + "=" * 70)
    print("[6] FIREWALL EXPERIMENT (Proposition 5.3)")
    print("=" * 70)

    # Find top fan-in nodes — these are the best firewall candidates
    top_fan_in = sorted(G.nodes(), key=lambda n: G.in_degree(n), reverse=True)[:5]
    print(f"\n  Top 5 fan-in nodes (firewall candidates):")
    for mid in top_fan_in:
        print(f"    {mid}: fan-in={G.in_degree(mid)}, out={G.out_degree(mid)}, "
              f"\"{meta[mid]['text'][:60]}\"")

    # Use the top out-degree source from before
    src = top_out[0]

    # Baseline: no firewall
    baseline = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9, tau=0.01)

    print(f"\n  Baseline cascade from: \"{meta[src]['text'][:60]}\"")
    print(f"    Nodes affected: {baseline['total_nodes']}")
    print(f"    Total impact: {baseline['total_impact']:.3f}")
    print(f"    Depth: {baseline['depth']}")

    # Try firewalls: single node, top-2, top-3
    for n_firewalls in [1, 2, 3, 5]:
        held = set(top_fan_in[:n_firewalls])

        result_fw = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9,
                                      tau=0.01, held_nodes=held)

        reduction_nodes = baseline['total_nodes'] - result_fw['total_nodes']
        reduction_impact = baseline['total_impact'] - result_fw['total_impact']
        pct_nodes = (reduction_nodes / baseline['total_nodes'] * 100) if baseline['total_nodes'] > 0 else 0
        pct_impact = (reduction_impact / baseline['total_impact'] * 100) if baseline['total_impact'] > 0 else 0

        print(f"\n  With {n_firewalls} firewall(s) (top fan-in held):")
        print(f"    Nodes affected: {result_fw['total_nodes']} "
              f"(reduction: {reduction_nodes}, {pct_nodes:.1f}%)")
        print(f"    Total impact: {result_fw['total_impact']:.3f} "
              f"(reduction: {reduction_impact:.3f}, {pct_impact:.1f}%)")
        print(f"    Depth: {result_fw['depth']}")
        print(f"    Blocked at firewall: {len(result_fw.get('blocked_by_firewall', set()))}")

    # Strategy 2: Block high OUT-degree nodes (cascade spreaders, not sinks)
    print(f"\n  --- Strategy 2: High out-degree firewalls ---")
    top_out_fw = sorted(G.nodes(), key=lambda n: G.out_degree(n), reverse=True)
    # Skip the source itself
    top_out_fw = [n for n in top_out_fw if n != src][:10]

    for n_fw in [1, 3, 5, 10]:
        held = set(top_out_fw[:n_fw])
        result_fw = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9,
                                      tau=0.01, held_nodes=held)
        reduction_n = baseline['total_nodes'] - result_fw['total_nodes']
        reduction_i = baseline['total_impact'] - result_fw['total_impact']
        pct_n = reduction_n / baseline['total_nodes'] * 100
        pct_i = reduction_i / baseline['total_impact'] * 100
        print(f"  {n_fw} high-out-degree firewalls: "
              f"nodes={result_fw['total_nodes']} (-{pct_n:.1f}%), "
              f"impact={result_fw['total_impact']:.1f} (-{pct_i:.1f}%), "
              f"depth={result_fw['depth']}")

    # Strategy 3: Block depth-1 neighbors of source (immediate firewall ring)
    print(f"\n  --- Strategy 3: Firewall ring (block all depth-1 successors) ---")
    depth1 = set(succ for _, succ in G.out_edges(src))
    # Pick top-N by out-degree from depth-1
    depth1_sorted = sorted(depth1, key=lambda n: G.out_degree(n), reverse=True)

    for n_fw in [5, 10, 20]:
        held = set(depth1_sorted[:n_fw])
        result_fw = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9,
                                      tau=0.01, held_nodes=held)
        reduction_n = baseline['total_nodes'] - result_fw['total_nodes']
        reduction_i = baseline['total_impact'] - result_fw['total_impact']
        pct_n = reduction_n / baseline['total_nodes'] * 100
        pct_i = reduction_i / baseline['total_impact'] * 100
        print(f"  {n_fw} depth-1 firewalls: "
              f"nodes={result_fw['total_nodes']} (-{pct_n:.1f}%), "
              f"impact={result_fw['total_impact']:.1f} (-{pct_i:.1f}%), "
              f"depth={result_fw['depth']}")

    # Strategy 4: Block ALL depth-1 successors
    held_all_d1 = set(depth1)
    result_all = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9,
                                   tau=0.01, held_nodes=held_all_d1)
    reduction_n = baseline['total_nodes'] - result_all['total_nodes']
    pct_n = reduction_n / baseline['total_nodes'] * 100
    print(f"\n  ALL {len(held_all_d1)} depth-1 firewalls: "
          f"nodes={result_all['total_nodes']} (-{pct_n:.1f}%), "
          f"impact={result_all['total_impact']:.1f}, "
          f"depth={result_all['depth']}")

    # Vertex cut analysis
    print(f"\n  --- Vertex cut analysis ---")
    G_undirected = G.to_undirected()
    try:
        artic_points = list(nx.articulation_points(G_undirected))
        print(f"  Articulation points: {len(artic_points)}")

        # Try using multiple articulation points as firewalls
        artic_by_degree = sorted(artic_points, key=lambda n: G.degree(n), reverse=True)
        for n_fw in [5, 10, 20]:
            held = set(artic_by_degree[:n_fw])
            result_fw = propagate_cascade(G, splats, src, delta_0=1.0, lipschitz=0.9,
                                          tau=0.01, held_nodes=held)
            reduction_n = baseline['total_nodes'] - result_fw['total_nodes']
            pct_n = reduction_n / baseline['total_nodes'] * 100
            print(f"  {n_fw} articulation-point firewalls: "
                  f"nodes={result_fw['total_nodes']} (-{pct_n:.1f}%), "
                  f"impact={result_fw['total_impact']:.1f}, "
                  f"depth={result_fw['depth']}")
    except Exception as e:
        print(f"  Articulation point analysis failed: {e}")

    # Summary comparison
    print("\n" + "=" * 70)
    print("SUMMARY: What the real data tells us about the theorems")
    print("=" * 70)

    is_dag = nx.is_directed_acyclic_graph(G)

    # DAG subgraph (RELATED_TO only)
    G_related = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if d.get("edge_type") == "RELATED_TO":
            G_related.add_edge(u, v, **d)

    related_is_dag = nx.is_directed_acyclic_graph(G_related)

    print(f"\n  Full graph is DAG: {is_dag}")
    print(f"  RELATED_TO subgraph is DAG: {related_is_dag}")

    if not is_dag:
        # Already counted above in topology report
        pass
        print(f"  -> Cycles come from bidirectional CONTRADICTS edges")

    # Fan-in stats
    in_degs = [G.in_degree(n) for n in G.nodes()]
    multi_parent = sum(1 for d in in_degs if d > 1)
    print(f"\n  Nodes with fan-in > 1 (multi-parent): {multi_parent}/{len(ids)} "
          f"({multi_parent/len(ids)*100:.1f}%)")
    print(f"  -> This is where Theorem 4.3's single-path assumption breaks")

    # Weight distribution
    weights = [d["weight"] for _, _, d in G.edges(data=True)]
    print(f"\n  Edge weight stats: min={min(weights):.3f}, max={max(weights):.3f}, "
          f"mean={np.mean(weights):.3f}")
    print(f"  Weights > 0.9: {sum(1 for w in weights if w > 0.9)}")
    print(f"  Weights < 0.5: {sum(1 for w in weights if w < 0.5)}")

    print(f"\n  DONE.")


if __name__ == "__main__":
    main()
