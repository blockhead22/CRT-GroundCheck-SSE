"""Compressed Epistemic Structure Lab

The question: Does epistemic structure survive vector compression?

Compression labs proved geometric preservation (0.983 cosine at 3-bit).
Backprop labs proved epistemic mechanics (30/30 on full-precision).
Nobody has checked if the BDG — dependency edges, cascade paths,
contradiction pairs, anchor basins — survives compression.

This lab builds the BDG twice: once from full-precision vectors, once
from compressed vectors. Then runs the backprop experiments on both
and compares results.

Run: python -m papers.belief_backpropagation.compressed_epistemic_lab
"""

import sys
import math
import time
sys.path.insert(0, r"D:\AI_round2")

import numpy as np

from personal_agent.memory_splats import create_locus, cosine_similarity as locus_cosine
from personal_agent.memory_graph import BeliefDependencyGraph, EdgeType
from papers.belief_backpropagation.backprop_engine import (
    EpistemicLoss, CorrectionEvent, DomainVolatility,
    compute_backward_gradients, apply_trust_adjustments,
)

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


# ===================================================================
# Compression functions (matching compression_lab methodology)
# ===================================================================

def quantize_3bit(vectors):
    """Uniform 3-bit scalar quantization per vector.

    Each dimension mapped to 8 levels (3 bits).
    Returns quantized vectors (dequantized back to float32).
    """
    compressed = []
    for v in vectors:
        vmin, vmax = v.min(), v.max()
        if vmax - vmin < 1e-10:
            compressed.append(v.copy())
            continue
        # Quantize to 8 levels
        normalized = (v - vmin) / (vmax - vmin)
        quantized = np.round(normalized * 7).astype(np.uint8)
        # Dequantize
        dequantized = (quantized / 7.0) * (vmax - vmin) + vmin
        compressed.append(dequantized.astype(np.float32))
    return compressed


def quantize_2bit(vectors):
    """Uniform 2-bit scalar quantization (4 levels)."""
    compressed = []
    for v in vectors:
        vmin, vmax = v.min(), v.max()
        if vmax - vmin < 1e-10:
            compressed.append(v.copy())
            continue
        normalized = (v - vmin) / (vmax - vmin)
        quantized = np.round(normalized * 3).astype(np.uint8)
        dequantized = (quantized / 3.0) * (vmax - vmin) + vmin
        compressed.append(dequantized.astype(np.float32))
    return compressed


def pca_reduce(vectors, target_dim=96):
    """PCA dimensionality reduction + reconstruction.

    Simulates the tier-0/tier-1 compression from CogniMap.
    """
    mat = np.array(vectors)
    mean = mat.mean(axis=0)
    centered = mat - mean
    # Truncated SVD
    U, S, Vt = np.linalg.svd(centered, full_matrices=False)
    # Keep top target_dim components
    reduced = centered @ Vt[:target_dim].T
    # Reconstruct
    reconstructed = reduced @ Vt[:target_dim] + mean
    return [reconstructed[i].astype(np.float32) for i in range(len(vectors))]


# ===================================================================
# Build a test BDG with known structure
# ===================================================================

def build_test_graph(vectors_dict):
    """Build a BDG from a dict of {name: (text, trust, vector)}.

    Returns (bdg, trust_state) with predetermined edges.
    """
    bdg = BeliefDependencyGraph(cascade_threshold=0.001)
    trust_state = {}

    for name, (text, trust, vec) in vectors_dict.items():
        bdg.add_belief(create_locus(name, vec, text, "fact", confidence=trust))
        trust_state[name] = trust

    # Fixed topology — same edges regardless of vectors
    edges = [
        # Anchor basin: identity
        ("name_nick", "lives_sussex", EdgeType.SUPPORTS, 0.8),
        ("name_nick", "left_walmart", EdgeType.SUPPORTS, 0.7),
        ("name_nick", "self_employed", EdgeType.SUPPORTS, 0.6),
        ("lives_sussex", "steaming_cup", EdgeType.SUPPORTS, 0.5),
        # Anchor basin: health
        ("leukemia", "cgvhd", EdgeType.SUPPORTS, 0.9),
        ("cgvhd", "left_walmart", EdgeType.SUPPORTS, 0.6),
        ("leukemia", "orange_color", EdgeType.SUPPORTS, 0.4),
        # Anchor basin: preferences
        ("orange_color", "not_green", EdgeType.CONTRADICTS, 0.8),
        ("coffee_real", "never_coffee", EdgeType.CONTRADICTS, 0.7),
        # Wrong belief with supporters
        ("old_convo", "design_studio", EdgeType.SUPPORTS, 0.6),
        ("retrieval_boost", "design_studio", EdgeType.SUPPORTS, 0.8),
        ("slot_classifier", "design_studio", EdgeType.SUPPORTS, 0.7),
        # Self-model
        ("self_reliable_empl", "design_studio", EdgeType.SUPPORTS, 0.7),
        ("self_reliable_empl", "left_walmart", EdgeType.SUPPORTS, 0.5),
        ("self_reliable_ident", "name_nick", EdgeType.SUPPORTS, 0.7),
    ]
    for src, tgt, etype, w in edges:
        if bdg.graph.has_node(src) and bdg.graph.has_node(tgt):
            bdg.add_dependency(src, tgt, etype, w)

    return bdg, trust_state


def make_test_nodes():
    """Create test nodes with full-precision vectors."""
    base_identity = make_embedding()
    base_health = make_embedding()
    base_pref = make_embedding()
    base_work = make_embedding()

    nodes = {
        # Identity anchor basin
        "name_nick":        ("My name is Nick", 0.95, make_embedding(base_identity, 0.05)),
        "lives_sussex":     ("I live in Sussex Wisconsin", 0.70, make_embedding(base_identity, 0.15)),
        "steaming_cup":     ("I go to the Steaming Cup", 0.50, make_embedding(base_identity, 0.20)),
        # Health anchor basin
        "leukemia":         ("I survived leukemia", 0.90, make_embedding(base_health, 0.05)),
        "cgvhd":            ("I have cGVHD", 0.85, make_embedding(base_health, 0.10)),
        # Work
        "left_walmart":     ("I left Walmart a year ago", 0.70, make_embedding(base_work, 0.10)),
        "self_employed":    ("I am self-employed", 0.65, make_embedding(base_work, 0.15)),
        "design_studio":    ("Nick works at a design studio", 0.45, make_embedding(base_work, 0.20)),
        # Preferences
        "orange_color":     ("My favorite color is orange", 0.90, make_embedding(base_pref, 0.05)),
        "not_green":        ("Actually my favorite color is green", 0.40, make_embedding(base_pref, 0.10)),
        "coffee_real":      ("I love coffee and hunt espresso makers", 0.58, make_embedding(base_pref, 0.15)),
        "never_coffee":     ("I never liked coffee", 0.30, make_embedding(base_pref, 0.20)),
        # Upstream supporters of wrong belief
        "old_convo":        ("Old conversation about design work", 0.50, make_embedding(base_work, 0.25)),
        "retrieval_boost":  ("Retrieval scoring boosted design memory", 0.70, make_embedding(base_work, 0.20)),
        "slot_classifier":  ("Slot classifier tagged as employer", 0.75, make_embedding(base_work, 0.18)),
        # Self-model
        "self_reliable_empl": ("I am reliable on employment facts", 0.80, make_embedding(base_work, 0.30)),
        "self_reliable_ident": ("I am reliable on identity facts", 0.80, make_embedding(base_identity, 0.30)),
    }
    return nodes


# ===================================================================
# Lab 7: Geometric Preservation Under Compression
# ===================================================================

def lab_7_geometric_preservation(full_nodes, compressed_nodes_3bit, compressed_nodes_2bit, compressed_nodes_pca):
    print("=" * 70)
    print("LAB 7: Geometric Preservation Under Compression")
    print("=" * 70)
    print("  Question: How much do vectors change under each compression level?")

    names = list(full_nodes.keys())

    for label, comp_nodes in [("3-bit", compressed_nodes_3bit), ("2-bit", compressed_nodes_2bit), ("PCA-96", compressed_nodes_pca)]:
        sims = []
        for name in names:
            v_full = full_nodes[name][2]
            v_comp = comp_nodes[name][2]
            sim = float(np.dot(v_full, v_comp) / (np.linalg.norm(v_full) * np.linalg.norm(v_comp)))
            sims.append(sim)

        mean_sim = np.mean(sims)
        min_sim = np.min(sims)
        print(f"\n  {label}: mean cosine = {mean_sim:.6f}, min = {min_sim:.6f}")
        check(mean_sim > 0.95, f"{label} mean cosine > 0.95 ({mean_sim:.4f})")

    return True


# ===================================================================
# Lab 8: Edge Preservation (Does the BDG topology survive?)
# ===================================================================

def lab_8_edge_preservation(full_nodes, compressed_nodes):
    print("\n" + "=" * 70)
    print("LAB 8: Edge Preservation Under Compression")
    print("=" * 70)
    print("  Question: Do BDG edges still make sense after compression?")

    bdg_full, _ = build_test_graph(full_nodes)
    bdg_comp, _ = build_test_graph(compressed_nodes)

    # Edges are topology-fixed (not derived from vectors), so they should be identical
    full_edges = set((u, v) for u, v, _ in bdg_full.graph.edges(data=True))
    comp_edges = set((u, v) for u, v, _ in bdg_comp.graph.edges(data=True))

    check(full_edges == comp_edges, f"Edge sets identical ({len(full_edges)} edges)")

    # But the SEMANTIC meaning of edges could drift.
    # Check: for SUPPORTS edges, are the source and target still similar?
    print("\n  Semantic edge validity (SUPPORTS edges, source-target similarity):")
    edge_drifts = []
    for u, v, edata in bdg_full.graph.edges(data=True):
        if edata.get("edge_type") == "CONTRADICTS":
            continue
        v_u_full = full_nodes[u][2]
        v_v_full = full_nodes[v][2]
        v_u_comp = compressed_nodes[u][2]
        v_v_comp = compressed_nodes[v][2]

        sim_full = float(np.dot(v_u_full, v_v_full) / (np.linalg.norm(v_u_full) * np.linalg.norm(v_v_full)))
        sim_comp = float(np.dot(v_u_comp, v_v_comp) / (np.linalg.norm(v_u_comp) * np.linalg.norm(v_v_comp)))
        drift = abs(sim_full - sim_comp)
        edge_drifts.append(drift)
        if drift > 0.05:
            print(f"    {u} -> {v}: full={sim_full:.4f} comp={sim_comp:.4f} drift={drift:.4f}")

    mean_drift = np.mean(edge_drifts) if edge_drifts else 0
    max_drift = np.max(edge_drifts) if edge_drifts else 0
    print(f"\n  Edge similarity drift: mean={mean_drift:.6f}, max={max_drift:.6f}")

    check(mean_drift < 0.02, f"Mean edge drift < 0.02 ({mean_drift:.6f})")
    check(max_drift < 0.10, f"Max edge drift < 0.10 ({max_drift:.6f})")

    return mean_drift, max_drift


# ===================================================================
# Lab 9: Backward Pass Gradient Preservation
# ===================================================================

def lab_9_gradient_preservation(full_nodes, compressed_nodes):
    print("\n" + "=" * 70)
    print("LAB 9: Backward Pass Gradient Preservation")
    print("=" * 70)
    print("  Question: Does backprop produce the same gradients after compression?")

    bdg_full, trust_full = build_test_graph(full_nodes)
    bdg_comp, trust_comp = build_test_graph(compressed_nodes)

    loss_fn = EpistemicLoss()
    event = CorrectionEvent(
        corrected_node_id="design_studio",
        trust_at_assertion=0.45,
        times_corrected=2,
        correction_source="user",
        time_since_assertion=7200,
        domain="employer",
    )
    loss = loss_fn.compute(event)

    lr = {n: 0.15 for n in trust_full}

    result_full = compute_backward_gradients(bdg_full.graph, "design_studio", loss, lr, damping_factor=0.9)
    result_comp = compute_backward_gradients(bdg_comp.graph, "design_studio", loss, lr, damping_factor=0.9)

    print(f"\n  Loss: {loss:.4f}")
    print(f"\n  Gradients (full vs compressed):")

    affected_full = result_full.affected_nodes - {"design_studio"}
    affected_comp = result_comp.affected_nodes - {"design_studio"}

    check(affected_full == affected_comp,
          f"Same nodes affected ({len(affected_full)} full, {len(affected_comp)} comp)")

    gradient_diffs = []
    for node in sorted(affected_full):
        g_full = result_full.gradients.get(node, 0)
        g_comp = result_comp.gradients.get(node, 0)
        diff = abs(g_full - g_comp)
        gradient_diffs.append(diff)
        print(f"    {node:25s}: full={g_full:.6f}  comp={g_comp:.6f}  diff={diff:.6f}")

    mean_diff = np.mean(gradient_diffs) if gradient_diffs else 0
    max_diff = np.max(gradient_diffs) if gradient_diffs else 0
    print(f"\n  Gradient diff: mean={mean_diff:.6f}, max={max_diff:.6f}")

    # Gradients should be IDENTICAL because they depend on edge weights and damping,
    # not on vector values. The BDG topology is fixed.
    check(max_diff < 0.001, f"Gradients identical (max diff {max_diff:.6f} < 0.001)")

    return mean_diff


# ===================================================================
# Lab 10: Self-Pruning Under Compression
# ===================================================================

def lab_10_self_pruning(full_nodes, compressed_nodes):
    print("\n" + "=" * 70)
    print("LAB 10: Self-Pruning Under Compression")
    print("=" * 70)
    print("  Question: Does the wrong belief still die after compression?")

    for label, nodes in [("Full precision", full_nodes), ("3-bit compressed", compressed_nodes)]:
        bdg, trust_state = build_test_graph(nodes)
        loss_fn = EpistemicLoss()
        vol = DomainVolatility()
        deprecation = 0.15

        for cycle in range(4):
            if trust_state["design_studio"] <= deprecation:
                break
            vol.record_correction("employer")
            vol.record_assertion("employer")
            lr = vol.get_learning_rate("employer", base_lr=0.15)
            learning_rates = {n: lr for n in trust_state}

            event = CorrectionEvent(
                corrected_node_id="design_studio",
                trust_at_assertion=trust_state["design_studio"],
                times_corrected=cycle + 1,
                correction_source="user",
                time_since_assertion=3600 * (cycle + 1),
                domain="employer",
            )
            loss = loss_fn.compute(event)

            result = compute_backward_gradients(
                bdg.graph, "design_studio", loss, learning_rates, damping_factor=0.9,
            )
            trust_state["design_studio"] = max(0, trust_state["design_studio"] - lr * loss)
            trust_state = apply_trust_adjustments(trust_state, result.trust_adjustments)

        pruned = trust_state["design_studio"] <= deprecation
        print(f"\n  {label}: design_studio final trust = {trust_state['design_studio']:.4f}, pruned = {pruned}")
        check(pruned, f"{label}: wrong belief self-pruned")

    return True


# ===================================================================
# Lab 11: Anchor Basin Survival
# ===================================================================

def lab_11_anchor_basins(full_nodes, compressed_nodes):
    print("\n" + "=" * 70)
    print("LAB 11: Anchor Basin Survival Under Compression")
    print("=" * 70)
    print("  Question: Do anchor gravitational basins survive compression?")

    anchors = ["name_nick", "leukemia", "orange_color"]
    satellites = {
        "name_nick": ["lives_sussex", "steaming_cup", "self_employed"],
        "leukemia": ["cgvhd", "left_walmart"],
        "orange_color": ["not_green", "coffee_real"],
    }

    print("\n  Anchor-satellite similarities (full vs compressed):")
    basin_preserved = 0
    basin_total = 0

    for anchor in anchors:
        for sat in satellites[anchor]:
            v_a_full = full_nodes[anchor][2]
            v_s_full = full_nodes[sat][2]
            v_a_comp = compressed_nodes[anchor][2]
            v_s_comp = compressed_nodes[sat][2]

            sim_full = float(np.dot(v_a_full, v_s_full) / (np.linalg.norm(v_a_full) * np.linalg.norm(v_s_full)))
            sim_comp = float(np.dot(v_a_comp, v_s_comp) / (np.linalg.norm(v_a_comp) * np.linalg.norm(v_s_comp)))
            drift = abs(sim_full - sim_comp)

            basin_total += 1
            if drift < 0.05:
                basin_preserved += 1

            print(f"    {anchor:15s} -> {sat:15s}: full={sim_full:.4f} comp={sim_comp:.4f} drift={drift:.4f}")

    # Check: nearest anchor for each non-anchor should be the SAME
    print("\n  Nearest-anchor assignment stability:")
    non_anchors = [n for n in full_nodes if n not in anchors]
    assignment_matches = 0

    for node in non_anchors:
        # Full precision: which anchor is closest?
        best_full = max(anchors, key=lambda a: float(
            np.dot(full_nodes[node][2], full_nodes[a][2]) /
            (np.linalg.norm(full_nodes[node][2]) * np.linalg.norm(full_nodes[a][2]))
        ))
        # Compressed: which anchor is closest?
        best_comp = max(anchors, key=lambda a: float(
            np.dot(compressed_nodes[node][2], compressed_nodes[a][2]) /
            (np.linalg.norm(compressed_nodes[node][2]) * np.linalg.norm(compressed_nodes[a][2]))
        ))
        match = best_full == best_comp
        if match:
            assignment_matches += 1
        else:
            print(f"    FLIP: {node}: full->{best_full}, comp->{best_comp}")

    assignment_rate = assignment_matches / len(non_anchors) if non_anchors else 1
    print(f"\n  Anchor assignment stability: {assignment_matches}/{len(non_anchors)} ({assignment_rate:.1%})")

    check(assignment_rate >= 0.85,
          f">=85% of nodes keep same nearest anchor ({assignment_rate:.1%})")
    check(basin_preserved / basin_total >= 0.80,
          f">=80% of basin similarities within 0.05 drift ({basin_preserved}/{basin_total})")

    return assignment_rate


# ===================================================================
# Lab 12: Convergence Under Compression
# ===================================================================

def lab_12_convergence(full_nodes, compressed_nodes):
    print("\n" + "=" * 70)
    print("LAB 12: Bidirectional Convergence Under Compression")
    print("=" * 70)
    print("  Question: Does the compressed system still converge?")

    results = {}

    for label, nodes in [("Full", full_nodes), ("3-bit", compressed_nodes)]:
        bdg, trust_state = build_test_graph(nodes)
        loss_fn = EpistemicLoss()
        vol = DomainVolatility()

        # Apply corrections to several nodes
        corrections = [
            ("design_studio", "employer"),
            ("not_green", "color"),
            ("never_coffee", "drink"),
            ("design_studio", "employer"),
            ("not_green", "color"),
        ]

        trust_history = [dict(trust_state)]
        for i, (node, domain) in enumerate(corrections):
            vol.record_correction(domain)
            vol.record_assertion(domain)
            lr = vol.get_learning_rate(domain, base_lr=0.12)
            learning_rates = {n: lr for n in trust_state}

            event = CorrectionEvent(
                corrected_node_id=node,
                trust_at_assertion=trust_state.get(node, 0.5),
                times_corrected=i + 1,
                correction_source="user",
                time_since_assertion=3600,
                domain=domain,
            )
            loss = loss_fn.compute(event)

            bp = compute_backward_gradients(bdg.graph, node, loss, learning_rates, damping_factor=0.85)
            trust_state[node] = max(0, trust_state[node] - lr * loss)
            trust_state = apply_trust_adjustments(trust_state, bp.trust_adjustments)
            trust_history.append(dict(trust_state))

        # Measure convergence
        deltas = []
        for i in range(1, len(trust_history)):
            delta = sum(abs(trust_history[i][n] - trust_history[i-1][n]) for n in trust_state) / len(trust_state)
            deltas.append(delta)

        early = np.mean(deltas[:2]) if len(deltas) >= 2 else deltas[0]
        late = np.mean(deltas[-2:]) if len(deltas) >= 2 else deltas[-1]
        contraction = late / early if early > 0 else 0

        print(f"\n  {label}: early_delta={early:.6f}, late_delta={late:.6f}, contraction={contraction:.4f}")
        results[label] = contraction

    check(results["3-bit"] < 1.0, f"Compressed system converges (contraction {results['3-bit']:.4f})")

    # Compare contraction ratios
    ratio_diff = abs(results["Full"] - results["3-bit"])
    print(f"\n  Contraction ratio difference: {ratio_diff:.4f}")
    check(ratio_diff < 0.3, f"Similar convergence behavior (diff {ratio_diff:.4f} < 0.3)")

    return results


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# COMPRESSED EPISTEMIC STRUCTURE LAB")
    print("# Question: Does epistemic structure survive vector compression?")
    print("#" * 70)

    # Build full-precision nodes
    full_nodes = make_test_nodes()
    full_vectors = [full_nodes[n][2] for n in full_nodes]
    names = list(full_nodes.keys())

    # Compress at multiple levels
    compressed_3bit = quantize_3bit(full_vectors)
    compressed_2bit = quantize_2bit(full_vectors)
    compressed_pca = pca_reduce(full_vectors, target_dim=96)

    # Rebuild node dicts with compressed vectors
    compressed_nodes_3bit = {
        n: (full_nodes[n][0], full_nodes[n][1], compressed_3bit[i])
        for i, n in enumerate(names)
    }
    compressed_nodes_2bit = {
        n: (full_nodes[n][0], full_nodes[n][1], compressed_2bit[i])
        for i, n in enumerate(names)
    }
    compressed_nodes_pca = {
        n: (full_nodes[n][0], full_nodes[n][1], compressed_pca[i])
        for i, n in enumerate(names)
    }

    # Run labs
    lab_7_geometric_preservation(full_nodes, compressed_nodes_3bit, compressed_nodes_2bit, compressed_nodes_pca)
    lab_8_edge_preservation(full_nodes, compressed_nodes_3bit)
    lab_9_gradient_preservation(full_nodes, compressed_nodes_3bit)
    lab_10_self_pruning(full_nodes, compressed_nodes_3bit)
    lab_11_anchor_basins(full_nodes, compressed_nodes_3bit)
    lab_12_convergence(full_nodes, compressed_nodes_3bit)

    # Bonus: Run edge preservation and anchor basins at 2-bit (stress test)
    print("\n" + "=" * 70)
    print("STRESS TEST: 2-bit compression")
    print("=" * 70)
    lab_8_edge_preservation(full_nodes, compressed_nodes_2bit)
    lab_11_anchor_basins(full_nodes, compressed_nodes_2bit)

    print("\n" + "=" * 70)
    print("STRESS TEST: PCA-96 compression")
    print("=" * 70)
    lab_8_edge_preservation(full_nodes, compressed_nodes_pca)
    lab_11_anchor_basins(full_nodes, compressed_nodes_pca)

    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed, {PASS_COUNT + FAIL_COUNT} total")
    print("=" * 70)

    if FAIL_COUNT == 0:
        print("ALL LABS PASSED - EPISTEMIC STRUCTURE SURVIVES COMPRESSION")
    else:
        print(f"{FAIL_COUNT} FAILURES - EPISTEMIC STRUCTURE PARTIALLY DEGRADED")

    sys.exit(0 if FAIL_COUNT == 0 else 1)
