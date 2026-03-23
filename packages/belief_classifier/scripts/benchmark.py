"""Benchmark classifier decisions vs a "preserve everything" baseline.

Usage:
    python -m scripts.benchmark --models models/ --test-data data/exported_pairs.json
    python -m scripts.benchmark --models models/ --synthetic 200
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from belief_classifier.classifier import ContradictionResolver
from belief_classifier.exporter import LedgerExporter
from belief_classifier.labeler import AutoLabeler
from belief_classifier.types import BeliefType, ContradictionPair, PolicyAction


def _load_data(
    path: str,
) -> List[Tuple[ContradictionPair, BeliefType, PolicyAction]]:
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    labeler = AutoLabeler()
    results = []
    for rec in records:
        pair = ContradictionPair(
            old_text=rec["old_text"],
            new_text=rec["new_text"],
            old_trust=float(rec["old_trust"]),
            new_trust=float(rec["new_trust"]),
            old_timestamp=float(rec["old_timestamp"]),
            new_timestamp=float(rec["new_timestamp"]),
            slot_name=rec.get("slot_name"),
            is_exclusive_slot=bool(rec.get("is_exclusive_slot", False)),
            similarity_score=float(rec.get("similarity_score", 0.0)),
            thread_id=rec.get("thread_id"),
        )
        if "belief_label" in rec and "policy_label" in rec:
            belief = BeliefType(rec["belief_label"])
            policy = PolicyAction(rec["policy_label"])
        else:
            belief, _ = labeler.label_belief(pair)
            policy, _ = labeler.label_policy(pair, belief)
        results.append((pair, belief, policy))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark classifier vs preserve-all baseline."
    )
    parser.add_argument("--models", default="models/")
    parser.add_argument("--test-data", help="JSON file with test pairs.")
    parser.add_argument("--synthetic", type=int, default=0)
    parser.add_argument("--output", "-o", help="Write markdown report to file.")
    args = parser.parse_args()

    model_dir = Path(args.models)
    belief_path = str(model_dir / "belief_xgboost.pkl")
    policy_path = str(model_dir / "policy_xgboost.pkl")

    if not Path(belief_path).exists() or not Path(policy_path).exists():
        print(f"Error: model files not found in {model_dir}")
        sys.exit(1)

    resolver = ContradictionResolver(belief_path, policy_path)

    data: List[Tuple[ContradictionPair, BeliefType, PolicyAction]] = []
    if args.test_data and Path(args.test_data).exists():
        data.extend(_load_data(args.test_data))
    if args.synthetic > 0:
        exporter = LedgerExporter([])
        data.extend(exporter.generate_synthetic_pairs(args.synthetic))
    if not data:
        print("Error: no data. Provide --test-data and/or --synthetic.")
        sys.exit(1)

    pairs = [d[0] for d in data]
    true_beliefs = [d[1] for d in data]
    true_policies = [d[2] for d in data]

    results = resolver.resolve_batch(pairs)
    pred_beliefs = [r[0] for r in results]
    pred_policies = [r[1] for r in results]

    n = len(data)

    # ── Baseline: preserve everything ────────────────────────────────────
    baseline_correct = sum(
        1 for tp in true_policies if tp == PolicyAction.PRESERVE
    )
    baseline_acc = baseline_correct / n if n else 0

    # ── Classifier stats ─────────────────────────────────────────────────
    clf_policy_correct = sum(
        1 for t, p in zip(true_policies, pred_policies) if t == p
    )
    clf_acc = clf_policy_correct / n if n else 0

    clf_belief_correct = sum(
        1 for t, p in zip(true_beliefs, pred_beliefs) if t == p
    )
    clf_belief_acc = clf_belief_correct / n if n else 0

    # Action distribution
    pred_policy_dist = Counter(p.value for p in pred_policies)
    true_policy_dist = Counter(p.value for p in true_policies)

    auto_resolved = pred_policy_dist.get("override", 0)
    escalated = pred_policy_dist.get("ask_user", 0)
    left_as_is = pred_policy_dist.get("preserve", 0)

    # Accuracy improvement
    acc_improvement = clf_acc - baseline_acc

    # ── Build report ─────────────────────────────────────────────────────
    lines = [
        "# Belief Classifier Benchmark Report",
        "",
        f"**Total test samples:** {n}",
        "",
        "## Baseline: Preserve Everything",
        "",
        f"- Policy accuracy: {baseline_acc:.1%} ({baseline_correct}/{n})",
        "- Strategy: never override, never ask user, keep all beliefs",
        "",
        "## Classifier Performance",
        "",
        f"- Belief accuracy:  {clf_belief_acc:.1%} ({clf_belief_correct}/{n})",
        f"- Policy accuracy:  {clf_acc:.1%} ({clf_policy_correct}/{n})",
        f"- **Accuracy improvement over baseline: {acc_improvement:+.1%}**",
        "",
        "## Action Distribution (Classifier)",
        "",
        f"| Action | Predicted | True |",
        f"|--------|-----------|------|",
        f"| Override (auto-resolve) | {pred_policy_dist.get('override', 0)} | {true_policy_dist.get('override', 0)} |",
        f"| Ask User (escalate) | {pred_policy_dist.get('ask_user', 0)} | {true_policy_dist.get('ask_user', 0)} |",
        f"| Preserve (leave as-is) | {pred_policy_dist.get('preserve', 0)} | {true_policy_dist.get('preserve', 0)} |",
        "",
        "## Summary",
        "",
        f"- **{auto_resolved}** contradictions would be auto-resolved (override)",
        f"- **{escalated}** would be escalated to the user (ask_user)",
        f"- **{left_as_is}** would be left as-is (preserve)",
        f"- Estimated accuracy improvement: **{acc_improvement:+.1%}** over naive baseline",
        "",
        "## Belief Type Distribution",
        "",
        "| Type | True | Predicted |",
        "|------|------|-----------|",
    ]
    true_belief_dist = Counter(b.value for b in true_beliefs)
    pred_belief_dist = Counter(b.value for b in pred_beliefs)
    for bt in BeliefType:
        lines.append(
            f"| {bt.value} | {true_belief_dist.get(bt.value, 0)} | {pred_belief_dist.get(bt.value, 0)} |"
        )

    report = "\n".join(lines) + "\n"

    print(report)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\nReport saved to {out}")


if __name__ == "__main__":
    main()
