from __future__ import annotations

from labs.mirus_router_harness_lab.original_router_lab import run_cases


def _result_by_id(report, case_id):
    return next(result for result in report["results"] if result["case_id"] == case_id)


def test_original_router_lab_routes_all_cases():
    report = run_cases()

    assert report["summary"] == {"passed": 5, "total": 5}


def test_mirus_multi_fact_candidates_are_review_only():
    report = run_cases()
    result = _result_by_id(report, "multi_fact_marigold_orange")

    assert result["intent_type"] == "mirus_extract_candidates"
    payload = result["slots"]["payload"]
    candidates = payload["candidates"]
    assert len(candidates) >= 2
    assert {candidate["slot"] for candidate in candidates} >= {
        "user:favorite_flower",
        "user:favorite_flower_reason",
    }
    assert payload["memory_write_allowed"] is False
    assert all(candidate["memory_write_allowed"] is False for candidate in candidates)
    assert all("review" in candidate["source_boundary"] for candidate in candidates)


def test_pending_short_confirmation_can_become_candidate():
    report = run_cases()
    result = _result_by_id(report, "short_confirmation_from_pending_sports_team")

    assert result["intent_type"] == "mirus_extract_candidates"
    candidates = result["slots"]["payload"]["candidates"]
    assert candidates == [
        {
            "kind": "profile_fact",
            "slot": "user:favorite_sports_team",
            "value": "Milwaukee Brewers",
            "reason": "model-assisted discovery candidate; requires review",
            "confidence": 0.84,
            "source_boundary": "not confirmed memory until reviewed",
            "memory_write_allowed": False,
        }
    ]


def test_archive_and_project_queries_route_to_bounded_tools():
    report = run_cases()
    archive = _result_by_id(report, "archive_search_gpt_logs")
    project = _result_by_id(report, "project_context_mill_bluff")

    assert archive["intent_type"] == "gpt_log_search"
    assert archive["slots"]["top_k"] == 5
    assert project["intent_type"] == "project_context_search"
    assert project["slots"]["project"] == "wisconsin-state-parks-map"


def test_casual_prefilter_preserves_original_no_tool_behavior():
    report = run_cases()
    casual = _result_by_id(report, "casual_hello_prefilter")

    assert casual["route"] == "conversational"
    assert casual["intent_type"] == "conversational"
    assert len(report["client_calls"]) == 4
