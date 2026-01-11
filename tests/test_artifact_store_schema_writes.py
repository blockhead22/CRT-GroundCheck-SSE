from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from personal_agent.artifact_store import (
    make_minimal_audit_answer_record,
    now_iso_utc,
    write_audit_answer_record,
    write_background_job_artifact,
    write_promotion_proposals,
)


def test_write_audit_answer_record_validates_and_writes(tmp_path: Path) -> None:
    out = tmp_path / "audit.json"
    payload = make_minimal_audit_answer_record(
        answer_id=str(uuid4()),
        user_text="Hello",
        answer_text="Hi",
        mode="gate",
        gate_reason="assistant_profile",
    )
    write_audit_answer_record(out, payload)
    assert out.exists()


def test_write_audit_answer_record_rejects_invalid(tmp_path: Path) -> None:
    out = tmp_path / "audit.json"
    payload = {"id": "x"}  # missing required fields
    with pytest.raises(ValueError):
        write_audit_answer_record(out, payload)


def test_write_background_job_artifact_validates(tmp_path: Path) -> None:
    out = tmp_path / "job.json"
    payload = {
        "job": {
            "id": str(uuid4()),
            "type": "summarize_session",
            "status": "queued",
            "priority": 0,
            "created_at": now_iso_utc(),
            "started_at": None,
            "finished_at": None,
            "payload": {"session_id": "abc"},
            "error": None,
        },
        "events": [],
        "artifacts": [],
        "result": None,
    }
    write_background_job_artifact(out, payload)
    assert out.exists()


def test_write_promotion_proposals_validates(tmp_path: Path) -> None:
    out = tmp_path / "proposals.json"
    payload = {
        "metadata": {"version": "v1", "generated_at": now_iso_utc(), "source_job_id": None, "notes": None},
        "proposals": [
            {
                "id": str(uuid4()),
                "status": "proposed",
                "rationale": "Extracted from chat",
                "memory": {
                    "kind": "fact",
                    "lane": "notes",
                    "key": "title",
                    "value_text": "Founder",
                    "source": "chat",
                    "trust": 0.8,
                    "confidence": 0.6,
                    "supersedes_id": None,
                    "provenance": {"source": "test"},
                    "evidence": [{"source_type": "chat", "memory_id": None, "url": None, "quote_text": "...", "timestamp": None}],
                },
            }
        ],
    }
    write_promotion_proposals(out, payload)
    assert out.exists()
