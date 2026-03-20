from types import SimpleNamespace
from pathlib import Path

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.intent_router import Intent


class _MetaQuestionRouter:
    def classify(self, _text: str):
        return SimpleNamespace(intent=Intent.FACT_QUESTION, confidence=0.99, extracted={})


def test_query_with_intent_bypasses_fact_store_for_meta_questions(tmp_path: Path) -> None:
    rag = CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
    )
    rag.intent_router = _MetaQuestionRouter()
    rag.fact_store.process_input("My name is Nick", thread_id="meta_thread")

    captured = {}

    def _fake_query(user_query, user_marked_important=False, mode=None, thread_id=None, **kwargs):
        captured["user_query"] = user_query
        captured["thread_id"] = thread_id
        return {
            "answer": "meta-path",
            "thinking": None,
            "mode": "quick",
            "confidence": 0.9,
            "response_type": "speech",
            "gates_passed": True,
            "gate_reason": "meta_test",
            "retrieved_memories": [],
        }

    rag.query = _fake_query  # type: ignore[method-assign]

    result = rag.query_with_intent(
        user_query="How do you remember my name?",
        thread_id="meta_thread",
    )

    assert result["answer"] == "meta-path"
    assert result["intent"] == Intent.FACT_QUESTION.value
    assert captured["user_query"] == "How do you remember my name?"
    assert captured["thread_id"] == "meta_thread"
