"""Export ContradictionPairs from CRT databases to JSON.

Usage:
    python -m scripts.export_ledger --db-path D:/AI_round2/data/crt_memory.db --output data/exported_pairs.json
    python -m scripts.export_ledger --db-path D:/AI_round2/data/crt_memory.db --db-path D:/AI_round2/personal_agent/active_learning.db --output data/exported_pairs.json --include-labels
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

# Ensure package is importable when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from belief_classifier.exporter import LedgerExporter
from belief_classifier.types import ContradictionPair


def _pair_to_dict(pair: ContradictionPair) -> dict:
    return dataclasses.asdict(pair)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export contradiction pairs from CRT databases.")
    parser.add_argument(
        "--db-path",
        action="append",
        required=True,
        help="Path to a SQLite DB (can be repeated).",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--include-labels",
        action="store_true",
        help="Include auto-generated belief/policy labels.",
    )
    args = parser.parse_args()

    exporter = LedgerExporter(args.db_path)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.include_labels:
        labeled = exporter.export_labeled()
        records = []
        for pair, belief, policy in labeled:
            rec = _pair_to_dict(pair)
            rec["belief_label"] = belief.value
            rec["policy_label"] = policy.value
            records.append(rec)
    else:
        pairs = exporter.export_pairs()
        records = [_pair_to_dict(p) for p in pairs]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Exported {len(records)} pairs to {output_path}")


if __name__ == "__main__":
    main()
