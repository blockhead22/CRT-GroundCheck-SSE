from __future__ import annotations

from labs.mirus_router_harness_lab.learned_mirus_scorer_lab import (
    LABELS,
    build_review_only_candidates,
    deterministic_baseline,
    holdout_cases,
    run_lab,
)


def _result_by_id(report, case_id):
    return next(result for result in report["results"] if result["case_id"] == case_id)


def test_learned_mirus_scorer_beats_brittle_baseline_on_holdout():
    report = run_lab(write_results=False)

    summary = report["summary"]
    assert report["lab"] == "learned_mirus_scorer_v0"
    assert set(report["labels"]) == set(LABELS)
    assert summary["learned_passed"] >= 6
    assert summary["learned_passed"] > summary["baseline_passed"]
    assert summary["safety_passed"] == summary["total"]


def test_learned_scorer_handles_contextual_orange_reason_without_confirming_memory():
    report = run_lab(write_results=False)
    result = _result_by_id(report, "holdout_orange_reason_from_context")

    assert result["expected"] == "review_candidate"
    assert result["predicted"] == "review_candidate"
    assert result["baseline_passed"] is False
    assert result["safety_passed"] is True
    [candidate] = result["candidates"]
    assert candidate["slot_id"] == "user:favorite_flower_reason"
    assert candidate["review_required"] is True
    assert candidate["memory_write_allowed"] is False
    assert candidate["confirmed_fact"] is False
    assert "deterministic review required" in candidate["source_boundary"]


def test_short_confirmation_can_be_ranked_without_becoming_truth():
    report = run_lab(write_results=False)
    result = _result_by_id(report, "holdout_short_confirmation_sports")

    assert result["expected"] == "confirmation_candidate"
    assert result["predicted"] == "confirmation_candidate"
    assert result["candidates"][0]["slot_id"] == "user:favorite_sports_team"
    assert result["candidates"][0]["proposed_value"] == "Milwaukee Brewers"
    assert result["candidates"][0]["confirmed_fact"] is False


def test_sensitive_archive_prompt_routes_to_search_not_memory_candidate():
    report = run_lab(write_results=False)
    result = _result_by_id(report, "holdout_archive_sensitive")

    assert result["expected"] == "archive_search"
    assert result["predicted"] == "archive_search"
    assert result["candidates"] == []
    assert result["safety_passed"] is True


def test_deterministic_candidate_payload_guard_is_separate_from_prediction():
    case = next(row for row in holdout_cases() if row.case_id == "holdout_orange_reason_from_context")

    assert deterministic_baseline(case) != case.label
    candidates = build_review_only_candidates(case, "review_candidate")

    assert candidates
    assert all(candidate["review_required"] is True for candidate in candidates)
    assert all(candidate["memory_write_allowed"] is False for candidate in candidates)
    assert all(candidate["confirmed_fact"] is False for candidate in candidates)
