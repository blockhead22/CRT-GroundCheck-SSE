from labs.meaning_compression_lab.scaffold_eval import (
    build_meaning_scaffold,
    render_scaffold,
    run,
)
from labs.meaning_compression_lab.run_lab import scenario_pack


def _scenario(out, name):
    return next(row for row in out["scenarios"] if row["scenario"] == name)


def test_scaffold_eval_passes_default_pack_and_beats_raw():
    out = run(write_results=False)
    agg = out["aggregate"]

    assert agg["case_count"] == 5
    assert agg["scaffold_pass_count"] == 5
    assert agg["crt_pass_count"] == 5
    assert agg["raw_pass_count"] < agg["scaffold_pass_count"]
    assert agg["avg_scaffold_compression_ratio"] < 1.0


def test_scaffold_eval_passes_adversarial_pack():
    out = run(write_results=False, scenarios=scenario_pack(include_adversarial=True))
    agg = out["aggregate"]

    assert agg["case_count"] == 15
    assert agg["scaffold_pass_count"] == 15
    assert agg["crt_pass_count"] == 15
    assert agg["raw_pass_count"] < agg["scaffold_pass_count"]
    assert agg["raw_pass_count"] <= 5


def test_scaffold_eval_passes_hardening_pack():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )
    agg = out["aggregate"]

    assert agg["case_count"] == 19
    assert agg["scaffold_pass_count"] == 19
    assert agg["crt_pass_count"] == 19
    assert agg["raw_pass_count"] < agg["scaffold_pass_count"]

    camera = _scenario(out, "camera_history_inventory")
    store = _scenario(out, "store_platform_authority_boundary")
    reaction = _scenario(out, "favorite_color_reaction_rule")
    policy = _scenario(out, "production_db_mock_policy")

    assert camera["scaffold_answer"] == "Canon 80D"
    assert store["scaffold_judgment"]["passed"] is True
    assert reaction["scaffold_judgment"]["passed"] is True
    assert policy["scaffold_judgment"]["passed"] is True


def test_scaffold_fragments_preserve_load_bearing_layers():
    scenario = next(
        scenario
        for scenario in scenario_pack(include_adversarial=True)
        if scenario.name == "model_generated_name_contamination"
    )
    scaffold = build_meaning_scaffold(scenario)
    rendered = render_scaffold(scaffold)

    assert "CURRENT name = Nick" in rendered
    assert "PROVISIONAL name = Mike" in rendered
    assert "HISTORY name" not in rendered
    assert "CONTRADICTION name" not in rendered
    assert "AUTHORITY name = confirmed" in rendered
    assert "REACTION name = answer_direct" in rendered


def test_provisional_observation_does_not_enter_authoritative_history():
    scenario = next(
        scenario
        for scenario in scenario_pack(include_hardening=True)
        if scenario.name == "store_platform_authority_boundary"
    )
    rendered = render_scaffold(build_meaning_scaffold(scenario))

    assert "CURRENT store_platform = custom e-commerce backend" in rendered
    assert "AUTHORITY store_platform = confirmed" in rendered
    assert "PROVISIONAL store_platform = Shopify" in rendered
    assert "HISTORY store_platform" not in rendered
    assert "CONTRADICTION store_platform" not in rendered


def test_scaffold_beats_raw_on_contamination_and_tool_noise():
    out = run(write_results=False, scenarios=scenario_pack(include_adversarial=True))

    name = _scenario(out, "model_generated_name_contamination")
    location = _scenario(out, "tool_inferred_location_noise")

    assert name["raw_judgment"]["passed"] is False
    assert name["scaffold_judgment"]["passed"] is True
    assert "mike" in name["raw_answer"].lower()
    assert name["scaffold_answer"] == "Nick"

    assert location["raw_judgment"]["passed"] is False
    assert location["scaffold_judgment"]["passed"] is True
    assert "los angeles" in location["raw_answer"].lower()
    assert location["scaffold_answer"] == "Chicago"


def test_scaffold_result_includes_auditable_decision_traces():
    out = run(
        write_results=False,
        scenarios=scenario_pack(include_hardening=True),
    )
    store = _scenario(out, "store_platform_authority_boundary")
    trace = store["decision_traces"]["hybrid_crt"]

    assert trace["selected_rule"] == "scaffold:confirmed_store_platform"
    assert trace["state_transformation"]["facts"]["store_platform"] == "custom e-commerce backend"
    assert trace["state_transformation"]["provisional"]["store_platform"] == ["Shopify"]
    assert trace["severity"] == "pass"
