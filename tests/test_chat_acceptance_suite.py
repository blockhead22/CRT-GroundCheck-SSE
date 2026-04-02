from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.governed_task import GovernedTaskStatus, GovernedTaskWaitKind
from personal_agent.task_agent import TaskIntent
from routes import chat as chat_routes
import routes.tasks as tasks_module
from routes.chat_governed_resume import ResumeOutcome
from routes.chat_runtime import StreamTerminalResult
from routes.tasks import router as tasks_router


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.include_router(tasks_router)
    app.state.get_engine = lambda thread_id: None
    app.state.get_llm_client = lambda: None
    app.state.scheduled_tasks_db_path = ""
    return app


def _noop_resume(*args, **kwargs):
    if False:
        yield ""
    return None


@pytest.fixture()
def client_and_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(tasks_module, "get_thread_session_db", lambda: db)
    app = _build_app()
    client = TestClient(app)
    return client, db


def _patch_common_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", _noop_resume)
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"agent_loop": {"enabled": False}})
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": default)
    monkeypatch.setattr(
        "personal_agent.task_agent.classify_intent",
        lambda message, active_task=None: TaskIntent(route="task", intent_type="research", slots={}, confidence=0.9, reason="test"),
    )
    monkeypatch.setattr(
        "personal_agent.routing_beliefs.should_orchestrate",
        lambda message, intent: SimpleNamespace(route="orchestrator", confidence=0.95, reasons=["test"]),
    )


def _patch_common_agent_loop(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_acceptance_ask_user_suspend_resume_and_recovery(
    monkeypatch: pytest.MonkeyPatch, client_and_db
) -> None:
    client, db = client_and_db
    task_ids: List[str] = []

    _patch_common_orchestrator(monkeypatch)

    def fake_orchestrator(runtime, task_intent, routing_reason, recent_history):
        task = runtime.ensure_governed_task(objective=runtime.req.message, max_iterations=10)
        runtime.update_governed_task(
            status=GovernedTaskStatus.AWAITING_USER.value,
            wait_kind=GovernedTaskWaitKind.ASK_USER.value,
            question="Which path should I take?",
            orch_answer_so_far="I found two options.\n\n",
        )
        runtime.session_db.store_suspended_loop(
            runtime.req.thread_id,
            {
                "objective": runtime.req.message,
                "steps_done": [],
                "question": "Which path should I take?",
                "orch_answer_so_far": "I found two options.\n\n",
                "remaining_iterations": 6,
            },
        )
        task_ids.append(str(task["task_id"]))
        yield runtime.emit({"type": "token", "content": "Which path should I take?"})
        yield runtime.emit(
            {
                "type": "done",
                "content": "I found two options.\n\n",
                "metadata": {"loop_suspended": True, "loop_question": "Which path should I take?", "response_type": "ask_user"},
            }
        )
        return StreamTerminalResult(terminal=True, handled=True, metadata={"loop_suspended": True})

    def resume_stub(runtime, recent_history=None):
        active = runtime.session_db.get_active_governed_task(runtime.req.thread_id)
        if not active:
            if False:
                yield ""
            return None
        runtime.governed_task = active
        runtime.update_governed_task(status=GovernedTaskStatus.RUNNING.value, wait_kind=None, question=None)
        yield runtime.emit({"type": "token", "content": "Resuming with your answer."})
        runtime.session_db.clear_suspended_loop(runtime.req.thread_id)
        runtime.governed_task = runtime.session_db.complete_governed_task(str(active["task_id"]), "Done after resume.") or active
        yield runtime.emit({"type": "done", "content": "Done after resume.", "metadata": {"response_type": "speech"}})
        return ResumeOutcome(handled=True, terminal=True, user_confirmed=True)

    monkeypatch.setattr(chat_routes, "run_orchestrator", fake_orchestrator)

    first = client.post("/api/chat/stream", json={"thread_id": "accept-ask", "message": "research the architecture"})
    assert first.status_code == 200
    first_events = _parse_sse_events(first.text)
    first_done = next(event for event in first_events if event["type"] == "done")
    assert first_done["metadata"]["loop_suspended"] is True
    assert first_done["metadata"]["task_id"] == task_ids[0]

    active = client.get("/api/tasks/active", params={"thread_id": "accept-ask"}).json()["task"]
    assert active["task_id"] == task_ids[0]
    assert active["status"] == GovernedTaskStatus.AWAITING_USER.value
    assert active["wait_kind"] == GovernedTaskWaitKind.ASK_USER.value

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", resume_stub)
    second = client.post("/api/chat/stream", json={"thread_id": "accept-ask", "message": "take the safer path"})
    assert second.status_code == 200
    second_events = _parse_sse_events(second.text)
    second_done = next(event for event in second_events if event["type"] == "done")
    assert second_done["content"] == "Done after resume."
    assert second_done["metadata"]["task_id"] == task_ids[0]
    assert client.get("/api/tasks/active", params={"thread_id": "accept-ask"}).json()["task"] is None
    assert db.get_suspended_loop("accept-ask") is None


def test_acceptance_checkpoint_approve_roundtrip(monkeypatch: pytest.MonkeyPatch, client_and_db) -> None:
    client, _db = client_and_db
    task_ids: List[str] = []

    _patch_common_agent_loop(monkeypatch)

    def fake_agent_runner(runtime, task_intent, active_task, user_confirmed, recent_history):
        task = runtime.ensure_governed_task(objective=runtime.req.message, max_iterations=3)
        runtime.session_db.store_pending_checkpoint(
            runtime.req.thread_id,
            intent_data={"route": "task", "intent_type": task_intent.intent_type, "_agent_loop": True},
            checkpoint_tier="medium",
            metadata={"tool_name": "write_file"},
        )
        runtime.update_governed_task(
            status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
            wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
            checkpoint_tier="medium",
            question="Approve write_file?",
        )
        task_ids.append(str(task["task_id"]))
        yield runtime.emit({"type": "agent_checkpoint", "content": "Approve write_file?", "metadata": {"checkpoint_tier": "medium", "tool_name": "write_file"}})
        yield runtime.emit({"type": "done", "content": "Approve write_file?", "metadata": {"checkpoint_pending": True, "agent_loop": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"checkpoint_pending": True})

    def approve_resume(runtime, recent_history=None):
        active = runtime.session_db.get_active_governed_task(runtime.req.thread_id)
        pending = runtime.session_db.get_pending_checkpoint(runtime.req.thread_id)
        if not active or not pending:
            if False:
                yield ""
            return None
        runtime.governed_task = active
        runtime.session_db.clear_pending_checkpoint(runtime.req.thread_id)
        runtime.update_governed_task(status=GovernedTaskStatus.RUNNING.value, wait_kind=None, checkpoint_tier=None, question=None)
        yield runtime.emit({"type": "token", "content": "Approved. Continuing."})
        runtime.governed_task = runtime.session_db.complete_governed_task(str(active["task_id"]), "Checkpoint complete.") or active
        yield runtime.emit({"type": "done", "content": "Checkpoint complete.", "metadata": {"agent_loop": True}})
        return ResumeOutcome(handled=True, terminal=True, user_confirmed=True)

    monkeypatch.setattr(chat_routes, "run_agent_tool_loop", fake_agent_runner)

    first = client.post("/api/chat/stream", json={"thread_id": "accept-cp-ok", "message": "refactor the file"})
    assert first.status_code == 200
    first_done = next(event for event in _parse_sse_events(first.text) if event["type"] == "done")
    assert first_done["metadata"]["checkpoint_pending"] is True
    assert first_done["metadata"]["task_id"] == task_ids[0]

    active = client.get("/api/tasks/active", params={"thread_id": "accept-cp-ok"}).json()["task"]
    assert active["status"] == GovernedTaskStatus.AWAITING_CHECKPOINT.value
    assert active["wait_kind"] == GovernedTaskWaitKind.CHECKPOINT.value

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", approve_resume)
    second = client.post("/api/chat/stream", json={"thread_id": "accept-cp-ok", "message": "yes"})
    assert second.status_code == 200
    second_done = next(event for event in _parse_sse_events(second.text) if event["type"] == "done")
    assert second_done["content"] == "Checkpoint complete."
    assert second_done["metadata"]["task_id"] == task_ids[0]
    assert client.get("/api/tasks/active", params={"thread_id": "accept-cp-ok"}).json()["task"] is None


def test_acceptance_checkpoint_deny_cancels_task(monkeypatch: pytest.MonkeyPatch, client_and_db) -> None:
    client, _db = client_and_db
    task_ids: List[str] = []

    _patch_common_agent_loop(monkeypatch)

    def fake_agent_runner(runtime, task_intent, active_task, user_confirmed, recent_history):
        task = runtime.ensure_governed_task(objective=runtime.req.message, max_iterations=3)
        runtime.session_db.store_pending_checkpoint(
            runtime.req.thread_id,
            intent_data={"route": "task", "intent_type": task_intent.intent_type, "_agent_loop": True},
            checkpoint_tier="medium",
            metadata={"tool_name": "write_file"},
        )
        runtime.update_governed_task(
            status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
            wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
            checkpoint_tier="medium",
            question="Approve write_file?",
        )
        task_ids.append(str(task["task_id"]))
        yield runtime.emit({"type": "done", "content": "Approve write_file?", "metadata": {"checkpoint_pending": True, "agent_loop": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"checkpoint_pending": True})

    def deny_resume(runtime, recent_history=None):
        active = runtime.session_db.get_active_governed_task(runtime.req.thread_id)
        pending = runtime.session_db.get_pending_checkpoint(runtime.req.thread_id)
        if not active or not pending:
            if False:
                yield ""
            return None
        runtime.governed_task = active
        runtime.session_db.clear_pending_checkpoint(runtime.req.thread_id)
        runtime.governed_task = runtime.session_db.cancel_governed_task(str(active["task_id"]), "Task cancelled. What would you like to do instead?") or active
        yield runtime.emit({"type": "task_cancelled", "content": "Task cancelled. What would you like to do instead?"})
        yield runtime.emit({"type": "done", "content": "Task cancelled. What would you like to do instead?", "metadata": {"task_cancelled": True}})
        return ResumeOutcome(handled=True, terminal=True, user_confirmed=False)

    monkeypatch.setattr(chat_routes, "run_agent_tool_loop", fake_agent_runner)
    client.post("/api/chat/stream", json={"thread_id": "accept-cp-no", "message": "refactor the file"})

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", deny_resume)
    second = client.post("/api/chat/stream", json={"thread_id": "accept-cp-no", "message": "no"})
    assert second.status_code == 200
    events = _parse_sse_events(second.text)
    assert any(event["type"] == "task_cancelled" for event in events)
    done = next(event for event in events if event["type"] == "done")
    assert done["metadata"]["task_cancelled"] is True
    assert done["metadata"]["task_id"] == task_ids[0]
    assert client.get("/api/tasks/active", params={"thread_id": "accept-cp-no"}).json()["task"] is None


def test_acceptance_followup_complete_false_persists_needs_followup(
    monkeypatch: pytest.MonkeyPatch, client_and_db
) -> None:
    client, _db = client_and_db

    _patch_common_orchestrator(monkeypatch)

    def fake_orchestrator(runtime, task_intent, routing_reason, recent_history):
        runtime.ensure_governed_task(objective=runtime.req.message, max_iterations=10)
        runtime.update_governed_task(
            status=GovernedTaskStatus.NEEDS_FOLLOWUP.value,
            pending_followups=["Run tests", "Open the failing file"],
            orch_answer_so_far="I reviewed the code.",
        )
        yield runtime.emit(
            {
                "type": "followup_suggest",
                "content": "Suggested follow-ups",
                "metadata": {"followups": ["Run tests", "Open the failing file"], "complete": False},
            }
        )
        yield runtime.emit({"type": "done", "content": "I reviewed the code.", "metadata": {"agent_loop": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"agent_loop": True})

    monkeypatch.setattr(chat_routes, "run_orchestrator", fake_orchestrator)

    resp = client.post("/api/chat/stream", json={"thread_id": "accept-followup", "message": "review the project state"})
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    followup = next(event for event in events if event["type"] == "followup_suggest")
    assert followup["metadata"]["complete"] is False

    active = client.get("/api/tasks/active", params={"thread_id": "accept-followup"}).json()["task"]
    assert active["status"] == GovernedTaskStatus.NEEDS_FOLLOWUP.value
    assert active["pending_followups"] == ["Run tests", "Open the failing file"]


def test_acceptance_failure_marks_task_failed_and_inactive(
    monkeypatch: pytest.MonkeyPatch, client_and_db
) -> None:
    client, db = client_and_db

    _patch_common_orchestrator(monkeypatch)

    def failing_orchestrator(runtime, task_intent, routing_reason, recent_history):
        task = runtime.ensure_governed_task(objective=runtime.req.message, max_iterations=10)
        runtime.governed_task = db.fail_governed_task(str(task["task_id"]), "synthetic failure") or task
        yield runtime.emit({"type": "error", "content": "synthetic failure", "metadata": {"error": True}})
        yield runtime.emit({"type": "done", "content": "synthetic failure", "metadata": {"error": True}})
        return StreamTerminalResult(terminal=True, handled=True, metadata={"error": True})

    monkeypatch.setattr(chat_routes, "run_orchestrator", failing_orchestrator)

    resp = client.post("/api/chat/stream", json={"thread_id": "accept-fail", "message": "research the architecture"})
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    assert any(event["type"] == "error" for event in events)
    assert client.get("/api/tasks/active", params={"thread_id": "accept-fail"}).json()["task"] is None
