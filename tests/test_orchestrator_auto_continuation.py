from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.governed_task import GovernedTaskStatus
from routes.chat_orchestrator_runner import run_orchestrator
from routes.chat_runtime import ChatStreamRuntime
from routes.models import ChatSendRequest


def _parse_sse_events(chunks: List[str]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


class _DummyEventBus:
    def emit_sync(self, *args, **kwargs) -> None:
        return None


class _DummyMemory:
    db_path = None


class _DummyEngine:
    memory = _DummyMemory()


class _DummyOutbox:
    def push(self, **kwargs) -> None:
        return None


class _DummyRunLog:
    def get_recent_runs(self, limit: int = 1):
        return []


class _DummySessionState:
    cumulative_density = 0.0
    open_contradiction_count = 0
    total_trust_delta = 0.0
    turn_count = 0
    memories_confirmed = 0


class _DummyBrain:
    _model = "dummy"


def _build_runtime(tmp_path: Path, message: str) -> tuple[ChatStreamRuntime, ThreadSessionDB]:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                get_engine=lambda thread_id: _DummyEngine(),
            )
        )
    )
    runtime = ChatStreamRuntime(
        req=ChatSendRequest(thread_id="auto-cont", message=message),
        request=request,
        authorization=None,
        uid=1,
        safe_print=lambda msg: None,
        session_db=db,
        event_bus=_DummyEventBus(),
    )
    return runtime, db


def test_orchestrator_auto_continues_to_completion(monkeypatch, tmp_path: Path) -> None:
    runtime, db = _build_runtime(tmp_path, "start")

    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "cloud_openai" if key == "generation_mode" else default)
    monkeypatch.setattr("personal_agent.cookie_orchestrator.OpenAIBrain", lambda model="gpt-4o": _DummyBrain())
    monkeypatch.setattr("personal_agent.cookie_orchestrator.ClaudeCliBrain", lambda: _DummyBrain())
    monkeypatch.setattr("personal_agent.outbox.get_outbox", lambda: _DummyOutbox())
    monkeypatch.setattr("personal_agent.agent_run_log.get_run_log_db", lambda: _DummyRunLog())
    monkeypatch.setattr("personal_agent.session_state.get_or_create_session", lambda thread_id: _DummySessionState())

    class _FakeOrchestrator:
        def __init__(self, brain, memory_system, max_iterations):
            self.max_iterations = max_iterations

        def run(self, message, conversation_history=None, intent_type=None, route=None):
            if message == "start":
                yield {"type": "response", "content": "Phase 1.\n"}
                yield {
                    "type": "followup_suggest",
                    "followups": ["continue phase 2"],
                    "complete": False,
                }
                return
            yield {"type": "response", "content": "Phase 2 done.\n"}
            yield {
                "type": "followup_suggest",
                "followups": ["optional"],
                "complete": True,
            }

    monkeypatch.setattr("personal_agent.cookie_orchestrator.Orchestrator", _FakeOrchestrator)

    events = _parse_sse_events(list(run_orchestrator(runtime, SimpleNamespace(intent_type="research", route="task"), "layer4", None)))
    done = next(event for event in events if event["type"] == "done")

    assert any(event["type"] == "status" and "Continuing with: continue phase 2" in event["content"] for event in events)
    assert done["metadata"]["continuations"] == 1
    assert "Phase 1." in done["content"]
    assert "Phase 2 done." in done["content"]
    assert db.get_active_governed_task("auto-cont") is None


def test_orchestrator_auto_continuation_limit_leaves_needs_followup(monkeypatch, tmp_path: Path) -> None:
    runtime, db = _build_runtime(tmp_path, "phase0")

    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "cloud_openai" if key == "generation_mode" else default)
    monkeypatch.setattr("personal_agent.cookie_orchestrator.OpenAIBrain", lambda model="gpt-4o": _DummyBrain())
    monkeypatch.setattr("personal_agent.cookie_orchestrator.ClaudeCliBrain", lambda: _DummyBrain())
    monkeypatch.setattr("personal_agent.outbox.get_outbox", lambda: _DummyOutbox())
    monkeypatch.setattr("personal_agent.agent_run_log.get_run_log_db", lambda: _DummyRunLog())
    monkeypatch.setattr("personal_agent.session_state.get_or_create_session", lambda thread_id: _DummySessionState())

    class _LoopingOrchestrator:
        def __init__(self, brain, memory_system, max_iterations):
            self.max_iterations = max_iterations

        def run(self, message, conversation_history=None, intent_type=None, route=None):
            next_index = int(message.replace("phase", "")) + 1 if message.startswith("phase") else 1
            yield {"type": "response", "content": f"{message} done.\n"}
            yield {
                "type": "followup_suggest",
                "followups": [f"phase{next_index}"],
                "complete": False,
            }

    monkeypatch.setattr("personal_agent.cookie_orchestrator.Orchestrator", _LoopingOrchestrator)

    events = _parse_sse_events(list(run_orchestrator(runtime, SimpleNamespace(intent_type="research", route="task"), "layer4", None)))
    done = next(event for event in reversed(events) if event["type"] == "done")

    assert any(event["type"] == "status" and event["content"] == "Auto-continuation limit reached" for event in events)
    assert any(
        event["type"] == "followup_suggest"
        and event.get("metadata", {}).get("auto_continuation_limit_reached") is True
        for event in events
    )
    assert done["metadata"]["auto_continuation_limit_reached"] is True

    active = db.get_active_governed_task("auto-cont")
    assert active is not None
    assert active["status"] == GovernedTaskStatus.NEEDS_FOLLOWUP.value
    assert active["pending_followups"] == ["phase4"]
