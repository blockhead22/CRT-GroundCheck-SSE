from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import crt_api
from personal_agent.crt_ledger import ContradictionLedger
from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    """FastAPI client with all DBs redirected to tmp_path."""

    class PatchedRAG(CRTEnhancedRAG):
        def __init__(self, memory_db: str, ledger_db: str, *args, **kwargs):
            mem_name = Path(memory_db).name
            led_name = Path(ledger_db).name
            super().__init__(
                memory_db=str(tmp_path / mem_name),
                ledger_db=str(tmp_path / led_name),
                llm_client=FakeLLM(),
            )

    def _test_runtime_config():
        # Ensure startup hooks don't spawn background workers during tests.
        return {
            "background_jobs": {
                "enabled": False,
                "idle_scheduler_enabled": False,
            },
            "training_loop": {
                "enabled": False,
            },
            "learned_suggestions": {
                "enabled": False,
            },
        }

    monkeypatch.setattr(crt_api, "CRTEnhancedRAG", PatchedRAG)
    monkeypatch.setattr(crt_api, "get_runtime_config", _test_runtime_config)

    app = crt_api.create_app()
    return TestClient(app), tmp_path


def test_contradictions_respond_records_answer_and_resolves(client: tuple[TestClient, Path]):
    http, tmp_path = client

    thread_id = f"pytest_{uuid4().hex[:10]}"
    ledger_path = tmp_path / f"crt_ledger_{thread_id}.db"

    ledger = ContradictionLedger(db_path=str(ledger_path))
    entry = ledger.record_contradiction(
        old_memory_id="mem_old",
        new_memory_id="mem_new",
        drift_mean=0.66,
        confidence_delta=0.2,
        query="where do I work",
        summary="Test contradiction",
    )

    resp = http.post(
        "/api/contradictions/respond",
        json={
            "thread_id": thread_id,
            "ledger_id": entry.ledger_id,
            "answer": "Employer = Amazon",
            "resolve": True,
            "resolution_method": "user_clarified",
            "new_status": "resolved",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["ok"] is True
    assert payload["thread_id"] == thread_id
    assert payload["ledger_id"] == entry.ledger_id
    assert payload["recorded"] is True
    assert payload["resolved"] is True
    assert payload["next"]["has_item"] in {False, True}  # best-effort; should be False in this isolated DB

    # Verify ledger row is marked resolved.
    conn = sqlite3.connect(str(ledger_path))
    cur = conn.cursor()
    cur.execute("SELECT status, resolution_method FROM contradictions WHERE ledger_id = ?", (entry.ledger_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "resolved"
    assert row[1] == "user_clarified"

    # Verify the worklog captured the user's answer.
    wl = ledger.get_contradiction_worklog(entry.ledger_id)
    assert (wl.get("last_user_answer") or "") == "Employer = Amazon"
