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


def test_gate_fail_answer_is_sanitized_and_metadata_exposes_gate(tmp_path: Path, monkeypatch) -> None:
    rag = _build_rag(tmp_path)
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))

    def _fake_query(**kwargs):
        return {
            "answer": (
                "Original question: Where do I work?\n\n"
                "CORRECTIONS from stored memory:\nContradiction: Umbrella Corp\n\n"
                "Revise your answer to be consistent."
            ),
            "response_type": "uncertainty",
            "gates_passed": False,
            "gate_reason": "unresolved_contradictions",
            "retrieved_memories": [],
            "prompt_memories": [],
            "confidence": 0.2,
            "contradiction_detected": True,
            "unresolved_contradictions_total": 1,
            "unresolved_hard_conflicts": 1,
            "gate_debug": {"slot": "employer"},
        }

    monkeypatch.setattr(rag, "query", _fake_query)
    monkeypatch.setattr(chat_routes, "get_thread_session_db", lambda: db)
    monkeypatch.setattr(chat_routes, "get_time_based_greeting", lambda **kwargs: None)
    monkeypatch.setattr(chat_routes, "_maybe_sync_groundcheck_bridge", lambda **kwargs: {"enabled": False})
    monkeypatch.setattr(chat_routes, "get_runtime_config", lambda: {"greeting": {"enabled": False}})
    monkeypatch.setenv("CRT_ENABLE_LLM", "false")

    client = TestClient(_build_app(rag))
    resp = client.post(
        "/api/chat/send",
        json={"thread_id": "gate_test", "message": "Where do I work?", "channel": "webchat"},
    )

    assert resp.status_code == 200
    body = resp.json() or {}
    assert body.get("gates_passed") is False
    assert body.get("gate_reason") == "unresolved_contradictions"
    assert body.get("answer") == (
        "I have conflicting information about your employer and can't answer confidently yet. "
        "Which version is correct right now?"
    )
    meta = body.get("metadata") or {}
    assert meta.get("gates_passed") is False
    assert meta.get("gate_reason") == "unresolved_contradictions"
