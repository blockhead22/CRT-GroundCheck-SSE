from __future__ import annotations

import json
from pathlib import Path

import sqlite3

from personal_agent.artifact_store import now_iso_utc, validate_payload_against_schema
from personal_agent.promotion_apply import apply_promotions


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
    conn.commit()
    conn.close()


def test_apply_promotions_dry_run_validates_and_does_not_write(tmp_path: Path) -> None:
    mem_db = tmp_path / "mem.db"
    _create_minimal_memory_db(mem_db)

    proposals_path = tmp_path / "proposals.json"
    decisions_path = tmp_path / "decisions.json"

    proposals_payload = {
        "metadata": {"version": "v1", "generated_at": now_iso_utc(), "source_job_id": "job-1", "notes": None},
        "proposals": [
            {
                "id": "job-1:name",
                "status": "proposed",
                "rationale": "test",
                "memory": {
                    "kind": "fact",
                    "lane": "notes",
                    "key": "name",
                    "value_text": "Nick Block",
                    "source": "user",
                    "trust": 0.7,
                    "confidence": 0.9,
                    "supersedes_id": None,
                    "provenance": {"memory_id": "m1", "job_id": "job-1"},
                    "evidence": [
                        {"source_type": "memory", "memory_id": "m1", "url": None, "quote_text": None, "timestamp": None}
                    ],
                },
            }
        ],
    }
    decisions_payload = {
        "metadata": {
            "version": "v1",
            "generated_at": now_iso_utc(),
            "source_proposals_path": str(proposals_path),
            "source_job_id": "job-1",
            "notes": None,
        },
        "decisions": [
            {"proposal_id": "job-1:name", "decision": "approved", "decided_at": now_iso_utc(), "reason": None}
        ],
    }

    proposals_path.write_text(json.dumps(proposals_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decisions_path.write_text(json.dumps(decisions_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload, results = apply_promotions(
        memory_db=str(mem_db),
        proposals_path=proposals_path,
        decisions_path=decisions_path,
        dry_run=True,
    )
    validate_payload_against_schema(payload, "crt_promotion_apply_result.v1.schema.json")
    assert len(results) == 1
    assert results[0]["action"] == "applied"
    assert results[0]["new_memory_id"] == "dry_run"

    conn = sqlite3.connect(str(mem_db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM memories")
    (count,) = cur.fetchone()
    conn.close()
    assert int(count) == 0


def test_apply_promotions_apply_writes_memory(tmp_path: Path) -> None:
    mem_db = tmp_path / "mem.db"
    # Use CRTMemorySystem initializer by letting the apply code create tables as needed.

    proposals_path = tmp_path / "proposals.json"
    decisions_path = tmp_path / "decisions.json"

    proposals_payload = {
        "metadata": {"version": "v1", "generated_at": now_iso_utc(), "source_job_id": "job-2", "notes": None},
        "proposals": [
            {
                "id": "job-2:title",
                "status": "proposed",
                "rationale": "test",
                "memory": {
                    "kind": "fact",
                    "lane": "notes",
                    "key": "title",
                    "value_text": "Founder",
                    "source": "user",
                    "trust": 0.7,
                    "confidence": 0.9,
                    "supersedes_id": None,
                    "provenance": {"memory_id": "m2", "job_id": "job-2"},
                    "evidence": [
                        {"source_type": "memory", "memory_id": "m2", "url": None, "quote_text": None, "timestamp": None}
                    ],
                },
            }
        ],
    }
    decisions_payload = {
        "metadata": {
            "version": "v1",
            "generated_at": now_iso_utc(),
            "source_proposals_path": str(proposals_path),
            "source_job_id": "job-2",
            "notes": None,
        },
        "decisions": [
            {"proposal_id": "job-2:title", "decision": "approved", "decided_at": now_iso_utc(), "reason": None}
        ],
    }

    proposals_path.write_text(json.dumps(proposals_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decisions_path.write_text(json.dumps(decisions_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload, results = apply_promotions(
        memory_db=str(mem_db),
        proposals_path=proposals_path,
        decisions_path=decisions_path,
        dry_run=False,
    )
    validate_payload_against_schema(payload, "crt_promotion_apply_result.v1.schema.json")
    assert results[0]["action"] == "applied"
    assert results[0]["new_memory_id"] not in (None, "dry_run")

    conn = sqlite3.connect(str(mem_db))
    cur = conn.cursor()
    cur.execute("SELECT text, context_json FROM memories")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert "FACT: title = Founder" in (row[0] or "")
    assert row[1] is not None
    ctx = json.loads(row[1])
    assert "promotion" in ctx
