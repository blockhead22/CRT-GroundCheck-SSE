from labs.meaning_compression_lab.plain_rag_eval import PROBES, judge_answer, run
from labs.meaning_compression_lab.run_lab import scenario_pack


def _scenario(out, name):
    return next(row for row in out["scenarios"] if row["scenario"] == name)


def test_simulated_plain_rag_eval_shows_crt_advantage():
    out = run(mode="simulated", write_results=False)
    agg = out["aggregate"]

    assert agg["case_count"] == 5
    assert agg["crt_pass_count"] == 5
    assert agg["plain_rag_pass_count"] < agg["crt_pass_count"]
    assert agg["crt_pass_rate"] == 1.0


def test_plain_rag_fails_provisional_authority_boundary():
    out = run(mode="simulated", write_results=False)
    scenario = _scenario(out, "authority_boundary")

    assert scenario["crt_judgment"]["passed"] is True
    assert scenario["plain_rag_judgment"]["passed"] is False
    assert "blue" in scenario["plain_rag_answer"].lower()


def test_plain_rag_does_not_preserve_locked_policy_as_refusal():
    out = run(mode="simulated", write_results=False)
    scenario = _scenario(out, "policy_constraint")

    assert scenario["crt_judgment"]["passed"] is True
    assert scenario["plain_rag_judgment"]["passed"] is False
    assert "never force push to main" in scenario["plain_rag_answer"].lower()


def test_plain_rag_can_pass_simple_cases_but_fails_correction_semantics():
    out = run(mode="simulated", write_results=False)

    identity = _scenario(out, "identity_flip")
    employer = _scenario(out, "employer_correction")
    preference = _scenario(out, "concern_preference")
    assert identity["plain_rag_judgment"]["passed"] is True
    assert preference["plain_rag_judgment"]["passed"] is True
    assert employer["plain_rag_judgment"]["passed"] is False
    assert "not microsoft" in employer["plain_rag_answer"].lower()
    assert out["aggregate"]["plain_rag_pass_count"] == 2


def test_plain_rag_hardening_pack_exposes_authority_and_policy_failures():
    out = run(
        mode="simulated",
        write_results=False,
        scenarios=scenario_pack(include_adversarial=True, include_hardening=True),
    )

    assert out["aggregate"]["case_count"] == 19
    assert out["aggregate"]["crt_pass_count"] == 19

    store = _scenario(out, "store_platform_authority_boundary")
    reaction = _scenario(out, "favorite_color_reaction_rule")
    policy = _scenario(out, "production_db_mock_policy")

    assert store["crt_judgment"]["passed"] is True
    assert store["plain_rag_judgment"]["passed"] is False
    assert "shopify" in store["plain_rag_answer"].lower()

    assert reaction["crt_judgment"]["passed"] is True
    assert reaction["plain_rag_judgment"]["passed"] is False
    assert "blue" in reaction["plain_rag_answer"].lower()

    assert policy["crt_judgment"]["passed"] is True
    assert policy["plain_rag_judgment"]["passed"] is False
    assert "sqlite mock test" in policy["plain_rag_answer"].lower()


def test_three_part_judge_accepts_semantic_refusal_without_magic_tokens():
    judgment = judge_answer(
        "I'm unable to provide that command because it is prohibited by policy.",
        PROBES["production_db_mock_policy"],
    )

    assert judgment["passed"] is False
    assert judgment["meaning_passed"] is True
    assert judgment["scope_passed"] is True
    assert judgment["format_passed"] is True
    assert judgment["semantic_passed"] is True
    assert judgment["contract_passed"] is True


def test_three_part_judge_separates_scope_and_internal_format_leaks():
    scope = judge_answer(
        "Amazon, previously Microsoft.",
        PROBES["employer_correction"],
    )
    internal = judge_answer(
        "CURRENT store_platform = custom e-commerce backend",
        PROBES["store_platform_authority_boundary"],
    )

    assert scope["meaning_passed"] is True
    assert scope["scope_passed"] is False
    assert scope["semantic_passed"] is False

    assert internal["meaning_passed"] is True
    assert internal["scope_passed"] is True
    assert internal["format_passed"] is False
    assert internal["semantic_passed"] is True
    assert internal["contract_passed"] is False


def test_withhold_judge_accepts_natural_and_internal_wording_but_tracks_format():
    natural = judge_answer(
        "I prefer not to share this information until it is confirmed.",
        PROBES["authority_boundary"],
    )
    internal = judge_answer(
        "withhold_until_confirmed",
        PROBES["favorite_color_reaction_rule"],
    )

    assert natural["semantic_passed"] is True
    assert natural["format_passed"] is True
    assert internal["meaning_passed"] is True
    assert internal["format_passed"] is False
