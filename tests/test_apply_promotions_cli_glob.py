from __future__ import annotations

import json
from pathlib import Path

from personal_agent.artifact_store import now_iso_utc


def test_crt_apply_promotions_cli_accepts_globs(tmp_path: Path) -> None:
    proposals_dir = tmp_path / "promotions"
    approvals_dir = tmp_path / "approvals"
    proposals_dir.mkdir()
    approvals_dir.mkdir()

    proposals_path = proposals_dir / "proposals.job-1.json"
    decisions_path = approvals_dir / "decisions.job-1.20260112_000000.json"

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

    # Import inside test so it stays importable.
    from crt_apply_promotions import main

    mem_db = tmp_path / "mem.db"
    artifacts_dir = tmp_path / "artifacts"
    rc = main(
        [
            "--memory-db",
            str(mem_db),
            "--proposals",
            str(proposals_dir / "proposals.*.json"),
            "--decisions",
            str(approvals_dir / "decisions.*.json"),
            "--dry-run",
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    assert rc == 0
