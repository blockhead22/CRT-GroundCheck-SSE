import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from labs.meaning_compression_lab.workbench_evidence_adapter import (
    adapt_rag_evidence_review_for_consolidation_preview,
    adapt_rag_suite_result_for_workbench_review,
    load_rag_suite_result_for_workbench_preview,
    load_rag_suite_result_for_workbench_review,
)


def _rag_result() -> dict:
    return {
        "lab": "local_router_rag_suite",
        "pack": "local_router_rag_adversarial_v2",
        "pack_path": "labs/meaning_compression_lab/replay_packs/local_router_rag_adversarial_v2.json",
        "case_count": 6,
        "case_ids": [],
        "modes": ["raw", "plain_rag", "scaffolded_rag", "governed"],
        "retrieval": {
            "corpus_chunk_count": 18,
            "k": 5,
            "method": "lexical_overlap_with_task_and_recency_tiebreak",
            "corpus_kinds": {
                "case_requirements": 6,
                "reference_response": 6,
                "user_prompt": 6,
            },
        },
        "aggregate": {
            "retrieval": {
                "avg_receipt_coverage": 1.0,
                "avg_concept_coverage": 1.0,
            },
            "raw": {
                "answer_pass_count": 0,
                "answer_avg_score": 0.492,
                "trace_pass_count": 0,
                "trace_avg_score": None,
                "repair_count": 0,
                "fallback_count": 0,
                "failure_count": 6,
                "failures_by_task_type": {"personal_synthesis": 3},
            },
            "plain_rag": {
                "answer_pass_count": 1,
                "answer_avg_score": 0.54,
                "trace_pass_count": 0,
                "trace_avg_score": None,
                "repair_count": 0,
                "fallback_count": 0,
                "failure_count": 5,
                "failures_by_task_type": {"personal_synthesis": 3},
            },
            "scaffolded_rag": {
                "answer_pass_count": 5,
                "answer_avg_score": 0.753,
                "trace_pass_count": 0,
                "trace_avg_score": None,
                "repair_count": 0,
                "fallback_count": 0,
                "failure_count": 1,
                "failures_by_task_type": {"personal_synthesis": 1},
            },
            "governed": {
                "answer_pass_count": 6,
                "answer_avg_score": 0.775,
                "trace_pass_count": 6,
                "trace_avg_score": 1.0,
                "repair_count": 0,
                "fallback_count": 0,
                "failure_count": 0,
                "failures_by_task_type": {},
            },
        },
        "rows": [],
    }


def test_rag_suite_result_maps_to_review_only_workbench_evidence():
    out = adapt_rag_suite_result_for_workbench_review(_rag_result())

    assert out["kind"] == "local_router_rag_evidence_review"
    assert out["pack"] == "local_router_rag_adversarial_v2"
    assert out["case_count"] == 6
    assert out["baseline_to_beat"] == "scaffolded_rag"
    assert out["baselines"]["governed"]["answer_pass_rate"] == 1.0
    assert out["baselines"]["scaffolded_rag"]["answer_pass_rate"] == 0.833
    assert out["governed_delta_vs_scaffolded_rag"] == {
        "answer_pass_delta": 1,
        "answer_avg_score_delta": 0.022,
        "trace_complete": True,
    }
    assert "scaffolded_rag_is_serious_baseline" in out["review_flags"]
    assert "perfect_governed_score_requires_holdout" in out["review_flags"]
    assert "governed_trace_complete" in out["review_flags"]


def test_rag_suite_evidence_adapter_does_not_authorize_learning_or_memory():
    out = adapt_rag_suite_result_for_workbench_review(_rag_result())

    assert out["safety_contract"] == {
        "promotion_status": "review_only",
        "memory_writes_allowed": False,
        "raw_chain_of_thought_stored": False,
        "silent_policy_mutation_allowed": False,
        "review_required_before_promotion": True,
    }
    assert out["failure_summary"] == {
        "raw": {"personal_synthesis": 3},
        "plain_rag": {"personal_synthesis": 3},
        "scaffolded_rag": {"personal_synthesis": 1},
    }
    assert "larger blind/adversarial mix" in out["next_review"]


def test_load_rag_suite_result_sets_source_result_path(tmp_path):
    result_path = tmp_path / "rag_result.json"
    result_path.write_text(json.dumps(_rag_result()), encoding="utf-8")

    out = load_rag_suite_result_for_workbench_review(result_path)

    assert out["result_path"] == str(result_path)
    assert out["retrieval"]["corpus_chunk_count"] == 18
    assert out["retrieval"]["avg_receipt_coverage"] == 1.0


def test_rag_evidence_review_maps_to_preview_only_learner_candidate():
    review = adapt_rag_suite_result_for_workbench_review(_rag_result(), result_path="result.json")

    preview = adapt_rag_evidence_review_for_consolidation_preview(review)

    assert preview["mode"] == "preview_only"
    assert preview["writes_performed"] is False
    assert preview["memory_ingestion_performed"] is False
    assert preview["support_pattern_import_performed"] is False
    assert preview["reflection_create_performed"] is False
    assert preview["inspected_turn_count"] == 6
    [candidate] = preview["candidates"]
    assert candidate["candidate_id"] == "local_router_rag_evidence_local_router_rag_adversarial_v2"
    assert candidate["category"] == "local_router_rag_evidence"
    assert candidate["summary"] == (
        "Adversarial v2: governed passed 6/6 with trace 6/6; scaffolded RAG passed 5/6."
    )
    assert candidate["memory_write_allowed"] is False
    assert candidate["confirmed_fact"] is False
    assert candidate["review_route"]["surface"] == "reflections"
    assert candidate["review_route"]["requires_adapter"] is True
    assert candidate["review_route"]["draft"]["confidence"] == 0.62
    assert candidate["review_route"]["draft"]["time_window"] == "local-router RAG local_router_rag_adversarial_v2"
    assert candidate["evidence"][0]["summary"] == (
        "governed 6/6 trace 6/6 vs scaffolded_rag 5/6; delta +1 pass, +0.022 avg"
    )
    assert "memory writes blocked" in candidate["evidence"][1]["summary"]


def test_load_rag_suite_result_for_preview_uses_loaded_result_path(tmp_path):
    result_path = tmp_path / "rag_result.json"
    result_path.write_text(json.dumps(_rag_result()), encoding="utf-8")

    preview = load_rag_suite_result_for_workbench_preview(result_path)

    candidate = preview["candidates"][0]
    assert candidate["evidence"][0]["reference_id"] == str(result_path)
    assert candidate["review_route"]["draft"]["suggested_experiment"]
