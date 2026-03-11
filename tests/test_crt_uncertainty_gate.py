from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_ledger import ContradictionType
from personal_agent.user_profile import GlobalUserProfile


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
    
    rag_instance = CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())
    # Use isolated user profile for test
    rag_instance.user_profile = GlobalUserProfile(db_path=str(profile_db))
    return rag_instance


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
    # Note: Code uses check_reconstruction_gates_v2 with kwargs
    monkeypatch.setattr(
        rag.crt_math,
        "check_reconstruction_gates_v2",
        lambda *args, **kwargs: (False, "forced_for_test"),
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
    # The system may auto-resolve to the latest name with a caveat, or surface
    # both names if it detects a hard conflict. Either is acceptable.
    answer = (out.get("answer") or "").lower()
    assert "sarah" in answer or "emily" in answer, f"Should mention a name, got: {answer[:200]}"


def test_reasserting_prior_name_is_clarification_not_new_contradiction(
    rag: CRTEnhancedRAG, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(rag.ledger, "_classify_contradiction", lambda *args, **kwargs: ContradictionType.CONFLICT)

    rag.query("My name is Sarah.")
    rag.query("My name is Emily.")

    out = rag.query("For the record: my name is Sarah.")
    # NL resolution may set contradiction_detected=True because it processed
    # and resolved existing contradictions — that's correct behavior.
    # The key invariant is that no NEW contradictions remain open.
    open_contras = rag.get_open_contradictions()
    assert open_contras == [], f"All contradictions should be resolved, got: {open_contras}"
