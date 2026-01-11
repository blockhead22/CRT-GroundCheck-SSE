from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.onboarding import run_onboarding_interactive


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_onboarding_stores_structured_fact_and_pref(rag: CRTEnhancedRAG):
    runtime_cfg = {
        "onboarding": {
            "enabled": True,
            "auto_run_when_memory_empty": True,
            "questions": [
                {"slot": "name", "kind": "fact", "prompt": "Name?"},
                {"slot": "communication_style", "kind": "pref", "prompt": "Style?"},
            ],
        }
    }

    answers = iter(["Alice", "concise"])

    def _fake_input(_: str) -> str:
        return next(answers)

    stored = run_onboarding_interactive(rag, runtime_cfg, input_fn=_fake_input, print_fn=lambda _: None)
    assert stored == {"name": "Alice", "communication_style": "concise"}

    mem_texts = [m.text for m in rag.memory._load_all_memories()]
    assert "FACT: name = Alice" in mem_texts
    assert "PREF: communication_style = concise" in mem_texts
