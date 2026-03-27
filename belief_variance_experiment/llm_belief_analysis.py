"""LLM Belief Analysis Pipeline
=================================
Takes the splats produced by variance_to_splats.py and runs them through
all 9 research modules. This is the bridge between the experiment and
the theory.

What each module tells us about LLM beliefs:

1. Disposition Classifier — Are the model's contradictions resolvable,
   held, evolving, or contextual?
2. Memory Graph — What's the dependency structure between beliefs?
3. Temporal Governance — How do beliefs decay with temperature (as proxy for time)?
4. Memory Splats — Already done by variance_to_splats.py
5. Predictive Contradiction — Can we predict which beliefs will split
   at higher temperatures from their lower-temperature trajectories?
6. Belief Topology — What's the topological structure of the model's
   belief space? Are there holes (avoidance patterns)?
7. Belief/Speech Separation — N/A for this experiment (no speech layer)
8. Information Geometry — Fisher distance between belief clusters
9. Active Inference — What should the model be ASKED to reduce its
   own uncertainty? (Generates questions the model should ask itself)
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

# Add paths
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.memory_splats import (
    MemorySplat, bhattacharyya_distance, overlap_integral,
    kl_divergence, cosine_similarity as splat_cosine,
)
from personal_agent.info_geometry import (
    fisher_rao_distance, fisher_mean_component, fisher_cov_component,
)
from personal_agent.predictive_contradiction import (
    extract_trajectory, analyze_convergence, Urgency,
)
from personal_agent.disposition_classifier import (
    Disposition, classify_contradiction, DispositionResult,
    extract_signals,
)

from variance_to_splats import (
    load_embeddings, load_raw_metadata,
    build_trajectory, BeliefTrajectory,
    find_held_contradictions, find_cross_prompt_contradictions,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
ANALYSIS_DIR = BASE_DIR / "results" / "belief_analysis"
TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]


# ---------------------------------------------------------------------------
# Module 1: Disposition Classification on LLM beliefs
# ---------------------------------------------------------------------------
def analyze_dispositions(trajectories: dict[str, BeliefTrajectory]) -> dict:
    """Classify held contradictions by disposition.

    For multi-modal prompts, classify the contradiction between
    the two largest clusters.
    """
    results = []

    for pid, traj in trajectories.items():
        if not traj.is_multi_modal:
            continue

        # Get clusters at T=1.0
        if 1.0 not in traj.splats_by_temp:
            continue

        cluster_splats = traj.splats_by_temp[1.0]
        if len(cluster_splats) < 2:
            continue

        # Classify the contradiction between the two largest clusters
        sorted_clusters = sorted(cluster_splats, key=lambda s: s.n_responses, reverse=True)
        a = sorted_clusters[0]
        b = sorted_clusters[1]

        # Use text-based classification
        signals = extract_signals(a.splat.text, b.splat.text)
        signals.domain = traj.domain
        result = classify_contradiction(a.splat.text, b.splat.text, signals)

        results.append({
            "prompt_id": pid,
            "domain": traj.domain,
            "disposition": result.disposition.value,
            "confidence": result.confidence,
            "explanation": result.explanation,
            "cluster_sizes": [a.n_responses, b.n_responses],
        })

    # Summary
    disp_counts = defaultdict(int)
    for r in results:
        disp_counts[r["disposition"]] += 1

    return {
        "total_classified": len(results),
        "disposition_counts": dict(disp_counts),
        "details": results,
    }


# ---------------------------------------------------------------------------
# Module 5: Predictive Contradiction across temperatures
# ---------------------------------------------------------------------------
def analyze_predictive(trajectories: dict[str, BeliefTrajectory]) -> dict:
    """Test predictive contradiction detection on LLM belief trajectories.

    Key question: can we predict at T=0.7 which prompts will become
    multi-modal at T=1.0 or T=1.5?

    This validates the "40% advance warning" finding on LLM data.
    """
    results = []
    correct_predictions = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0

    for pid, traj in trajectories.items():
        if len(traj.primary_splats) < 3:
            continue

        # Check trajectory at T=0.7 (index 2 if we have all 5 temps)
        # Predict whether it will split at T=1.0+
        mid_splat = None
        for bs in (traj.splats_by_temp.get(0.7, []) or []):
            mid_splat = bs
            break

        # Ground truth: does it become multi-modal at T>=1.0?
        becomes_multi = False
        for temp in [1.0, 1.5]:
            if temp in traj.splats_by_temp:
                if any(s.n_clusters >= 2 for s in traj.splats_by_temp[temp]):
                    becomes_multi = True
                    break

        # Extract trajectory features from primary splats up to T=0.7
        early_splats = [s for s in traj.primary_splats if s.created_at <= 0.7]
        if len(early_splats) < 2:
            continue

        # Check if the trajectory is widening (uncertainty growing)
        state = extract_trajectory(early_splats[-1])
        predicted_split = False
        if state:
            predicted_split = state.is_widening and state.covariance_velocity > 0.001

        # Score
        if predicted_split and becomes_multi:
            correct_predictions += 1
            outcome = "true_positive"
        elif predicted_split and not becomes_multi:
            false_positives += 1
            outcome = "false_positive"
        elif not predicted_split and becomes_multi:
            false_negatives += 1
            outcome = "false_negative"
        else:
            true_negatives += 1
            outcome = "true_negative"

        results.append({
            "prompt_id": pid,
            "domain": traj.domain,
            "predicted_split": predicted_split,
            "actual_multi_modal": becomes_multi,
            "outcome": outcome,
            "widening": state.is_widening if state else None,
            "cov_velocity": state.covariance_velocity if state else None,
            "susceptibility": traj.susceptibility,
        })

    total = correct_predictions + false_positives + false_negatives + true_negatives
    precision = correct_predictions / (correct_predictions + false_positives) if (correct_predictions + false_positives) > 0 else 0
    recall = correct_predictions / (correct_predictions + false_negatives) if (correct_predictions + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_prompts": total,
        "true_positives": correct_predictions,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Module 8: Information Geometry analysis
# ---------------------------------------------------------------------------
def analyze_information_geometry(trajectories: dict[str, BeliefTrajectory]) -> dict:
    """Apply Fisher-Rao distance analysis to LLM beliefs.

    Key questions:
    - Does Fisher distance discriminate better than cosine for LLM beliefs?
    - Is the 3.16x factor from synthetic data replicated on real LLM data?
    - Which dimensions carry the most Fisher information per domain?
    """
    comparisons = []

    # Compare all pairs within the same domain
    by_domain = defaultdict(list)
    for pid, traj in trajectories.items():
        if traj.primary_splats:
            by_domain[traj.domain].append((pid, traj.primary_splats[-1]))  # T=max splat

    for domain, entries in by_domain.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                pid_a, splat_a = entries[i]
                pid_b, splat_b = entries[j]

                fisher = fisher_rao_distance(splat_a, splat_b)
                cos = splat_cosine(splat_a, splat_b)
                cos_dist = 1.0 - cos

                mean_term = fisher_mean_component(splat_a, splat_b)
                cov_term = fisher_cov_component(splat_a, splat_b)

                comparisons.append({
                    "prompt_a": pid_a,
                    "prompt_b": pid_b,
                    "domain": domain,
                    "fisher_distance": fisher,
                    "cosine_distance": cos_dist,
                    "fisher_cosine_ratio": fisher / (cos_dist + 1e-10),
                    "mean_term": mean_term,
                    "cov_term": cov_term,
                    "cov_fraction": cov_term / (fisher + 1e-10),
                })

    # Aggregate by domain
    domain_stats = {}
    for domain in by_domain:
        domain_comps = [c for c in comparisons if c["domain"] == domain]
        if domain_comps:
            ratios = [c["fisher_cosine_ratio"] for c in domain_comps]
            cov_fracs = [c["cov_fraction"] for c in domain_comps]
            domain_stats[domain] = {
                "n_pairs": len(domain_comps),
                "mean_fisher_cosine_ratio": float(np.mean(ratios)),
                "std_fisher_cosine_ratio": float(np.std(ratios)),
                "mean_cov_fraction": float(np.mean(cov_fracs)),
                "std_cov_fraction": float(np.std(cov_fracs)),
            }

    return {
        "total_pairs": len(comparisons),
        "domain_stats": domain_stats,
        "top_fisher_pairs": sorted(comparisons, key=lambda c: c["fisher_distance"], reverse=True)[:20],
        "top_cov_fraction_pairs": sorted(comparisons, key=lambda c: c["cov_fraction"], reverse=True)[:20],
    }


# ---------------------------------------------------------------------------
# Module 6: Topology (requires ripser)
# ---------------------------------------------------------------------------
def analyze_topology(trajectories: dict[str, BeliefTrajectory]) -> dict:
    """Run persistent homology on LLM belief space.

    Key questions:
    - Are there H1 features (holes/loops) in the model's belief space?
    - Do they correspond to avoidance patterns or held contradictions?
    - Does the topology differ between domains?
    """
    try:
        from ripser import ripser
    except ImportError:
        return {"error": "ripser not installed. pip install ripser"}

    results_by_domain = {}

    # Group final splats by domain
    by_domain = defaultdict(list)
    for pid, traj in trajectories.items():
        if traj.primary_splats:
            by_domain[traj.domain].append(traj.primary_splats[-1])

    for domain, splats in by_domain.items():
        if len(splats) < 5:
            continue

        # Build distance matrix from splat centers
        n = len(splats)
        centers = np.array([s.mu for s in splats])
        # Cosine distance
        from sklearn.metrics.pairwise import cosine_distances
        D = cosine_distances(centers)

        # Run ripser
        rips = ripser(D, maxdim=1, distance_matrix=True)
        dgms = rips['dgms']

        # H0: connected components
        h0 = dgms[0]
        h0_persistence = h0[:, 1] - h0[:, 0]
        h0_persistence = h0_persistence[np.isfinite(h0_persistence)]

        # H1: loops/holes
        h1 = dgms[1] if len(dgms) > 1 else np.array([]).reshape(0, 2)
        h1_persistence = h1[:, 1] - h1[:, 0] if len(h1) > 0 else np.array([])

        results_by_domain[domain] = {
            "n_splats": n,
            "h0_features": len(h0),
            "h0_max_persistence": float(np.max(h0_persistence)) if len(h0_persistence) > 0 else 0,
            "h1_features": len(h1),
            "h1_max_persistence": float(np.max(h1_persistence)) if len(h1_persistence) > 0 else 0,
            "h1_mean_persistence": float(np.mean(h1_persistence)) if len(h1_persistence) > 0 else 0,
        }

    return {
        "domains_analyzed": len(results_by_domain),
        "results": results_by_domain,
    }


# ---------------------------------------------------------------------------
# Module 9: Active Inference — what should the model ask itself?
# ---------------------------------------------------------------------------
def analyze_active_inference(trajectories: dict[str, BeliefTrajectory]) -> dict:
    """Generate clarification questions the model should ask itself.

    For each uncertain or contradictory belief, generate a question
    that would reduce the model's free energy if answered.
    """
    try:
        from active_inference import (
            scan_for_uncertainty, generate_inquiries,
            UncertaintyType,
        )
    except ImportError:
        # Fallback: generate questions heuristically
        pass

    questions = []

    for pid, traj in trajectories.items():
        # High susceptibility = the model should ask itself about this
        if traj.susceptibility > 0.5:
            questions.append({
                "prompt_id": pid,
                "domain": traj.domain,
                "reason": "high_susceptibility",
                "urgency": "HIGH",
                "question": f"Why does my response to '{pid}' vary so much? "
                           f"Is there genuine ambiguity or am I confused?",
                "susceptibility": traj.susceptibility,
            })

        # Multi-modal = held contradiction, should examine
        if traj.is_multi_modal:
            questions.append({
                "prompt_id": pid,
                "domain": traj.domain,
                "reason": "held_contradiction",
                "urgency": "MEDIUM",
                "question": f"I give {traj.max_clusters} distinct answers to '{pid}'. "
                           f"Are both positions defensible, or should I resolve this?",
                "max_clusters": traj.max_clusters,
            })

        # Phase transition = something structural changes
        if traj.phase_transition_temp is not None:
            questions.append({
                "prompt_id": pid,
                "domain": traj.domain,
                "reason": "phase_transition",
                "urgency": "HIGH",
                "question": f"My belief about '{pid}' fundamentally changes at "
                           f"T={traj.phase_transition_temp}. What's the unstable "
                           f"assumption that breaks under perturbation?",
                "phase_temp": traj.phase_transition_temp,
            })

    # Sort by urgency
    urgency_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    questions.sort(key=lambda q: urgency_order.get(q["urgency"], 3))

    return {
        "total_questions": len(questions),
        "by_reason": {
            reason: len([q for q in questions if q["reason"] == reason])
            for reason in set(q["reason"] for q in questions)
        },
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------
def run_full_analysis(save: bool = True) -> dict:
    """Run all applicable modules on LLM belief data."""
    print("=" * 60)
    print("  LLM BELIEF ANALYSIS — ALL MODULES")
    print("=" * 60)

    # Load data
    print("\n[1/6] Loading embeddings and building trajectories...")
    embeddings = load_embeddings()
    metadata = load_raw_metadata()

    if not embeddings:
        print("No embeddings found. Run experiment + analyze.py first.")
        print("Or use: python variance_to_splats.py --synthetic")
        return {}

    trajectories: dict[str, BeliefTrajectory] = {}
    for pid, temp_embeddings in embeddings.items():
        domain = metadata.get(pid, {}).get("domain", "unknown")
        traj = build_trajectory(pid, temp_embeddings, domain)
        trajectories[pid] = traj

    print(f"  {len(trajectories)} belief trajectories loaded")

    # Module 1: Disposition classification
    print("\n[2/6] Module 1 — Disposition Classification...")
    dispositions = analyze_dispositions(trajectories)
    print(f"  {dispositions['total_classified']} contradictions classified")
    for disp, count in dispositions['disposition_counts'].items():
        print(f"    {disp}: {count}")

    # Module 5: Predictive contradiction
    print("\n[3/6] Module 5 — Predictive Contradiction...")
    predictive = analyze_predictive(trajectories)
    print(f"  Precision: {predictive['precision']:.3f}")
    print(f"  Recall: {predictive['recall']:.3f}")
    print(f"  F1: {predictive['f1']:.3f}")
    print(f"  (TP={predictive['true_positives']}, FP={predictive['false_positives']}, "
          f"FN={predictive['false_negatives']}, TN={predictive['true_negatives']})")

    # Module 8: Information geometry
    print("\n[4/6] Module 8 — Information Geometry...")
    geometry = analyze_information_geometry(trajectories)
    print(f"  {geometry['total_pairs']} pairs compared")
    for domain, stats in geometry['domain_stats'].items():
        print(f"    {domain}: Fisher/cosine ratio = "
              f"{stats['mean_fisher_cosine_ratio']:.2f}x, "
              f"cov fraction = {stats['mean_cov_fraction']:.3f}")

    # Module 6: Topology
    print("\n[5/6] Module 6 — Belief Topology...")
    topology = analyze_topology(trajectories)
    if "error" in topology:
        print(f"  {topology['error']}")
    else:
        for domain, stats in topology.get('results', {}).items():
            print(f"    {domain}: H0={stats['h0_features']} components, "
                  f"H1={stats['h1_features']} holes "
                  f"(max persistence={stats['h1_max_persistence']:.4f})")

    # Module 9: Active inference
    print("\n[6/6] Module 9 — Active Inference (Self-Questions)...")
    inference = analyze_active_inference(trajectories)
    print(f"  {inference['total_questions']} questions generated")
    for reason, count in inference['by_reason'].items():
        print(f"    {reason}: {count}")

    if inference['questions']:
        print(f"\n  Top 5 questions the model should ask itself:")
        for q in inference['questions'][:5]:
            print(f"    [{q['urgency']}] {q['question']}")

    # Compile results
    all_results = {
        "n_trajectories": len(trajectories),
        "dispositions": dispositions,
        "predictive": predictive,
        "information_geometry": geometry,
        "topology": topology,
        "active_inference": inference,
        "held_contradictions": find_held_contradictions(trajectories),
    }

    if save:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ANALYSIS_DIR / "full_analysis.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\nResults saved to {out_path}")

    print("\n" + "=" * 60)
    print("  ANALYSIS COMPLETE")
    print("=" * 60)

    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM Belief Analysis — Full Module Suite")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    args = parser.parse_args()

    run_full_analysis(save=not args.no_save)
