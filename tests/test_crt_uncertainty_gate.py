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


def test_revision_contradiction_does_not_force_uncertainty_loop(rag: CRTEnhancedRAG):
    rag.query("My name is Sarah.")
    rag.query("Actually, my name is Emily.")

    # Asking a question after a revision should not automatically trigger uncertainty
    # just because there is an open non-CONFLICT ledger entry.
    out = rag.query("What's my name?")
    assert out["mode"] != "uncertainty"
