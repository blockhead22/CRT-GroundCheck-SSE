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


def test_sync_write_duplicate_is_idempotent_by_origin_and_text(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    payload = {
        "thread_id": "openclaw",
        "text": "My favorite color is orange",
        "source": "user",
        "channel": "system",
        "origin": "USER.md:Favorite Color",
        "authority": "confirmed",
        "kind": "user_fact",
        "context": {"type": "sync_user_md", "field": "Favorite Color"},
    }

    first = client.post("/api/memory/store", json=payload)
    second = client.post("/api/memory/store", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    first_memory = (first.json() or {}).get("memory") or {}
    second_memory = (second.json() or {}).get("memory") or {}
    assert second_memory.get("memory_id") == first_memory.get("memory_id")

    related = [
        m for m in rag.memory._load_all_memories()
        if str(getattr(m, "origin", "") or "") == "USER.md:Favorite Color"
    ]
    active = [m for m in related if not bool(getattr(m, "deprecated", False))]
    assert len(active) == 1

    events = rag.memory.get_memory_events(first_memory.get("memory_id"))
    assert any(event.get("event_type") == "sync_duplicate_skipped" for event in events)


def test_sync_write_replaces_prior_same_origin_value_without_deleting_history(tmp_path: Path):
    rag = _build_rag(tmp_path)

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag

    client = TestClient(app)
    first = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My favorite color is orange",
            "source": "user",
            "channel": "system",
            "origin": "USER.md:Favorite Color",
            "authority": "confirmed",
            "kind": "user_fact",
            "context": {"type": "sync_user_md", "field": "Favorite Color"},
        },
    )
    second = client.post(
        "/api/memory/store",
        json={
            "thread_id": "openclaw",
            "text": "My favorite color is blue",
            "source": "user",
            "channel": "system",
            "origin": "USER.md:Favorite Color",
            "authority": "confirmed",
            "kind": "user_fact",
            "context": {"type": "sync_user_md", "field": "Favorite Color"},
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    memories = [
        m for m in rag.memory._load_all_memories()
        if str(getattr(m, "origin", "") or "") == "USER.md:Favorite Color"
    ]
    assert len(memories) == 2

    active = [m for m in memories if not bool(getattr(m, "deprecated", False))]
    deprecated = [m for m in memories if bool(getattr(m, "deprecated", False))]
    assert len(active) == 1
    assert len(deprecated) == 1
    assert str(getattr(active[0], "text", "") or "").endswith("blue")
    assert str(getattr(deprecated[0], "text", "") or "").endswith("orange")

    new_memory_id = ((second.json() or {}).get("memory") or {}).get("memory_id")
    events = rag.memory.get_memory_events(new_memory_id)
    assert any(event.get("event_type") == "sync_replaced" for event in events)
