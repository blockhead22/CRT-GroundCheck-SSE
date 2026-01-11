from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        # If we hit this, we did NOT take the deterministic safe path.
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_user_named_reference_occupation_avoids_world_facts(rag: CRTEnhancedRAG):
    # Seed user identity and a work-related claim.
    rag.query("For the record: my name is Nick Block.")
    rag.query("I run The Printing Lair (print/sticker shop).")

    extracted_slot = rag._get_latest_user_slot_value("name")
    extracted_guess = rag._get_latest_user_name_guess()
    assert (extracted_slot or extracted_guess), f"expected a user name to be extractable, got slot={extracted_slot!r} guess={extracted_guess!r}"
    assert rag._is_user_named_reference_question("What is Nick Block's occupation?"), (
        f"expected name-reference detector to trigger; slot={extracted_slot!r} guess={extracted_guess!r}"
    )

    out = rag.query("What is Nick Block's occupation?")
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "user_named_reference"
    assert "printing lair" in ans

    # Must not fall back to the LLM stub.
    assert "ok" not in ans

    # Must not invent public-figure facts.
    assert "film director" not in ans
    assert "screenwriter" not in ans


def test_user_named_reference_kind_of_work_paraphrase_triggers_safe_path(rag: CRTEnhancedRAG):
    rag.query("For the record: my name is Nick Block.")
    rag.query("I run The Printing Lair (print/sticker shop).")

    q = "Can you tell me what kind of work Nick Block does besides running The Printing Lair?"
    assert rag._is_user_named_reference_question(q)

    out = rag.query(q)
    ans = (out.get("answer") or "").lower()

    assert out.get("gate_reason") == "user_named_reference"
    assert "printing lair" in ans
    assert "ok" not in ans

    # Must not invent public-figure facts.
    assert "battles" not in ans
    assert "musician" not in ans
