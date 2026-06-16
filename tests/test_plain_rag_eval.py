from labs.meaning_compression_lab.plain_rag_eval import run


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
