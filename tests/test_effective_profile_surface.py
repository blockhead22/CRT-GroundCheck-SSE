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


def test_effective_profile_surfaces_cross_thread_authoritative_facts(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    store = client.post(
        "/api/memory/store",
        json={
            "thread_id": "default",
            "text": "My favorite color is orange",
            "source": "user",
            "channel": "webchat",
            "origin": "test:favorite-color:default",
            "authority": "confirmed",
            "kind": "user_fact",
        },
    )
    assert store.status_code == 200

    facts = client.get("/api/facts/structured", params={"thread_id": "openclaw", "scope": "effective"})
    assert facts.status_code == 200
    facts_body = facts.json() or {}
    favorite_color = (facts_body.get("facts") or {}).get("favorite_color") or {}
    assert favorite_color.get("value") == "orange"
    assert favorite_color.get("source_surface") == "global_profile"
    assert favorite_color.get("source_thread") == "default"

    profile = client.get("/api/profile", params={"thread_id": "openclaw"})
    assert profile.status_code == 200
    profile_body = profile.json() or {}
    assert (profile_body.get("slots") or {}).get("favorite_color") == "orange"

    searched = client.get(
        "/api/facts/search",
        params={"thread_id": "openclaw", "scope": "effective", "q": "favorite color"},
    )
    assert searched.status_code == 200
    items = searched.json() or []
    assert items
    assert items[0]["slot"] == "favorite_color"
    assert items[0]["value"] == "orange"

    answer = rag.query_with_intent("What is my favorite color?", thread_id="openclaw")
    assert "orange" in str(answer.get("answer") or "").lower()
