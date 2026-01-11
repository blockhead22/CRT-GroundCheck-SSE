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


def test_conflict_resolution_loop_employer(rag: CRTEnhancedRAG):
    # Create a hard conflict (avoid explicit revision cues like "actually").
    rag.query("I work at Microsoft as an engineer.")
    rag.query("I work at Amazon as an engineer.")

    out1 = rag.query("Where do I work?")
    assert out1["mode"] == "uncertainty"

    # User clarifies with an explicit slot=value, which CRT knows how to parse deterministically.
    rag.query("Employer = Amazon")

    out2 = rag.query("Where do I work?")
    assert out2["mode"] != "uncertainty"

    ans2 = (out2.get("answer") or "").lower()
    assert "amazon" in ans2
    assert "which is correct" not in ans2


def test_conflict_resolution_loop_title(rag: CRTEnhancedRAG):
    rag.query("My title is Engineer.")
    rag.query("My title is Manager.")

    out1 = rag.query("What is my title?")
    assert out1["mode"] == "uncertainty"

    rag.query("Title = Manager")

    out2 = rag.query("What is my title?")
    assert out2["mode"] != "uncertainty"

    ans2 = (out2.get("answer") or "").lower()
    assert "manager" in ans2
    assert "which is correct" not in ans2
