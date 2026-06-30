"""Map local-router RAG-suite results into Workbench review metadata.

This adapter is deliberately review-only. It makes replay/RAG evidence easier
to inspect in Workbench without treating lab results as user memory, learned
policy, or proof that the governed route is finished.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SERIOUS_BASELINE = "scaffolded_rag"


def load_rag_suite_result_for_workbench_review(path: Path) -> dict[str, Any]:
    """Load a RAG-suite artifact and adapt it into Workbench review shape."""
    result_path = Path(path)
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    return adapt_rag_suite_result_for_workbench_review(result, result_path=result_path)


def load_rag_suite_result_for_workbench_preview(path: Path) -> dict[str, Any]:
    """Load a RAG-suite artifact and adapt it into Workbench learner preview."""
    review = load_rag_suite_result_for_workbench_review(path)
    return adapt_rag_evidence_review_for_consolidation_preview(review)


def adapt_rag_suite_result_for_workbench_review(
    result: dict[str, Any],
    *,
    result_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return compact, safe Workbench review metadata for a RAG-suite run."""
    case_count = int(result.get("case_count") or 0)
    aggregate = result.get("aggregate") or {}
    modes = list(result.get("modes") or [])
    baselines = {
        mode: _mode_summary(aggregate.get(mode) or {}, case_count)
        for mode in modes
        if mode in aggregate
    }
    governed = baselines.get("governed", _mode_summary({}, case_count))
    scaffolded = baselines.get(SERIOUS_BASELINE, _mode_summary({}, case_count))
    trace_complete = case_count > 0 and governed.get("trace_pass_count") == case_count
    pass_delta = int(governed.get("answer_pass_count") or 0) - int(scaffolded.get("answer_pass_count") or 0)
    avg_delta = _round_or_none(_as_float(governed.get("answer_avg_score")) - _as_float(scaffolded.get("answer_avg_score")))

    return {
        "kind": "local_router_rag_evidence_review",
        "source": "local_router_rag_suite",
        "pack": result.get("pack"),
        "pack_path": result.get("pack_path"),
        "result_path": str(result_path or result.get("result_path") or ""),
        "case_count": case_count,
        "case_ids": list(result.get("case_ids") or []),
        "retrieval": _retrieval_summary(result),
        "baseline_to_beat": SERIOUS_BASELINE,
        "baselines": baselines,
        "governed_delta_vs_scaffolded_rag": {
            "answer_pass_delta": pass_delta,
            "answer_avg_score_delta": avg_delta,
            "trace_complete": trace_complete,
        },
        "review_flags": _review_flags(
            case_count=case_count,
            baselines=baselines,
            pass_delta=pass_delta,
            trace_complete=trace_complete,
        ),
        "failure_summary": _failure_summary(baselines),
        "safety_contract": {
            "promotion_status": "review_only",
            "memory_writes_allowed": False,
            "raw_chain_of_thought_stored": False,
            "silent_policy_mutation_allowed": False,
            "review_required_before_promotion": True,
        },
        "next_review": _next_review(case_count=case_count, baselines=baselines, pass_delta=pass_delta),
    }


def adapt_rag_evidence_review_for_consolidation_preview(review: dict[str, Any]) -> dict[str, Any]:
    """Wrap RAG evidence review metadata as a preview-only learner candidate."""
    governed = (review.get("baselines") or {}).get("governed") or {}
    scaffolded = (review.get("baselines") or {}).get(SERIOUS_BASELINE) or {}
    delta = review.get("governed_delta_vs_scaffolded_rag") or {}
    case_count = int(review.get("case_count") or 0)
    pack = str(review.get("pack") or "unknown_pack")
    result_path = str(review.get("result_path") or "")
    governed_pass = int(governed.get("answer_pass_count") or 0)
    scaffolded_pass = int(scaffolded.get("answer_pass_count") or 0)
    trace_pass = int(governed.get("trace_pass_count") or 0)
    score_delta = _round_or_none(delta.get("answer_avg_score_delta"))
    return {
        "mode": "preview_only",
        "writes_performed": False,
        "memory_ingestion_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "inspected_turn_count": case_count,
        "candidates": [
            {
                "candidate_id": f"local_router_rag_evidence_{_slug(pack)}",
                "candidate_type": "background_consolidation_candidate",
                "category": "local_router_rag_evidence",
                "candidate_kind": "baseline_evidence_review",
                "summary": (
                    f"{_title_pack(pack)}: governed passed {governed_pass}/{case_count} "
                    f"with trace {trace_pass}/{case_count}; scaffolded RAG passed {scaffolded_pass}/{case_count}."
                ),
                "proposed_action": "Review as evidence for governed cognition, but do not tune against this pack again.",
                "risk": (
                    "Small or tuned packs and perfect governed scores require caution; "
                    "this is evidence for review, not a product or grant claim by itself."
                ),
                "review_required": True,
                "memory_write_allowed": False,
                "confirmed_fact": False,
                "review_route": {
                    "surface": "reflections",
                    "action": "review_rag_evidence",
                    "endpoint": "/v1/reflections",
                    "requires_adapter": True,
                    "draft": {
                        "subject": "agent",
                        "observation": (
                            f"In {pack}, governed Aether passed {governed_pass}/{case_count} "
                            f"with trace {trace_pass}/{case_count} while scaffolded RAG passed "
                            f"{scaffolded_pass}/{case_count}."
                        ),
                        "interpretation": (
                            "Governance appears to add reviewable value over scaffolded RAG on this pack, "
                            "but the result should remain bounded by pack size, evaluator fit, and holdout quality."
                        ),
                        "alternatives": [
                            "The result may partially reflect pack design or evaluator fit.",
                            "A larger blind/adversarial mix may reveal additional governed failure modes.",
                        ],
                        "confidence": _preview_confidence(review),
                        "time_window": f"local-router RAG {pack}",
                        "suggested_experiment": str(review.get("next_review") or ""),
                    },
                },
                "evidence": [
                    {
                        "evidence_type": "rag_suite_result",
                        "reference_id": result_path,
                        "summary": (
                            f"governed {governed_pass}/{case_count} trace {trace_pass}/{case_count} "
                            f"vs scaffolded_rag {scaffolded_pass}/{case_count}; "
                            f"delta {_format_pass_delta(delta.get('answer_pass_delta'))}, "
                            f"{_format_score_delta(score_delta)} avg"
                        ),
                    },
                    {
                        "evidence_type": "safety_contract",
                        "reference_id": "local_router_rag_evidence_review",
                        "summary": (
                            "review_only; memory writes blocked; raw hidden CoT not stored; "
                            "silent policy mutation blocked"
                        ),
                    },
                ],
            }
        ],
    }


def _mode_summary(mode: dict[str, Any], case_count: int) -> dict[str, Any]:
    answer_pass_count = int(mode.get("answer_pass_count") or 0)
    trace_pass_count = int(mode.get("trace_pass_count") or 0)
    return {
        "answer_pass_count": answer_pass_count,
        "answer_pass_rate": _rate(answer_pass_count, case_count),
        "answer_avg_score": _round_or_none(mode.get("answer_avg_score")),
        "trace_pass_count": trace_pass_count,
        "trace_pass_rate": _rate(trace_pass_count, case_count),
        "trace_avg_score": _round_or_none(mode.get("trace_avg_score")),
        "repair_count": int(mode.get("repair_count") or 0),
        "fallback_count": int(mode.get("fallback_count") or 0),
        "failure_count": int(mode.get("failure_count") or 0),
        "failures_by_task_type": dict(mode.get("failures_by_task_type") or {}),
    }


def _retrieval_summary(result: dict[str, Any]) -> dict[str, Any]:
    aggregate = result.get("aggregate") or {}
    retrieval = result.get("retrieval") or {}
    coverage = aggregate.get("retrieval") or {}
    return {
        "k": retrieval.get("k"),
        "method": retrieval.get("method"),
        "corpus_chunk_count": retrieval.get("corpus_chunk_count"),
        "corpus_kinds": dict(retrieval.get("corpus_kinds") or {}),
        "avg_receipt_coverage": _round_or_none(coverage.get("avg_receipt_coverage")),
        "avg_concept_coverage": _round_or_none(coverage.get("avg_concept_coverage")),
    }


def _review_flags(
    *,
    case_count: int,
    baselines: dict[str, dict[str, Any]],
    pass_delta: int,
    trace_complete: bool,
) -> list[str]:
    flags = ["review_only_evidence"]
    governed = baselines.get("governed")
    scaffolded = baselines.get(SERIOUS_BASELINE)
    plain = baselines.get("plain_rag")
    if scaffolded:
        flags.append("scaffolded_rag_is_serious_baseline")
        if int(scaffolded.get("failure_count") or 0) > 0:
            flags.append("scaffolded_rag_failures_present")
    if plain and scaffolded and _as_float(plain.get("answer_avg_score")) < _as_float(scaffolded.get("answer_avg_score")):
        flags.append("plain_rag_not_competitive")
    if governed and case_count > 0 and int(governed.get("answer_pass_count") or 0) == case_count:
        flags.append("perfect_governed_score_requires_holdout")
    if trace_complete:
        flags.append("governed_trace_complete")
    if pass_delta > 0:
        flags.append("governed_beats_scaffolded_rag_on_pass_count")
    elif pass_delta == 0:
        flags.append("governed_ties_scaffolded_rag_on_pass_count")
    else:
        flags.append("governed_underperforms_scaffolded_rag_on_pass_count")
    return flags


def _failure_summary(baselines: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        mode: summary.get("failures_by_task_type") or {}
        for mode, summary in baselines.items()
        if int(summary.get("failure_count") or 0) > 0
    }


def _next_review(*, case_count: int, baselines: dict[str, dict[str, Any]], pass_delta: int) -> str:
    governed = baselines.get("governed", {})
    if case_count == 0:
        return "No cases were run; rerun a representative pack before review."
    if int(governed.get("answer_pass_count") or 0) == case_count:
        return "Do not tune against this pack again; review in Workbench, then use a larger blind/adversarial mix."
    if pass_delta <= 0:
        return "Inspect governed misses against scaffolded RAG before promoting policy or scaffold changes."
    return "Review governed misses by task type, then decide whether the fix belongs in policy, retrieval, or scaffold selection."


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 3)


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return round(_as_float(value), 3)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _preview_confidence(review: dict[str, Any]) -> float:
    case_count = int(review.get("case_count") or 0)
    delta = review.get("governed_delta_vs_scaffolded_rag") or {}
    pass_delta = int(delta.get("answer_pass_delta") or 0)
    if case_count >= 30 and pass_delta > 0:
        return 0.7
    if case_count >= 6 and pass_delta > 0:
        return 0.62
    if pass_delta > 0:
        return 0.55
    return 0.45


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "unknown_pack"


def _title_pack(value: str) -> str:
    text = value.replace("local_router_rag_", "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "RAG evidence"


def _format_pass_delta(value: Any) -> str:
    delta = int(value or 0)
    return f"+{delta} pass" if delta > 0 else f"{delta} pass"


def _format_score_delta(value: float | None) -> str:
    if value is None:
        return "no score delta"
    return f"+{value:.3f}" if value >= 0 else f"{value:.3f}"
