from labs.meaning_compression_lab.generative_governance_lab import (
    AutoPolicy,
    EvidenceReceipt,
    decide_proposal,
    proposal_from_model_json,
    run_lab,
)


def test_generative_governance_lab_passes_auto_mode():
    result = run_lab(AutoPolicy(mode="auto"))

    assert result["passed"] is True
    assert result["case_count"] == 6
    assert result["writes_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False
    assert result["auto_actions_used"] == 2


def test_small_model_archive_health_proposal_is_answer_only_not_memory():
    proposal = proposal_from_model_json({
        "proposal_id": "p_archive_health",
        "intent": "archive_search",
        "category": "archive_evidence",
        "proposed_action": "answer_from_sources",
        "sensitive_domains": ["health"],
        "required_tools": ["document_search"],
        "claim_policy": "source_bound_only",
        "evidence_ids": ["doc_health"],
        "confidence": 0.9,
    })

    decision = decide_proposal(
        proposal,
        [EvidenceReceipt("doc_health", "chatgpt_archive", "archive", "bounded health archive hit")],
        policy=AutoPolicy(mode="auto"),
    )

    assert decision.decision == "answer_only"
    assert decision.review_required is False
    assert decision.memory_write_allowed is False
    assert "sensitive_domains=health" in decision.warnings


def test_low_risk_preference_requires_repeated_user_receipts_for_auto():
    proposal = proposal_from_model_json({
        "proposal_id": "p_single",
        "intent": "memory_fact_candidate",
        "category": "low_risk_preference",
        "proposed_action": "promote_candidate",
        "slot_id": "user:favorite_drink",
        "proposed_value": "iced coffee",
        "evidence_ids": ["u1"],
        "confidence": 0.9,
    })

    decision = decide_proposal(
        proposal,
        [EvidenceReceipt("u1", "chat_turn", "user_current", "I also like iced coffee.")],
        policy=AutoPolicy(mode="auto"),
    )

    assert decision.decision == "review"
    assert decision.reason == "insufficient_user_receipts_for_auto"
    assert decision.memory_write_allowed is False


def test_sensitive_fact_never_auto_promotes_even_with_repeated_user_receipts():
    proposal = proposal_from_model_json({
        "proposal_id": "p_health",
        "intent": "memory_fact_candidate",
        "category": "low_risk_preference",
        "proposed_action": "promote_candidate",
        "slot_id": "user:health_history",
        "proposed_value": "leukemia survivor",
        "sensitive_domains": ["health"],
        "evidence_ids": ["u1", "u2"],
        "confidence": 0.99,
    })

    decision = decide_proposal(
        proposal,
        [
            EvidenceReceipt("u1", "chat_turn", "user_current", "I had leukemia."),
            EvidenceReceipt("u2", "chat_turn", "user_current", "I am a leukemia survivor."),
        ],
        policy=AutoPolicy(mode="auto"),
    )

    assert decision.decision == "review"
    assert decision.reason == "sensitive_fact_requires_human_review"
    assert decision.memory_write_allowed is False


def test_auto_mode_rate_limits_promotion():
    proposal = proposal_from_model_json({
        "proposal_id": "p_favorite",
        "intent": "memory_fact_candidate",
        "category": "low_risk_preference",
        "proposed_action": "promote_candidate",
        "slot_id": "user:favorite_sports_team",
        "proposed_value": "Milwaukee Brewers",
        "evidence_ids": ["u1", "u2"],
        "confidence": 0.9,
    })

    decision = decide_proposal(
        proposal,
        [
            EvidenceReceipt("u1", "chat_turn", "user_current", "I like the Brewers."),
            EvidenceReceipt("u2", "chat_turn", "user_current", "The Brewers are my favorite team."),
        ],
        policy=AutoPolicy(mode="auto", max_auto_actions_per_run=1),
        auto_actions_used=1,
    )

    assert decision.decision == "review"
    assert decision.reason == "auto_rate_limit_reached"
