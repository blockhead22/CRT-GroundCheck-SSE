from __future__ import annotations

import json
import subprocess

from labs.frontier_observer_lab.frontier_observer_lab import (
    ALLOWED_TRACE_FIELDS,
    QUALITY_DIMENSIONS,
    ObserverConfig,
    build_observer_packet,
    run_codex_observer,
)


def _grade_payload() -> dict:
    return {
        "verdict": "review",
        "scores": {dimension: 4 for dimension in QUALITY_DIMENSIONS},
        "summary": "Useful answer, but the source boundary should be clearer.",
        "findings": [{
            "dimension": "source_fidelity",
            "severity": "medium",
            "answer_excerpt": "I know this because...",
            "reason": "The answer did not name whether the basis was memory or inference.",
        }],
        "suggestions": [{
            "target": "verifier",
            "proposal": "Check that provenance follow-ups name their evidence class.",
            "expected_effect": "Reduce unsupported certainty without templating final prose.",
        }],
    }


def test_observer_defaults_off_and_has_no_write_controls(monkeypatch):
    for name in (
        "AETHER_FRONTIER_OBSERVER_ENABLED",
        "AETHER_FRONTIER_OBSERVER_SAMPLE_RATE",
        "AETHER_FRONTIER_OBSERVER_COMMAND",
        "AETHER_FRONTIER_OBSERVER_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    config = ObserverConfig.from_env()
    assert config.enabled is False
    assert config.sample_rate == 0.0
    assert not hasattr(config, "memory_write_allowed")
    assert not hasattr(config, "auto_apply")


def test_packet_allows_only_public_trace_summary_and_bounds_text():
    config = ObserverConfig(max_prompt_chars=10, max_answer_chars=12)
    packet = build_observer_packet(
        turn_id="turn-1",
        user_prompt="0123456789extra",
        accepted_answer="abcdefghijklmnop",
        public_trace={
            "route": "general_local",
            "public_steps": ["source", "render", "verify"],
            "raw_hidden_chain_of_thought": "must not cross boundary",
            "memory_candidates": [{"sensitive": "must not cross boundary"}],
        },
        config=config,
    )
    assert packet.user_prompt == "0123456789"
    assert packet.accepted_answer == "abcdefghijkl"
    assert set(packet.public_trace).issubset(ALLOWED_TRACE_FIELDS)
    assert "raw_hidden_chain_of_thought" not in packet.public_trace
    assert "memory_candidates" not in packet.public_trace


def test_disabled_observer_never_invokes_runner():
    packet = build_observer_packet(
        turn_id="turn-disabled",
        user_prompt="hello",
        accepted_answer="hi",
        public_trace={},
    )

    def forbidden_runner(*args, **kwargs):
        raise AssertionError("runner must not be called")

    result = run_codex_observer(
        packet,
        config=ObserverConfig(enabled=False, sample_rate=1.0),
        runner=forbidden_runner,
    )
    assert result.status == "skipped_disabled"
    assert result.answer_effect is False
    assert result.memory_writes is False


def test_codex_observer_is_ephemeral_read_only_structured_and_inert():
    packet = build_observer_packet(
        turn_id="turn-live",
        user_prompt="How do you know?",
        accepted_answer="I know this because governed memory released the fact.",
        public_trace={"route": "general_local", "verifier_status": "passed"},
    )
    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(_grade_payload()),
            stderr="",
        )

    result = run_codex_observer(
        packet,
        config=ObserverConfig(enabled=True, sample_rate=1.0, model="gpt-test"),
        runner=fake_runner,
    )
    assert result.status == "completed"
    assert result.grade is not None
    assert result.grade.authority_applied is False
    assert all(item.requires_human_review for item in result.grade.suggestions)
    command = captured["command"]
    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--output-schema" in command
    assert command[command.index("--model") + 1] == "gpt-test"
    assert captured["cwd"]
    sent = json.loads(captured["input"])
    assert sent["accepted_answer"] == packet.accepted_answer
    assert "memory_candidates" not in sent["public_trace"]
    assert result.memory_writes is False
    assert result.support_reflection_writes is False
    assert result.policy_or_route_mutation is False
    assert result.answer_effect is False


def test_invalid_or_authority_seeking_output_fails_closed():
    packet = build_observer_packet(
        turn_id="turn-invalid",
        user_prompt="hello",
        accepted_answer="hello",
        public_trace={},
    )
    payload = _grade_payload()
    payload["suggestions"][0]["target"] = "write_memory"

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payload),
            stderr="",
        )

    result = run_codex_observer(
        packet,
        config=ObserverConfig(enabled=True, sample_rate=1.0),
        runner=fake_runner,
    )
    assert result.status == "failed"
    assert result.grade is None
    assert result.answer_effect is False
    assert result.memory_writes is False

