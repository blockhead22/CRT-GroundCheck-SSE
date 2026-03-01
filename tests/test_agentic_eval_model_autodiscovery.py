from __future__ import annotations

from tools.agentic_eval.model_autodiscovery import ModelProbeResult, select_models
import tools.agentic_eval.model_autodiscovery as md


def test_select_models_prefers_distinct_roles(monkeypatch):
    monkeypatch.setattr(md, "_list_ollama_models", lambda _url: ["alpha", "beta"])

    def fake_probe(*, ollama_base_url, model, role, attempts, timeout_seconds):
        score_map = {
            ("alpha", "attacker"): 95.0,
            ("alpha", "judge"): 80.0,
            ("beta", "attacker"): 88.0,
            ("beta", "judge"): 92.0,
        }
        score = score_map[(model, role)]
        return ModelProbeResult(
            model=model,
            role=role,
            valid_json_rate=1.0,
            avg_latency_ms=120.0,
            attempts=attempts,
            score=score,
            notes=[],
        )

    monkeypatch.setattr(md, "_probe_model_for_role", fake_probe)
    sel = select_models(
        ollama_base_url="http://127.0.0.1:11434",
        attacker_model=None,
        judge_model=None,
        probe_attempts=1,
        probe_timeout_seconds=5.0,
    )
    assert sel.attacker_model == "alpha"
    assert sel.judge_model == "beta"
    assert len(sel.probes) == 4


def test_select_models_requires_available_candidates(monkeypatch):
    monkeypatch.setattr(md, "_list_ollama_models", lambda _url: [])
    try:
        select_models(
            ollama_base_url="http://127.0.0.1:11434",
            attacker_model=None,
            judge_model=None,
        )
    except RuntimeError as exc:
        assert "No compatible Ollama chat models" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when no models are available")
