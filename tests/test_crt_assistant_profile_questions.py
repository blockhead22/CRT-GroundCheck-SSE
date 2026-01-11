from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        # If this gets returned to the user, it means we didn't hit the deterministic path.
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_assistant_occupation_is_deterministic_and_not_chat_backed(rag: CRTEnhancedRAG):
    out = rag.query("What is your occupation?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "assistant" in ans
    assert "ai" in ans

    # Should not claim it came from stored user memories.
    assert "stored memories" not in ans
    assert "i recall" not in ans
    assert "you mentioned" not in ans


def test_assistant_identity_question_is_deterministic(rag: CRTEnhancedRAG):
    out = rag.query("Who are you?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "assistant" in ans
    assert "ok" not in ans


def test_assistant_background_filmmaking_is_deterministic_and_not_chat_backed(rag: CRTEnhancedRAG):
    out = rag.query("What's your background in filmmaking?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "background" in ans or "experience" in ans
    assert "film" in ans
    assert "ok" not in ans

    assert "stored memories" not in ans
    assert "i recall" not in ans
    assert "you mentioned" not in ans


def test_assistant_background_filmmaking_paraphrase_is_deterministic(rag: CRTEnhancedRAG):
    out = rag.query("Can you tell me about your background in filmmaking?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "film" in ans
    assert "ok" not in ans

    assert "stored memories" not in ans
    assert "i recall" not in ans
    assert "you mentioned" not in ans


def test_assistant_work_filmmaking_paraphrase_is_deterministic(rag: CRTEnhancedRAG):
    out = rag.query("Can you tell me about your work in filmmaking?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "film" in ans
    assert "ok" not in ans

    assert "stored memories" not in ans
    assert "i recall" not in ans
    assert "you mentioned" not in ans


def test_assistant_experience_question_is_deterministic(rag: CRTEnhancedRAG):
    out = rag.query("Do you have experience as a filmmaker?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "assistant_profile"
    assert "experience" in ans or "background" in ans
    assert "assistant" in ans or "ai" in ans
    assert "ok" not in ans
