from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES
from labs.meaning_compression_lab.interface_pivot_eval import (
    project_scaffold,
    question_contract,
    validate_and_repair,
)
from labs.meaning_compression_lab.run_lab import canonical_meaning_state
from labs.meaning_compression_lab.scaffold_eval import build_meaning_scaffold


def test_current_projection_hides_history_contradiction_and_provisional():
    case = HELDOUT_CASES[0]
    scaffold = build_meaning_scaffold(case.scenario)
    projected = project_scaffold(scaffold, case.probe)
    kinds = {fragment["kind"] for fragment in projected["fragments"]}

    assert question_contract(case.probe).kind == "current"
    assert kinds <= {"current_fact", "authority"}
    assert any(fragment.get("value") == "Marcus" for fragment in projected["fragments"])
    assert all(fragment.get("value") != "David" for fragment in projected["fragments"])


def test_current_gate_repairs_history_leak_from_governed_state_without_expected_tokens():
    case = HELDOUT_CASES[0]
    state = canonical_meaning_state(case.scenario.memories)

    result = validate_and_repair(
        "Marcus (Previously Daniel)",
        probe=case.probe,
        state=state,
    )

    assert result["status"] == "repaired"
    assert result["released_answer"] == "Marcus"
    assert result["violations"] == ["leaked_noncurrent_value"]


def test_current_gate_releases_compliant_answer_without_false_repair():
    case = HELDOUT_CASES[0]
    state = canonical_meaning_state(case.scenario.memories)

    result = validate_and_repair("Marcus", probe=case.probe, state=state)

    assert result["status"] == "released"
    assert result["released_answer"] == "Marcus"
    assert result["repair_applied"] is False


def test_current_gate_repairs_internal_protocol_syntax():
    case = HELDOUT_CASES[4]
    state = canonical_meaning_state(case.scenario.memories)

    result = validate_and_repair(
        "CURRENT store_platform = Django commerce service",
        probe=case.probe,
        state=state,
    )

    assert result["status"] == "repaired"
    assert result["released_answer"] == "Django commerce service"
    assert "internal_scaffold_syntax" in result["violations"]


def test_policy_gate_repairs_missing_refusal_once():
    case = HELDOUT_CASES[5]
    state = canonical_meaning_state(case.scenario.memories)

    result = validate_and_repair(
        "Delete it recursively.",
        probe=case.probe,
        state=state,
    )

    assert result["status"] == "repaired"
    assert result["released_answer"].startswith("No.")
    assert result["violations"] == ["missing_policy_refusal"]
