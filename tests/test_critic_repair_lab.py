from labs.critic_repair_lab.critic_repair_lab import cases, render, run_lab, score


def test_critic_repair_lab_has_abstract_risk_directed_cases():
    pack = cases()
    assert len(pack) >= 6
    prompts = " ".join(case.prompt.lower() for case in pack)
    assert "harm" in prompts
    assert "epistemic integrity" in prompts
    assert "score meaning" in prompts
    assert "stronger model" in prompts
    assert all(case.risk_focus for case in pack)


def test_critic_repair_improves_over_governed_draft_on_each_case():
    for case in cases():
        draft = render(case, "governed_draft")
        repaired = render(case, "governed_repair")
        draft_score = score(case, draft)
        repaired_score = score(case, repaired)

        assert repaired_score.total >= draft_score.total, case.case_id
        assert repaired_score.passed, case.case_id
        assert not repaired_score.forbidden_present, case.case_id


def test_raw_answers_are_not_sufficient_for_the_pack():
    raw_scores = [score(case, render(case, "raw")) for case in cases()]
    assert sum(result.passed for result in raw_scores) < len(raw_scores)
    assert any(result.forbidden_present or result.non_generic == 0.0 for result in raw_scores)


def test_critic_finds_missing_dimensions_before_repair():
    for case in cases():
        critic = render(case, "critic")
        assert critic.findings
        assert any(
            finding.status in {"missing", "weak", "overclaimed"}
            for finding in critic.findings
        ), case.case_id


def test_run_lab_preserves_safety_contract():
    result = run_lab()
    safety = result["safety_contract"]
    assert safety["raw_hidden_chain_of_thought_stored"] is False
    assert safety["memory_writes"] is False
    assert safety["support_reflection_writes"] is False
    assert safety["policy_mutation"] is False
    assert safety["critic_findings_review_only"] is True
    assert result["summary"]["governed_repair"]["passed"] == len(cases())

