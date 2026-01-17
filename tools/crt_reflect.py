#!/usr/bin/env python3
"""CRT reflection runner (non-interfering).

Intended usage: run on a schedule (cron/Task Scheduler) to batch-train the
learned-suggestions model from accumulated artifacts.

This does NOT change CRT memories or resolve contradictions.
It only produces a suggestion-only model artifact.

Defaults:
- Reads ./crt_runtime_config.json if present
- Scans ./artifacts for paired crt_stress_memory.<runid>.db + crt_stress_ledger.<runid>.db
- Writes ./artifacts/learned_suggestions.latest.joblib

You can point to a different config via CRT_RUNTIME_CONFIG_PATH.

"""

from __future__ import annotations

import os
import time
from pathlib import Path

from personal_agent.runtime_config import load_runtime_config


def _acquire_lock(lock_path: Path, stale_seconds: int = 3600) -> bool:
    try:
        if lock_path.exists():
            age = time.time() - lock_path.stat().st_mtime
            if age < stale_seconds:
                return False
            try:
                lock_path.unlink()
            except Exception:
                return False
        lock_path.write_text(str(time.time()), encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> int:
    cfg = load_runtime_config(None)
    reflect_cfg = (cfg or {}).get("reflection", {})

    artifacts_dir = Path(reflect_cfg.get("artifacts_dir") or "artifacts")
    out_path = Path(reflect_cfg.get("out_model_path") or (artifacts_dir / "learned_suggestions.latest.joblib"))
    min_examples = int(reflect_cfg.get("min_examples") or 50)
    max_runs = int(reflect_cfg.get("max_runs") or 0)

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    lock_path = artifacts_dir / ".crt_reflect.lock"
    if not _acquire_lock(lock_path):
        print("Reflection already running (lock present).")
        return 0

    try:
        from crt_learn_train import main as train_main
        import sys

        # Call trainer via argv so we reuse its CLI.
        argv = [
            sys.argv[0],
            "--artifacts-dir",
            str(artifacts_dir),
            "--out",
            str(out_path),
            "--min-examples",
            str(min_examples),
        ]
        if max_runs and max_runs > 0:
            argv.extend(["--max-runs", str(max_runs)])

        old_argv = sys.argv
        sys.argv = argv
        try:
            return int(train_main() or 0)
        finally:
            sys.argv = old_argv
    finally:
        try:
            lock_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
