from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from personal_agent.artifact_store import validate_payload_against_schema


def _create_minimal_memory_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
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


def test_background_worker_cli_can_enqueue_and_run_propose_promotions(tmp_path: Path) -> None:
    mem_db = tmp_path / "mem.db"
    _create_minimal_memory_db(mem_db)

    jobs_db = tmp_path / "crt_jobs.db"
    artifacts_dir = tmp_path / "artifacts"

    # Import inside the test to ensure the module stays importable.
    from crt_background_worker import main

    job_id = "job-123"
    rc = main(
        [
            "--db",
            str(jobs_db),
            "--artifacts-dir",
            str(artifacts_dir),
            "--once",
            "--enqueue-propose-promotions",
            "--memory-db",
            str(mem_db),
            "--job-id",
            job_id,
        ]
    )
    assert rc == 0

    job_artifact = artifacts_dir / "background_jobs" / f"job.{job_id}.json"
    assert job_artifact.exists()

    proposals_path = artifacts_dir / "promotions" / f"proposals.{job_id}.json"
    assert proposals_path.exists()

    proposals_payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    validate_payload_against_schema(proposals_payload, "crt_promotion_proposals.v1.schema.json")
