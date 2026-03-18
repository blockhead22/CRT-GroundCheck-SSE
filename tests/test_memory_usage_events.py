from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG
from routes import memory as memory_routes


class _FakeLLM:
    _SKIP_PREFIXES = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        if "[RESOLVED FACT DATA]" in prompt:
            block = prompt.split("[RESOLVED FACT DATA]", 1)[1]
            for end in ("[", "===", "User:"):
                if end in block:
                    block = block[:block.index(end)]
            past_header = False
            for line in block.splitlines():
                text = line.strip()
                if "found:" in text.lower():
                    past_header = True
                    continue
                if past_header and text and not any(text.startswith(prefix) for prefix in self._SKIP_PREFIXES):
                    return text
        return "OK"


def _build_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
        llm_client=_FakeLLM(),
    )


def _build_client(rag: CRTEnhancedRAG) -> TestClient:
    app = FastAPI()
    app.include_router(memory_routes.router)
    app.state.get_engine = lambda thread_id: rag
    return TestClient(app)


def test_query_logs_retrieval_prompt_and_slot_hits(tmp_path: Path) -> None:
    rag = _build_rag(tmp_path)
    memory = rag.memory.store_memory(
        text="My favorite color is orange.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="default",
        channel="webchat",
        kind="user_fact",
    )

    out = rag.query("What's my favorite color?", thread_id="default")
    assert "orange" in str(out.get("answer") or "").lower()

    events = rag.memory.get_memory_events(memory.memory_id)
    event_types = {event["event_type"] for event in events}
    assert "retrieved" in event_types
    assert "prompt_included" in event_types
    assert "slot_selected" in event_types

    summary = rag.memory.get_memory_usage_summary(thread_id="default", limit=10)
    summary_item = next(item for item in summary if item["memory_id"] == memory.memory_id)
    assert summary_item["retrieved_hits"] >= 1
    assert summary_item["prompt_included_hits"] >= 1
    assert summary_item["slot_selected_hits"] >= 1


def test_guard_blocked_events_show_up_in_usage_api(tmp_path: Path) -> None:
    rag = _build_rag(tmp_path)
    old_mem = rag.memory.store_memory(
        text="I work at Amazon.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="default",
        channel="webchat",
        kind="user_fact",
    )
    new_mem = rag.memory.store_memory(
        text="I work at Microsoft.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="default",
        channel="webchat",
        kind="user_fact",
    )

    rag.ledger.record_contradiction(
        old_memory_id=old_mem.memory_id,
        new_memory_id=new_mem.memory_id,
        drift_mean=0.9,
        confidence_delta=0.0,
        query="employer contradiction",
        old_text=old_mem.text,
        new_text=new_mem.text,
        old_vector=old_mem.vector,
        new_vector=new_mem.vector,
    )

    rag.query("Where do I work?", thread_id="default")

    client = _build_client(rag)
    events_resp = client.get(
        f"/api/memory/{old_mem.memory_id}/events",
        params={"thread_id": "default", "event_type": "guard_blocked"},
    )
    assert events_resp.status_code == 200
    events = events_resp.json() or []
    assert any(event.get("event_type") == "guard_blocked" for event in events)

    summary_resp = client.get(
        "/api/memory/usage/summary",
        params={"thread_id": "default", "limit": 10},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json() or []
    old_item = next(item for item in summary if item.get("memory_id") == old_mem.memory_id)
    new_item = next(item for item in summary if item.get("memory_id") == new_mem.memory_id)
    assert old_item.get("guard_blocked_hits", 0) >= 1
    assert new_item.get("guard_blocked_hits", 0) >= 1
