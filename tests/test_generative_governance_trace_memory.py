from labs.meaning_compression_lab.generative_governance_spike import build_governance_trace
from labs.meaning_compression_lab.generative_governance_trace_memory import (
    build_trace_memory_records,
    decide_from_trace_memory,
    holdout_cases,
    retrieve_similar_traces,
    run_trace_memory,
    vectorize_trace,
)


def test_trace_memory_passes_without_writes_or_raw_cot():
    result = run_trace_memory()

    assert result["passed"] is True
    assert result["case_count"] == 5
    assert result["training_record_count"] == 5
    assert result["writes_performed"] is False
    assert result["memory_write_performed"] is False
    assert result["support_pattern_import_performed"] is False
    assert result["reflection_create_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False


def test_trace_memory_chooses_governance_only_for_boundary_cases():
    result = run_trace_memory()
    by_case = {row["case_id"]: row for row in result["rows"]}

    assert by_case["holdout_personal_no_receipts"]["actual_decision"] == "governance_only"
    assert by_case["holdout_memory_conflict"]["actual_decision"] == "governance_only"


def test_trace_memory_chooses_holden_render_for_grounded_cases():
    result = run_trace_memory()
    by_case = {row["case_id"]: row for row in result["rows"]}

    assert by_case["holdout_personal_grounded_receipts"]["actual_decision"] == "governance_plus_model"
    assert by_case["holdout_architecture_governance"]["actual_decision"] == "governance_plus_model"
    assert by_case["holdout_business_bounded"]["actual_decision"] == "governance_plus_model"


def test_vector_surface_prioritizes_governance_features():
    trace = build_governance_trace(
        "Can you tell me who I am becoming from all this?",
        task_type="personal_synthesis",
    )
    vector = vectorize_trace(trace)

    assert vector["intent::personal_synthesis"] == 4.0
    assert vector["evidence::no_receipts"] == 3.0
    assert vector["answerability::insufficient_evidence"] == 4.0
    assert vector["render_needed::False"] == 2.0
    assert vector["review::receipt_request_pattern"] == 2.0


def test_retrieval_finds_similar_boundary_trace_before_decision():
    records = build_trace_memory_records()
    case = next(item for item in holdout_cases() if item.case_id == "holdout_personal_no_receipts")
    trace = build_governance_trace(case.query, task_type=case.task_type, context=case.context)

    retrieved = retrieve_similar_traces(trace, records, top_k=1)
    decision = decide_from_trace_memory(trace, records)

    assert retrieved[0].record_id == "weak_personal_receipts_boundary"
    assert retrieved[0].decision == "governance_only"
    assert decision.decision == "governance_only"
    assert decision.governance_fallback == "governance_only"
