from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.chat as chat_routes
from personal_agent.db_utils import ThreadSessionDB


class _StubMemory:
    db_path = ":memory:"


class _FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


class _StubEngine:
    def __init__(self):
        self.memory = _StubMemory()
        self.ledger = type("Ledger", (), {"has_open_contradiction": staticmethod(lambda _mid: False)})()

    def query(self, **kwargs):
        return {
            "answer": "",
            "thinking": None,
            "mode": "quick",
            "confidence": 0.2,
            "response_type": "speech",
            "gates_passed": False,
            "gate_reason": "explanatory_memory_fail (align=0.000 < 0.18)|degraded_output",
            "retrieved_memories": [],
            "prompt_memories": [],
            "learned_suggestions": [],
            "heuristic_suggestions": [],
            "profile_updates": [],
            "contradiction_detected": False,
            "contradiction_resolved": False,
            "unresolved_contradictions_total": 0,
            "unresolved_hard_conflicts": 0,
            "session_id": "meta-fallback",
            "gate_debug": None,
        }


def test_meta_provenance_gate_failure_returns_deterministic_explanation(monkeypatch, tmp_path: Path):
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda _thread_id: _StubEngine()
    app.state.get_llm_client = lambda: None
    app.state.increment_turn = lambda _thread_id: None
    app.state.log_collapse_trail = lambda **_kwargs: None

    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    monkeypatch.setattr(chat_routes, "_load_recent_history_messages", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(chat_routes, "_get_preference_profile", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(chat_routes, "_get_verbosity_preference", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(chat_routes, "_route_model_for_request", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **_kwargs: None)
    monkeypatch.setattr(chat_routes, "_maybe_sync_groundcheck_bridge", lambda **_kwargs: {"enabled": False})
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"greeting": {"enabled": False}})

    client = TestClient(app)
    resp = client.post(
        "/api/chat/send",
        json={
            "thread_id": "meta_thread",
            "message": "How do you remember you are Aether and I am Nick?",
            "channel": "webchat",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    answer = body.get("answer") or ""
    assert "storing your confirmed facts in memory" in answer
    assert "configured system role" in answer
    assert "disclose the conflict" in answer
