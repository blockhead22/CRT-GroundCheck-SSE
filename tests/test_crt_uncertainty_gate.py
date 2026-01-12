from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_ledger import ContradictionType


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


def test_unrelated_hard_conflict_does_not_block_smalltalk(rag: CRTEnhancedRAG):
    # Create an open hard CONFLICT about a personal slot (name).
    rag.query("My name is Sarah.")
    rag.query("My name is Emily.")

    # Normal conversation should remain generative (not forced into uncertainty)
    # when the user is not asking about the conflicting slot.
    out = rag.query("Hello again!")
    assert out["mode"] != "uncertainty"


def test_provenance_footer_requires_gates_passed(rag: CRTEnhancedRAG, monkeypatch: pytest.MonkeyPatch):
    rag.query("My name is Sarah.")

    # Force reconstruction gates to fail, regardless of embeddings.
    monkeypatch.setattr(
        rag.crt_math,
        "check_reconstruction_gates",
        lambda _intent, _mem: (False, "forced_for_test"),
    )

    out = rag.query("What's my name?")
    assert out["gates_passed"] is False
    assert "Provenance:" not in out["answer"]


def test_uncertainty_response_invites_continuing_conversation(rag: CRTEnhancedRAG, monkeypatch: pytest.MonkeyPatch):
    # Force a hard CONFLICT classification so this test doesn't depend on
    # embedding similarity heuristics.
    monkeypatch.setattr(rag.ledger, "_classify_contradiction", lambda *args, **kwargs: ContradictionType.CONFLICT)

    # Create a hard CONFLICT and ask about the conflicted slot.
    rag.query("My name is Sarah.")
    rag.query("My name is Emily.")

    out = rag.query("What's my name?")
    assert out["mode"] == "uncertainty"
    assert "I can still help with other parts of your question" in out["answer"]


def test_reasserting_prior_name_is_clarification_not_new_contradiction(
    rag: CRTEnhancedRAG, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(rag.ledger, "_classify_contradiction", lambda *args, **kwargs: ContradictionType.CONFLICT)

    rag.query("My name is Sarah.")
    rag.query("My name is Emily.")

    out = rag.query("For the record: my name is Sarah.")
    assert out["contradiction_detected"] is False

    # The earlier name conflict should be resolvable by this clarification.
    open_contras = rag.get_open_contradictions()
    assert open_contras == []
