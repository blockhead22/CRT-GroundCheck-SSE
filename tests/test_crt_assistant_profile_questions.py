from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        # With template fast-paths removed, identity questions now flow through
        # the reasoning engine. Return a contextually reasonable response.
        prompt_lower = prompt.lower()
        if "who are you" in prompt_lower or "what are you" in prompt_lower:
            return "I'm Aether, a personal AI assistant with persistent memory."
        if "occupation" in prompt_lower or "what do you do" in prompt_lower:
            return "I'm an AI assistant — I help with questions, remember facts, and track contradictions."
        if "film" in prompt_lower or "background" in prompt_lower:
            return "I don't have personal experience in filmmaking. I'm an AI assistant."
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_assistant_occupation_produces_answer(rag: CRTEnhancedRAG):
    """Identity questions should produce an answer (via reasoning engine, not template)."""
    out = rag.query("What is your occupation?")
    ans = (out.get("answer") or "").lower()
    assert ans, "Should produce a non-empty answer"
    # Should not claim the user's attributes as its own
    assert "you mentioned" not in ans


def test_assistant_identity_question_produces_answer(rag: CRTEnhancedRAG):
    out = rag.query("Who are you?")
    ans = (out.get("answer") or "").lower()
    assert ans, "Should produce a non-empty answer"
    assert "ok" not in ans or len(ans) > 10  # Should not just return "OK"


def test_assistant_filmmaking_question_does_not_hallucinate(rag: CRTEnhancedRAG):
    """If no filmmaking memories exist, the assistant should not hallucinate experience."""
    out = rag.query("What's your background in filmmaking?")
    ans = (out.get("answer") or "").lower()
    assert ans, "Should produce a non-empty answer"
    # Should not claim user memories for this
    assert "stored memories" not in ans
    assert "i recall" not in ans
