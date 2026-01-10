from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        # Deterministic, fast, and good enough for CRT pipeline tests.
        return "OK"


class CapturingLLM:
    def __init__(self):
        self.last_prompt: str | None = None

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        self.last_prompt = prompt
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


@pytest.fixture()
def capturing_rag(tmp_path: Path):
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    llm = CapturingLLM()
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=llm), llm


def test_question_does_not_create_contradiction(rag: CRTEnhancedRAG):
    rag.query("Hello. My name is Sarah.")

    before = len(rag.ledger.get_open_contradictions(limit=100))
    out = rag.query("What's my name?")
    after = len(rag.ledger.get_open_contradictions(limit=100))

    assert out["contradiction_detected"] is False
    assert after == before


def test_conflicting_name_assertion_creates_contradiction(rag: CRTEnhancedRAG):
    rag.query("My name is Sarah.")

    out = rag.query("Actually, my name is Emily.")
    open_contras = rag.ledger.get_open_contradictions(limit=100)

    assert out["contradiction_entry"] is not None
    assert len(open_contras) >= 1


def test_reinforcement_does_not_create_contradiction(rag: CRTEnhancedRAG):
    rag.query("My name is Sarah.")

    out = rag.query("Yes, I'm Sarah.")
    open_contras = rag.ledger.get_open_contradictions(limit=100)

    assert out["contradiction_detected"] is False
    assert len(open_contras) == 0


def test_employer_change_creates_contradiction_entry(rag: CRTEnhancedRAG):
    rag.query("I work at Microsoft as a senior developer.")

    out = rag.query("Actually, I work at Amazon, not Microsoft.")
    open_contras = rag.ledger.get_open_contradictions(limit=100)

    assert out["contradiction_entry"] is not None
    assert out["contradiction_detected"] is True
    assert len(open_contras) >= 1


def test_location_refinement_records_ledger_entry(rag: CRTEnhancedRAG):
    rag.query("I live in Seattle, Washington.")

    out = rag.query("I live in the Seattle metro area, specifically in Bellevue.")
    open_contras = rag.ledger.get_open_contradictions(limit=100)

    # We still want observability (a ledger entry) when a slot changes,
    # even if it later gets classified as a refinement rather than a hard conflict.
    assert out["contradiction_entry"] is not None
    assert out["contradiction_detected"] is True
    assert len(open_contras) >= 1


def test_prompt_prefers_latest_employer_fact(capturing_rag):
    rag, llm = capturing_rag
    rag.query("I work at Microsoft as a senior developer.")
    rag.query("Actually, I work at Amazon, not Microsoft.")

    rag.query("Where do I work?")
    assert llm.last_prompt is not None

    prompt_lower = llm.last_prompt.lower()
    assert "fact: employer = amazon" in prompt_lower
    assert "fact: employer = microsoft" not in prompt_lower


def test_slot_question_augmentation_injects_latest_employer(capturing_rag):
    rag, llm = capturing_rag

    # Create two conflicting employer assertions.
    rag.query("I work at Microsoft as a senior developer.")
    rag.query("Actually, I work at Amazon, not Microsoft.")

    # Simulate a retrieval miss that only returns the older Microsoft memory.
    all_mems = rag.memory._load_all_memories()
    ms_mem = next(m for m in all_mems if "i work at microsoft" in m.text.lower())

    rag.retrieve = lambda query, k=5, min_trust=0.0: [(ms_mem, 1.0)]

    rag.query("Where do I work?")
    assert llm.last_prompt is not None

    prompt_lower = llm.last_prompt.lower()
    assert "fact: employer = amazon" in prompt_lower
    assert "fact: employer = microsoft" not in prompt_lower
