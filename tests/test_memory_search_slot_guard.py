from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_rag import CRTEnhancedRAG
from routes import memory as memory_routes


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


def test_memory_search_returns_empty_for_slot_query_without_matching_slot_support(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    store = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My name is Nick",
            "source": "user",
            "channel": "webchat",
            "origin": "test:name",
            "authority": "confirmed",
            "kind": "user_fact",
        },
    )
    assert store.status_code == 200

    search = client.get(
        "/api/memory/search",
        params={"thread_id": "openclaw", "q": "favorite color", "k": 10},
    )

    assert search.status_code == 200
    assert search.json() == []
