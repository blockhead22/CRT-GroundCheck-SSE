from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.db_utils import ThreadSessionDB
from routes import chat as chat_routes


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


def _build_app(rag: CRTEnhancedRAG) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda thread_id: rag
    app.state.get_llm_client = lambda: None
    app.state.increment_turn = lambda thread_id: None
    app.state.log_collapse_trail = lambda **kwargs: None
    return app


def _runtime_cfg() -> dict:
    return {
        "greeting": {"enabled": False},
        "openclaw_handoff": {
            "enabled": True,
            "agent_id": "main",
            "session_prefix": "crt",
            "timeout_seconds": 30,
            "allowed_channels": ["telegram", "webchat"],
            "denied_channels": [],
            "inject_crt_context": True,
            "include_api_guide": True,
            "max_fact_items": 8,
            "auto_keywords": ["research", "github", "openclaw", "moltbook"],
        },
    }


def test_chat_send_delegates_telegram_research_to_openclaw(tmp_path: Path, monkeypatch) -> None:
    rag = _build_rag(tmp_path)
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))

    monkeypatch.setattr(chat_routes, "get_runtime_config", _runtime_cfg)
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_routes,
        "run_openclaw_agent",
        lambda **kwargs: {
            "ok": True,
            "answer": "OpenClaw delegated answer.",
            "session_id": "crt-tg_12345",
            "agent_id": "main",
            "returncode": 0,
            "stderr": "",
        },
    )

    client = TestClient(_build_app(rag))
    resp = client.post(
        "/api/chat/send",
        json={
            "thread_id": "tg_12345",
            "message": "research the latest rust memory systems",
            "channel": "telegram",
            "origin": "telegram:12345:77",
            "actor_id": "12345",
        },
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("answer") == "OpenClaw delegated answer."
    assert body.get("gate_reason") == "openclaw_handoff"
    meta = body.get("metadata") or {}
    assert meta.get("openclaw_delegated") is True
    assert meta.get("agent_activated") is True
    assert meta.get("mode") == "openclaw"
    assert meta.get("openclaw_session_id") == "crt-tg_12345"


def test_chat_send_falls_back_to_crt_when_openclaw_fails(tmp_path: Path, monkeypatch) -> None:
    rag = _build_rag(tmp_path)
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))

    def _fake_query(**kwargs):
        return {
            "answer": "CRT fallback answer.",
            "response_type": "speech",
            "gates_passed": True,
            "gate_reason": "normal",
            "retrieved_memories": [],
            "prompt_memories": [],
            "confidence": 0.81,
            "contradiction_detected": False,
        }

    monkeypatch.setattr(rag, "query", _fake_query)
    monkeypatch.setattr(chat_routes, "get_runtime_config", _runtime_cfg)
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **kwargs: None)
    monkeypatch.setattr(chat_routes, "_maybe_sync_groundcheck_bridge", lambda **kwargs: {"enabled": False})
    monkeypatch.setenv("CRT_ENABLE_LLM", "false")
    monkeypatch.setattr(
        chat_routes,
        "run_openclaw_agent",
        lambda **kwargs: {
            "ok": False,
            "answer": "",
            "session_id": "crt-tg_99999",
            "agent_id": "main",
            "returncode": 1,
            "stderr": "gateway unavailable",
        },
    )

    client = TestClient(_build_app(rag))
    resp = client.post(
        "/api/chat/send",
        json={
            "thread_id": "tg_99999",
            "message": "research github issues for this repo",
            "channel": "telegram",
        },
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("answer") == "CRT fallback answer."
    assert body.get("gate_reason") == "normal"
    stages = ((body.get("metadata") or {}).get("response_control") or {}).get("stages") or []
    assert any(s.get("stage") == "decide" and s.get("status") == "openclaw_fallback" for s in stages)


def test_chat_send_delegates_webchat_moltbook_query_to_openclaw(tmp_path: Path, monkeypatch) -> None:
    rag = _build_rag(tmp_path)
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))

    monkeypatch.setattr(chat_routes, "get_runtime_config", _runtime_cfg)
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_routes,
        "run_openclaw_agent",
        lambda **kwargs: {
            "ok": True,
            "answer": "Moltbook delegated answer.",
            "session_id": "crt-webchat_default",
            "agent_id": "main",
            "returncode": 0,
            "stderr": "",
        },
    )

    client = TestClient(_build_app(rag))
    resp = client.post(
        "/api/chat/send",
        json={
            "thread_id": "webchat_default",
            "message": "Anything new on Moltbook? also new updates?",
            "channel": "webchat",
            "origin": "webchat:test-moltbook",
        },
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("answer") == "Moltbook delegated answer."
    assert body.get("gate_reason") == "openclaw_handoff"
    meta = body.get("metadata") or {}
    assert meta.get("openclaw_delegated") is True
    assert meta.get("mode") == "openclaw"
