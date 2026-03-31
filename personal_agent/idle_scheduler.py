from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from personal_agent.artifact_store import now_iso_utc
from personal_agent.db_utils import get_db_connection
from personal_agent.jobs_db import enqueue_job, init_jobs_db

try:
    from personal_agent.active_learning import get_active_learning_coordinator
    ACTIVE_LEARNING_AVAILABLE = True
except ImportError:
    ACTIVE_LEARNING_AVAILABLE = False

try:
    from personal_agent.trust_decay import run_trust_decay_pass
    TRUST_DECAY_AVAILABLE = True
except ImportError:
    TRUST_DECAY_AVAILABLE = False

# CRT math for volatility-based priority routing
_crt_math = None

def _get_crt_math():
    """Lazy-load CRTMath singleton for idle scheduler."""
    global _crt_math
    if _crt_math is not None:
        return _crt_math
    try:
        from personal_agent.crt_core import CRTMath, CRTConfig
        _crt_math = CRTMath(CRTConfig())
        return _crt_math
    except Exception:
        return None


def _safe_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _count_open_contradictions(ledger_db: Path) -> int:
    if not ledger_db.exists():
        return 0
    try:
        with get_db_connection(str(ledger_db)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(1) FROM contradictions WHERE status = ?", ("open",))
            n = int((cur.fetchone() or [0])[0] or 0)
            return n
    except Exception:
        return 0


def _last_user_activity_ts(memory_db: Path) -> float:
    if not memory_db.exists():
        return 0.0
    try:
        with get_db_connection(str(memory_db)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT MAX(timestamp) FROM memories WHERE LOWER(source) = 'user'")
            v = cur.fetchone()
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
        auto_consolidation_enabled: bool = True,
    ):
        self.repo_root = Path(repo_root)
        self.jobs_db_path = str(jobs_db_path)
        self.enabled = bool(enabled)
        self.idle_seconds = max(5, int(idle_seconds))
        self.interval_seconds = max(2, int(interval_seconds))
        self.auto_resolve_contradictions_enabled = bool(auto_resolve_contradictions_enabled)
        self.auto_web_research_enabled = bool(auto_web_research_enabled)
        self.auto_learning_enabled = bool(auto_learning_enabled) and ACTIVE_LEARNING_AVAILABLE
        self.auto_consolidation_enabled = bool(auto_consolidation_enabled)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_enqueued_by_thread: Dict[str, float] = {}
        self._last_consolidation_ts: float = 0.0
        self._CONSOLIDATION_MIN_INTERVAL = 21600  # 6 hours between passes

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
        """Single scheduler tick — CRT volatility-prioritized."""
        if not self.enabled:
            return

        # Scan per-thread DBs and compute priority scores
        pa_dir = (self.repo_root / "personal_agent").resolve()
        thread_candidates = []

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

            # CRT volatility score for priority routing
            # Threads with more contradictions and longer idle time get higher priority
            priority_score = 0.0
            crt = _get_crt_math()
            if crt is not None:
                # Use CRT volatility formula:
                # V = β_drift * (normalized idle) + β_contradiction * (normalized contras)
                # Normalized idle: 1.0 if idle > 1 hour, scaled below
                norm_idle = min(1.0, idle_for / 3600.0)
                norm_contras = min(1.0, open_contras / 10.0)
                priority_score = crt.compute_volatility(
                    drift=norm_idle,
                    memory_alignment=1.0 - norm_contras,  # More contras = less alignment
                    is_contradiction=open_contras > 0,
                    is_fallback=False,
                )
            else:
                priority_score = float(open_contras)

            thread_candidates.append({
                "thread_id": thread_id,
                "mem_db": mem_db,
                "led_db": led_db,
                "open_contras": open_contras,
                "idle_for": idle_for,
                "priority_score": priority_score,
                "now_ts": now_ts,
            })

        # Sort by volatility/priority — highest first
        thread_candidates.sort(key=lambda t: t["priority_score"], reverse=True)

        for candidate in thread_candidates:
            thread_id = candidate["thread_id"]
            now_ts = candidate["now_ts"]

            if self.auto_resolve_contradictions_enabled:
                # Determine job priority from CRT volatility
                crt = _get_crt_math()
                needs_reflection = False
                if crt is not None:
                    needs_reflection = crt.should_reflect(candidate["priority_score"])

                # High-volatility threads get reflection jobs in addition to resolution
                jid = f"job_auto_resolve_{thread_id}_{int(now_ts)}"
                enqueue_job(
                    db_path=self.jobs_db_path,
                    job_id=jid,
                    job_type="auto_resolve_contradictions",
                    created_at=now_iso_utc(),
                    payload={
                        "thread_id": thread_id,
                        "memory_db": str(candidate["mem_db"]),
                        "ledger_db": str(candidate["led_db"]),
                        "max_to_resolve": 10,
                        "volatility": candidate["priority_score"],
                        "needs_reflection": needs_reflection,
                    },
                    priority=1 if needs_reflection else 0,
                )
                self._last_enqueued_by_thread[thread_id] = now_ts

            # auto_web_research_enabled is intentionally a no-op for now.
        
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

        # Trust decay: gently age stale memories, reinforce active ones
        if TRUST_DECAY_AVAILABLE:
            try:
                run_trust_decay_pass()
            except Exception:
                pass  # Graceful degradation

        # Memory consolidation: batch NLI contradiction sweep
        if self.auto_consolidation_enabled:
            now_ts = time.time()
            if (now_ts - self._last_consolidation_ts) >= self._CONSOLIDATION_MIN_INTERVAL:
                try:
                    from personal_agent.memory_consolidation import run_consolidation_pass
                    from personal_agent.crt_memory import CRTMemorySystem
                    from personal_agent.crt_ledger import ContradictionLedger

                    pa_dir = (self.repo_root / "personal_agent").resolve()
                    for mem_db in pa_dir.glob("crt_memory_*.db"):
                        thread_id = mem_db.stem.replace("crt_memory_", "") or "default"
                        led_db = pa_dir / f"crt_ledger_{thread_id}.db"
                        if not led_db.exists():
                            continue

                        mem_sys = CRTMemorySystem(db_path=str(mem_db))
                        ledger = ContradictionLedger(db_path=str(led_db))
                        result = run_consolidation_pass(
                            memory_system=mem_sys,
                            ledger=ledger,
                            max_pairs=30,
                        )
                        if result.new_contradictions_found > 0:
                            import logging as _log
                            _log.getLogger(__name__).info(
                                f"[IDLE] Consolidation for {thread_id}: "
                                f"found={result.new_contradictions_found} "
                                f"resolved={result.auto_resolved}"
                            )

                    self._last_consolidation_ts = now_ts
                except ImportError:
                    pass  # Module not available
                except Exception:
                    pass  # Graceful degradation
