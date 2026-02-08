from __future__ import annotations

import json
from pathlib import Path

from personal_agent.dnnt.background_learning import (
    BackgroundLearningConfig,
    DNNTBackgroundLearner,
)
from personal_agent.dnnt.inference import ReasoningInference
from personal_agent.dnnt.trust_gate import TrustGate, TrustGateConfig


def test_trust_gate_rejects_recent_corrections() -> None:
    gate = TrustGate(
        TrustGateConfig(
            min_fact_trust=0.5,
            max_unresolved_contradictions=0,
            require_groundcheck_pass=False,
            reject_if_corrected_within_turns=3,
        )
    )
    accepted, reason = gate.should_accept(
        facts=["favorite_color=blue (0.91)"],
        meta={"was_corrected": True, "turns_since_response": 2},
    )
    assert accepted is False
    assert reason.startswith("corrected_recently")


def test_trust_gate_accepts_when_correction_window_passed() -> None:
    gate = TrustGate(
        TrustGateConfig(
            min_fact_trust=0.5,
            max_unresolved_contradictions=0,
            require_groundcheck_pass=False,
            reject_if_corrected_within_turns=2,
        )
    )
    accepted, reason = gate.should_accept(
        facts=["favorite_color=blue (0.91)"],
        meta={"was_corrected": True, "turns_since_response": 3},
    )
    assert accepted is True
    assert reason == "accepted"


def test_background_learning_reads_collected_examples_and_updates_state(tmp_path: Path) -> None:
    collected_path = tmp_path / "collected.jsonl"
    state_path = tmp_path / "state.json"
    model_out = tmp_path / "models" / "dnnt"

    records = [
        {
            "query": "Where do I work?",
            "facts": ["employer=DataCore (0.92)"],
            "thinking": "Use high-trust slot memory.",
            "response": "You work at DataCore.",
            "confidence": 0.9,
            "thread_id": "t1",
        },
        {
            "query": "What is my favorite color?",
            "facts": ["favorite_color=cyan (0.89)"],
            "thinking": "Read favorite_color slot.",
            "response": "Your favorite color is cyan.",
            "confidence": 0.88,
            "thread_id": "t1",
        },
    ]
    with open(collected_path, "w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    cfg = BackgroundLearningConfig(
        output_dir=str(model_out),
        collected_examples_path=str(collected_path),
        collapse_trails_db_path=str(tmp_path / "missing_collapse.db"),
        active_learning_db_path=str(tmp_path / "missing_active.db"),
        state_path=str(state_path),
        min_new_examples=5,
        max_examples_per_cycle=16,
        max_steps_per_cycle=5,
    )
    learner = DNNTBackgroundLearner(config=cfg)
    summary = learner.run_once()

    assert summary["trained"] is False
    assert summary["candidate_examples"] == 2
    assert "skipped_insufficient_examples" in summary["status"]
    assert state_path.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert int(state.get("collected_offset", 0)) > 0
    assert state.get("last_cycle_examples") == 2


def test_inference_hot_reload_detects_model_signature_change(tmp_path: Path) -> None:
    model_dir = tmp_path / "dnnt_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.pt").write_bytes(b"placeholder")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    engine = ReasoningInference(model_path=str(tmp_path / "missing_model"), collect_training_data=False)
    engine.model_path = model_dir
    engine.auto_reload_enabled = True
    engine.reload_check_interval_sec = 0.0
    engine._loaded_signature = (1.0, 1.0, 1.0)

    calls: list[str] = []

    def fake_load(path: str) -> None:
        calls.append(path)
        engine.model_loaded = True
        engine._loaded_signature = (2.0, 1.0, 1.0)

    sig_calls = {"count": 0}

    def fake_sig(_: Path) -> tuple[float, float, float]:
        sig_calls["count"] += 1
        if sig_calls["count"] == 1:
            return (1.0, 1.0, 1.0)
        return (2.0, 1.0, 1.0)

    engine.load_model = fake_load  # type: ignore[assignment]
    engine._model_signature = fake_sig  # type: ignore[assignment]

    engine._maybe_hot_reload_model()
    assert calls == []
    assert engine.hot_reload_count == 0

    engine._last_reload_check_at = 0.0
    engine._maybe_hot_reload_model()
    assert calls == [str(model_dir)]
    assert engine.hot_reload_count == 1
    assert engine.last_hot_reload_reason == "reloaded"
