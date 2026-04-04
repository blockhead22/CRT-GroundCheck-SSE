#!/usr/bin/env python3
"""Train → eval → publish pipeline for CRT learned-suggestions model.

Goal: treat learned model updates like a controlled release:
- produce timestamped artifacts
- evaluate them
- only update learned_suggestions.latest.joblib if thresholds pass
- write a publish report JSON

This keeps the learned component suggestion-only, observable, and regressions-detectable.

CLI example:
  D:/AI_round2/.venv/Scripts/python.exe crt_learn_publish.py \
    --artifacts-dir artifacts/adaptive_all_3x200_seed1337_postgates_20260111 \
    --max-runs 3 \
    --min-eval-accuracy 0.60 \
    --max-prefer-latest-rate 0.80

"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    decision: str
    reason: str
    trained_model_path: str
    published_model_path: Optional[str]
    eval_metrics: Dict[str, Any]
    report_path: str


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_train_eval_publish(
    *,
    out_dir: Path,
    publish_path: Path,
    artifacts_dir: Optional[Path] = None,
    memory_db: Optional[Path] = None,
    ledger_db: Optional[Path] = None,
    eval_set: Optional[Path] = None,
    max_runs: int = 0,
    min_train_examples: int = 20,
    min_eval_examples: int = 20,
    min_eval_accuracy: Optional[float] = None,
    max_prefer_latest_rate: Optional[float] = None,
    dry_run: bool = False,
) -> PublishResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = _utc_run_id()
    trained_model = out_dir / f"learned_suggestions.{run_id}.joblib"
    trained_eval = trained_model.with_suffix(".eval.json")
    trained_meta = trained_model.with_suffix(".meta.json")

    # Train
    from crt_learn_train import main as train_main

    train_argv: List[str] = ["--out", str(trained_model), "--min-examples", str(int(min_train_examples))]
    if artifacts_dir is not None:
        train_argv += ["--artifacts-dir", str(artifacts_dir), "--max-runs", str(int(max_runs))]
    else:
        if memory_db is None or ledger_db is None:
            raise ValueError("Provide either artifacts_dir or both memory_db and ledger_db")
        train_argv += ["--memory-db", str(memory_db), "--ledger-db", str(ledger_db)]

    train_main(train_argv)

    # Eval
    from crt_learn_eval import main as eval_main

    eval_argv: List[str] = ["--model", str(trained_model), "--out", str(trained_eval), "--min-examples", str(int(min_eval_examples))]
    if eval_set is not None:
        eval_argv += ["--eval-set", str(eval_set)]
    elif artifacts_dir is not None:
        eval_argv += ["--artifacts-dir", str(artifacts_dir), "--max-runs", str(int(max_runs))]
    else:
        eval_argv += ["--memory-db", str(memory_db), "--ledger-db", str(ledger_db)]

    eval_main(eval_argv)

    ev = _read_json(trained_eval)
    metrics = ev.get("metrics") if isinstance(ev.get("metrics"), dict) else {}

    examples = int(metrics.get("examples") or 0)
    accuracy = metrics.get("accuracy")
    prefer_latest_rate = metrics.get("prefer_latest_rate_pred")

    # Gate decision
    if examples < int(min_eval_examples):
        ok = False
        decision = "reject"
        reason = f"eval examples {examples} < min_eval_examples {int(min_eval_examples)}"
    elif min_eval_accuracy is not None and accuracy is not None and float(accuracy) < float(min_eval_accuracy):
        ok = False
        decision = "reject"
        reason = f"eval accuracy {float(accuracy):.3f} < min_eval_accuracy {float(min_eval_accuracy):.3f}"
    elif max_prefer_latest_rate is not None and prefer_latest_rate is not None and float(prefer_latest_rate) > float(max_prefer_latest_rate):
        ok = False
        decision = "reject"
        reason = f"prefer_latest_rate_pred {float(prefer_latest_rate):.3f} > max_prefer_latest_rate {float(max_prefer_latest_rate):.3f}"
    else:
        ok = True
        decision = "publish"
        reason = "passed thresholds"

    published_model_path: Optional[str] = None

    if ok and not dry_run:
        publish_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(trained_model, publish_path)
        # Copy sidecars so the dashboard can inspect latest immediately.
        if trained_meta.exists():
            shutil.copy2(trained_meta, publish_path.with_suffix(".meta.json"))
        if trained_eval.exists():
            shutil.copy2(trained_eval, publish_path.with_suffix(".eval.json"))
        published_model_path = str(publish_path)

    report = {
        "type": "crt_learned_suggestions_publish_report",
        "version": "v1",
        "run_id": run_id,
        "decision": decision,
        "ok": ok,
        "reason": reason,
        "dry_run": bool(dry_run),
        "trained": {
            "model_path": str(trained_model),
            "meta_path": str(trained_meta) if trained_meta.exists() else None,
            "eval_path": str(trained_eval) if trained_eval.exists() else None,
        },
        "published": {
            "model_path": published_model_path,
            "meta_path": str(publish_path.with_suffix(".meta.json")) if published_model_path else None,
            "eval_path": str(publish_path.with_suffix(".eval.json")) if published_model_path else None,
        },
        "thresholds": {
            "min_train_examples": int(min_train_examples),
            "min_eval_examples": int(min_eval_examples),
            "min_eval_accuracy": min_eval_accuracy,
            "max_prefer_latest_rate": max_prefer_latest_rate,
        },
        "inputs": {
            "artifacts_dir": str(artifacts_dir) if artifacts_dir is not None else None,
            "max_runs": int(max_runs),
            "memory_db": str(memory_db) if memory_db is not None else None,
            "ledger_db": str(ledger_db) if ledger_db is not None else None,
        },
        "eval_metrics": metrics,
    }

    report_path = out_dir / f"learned_suggestions.publish.{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return PublishResult(
        ok=ok,
        decision=decision,
        reason=reason,
        trained_model_path=str(trained_model),
        published_model_path=published_model_path,
        eval_metrics=metrics if isinstance(metrics, dict) else {},
        report_path=str(report_path),
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Train → eval → publish CRT learned suggestion model")
    ap.add_argument("--out-dir", default="artifacts", help="Directory to write timestamped artifacts and publish report")
    ap.add_argument("--publish-path", default="artifacts/learned_suggestions.latest.joblib", help="Path to update on successful publish")

    ap.add_argument("--artifacts-dir", default=None, help="Directory containing crt_stress_memory.*.db and crt_stress_ledger.*.db")
    ap.add_argument("--eval-set", default=None, help="Frozen eval-set JSON to evaluate against")
    ap.add_argument("--memory-db", default=None, help="Path to memory sqlite db")
    ap.add_argument("--ledger-db", default=None, help="Path to ledger sqlite db")
    ap.add_argument("--max-runs", type=int, default=0)

    ap.add_argument("--min-train-examples", type=int, default=20)
    ap.add_argument("--min-eval-examples", type=int, default=20)
    ap.add_argument("--min-eval-accuracy", type=float, default=None)
    ap.add_argument("--max-prefer-latest-rate", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")

    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    publish_path = Path(args.publish_path)

    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None
    eval_set = Path(args.eval_set) if args.eval_set else None
    memory_db = Path(args.memory_db) if args.memory_db else None
    ledger_db = Path(args.ledger_db) if args.ledger_db else None

    res = run_train_eval_publish(
        out_dir=out_dir,
        publish_path=publish_path,
        artifacts_dir=artifacts_dir,
        eval_set=eval_set,
        memory_db=memory_db,
        ledger_db=ledger_db,
        max_runs=int(args.max_runs),
        min_train_examples=int(args.min_train_examples),
        min_eval_examples=int(args.min_eval_examples),
        min_eval_accuracy=args.min_eval_accuracy,
        max_prefer_latest_rate=args.max_prefer_latest_rate,
        dry_run=bool(args.dry_run),
    )

    print(json.dumps(res.__dict__, indent=2, sort_keys=True))
    return 0 if res.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
