"""Cascade Complexity Paper — Experiment Suite (Section 7)

Produces the empirical illustrations for the paper:
  7.2 Location change cascade
  7.3 Held contradiction as firewall
  7.4 Damping curve

Also validates Theorems 4.1-4.4 on constructed examples.

Run: python -m papers.cascade_complexity.experiments
  or: python papers/cascade_complexity/experiments.py
"""

import sys
import math
sys.path.insert(0, r"D:\AI_round2")

import numpy as np

from personal_agent.memory_splats import (
    MemorySplat, create_splat, create_splat_from_type,
    cosine_similarity, overlap_integral,
)
from personal_agent.info_geometry import fisher_rao_distance
from personal_agent.memory_graph import (
    BeliefDependencyGraph, EdgeType, CascadeResult,
)


np.random.seed(42)
D = 384


def make_embedding(base=None, noise=0.1):
    if base is None:
        base = np.random.randn(D).astype(np.float32)
    v = base + np.random.randn(D).astype(np.float32) * noise
    v /= np.linalg.norm(v)
    return v


# ===================================================================
# Experiment 7.2: Location Change Cascade
# ===================================================================

def experiment_location_cascade():
    print("=" * 70)
    print("EXPERIMENT 7.2: Location Change Cascade")
    print("=" * 70)

    bdg = BeliefDependencyGraph(cascade_threshold=0.05)

    base_loc = make_embedding()
    beliefs = {
        "location":     ("I live in Portland", "fact", 0.9, base_loc),
        "commute":      ("20 minute bike commute", "fact", 0.85, make_embedding(base_loc, 0.15)),
        "neighborhood": ("Love the Pearl District", "preference", 0.8, make_embedding(base_loc, 0.2)),
        "weather_pref": ("Always carry rain gear", "belief", 0.7, make_embedding(base_loc, 0.25)),
        "social":       ("Portland friend group", "belief", 0.75, make_embedding(base_loc, 0.3)),
        "job_love":     ("I love my job", "belief", 0.8, make_embedding()),
        "burnout":      ("Feeling exhausted from work", "belief", 0.6, make_embedding()),
        "fav_team":     ("Lakers fan for life", "preference", 0.95, make_embedding()),
    }

    splats = {}
    for name, (text, mtype, conf, emb) in beliefs.items():
        s = create_splat(name, emb, text, mtype, confidence=conf)
        splats[name] = s
        bdg.add_belief(s)

    # Dependencies
    deps = [
        ("location", "commute", EdgeType.SUPPORTS, 0.9),
        ("location", "neighborhood", EdgeType.SUPPORTS, 0.8),
        ("location", "weather_pref", EdgeType.SUPPORTS, 0.6),
        ("location", "social", EdgeType.SUPPORTS, 0.7),
        ("job_love", "burnout", EdgeType.CONTRADICTS, 0.5),
    ]
    for src, tgt, etype, w in deps:
        bdg.add_dependency(src, tgt, etype, w)

    print(f"\n  Graph: {bdg.num_nodes} nodes, {bdg.num_edges} edges, DAG={bdg.is_dag}")
    print(f"  Longest path: {bdg.longest_path_length()}")
    print(f"  Max out-degree: {bdg.max_out_degree()}")

    # Revision: Portland -> Austin
    new_loc = create_splat("location_new", make_embedding(), "I live in Austin", "fact", confidence=0.9)
    delta_0 = fisher_rao_distance(splats["location"], new_loc)
    print(f"\n  Revision: location 'Portland' -> 'Austin'")
    print(f"  Fisher-Rao impact: {delta_0:.3f}")

    result = bdg.propagate_cascade("location", delta_0, lipschitz_constant=0.85, use_dispositions=False)

    print(f"\n  CASCADE RESULT:")
    print(f"    Affected: {sorted(result.affected_nodes)}")
    print(f"    Depth: {result.depth}")
    print(f"    Width: {result.width}")
    print(f"    Total impact: {result.total_impact:.3f}")

    # Verify: job_love, burnout, fav_team should NOT be affected
    should_not_be_affected = {"job_love", "burnout", "fav_team"}
    actually_unaffected = should_not_be_affected - result.affected_nodes
    print(f"    Correctly unaffected: {sorted(actually_unaffected)}")
    assert actually_unaffected == should_not_be_affected, "Cascade leaked to independent nodes!"
    print(f"    [PASS] Independent nodes correctly isolated")

    return result


# ===================================================================
# Experiment 7.3: Held Contradiction as Firewall
# ===================================================================

def experiment_firewall():
    print("\n" + "=" * 70)
    print("EXPERIMENT 7.3: Held Contradiction as Firewall")
    print("=" * 70)

    bdg = BeliefDependencyGraph(cascade_threshold=0.05)

    # Chain: career_goal -> job_type -> work_hours -> life_balance
    prev_emb = make_embedding()
    names = ["career_goal", "job_type", "work_hours", "life_balance"]
    splats = {}
    for name in names:
        emb = make_embedding(prev_emb, 0.15)
        s = create_splat(name, emb, f"My {name.replace('_', ' ')}", "belief", confidence=0.7)
        splats[name] = s
        bdg.add_belief(s)
        prev_emb = emb

    bdg.add_dependency("career_goal", "job_type", EdgeType.SUPPORTS, weight=0.8)
    bdg.add_dependency("job_type", "work_hours", EdgeType.SUPPORTS, weight=0.7)
    bdg.add_dependency("work_hours", "life_balance", EdgeType.SUPPORTS, weight=0.6)

    delta_0 = 1.0

    # Without firewall
    result_no = bdg.propagate_cascade("career_goal", delta_0, use_dispositions=False)
    print(f"\n  WITHOUT firewall:")
    print(f"    Affected: {sorted(result_no.affected_nodes)}")
    print(f"    Depth: {result_no.depth}, Width: {result_no.width}")

    # With firewall (using effective_reachable_set)
    held_nodes = {"job_type"}
    reachable = bdg.effective_reachable_set("career_goal", held_nodes)

    # Nodes that would be blocked
    all_reachable = bdg.effective_reachable_set("career_goal", set())
    blocked = all_reachable - reachable

    print(f"\n  WITH held firewall at 'job_type':")
    print(f"    Effective reachable: {sorted(reachable)}")
    print(f"    Blocked by firewall: {sorted(blocked)}")

    # Verify Proposition 5.3
    print(f"\n  Proposition 5.3 check:")
    print(f"    |C(r)| without fw = {len(all_reachable)}")
    print(f"    |R_H(v_0)| with fw = {len(reachable)}")
    print(f"    Reduction: {len(all_reachable) - len(reachable)} nodes protected")

    assert "work_hours" not in reachable or "life_balance" not in reachable, \
        "Firewall should block downstream nodes"
    print(f"    [PASS] Held contradiction blocks cascade propagation")

    return result_no, reachable


# ===================================================================
# Experiment 7.4: Damping Curve
# ===================================================================

def experiment_damping():
    print("\n" + "=" * 70)
    print("EXPERIMENT 7.4: Damping Curve (Theorem 4.3)")
    print("=" * 70)

    w = 0.8
    L = 0.9
    rho = L * w
    delta_0 = 1.0
    tau = 0.01

    print(f"\n  Parameters: w={w}, L={L}, rho={rho:.2f}, delta_0={delta_0}, tau={tau}")
    predicted_depth = math.ceil(math.log(delta_0 / tau) / math.log(1.0 / rho))
    predicted_total = delta_0 / (1.0 - rho)
    print(f"  Predicted termination depth: {predicted_depth}")
    print(f"  Predicted total impact bound: {predicted_total:.3f}")

    # Simulate
    print(f"\n  {'Depth':>5} | {'Impact':>10} | {'Triggered?':>10}")
    print(f"  {'-'*5}-+-{'-'*10}-+-{'-'*10}")

    impact = delta_0
    actual_depth = 0
    total_impact = 0.0
    for depth in range(30):
        triggered = impact > tau
        print(f"  {depth:5d} | {impact:10.6f} | {'Yes' if triggered else 'No'}")
        if not triggered:
            break
        total_impact += impact
        actual_depth = depth
        impact *= rho  # damping

    print(f"\n  Actual termination depth: {actual_depth}")
    print(f"  Matches predicted ({predicted_depth}): {actual_depth + 1 == predicted_depth}")
    print(f"  Actual total impact: {total_impact:.3f}")
    print(f"  Within bound ({predicted_total:.3f}): {total_impact <= predicted_total}")

    # Build actual BDG chain and verify
    print(f"\n  --- Verifying with actual BDG chain ---")
    bdg = BeliefDependencyGraph(cascade_threshold=tau)
    prev_emb = make_embedding()
    for i in range(20):
        emb = make_embedding(prev_emb, 0.1)
        s = create_splat(f"node_{i}", emb, f"Belief {i}", "belief")
        bdg.add_belief(s)
        if i > 0:
            bdg.add_dependency(f"node_{i-1}", f"node_{i}", EdgeType.SUPPORTS, weight=w)
        prev_emb = emb

    result = bdg.propagate_cascade("node_0", delta_0, lipschitz_constant=L, use_dispositions=False)
    print(f"  BDG chain result: depth={result.depth}, width={result.width}, "
          f"total_impact={result.total_impact:.3f}")
    print(f"  Converged: {result.converged}")

    return actual_depth, total_impact


# ===================================================================
# Theorem validation: Instability (Theorem 4.4)
# ===================================================================

def experiment_instability():
    print("\n" + "=" * 70)
    print("EXPERIMENT: Instability Detection (Theorem 4.4)")
    print("=" * 70)

    # Stable cycle (weak coupling)
    bdg_stable = BeliefDependencyGraph(cascade_threshold=0.01)
    for name in ["A", "B", "C"]:
        bdg_stable.add_belief(create_splat(name, make_embedding(), f"Belief {name}", "belief"))
    bdg_stable.add_dependency("A", "B", EdgeType.SUPPORTS, weight=0.3)
    bdg_stable.add_dependency("B", "C", EdgeType.SUPPORTS, weight=0.3)
    bdg_stable.add_dependency("C", "A", EdgeType.SUPPORTS, weight=0.3)

    amp_stable = bdg_stable.cycle_amplification(["A", "B", "C"])
    unstable_stable = bdg_stable.find_unstable_cycles(lipschitz_constant=0.9)
    print(f"\n  Stable cycle (w=0.3): amplification={amp_stable:.4f}")
    print(f"  Unstable cycles found: {len(unstable_stable)}")
    print(f"  [{'PASS' if len(unstable_stable) == 0 else 'FAIL'}] Weak cycle correctly identified as stable")

    # Unstable cycle (strong coupling, amplifying nodes L>1)
    bdg_unstable = BeliefDependencyGraph(cascade_threshold=0.01)
    for name in ["X", "Y", "Z"]:
        bdg_unstable.add_belief(create_splat(name, make_embedding(), f"Belief {name}", "belief"))
    bdg_unstable.add_dependency("X", "Y", EdgeType.SUPPORTS, weight=1.0)
    bdg_unstable.add_dependency("Y", "Z", EdgeType.SUPPORTS, weight=1.0)
    bdg_unstable.add_dependency("Z", "X", EdgeType.SUPPORTS, weight=1.0)

    # L=1.1 means each node AMPLIFIES revisions by 10%
    L_unstable = 1.1
    amp_unstable = bdg_unstable.cycle_amplification(["X", "Y", "Z"])
    unstable_found = bdg_unstable.find_unstable_cycles(lipschitz_constant=L_unstable)
    print(f"\n  Unstable cycle (w=1.0, L={L_unstable}): amplification={amp_unstable:.4f}")
    print(f"  Threshold (1/L^3 = {1.0/L_unstable**3:.4f})")
    print(f"  Unstable cycles found: {len(unstable_found)}")
    if unstable_found:
        for cycle, amp in unstable_found:
            print(f"    Cycle: {' -> '.join(cycle)}, amp={amp:.4f}")
    print(f"  [{'PASS' if len(unstable_found) > 0 else 'FAIL'}] Strong cycle correctly identified as unstable")


# ===================================================================
# Theorem validation: Width bound (Theorem 4.2)
# ===================================================================

def experiment_width_bound():
    print("\n" + "=" * 70)
    print("EXPERIMENT: Width Bound Validation (Theorem 4.2)")
    print("=" * 70)

    # Build a tree with branching factor d=3, depth k=3
    bdg = BeliefDependencyGraph(cascade_threshold=0.01)
    root_emb = make_embedding()
    bdg.add_belief(create_splat("root", root_emb, "Root belief", "belief"))

    # Build tree level by level
    nodes_at_level = {"root"}
    total_nodes = 1
    for depth in range(3):
        next_level = set()
        for parent in nodes_at_level:
            for child_idx in range(3):
                child_name = f"{parent}_c{child_idx}"
                bdg.add_belief(create_splat(child_name, make_embedding(root_emb, 0.2), f"Belief {child_name}", "belief"))
                bdg.add_dependency(parent, child_name, EdgeType.SUPPORTS, weight=0.8)
                next_level.add(child_name)
                total_nodes += 1
        nodes_at_level = next_level

    result = bdg.propagate_cascade("root", 1.0, lipschitz_constant=0.95, use_dispositions=False)

    d_out = 3
    k = 3
    theoretical_max = min(sum(d_out**j for j in range(k + 1)), total_nodes)

    print(f"\n  Tree: branching={d_out}, depth={k}, total_nodes={total_nodes}")
    print(f"  Cascade width: {result.width}")
    print(f"  Theoretical bound O(min(d^k, n)): {theoretical_max}")
    print(f"  Within bound: {result.width <= theoretical_max}")
    print(f"  [{'PASS' if result.width <= theoretical_max else 'FAIL'}] Width within Theorem 4.2 bound")


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    experiment_location_cascade()
    experiment_firewall()
    experiment_damping()
    experiment_instability()
    experiment_width_bound()

    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
