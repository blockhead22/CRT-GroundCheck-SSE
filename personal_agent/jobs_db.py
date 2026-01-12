from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class JobRow:
    id: str
    type: str
    status: str
    priority: int
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    payload: Dict[str, Any]
    error: Optional[str]


def init_jobs_db(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            payload_json TEXT NOT NULL,
            error TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            data_json TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            path TEXT NOT NULL,
            sha256 TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_job_artifacts_job_id ON job_artifacts(job_id)")

    conn.commit()
    conn.close()


def enqueue_job(
    *,
    db_path: str,
    job_id: str,
    job_type: str,
    created_at: str,
    payload: Dict[str, Any],
    priority: int = 0,
) -> None:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO jobs (id, type, status, priority, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, job_type, "queued", int(priority), created_at, json.dumps(payload, sort_keys=True)),
    )
    conn.commit()
    conn.close()


def fetch_next_queued_job(db_path: str) -> Optional[JobRow]:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Highest priority first, then FIFO by created_at.
    cur.execute(
        "SELECT id, type, status, priority, created_at, started_at, finished_at, payload_json, error "
        "FROM jobs WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT 1",
        ("queued",),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    payload = {}
    try:
        payload = json.loads(row[7] or "{}")
    except Exception:
        payload = {}

    return JobRow(
        id=str(row[0]),
        type=str(row[1]),
        status=str(row[2]),
        priority=int(row[3] or 0),
        created_at=str(row[4]),
        started_at=(str(row[5]) if row[5] is not None else None),
        finished_at=(str(row[6]) if row[6] is not None else None),
        payload=payload,
        error=(str(row[8]) if row[8] is not None else None),
    )


def update_job_status(
    *,
    db_path: str,
    job_id: str,
    status: str,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    fields: List[str] = ["status = ?"]
    params: List[Any] = [status]

    if started_at is not None:
        fields.append("started_at = ?")
        params.append(started_at)
    if finished_at is not None:
        fields.append("finished_at = ?")
        params.append(finished_at)
    if error is not None:
        fields.append("error = ?")
        params.append(error)

    params.append(job_id)
    cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", tuple(params))

    conn.commit()
    conn.close()


def add_job_event(
    *,
    db_path: str,
    job_id: str,
    ts: str,
    level: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_events (job_id, ts, level, message, data_json) VALUES (?, ?, ?, ?, ?)",
        (job_id, ts, level, message, json.dumps(data, sort_keys=True) if data is not None else None),
    )
    conn.commit()
    conn.close()


def add_job_artifact(
    *,
    db_path: str,
    job_id: str,
    kind: str,
    path: str,
    created_at: str,
    sha256_hex: Optional[str] = None,
) -> None:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_artifacts (job_id, kind, path, sha256, created_at) VALUES (?, ?, ?, ?, ?)",
        (job_id, kind, path, sha256_hex, created_at),
    )
    conn.commit()
    conn.close()


def list_job_events(db_path: str, job_id: str) -> List[Dict[str, Any]]:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, level, message, data_json FROM job_events WHERE job_id = ? ORDER BY id ASC",
        (job_id,),
    )
    rows = cur.fetchall()
    conn.close()

    out: List[Dict[str, Any]] = []
    for ts, level, message, data_json in rows:
        data = None
        try:
            data = json.loads(data_json) if data_json else None
        except Exception:
            data = None
        out.append({"ts": ts, "level": level, "message": message, "data": data})
    return out


def list_job_artifacts(db_path: str, job_id: str) -> List[Dict[str, Any]]:
    init_jobs_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT kind, path, sha256, created_at FROM job_artifacts WHERE job_id = ? ORDER BY id ASC",
        (job_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return [{"kind": r[0], "path": r[1], "sha256": r[2], "created_at": r[3]} for r in rows]
