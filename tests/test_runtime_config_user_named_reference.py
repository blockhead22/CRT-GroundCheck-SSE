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


def test_user_named_reference_response_can_be_overridden_via_runtime_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "user_named_reference": {
                    "enabled": True,
                    "responses": {
                        "known_work_prefix": "CUSTOM PREFIX:",
                        "ask_to_store": "CUSTOM ASK",
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

    r.query("For the record: my name is Nick Block.")
    r.query("I run The Printing Lair (print/sticker shop).")

    out = r.query("What is Nick Block's occupation?")
    assert out.get("gate_reason") == "user_named_reference"

    ans = out.get("answer") or ""
    assert "CUSTOM PREFIX:" in ans
    assert "CUSTOM ASK" in ans


def test_user_named_reference_can_be_disabled_via_runtime_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps({"user_named_reference": {"enabled": False}}), encoding="utf-8")

    monkeypatch.setenv("CRT_RUNTIME_CONFIG_PATH", str(cfg_path))
    runtime_config_module.clear_runtime_config_cache()

    mem_db = tmp_path / "mem2.db"
    led_db = tmp_path / "led2.db"
    r = CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())

    r.query("For the record: my name is Nick Block.")
    r.query("I run The Printing Lair (print/sticker shop).")

    out = r.query("What is Nick Block's occupation?")
    assert out.get("gate_reason") != "user_named_reference"
    assert "OK" in (out.get("answer") or "")
