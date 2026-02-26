from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_rag import CRTEnhancedRAG
from routes import chat as chat_routes
from routes.models import ChatSendResponse


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    profile_db = tmp_path / "profile.db"
    return CRTEnhancedRAG(
        memory_db=str(mem_db),
        ledger_db=str(led_db),
        profile_db=str(profile_db),
        llm_client=FakeLLM(),
    )


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def test_continuity_augmented_text_does_not_trigger_contradiction_spam(rag: CRTEnhancedRAG):
    before = len(rag.ledger.get_open_contradictions(limit=200))
    rag.query("My name is Nick Block.")
    augmented = (
        "hello\n\n"
        "[CONTINUITY INSTRUCTION] Treat this as a follow-up.\n"
        "[RECENT CONVERSATION CONTEXT]\n"
        "User: My name is Aether\n"
        "Assistant: Thanks."
    )

    out = rag.query(augmented)

    assert out.get("contradiction_detected") is False
    after = len(rag.ledger.get_open_contradictions(limit=200))
    assert after == before


def test_nickname_history_query_bypasses_contradiction_prompt(rag: CRTEnhancedRAG):
    rag.query("My name is Nick Block.")
    rag.query("Call me Nicky.")

    out = rag.query("what other nicknames did i say i had?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "name_history"
    assert out.get("contradiction_detected") is False
    assert "nick block" in ans
    assert "nicky" in ans


def test_continuity_helper_avoids_short_message_contamination():
    history = [
        {"role": "user", "content": "What were the top three highlights?"},
        {"role": "assistant", "content": "I can summarize those highlights."},
    ]

    unchanged = chat_routes._augment_query_with_continuity(
        message="hello",
        history_messages=history,
    )
    assert unchanged == "hello"

    augmented = chat_routes._augment_query_with_continuity(
        message="tell me the highlights",
        history_messages=history,
    )
    assert "[RECENT CONVERSATION CONTEXT]" in augmented


def test_stream_uses_shared_pipeline_and_surfaces_thinking(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(chat_routes.router)

    def fake_shared_pipeline(req, request) -> ChatSendResponse:
        return ChatSendResponse(
            answer="Final streamed answer.",
            response_type="speech",
            gates_passed=True,
            gate_reason="ok",
            session_id="s1",
            metadata={"thinking": "Step A. Step B."},
        )

    monkeypatch.setattr(chat_routes, "_run_shared_chat_pipeline", fake_shared_pipeline)
    client = TestClient(app)

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "stream_t", "message": "hi"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    event_types = [e.get("type") for e in events]

    assert "thinking_start" in event_types
    assert "thinking_end" in event_types
    assert "token" in event_types
    assert "done" in event_types
    assert "error" not in event_types

    done = next(e for e in events if e.get("type") == "done")
    assert done.get("content") == "Final streamed answer."
    assert done.get("metadata", {}).get("gate_reason") == "ok"


def test_stream_think_fallback_no_thinking_still_completes(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(chat_routes.router)

    def fake_shared_pipeline(req, request) -> ChatSendResponse:
        return ChatSendResponse(
            answer="No thinking payload.",
            response_type="speech",
            gates_passed=True,
            gate_reason="ok",
            session_id="s2",
            metadata={},
        )

    monkeypatch.setattr(chat_routes, "_run_shared_chat_pipeline", fake_shared_pipeline)
    client = TestClient(app)

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "stream_t2", "message": "hi"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    event_types = [e.get("type") for e in events]
    assert "error" not in event_types
    done = next(e for e in events if e.get("type") == "done")
    assert done.get("content") == "No thinking payload."
