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


def test_scaffold_fragments_preserve_load_bearing_layers():
    scenario = next(
        scenario
        for scenario in scenario_pack(include_adversarial=True)
        if scenario.name == "model_generated_name_contamination"
    )
    scaffold = build_meaning_scaffold(scenario)
    rendered = render_scaffold(scaffold)

    assert "CURRENT name = Nick" in rendered
    assert "HISTORY name = Nick -> Mike" in rendered
    assert "CONTRADICTION name Nick -> Mike" in rendered
    assert "AUTHORITY name = confirmed" in rendered
    assert "REACTION name = answer_current_with_history" in rendered


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
