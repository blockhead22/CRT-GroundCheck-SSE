from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from personal_agent.artifact_store import validate_payload_against_schema
from personal_agent.background_jobs import run_job
from personal_agent.jobs_db import enqueue_job, fetch_next_queued_job, init_jobs_db


def test_jobs_db_enqueue_and_fetch(tmp_path: Path) -> None:
    db_path = tmp_path / "crt_jobs.db"
    init_jobs_db(str(db_path))

    jid = str(uuid4())
    enqueue_job(
        db_path=str(db_path),
        job_id=jid,
        job_type="summarize_session",
        created_at="2026-01-11T00:00:00+00:00",
        payload={"text": "hello"},
        priority=1,
    )

    job = fetch_next_queued_job(str(db_path))
    assert job is not None
    assert job.id == jid
    assert job.type == "summarize_session"
    assert job.status == "queued"
    assert job.payload.get("text") == "hello"


def test_background_job_schema_accepts_minimal_payload(tmp_path: Path) -> None:
    payload = {
        "job": {
            "id": "job-1",
            "type": "summarize_session",
            "status": "queued",
            "priority": 0,
            "created_at": "2026-01-11T00:00:00+00:00",
            "started_at": None,
            "finished_at": None,
            "payload": {},
            "error": None,
        },
        "events": [],
        "artifacts": [],
        "result": None,
    }
    validate_payload_against_schema(payload, "crt_background_job.v1.schema.json")

    out = tmp_path / "job.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    assert out.exists()


def test_propose_promotions_job_writes_valid_proposals(tmp_path: Path) -> None:
    # Create a minimal memory db with one USER memory.
    mem_db = tmp_path / "mem.db"
    import sqlite3

    conn = sqlite3.connect(str(mem_db))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp REAL NOT NULL,
            confidence REAL NOT NULL,
            trust REAL NOT NULL,
            source TEXT NOT NULL,
            sse_mode TEXT NOT NULL,
            context_json TEXT,
            tags_json TEXT,
            thread_id TEXT
        )
        """
    )
    cur.execute(
        "INSERT INTO memories (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "m1",
            "[]",
            "FACT: title = Founder",
            1.0,
            0.95,
            0.8,
            "user",
            "L",
        ),
    )
    conn.commit()
    conn.close()

    artifacts_dir = tmp_path / "artifacts"
    result, produced = run_job(
        job_type="propose_promotions",
        payload={"memory_db": str(mem_db)},
        artifacts_dir=artifacts_dir,
        job_id="job-123",
    )

    assert result.get("proposals_written") == 1
    assert len(produced) == 1
    assert produced[0].kind == "proposal"

    proposals_path = Path(produced[0].path)
    assert proposals_path.exists()

    proposals_payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    validate_payload_against_schema(proposals_payload, "crt_promotion_proposals.v1.schema.json")
