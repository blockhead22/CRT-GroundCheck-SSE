from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    _SKIP = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
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
                if past_header and s and not any(s.startswith(p) for p in self._SKIP):
                    return s
        if "[UNRESOLVED CONFLICT" in prompt:
            return "I have conflicting information about that."
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    profile_db = tmp_path / "profile.db"
    return CRTEnhancedRAG(
        memory_db=str(mem_db),
        ledger_db=str(led_db),
        profile_db=str(profile_db),
        llm_client=FakeLLM(),
    )


def test_conflict_resolution_loop_employer(rag: CRTEnhancedRAG):
    # Create a hard conflict (avoid explicit revision cues like "actually").
    rag.query("I work at Microsoft as an engineer.")
    rag.query("I work at Amazon as an engineer.")

    out1 = rag.query("Where do I work?")
    # The system may auto-resolve to the latest value with a caveat, or surface
    # both if it's a hard conflict. Either behavior is acceptable.
    ans1 = (out1.get("answer") or "").lower()
    assert "amazon" in ans1 or "microsoft" in ans1, f"Should mention an employer, got: {ans1[:200]}"

    # User clarifies with an explicit slot=value
    rag.query("Employer = Amazon")

    out2 = rag.query("Where do I work?")
    ans2 = (out2.get("answer") or "").lower()
    assert "amazon" in ans2


def test_conflict_resolution_loop_title(rag: CRTEnhancedRAG):
    rag.query("My title is Engineer.")
    rag.query("My title is Manager.")

    out1 = rag.query("What is my title?")
    ans1 = (out1.get("answer") or "").lower()
    assert "manager" in ans1 or "engineer" in ans1, f"Should mention a title, got: {ans1[:200]}"

    rag.query("Title = Manager")

    out2 = rag.query("What is my title?")
    ans2 = (out2.get("answer") or "").lower()
    assert "manager" in ans2
