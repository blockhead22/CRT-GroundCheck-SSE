from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.db_utils import ThreadSessionDB
from routes import chat as chat_routes


def _build_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
    )


def _build_app(rag: CRTEnhancedRAG) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.state.get_engine = lambda _thread_id: rag
    app.state.get_llm_client = lambda: None
    app.state.increment_turn = lambda _thread_id: None
    app.state.log_collapse_trail = lambda **_kwargs: None
    return app


def test_chat_collapses_exact_repetition_loops(tmp_path: Path, monkeypatch) -> None:
    rag = _build_rag(tmp_path)
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    repeated = "You are Aether. Your name is Nick."

    def _fake_query(**kwargs):
        return {
            "answer": " ".join([repeated] * 12),
            "response_type": "belief",
            "gates_passed": True,
            "gate_reason": "gates_passed",
            "retrieved_memories": [],
            "prompt_memories": [],
            "confidence": 0.8,
            "contradiction_detected": False,
            "unresolved_contradictions_total": 0,
            "unresolved_hard_conflicts": 0,
        }

    monkeypatch.setattr(rag, "query", _fake_query)
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **_kwargs: None)
    monkeypatch.setattr(chat_routes, "_maybe_sync_groundcheck_bridge", lambda **_kwargs: {"enabled": False})
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"greeting": {"enabled": False}})

    client = TestClient(_build_app(rag))
    resp = client.post(
        "/api/chat/send",
        json={"thread_id": "repeat_test", "message": "meta", "channel": "webchat"},
    )

    assert resp.status_code == 200
    assert resp.json().get("answer") == repeated
