from labs.meaning_compression_lab.baseline_eval import run


def _aggregate(out):
    return {row["baseline"]: row for row in out["aggregate"]}


def _scenario(out, name):
    return next(row for row in out["scenarios"] if row["name"] == name)


def _baselines(scenario):
    return {row["baseline"]: row for row in scenario["baselines"]}


def test_crt_governed_beats_simpler_baselines_on_current_scenarios():
    out = run(write_results=False)
    rows = _aggregate(out)

    assert out["scenario_count"] == 5
    assert rows["crt_governed"]["pass_count"] == 5
    assert rows["crt_governed"]["avg_score"] == 1.0
    assert rows["crt_governed"]["avg_score"] > rows["latest_only_slots"]["avg_score"]
    assert rows["crt_governed"]["avg_score"] > rows["plain_retrieval"]["avg_score"]
    assert rows["crt_governed"]["avg_score"] > rows["summary_only"]["avg_score"]


def test_latest_only_loses_contradiction_history():
    out = run(write_results=False)
    identity = _baselines(_scenario(out, "identity_flip"))
    employer = _baselines(_scenario(out, "employer_correction"))

    assert identity["latest_only_slots"]["verdict"] != "pass"
    assert "history:name" in identity["latest_only_slots"]["failed_invariants"]
    assert "contradiction:name" in identity["latest_only_slots"]["failed_invariants"]
    assert employer["latest_only_slots"]["verdict"] != "pass"
    assert "history:employer" in employer["latest_only_slots"]["failed_invariants"]
    assert "contradiction:employer" in employer["latest_only_slots"]["failed_invariants"]


def test_plain_retrieval_loses_authority_and_policy_governance():
    out = run(write_results=False)
    authority = _baselines(_scenario(out, "authority_boundary"))
    policy = _baselines(_scenario(out, "policy_constraint"))

    assert authority["plain_retrieval"]["verdict"] == "fail"
    assert "authority:favorite_color" in authority["plain_retrieval"]["failed_invariants"]
    assert "reaction:favorite_color" in authority["plain_retrieval"]["failed_invariants"]
    assert policy["plain_retrieval"]["verdict"] == "fail"
    assert "policy:git.force_push_main" in policy["plain_retrieval"]["failed_invariants"]
    assert "reaction:git.force_push_main" in policy["plain_retrieval"]["failed_invariants"]


def test_summary_only_is_not_meaning_preserving():
    out = run(write_results=False)
    rows = _aggregate(out)

    assert rows["summary_only"]["pass_count"] == 0
    assert rows["summary_only"]["avg_score"] < 0.1
