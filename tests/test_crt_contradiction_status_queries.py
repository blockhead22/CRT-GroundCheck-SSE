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


def test_identity_contradiction_query_with_no_ledger_entries_is_ledger_grounded(rag: CRTEnhancedRAG):
    rag.query("My name is Sarah.")

    out = rag.query("Do you have any open contradictions about my identity? List them.")
    ans = (out.get("answer") or "").lower()

    # Should be a ledger-grounded "none" answer and must not invent specifics.
    assert "no open contradictions" in ans
    assert "new york" not in ans
    assert "california" not in ans


def test_identity_contradiction_query_lists_actual_name_conflict(rag: CRTEnhancedRAG):
    rag.query("My name is Sarah.")
    rag.query("Actually, my name is Emily.")

    out = rag.query("Do you have any open contradictions about my identity? List them.")
    ans = (out.get("answer") or "").lower()

    assert "name" in ans
    assert "sarah" in ans
    assert "emily" in ans
    assert "to resolve" in ans
