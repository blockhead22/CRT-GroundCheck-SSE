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

    assert out["mode"] == "uncertainty"
    assert out.get("recommended_next_action") is not None
    assert out["recommended_next_action"]["action_type"] == "ask_user"
    assert out["recommended_next_action"]["slot"] == "employer"

    # The user-facing answer should ask for clarification, not silently pick a winner.
    answer = (out.get("answer") or "").lower()
    assert "which is correct" in answer
    assert "amazon" in answer
    assert "microsoft" in answer
