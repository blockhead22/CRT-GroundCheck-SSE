from __future__ import annotations

from pathlib import Path

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fidelity_mirror import check_fidelity


class _FactEchoLLM:
    """Deterministic LLM stub: echo resolved fact blocks, otherwise stay neutral."""

    _SKIP_PREFIXES = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False) -> str:
        if "[RESOLVED FACT DATA]" in prompt:
            block = prompt.split("[RESOLVED FACT DATA]", 1)[1]
            for end in ("[", "===", "User:"):
                if end in block:
                    block = block[: block.index(end)]
            past_header = False
            for line in block.splitlines():
                text = line.strip()
                if "found:" in text.lower():
                    past_header = True
                    continue
                if past_header and text and not any(text.startswith(prefix) for prefix in self._SKIP_PREFIXES):
                    return text
        return "OK"


def _make_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
        llm_client=_FactEchoLLM(),
    )


def _answer_text(result: dict) -> str:
    return str(result.get("answer") or "").lower()


def test_compact_meaning_loop_preserves_high_impact_state_changes(tmp_path: Path) -> None:
    """One small end-to-end spec for the meaning thesis.

    Public claim under test:
    CRT should treat identity, contradiction, authority, and action constraints as
    higher-impact state changes than ordinary remembered text.
    """

    rag = _make_rag(tmp_path)

    # Identity claims are meaningful because they bind future self/user reference.
    first_name = rag.query("My name is Sarah.")
    name_correction = rag.query("Actually, my name is Emily.")

    assert first_name.get("contradiction_detected") is False
    assert name_correction.get("contradiction_entry") is not None

    name_answer = _answer_text(rag.query("What's my name?"))
    assert name_answer != "ok"
    assert "conflict" in name_answer or "sarah" in name_answer or "emily" in name_answer

    # Slot correction should preserve history while retrieving the latest active value.
    rag.query("I work at Microsoft as a senior developer.")
    employer_correction = rag.query("Actually, I work at Amazon, not Microsoft.")
    assert employer_correction.get("contradiction_entry") is not None

    employer_answer = _answer_text(rag.query("Where do I work?"))
    assert "amazon" in employer_answer
    assert "microsoft" not in employer_answer

    # Behavioral constraints are meaningful because they should affect later action posture.
    constraint = rag.memory.store_memory(
        text="Never force push to main.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel="webchat",
        kind="user_fact",
    )
    trivia = rag.memory.store_memory(
        text="I had cereal this morning.",
        confidence=0.75,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel="webchat",
        kind="observation",
    )

    retrieved = rag.retrieve("Can I force push to main?", k=5, min_trust=0.0)
    retrieved_ids = [mem.memory_id for mem, _score in retrieved]
    assert constraint.memory_id in retrieved_ids
    assert retrieved_ids.index(constraint.memory_id) < retrieved_ids.index(trivia.memory_id)

    # Social/external claims should not silently become confirmed user facts.
    social_claim = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion", "origin": "moltbook:comment:42"},
        channel="moltbook",
        kind="user_fact",
    )
    assert social_claim.authority == "provisional"
    assert rag.memory.can_answer_user_fact(social_claim) is False

    # A faithful answer should be accepted by the post-generation fidelity mirror.
    fidelity = check_fidelity(
        response="Your current employer is Amazon.",
        query="Where do I work?",
        memories=[{"text": "FACT: employer = Amazon", "trust": 0.95, "kind": "user_fact", "source": "user"}],
    )
    assert fidelity.passed
