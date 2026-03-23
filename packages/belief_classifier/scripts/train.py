"""Train belief and policy XGBoost classifiers.

Usage:
    python -m scripts.train --data data/exported_pairs.json --synthetic 200 --output models/
    python -m scripts.train --synthetic 300 --output models/  # synthetic-only
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from belief_classifier.classifier import BeliefClassifier, PolicyClassifier
from belief_classifier.exporter import LedgerExporter
from belief_classifier.labeler import AutoLabeler
from belief_classifier.types import BeliefType, ContradictionPair, PolicyAction


def _load_pairs_from_json(
    path: str,
) -> List[Tuple[ContradictionPair, BeliefType, PolicyAction]]:
    """Load pairs from exported JSON, auto-labeling if labels are missing."""
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
    parser = argparse.ArgumentParser(description="Train belief/policy classifiers.")
    parser.add_argument("--data", help="Path to exported JSON pairs.")
    parser.add_argument(
        "--synthetic",
        type=int,
        default=0,
        help="Number of synthetic pairs to add (default 0).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="models/",
        help="Output directory for trained models.",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.2,
        help="Fraction of data to hold out for eval (default 0.2).",
    )
    args = parser.parse_args()

    # Collect training data
    all_data: List[Tuple[ContradictionPair, BeliefType, PolicyAction]] = []

    if args.data:
        data_path = Path(args.data)
        if data_path.exists():
            all_data.extend(_load_pairs_from_json(str(data_path)))
            print(f"Loaded {len(all_data)} pairs from {data_path}")
        else:
            print(f"Warning: {data_path} not found, skipping.")

    if args.synthetic > 0:
        exporter = LedgerExporter([])
        synthetic = exporter.generate_synthetic_pairs(args.synthetic)
        print(f"Generated {len(synthetic)} synthetic pairs")
        all_data.extend(synthetic)

    if not all_data:
        print("Error: no training data. Provide --data and/or --synthetic.")
        sys.exit(1)

    print(f"Total training samples: {len(all_data)}")

    pairs = [d[0] for d in all_data]
    belief_labels = [d[1] for d in all_data]
    policy_labels = [d[2] for d in all_data]

    # Print label distribution
    print("\n--- Label Distribution ---")
    for bt in BeliefType:
        count = sum(1 for b in belief_labels if b == bt)
        print(f"  {bt.value:12s}: {count}")
    for pa in PolicyAction:
        count = sum(1 for p in policy_labels if p == pa)
        print(f"  {pa.value:12s}: {count}")

    # Train/test split
    indices = list(range(len(all_data)))
    if len(all_data) >= 10:
        train_idx, test_idx = train_test_split(
            indices, test_size=args.test_split, random_state=42
        )
    else:
        train_idx = indices
        test_idx = indices  # too small to split

    train_pairs = [pairs[i] for i in train_idx]
    train_beliefs = [belief_labels[i] for i in train_idx]
    train_policies = [policy_labels[i] for i in train_idx]
    test_pairs = [pairs[i] for i in test_idx]
    test_beliefs = [belief_labels[i] for i in test_idx]
    test_policies = [policy_labels[i] for i in test_idx]

    # Train belief classifier
    print("\n--- Training Belief Classifier ---")
    belief_clf = BeliefClassifier()
    metrics = belief_clf.train(train_pairs, train_beliefs)
    print(f"  Train accuracy: {metrics['train_accuracy']:.3f}")

    if test_pairs:
        preds = belief_clf.predict_batch(test_pairs)
        pred_labels = [p[0].value for p in preds]
        true_labels = [b.value for b in test_beliefs]
        print("\n  Test Classification Report (Belief):")
        print(classification_report(true_labels, pred_labels, zero_division=0))

    # Train policy classifier
    print("--- Training Policy Classifier ---")
    policy_clf = PolicyClassifier()
    metrics = policy_clf.train(train_pairs, train_beliefs, train_policies)
    print(f"  Train accuracy: {metrics['train_accuracy']:.3f}")

    if test_pairs:
        preds = policy_clf.predict_batch(test_pairs, test_beliefs)
        pred_labels = [p[0].value for p in preds]
        true_labels = [p.value for p in test_policies]
        print("\n  Test Classification Report (Policy):")
        print(classification_report(true_labels, pred_labels, zero_division=0))

    # Save models
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    belief_path = str(output_dir / "belief_xgboost.pkl")
    policy_path = str(output_dir / "policy_xgboost.pkl")
    belief_clf.save(belief_path)
    policy_clf.save(policy_path)
    print(f"\nModels saved to {output_dir}/")
    print(f"  {belief_path}")
    print(f"  {policy_path}")


if __name__ == "__main__":
    main()
