from __future__ import annotations

from pathlib import Path

import pytest

from labs.frontier_observer_lab.frontier_observer_lab import (
    ObserverFinding,
    ObserverGrade,
)
from labs.frontier_observer_lab.observer_eval import (
    load_frozen_cases,
    score_observer_grades,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "labs"
    / "frontier_observer_lab"
    / "fixtures"
    / "observer_quality_pack_v0.json"
)


def _grade(case, *, findings=None, verdict=None):
    dimensions = tuple(findings if findings is not None else case.expected_findings)
    return ObserverGrade(
        verdict=verdict or case.expected_verdict,
        scores={},
        summary="Frozen evaluator test grade.",
        findings=tuple(
            ObserverFinding(
                dimension=dimension,
                severity="medium",
                answer_excerpt="bounded excerpt",
                reason="human-labeled regression",
            )
            for dimension in dimensions
        ),
        suggestions=(),
    )


def test_frozen_pack_covers_clean_and_recurring_regression_classes():
    cases = load_frozen_cases(FIXTURE)
    assert len(cases) == 8
    ids = {case.case_id for case in cases}
    assert {
        "good_general_answer",
        "canned_governance_pamphlet",
        "unrelated_personal_memory_leak",
        "speaker_ownership_inversion",
        "fabricated_capability",
        "broken_followup_continuity",
        "source_status_blur",
        "good_governed_personal_recall",
    } == ids
    assert sum(case.expected_verdict == "pass" for case in cases) == 2


def test_perfect_observer_grades_pass_the_eval_gate():
    cases = load_frozen_cases(FIXTURE)
    result = score_observer_grades(
        cases,
        {case.case_id: _grade(case) for case in cases},
    )
    assert result.verdict_accuracy == 1.0
    assert result.finding_precision == 1.0
    assert result.finding_recall == 1.0
    assert result.clean_case_false_positive_rate == 0.0
    assert result.unsupported_dimension_rate == 0.0
    assert result.passed_gate is True


def test_eloquent_but_noisy_observer_fails_the_eval_gate():
    cases = load_frozen_cases(FIXTURE)
    grades = {
        case.case_id: _grade(
            case,
            findings=("non_canned_synthesis",),
            verdict="review",
        )
        for case in cases
    }
    result = score_observer_grades(cases, grades)
    assert result.verdict_accuracy < 0.85
    assert result.finding_recall < 0.75
    assert result.clean_case_false_positive_rate == 1.0
    assert result.passed_gate is False


def test_missing_grade_is_rejected_instead_of_silently_scored():
    cases = load_frozen_cases(FIXTURE)
    with pytest.raises(ValueError, match="missing grades"):
        score_observer_grades(cases, {})

