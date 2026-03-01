from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.scheduled_tasks import get_pending_scheduled_tasks
from routes import chat as chat_routes
from routes.meta_awareness import build_meta_awareness_snapshot, render_meta_awareness_response
from routes import notifications as notifications_routes


class _LedgerStub:
    def get_open_contradictions(self, limit: int = 10):
        return []


class _EngineStub:
    def __init__(self) -> None:
        self.user_profile = {}
        self.session_id = "s-test"
        self.ledger = _LedgerStub()


def test_meta_awareness_snapshot_contains_reflection_and_personality(tmp_path: Path):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    thread_id = "meta_t1"
    db.get_or_create_session(thread_id)
    db.store_reflection_scorecard(
        thread_id,
        {
            "updated_at": 1710000000.0,
            "top_topics": [{"topic": "payments", "weight": 0.9}],
            "open_questions": [{"question": "Is Tuesday payment still pending?"}],
        },
    )
    db.store_personality_profile(
        thread_id,
        {
            "state": "structured_coach",
            "state_reason": "high planning density",
            "verbosity": "balanced",
            "format": "structured",
        },
    )
    db.record_query(
        thread_id=thread_id,
        query_text="remind me about rent on tuesday",
        response_text="I can help track that.",
        detected_slot="reminder",
    )

    snapshot = build_meta_awareness_snapshot(
        thread_id=thread_id,
        session_db=db,
        engine=None,
    )
    reply = render_meta_awareness_response(snapshot)

    assert snapshot["thread_id"] == thread_id
    assert snapshot["topics_on_mind"][0]["topic"] == "payments"
    assert snapshot["personality_mode"]["state"] == "structured_coach"
    assert "payments" in reply.lower()


def test_notifications_routes_enqueue_claim_ack_cycle(tmp_path: Path, monkeypatch):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    monkeypatch.setattr(notifications_routes, "get_thread_session_db", lambda: db)

    app = FastAPI()
    app.include_router(notifications_routes.router)
    client = TestClient(app)

    enqueue = client.post(
        "/api/notifications/enqueue",
        json={
            "thread_id": "tg_12345",
            "channel": "telegram",
            "destination_id": "12345",
            "content": "Reminder: pay invoice",
            "category": "reminder",
            "priority": "high",
            "dedupe_key": "reminder:test-1",
        },
    )
    assert enqueue.status_code == 200
    notification_id = str((enqueue.json() or {}).get("notification_id") or "")
    assert notification_id

    claimed = client.post(
        "/api/notifications/claim",
        json={"worker_id": "test-worker", "channel": "telegram", "limit": 5},
    )
    assert claimed.status_code == 200
    items = (claimed.json() or {}).get("items") or []
    assert len(items) == 1
    assert items[0]["notification_id"] == notification_id

    ack = client.post(f"/api/notifications/{notification_id}/ack")
    assert ack.status_code == 200
    assert (ack.json() or {}).get("ok") is True

    listed = client.get("/api/notifications", params={"thread_id": "tg_12345", "status": "sent"})
    assert listed.status_code == 200
    assert (listed.json() or {}).get("count") == 1


def test_chat_reminder_requires_confirmation_then_schedules(tmp_path: Path, monkeypatch):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    scheduled_db = str(tmp_path / "scheduled_tasks.db")

    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **kwargs: None)

    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda thread_id: _EngineStub()
    app.state.get_llm_client = lambda: None
    app.state.increment_turn = lambda thread_id: None
    app.state.log_collapse_trail = lambda **kwargs: None
    app.state.scheduled_tasks_db_path = scheduled_db

    client = TestClient(app)
    thread_id = "tg_98765"

    first = client.post(
        "/api/chat/send",
        json={"thread_id": thread_id, "message": "remind me to pay rent tomorrow at 9am"},
    )
    assert first.status_code == 200
    first_body = first.json() or {}
    assert first_body.get("gate_reason") == "reminder_confirmation_required"

    second = client.post(
        "/api/chat/send",
        json={"thread_id": thread_id, "message": "yes"},
    )
    assert second.status_code == 200
    second_body = second.json() or {}
    assert second_body.get("gate_reason") == "reminder_scheduled"

    tasks = get_pending_scheduled_tasks(scheduled_db, thread_id=thread_id)
    assert any("pay rent" in str((t.payload or {}).get("reminder_text", "")) for t in tasks)
