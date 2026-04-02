from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.task_agent import TaskIntent
from routes import chat as chat_routes
from routes.chat_runtime import StreamTerminalResult


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _noop_resume(*args, **kwargs):
    if False:
        yield ""
    return None


@pytest.fixture()
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda thread_id: None
    app.state.get_llm_client = lambda: None
    app.state.scheduled_tasks_db_path = ""
    return app


def test_chat_stream_delegates_agent_loop_runner(monkeypatch: pytest.MonkeyPatch, app: FastAPI) -> None:
    called: dict[str, Any] = {}

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", _noop_resume)
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"agent_loop": {"enabled": True, "max_iterations": 3, "show_thinking": True}})
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "cloud_openai" if key == "generation_mode" else default)
    monkeypatch.setattr(
        "personal_agent.task_agent.classify_intent",
        lambda message, active_task=None: TaskIntent(route="task", intent_type="code_task", slots={}, confidence=0.92, reason="test"),
    )
    monkeypatch.setattr(
        "personal_agent.routing_beliefs.should_orchestrate",
        lambda message, intent: SimpleNamespace(route="task", confidence=0.2, reasons=["test"]),
    )

    def fake_runner(runtime, task_intent, active_task, user_confirmed, recent_history):
        called["intent_type"] = task_intent.intent_type
        called["thread_id"] = runtime.req.thread_id
        yield runtime.emit({"type": "token", "content": "runner token"})
        yield runtime.emit({"type": "done", "content": "runner done", "metadata": {"agent_loop": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"agent_loop": True})

    monkeypatch.setattr(chat_routes, "run_agent_tool_loop", fake_runner)

    client = TestClient(app)
    resp = client.post("/api/chat/stream", json={"thread_id": "split-agent-loop", "message": "refactor these files please"})

    assert resp.status_code == 200
    assert called == {"intent_type": "code_task", "thread_id": "split-agent-loop"}
    events = _parse_sse_events(resp.text)
    assert any(event.get("content") == "runner token" for event in events)
    assert any(event.get("content") == "runner done" and event.get("type") == "done" for event in events)


def test_chat_stream_delegates_orchestrator_runner(monkeypatch: pytest.MonkeyPatch, app: FastAPI) -> None:
    called: dict[str, Any] = {}

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", _noop_resume)
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"agent_loop": {"enabled": False}})
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": default)
    monkeypatch.setattr(
        "personal_agent.task_agent.classify_intent",
        lambda message, active_task=None: TaskIntent(route="task", intent_type="research", slots={}, confidence=0.88, reason="test"),
    )
    monkeypatch.setattr(
        "personal_agent.routing_beliefs.should_orchestrate",
        lambda message, intent: SimpleNamespace(route="orchestrator", confidence=0.95, reasons=["test"]),
    )

    def fake_runner(runtime, task_intent, routing_reason, recent_history):
        called["intent_type"] = task_intent.intent_type
        called["routing_reason"] = routing_reason
        yield runtime.emit({"type": "token", "content": "orch token"})
        yield runtime.emit({"type": "done", "content": "orch done", "metadata": {"agent_loop": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"agent_loop": True})

    monkeypatch.setattr(chat_routes, "run_orchestrator", fake_runner)

    client = TestClient(app)
    resp = client.post("/api/chat/stream", json={"thread_id": "split-orch", "message": "research the latest architecture notes"})

    assert resp.status_code == 200
    assert called == {"intent_type": "research", "routing_reason": "layer4"}
    events = _parse_sse_events(resp.text)
    assert any(event.get("content") == "orch token" for event in events)
    assert any(event.get("content") == "orch done" and event.get("type") == "done" for event in events)
