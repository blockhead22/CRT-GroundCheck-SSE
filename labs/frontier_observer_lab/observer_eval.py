"""Frozen, no-write evaluation helpers for the frontier shadow observer."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from .frontier_observer_lab import ObserverGrade, QUALITY_DIMENSIONS


@dataclass(frozen=True)
class ObserverEvalCase:
    case_id: str
    user_prompt: str
    accepted_answer: str
    public_trace: dict[str, Any]
    expected_verdict: str
    expected_findings: frozenset[str]
    forbidden_findings: frozenset[str]
    note: str


@dataclass(frozen=True)
class ObserverEvalResult:
    case_count: int
    verdict_accuracy: float
    finding_precision: float
    finding_recall: float
    clean_case_false_positive_rate: float
    unsupported_dimension_rate: float
    passed_gate: bool


def load_frozen_cases(path: str | Path) -> tuple[ObserverEvalCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("observer fixture must contain a cases list")

    cases: list[ObserverEvalCase] = []
    seen: set[str] = set()
    for raw in payload["cases"]:
        if not isinstance(raw, dict):
            raise ValueError("each observer fixture case must be an object")
        case_id = str(raw.get("case_id") or "").strip()
        if not case_id or case_id in seen:
            raise ValueError("case_id must be present and unique")
        seen.add(case_id)

        expected_verdict = str(raw.get("expected_verdict") or "")
        if expected_verdict not in {"pass", "review"}:
            raise ValueError(f"invalid expected verdict for {case_id}")
        expected = frozenset(str(item) for item in raw.get("expected_findings", []))
        forbidden = frozenset(str(item) for item in raw.get("forbidden_findings", []))
        if not expected.issubset(QUALITY_DIMENSIONS):
            raise ValueError(f"unknown expected dimension for {case_id}")
        if not forbidden.issubset(QUALITY_DIMENSIONS):
            raise ValueError(f"unknown forbidden dimension for {case_id}")
        if expected & forbidden:
            raise ValueError(f"dimension both expected and forbidden for {case_id}")

        cases.append(
            ObserverEvalCase(
                case_id=case_id,
                user_prompt=str(raw.get("user_prompt") or ""),
                accepted_answer=str(raw.get("accepted_answer") or ""),
                public_trace=dict(raw.get("public_trace") or {}),
                expected_verdict=expected_verdict,
                expected_findings=expected,
                forbidden_findings=forbidden,
                note=str(raw.get("note") or ""),
            )
        )
    return tuple(cases)


def score_observer_grades(
    cases: Iterable[ObserverEvalCase],
    grades: dict[str, ObserverGrade],
) -> ObserverEvalResult:
    frozen = tuple(cases)
    if not frozen:
        raise ValueError("at least one observer case is required")
    missing = {case.case_id for case in frozen} - set(grades)
    if missing:
        raise ValueError(f"missing grades for: {', '.join(sorted(missing))}")

    verdict_hits = 0
    true_positive = 0
    false_positive = 0
    false_negative = 0
    clean_cases = 0
    clean_case_false_positives = 0
    unsupported = 0
    total_reported = 0

    for case in frozen:
        grade = grades[case.case_id]
        if grade.verdict == case.expected_verdict:
            verdict_hits += 1
        reported = {finding.dimension for finding in grade.findings}
        total_reported += len(reported)
        unsupported += len(reported & case.forbidden_findings)

        true_positive += len(reported & case.expected_findings)
        false_positive += len(reported - case.expected_findings)
        false_negative += len(case.expected_findings - reported)

        if not case.expected_findings:
            clean_cases += 1
            if reported or grade.verdict != "pass":
                clean_case_false_positives += 1

    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 1.0
    recall = true_positive / recall_denominator if recall_denominator else 1.0
    clean_fpr = clean_case_false_positives / clean_cases if clean_cases else 0.0
    unsupported_rate = unsupported / total_reported if total_reported else 0.0
    verdict_accuracy = verdict_hits / len(frozen)

    return ObserverEvalResult(
        case_count=len(frozen),
        verdict_accuracy=verdict_accuracy,
        finding_precision=precision,
        finding_recall=recall,
        clean_case_false_positive_rate=clean_fpr,
        unsupported_dimension_rate=unsupported_rate,
        passed_gate=(
            verdict_accuracy >= 0.85
            and precision >= 0.75
            and recall >= 0.75
            and clean_fpr <= 0.25
            and unsupported_rate == 0.0
        ),
    )

