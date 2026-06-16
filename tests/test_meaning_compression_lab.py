from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem

from labs.meaning_compression_lab.run_lab import (
    canonical_meaning_state,
    run,
    scenario_from_crt_memory_db,
    score_scenario,
)


def _aggregate_by_name(out):
    return {row["name"]: row for row in out["aggregate_representations"]}


def _scenario(out, name):
    return next(s for s in out["scenarios"] if s["name"] == name)


def _rows_by_name(scenario):
    return {row["name"]: row for row in scenario["representations"]}


def _store_user_fact(memory, text, *, channel="webchat", thread_id="lab-thread"):
    return memory.store_memory(
        text=text,
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel=channel,
        kind="user_fact",
        thread_id=thread_id,
    )


def _store_locked_ops(memory, text, *, thread_id="lab-thread"):
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


def test_crt_compressed_preserves_structure_across_scenarios():
    out = run(write_results=False)
    rows = _aggregate_by_name(out)

    assert out["scenario_count"] == 5
    assert out["evidence_counts"] == {"fixture": 5}
    assert rows["crt_compressed"]["avg_structural_score"] == 1.0
    assert rows["crt_compressed"]["avg_behavior_score"] == 1.0
    assert rows["crt_compressed"]["avg_structural_score"] > rows["naive_summary"]["avg_structural_score"]
    assert rows["crt_compressed"]["avg_structural_score"] > rows["slot_only"]["avg_structural_score"]
    assert rows["crt_compressed"]["avg_meaning_density"] > rows["full_transcript"]["avg_meaning_density"]


def test_each_scenario_has_full_and_crt_structural_equivalence():
    out = run(write_results=False)

    for scenario in out["scenarios"]:
        rows = _rows_by_name(scenario)
        assert rows["full_transcript"]["structural_score"] == 1.0
        assert rows["crt_compressed"]["structural_score"] == 1.0
        assert rows["crt_compressed"]["size_bytes"] < rows["full_transcript"]["size_bytes"]


def test_scenario_sensitivity_identifies_load_bearing_layers():
    out = run(write_results=False)

    identity = _scenario(out, "identity_flip")
    employer = _scenario(out, "employer_correction")
    authority = _scenario(out, "authority_boundary")
    policy = _scenario(out, "policy_constraint")

    identity_impacts = {item["perturbation"]: item for item in identity["semantic_sensitivity"]}
    employer_impacts = {item["perturbation"]: item for item in employer["semantic_sensitivity"]}
    authority_impacts = {item["perturbation"]: item for item in authority["semantic_sensitivity"]}
    policy_impacts = {item["perturbation"]: item for item in policy["semantic_sensitivity"]}

    assert identity_impacts["remove_contradictions"]["damage"] > 0
    assert "contradiction:name" in identity_impacts["remove_contradictions"]["failed_invariants"]
    assert employer_impacts["remove_contradictions"]["damage"] > 0
    assert "volatility:employer" in employer_impacts["remove_contradictions"]["failed_invariants"]
    assert authority_impacts["remove_authority"]["damage"] == 1.0
    assert policy_impacts["remove_policies"]["damage"] == 1.0


def test_bit_sensitivity_maps_bit_flips_to_structural_failures():
    out = run(write_results=False)
    employer = _scenario(out, "employer_correction")
    impacts = {item["bit"]: item for item in employer["bit_sensitivity"]}

    assert impacts["flipped:employer"]["damage"] > 0
    assert impacts["contradiction:employer"]["damage"] > 0
    assert "bit:flipped:employer" in impacts["flipped:employer"]["failed_invariants"]
    assert "bit:contradiction:employer" in impacts["contradiction:employer"]["failed_invariants"]


def test_crt_db_replay_uses_actual_store_for_name_correction(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))

    _store_user_fact(memory, "My name is Sarah.")
    _store_user_fact(memory, "Actually, my name is Emily.")

    scenario = scenario_from_crt_memory_db(
        db_path,
        name="actual_crt_name_replay",
        thread_id="lab-thread",
    )
    assert [m.value for m in scenario.memories if m.slot == "name"] == ["Sarah", "Emily"]
    assert scenario.memories[-1].prior_value == "Sarah"

    state = canonical_meaning_state(scenario.memories)
    assert state["facts"]["name"] == "Emily"
    assert state["history"]["name"] == ["Sarah", "Emily"]
    assert state["contradictions"] == [
        {"slot": "name", "old": "Sarah", "new": "Emily", "status": "preserved"}
    ]

    rows = _rows_by_name(score_scenario(scenario))
    assert rows["crt_compressed"]["structural_score"] == 1.0
    assert rows["slot_only"]["structural_score"] < 1.0


def test_crt_db_replay_uses_actual_store_for_employer_correction(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))

    _store_user_fact(memory, "I work at Microsoft as a senior developer.")
    _store_user_fact(memory, "Actually, I work at Amazon, not Microsoft.")

    scenario = scenario_from_crt_memory_db(
        db_path,
        name="actual_crt_employer_replay",
        thread_id="lab-thread",
    )
    state = canonical_meaning_state(scenario.memories)

    assert scenario.evidence == "crt_db_replay"
    assert state["facts"]["employer"] == "Amazon"
    assert state["history"]["employer"] == ["Microsoft", "Amazon"]
    assert state["contradictions"] == [
        {"slot": "employer", "old": "Microsoft", "new": "Amazon", "status": "preserved"}
    ]
    assert state["reaction_policy"]["employer"] == "answer_current_with_history"

    rows = _rows_by_name(score_scenario(scenario))
    assert rows["crt_compressed"]["structural_score"] == 1.0
    assert rows["slot_only"]["structural_score"] < 1.0


def test_crt_db_replay_preserves_social_authority_boundary(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))

    stored = _store_user_fact(memory, "My favorite color is blue.", channel="moltbook")
    assert stored.authority == "provisional"
    assert stored.kind == "observation"

    scenario = scenario_from_crt_memory_db(db_path, thread_id="lab-thread")
    state = canonical_meaning_state(scenario.memories)

    assert "favorite_color" not in state["facts"]
    assert state["authority"]["favorite_color"] == "provisional_social"
    assert state["reaction_policy"]["favorite_color"] == "withhold_until_confirmed"


def test_crt_db_replay_preserves_locked_force_push_policy(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))

    stored = _store_locked_ops(memory, "Never force push to main.")
    assert stored.authority == "locked"
    assert stored.kind == "ops"

    scenario = scenario_from_crt_memory_db(db_path, thread_id="lab-thread")
    state = canonical_meaning_state(scenario.memories)

    assert state["policies"]["git.force_push_main"] == "forbidden"
    assert state["reaction_policy"]["git.force_push_main"] == "refuse_action"
    assert state["bit_flags"]["policy:git.force_push_main=forbidden"] is True

    rows = _rows_by_name(score_scenario(scenario))
    assert rows["crt_compressed"]["structural_score"] == 1.0
    assert rows["naive_summary"]["structural_score"] < 1.0


def test_run_report_distinguishes_fixture_and_crt_replay_evidence(tmp_path):
    db_path = tmp_path / "crt.db"
    memory = CRTMemorySystem(db_path=str(db_path))
    _store_user_fact(memory, "My name is Sarah.")

    replay = scenario_from_crt_memory_db(db_path, thread_id="lab-thread")
    out = run(write_results=False, scenarios=[replay])

    assert out["evidence_counts"] == {"crt_db_replay": 1}
    assert out["scenarios"][0]["evidence"] == "crt_db_replay"
