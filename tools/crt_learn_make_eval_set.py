#!/usr/bin/env python3
"""Create a frozen eval set for the learned-suggestions model.

Why:
- The learned model is suggestion-only, but we still want regression detection.
- Weak labels from contradictions are OK for trend tracking, but you need a *frozen* set
  so scores are comparable week-to-week.

What this does:
- Extracts labeled training-style examples (feature dict + label) from stress artifacts
  (or a single memory/ledger DB pair)
- Writes a JSON eval-set artifact that `crt_learn_eval.py --eval-set ...` can consume.

Usage:
  D:/AI_round2/.venv/Scripts/python.exe crt_learn_make_eval_set.py \
    --artifacts-dir artifacts/adaptive_all_3x200_seed1337_postgates_20260111 \
    --max-runs 3 \
    --out artifacts/eval_sets/learned_suggestions.eval_set.v1.json \
    --min-examples 200

"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Create frozen eval set for learned-suggestions")
    ap.add_argument("--out", required=True, help="Output JSON path")

    ap.add_argument("--artifacts-dir", default=None, help="Directory containing crt_stress_memory.*.db and crt_stress_ledger.*.db")
    ap.add_argument("--max-runs", type=int, default=0)
    ap.add_argument("--memory-db", default=None, help="Path to memory sqlite db")
    ap.add_argument("--ledger-db", default=None, help="Path to ledger sqlite db")

    ap.add_argument("--min-examples", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0, help="If >0, cap number of examples written")

    args = ap.parse_args(argv)

    # Reuse the exact feature/label extraction logic from crt_learn_eval.
    from crt_learn_eval import _choose_runs_from_artifacts_dir, _collect_labeled_examples

    runs: List[Tuple[str, str]] = []
    if args.artifacts_dir:
        art = Path(args.artifacts_dir)
        if not art.exists():
            raise SystemExit(f"artifacts-dir not found: {art}")
        runs = _choose_runs_from_artifacts_dir(art, int(args.max_runs))
        if not runs:
            raise SystemExit("No paired memory/ledger DBs found in artifacts-dir")
    else:
        if not args.memory_db or not args.ledger_db:
            raise SystemExit("Provide either --artifacts-dir or both --memory-db and --ledger-db")
        runs = [(args.memory_db, args.ledger_db)]

    X_all: List[Dict[str, Any]] = []
    y_all: List[str] = []
    scanned = 0
    for mem_db, led_db in runs:
        X, y, meta = _collect_labeled_examples(mem_db_path=mem_db, led_db_path=led_db)
        scanned += int(meta.get("contradictions_scanned") or 0)
        X_all.extend(X)
        y_all.extend(y)

    if len(X_all) < int(args.min_examples):
        raise SystemExit(f"Not enough examples for eval set: {len(X_all)} < {int(args.min_examples)}")

    items = [{"x": x, "y": y} for x, y in zip(X_all, y_all)]
    if int(args.limit) and int(args.limit) > 0:
        items = items[: int(args.limit)]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "type": "crt_learned_suggestions_eval_set",
        "version": "v1",
        "eval_set_id": f"v1_{_utc_run_id()}",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "inputs": {
            "artifacts_dir": str(Path(args.artifacts_dir)) if args.artifacts_dir else None,
            "max_runs": int(args.max_runs),
            "memory_db": str(args.memory_db) if args.memory_db else None,
            "ledger_db": str(args.ledger_db) if args.ledger_db else None,
            "min_examples": int(args.min_examples),
            "limit": int(args.limit),
            "contradictions_scanned": int(scanned),
        },
        "examples": {
            "count": int(len(items)),
            "items": items,
        },
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote eval set: {out_path} ({len(items)} examples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
