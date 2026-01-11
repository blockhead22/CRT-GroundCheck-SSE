from __future__ import annotations

import json
from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent import runtime_config as runtime_config_module


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_assistant_profile_response_can_be_overridden_via_runtime_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "assistant_profile": {
                    "enabled": True,
                    "responses": {
                        "occupation": "CUSTOM OCCUPATION ANSWER",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CRT_RUNTIME_CONFIG_PATH", str(cfg_path))
    runtime_config_module.clear_runtime_config_cache()

    mem_db = tmp_path / "mem2.db"
    led_db = tmp_path / "led2.db"
    r = CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())

    out = r.query("What is your occupation?")
    assert out.get("gate_reason") == "assistant_profile"
    assert out.get("answer") == "CUSTOM OCCUPATION ANSWER"
