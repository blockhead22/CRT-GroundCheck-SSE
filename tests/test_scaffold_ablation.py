from labs.meaning_compression_lab.scaffold_ablation import (
    ABLATIONS,
    ablate_scaffold,
    run,
    summarize_ablation,
)
from labs.meaning_compression_lab.scaffold_eval import build_meaning_scaffold
from labs.meaning_compression_lab.run_lab import scenario_pack


def _ablation(out, name):
    return next(row for row in out["ablation_results"] if row["ablation"] == name)


def _failed_names(row):
    return {item["scenario"] for item in row["failed_scenarios"]}


def test_ablate_scaffold_removes_requested_fragment_kinds():
    scenario = next(s for s in scenario_pack(include_adversarial=True) if s.name == "identity_flip")
    full = build_meaning_scaffold(scenario)
    ablated = ablate_scaffold(full, next(a for a in ABLATIONS if a.name == "no_contradictions"))

    assert any(fragment["kind"] == "contradiction" for fragment in full["fragments"])
    assert not any(fragment["kind"] == "contradiction" for fragment in ablated["fragments"])


def test_deterministic_ablation_identifies_load_bearing_layers():
    out = run(write_results=False)

    full = _ablation(out, "full")
    no_current = _ablation(out, "no_current_facts")
    no_history = _ablation(out, "no_history")
    no_contradictions = _ablation(out, "no_contradictions")
    no_authority = _ablation(out, "no_authority")
    no_policies = _ablation(out, "no_policies")
    no_reaction = _ablation(out, "no_reaction")
    no_preferences = _ablation(out, "no_preferences")

    assert full["pass_count"] == 19
    assert no_current["pass_count"] < full["pass_count"]
    assert no_history["pass_count"] < full["pass_count"]
    assert no_contradictions["pass_count"] < full["pass_count"]
    assert no_authority["pass_count"] < full["pass_count"]
    assert no_policies["pass_count"] < full["pass_count"]
    assert no_reaction["pass_count"] < full["pass_count"]
    assert no_preferences["pass_count"] < full["pass_count"]

    assert "identity_flip" in _failed_names(no_current)
    assert "camera_history_inventory" in _failed_names(no_history)
    assert "name_contradiction_status" in _failed_names(no_contradictions)
    assert "store_platform_authority_boundary" in _failed_names(no_authority)
    assert "policy_constraint" in _failed_names(no_policies)
    assert "favorite_color_reaction_rule" in _failed_names(no_reaction)
    assert "concern_preference" in _failed_names(no_preferences)


def test_deterministic_ablation_surfaces_non_load_bearing_prompt_layers():
    out = run(write_results=False)
    full = _ablation(out, "full")

    assert _ablation(out, "no_query_contract")["pass_count"] == full["pass_count"]
    assert _ablation(out, "no_policy_plaintext")["pass_count"] == full["pass_count"]


def test_summarize_ablation_tracks_failed_scenarios():
    ablation = next(a for a in ABLATIONS if a.name == "full")
    rows = [
        {
            "scenario": "ok",
            "probe": "probe",
            "answer": "yes",
            "passed": True,
            "judgment": {"expected_contains": [], "expected_excludes": []},
            "scaffold_compression_ratio": 0.5,
        },
        {
            "scenario": "bad",
            "probe": "probe",
            "answer": "no",
            "passed": False,
            "judgment": {"expected_contains": ["yes"], "expected_excludes": []},
            "scaffold_compression_ratio": 0.3,
        },
    ]

    summary = summarize_ablation(ablation, rows)

    assert summary["pass_count"] == 1
    assert summary["fail_count"] == 1
    assert summary["avg_scaffold_compression_ratio"] == 0.4
    assert summary["failed_scenarios"][0]["scenario"] == "bad"
