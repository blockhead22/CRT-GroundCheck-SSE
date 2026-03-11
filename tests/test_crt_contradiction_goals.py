from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_hard_conflict_slot_question_returns_goal_instead_of_silent_latest(rag: CRTEnhancedRAG):
    # Avoid explicit revision keywords like "actually" so the ledger classifies this as a hard CONFLICT.
    rag.query("I work at Microsoft as an engineer.")
    rag.query("I work at Amazon as an engineer.")

    out = rag.query("Where do I work?")

    # After removing template early-returns, the system injects conflict context
    # and the reasoning engine generates the response. The answer should still
    # surface the conflict rather than silently picking a winner.
    answer = (out.get("answer") or "").lower()
    # The model should mention both conflicting values
    has_both = "amazon" in answer and "microsoft" in answer
    # Or the system should signal a contradiction was detected
    has_conflict_signal = out.get("contradiction_detected") or out.get("gates_passed") is False
    assert has_both or has_conflict_signal, f"Should surface conflict, got: {answer[:200]}"
