from __future__ import annotations

import os
import threading
import time
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class TrainingLoopStatus:
    enabled: bool
    running: bool
    last_started_at: Optional[float]
    last_finished_at: Optional[float]
    last_ok: Optional[bool]
    last_decision: Optional[str]
    last_reason: Optional[str]
    last_report_path: Optional[str]
    last_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "last_started_at": self.last_started_at,
            "last_finished_at": self.last_finished_at,
            "last_ok": self.last_ok,
            "last_decision": self.last_decision,
            "last_reason": self.last_reason,
            "last_report_path": self.last_report_path,
            "last_error": self.last_error,
        }


class CRTTrainingLoop:
    """Conservative training loop for the suggestion-only learned model.

    - Trains/evals/publishes via crt_learn_publish.run_train_eval_publish
    - Publishes to reflection.out_model_path
    - Does NOT change memories automatically (model is suggestion-only)

    This is intentionally minimal + dev-friendly.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        reflection_cfg: Dict[str, Any],
        learned_cfg: Dict[str, Any],
        loop_cfg: Dict[str, Any],
    ):
        self.repo_root = Path(repo_root)
        self.reflection_cfg = reflection_cfg or {}
        self.learned_cfg = learned_cfg or {}
        self.loop_cfg = loop_cfg or {}

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._running = False
        self._last_started_at: Optional[float] = None
        self._last_finished_at: Optional[float] = None
        self._last_ok: Optional[bool] = None
        self._last_decision: Optional[str] = None
        self._last_reason: Optional[str] = None
        self._last_report_path: Optional[str] = None
        self._last_error: Optional[str] = None

    def enabled(self) -> bool:
        if not bool(self.learned_cfg.get("enabled", True)):
            return False
        return bool(self.loop_cfg.get("enabled", False))

    def start(self) -> None:
        if not self.enabled():
            return
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        t = threading.Thread(target=self._run, name="crt-training-loop", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> TrainingLoopStatus:
        return TrainingLoopStatus(
            enabled=self.enabled(),
            running=bool(self._running),
            last_started_at=self._last_started_at,
            last_finished_at=self._last_finished_at,
            last_ok=self._last_ok,
            last_decision=self._last_decision,
            last_reason=self._last_reason,
            last_report_path=self._last_report_path,
            last_error=self._last_error,
        )

    def trigger_async(self) -> bool:
        """Kick off a one-shot run in a background thread; returns False if already running."""
        if not self.enabled():
            return False
        if self._running:
            return False

        t = threading.Thread(target=self.run_once, name="crt-training-once", daemon=True)
        t.start()
        return True

    def run_once(self) -> TrainingLoopStatus:
        if not self.enabled():
            return self.status()

        # Prevent concurrent runs.
        if not self._lock.acquire(blocking=False):
            return self.status()

        try:
            self._running = True
            self._last_error = None
            self._last_started_at = time.time()

            # Configure model path for runtime loading.
            out_model_path = str(self.reflection_cfg.get("out_model_path") or "artifacts/learned_suggestions.latest.joblib")
            publish_path = (self.repo_root / out_model_path).resolve()
            os.environ["CRT_LEARNED_MODEL_PATH"] = str(publish_path)

            artifacts_dir = str(self.reflection_cfg.get("artifacts_dir") or "artifacts")
            artifacts_path = (self.repo_root / artifacts_dir).resolve()

            # Input selection
            source_mode = str(self.loop_cfg.get("source") or "thread").strip().lower()
            thread_id = str(self.loop_cfg.get("thread_id") or "default").strip() or "default"

            max_runs = int(self.reflection_cfg.get("max_runs") or 0)
            min_examples = int(self.reflection_cfg.get("min_examples") or 0)

            min_eval_accuracy = self.loop_cfg.get("min_eval_accuracy")
            max_prefer_latest_rate = self.loop_cfg.get("max_prefer_latest_rate")
            min_train_examples = int(self.loop_cfg.get("min_train_examples") or max(20, min_examples))
            min_eval_examples = int(self.loop_cfg.get("min_eval_examples") or max(20, min_examples))

            from crt_learn_publish import run_train_eval_publish

            # Where to write timestamped reports
            out_dir = artifacts_path

            if source_mode == "artifacts":
                # If no paired stress DBs exist, skip quietly.
                mem_glob = list(artifacts_path.glob("crt_stress_memory.*.db"))
                led_glob = list(artifacts_path.glob("crt_stress_ledger.*.db"))
                if not mem_glob or not led_glob:
                    self._last_ok = False
                    self._last_decision = "skip"
                    self._last_reason = "no_artifact_runs"
                    self._last_report_path = None
                    self._last_finished_at = time.time()
                    return self.status()

                res = run_train_eval_publish(
                    out_dir=out_dir,
                    publish_path=publish_path,
                    artifacts_dir=artifacts_path,
                    max_runs=max_runs,
                    min_train_examples=min_train_examples,
                    min_eval_examples=min_eval_examples,
                    min_eval_accuracy=(float(min_eval_accuracy) if min_eval_accuracy is not None else None),
                    max_prefer_latest_rate=(float(max_prefer_latest_rate) if max_prefer_latest_rate is not None else None),
                    dry_run=False,
                )
            else:
                mem_db = (self.repo_root / "personal_agent" / f"crt_memory_{thread_id}.db").resolve()
                led_db = (self.repo_root / "personal_agent" / f"crt_ledger_{thread_id}.db").resolve()

                # Quick precheck: if there are no contradictions at all, training can't proceed.
                contra_total = 0
                try:
                    if led_db.exists():
                        conn = sqlite3.connect(str(led_db))
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(1) FROM contradictions")
                        contra_total = int((cur.fetchone() or [0])[0] or 0)
                        conn.close()
                except Exception:
                    contra_total = 0

                if contra_total <= 0:
                    self._last_ok = False
                    self._last_decision = "skip"
                    self._last_reason = "no_contradictions"
                    self._last_report_path = None
                    self._last_finished_at = time.time()
                    return self.status()

                res = run_train_eval_publish(
                    out_dir=out_dir,
                    publish_path=publish_path,
                    memory_db=mem_db,
                    ledger_db=led_db,
                    max_runs=0,
                    min_train_examples=min_train_examples,
                    min_eval_examples=min_eval_examples,
                    min_eval_accuracy=(float(min_eval_accuracy) if min_eval_accuracy is not None else None),
                    max_prefer_latest_rate=(float(max_prefer_latest_rate) if max_prefer_latest_rate is not None else None),
                    dry_run=False,
                )

            self._last_ok = bool(res.ok)
            self._last_decision = str(res.decision)
            self._last_reason = str(res.reason)
            self._last_report_path = str(res.report_path)
            self._last_finished_at = time.time()
            return self.status()

        except BaseException as e:
            self._last_ok = False
            self._last_decision = None
            self._last_reason = None
            self._last_report_path = None
            self._last_error = str(e)
            self._last_finished_at = time.time()
            return self.status()

        finally:
            self._running = False
            try:
                self._lock.release()
            except Exception:
                pass

    def _run(self) -> None:
        interval = float(self.loop_cfg.get("interval_seconds") or 300.0)
        jitter = float(self.loop_cfg.get("jitter_seconds") or 5.0)
        
        # Run quickly at startup if requested.
        if bool(self.loop_cfg.get("run_on_startup", True)):
            self.run_once()

        while not self._stop.is_set():
            # Simple sleep loop with tiny jitter to avoid synchronized runs.
            time.sleep(max(1.0, interval) + (jitter * 0.0))
            if self._stop.is_set():
                break
            self.run_once()
