from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_core import MemorySource
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


def test_dashboard_overview_reports_thread_scope_separately_from_global_totals(tmp_path: Path) -> None:
    rag = _build_rag(tmp_path)

    rag.memory.store_memory(
        "My favorite color is orange",
        confidence=0.95,
        source=MemorySource.USER,
        thread_id="thread_a",
        authority="confirmed",
        channel="webchat",
        origin="test:thread-a",
        kind="user_fact",
    )
    rag.memory.store_memory(
        "My favorite color is blue",
        confidence=0.95,
        source=MemorySource.USER,
        thread_id="thread_b",
        authority="confirmed",
        channel="webchat",
        origin="test:thread-b",
        kind="user_fact",
    )
    rag.memory.store_memory(
        "I am Aether, a personal AI assistant.",
        confidence=1.0,
        source=MemorySource.SYSTEM,
        authority="provisional",
        channel="system",
        origin="system:self_knowledge",
        kind="observation",
    )

    rag.ledger.record_contradiction(
        old_memory_id="old-a",
        new_memory_id="new-a",
        drift_mean=0.8,
        confidence_delta=0.1,
        summary="thread_a contradiction",
        old_text="old a",
        new_text="new a",
        thread_id="thread_a",
    )
    rag.ledger.record_contradiction(
        old_memory_id="old-b",
        new_memory_id="new-b",
        drift_mean=0.7,
        confidence_delta=0.1,
        summary="thread_b contradiction",
        old_text="old b",
        new_text="new b",
        thread_id="thread_b",
    )

    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda _thread_id: rag

    client = TestClient(app)
    resp = client.get("/api/dashboard/overview", params={"thread_id": "thread_a"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == "thread_a"
    assert body["memories_total"] == 1
    assert body["global_memories_total"] == 3
    assert body["effective_facts_total"] == 1
    assert body["open_contradictions"] == 1
    assert body["memory_scope"] == "thread"
    assert body["contradiction_scope"] == "thread"
    assert body["belief_speech_scope"] == "global_7d"
