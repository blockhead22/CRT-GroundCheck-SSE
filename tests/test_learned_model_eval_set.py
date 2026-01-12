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
    runtime_config_module.clear_runtime_config_cache()
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def _seed_contradictions(rag: CRTEnhancedRAG) -> None:
    rag.query("My name is Sarah.")
    rag.query("Actually, my name is Emily.")
    rag.query("Actually, my name is Sarah.")
    rag.query("Actually, my name is Emily.")


def test_make_eval_set_then_eval_from_it(tmp_path: Path, rag: CRTEnhancedRAG) -> None:
    _seed_contradictions(rag)

    eval_set_path = tmp_path / "eval_set.json"
    from crt_learn_make_eval_set import main as make_main

    make_main(
        [
            "--memory-db",
            str(tmp_path / "mem.db"),
            "--ledger-db",
            str(tmp_path / "ledger.db"),
            "--out",
            str(eval_set_path),
            "--min-examples",
            "1",
        ]
    )
    assert eval_set_path.exists()

    payload = json.loads(eval_set_path.read_text(encoding="utf-8"))
    assert payload.get("type") == "crt_learned_suggestions_eval_set"
    assert int(((payload.get("examples") or {}).get("count") or 0)) >= 1

    # Train a model
    model_path = tmp_path / "model.joblib"
    from crt_learn_train import main as train_main

    train_main(
        [
            "--memory-db",
            str(tmp_path / "mem.db"),
            "--ledger-db",
            str(tmp_path / "ledger.db"),
            "--out",
            str(model_path),
            "--min-examples",
            "1",
        ]
    )
    assert model_path.exists()

    # Eval from frozen eval set
    out_eval = tmp_path / "eval.json"
    from crt_learn_eval import main as eval_main

    eval_main(
        [
            "--model",
            str(model_path),
            "--out",
            str(out_eval),
            "--eval-set",
            str(eval_set_path),
            "--min-examples",
            "1",
        ]
    )
    assert out_eval.exists()
    ev = json.loads(out_eval.read_text(encoding="utf-8"))
    assert (ev.get("data") or {}).get("eval_set_path") is not None
