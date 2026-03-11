from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    _SKIP_PREFIXES = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        # Context-aware: extract fact data from [RESOLVED FACT DATA] block
        if "[RESOLVED FACT DATA]" in prompt:
            block = prompt.split("[RESOLVED FACT DATA]")[1]
            for end in ("[", "===", "User:"):
                if end in block:
                    block = block[:block.index(end)]
            past_header = False
            for line in block.split("\n"):
                s = line.strip()
                if "found:" in s.lower():
                    past_header = True
                    continue
                if past_header and s and not any(s.startswith(p) for p in self._SKIP_PREFIXES):
                    return s
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_favorite_color_slot_question_answers_from_memory(rag: CRTEnhancedRAG) -> None:
    rag.query("My favorite color is orange.")
    out = rag.query("Do you recall my favorite color?")
    assert "orange" in (out.get("answer") or "").lower()
