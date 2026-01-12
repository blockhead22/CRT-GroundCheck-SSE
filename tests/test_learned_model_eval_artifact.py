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


def test_learned_model_eval_writes_eval_json(tmp_path: Path, rag: CRTEnhancedRAG, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a few contradictions on the same slot (name) so training/eval has examples.
    rag.query("My name is Sarah.")
    rag.query("Actually, my name is Emily.")
    rag.query("Actually, my name is Sarah.")
    rag.query("Actually, my name is Emily.")

    model_path = tmp_path / "learned_suggestions.test.joblib"
    eval_path = tmp_path / "learned_suggestions.test.eval.json"

    # Train (allow tiny dataset).
    from crt_learn_train import main as train_main

    monkeypatch.setattr(
        "sys.argv",
        [
            "crt_learn_train.py",
            "--memory-db",
            str(tmp_path / "mem.db"),
            "--ledger-db",
            str(tmp_path / "ledger.db"),
            "--out",
            str(model_path),
            "--min-examples",
            "1",
        ],
    )
    train_main()
    assert model_path.exists()

    # Eval.
    from crt_learn_eval import main as eval_main

    eval_main(
        [
            "--model",
            str(model_path),
            "--memory-db",
            str(tmp_path / "mem.db"),
            "--ledger-db",
            str(tmp_path / "ledger.db"),
            "--out",
            str(eval_path),
            "--min-examples",
            "1",
        ]
    )

    assert eval_path.exists()
    payload = json.loads(eval_path.read_text(encoding="utf-8"))
    assert payload.get("type") == "crt_learned_suggestions_eval"
    metrics = payload.get("metrics") or {}
    assert int(metrics.get("examples") or 0) >= 1
