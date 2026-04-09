"""Belief Backpropagation — Experiment Suite

Six labs validating the core claims of the belief backpropagation paper:
  Lab 1: Backward pass mechanics (gradient flows correctly)
  Lab 2: Design studio problem (backprop vs flat demotion)
  Lab 3: Self-pruning emergence (wrong beliefs die from gradient)
  Lab 4: Domain volatility (measurable, predictive)
  Lab 5: Bidirectional convergence (forward + backward → fixed point)
  Lab 6: Reflexive self-model (self-beliefs in same graph)

Run: python -m papers.belief_backpropagation.experiments
  or: python papers/belief_backpropagation/experiments.py
"""

import sys
import math
import time
sys.path.insert(0, r"D:\AI_round2")

import numpy as np

from personal_agent.memory_splats import create_locus
from personal_agent.memory_graph import BeliefDependencyGraph, EdgeType, CascadeResult
from papers.belief_backpropagation.backprop_engine import (
    EpistemicLoss, CorrectionEvent, DomainVolatility,
    compute_backward_gradients, apply_trust_adjustments, flat_demotion,
    BackpropResult,
)

np.random.seed(42)
D = 384
PASS_COUNT = 0
FAIL_COUNT = 0


def make_embedding(base=None, noise=0.1):
    if base is None:
        base = np.random.randn(D).astype(np.float32)
    v = base + np.random.randn(D).astype(np.float32) * noise
    v /= np.linalg.norm(v)
    return v


def check(condition, label):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"    [PASS] {label}")
    else:
        FAIL_COUNT += 1
        print(f"    [FAIL] {label}")
    return condition


# ===================================================================
# Lab 1: Backward Pass Mechanics
# ===================================================================

def lab_1_backward_mechanics():
    print("=" * 70)
    print("LAB 1: Backward Pass Mechanics")
    print("=" * 70)
    print("  Question: Does gradient flow backward through supporters correctly?")

    bdg = BeliefDependencyGraph(cascade_threshold=0.001)

    # Build graph: A -> B -> C -> D (corrected), E -> C
    base = make_embedding()
    nodes = {
        "A": ("Upstream belief A", 0.8),
        "B": ("Mid-chain belief B", 0.7),
        "C": ("Direct supporter C", 0.6),
        "D": ("Wrong belief D (corrected)", 0.73),
        "E": ("Alternate supporter E", 0.5),
    }
    for name, (text, conf) in nodes.items():
        bdg.add_belief(create_locus(name, make_embedding(base, 0.15), text, "fact", confidence=conf))

    bdg.add_dependency("A", "B", EdgeType.SUPPORTS, weight=0.8)
    bdg.add_dependency("B", "C", EdgeType.SUPPORTS, weight=0.7)
    bdg.add_dependency("C", "D", EdgeType.SUPPORTS, weight=0.9)
    bdg.add_dependency("E", "C", EdgeType.SUPPORTS, weight=0.6)

    # Also add a CONTRADICTS edge to verify it's skipped
    bdg.add_dependency("E", "D", EdgeType.CONTRADICTS, weight=0.5)

    print(f"\n  Graph: {bdg.num_nodes} nodes, {bdg.num_edges} edges")
    print(f"  A(0.8) -> B(0.7) -> C(0.6) -> D(corrected)")
    print(f"  E(0.5) -> C(0.6)")
    print(f"  E --CONTRADICTS--> D (should be skipped)")

    # Compute loss
    loss_fn = EpistemicLoss()
    event = CorrectionEvent(
        corrected_node_id="D",
        trust_at_assertion=0.73,
        times_corrected=1,
        correction_source="user",
        time_since_assertion=3600,
        domain="employer",
    )
    loss = loss_fn.compute(event)
    print(f"\n  Epistemic loss at D: {loss:.4f}")

    # Backward pass
    learning_rates = {n: 0.1 for n in nodes}
    result = compute_backward_gradients(
        bdg.graph, "D", loss, learning_rates, damping_factor=0.9,
    )

    print(f"\n  Gradients:")
    for node in ["C", "B", "A", "E"]:
        g = result.gradients.get(node, 0)
        print(f"    {node}: {g:.6f}")

    # Also test BDG's propagate_backward
    bdg_result = bdg.propagate_backward("D", loss, damping_factor=0.9)
    print(f"\n  BDG propagate_backward:")
    print(f"    Affected: {sorted(bdg_result.affected_nodes - {'D'})}")
    print(f"    Depth: {bdg_result.depth}")

    # Checks
    g_C = result.gradients.get("C", 0)
    g_B = result.gradients.get("B", 0)
    g_A = result.gradients.get("A", 0)
    g_E = result.gradients.get("E", 0)

    check(g_C > g_B > g_A, "Gradient decays with depth: C > B > A")
    check(g_C > 0, "C gets gradient (direct supporter)")
    check(g_E > 0, "E gets gradient (supports C)")
    check("D" not in result.trust_adjustments or result.trust_adjustments.get("D", 0) == 0,
          "Source node D not self-adjusted (loss is applied separately)")

    # Verify damping: each hop should multiply by (weight * damping)
    expected_C = loss * 0.9 * 0.9  # D->C edge weight=0.9, damping=0.9
    expected_B = g_C * 0.7 * 0.9   # C->B edge weight=0.7, damping=0.9
    check(abs(g_C - expected_C) < 0.01, f"C gradient matches expected ({g_C:.4f} ~ {expected_C:.4f})")
    check(abs(g_B - expected_B) < 0.01, f"B gradient matches expected ({g_B:.4f} ~ {expected_B:.4f})")

    # E should NOT get gradient through CONTRADICTS edge to D, only through C
    # E -> C (SUPPORTS, w=0.6) -> ... but E doesn't directly support D
    # E supports C, so E's gradient comes from C's gradient
    # E supports C (E->C edge). In backward from D: D <- C <- E.
    # E's gradient comes from C's gradient * edge_weight(E->C) * damping.
    # But the backward BFS may pick up slightly different due to MAX aggregation.
    check(g_E > 0.1, f"E gets meaningful gradient through C ({g_E:.4f})")
    check(g_E < g_C, f"E gradient < C gradient (further from source, {g_E:.4f} < {g_C:.4f})")

    return result


# ===================================================================
# Lab 2: Design Studio Problem
# ===================================================================

def lab_2_design_studio():
    print("\n" + "=" * 70)
    print("LAB 2: Design Studio Problem")
    print("=" * 70)
    print("  Question: Does backprop kill the bad memory faster than flat demotion?")

    # --- Flat demotion baseline ---
    print("\n  --- Flat Demotion Baseline ---")
    trust_flat = 0.73
    flat_trajectory = [trust_flat]
    deprecation_threshold = 0.15
    flat_corrections = 0

    while trust_flat > deprecation_threshold:
        trust_flat = flat_demotion(trust_flat, 0.4)
        flat_trajectory.append(trust_flat)
        flat_corrections += 1

    print(f"  Trajectory: {' -> '.join(f'{t:.3f}' for t in flat_trajectory)}")
    print(f"  Corrections to deprecation: {flat_corrections}")

    # --- Backprop ---
    print("\n  --- Backprop ---")
    bdg = BeliefDependencyGraph(cascade_threshold=0.001)
    base = make_embedding()

    # Build the support structure
    nodes = {
        "retrieval_boost": ("Retrieval scoring boosted this memory", 0.7),
        "slot_classifier": ("Slot classifier tagged as employer", 0.75),
        "old_conversation": ("Old conversation mentioned design work", 0.5),
        "design_studio": ("Nick works at a design studio downtown", 0.73),
    }
    for name, (text, conf) in nodes.items():
        bdg.add_belief(create_locus(name, make_embedding(base, 0.15), text, "fact", confidence=conf))

    bdg.add_dependency("retrieval_boost", "design_studio", EdgeType.SUPPORTS, weight=0.8)
    bdg.add_dependency("slot_classifier", "design_studio", EdgeType.SUPPORTS, weight=0.7)
    bdg.add_dependency("old_conversation", "design_studio", EdgeType.SUPPORTS, weight=0.6)

    trust_state = {n: conf for n, (_, conf) in nodes.items()}
    loss_fn = EpistemicLoss()
    vol = DomainVolatility()
    backprop_trajectory = [trust_state["design_studio"]]
    bp_corrections = 0

    print(f"\n  Initial trust state:")
    for n, t in trust_state.items():
        print(f"    {n}: {t:.3f}")

    while trust_state["design_studio"] > deprecation_threshold:
        bp_corrections += 1
        vol.record_correction("employer")
        vol.record_assertion("employer")  # it asserted before being corrected

        lr = vol.get_learning_rate("employer", base_lr=0.1)
        learning_rates = {n: lr for n in trust_state}

        event = CorrectionEvent(
            corrected_node_id="design_studio",
            trust_at_assertion=trust_state["design_studio"],
            times_corrected=bp_corrections,
            correction_source="user",
            time_since_assertion=3600 * bp_corrections,
            domain="employer",
        )
        loss = loss_fn.compute(event)

        result = compute_backward_gradients(
            bdg.graph, "design_studio", loss, learning_rates,
            damping_factor=0.9,
        )

        # Apply direct correction to the wrong belief
        direct_adjustment = -lr * loss
        trust_state["design_studio"] = max(0, trust_state["design_studio"] + direct_adjustment)

        # Apply upstream adjustments
        trust_state = apply_trust_adjustments(trust_state, result.trust_adjustments)

        backprop_trajectory.append(trust_state["design_studio"])

        if bp_corrections > 20:  # safety valve
            break

    print(f"\n  Backprop trajectory: {' -> '.join(f'{t:.3f}' for t in backprop_trajectory)}")
    print(f"  Corrections to deprecation: {bp_corrections}")

    print(f"\n  Final upstream trust:")
    for n in ["retrieval_boost", "slot_classifier", "old_conversation"]:
        orig = nodes[n][1]
        final = trust_state[n]
        print(f"    {n}: {orig:.3f} -> {final:.3f} (delta: {final - orig:+.3f})")

    check(bp_corrections <= flat_corrections,
          f"Backprop ({bp_corrections}) at least as fast as flat demotion ({flat_corrections})")
    # The real advantage: backprop erodes upstream, flat demotion doesn't
    total_upstream_erosion = sum(
        nodes[n][1] - trust_state[n]
        for n in ["retrieval_boost", "slot_classifier", "old_conversation"]
    )
    check(total_upstream_erosion > 0.5,
          f"Backprop erodes upstream (total: {total_upstream_erosion:.3f} > 0.5)")
    check(trust_state["retrieval_boost"] < nodes["retrieval_boost"][1],
          "Retrieval boost trust eroded (upstream learned)")
    check(trust_state["slot_classifier"] < nodes["slot_classifier"][1],
          "Slot classifier trust eroded (upstream learned)")
    check(trust_state["old_conversation"] < nodes["old_conversation"][1],
          "Old conversation trust eroded (upstream learned)")

    return flat_corrections, bp_corrections


# ===================================================================
# Lab 3: Self-Pruning Emergence
# ===================================================================

def lab_3_self_pruning():
    print("\n" + "=" * 70)
    print("LAB 3: Self-Pruning Emergence")
    print("=" * 70)
    print("  Question: Do wrong beliefs die from gradient without explicit rules?")

    bdg = BeliefDependencyGraph(cascade_threshold=0.001)
    base = make_embedding()

    # 20 beliefs: 5 wrong (will be corrected), 15 correct (should be stable)
    wrong_ids = set()
    correct_ids = set()
    initial_trust = {}

    for i in range(20):
        name = f"belief_{i}"
        is_wrong = i < 5
        trust = 0.7 if is_wrong else 0.75
        bdg.add_belief(create_locus(
            name, make_embedding(base, 0.2),
            f"{'Wrong' if is_wrong else 'Correct'} belief {i}",
            "fact", confidence=trust,
        ))
        initial_trust[name] = trust
        if is_wrong:
            wrong_ids.add(name)
        else:
            correct_ids.add(name)

    # Add support edges: each wrong belief supported by 2-3 correct beliefs
    for i in range(5):
        wrong = f"belief_{i}"
        for j in range(5 + i * 2, min(5 + i * 2 + 3, 20)):
            correct = f"belief_{j}"
            bdg.add_dependency(correct, wrong, EdgeType.SUPPORTS, weight=0.6)

    trust_state = dict(initial_trust)
    loss_fn = EpistemicLoss()
    vol = DomainVolatility()
    deprecation = 0.15
    trajectories = {n: [t] for n, t in trust_state.items()}

    # 3 correction cycles per wrong belief
    for cycle in range(3):
        for wrong_id in sorted(wrong_ids):
            if trust_state[wrong_id] <= deprecation:
                continue

            vol.record_correction("test_domain")
            vol.record_assertion("test_domain")
            lr = vol.get_learning_rate("test_domain", base_lr=0.15)
            learning_rates = {n: lr for n in trust_state}

            event = CorrectionEvent(
                corrected_node_id=wrong_id,
                trust_at_assertion=trust_state[wrong_id],
                times_corrected=cycle + 1,
                correction_source="user",
                time_since_assertion=3600,
                domain="test_domain",
            )
            loss = loss_fn.compute(event)

            result = compute_backward_gradients(
                bdg.graph, wrong_id, loss, learning_rates, damping_factor=0.9,
            )

            # Direct correction
            direct = -lr * loss
            trust_state[wrong_id] = max(0, trust_state[wrong_id] + direct)

            # Upstream adjustments
            trust_state = apply_trust_adjustments(trust_state, result.trust_adjustments)

        # Record trajectories
        for n in trust_state:
            trajectories[n].append(trust_state[n])

    print(f"\n  Wrong belief trajectories:")
    for wid in sorted(wrong_ids):
        traj = trajectories[wid]
        print(f"    {wid}: {' -> '.join(f'{t:.3f}' for t in traj)}")

    # Separate correct beliefs into: connected (support wrong beliefs) vs unconnected
    connected_correct = set()
    for i in range(5):
        wrong = f"belief_{i}"
        for j in range(5 + i * 2, min(5 + i * 2 + 3, 20)):
            connected_correct.add(f"belief_{j}")
    unconnected_correct = correct_ids - connected_correct

    connected_deltas = [abs(trust_state[c] - initial_trust[c]) for c in connected_correct]
    unconnected_deltas = [abs(trust_state[c] - initial_trust[c]) for c in unconnected_correct]

    max_connected = max(connected_deltas) if connected_deltas else 0
    max_unconnected = max(unconnected_deltas) if unconnected_deltas else 0

    print(f"\n  Correct belief stability:")
    print(f"    Connected to wrong (expected gradient): max delta = {max_connected:.4f} ({len(connected_correct)} beliefs)")
    print(f"    Unconnected (should be untouched):      max delta = {max_unconnected:.4f} ({len(unconnected_correct)} beliefs)")

    wrong_pruned = sum(1 for wid in wrong_ids if trust_state[wid] <= deprecation)
    print(f"\n  Self-pruning: {wrong_pruned}/{len(wrong_ids)} wrong beliefs below deprecation ({deprecation})")

    check(wrong_pruned >= 3, f"At least 3/5 wrong beliefs self-pruned ({wrong_pruned}/5)")
    check(max_unconnected < 0.01,
          f"Unconnected correct beliefs untouched ({max_unconnected:.4f} < 0.01)")
    check(max_connected > 0,
          f"Connected supporters got gradient (expected behavior, delta={max_connected:.4f})")

    return wrong_pruned, max_unconnected


# ===================================================================
# Lab 4: Domain Volatility
# ===================================================================

def lab_4_domain_volatility():
    print("\n" + "=" * 70)
    print("LAB 4: Domain Volatility")
    print("=" * 70)
    print("  Question: Is volatility measurable, predictive, and does it drive LR?")

    vol = DomainVolatility(recency_halflife=172800)
    now = time.time()

    # Seed histories
    vol.seed_history("name", assertions=50, corrections=0, base_time=now, spread=86400)
    vol.seed_history("employer", assertions=10, corrections=3, base_time=now, spread=86400)
    vol.seed_history("color", assertions=8, corrections=5, base_time=now, spread=86400)

    # Measure volatilities
    v_name = vol.get_volatility("name", now)
    v_employer = vol.get_volatility("employer", now)
    v_color = vol.get_volatility("color", now)

    print(f"\n  Volatility scores:")
    print(f"    name:     {v_name:.4f} (0 corrections / 50 assertions)")
    print(f"    employer: {v_employer:.4f} (3 corrections / 10 assertions)")
    print(f"    color:    {v_color:.4f} (5 corrections / 8 assertions)")

    check(v_name < v_employer < v_color, "Volatility ranks correctly: name < employer < color")
    check(v_name < 0.05, f"Name volatility near zero ({v_name:.4f})")
    check(v_color > 0.3, f"Color volatility high ({v_color:.4f})")

    # Learning rate adaptation
    lr_name = vol.get_learning_rate("name", base_lr=0.1, now=now)
    lr_employer = vol.get_learning_rate("employer", base_lr=0.1, now=now)
    lr_color = vol.get_learning_rate("color", base_lr=0.1, now=now)

    print(f"\n  Learning rates:")
    print(f"    name:     {lr_name:.4f}")
    print(f"    employer: {lr_employer:.4f}")
    print(f"    color:    {lr_color:.4f}")

    check(lr_name < lr_employer < lr_color, "Learning rate scales with volatility")

    # Test: same correction, different domains → different trust impact
    loss_fn = EpistemicLoss()
    event_template = CorrectionEvent(
        corrected_node_id="test",
        trust_at_assertion=0.7,
        times_corrected=1,
        correction_source="user",
        time_since_assertion=3600,
        domain="",
    )

    impact_name = lr_name * loss_fn.compute(event_template)
    impact_color = lr_color * loss_fn.compute(event_template)
    ratio = impact_color / impact_name if impact_name > 0 else float('inf')

    print(f"\n  Trust impact from same correction:")
    print(f"    In 'name' domain:  {impact_name:.4f}")
    print(f"    In 'color' domain: {impact_color:.4f}")
    print(f"    Ratio: {ratio:.2f}x")

    check(ratio > 2.0, f"Volatile domain correction >2x impact ({ratio:.2f}x)")

    return v_name, v_employer, v_color


# ===================================================================
# Lab 5: Bidirectional Convergence
# ===================================================================

def lab_5_convergence():
    print("\n" + "=" * 70)
    print("LAB 5: Bidirectional Convergence")
    print("=" * 70)
    print("  Question: Does forward + backward converge to a unique fixed point?")

    np.random.seed(123)

    def build_graph_and_state(n_nodes=30, n_edges=50):
        bdg = BeliefDependencyGraph(cascade_threshold=0.005)
        base = make_embedding()
        trust = {}
        for i in range(n_nodes):
            name = f"n{i}"
            t = 0.5 + np.random.random() * 0.4  # trust in [0.5, 0.9]
            bdg.add_belief(create_locus(name, make_embedding(base, 0.3), f"Belief {i}", "fact", confidence=t))
            trust[name] = t

        added = 0
        attempts = 0
        while added < n_edges and attempts < n_edges * 5:
            a = f"n{np.random.randint(0, n_nodes)}"
            b = f"n{np.random.randint(0, n_nodes)}"
            if a != b:
                w = 0.3 + np.random.random() * 0.5
                bdg.add_dependency(a, b, EdgeType.SUPPORTS, weight=w)
                added += 1
            attempts += 1

        return bdg, trust

    # Run 1: apply 15 corrections in order A
    bdg1, trust1 = build_graph_and_state()
    np.random.seed(456)
    correction_nodes = [f"n{np.random.randint(0, 30)}" for _ in range(15)]

    loss_fn = EpistemicLoss()
    vol = DomainVolatility()

    trust_history = [dict(trust1)]

    for i, node in enumerate(correction_nodes):
        vol.record_correction("convergence_test")
        vol.record_assertion("convergence_test")
        lr = vol.get_learning_rate("convergence_test", base_lr=0.1)
        learning_rates = {n: lr for n in trust1}

        event = CorrectionEvent(
            corrected_node_id=node,
            trust_at_assertion=trust1[node],
            times_corrected=1,
            correction_source="user",
            time_since_assertion=3600,
            domain="convergence_test",
        )
        loss = loss_fn.compute(event)

        # Backward pass
        bp_result = compute_backward_gradients(
            bdg1.graph, node, loss, learning_rates, damping_factor=0.85,
        )

        # Direct correction
        trust1[node] = max(0, trust1[node] - lr * loss)

        # Apply upstream
        trust1 = apply_trust_adjustments(trust1, bp_result.trust_adjustments)

        # Forward cascade from corrected node
        fwd_result = bdg1.propagate_cascade(node, loss * 0.5, lipschitz_constant=0.85)
        for affected, impact in fwd_result.impacts.items():
            if affected != node and affected in trust1:
                trust1[affected] = max(0, min(1, trust1[affected] - 0.02 * impact))

        trust_history.append(dict(trust1))

    # Measure convergence: delta between successive states
    deltas = []
    for i in range(1, len(trust_history)):
        prev = trust_history[i - 1]
        curr = trust_history[i]
        delta = sum(abs(curr[n] - prev[n]) for n in curr) / len(curr)
        deltas.append(delta)

    print(f"\n  Applied {len(correction_nodes)} corrections")
    print(f"  Mean delta per round (first 5):  {sum(deltas[:5])/5:.6f}")
    print(f"  Mean delta per round (last 5):   {sum(deltas[-5:])/5:.6f}")
    print(f"  Trend: {'converging' if deltas[-1] < deltas[0] else 'DIVERGING'}")

    # Run 2: same corrections in REVERSE order, same graph
    np.random.seed(123)  # same seed for graph construction
    bdg2, trust2 = build_graph_and_state()
    vol2 = DomainVolatility()

    for i, node in enumerate(reversed(correction_nodes)):
        vol2.record_correction("convergence_test")
        vol2.record_assertion("convergence_test")
        lr = vol2.get_learning_rate("convergence_test", base_lr=0.1)
        learning_rates = {n: lr for n in trust2}

        event = CorrectionEvent(
            corrected_node_id=node,
            trust_at_assertion=trust2[node],
            times_corrected=1,
            correction_source="user",
            time_since_assertion=3600,
            domain="convergence_test",
        )
        loss = loss_fn.compute(event)

        bp_result = compute_backward_gradients(
            bdg2.graph, node, loss, learning_rates, damping_factor=0.85,
        )
        trust2[node] = max(0, trust2[node] - lr * loss)
        trust2 = apply_trust_adjustments(trust2, bp_result.trust_adjustments)

        fwd_result = bdg2.propagate_cascade(node, loss * 0.5, lipschitz_constant=0.85)
        for affected, impact in fwd_result.impacts.items():
            if affected != node and affected in trust2:
                trust2[affected] = max(0, min(1, trust2[affected] - 0.02 * impact))

    # Compare final states
    order_diff = sum(abs(trust1[n] - trust2[n]) for n in trust1) / len(trust1)
    print(f"\n  Order independence:")
    print(f"    Mean trust difference (order A vs reversed): {order_diff:.6f}")

    # Contraction check: ratio of successive deltas should be < 1
    # If the system is contracting, each correction produces less change than the previous
    if len(deltas) >= 4:
        early_avg = sum(deltas[:3]) / 3
        late_avg = sum(deltas[-3:]) / 3
        contraction = late_avg / early_avg if early_avg > 0 else 0
    else:
        contraction = 0
    print(f"\n  Contraction ratio (late/early deltas): {contraction:.4f} (< 1 = contracting)")

    check(deltas[-1] < deltas[0], "System converges (later deltas smaller than early)")
    check(order_diff < 0.05, f"Order-independent within tolerance ({order_diff:.6f} < 0.05)")
    check(contraction < 1.0, f"Contraction constant < 1 ({contraction:.4f})")

    return deltas, order_diff, contraction


# ===================================================================
# Lab 6: Reflexive Self-Model
# ===================================================================

def lab_6_self_model():
    print("\n" + "=" * 70)
    print("LAB 6: Reflexive Self-Model")
    print("=" * 70)
    print("  Question: Do self-beliefs adjust from the same backward pass?")

    bdg = BeliefDependencyGraph(cascade_threshold=0.001)
    base = make_embedding()

    # World beliefs
    world_nodes = {
        "design_studio": ("Nick works at a design studio", 0.73),
        "name_nick": ("User's name is Nick", 0.95),
        "color_orange": ("Favorite color is orange", 0.90),
    }

    # Self-model beliefs
    self_nodes = {
        "self_reliable_employment": ("I am reliable on employment facts", 0.80),
        "self_reliable_identity": ("I am reliable on identity facts", 0.80),
        "self_confidence_accuracy": ("My confidence tracks my accuracy", 0.70),
    }

    all_nodes = {**world_nodes, **self_nodes}
    for name, (text, conf) in all_nodes.items():
        mtype = "belief" if name.startswith("self_") else "fact"
        bdg.add_belief(create_locus(name, make_embedding(base, 0.15), text, mtype, confidence=conf))

    # Wiring: self-model beliefs SUPPORT the claims they're about
    bdg.add_dependency("self_reliable_employment", "design_studio", EdgeType.SUPPORTS, weight=0.7)
    bdg.add_dependency("self_reliable_identity", "name_nick", EdgeType.SUPPORTS, weight=0.7)
    bdg.add_dependency("self_confidence_accuracy", "design_studio", EdgeType.SUPPORTS, weight=0.5)

    trust_state = {n: conf for n, (_, conf) in all_nodes.items()}
    loss_fn = EpistemicLoss()
    vol = DomainVolatility()

    print(f"\n  Initial self-model trust:")
    for n in sorted(self_nodes):
        print(f"    {n}: {trust_state[n]:.3f}")

    # 3 employment corrections
    for cycle in range(3):
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

        # Direct correction
        trust_state["design_studio"] = max(0, trust_state["design_studio"] - lr * loss)
        trust_state = apply_trust_adjustments(trust_state, result.trust_adjustments)

    print(f"\n  After 3 employment corrections:")
    print(f"\n  Self-model trust changes:")
    for n in sorted(self_nodes):
        orig = self_nodes[n][1]
        final = trust_state[n]
        delta = final - orig
        print(f"    {n}: {orig:.3f} -> {final:.3f} (delta: {delta:+.4f})")

    print(f"\n  World belief trust changes:")
    for n in sorted(world_nodes):
        orig = world_nodes[n][1]
        final = trust_state[n]
        delta = final - orig
        print(f"    {n}: {orig:.3f} -> {final:.3f} (delta: {delta:+.4f})")

    # Checks
    empl_delta = abs(trust_state["self_reliable_employment"] - self_nodes["self_reliable_employment"][1])
    ident_delta = abs(trust_state["self_reliable_identity"] - self_nodes["self_reliable_identity"][1])
    conf_delta = abs(trust_state["self_confidence_accuracy"] - self_nodes["self_confidence_accuracy"][1])
    name_delta = abs(trust_state["name_nick"] - world_nodes["name_nick"][1])
    color_delta = abs(trust_state["color_orange"] - world_nodes["color_orange"][1])

    check(empl_delta > 0.01,
          f"Employment self-model adjusted ({empl_delta:.4f})")
    check(ident_delta < 0.001,
          f"Identity self-model untouched ({ident_delta:.4f})")
    check(conf_delta > 0.001,
          f"Confidence-accuracy self-model adjusted ({conf_delta:.4f})")
    check(empl_delta > ident_delta,
          f"Employment self-model changed more than identity ({empl_delta:.4f} > {ident_delta:.4f})")
    check(name_delta < 0.001,
          f"Name belief untouched ({name_delta:.4f})")
    check(color_delta < 0.001,
          f"Color belief untouched ({color_delta:.4f})")

    # The personality shift: system is now less confident about employment
    print(f"\n  Personality shift:")
    print(f"    Employment reliability: {self_nodes['self_reliable_employment'][1]:.3f} -> {trust_state['self_reliable_employment']:.3f}")
    print(f"    Identity reliability:   {self_nodes['self_reliable_identity'][1]:.3f} -> {trust_state['self_reliable_identity']:.3f}")
    print(f"    This IS domain-specific caution — earned, not programmed.")

    return empl_delta, ident_delta


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# BELIEF BACKPROPAGATION — EXPERIMENT SUITE")
    print("# Papers: papers/belief_backpropagation/")
    print("#" * 70)

    lab_1_backward_mechanics()
    lab_2_design_studio()
    lab_3_self_pruning()
    lab_4_domain_volatility()
    lab_5_convergence()
    lab_6_self_model()

    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed, {PASS_COUNT + FAIL_COUNT} total")
    print("=" * 70)

    if FAIL_COUNT == 0:
        print("ALL LABS PASSED")
    else:
        print(f"{FAIL_COUNT} FAILURES — review above")

    sys.exit(0 if FAIL_COUNT == 0 else 1)
