from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.governed_task import GovernedTask, GovernedTaskStatus
from personal_agent.task_agent import TaskIntent
from routes import chat as chat_routes


class _StubMemory:
    db_path = ":memory:"


class _ReplayEngine:
    def __init__(self, *, answer: str = "OK"):
        self.memory = _StubMemory()
        self.ledger = type("Ledger", (), {"has_open_contradiction": staticmethod(lambda _mid: False)})()
        self.answer = answer
        self.last_user_query: Optional[str] = None

    def query(self, **kwargs):
        self.last_user_query = kwargs.get("user_query")
        return {
            "answer": self.answer,
            "thinking": None,
            "mode": "quick",
            "confidence": 0.4,
            "response_type": "speech",
            "gates_passed": True,
            "gate_reason": None,
            "retrieved_memories": [],
            "prompt_memories": [],
            "learned_suggestions": [],
            "heuristic_suggestions": [],
            "profile_updates": [],
            "contradiction_detected": False,
            "contradiction_resolved": False,
            "unresolved_contradictions_total": 0,
            "unresolved_hard_conflicts": 0,
            "session_id": "acceptance-replay",
            "gate_debug": None,
        }


class _PendingAwareEngine(_ReplayEngine):
    def query(self, **kwargs):
        self.last_user_query = kwargs.get("user_query")
        if self.last_user_query and "[PENDING FOLLOW-UP QUESTION]" in self.last_user_query:
            answer = "bound pending follow-up"
        else:
            answer = "missed pending follow-up"
        result = super().query(**kwargs)
        result["answer"] = answer
        return result


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _build_app(engine: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda _thread_id: engine
    app.state.get_llm_client = lambda: None
    app.state.increment_turn = lambda _thread_id: None
    app.state.log_collapse_trail = lambda **_kwargs: None
    app.state.scheduled_tasks_db_path = ""
    return app


def _noop_resume(*args, **kwargs):
    if False:
        yield ""
    return None


def _patch_route_defaults(monkeypatch: pytest.MonkeyPatch, db: ThreadSessionDB) -> None:
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **_kwargs: None)
    monkeypatch.setattr(chat_routes, "_maybe_sync_groundcheck_bridge", lambda **_kwargs: {"enabled": False})
    monkeypatch.setattr(chat_routes, "_get_preference_profile", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(chat_routes, "_get_verbosity_preference", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(chat_routes, "_route_model_for_request", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(chat_routes, "_should_expand_response", lambda *_args, **_kwargs: (False, None))
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"greeting": {"enabled": False}, "agent_loop": {"enabled": False}})
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": default)
    monkeypatch.setattr(chat_routes, "resolve_effective_generation_mode", lambda req, uid=None: "local")


@pytest.fixture()
def replay_client_and_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    engine = _ReplayEngine()
    _patch_route_defaults(monkeypatch, db)
    client = TestClient(_build_app(engine))
    return client, db, engine


def test_replay_direct_health_history_uses_gpt_reference_override(
    replay_client_and_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _db, engine = replay_client_and_db
    engine.answer = (
        "I know that your health history is important to you. However, I don't have specific "
        "details about your medical history at this moment. If you'd like to share more, "
        "I can help you keep track of it."
    )
    packet = {
        "thread_id": "replay-health",
        "topic_key": "health_history",
        "query_text": "Aether, what do you know about my health history?",
        "summary": "Temporary GPT archive references for this thread:\n- [user] 2025-04-06 | Thread Assessment: remember my three promises",
        "excerpts": [
            {
                "role": "user",
                "date": "2025-04-06",
                "conv_title": "Thread Assessment",
                "text": "remember my three promises to myself that first night in the hospital",
            }
        ],
    }
    monkeypatch.setattr(chat_routes, "_get_or_build_gpt_reference_packet", lambda *args, **kwargs: (packet, False))

    resp = client.post(
        "/api/chat/send",
        json={"thread_id": "replay-health", "message": "Aether, what do you know about my health history?", "channel": "webchat"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "I checked your GPT archive for relevant past context." in body["answer"]
    assert "three promises" in body["answer"].lower()
    assert body["metadata"]["gpt_reference_used"] is True
    assert body["metadata"]["gpt_reference_topic"] == "health_history"


def test_replay_retry_followup_carries_health_history_topic(
    replay_client_and_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, engine = replay_client_and_db
    engine.answer = "From what I remember, you've mentioned an ICU stay."
    packet = {
        "thread_id": "replay-retry",
        "topic_key": "health_history",
        "query_text": "medical history",
        "summary": "Temporary GPT archive references for this thread:\n- [user] 2025-03-24 | Notes: those three promises",
        "excerpts": [
            {
                "role": "user",
                "date": "2025-03-24",
                "conv_title": "Notes",
                "text": "those three promises... my philosophy seeing it through",
            }
        ],
    }
    monkeypatch.setattr(chat_routes, "_get_or_build_gpt_reference_packet", lambda *args, **kwargs: (packet, True))
    db.record_query(
        thread_id="replay-retry",
        query_text="Aether, what do you know about my health history?",
        response_text="I have fragments, not the full picture.",
        detected_slot=None,
    )

    resp = client.post(
        "/api/chat/send",
        json={"thread_id": "replay-retry", "message": "can you try again?", "channel": "webchat"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "temporary GPT-history references already loaded" in body["answer"]
    assert "three promises" in body["answer"].lower()
    assert body["metadata"]["gpt_reference_topic"] == "health_history"


def test_replay_pending_followup_shortcut_binds_to_open_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    engine = _PendingAwareEngine()
    _patch_route_defaults(monkeypatch, db)
    client = TestClient(_build_app(engine))

    task = GovernedTask.new(thread_id="replay-pending", objective="Answer the contradiction follow-up")
    task.status = GovernedTaskStatus.NEEDS_FOLLOWUP
    task.question = "What contradictions do you see between what I believe and how I act?"
    task.orch_answer_so_far = "I can summarize the contradiction ledger so far."
    db.create_governed_task(task)

    resp = client.post(
        "/api/chat/send",
        json={"thread_id": "replay-pending", "message": "tell me", "channel": "webchat"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "bound pending follow-up"
    assert engine.last_user_query is not None
    assert "[PENDING FOLLOW-UP QUESTION]" in engine.last_user_query
    assert "what contradictions do you see" in engine.last_user_query.lower()


def test_replay_stream_health_history_emits_intent_preview(
    replay_client_and_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _db, engine = replay_client_and_db
    engine.answer = "I don't have specific details about your medical history at this moment."
    packet = {
        "thread_id": "replay-stream-health",
        "topic_key": "health_history",
        "query_text": "Aether, what do you know about my health history?",
        "summary": "Temporary GPT archive references for this thread:\n- [user] 2025-04-06 | Thread Assessment: remember my three promises",
        "excerpts": [],
    }
    monkeypatch.setattr(chat_routes, "_get_or_build_gpt_reference_packet", lambda *args, **kwargs: (packet, False))

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "replay-stream-health", "message": "Aether, what do you know about my health history?", "channel": "webchat"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    preview = next(
        event
        for event in events
        if event["type"] == "intent_preview"
        and (event.get("metadata") or {}).get("intent") == "gpt_reference_lookup"
    )
    assert "checking your GPT history" in preview["content"]
    assert preview["metadata"]["intent"] == "gpt_reference_lookup"
    assert preview["metadata"]["topic"] == "health_history"


def test_replay_stream_conversational_orchestrator_emits_ack_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    engine = _ReplayEngine()
    _patch_route_defaults(monkeypatch, db)
    client = TestClient(_build_app(engine))

    monkeypatch.setattr(chat_routes, "try_resume_or_resolve", _noop_resume)
    monkeypatch.setattr(
        "personal_agent.task_agent.classify_intent",
        lambda message, active_task=None: TaskIntent(
            route="conversational",
            intent_type="conversational",
            slots={},
            confidence=0.92,
            reason="replay",
        ),
    )
    monkeypatch.setattr(
        "personal_agent.routing_beliefs.should_orchestrate",
        lambda message, intent: type("Routing", (), {"route": "orchestrator", "confidence": 0.95, "reasons": ["replay"]})(),
    )

    def fake_orchestrator(runtime, task_intent, routing_reason, recent_history):
        yield runtime.emit({"type": "done", "content": "Here is the reflective answer.", "metadata": {"agent_loop": True}})
        from routes.chat_runtime import StreamTerminalResult

        return StreamTerminalResult(terminal=True, handled=True, metadata={"agent_loop": True})

    monkeypatch.setattr(chat_routes, "run_orchestrator", fake_orchestrator)

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "replay-orch", "message": "What do you believe?", "channel": "webchat"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    preview = next(event for event in events if event["type"] == "intent_preview")
    assert preview["content"] == "I'm going to think that through for a moment, then I'll answer directly."
