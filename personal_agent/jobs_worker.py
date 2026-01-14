from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from personal_agent.artifact_store import now_iso_utc, sha256_file, write_background_job_artifact
from personal_agent.background_jobs import run_job
from personal_agent.jobs_db import (
    add_job_artifact,
    add_job_event,
    fetch_next_queued_job,
    get_job,
    init_jobs_db,
    list_job_artifacts,
    list_job_events,
    update_job_status,
)


@dataclass
class JobsWorkerStatus:
    enabled: bool
    running: bool
    last_tick_at: Optional[float]
    last_job_id: Optional[str]
    last_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "last_tick_at": self.last_tick_at,
            "last_job_id": self.last_job_id,
            "last_error": self.last_error,
        }


class CRTJobsWorker:
    """Simple background worker for CRT jobs.

    - Pulls jobs from SQLite queue (jobs_db)
    - Executes via personal_agent.background_jobs.run_job
    - Writes events + artifacts + a portable job record JSON

    Intentionally conservative:
    - Processes one job at a time
    - No parallelism (keeps DB locking simple)
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        jobs_db_path: str,
        artifacts_dir: str,
        enabled: bool = True,
        interval_seconds: float = 2.0,
    ):
        self.repo_root = Path(repo_root)
        self.jobs_db_path = str(jobs_db_path)
        self.artifacts_dir = str(artifacts_dir)
        self.enabled = bool(enabled)
        self.interval_seconds = float(interval_seconds)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._running = False
        self._last_tick_at: Optional[float] = None
        self._last_job_id: Optional[str] = None
        self._last_error: Optional[str] = None

        init_jobs_db(self.jobs_db_path)

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        t = threading.Thread(target=self._run, name="crt-jobs-worker", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> JobsWorkerStatus:
        return JobsWorkerStatus(
            enabled=self.enabled,
            running=bool(self._running),
            last_tick_at=self._last_tick_at,
            last_job_id=self._last_job_id,
            last_error=self._last_error,
        )

    def run_one(self) -> Optional[str]:
        """Process a single queued job. Returns job_id if one was processed."""
        if not self.enabled:
            return None

        if not self._lock.acquire(blocking=False):
            return None

        try:
            job = fetch_next_queued_job(self.jobs_db_path)
            self._last_tick_at = time.time()
            if job is None:
                return None

            self._last_job_id = job.id
            self._last_error = None

            started = now_iso_utc()
            update_job_status(db_path=self.jobs_db_path, job_id=job.id, status="running", started_at=started)
            add_job_event(db_path=self.jobs_db_path, job_id=job.id, ts=started, level="info", message="job_started")

            artifacts_path = (self.repo_root / self.artifacts_dir).resolve()
            artifacts_path.mkdir(parents=True, exist_ok=True)

            result: Dict[str, Any] = {}
            produced = []
            try:
                result, produced = run_job(job_type=job.type, payload=job.payload, artifacts_dir=artifacts_path, job_id=job.id)
            except Exception as e:
                finished = now_iso_utc()
                add_job_event(
                    db_path=self.jobs_db_path,
                    job_id=job.id,
                    ts=finished,
                    level="error",
                    message="job_failed",
                    data={"error": str(e)},
                )
                update_job_status(db_path=self.jobs_db_path, job_id=job.id, status="failed", finished_at=finished, error=str(e))
                self._write_job_record(job.id)
                return job.id

            # Persist artifacts
            for a in produced or []:
                try:
                    sha = a.sha256
                    if not sha and a.path:
                        p = Path(a.path)
                        if p.exists() and p.is_file():
                            sha = sha256_file(p)
                    add_job_artifact(
                        db_path=self.jobs_db_path,
                        job_id=job.id,
                        kind=str(a.kind),
                        path=str(a.path),
                        created_at=str(a.created_at),
                        sha256_hex=sha,
                    )
                except Exception:
                    # Artifact logging should never fail the job.
                    pass

            finished = now_iso_utc()
            add_job_event(
                db_path=self.jobs_db_path,
                job_id=job.id,
                ts=finished,
                level="info",
                message="job_succeeded",
                data={"result": result},
            )
            update_job_status(db_path=self.jobs_db_path, job_id=job.id, status="succeeded", finished_at=finished)

            self._write_job_record(job.id, result=result)
            return job.id

        finally:
            try:
                self._lock.release()
            except Exception:
                pass

    def _write_job_record(self, job_id: str, *, result: Optional[Dict[str, Any]] = None) -> None:
        try:
            job = get_job(self.jobs_db_path, job_id)
            if job is None:
                return
            events = list_job_events(self.jobs_db_path, job_id)
            artifacts = list_job_artifacts(self.jobs_db_path, job_id)

            payload = {
                "job": {
                    "id": job.id,
                    "type": job.type,
                    "status": job.status,
                    "priority": job.priority,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "finished_at": job.finished_at,
                    "payload": job.payload,
                    "error": job.error,
                },
                "events": events,
                "artifacts": artifacts,
                "result": result,
            }

            out_dir = (self.repo_root / self.artifacts_dir / "jobs").resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"job.{job_id}.json"
            write_background_job_artifact(out_path, payload)
        except Exception as e:
            self._last_error = str(e)

    def _run(self) -> None:
        if not self.enabled:
            return

        self._running = True
        try:
            while not self._stop.is_set():
                try:
                    self.run_one()
                except Exception as e:
                    self._last_error = str(e)
                time.sleep(max(0.25, self.interval_seconds))
        finally:
            self._running = False
