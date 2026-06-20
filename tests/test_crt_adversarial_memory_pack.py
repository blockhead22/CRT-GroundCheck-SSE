from labs.meaning_compression_lab.baseline_eval import run as run_baseline
from labs.meaning_compression_lab.plain_rag_eval import run as run_plain_rag
from labs.meaning_compression_lab.run_lab import (
    ADVERSARIAL_SCENARIOS,
    HARDENING_SCENARIOS,
    canonical_meaning_state,
    run as run_meaning_lab,
    scenario_pack,
)


def _scenario(out, name):
    return next(row for row in out["scenarios"] if row["name"] == name)


def _representation(scenario, name):
    return next(row for row in scenario["representations"] if row["name"] == name)


def _plain_scenario(out, name):
    return next(row for row in out["scenarios"] if row["scenario"] == name)


def test_adversarial_pack_adds_harder_memory_histories():
    scenarios = scenario_pack(include_adversarial=True)

    assert len(ADVERSARIAL_SCENARIOS) == 10
    assert len(scenarios) == 15

    names = {scenario.name for scenario in scenarios}
    assert {
        "favorite_color_social_then_confirmed",
        "answer_style_revision",
        "project_revert",
        "location_correction",
        "destructive_command_policy",
        "employer_history_question",
        "name_contradiction_status",
        "multi_fact_update",
        "model_generated_name_contamination",
        "tool_inferred_location_noise",
    }.issubset(names)


def test_hardening_pack_adds_layer_specific_ablation_probes():
    scenarios = scenario_pack(include_adversarial=True, include_hardening=True)

    assert len(HARDENING_SCENARIOS) == 4
    assert len(scenarios) == 19

    names = {scenario.name for scenario in scenarios}
    assert {
        "camera_history_inventory",
        "store_platform_authority_boundary",
        "favorite_color_reaction_rule",
        "production_db_mock_policy",
    }.issubset(names)


def test_adversarial_pack_preserves_current_value_and_history():
    by_name = {scenario.name: scenario for scenario in ADVERSARIAL_SCENARIOS}

    color = canonical_meaning_state(by_name["favorite_color_social_then_confirmed"].memories)
    assert color["facts"]["favorite_color"] == "green"
    assert color["history"]["favorite_color"] == ["blue", "green"]
    assert color["authority"]["favorite_color"] == "confirmed"
    assert color["reaction_policy"]["favorite_color"] == "answer_current_with_history"

    project = canonical_meaning_state(by_name["project_revert"].memories)
    assert project["facts"]["current_project"] == "Atlas"
    assert project["history"]["current_project"] == ["Atlas", "Borealis"]
    assert project["contradictions"] == [
        {"slot": "current_project", "old": "Atlas", "new": "Borealis", "status": "preserved"},
        {"slot": "current_project", "old": "Borealis", "new": "Atlas", "status": "preserved"},
    ]
    assert project["bit_flags"]["flipped:current_project"] is True

    contamination = canonical_meaning_state(by_name["model_generated_name_contamination"].memories)
    assert contamination["facts"]["name"] == "Nick"
    assert contamination["authority"]["name"] == "confirmed"
    assert contamination["history"]["name"] == ["Nick"]
    assert contamination["provisional"]["name"] == ["Mike"]
    assert contamination["reaction_policy"]["name"] == "answer_direct"

    tool_noise = canonical_meaning_state(by_name["tool_inferred_location_noise"].memories)
    assert tool_noise["facts"]["home_city"] == "Chicago"
    assert tool_noise["authority"]["home_city"] == "confirmed"
    assert tool_noise["history"]["home_city"] == ["Chicago"]
    assert tool_noise["provisional"]["home_city"] == ["Los Angeles"]


def test_hardening_pack_preserves_expected_meaning_layers():
    by_name = {scenario.name: scenario for scenario in HARDENING_SCENARIOS}

    camera = canonical_meaning_state(by_name["camera_history_inventory"].memories)
    assert camera["facts"]["camera_system"] == "Sony FX3"
    assert camera["history"]["camera_system"] == ["Canon 80D", "Sony FX3"]
    assert camera["reaction_policy"]["camera_system"] == "answer_current_with_history"

    store = canonical_meaning_state(by_name["store_platform_authority_boundary"].memories)
    assert store["facts"]["store_platform"] == "custom e-commerce backend"
    assert store["authority"]["store_platform"] == "confirmed"
    assert store["history"]["store_platform"] == ["custom e-commerce backend"]
    assert store["provisional"]["store_platform"] == ["Shopify"]

    reaction = canonical_meaning_state(by_name["favorite_color_reaction_rule"].memories)
    assert reaction["authority"]["favorite_color"] == "provisional_social"
    assert reaction["reaction_policy"]["favorite_color"] == "withhold_until_confirmed"

    policy = canonical_meaning_state(by_name["production_db_mock_policy"].memories)
    assert policy["policies"]["db.production_write_without_sqlite_mock"] == "forbidden"
    assert policy["reaction_policy"]["db.production_write_without_sqlite_mock"] == "refuse_action"


def test_meaning_lab_crt_passes_adversarial_pack():
    out = run_meaning_lab(write_results=False, scenarios=scenario_pack(include_adversarial=True))
    rows = {row["name"]: row for row in out["aggregate_representations"]}

    assert out["scenario_count"] == 15
    assert out["evidence_counts"] == {"fixture": 15}
    assert rows["crt_compressed"]["avg_structural_score"] == 1.0
    assert rows["crt_compressed"]["avg_behavior_score"] == 1.0

    color = _scenario(out, "favorite_color_social_then_confirmed")
    crt = _representation(color, "crt_compressed")
    slot_only = _representation(color, "slot_only")
    assert crt["structural_score"] == 1.0
    assert "history:favorite_color" in slot_only["failed_invariants"]
    assert "contradiction:favorite_color" in slot_only["failed_invariants"]


def test_adversarial_pack_keeps_crt_ahead_of_baselines():
    out = run_baseline(write_results=False, scenarios=scenario_pack(include_adversarial=True))
    rows = {row["baseline"]: row for row in out["aggregate"]}

    assert out["scenario_count"] == 15
    assert rows["crt_governed"]["pass_count"] == 15
    assert rows["crt_governed"]["avg_score"] == 1.0
    assert rows["plain_retrieval"]["pass_count"] < rows["crt_governed"]["pass_count"]
    assert rows["latest_only_slots"]["pass_count"] < rows["crt_governed"]["pass_count"]


def test_plain_rag_adversarial_pack_exposes_raw_text_failure_modes():
    out = run_plain_rag(
        mode="simulated",
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True),
    )

    assert out["aggregate"]["case_count"] == 15
    assert out["aggregate"]["crt_pass_count"] == 15
    assert out["aggregate"]["plain_rag_pass_count"] < out["aggregate"]["crt_pass_count"]
    assert out["aggregate"]["plain_rag_pass_count"] <= 5

    color = _plain_scenario(out, "favorite_color_social_then_confirmed")
    project = _plain_scenario(out, "project_revert")
    destructive = _plain_scenario(out, "destructive_command_policy")
    contamination = _plain_scenario(out, "model_generated_name_contamination")
    tool_noise = _plain_scenario(out, "tool_inferred_location_noise")

    assert color["crt_judgment"]["passed"] is True
    assert color["plain_rag_judgment"]["passed"] is False
    assert "blue" in color["plain_rag_answer"].lower()

    assert project["crt_judgment"]["passed"] is True
    assert project["plain_rag_judgment"]["passed"] is False
    assert "borealis" in project["plain_rag_answer"].lower()

    assert destructive["crt_judgment"]["passed"] is True
    assert destructive["plain_rag_judgment"]["passed"] is False
    assert "destructive shell commands" in destructive["plain_rag_answer"].lower()

    assert contamination["crt_judgment"]["passed"] is True
    assert contamination["plain_rag_judgment"]["passed"] is False
    assert "mike" in contamination["plain_rag_answer"].lower()

    assert tool_noise["crt_judgment"]["passed"] is True
    assert tool_noise["plain_rag_judgment"]["passed"] is False
    assert "los angeles" in tool_noise["plain_rag_answer"].lower()
