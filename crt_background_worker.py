#!/usr/bin/env python3
"""CRT background worker (minimal scaffold).

This is the start of the "subconscious" loop in the master roadmap:
- Uses a SQLite job queue (crt_jobs.db)
- Executes queued jobs (currently: minimal stubs)
- Writes schema-validated job artifacts to disk

This is intentionally conservative: it produces *artifacts* and logs, but does not
promote anything into belief-lane memories.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from personal_agent.artifact_store import now_iso_utc, sha256_file, write_background_job_artifact
from personal_agent.background_jobs import run_job
from personal_agent.jobs_db import (
    add_job_artifact,
    add_job_event,
    enqueue_job,
    fetch_next_queued_job,
    init_jobs_db,
    update_job_status,
)


def _job_artifact_path(base_dir: Path, job_id: str) -> Path:
    return base_dir / "background_jobs" / f"job.{job_id}.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CRT background worker (jobs + artifacts)")
    ap.add_argument("--db", default="artifacts/crt_jobs.db", help="Path to jobs sqlite db")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Base dir for artifact outputs")
    ap.add_argument("--once", action="store_true", help="Process at most one queued job then exit")
    ap.add_argument("--poll-seconds", type=float, default=2.0, help="Poll interval when idle")

    ap.add_argument(
        "--job-id",
        default=None,
        help="Optional explicit job id to use when enqueuing (otherwise a UUID is generated)",
    )

    ap.add_argument(
        "--enqueue-demo",
        action="store_true",
        help="Enqueue one demo summarize_session job (for smoke testing)",
    )

    ap.add_argument(
        "--enqueue-propose-promotions",
        action="store_true",
        help="Enqueue one propose_promotions job (payload requires --memory-db)",
    )
    ap.add_argument(
        "--memory-db",
        default=None,
        help="Path to crt_memory.db (required for --enqueue-propose-promotions)",
    )

    args = ap.parse_args(argv)

    db_path = str(Path(args.db))
    init_jobs_db(db_path)

    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if args.enqueue_demo:
        jid = str(args.job_id) if args.job_id else str(uuid4())
        enqueue_job(
            db_path=db_path,
            job_id=jid,
            job_type="summarize_session",
            created_at=now_iso_utc(),
            payload={"text": "This is a demo background job. It should produce a short summary artifact."},
            priority=0,
        )
        print(f"Enqueued demo job: {jid}")

    if args.enqueue_propose_promotions:
        memory_db = str(args.memory_db or "").strip()
        if not memory_db:
            raise SystemExit("--memory-db is required when using --enqueue-propose-promotions")
        jid = str(args.job_id) if args.job_id else str(uuid4())
        enqueue_job(
            db_path=db_path,
            job_id=jid,
            job_type="propose_promotions",
            created_at=now_iso_utc(),
            payload={"memory_db": memory_db},
            priority=0,
        )
        print(f"Enqueued propose_promotions job: {jid}")

    while True:
        job = fetch_next_queued_job(db_path)
        if not job:
            if args.once:
                return 0
            time.sleep(float(args.poll_seconds))
            continue

        started = now_iso_utc()
        update_job_status(db_path=db_path, job_id=job.id, status="running", started_at=started)
        add_job_event(db_path=db_path, job_id=job.id, ts=started, level="info", message="job started")

        artifact_path = _job_artifact_path(artifacts_dir, job.id)
        try:
            result, produced = run_job(job_type=job.type, payload=job.payload, artifacts_dir=artifacts_dir, job_id=job.id)

            payload = {
                "job": {
                    "id": job.id,
                    "type": job.type,
                    "status": "succeeded",
                    "priority": int(job.priority),
                    "created_at": job.created_at,
                    "started_at": started,
                    "finished_at": now_iso_utc(),
                    "payload": job.payload,
                    "error": None,
                },
                "events": [
                    {"ts": started, "level": "info", "message": "job started", "data": None},
                    {"ts": now_iso_utc(), "level": "info", "message": "job finished", "data": None},
                ],
                "artifacts": [
                    {
                        "kind": a.kind,
                        "path": a.path,
                        "sha256": a.sha256,
                        "created_at": a.created_at,
                    }
                    for a in (produced or [])
                ],
                "result": result,
            }

            write_background_job_artifact(artifact_path, payload)
            job_sha = sha256_file(artifact_path)

            # Update sha in job artifact payload (best effort).
            try:
                data = json.loads(artifact_path.read_text(encoding="utf-8"))
                data.setdefault("job", {})
                data["job"]["artifact_sha256"] = job_sha
                artifact_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except Exception:
                pass

            # Record produced artifacts.
            for a in (produced or []):
                add_job_artifact(
                    db_path=db_path,
                    job_id=job.id,
                    kind=a.kind,
                    path=a.path,
                    created_at=a.created_at,
                    sha256_hex=a.sha256,
                )

            finished = now_iso_utc()
            update_job_status(db_path=db_path, job_id=job.id, status="succeeded", finished_at=finished)
            add_job_event(db_path=db_path, job_id=job.id, ts=finished, level="info", message="job finished")
            print(f"Job {job.id} succeeded; wrote {artifact_path}")

        except Exception as e:
            finished = now_iso_utc()
            update_job_status(db_path=db_path, job_id=job.id, status="failed", finished_at=finished, error=str(e))
            add_job_event(db_path=db_path, job_id=job.id, ts=finished, level="error", message=str(e))
            print(f"Job {job.id} failed: {e}")

        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
