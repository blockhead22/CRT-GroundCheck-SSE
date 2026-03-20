from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource
from personal_agent.fact_store import FactStore
from personal_agent.user_profile import GlobalUserProfile
from routes import threads as thread_routes


class _FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


def _build_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
        llm_client=_FakeLLM(),
    )


def test_thread_reset_clears_shared_fact_rows_for_target_thread(tmp_path: Path, monkeypatch):
    rag = _build_rag(tmp_path)
    rag.ingest_memory_write(
        text="My name is Nick",
        confidence=0.95,
        source=MemorySource.USER,
        thread_id="openclaw",
    )
    rag.ingest_memory_write(
        text="My name is Mike",
        confidence=0.95,
        source=MemorySource.USER,
        thread_id="other-thread",
    )

    profile_path = tmp_path / "profile.db"

    def _fake_paths_map(tid: str):
        return {
            "memory": Path(rag.memory.db_path),
            "ledger": Path(rag.ledger.db_path),
            "facts": Path(rag.fact_store.db_path),
        }

    monkeypatch.setattr(thread_routes, "_thread_db_paths_map", _fake_paths_map)
    monkeypatch.setattr(
        thread_routes,
        "GlobalUserProfile",
        lambda: GlobalUserProfile(db_path=str(profile_path), use_llm_extraction=False),
    )

    app = FastAPI()
    app.include_router(thread_routes.router)
    app.state.engines = {"openclaw": rag}
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    resp = client.post("/api/thread/reset", json={"thread_id": "openclaw", "target": "all"})

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("deleted", {}).get("fact_rows") is True

    fact_store = FactStore(str(rag.fact_store.db_path))
    assert fact_store.get_all_facts(thread_id="openclaw") == {}
    remaining = fact_store.get_all_facts(thread_id="other-thread")
    assert (remaining.get("user.name") or {}).get("value") == "Mike"

    profile = GlobalUserProfile(db_path=str(profile_path), use_llm_extraction=False)
    facts = profile.get_all_facts()
    assert str(getattr(facts.get("name"), "value", "") or "") == "Mike"
