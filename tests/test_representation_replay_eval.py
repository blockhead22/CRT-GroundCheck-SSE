from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem

from labs.meaning_compression_lab.representation_replay import (
    run,
    run_bridge_candidate_comparison,
    scenarios_from_crt_db,
)
from labs.meaning_compression_lab.run_lab import scenario_pack


def _aggregate_by_name(out):
    return {row["name"]: row for row in out["aggregate_representations"]}


def _scenario(out, name):
    return next(row for row in out["scenarios"] if row["scenario"] == name)


def _representation(row, name):
    return next(rep for rep in row["representations"] if rep["name"] == name)


def _store_user_fact(memory, text, *, channel="webchat", thread_id="replay-thread"):
    return memory.store_memory(
        text=text,
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel=channel,
        kind="user_fact",
        thread_id=thread_id,
    )


def _store_locked_ops(memory, text, *, thread_id="replay-thread"):
    return memory.store_memory(
        text=text,
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "ops"},
        authority="locked",
        channel="webchat",
        kind="ops",
        thread_id=thread_id,
    )


def test_representation_replay_passes_full_hardening_pack():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )
    rows = _aggregate_by_name(out)

    assert out["scenario_count"] == 19
    assert rows["governed_scaffold"]["pass_count"] == 19
    assert rows["crt_compressed"]["pass_count"] == 19
    assert rows["governed_scaffold"]["avg_compression_ratio"] < 0.5
    assert rows["crt_compressed"]["avg_compression_ratio"] < 1.0


def test_representation_replay_identifies_lossy_layer_failures():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )
    rows = _aggregate_by_name(out)

    assert rows["quantized_scaffold"]["pass_count"] < rows["governed_scaffold"]["pass_count"]
    assert rows["context_bridge_profile"]["pass_count"] < rows["governed_scaffold"]["pass_count"]
    assert rows["context_bridge_profile_candidates"]["pass_count"] < rows["governed_scaffold"]["pass_count"]
    assert rows["context_bridge_profile"]["pass_count"] > rows["slot_only"]["pass_count"]
    assert rows["context_bridge_profile_candidates"]["pass_count"] > rows["slot_only"]["pass_count"]
    assert rows["slot_only"]["pass_count"] < rows["quantized_scaffold"]["pass_count"]
    assert rows["naive_summary"]["pass_count"] < rows["slot_only"]["pass_count"]
    assert rows["raw_retrieval"]["pass_count"] < rows["governed_scaffold"]["pass_count"]


def test_representation_replay_pinpoints_history_authority_and_reaction_layers():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )

    employer_history = _scenario(out, "employer_history_question")
    store_boundary = _scenario(out, "store_platform_authority_boundary")
    reaction_rule = _scenario(out, "favorite_color_reaction_rule")

    assert _representation(employer_history, "governed_scaffold")["judgment"]["passed"] is True
    assert _representation(employer_history, "quantized_scaffold")["judgment"]["passed"] is False
    assert _representation(store_boundary, "governed_scaffold")["judgment"]["passed"] is True
    assert _representation(store_boundary, "quantized_scaffold")["judgment"]["passed"] is False
    assert _representation(reaction_rule, "governed_scaffold")["judgment"]["passed"] is True
    assert _representation(reaction_rule, "quantized_scaffold")["judgment"]["passed"] is False


def test_context_bridge_profile_is_not_a_full_meaning_replay_substitute():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )
    rows = _aggregate_by_name(out)
    employer_history = _scenario(out, "employer_history_question")
    force_push = _scenario(out, "policy_constraint")
    current_name = _scenario(out, "identity_flip")

    assert rows["context_bridge_profile"]["pass_count"] == 10
    assert rows["context_bridge_profile"]["avg_compression_ratio"] > 1.0
    assert rows["context_bridge_profile_candidates"]["pass_count"] == rows["context_bridge_profile"]["pass_count"]
    assert rows["context_bridge_profile_candidates"]["avg_compression_ratio"] < rows["context_bridge_profile"]["avg_compression_ratio"]
    assert rows["context_bridge_profile_candidates"]["avg_compression_ratio"] < 1.0
    assert _representation(current_name, "context_bridge_profile")["judgment"]["passed"] is True
    assert _representation(employer_history, "context_bridge_profile")["judgment"]["passed"] is False
    assert _representation(force_push, "context_bridge_profile")["judgment"]["passed"] is False


def test_representation_replay_does_not_write_by_default_when_disabled():
    out = run(write_results=False)

    assert out["lab"] == "representation_replay_eval"
    assert "result_path" not in out


def test_representation_replay_derives_probe_cases_from_crt_db(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))

    _store_user_fact(memory, "My name is Sarah.")
    _store_user_fact(memory, "Actually, my name is Emily.")
    _store_user_fact(memory, "I work at Microsoft as a senior developer.")
    _store_user_fact(memory, "Actually, I work at Amazon, not Microsoft.")
    _store_user_fact(memory, "My favorite color is blue.", channel="moltbook")
    _store_locked_ops(memory, "Never force push to main.")

    scenarios, probes = scenarios_from_crt_db(db_path, thread_id="replay-thread")
    out = run(write_results=False, scenarios=scenarios, probes=probes)
    rows = _aggregate_by_name(out)

    assert out["evidence_counts"] == {"crt_db_replay": len(out["scenarios"])}
    assert {
        "crt_db_current_name",
        "crt_db_name_correction_status",
        "crt_db_current_employer",
        "crt_db_previous_employer",
        "crt_db_provisional_favorite_color",
        "crt_db_favorite_color_response_rule",
        "crt_db_locked_force_push_policy",
    }.issubset({row["scenario"] for row in out["scenarios"]})
    assert rows["governed_scaffold"]["pass_count"] == out["scenario_count"]
    assert rows["crt_compressed"]["pass_count"] == out["scenario_count"]
    assert rows["slot_only"]["pass_count"] < out["scenario_count"]


def test_bridge_candidate_packet_eval_splits_project_support_and_reflection_payloads():
    out = run_bridge_candidate_comparison(write_results=False)
    rows = _aggregate_by_name(out)
    project = _scenario(out, "bridge_project_packet")
    support = _scenario(out, "bridge_support_packet")
    reflection = _scenario(out, "bridge_reflection_packet")

    assert out["scenario_count"] == 3
    assert rows["context_bridge_full_packet"]["pass_count"] == 3
    assert rows["context_bridge_project_candidates"]["pass_count"] == 1
    assert rows["context_bridge_support_candidates"]["pass_count"] == 1
    assert rows["context_bridge_reflection_candidates"]["pass_count"] == 1
    assert rows["context_bridge_project_candidates"]["avg_compression_ratio"] < 0.5
    assert rows["context_bridge_support_candidates"]["avg_compression_ratio"] < 0.2
    assert rows["context_bridge_reflection_candidates"]["avg_compression_ratio"] < 0.2

    assert _representation(project, "context_bridge_project_candidates")["judgment"]["passed"] is True
    assert _representation(project, "context_bridge_support_candidates")["judgment"]["passed"] is False
    assert _representation(support, "context_bridge_support_candidates")["judgment"]["passed"] is True
    assert _representation(reflection, "context_bridge_reflection_candidates")["judgment"]["passed"] is True
