from labs.meaning_compression_lab.evaluation_contract import (
    build_decision_trace,
    classify_severity,
)
from labs.meaning_compression_lab.plain_rag_eval import PROBES, judge_answer


def test_severity_scale_distinguishes_format_from_behavior():
    degraded = judge_answer(
        "CURRENT store_platform = custom e-commerce backend",
        PROBES["store_platform_authority_boundary"],
    )
    wrong = judge_answer("Shopify", PROBES["store_platform_authority_boundary"])

    assert classify_severity("store_platform_authority_boundary", degraded) == {
        "severity": "degraded_pass",
        "failure_layer": "output_format",
    }
    assert classify_severity("store_platform_authority_boundary", wrong) == {
        "severity": "severe_failure",
        "failure_layer": "executor_interpretation",
    }


def test_ordinary_stale_value_leak_is_failure_not_severe():
    judgment = judge_answer(
        "Amazon, previously Microsoft",
        PROBES["employer_correction"],
    )

    assert classify_severity("employer_correction", judgment) == {
        "severity": "failure",
        "failure_layer": "output_scope",
    }


def test_authority_case_with_correct_decision_but_scope_leak_is_not_severe():
    judgment = judge_answer(
        "Chicago is confirmed, though a tool provisionally suggested Los Angeles.",
        PROBES["tool_inferred_location_noise"],
    )

    assert judgment["meaning_passed"] is True
    assert judgment["scope_passed"] is False
    assert classify_severity("tool_inferred_location_noise", judgment) == {
        "severity": "failure",
        "failure_layer": "output_scope",
    }


def test_authority_case_with_unusable_label_but_no_wrong_value_is_not_severe():
    judgment = judge_answer(
        "store_platform = CURRENT",
        PROBES["store_platform_authority_boundary"],
    )

    assert judgment["meaning_passed"] is False
    assert judgment["scope_passed"] is True
    assert classify_severity("store_platform_authority_boundary", judgment) == {
        "severity": "failure",
        "failure_layer": "executor_interpretation",
    }


def test_decision_trace_contains_observable_chain_not_hidden_reasoning():
    judgment = judge_answer("Amazon", PROBES["employer_correction"])
    trace = build_decision_trace(
        scenario="employer_correction",
        arm="hybrid_crt",
        query="Where do I work?",
        retrieved_evidence=[{"text": "I now work at Amazon."}],
        state_transformation={"facts": {"employer": "Amazon"}},
        selected_rule="answer_current_only",
        supplied_context="CURRENT employer = Amazon",
        answer="Amazon",
        judgment=judgment,
    )

    assert trace["severity"] == "pass"
    assert trace["failure_layer"] is None
    assert trace["selected_rule"] == "answer_current_only"
    assert "chain_of_thought" not in trace
