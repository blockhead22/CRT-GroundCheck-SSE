from __future__ import annotations

from pathlib import Path

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG


class _FactEchoLLM:
    """Deterministic LLM stub that echoes resolved fact data when provided."""

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


def _answer(result: dict) -> str:
    return str(result.get("answer") or "").lower()


def test_name_correction_changes_user_visible_answer(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    rag.query("My name is Sarah.")
    correction = rag.query("Actually, my name is Emily.")
    answer = _answer(rag.query("What's my name?"))

    assert correction.get("contradiction_entry") is not None
    assert answer != "ok"
    assert "emily" in answer or "conflict" in answer


def test_latest_employer_correction_governs_answer(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    rag.query("I work at Microsoft as a senior developer.")
    correction = rag.query("Actually, I work at Amazon, not Microsoft.")
    answer = _answer(rag.query("Where do I work?"))

    assert correction.get("contradiction_entry") is not None
    assert "amazon" in answer
    assert "microsoft" not in answer


def test_provisional_social_fact_does_not_answer_user_fact_question(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    social = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion", "origin": "moltbook:comment:42"},
        channel="moltbook",
        kind="user_fact",
        thread_id="default",
    )
    answer = _answer(rag.query("What's my favorite color?", thread_id="default"))

    assert social.authority == "provisional"
    assert rag.memory.can_answer_user_fact(social) is False
    assert "blue" not in answer


def test_locked_force_push_policy_refuses_action(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    policy = rag.memory.store_memory(
        text="Never force push to main.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "ops"},
        authority="locked",
        channel="webchat",
        kind="ops",
        thread_id="default",
    )
    out = rag.query("Can I force push to main?", thread_id="default")
    answer = _answer(out)

    assert policy.authority == "locked"
    assert policy.kind == "ops"
    assert out.get("gate_reason") == "locked_action_policy"
    assert "no" in answer
    assert "never force push to main" in answer
