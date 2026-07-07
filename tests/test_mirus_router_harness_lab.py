from __future__ import annotations

from labs.mirus_router_harness_lab.original_router_lab import run_cases, run_governed_cases


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


class UnsafeModelClient:
    def __init__(self):
        self.calls = []

    def chat_with_tools(self, messages, tools, **kwargs):
        prompt = messages[-1]["content"]
        self.calls.append({"message": prompt})
        lower = prompt.lower()
        if "marigold" in lower:
            return {
                "tool_calls": [
                    {
                        "name": "mirus_extract_candidates",
                        "arguments": {
                            "payload": {
                                "candidates": [
                                    {
                                        "kind": "preference",
                                        "slot": "favorite_flower",
                                        "value": "marigolds",
                                        "reason": "they are orange",
                                        "confidence": 0.8,
                                        "source_boundary": "user_statement",
                                        "memory_write_allowed": True,
                                    }
                                ]
                            }
                        },
                    }
                ],
                "content": "",
                "used_tools": True,
            }
        if "brewers" in lower:
            return {
                "tool_calls": [{"name": "memory_recall", "arguments": {"query": "favorite sports team"}}],
                "content": "",
                "used_tools": True,
            }
        if "gpt logs" in lower:
            return {
                "tool_calls": [{"name": "gpt_log_search", "arguments": {"query": "CRT concepts", "top_k": 5}}],
                "content": "",
                "used_tools": True,
            }
        if "mill bluff" in lower:
            return {
                "tool_calls": [
                    {
                        "name": "project_context_search",
                        "arguments": {"query": prompt, "project": "wisconsin-state-parks-map"},
                    }
                ],
                "content": "",
                "used_tools": True,
            }
        return {"tool_calls": [], "content": "No tool needed.", "used_tools": False}


def test_governed_front_back_repairs_wrong_tool_and_unsafe_payload():
    report = run_governed_cases(client=UnsafeModelClient(), client_label="unsafe-fixture")

    assert report["summary"] == {"passed": 5, "total": 5}

    marigold = _result_by_id(report, "multi_fact_marigold_orange")
    assert marigold["intent_type"] == "mirus_extract_candidates"
    assert marigold["quality_flags"] == []
    assert "forced_review_only_candidate_payload" in marigold["repairs"]
    assert {candidate["slot"] for candidate in marigold["slots"]["payload"]["candidates"]} >= {
        "user:favorite_flower",
        "user:favorite_flower_reason",
    }
    assert all(
        candidate["memory_write_allowed"] is False
        for candidate in marigold["slots"]["payload"]["candidates"]
    )

    brewers = _result_by_id(report, "short_confirmation_from_pending_sports_team")
    assert brewers["intent_type"] == "mirus_extract_candidates"
    assert brewers["slots"]["payload"]["candidates"][0]["slot"] == "user:favorite_sports_team"
    assert brewers["quality_flags"] == []


def test_governed_logic_graph_shows_front_router_validator_repair_final():
    report = run_governed_cases(client=UnsafeModelClient(), client_label="unsafe-fixture")
    marigold = _result_by_id(report, "multi_fact_marigold_orange")

    graph = marigold["logic_graph"]
    node_ids = [node["id"] for node in graph["nodes"]]
    assert node_ids == ["input", "mirus_front", "holden_router", "crt_validator", "crt_repair", "final"]
    assert graph["nodes"][1]["data"]["preferred_intent"] == "mirus_extract_candidates"
    assert graph["nodes"][-1]["data"]["passed"] is True
