from __future__ import annotations

from pathlib import Path

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
    class PatchedRAG(CRTEnhancedRAG):
        def __init__(self, memory_db: str, ledger_db: str, *args, **kwargs):
            mem_name = Path(memory_db).name
            led_name = Path(ledger_db).name
            profile_name = f"profile_{Path(memory_db).stem}.db"
            super().__init__(
                memory_db=str(tmp_path / mem_name),
                ledger_db=str(tmp_path / led_name),
                profile_db=str(tmp_path / profile_name),
                llm_client=FakeLLM(),
            )

    def _runtime_config():
        return {
            "background_jobs": {"enabled": False, "idle_scheduler_enabled": False},
            "training_loop": {"enabled": False},
            "learned_suggestions": {"enabled": False},
        }

    monkeypatch.setenv("CRT_SHARED_MEMORY", "true")
    monkeypatch.setattr(crt_api, "CRTEnhancedRAG", PatchedRAG)
    monkeypatch.setattr(crt_api, "get_runtime_config", _runtime_config)

    app = crt_api.create_app()
    return TestClient(app), tmp_path


def test_contradictions_endpoint_uses_shared_ledger_db(client: tuple[TestClient, Path]) -> None:
    http, tmp_path = client

    ledger_path = tmp_path / "crt_ledger_shared.db"
    ledger = ContradictionLedger(db_path=str(ledger_path))
    entry = ledger.record_contradiction(
        old_memory_id="mem_old",
        new_memory_id="mem_new",
        drift_mean=0.75,
        confidence_delta=0.1,
        query="shared contradiction check",
        summary="Shared route test contradiction",
    )

    resp = http.get("/api/contradictions", params={"thread_id": "openclaw"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload.get("error") in {None, ""}
    assert int(payload.get("count") or 0) == 1
    contradictions = payload.get("contradictions") or []
    assert len(contradictions) == 1
    assert contradictions[0].get("ledger_id") == entry.ledger_id
