"""Evaluate trained belief/policy classifiers on test data.

Usage:
    python -m scripts.eval --models models/ --test-data data/exported_pairs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

from belief_classifier.classifier import ContradictionResolver
from belief_classifier.exporter import LedgerExporter
from belief_classifier.labeler import AutoLabeler
from belief_classifier.types import BeliefType, ContradictionPair, PolicyAction


def _load_test_data(
    path: str,
) -> List[Tuple[ContradictionPair, BeliefType, PolicyAction]]:
    """Load test data from JSON."""
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


def _print_confusion(
    true_labels: List[str], pred_labels: List[str], label_names: List[str]
) -> None:
    """Pretty-print a confusion matrix."""
    cm = confusion_matrix(true_labels, pred_labels, labels=label_names)
    max_name = max(len(n) for n in label_names)
    header = " " * (max_name + 2) + "  ".join(f"{n:>10s}" for n in label_names)
    print(header)
    for i, name in enumerate(label_names):
        row = "  ".join(f"{cm[i][j]:>10d}" for j in range(len(label_names)))
        print(f"{name:>{max_name}s}  {row}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained classifiers.")
    parser.add_argument(
        "--models",
        default="models/",
        help="Directory containing trained model files.",
    )
    parser.add_argument(
        "--test-data",
        required=True,
        help="JSON file with test pairs.",
    )
    parser.add_argument(
        "--synthetic",
        type=int,
        default=0,
        help="Generate synthetic test data instead of/in addition to file.",
    )
    args = parser.parse_args()

    model_dir = Path(args.models)
    belief_path = str(model_dir / "belief_xgboost.pkl")
    policy_path = str(model_dir / "policy_xgboost.pkl")

    if not Path(belief_path).exists() or not Path(policy_path).exists():
        print(f"Error: model files not found in {model_dir}")
        sys.exit(1)

    resolver = ContradictionResolver(belief_path, policy_path)

    # Load test data
    test_data: List[Tuple[ContradictionPair, BeliefType, PolicyAction]] = []

    test_path = Path(args.test_data)
    if test_path.exists():
        test_data.extend(_load_test_data(str(test_path)))
        print(f"Loaded {len(test_data)} test pairs from {test_path}")

    if args.synthetic > 0:
        exporter = LedgerExporter([])
        test_data.extend(exporter.generate_synthetic_pairs(args.synthetic))
        print(f"Added {args.synthetic} synthetic test pairs")

    if not test_data:
        print("Error: no test data available.")
        sys.exit(1)

    # Run predictions
    pairs = [d[0] for d in test_data]
    true_beliefs = [d[1] for d in test_data]
    true_policies = [d[2] for d in test_data]

    results = resolver.resolve_batch(pairs)
    pred_beliefs = [r[0] for r in results]
    pred_policies = [r[1] for r in results]

    # Belief evaluation
    belief_names = [bt.value for bt in BeliefType]
    true_b = [b.value for b in true_beliefs]
    pred_b = [b.value for b in pred_beliefs]

    print("\n" + "=" * 60)
    print("BELIEF CLASSIFIER EVALUATION")
    print("=" * 60)
    print("\nClassification Report:")
    print(classification_report(true_b, pred_b, labels=belief_names, zero_division=0))
    print("Confusion Matrix:")
    _print_confusion(true_b, pred_b, belief_names)

    # Per-class accuracy
    print("\nPer-Class Accuracy:")
    for bt in BeliefType:
        mask = [t == bt.value for t in true_b]
        if any(mask):
            correct = sum(1 for m, t, p in zip(mask, true_b, pred_b) if m and t == p)
            total = sum(mask)
            print(f"  {bt.value:12s}: {correct}/{total} = {correct / total:.3f}")

    # Policy evaluation
    policy_names = [pa.value for pa in PolicyAction]
    true_p = [p.value for p in true_policies]
    pred_p = [p.value for p in pred_policies]

    print("\n" + "=" * 60)
    print("POLICY CLASSIFIER EVALUATION")
    print("=" * 60)
    print("\nClassification Report:")
    print(classification_report(true_p, pred_p, labels=policy_names, zero_division=0))
    print("Confusion Matrix:")
    _print_confusion(true_p, pred_p, policy_names)

    # Per-class accuracy
    print("\nPer-Class Accuracy:")
    for pa in PolicyAction:
        mask = [t == pa.value for t in true_p]
        if any(mask):
            correct = sum(1 for m, t, p in zip(mask, true_p, pred_p) if m and t == p)
            total = sum(mask)
            print(f"  {pa.value:12s}: {correct}/{total} = {correct / total:.3f}")

    # Overall
    belief_acc = sum(1 for t, p in zip(true_b, pred_b) if t == p) / len(true_b)
    policy_acc = sum(1 for t, p in zip(true_p, pred_p) if t == p) / len(true_p)
    print(f"\nOverall belief accuracy:  {belief_acc:.3f}")
    print(f"Overall policy accuracy:  {policy_acc:.3f}")


if __name__ == "__main__":
    main()
