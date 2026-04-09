"""Wobble Lab — Query Resonance Through the BDG

Two questions:
  1. Does the BDG wobble pattern surface memories that cosine alone misses?
  2. Can facts propagate forward through edges WITHOUT a full retrieval call?

The wobble: a query vector lands in the BDG. Every node resonates based on
cosine distance to the query. That resonance propagates through SUPPORTS edges.
Nodes that are FAR from the query in vector space but CONNECTED to resonant
nodes also activate. The BDG amplifies what cosine alone would miss.

Run: python -m papers.belief_backpropagation.wobble_lab
"""

import sys
sys.path.insert(0, r"D:\AI_round2")

import numpy as np
from personal_agent.memory_splats import create_locus
from personal_agent.memory_graph import BeliefDependencyGraph, EdgeType

np.random.seed(42)
D = 384
PASS_COUNT = 0
FAIL_COUNT = 0


def check(condition, label):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"    [PASS] {label}")
    else:
        FAIL_COUNT += 1
        print(f"    [FAIL] {label}")
    return condition


def make_embedding(base=None, noise=0.1):
    if base is None:
        base = np.random.randn(D).astype(np.float32)
    v = base + np.random.randn(D).astype(np.float32) * noise
    v /= np.linalg.norm(v)
    return v


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ===================================================================
# Quantize for compressed tests
# ===================================================================

def quantize_3bit(vec):
    vmin, vmax = vec.min(), vec.max()
    if vmax - vmin < 1e-10:
        return vec.copy()
    normalized = (vec - vmin) / (vmax - vmin)
    quantized = np.round(normalized * 7).astype(np.uint8)
    return ((quantized / 7.0) * (vmax - vmin) + vmin).astype(np.float32)


# ===================================================================
# Wobble: query resonance through the BDG
# ===================================================================

def compute_wobble(bdg, vectors, query_vec, damping=0.7, threshold=0.01):
    """Compute resonance pattern from a query through the BDG.

    Step 1: Direct cosine similarity (query vs each node).
    Step 2: Propagate resonance through SUPPORTS edges.
             If node A resonates at 0.6 and A->B has weight 0.8,
             B gets additional resonance of 0.6 * 0.8 * damping.
    Step 3: Final resonance = direct + propagated.

    Returns dict of {node_id: (direct_sim, propagated_sim, total_resonance)}.
    """
    from collections import deque

    # Step 1: direct cosine
    direct = {}
    for node_id, vec in vectors.items():
        direct[node_id] = cosine(query_vec, vec)

    # Step 2: propagate through edges (BFS, like forward cascade)
    propagated = {n: 0.0 for n in vectors}

    # Start from all nodes with positive direct similarity
    queue = deque()
    for node_id, sim in direct.items():
        if sim > threshold:
            queue.append((node_id, sim, 0))

    visited_depth = {n: -1 for n in vectors}

    while queue:
        node, resonance, depth = queue.popleft()
        if depth > 5:  # max propagation depth
            continue

        # Propagate through outgoing SUPPORTS edges
        if not bdg.graph.has_node(node):
            continue

        for _, succ, edata in bdg.graph.out_edges(node, data=True):
            edge_type = edata.get("edge_type", "SUPPORTS")
            if edge_type == "CONTRADICTS":
                continue  # contradictions don't propagate wobble

            w = edata.get("weight", 0.5)
            prop = resonance * w * damping

            if prop < threshold:
                continue

            if prop > propagated[succ]:
                propagated[succ] = prop
                queue.append((succ, prop, depth + 1))

    # Also propagate BACKWARDS (if A supports B and B resonates, A should wobble too)
    queue = deque()
    for node_id, sim in direct.items():
        if sim > threshold:
            queue.append((node_id, sim, 0))

    while queue:
        node, resonance, depth = queue.popleft()
        if depth > 3:  # shorter backward propagation
            continue

        if not bdg.graph.has_node(node):
            continue

        for pred, _, edata in bdg.graph.in_edges(node, data=True):
            edge_type = edata.get("edge_type", "SUPPORTS")
            if edge_type == "CONTRADICTS":
                continue

            w = edata.get("weight", 0.5)
            prop = resonance * w * damping * 0.5  # weaker backward wobble

            if prop < threshold:
                continue

            if prop > propagated[pred]:
                propagated[pred] = prop
                queue.append((pred, prop, depth + 1))

    # Combine
    result = {}
    for node_id in vectors:
        d = direct[node_id]
        p = propagated[node_id]
        result[node_id] = (d, p, d + p)

    return result


# ===================================================================
# Build test graph (production-like)
# ===================================================================

def build_test_world():
    """Build a BDG with semantic clusters that have known relationships."""

    # Create distinct semantic bases for different domains
    base_health = make_embedding()
    base_work = make_embedding()
    base_identity = make_embedding()
    base_pref = make_embedding()
    base_project = make_embedding()

    nodes = {
        # Health cluster
        "leukemia":        ("I survived leukemia", 0.90, make_embedding(base_health, 0.05)),
        "cgvhd":           ("I have chronic graft versus host disease", 0.85, make_embedding(base_health, 0.08)),
        "overnight_hard":  ("Overnight shifts are hard with cGVHD", 0.70, make_embedding(base_health, 0.15)),
        "orange_awareness":("Orange is the leukemia awareness color", 0.80, make_embedding(base_health, 0.20)),

        # Work cluster
        "left_walmart":    ("I left Walmart a year ago", 0.70, make_embedding(base_work, 0.05)),
        "self_employed":   ("I consider myself self-employed", 0.65, make_embedding(base_work, 0.10)),
        "freelance":       ("I do freelance photography and web dev", 0.55, make_embedding(base_work, 0.15)),
        "need_money":      ("I still need money though", 0.50, make_embedding(base_work, 0.20)),

        # Identity cluster
        "name_nick":       ("My name is Nick", 0.95, make_embedding(base_identity, 0.05)),
        "lives_sussex":    ("I live in Sussex Wisconsin", 0.70, make_embedding(base_identity, 0.10)),
        "blockhead":       ("My handle is Blockhead", 0.80, make_embedding(base_identity, 0.12)),

        # Project cluster
        "built_crt":       ("I built the CRT memory architecture", 0.85, make_embedding(base_project, 0.05)),
        "solo_builder":    ("I'm the sole builder of Aether", 0.80, make_embedding(base_project, 0.08)),
        "year_of_work":    ("Been working on this for over a year", 0.70, make_embedding(base_project, 0.12)),

        # Preference cluster
        "color_orange":    ("My favorite color is orange", 0.90, make_embedding(base_pref, 0.05)),
        "coffee_yes":      ("I love coffee and hunt espresso makers", 0.58, make_embedding(base_pref, 0.10)),
    }

    bdg = BeliefDependencyGraph(cascade_threshold=0.001)
    vectors = {}

    for name, (text, trust, vec) in nodes.items():
        bdg.add_belief(create_locus(name, vec, text, "fact", confidence=trust))
        vectors[name] = vec

    # Cross-domain edges (the interesting ones)
    edges = [
        # Health -> Work (cGVHD made overnights hard, which led to leaving)
        ("cgvhd", "overnight_hard", EdgeType.SUPPORTS, 0.8),
        ("overnight_hard", "left_walmart", EdgeType.SUPPORTS, 0.7),

        # Health -> Preference (leukemia awareness -> orange)
        ("leukemia", "orange_awareness", EdgeType.SUPPORTS, 0.6),
        ("orange_awareness", "color_orange", EdgeType.SUPPORTS, 0.5),

        # Work chain
        ("left_walmart", "self_employed", EdgeType.SUPPORTS, 0.8),
        ("self_employed", "freelance", EdgeType.SUPPORTS, 0.6),
        ("self_employed", "need_money", EdgeType.SUPPORTS, 0.5),

        # Identity -> Project
        ("name_nick", "built_crt", EdgeType.SUPPORTS, 0.4),
        ("built_crt", "solo_builder", EdgeType.SUPPORTS, 0.9),
        ("solo_builder", "year_of_work", EdgeType.SUPPORTS, 0.7),

        # Work -> Project (left walmart TO work on this)
        ("left_walmart", "year_of_work", EdgeType.SUPPORTS, 0.6),
    ]

    for src, tgt, etype, w in edges:
        bdg.add_dependency(src, tgt, etype, w)

    return bdg, nodes, vectors


# ===================================================================
# Lab 13: Wobble Surfaces What Cosine Misses
# ===================================================================

def lab_13_wobble_vs_cosine():
    print("=" * 70)
    print("LAB 13: Wobble vs Pure Cosine Retrieval")
    print("=" * 70)
    print("  Question: Does BDG wobble surface relevant memories cosine alone misses?")

    bdg, nodes, vectors = build_test_world()

    # Query: "Why did you leave your job?"
    # This should resonate with work cluster directly,
    # but wobble should ALSO activate health (cGVHD made overnights hard)
    # and project (left to work on CRT) through edges.
    query_vec = make_embedding(vectors["left_walmart"], 0.12)

    # Pure cosine retrieval (top-k)
    cosine_scores = {n: cosine(query_vec, v) for n, v in vectors.items()}
    cosine_ranked = sorted(cosine_scores.items(), key=lambda x: -x[1])

    print(f"\n  Pure cosine top-8:")
    for name, score in cosine_ranked[:8]:
        print(f"    {name:20s}: {score:.4f}  ({nodes[name][0][:50]})")

    # Wobble retrieval
    wobble = compute_wobble(bdg, vectors, query_vec)
    wobble_ranked = sorted(wobble.items(), key=lambda x: -x[1][2])

    print(f"\n  Wobble top-8 (direct + propagated = total):")
    for name, (d, p, t) in wobble_ranked[:8]:
        marker = " << EDGE-BOOSTED" if p > 0.05 and d < 0.2 else ""
        print(f"    {name:20s}: d={d:.4f} p={p:.4f} t={t:.4f}  ({nodes[name][0][:40]}){marker}")

    # Find memories that wobble surfaces but cosine doesn't
    cosine_top8 = set(n for n, _ in cosine_ranked[:8])
    wobble_top8 = set(n for n, _ in wobble_ranked[:8])

    wobble_only = wobble_top8 - cosine_top8
    print(f"\n  Memories wobble found that cosine missed: {wobble_only}")
    for name in wobble_only:
        d, p, t = wobble[name]
        print(f"    {name}: propagated={p:.4f} (brought forward by edges, not vector proximity)")

    # Key check: does wobble bring forward health facts through the
    # cgvhd -> overnight_hard -> left_walmart chain?
    cgvhd_wobble = wobble["cgvhd"][2]
    overnight_wobble = wobble["overnight_hard"][2]

    print(f"\n  Cross-domain propagation:")
    print(f"    cgvhd:          cosine={cosine_scores['cgvhd']:.4f}  wobble={cgvhd_wobble:.4f}")
    print(f"    overnight_hard: cosine={cosine_scores['overnight_hard']:.4f}  wobble={overnight_wobble:.4f}")

    check(len(wobble_only) >= 1,
          f"Wobble surfaces at least 1 memory cosine misses ({len(wobble_only)} found)")
    check(overnight_wobble > cosine_scores["overnight_hard"],
          f"Overnight shifts boosted by edge propagation ({overnight_wobble:.4f} > {cosine_scores['overnight_hard']:.4f})")

    return wobble_only


# ===================================================================
# Lab 14: Wobble Pattern Classification
# ===================================================================

def lab_14_wobble_patterns():
    print("\n" + "=" * 70)
    print("LAB 14: Wobble Pattern Classification")
    print("=" * 70)
    print("  Question: Can wobble patterns distinguish confident/contested/unknown?")

    bdg, nodes, vectors = build_test_world()

    # Query 1: "What's your name?" — should be tight, single-basin
    q1 = make_embedding(vectors["name_nick"], 0.08)
    w1 = compute_wobble(bdg, vectors, q1)
    resonances_1 = sorted([(n, t) for n, (d, p, t) in w1.items()], key=lambda x: -x[1])

    # Query 2: "Tell me about leaving your job and your health"
    # — touches two basins (work + health), should be scattered
    q2 = (vectors["left_walmart"] + vectors["cgvhd"]) / 2
    q2 /= np.linalg.norm(q2)
    w2 = compute_wobble(bdg, vectors, q2)
    resonances_2 = sorted([(n, t) for n, (d, p, t) in w2.items()], key=lambda x: -x[1])

    # Query 3: Random vector — nothing should resonate
    q3 = make_embedding()
    w3 = compute_wobble(bdg, vectors, q3)
    resonances_3 = sorted([(n, t) for n, (d, p, t) in w3.items()], key=lambda x: -x[1])

    # Measure pattern shape
    def wobble_profile(wobble_result):
        totals = sorted([t for _, (_, _, t) in wobble_result.items()], reverse=True)
        top1 = totals[0] if totals else 0
        top3_mean = np.mean(totals[:3]) if len(totals) >= 3 else top1
        above_threshold = sum(1 for t in totals if t > 0.15)
        spread = np.std(totals[:5]) if len(totals) >= 5 else 0
        return top1, top3_mean, above_threshold, spread

    p1 = wobble_profile(w1)
    p2 = wobble_profile(w2)
    p3 = wobble_profile(w3)

    print(f"\n  Query 1 (identity - should be tight):")
    print(f"    Top resonance: {p1[0]:.4f}, Top-3 mean: {p1[1]:.4f}, Above 0.15: {p1[2]}, Spread: {p1[3]:.4f}")
    for name, total in resonances_1[:5]:
        print(f"      {name:20s}: {total:.4f}")

    print(f"\n  Query 2 (multi-domain - should be scattered):")
    print(f"    Top resonance: {p2[0]:.4f}, Top-3 mean: {p2[1]:.4f}, Above 0.15: {p2[2]}, Spread: {p2[3]:.4f}")
    for name, total in resonances_2[:5]:
        print(f"      {name:20s}: {total:.4f}")

    print(f"\n  Query 3 (random - should be silent):")
    print(f"    Top resonance: {p3[0]:.4f}, Top-3 mean: {p3[1]:.4f}, Above 0.15: {p3[2]}, Spread: {p3[3]:.4f}")
    for name, total in resonances_3[:3]:
        print(f"      {name:20s}: {total:.4f}")

    # Tight: high top, few above threshold, low spread
    # Scattered: moderate top, many above threshold, high spread
    # Silent: low top, none above threshold
    check(p1[2] < p2[2],
          f"Multi-domain has more resonant nodes than single-domain ({p2[2]} > {p1[2]})")
    check(p3[0] < 0.25,
          f"Random query produces weak resonance ({p3[0]:.4f} < 0.25)")
    check(p1[0] > p3[0],
          f"Known query resonates stronger than random ({p1[0]:.4f} > {p3[0]:.4f})")

    return p1, p2, p3


# ===================================================================
# Lab 15: Token Propagation — Facts Without Retrieval
# ===================================================================

def lab_15_fact_propagation():
    print("\n" + "=" * 70)
    print("LAB 15: Fact Propagation Without Full Retrieval")
    print("=" * 70)
    print("  Question: Can the wobble bring forward associated facts")
    print("            that the query didn't directly ask about?")

    bdg, nodes, vectors = build_test_world()

    # Query about health: "How is your cGVHD?"
    # Direct resonance: cgvhd, leukemia (health cluster)
    # Edge propagation SHOULD bring forward:
    #   - overnight_hard (cgvhd -> overnight_hard)
    #   - left_walmart (overnight_hard -> left_walmart)
    #   - self_employed (left_walmart -> self_employed)
    #   - orange_awareness (leukemia -> orange_awareness)
    #   - color_orange (orange_awareness -> color_orange)
    # These are FACTS ABOUT WORK AND PREFERENCES that are relevant
    # to a health question because the BDG knows they're connected.

    query_vec = make_embedding(vectors["cgvhd"], 0.08)

    wobble = compute_wobble(bdg, vectors, query_vec)

    # Separate into: direct resonance vs edge-propagated
    direct_only = {}
    edge_brought = {}
    for name, (d, p, t) in wobble.items():
        if d > 0.2:
            direct_only[name] = (d, p, t)
        elif p > 0.02:
            edge_brought[name] = (d, p, t)

    print(f"\n  Query: 'How is your cGVHD?' (health domain)")
    print(f"\n  Directly resonant ({len(direct_only)}):")
    for name, (d, p, t) in sorted(direct_only.items(), key=lambda x: -x[1][2]):
        print(f"    {name:20s}: direct={d:.4f}  ({nodes[name][0][:50]})")

    print(f"\n  Edge-propagated facts ({len(edge_brought)}):")
    for name, (d, p, t) in sorted(edge_brought.items(), key=lambda x: -x[1][1], reverse=True):
        print(f"    {name:20s}: propagated={p:.4f}  ({nodes[name][0][:50]})")

    # The key insight: these edge-propagated facts are things a COSINE-ONLY
    # retrieval would never return for a health query, but they're relevant
    # because the BDG knows the causal chain.

    # Did we bring forward work facts from a health query?
    work_facts_brought = [n for n in edge_brought if n in
                          {"left_walmart", "self_employed", "freelance", "need_money",
                           "overnight_hard", "year_of_work"}]
    pref_facts_brought = [n for n in edge_brought if n in
                          {"color_orange", "orange_awareness"}]

    print(f"\n  Cross-domain facts surfaced:")
    print(f"    Work facts from health query: {work_facts_brought}")
    print(f"    Preference facts from health query: {pref_facts_brought}")

    check(len(work_facts_brought) >= 1,
          f"Health query surfaces work facts through edges ({work_facts_brought})")
    check(len(pref_facts_brought) >= 1,
          f"Health query surfaces preference facts through edges ({pref_facts_brought})")

    # Verify the causal chain is intact
    # cgvhd -> overnight_hard -> left_walmart -> self_employed
    chain = ["cgvhd", "overnight_hard", "left_walmart", "self_employed"]
    chain_resonances = [wobble[n][2] for n in chain]
    chain_decreasing = all(chain_resonances[i] >= chain_resonances[i+1]
                          for i in range(len(chain_resonances)-1))

    print(f"\n  Causal chain resonance:")
    for name, res in zip(chain, chain_resonances):
        print(f"    {name:20s}: {res:.4f}")
    print(f"  Chain decreasing: {chain_decreasing}")

    check(chain_decreasing, "Resonance decreases along causal chain (damping works)")

    return work_facts_brought, pref_facts_brought


# ===================================================================
# Lab 16: Wobble on Compressed Vectors
# ===================================================================

def lab_16_compressed_wobble():
    print("\n" + "=" * 70)
    print("LAB 16: Wobble Preservation Under 3-bit Compression")
    print("=" * 70)
    print("  Question: Does the wobble pattern survive compression?")

    bdg, nodes, vectors = build_test_world()

    # Compress all vectors
    compressed_vectors = {n: quantize_3bit(v) for n, v in vectors.items()}

    # Build compressed BDG (same topology)
    bdg_comp = BeliefDependencyGraph(cascade_threshold=0.001)
    for name, (text, trust, vec) in nodes.items():
        bdg_comp.add_belief(create_locus(name, compressed_vectors[name], text, "fact", confidence=trust))
    for src, tgt, edata in bdg.graph.edges(data=True):
        etype_str = edata.get("edge_type", "SUPPORTS")
        etype = EdgeType.CONTRADICTS if etype_str == "CONTRADICTS" else EdgeType.SUPPORTS
        bdg_comp.add_dependency(src, tgt, etype, edata.get("weight", 0.5))

    # Same query on both
    query_vec = make_embedding(vectors["cgvhd"], 0.08)
    query_comp = quantize_3bit(query_vec)

    wobble_full = compute_wobble(bdg, vectors, query_vec)
    wobble_comp = compute_wobble(bdg_comp, compressed_vectors, query_comp)

    # Compare rankings
    rank_full = sorted(wobble_full.items(), key=lambda x: -x[1][2])
    rank_comp = sorted(wobble_comp.items(), key=lambda x: -x[1][2])

    top8_full = [n for n, _ in rank_full[:8]]
    top8_comp = [n for n, _ in rank_comp[:8]]

    overlap = len(set(top8_full) & set(top8_comp))

    print(f"\n  Top-8 comparison:")
    print(f"    Full:       {top8_full}")
    print(f"    Compressed: {top8_comp}")
    print(f"    Overlap: {overlap}/8")

    # Compare total resonance values
    print(f"\n  Resonance comparison (top-10):")
    for name, (d_f, p_f, t_f) in rank_full[:10]:
        d_c, p_c, t_c = wobble_comp.get(name, (0, 0, 0))
        drift = abs(t_f - t_c)
        print(f"    {name:20s}: full={t_f:.4f}  comp={t_c:.4f}  drift={drift:.4f}")

    # Same edge-propagated facts?
    edge_full = {n for n, (d, p, t) in wobble_full.items() if d < 0.2 and p > 0.02}
    edge_comp = {n for n, (d, p, t) in wobble_comp.items() if d < 0.2 and p > 0.02}

    print(f"\n  Edge-propagated facts:")
    print(f"    Full: {sorted(edge_full)}")
    print(f"    Comp: {sorted(edge_comp)}")

    edge_overlap = len(edge_full & edge_comp)
    edge_total = len(edge_full | edge_comp)
    edge_pct = edge_overlap / edge_total if edge_total > 0 else 1

    check(overlap >= 6, f">=6/8 top wobble memories preserved ({overlap}/8)")
    check(edge_pct >= 0.70, f">=70% edge-propagated facts preserved ({edge_pct:.0%})")

    return overlap, edge_pct


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# WOBBLE LAB — Query Resonance Through the BDG")
    print("# Can the graph bring forward facts the query didn't ask for?")
    print("#" * 70)

    lab_13_wobble_vs_cosine()
    lab_14_wobble_patterns()
    lab_15_fact_propagation()
    lab_16_compressed_wobble()

    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed, {PASS_COUNT + FAIL_COUNT} total")
    print("=" * 70)

    if FAIL_COUNT == 0:
        print("ALL LABS PASSED")
    else:
        print(f"{FAIL_COUNT} FAILURES")

    sys.exit(0 if FAIL_COUNT == 0 else 1)
