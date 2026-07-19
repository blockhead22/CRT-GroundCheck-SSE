from labs.meaning_compression_lab.generative_governance_spike import (
    GovernanceReceipt,
    build_governance_trace,
    run_spike,
)


def test_spike_pack_passes_without_writes_or_raw_cot():
    result = run_spike()

    assert result["passed"] is True
    assert result["case_count"] == 5
    assert result["writes_performed"] is False
    assert result["memory_write_performed"] is False
    assert result["support_pattern_import_performed"] is False
    assert result["reflection_create_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False


def test_weak_personal_synthesis_generates_boundary_before_model():
    trace = build_governance_trace(
        "Who am I becoming as a founder?",
        task_type="personal_synthesis",
    )

    assert trace.answerability == "insufficient_evidence"
    assert trace.evidence_state == "no_receipts"
    assert trace.model_render_needed is False
    assert "governance_can_answer_boundary_without_holden" == trace.model_render_reason
    assert any("identity claims" in claim for claim in trace.blocked_claims)
    assert any(item["candidate_type"] == "receipt_request_pattern" for item in trace.review_candidates)
    assert "I am treating this as personal_synthesis" in trace.governance_only_answer
    assert trace.raw_chain_of_thought_stored is False


def test_self_boundary_separates_user_self_from_aether_self():
    trace = build_governance_trace(
        "Could generative governance respond before the model?",
        task_type="architecture_synthesis",
        context="Aether routes, builds Mirus packets, verifies, repairs, and stores durable traces.",
    )

    assert "facts, memories, preferences" in trace.self_boundary["user_self"]
    assert "intent analysis, route choice" in trace.self_boundary["aether_self"]
    assert any("Separate USER_SELF claims from AETHER_SELF" in item for item in trace.response_spine)
    assert "user facts are separate from aether governance state" in trace.vectorizable_trace_text


def test_grounded_personal_synthesis_builds_spine_for_holden_render():
    trace = build_governance_trace(
        "What pattern do you see in me right now?",
        task_type="personal_synthesis",
        receipts=(
            GovernanceReceipt("r1", "user_prompt", "Road America video posted.", tags=("concrete_receipt",)),
            GovernanceReceipt("r2", "user_prompt", "12,730 steps logged.", tags=("concrete_receipt",)),
        ),
    )

    assert trace.answerability == "answerable"
    assert trace.evidence_state == "sufficient_receipts"
    assert trace.model_render_needed is True
    assert trace.model_render_reason == "holden_or_model_useful_for_humane_nuanced_render"
    assert any("bounded pattern claims" in claim for claim in trace.allowed_claims)
    assert any("Use receipts before pattern language" in item for item in trace.response_spine)
    assert "receipt ids: r1, r2" in " ".join(trace.response_spine)


def test_memory_conflict_is_review_not_generated_truth():
    trace = build_governance_trace(
        "Where do I currently work?",
        task_type="exact_memory",
        conflict_slots=("user:employer",),
    )

    assert trace.answerability == "needs_memory_review"
    assert trace.evidence_state == "conflicted_receipts"
    assert trace.model_render_needed is False
    assert any("choose one conflicted memory value" in claim for claim in trace.blocked_claims)
    assert any(item["candidate_type"] == "contradiction_review" for item in trace.review_candidates)
    assert "should not choose one value" in trace.governance_only_answer


def test_vectorizable_trace_text_carries_retrieval_features():
    trace = build_governance_trace(
        "Could the print shop and camera work become a realistic small business lane?",
        task_type="business_planning",
        context="The Printing Lair handles stickers and low-batch prints.\nCamera/video work is active but not proven as full-time income.",
    )

    text = trace.vectorizable_trace_text

    assert "intent: business_planning" in text
    assert "evidence_state: sufficient_receipts" in text
    assert "answerability: answerable" in text
    assert "allowed_claims:" in text
    assert "blocked_claims:" in text
    assert "response_spine:" in text
    assert "guaranteed income" in text
