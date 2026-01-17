from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from personal_agent.artifact_store import now_iso_utc
from personal_agent.jobs_db import enqueue_job, init_jobs_db

try:
    from personal_agent.active_learning import get_active_learning_coordinator
    ACTIVE_LEARNING_AVAILABLE = True
except ImportError:
    ACTIVE_LEARNING_AVAILABLE = False


def _safe_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _count_open_contradictions(ledger_db: Path) -> int:
    if not ledger_db.exists():
        return 0
    try:
        conn = sqlite3.connect(str(ledger_db))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM contradictions WHERE status = ?", ("open",))
        n = int((cur.fetchone() or [0])[0] or 0)
        conn.close()
        return n
    except Exception:
        return 0


def _last_user_activity_ts(memory_db: Path) -> float:
    if not memory_db.exists():
        return 0.0
    try:
        conn = sqlite3.connect(str(memory_db))
        cur = conn.cursor()
        cur.execute("SELECT MAX(timestamp) FROM memories WHERE LOWER(source) = 'user'")
        v = cur.fetchone()
        conn.close()
        if not v or v[0] is None:
            return 0.0
        return float(v[0])
    except Exception:
        return 0.0


class CRTIdleScheduler:
    """Idle-time scheduler that enqueues conservative background jobs.

    Current behavior (by design):
    - Optionally enqueue auto-resolve attempts for OPEN contradictions once the thread is idle.

    Web research while idle is intentionally *not* automatically triggered here unless you
    explicitly enable it and add a trigger mechanism.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        jobs_db_path: str,
        enabled: bool,
        idle_seconds: int,
        interval_seconds: int = 10,
        auto_resolve_contradictions_enabled: bool = False,
        auto_web_research_enabled: bool = False,
        auto_learning_enabled: bool = True,
    ):
        self.repo_root = Path(repo_root)
        self.jobs_db_path = str(jobs_db_path)
        self.enabled = bool(enabled)
        self.idle_seconds = max(5, int(idle_seconds))
        self.interval_seconds = max(2, int(interval_seconds))
        self.auto_resolve_contradictions_enabled = bool(auto_resolve_contradictions_enabled)
        self.auto_web_research_enabled = bool(auto_web_research_enabled)
        self.auto_learning_enabled = bool(auto_learning_enabled) and ACTIVE_LEARNING_AVAILABLE

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_enqueued_by_thread: Dict[str, float] = {}

        init_jobs_db(self.jobs_db_path)

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        t = threading.Thread(target=self._run, name="crt-idle-scheduler", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        if not self.enabled:
            return

        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                pass
            time.sleep(float(self.interval_seconds))

    def tick(self) -> None:
        """Single scheduler tick."""
        if not self.enabled:
            return

        # Scan per-thread DBs.
        pa_dir = (self.repo_root / "personal_agent").resolve()
        for mem_db in pa_dir.glob("crt_memory_*.db"):
            thread_id = mem_db.stem.replace("crt_memory_", "") or "default"
            led_db = pa_dir / f"crt_ledger_{thread_id}.db"

            last_user_ts = _last_user_activity_ts(mem_db)
            if last_user_ts <= 0:
                continue

            now_ts = time.time()
            idle_for = now_ts - float(last_user_ts)
            if idle_for < float(self.idle_seconds):
                continue

            open_contras = _count_open_contradictions(led_db)
            if open_contras <= 0:
                continue

            last_enq = self._last_enqueued_by_thread.get(thread_id, 0.0)
            if (now_ts - last_enq) < float(self.idle_seconds):
                continue

            if self.auto_resolve_contradictions_enabled:
                # Enqueue a conservative auto-resolve attempt.
                jid = f"job_auto_resolve_{thread_id}_{int(now_ts)}"
                enqueue_job(
                    db_path=self.jobs_db_path,
                    job_id=jid,
                    job_type="auto_resolve_contradictions",
                    created_at=now_iso_utc(),
                    payload={
                        "thread_id": thread_id,
                        "memory_db": str(mem_db),
                        "ledger_db": str(led_db),
                        "max_to_resolve": 10,
                    },
                    priority=0,
                )
                self._last_enqueued_by_thread[thread_id] = now_ts

            # auto_web_research_enabled is intentionally a no-op for now.
            # We need a user-approved trigger (e.g., explicit queued research tasks) to avoid surprise.
        
        # Active learning: retrain during idle time if needed
        if self.auto_learning_enabled and ACTIVE_LEARNING_AVAILABLE:
            try:
                coordinator = get_active_learning_coordinator()
                stats = coordinator.get_stats()
                
                # Only retrain if:
                # 1. Not currently training
                # 2. Have enough corrections (50+)
                # 3. No model or accuracy < 80%
                if stats.pending_training and not stats.model_loaded:
                    coordinator._trigger_training()
                elif stats.pending_training and stats.model_accuracy and stats.model_accuracy < 0.80:
                    coordinator._trigger_training()
            except Exception:
                pass  # Graceful degradation
