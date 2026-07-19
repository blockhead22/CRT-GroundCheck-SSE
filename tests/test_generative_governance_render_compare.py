from labs.meaning_compression_lab.generative_governance_render_compare import (
    compare_cases,
    evaluate_render,
    run_compare,
)
from labs.meaning_compression_lab.generative_governance_spike import build_governance_trace


def test_render_compare_passes_without_writes_or_raw_cot():
    result = run_compare()

    assert result["passed"] is True
    assert result["case_count"] == 5
    assert result["writes_performed"] is False
    assert result["memory_write_performed"] is False
    assert result["support_pattern_import_performed"] is False
    assert result["reflection_create_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False


def test_boundary_cases_choose_governance_only():
    result = run_compare()
    by_case = {row["case_id"]: row for row in result["rows"]}

    assert by_case["weak_personal_receipts_boundary"]["actual_best_mode"] == "governance_only"
    assert by_case["exact_memory_conflict"]["actual_best_mode"] == "governance_only"


def test_rich_cases_choose_governance_plus_model():
    result = run_compare()
    by_case = {row["case_id"]: row for row in result["rows"]}

    assert by_case["grounded_personal_synthesis"]["actual_best_mode"] == "governance_plus_model"
    assert by_case["architecture_governance"]["actual_best_mode"] == "governance_plus_model"
    assert by_case["business_planning"]["actual_best_mode"] == "governance_plus_model"


def test_model_only_is_risky_on_weak_personal_synthesis():
    case = next(item for item in compare_cases() if item.case_id == "weak_personal_receipts_boundary")
    trace = build_governance_trace(case.query, task_type=case.task_type)
    render = evaluate_render(
        "model_only",
        "You are becoming a resilient founder who is clearly entering a stronger chapter.",
        trace,
    )

    assert render.passed is False
    assert render.boundary_score < 0.75
    assert render.overclaim_risk > 0.35
    assert "identity_claim_from_weak_receipts" in render.notes


def test_governance_plus_model_uses_receipts_and_boundary_for_business():
    case = next(item for item in compare_cases() if item.case_id == "business_planning")
    trace = build_governance_trace(case.query, task_type=case.task_type, context=case.context)
    answer = (
        "I am treating this as business planning. Receipts: The Printing Lair handles "
        "stickers and low-batch prints; Camera/video work is active but not proven as "
        "full-time income. The bounded answer is yes, this can be explored as a "
        "realistic lane, but not as a guaranteed income claim or full-time replacement claim."
    )
    render = evaluate_render("governance_plus_model", answer, trace)

    assert render.passed is True
    assert render.boundary_score == 1.0
    assert render.evidence_score == 1.0
    assert render.overclaim_risk <= 0.35
