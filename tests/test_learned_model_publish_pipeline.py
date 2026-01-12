from __future__ import annotations

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
    # Create repeated contradictions so the weak-label pipeline yields examples.
    rag.query("My name is Sarah.")
    rag.query("Actually, my name is Emily.")
    rag.query("Actually, my name is Sarah.")
    rag.query("Actually, my name is Emily.")


def test_publish_pipeline_dry_run_does_not_update_latest(tmp_path: Path, rag: CRTEnhancedRAG) -> None:
    _seed_contradictions(rag)

    from crt_learn_publish import run_train_eval_publish

    out_dir = tmp_path / "artifacts"
    latest = out_dir / "learned_suggestions.latest.joblib"

    res = run_train_eval_publish(
        out_dir=out_dir,
        publish_path=latest,
        memory_db=tmp_path / "mem.db",
        ledger_db=tmp_path / "ledger.db",
        min_train_examples=1,
        min_eval_examples=1,
        min_eval_accuracy=None,
        max_prefer_latest_rate=None,
        dry_run=True,
    )

    assert res.report_path
    assert res.trained_model_path
    assert Path(res.trained_model_path).exists()
    # Should not publish in dry run.
    assert not latest.exists()


def test_publish_pipeline_updates_latest_on_pass(tmp_path: Path, rag: CRTEnhancedRAG) -> None:
    _seed_contradictions(rag)

    from crt_learn_publish import run_train_eval_publish

    out_dir = tmp_path / "artifacts"
    latest = out_dir / "learned_suggestions.latest.joblib"

    res = run_train_eval_publish(
        out_dir=out_dir,
        publish_path=latest,
        memory_db=tmp_path / "mem.db",
        ledger_db=tmp_path / "ledger.db",
        min_train_examples=1,
        min_eval_examples=1,
        min_eval_accuracy=None,
        max_prefer_latest_rate=None,
        dry_run=False,
    )

    assert res.ok is True
    assert res.published_model_path is not None
    assert latest.exists()
    # Sidecars copied too.
    assert latest.with_suffix(".meta.json").exists()
    assert latest.with_suffix(".eval.json").exists()
