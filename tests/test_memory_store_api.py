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


def test_memory_store_endpoint_persists_authoritative_user_fact_and_updates_fact_store(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    resp = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My name is Nick",
            "source": "user",
            "channel": "system",
            "origin": "USER.md:Name",
            "authority": "confirmed",
            "kind": "user_fact",
            "context": {"type": "sync_user_md", "field": "Name"},
        },
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("stored") is True
    assert body.get("fact_store_updated") is True
    memory = body.get("memory") or {}
    assert memory.get("authority") == "confirmed"
    assert memory.get("channel") == "system"
    assert memory.get("origin") == "USER.md:Name"
    assert memory.get("kind") == "user_fact"

    fact = rag.fact_store.get_fact("user.name")
    assert fact is not None
    assert str(fact.get("value") or "").lower() == "nick"


def test_memory_store_endpoint_keeps_social_claims_provisional_and_out_of_fact_store(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    resp = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My favorite color is blue",
            "source": "user",
            "channel": "moltbook",
            "origin": "https://www.moltbook.com/posts/test",
            "authority": "confirmed",
            "kind": "user_fact",
        },
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("stored") is True
    assert body.get("fact_store_updated") is False
    memory = body.get("memory") or {}
    assert memory.get("authority") == "provisional"
    assert memory.get("channel") == "moltbook"
    assert memory.get("kind") == "observation"

    assert rag.fact_store.get_fact("user.favorite_color") is None


def test_memory_store_endpoint_does_not_flag_name_refinement_as_contradiction(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    first = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My name is Nick Block",
            "source": "user",
            "channel": "webchat",
            "origin": "test:first-name",
            "authority": "confirmed",
            "kind": "user_fact",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My name is Nick",
            "source": "user",
            "channel": "webchat",
            "origin": "test:refined-name",
            "authority": "confirmed",
            "kind": "user_fact",
        },
    )

    assert second.status_code == 200
    body = second.json() or {}
    assert body.get("contradiction_detected") is False
