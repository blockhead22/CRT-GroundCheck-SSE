"""Review-only feedback ledger for local-router replay results."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.run_lab import OUT_DIR


def build_feedback_ledger(replay: dict[str, Any]) -> dict[str, Any]:
    """Convert replay rows into structured, review-only feedback metadata."""
    rows = list(replay.get("rows") or [])
    feedback = [_feedback_for_row(row) for row in rows]
    tag_counts = Counter(tag for item in feedback for tag in item["tags"])
    route_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in feedback:
        route_counts[item["task_type"]].update(item["tags"])
    candidates = _learning_candidates(feedback, tag_counts, route_counts)
    return {
        "lab": "local_router_feedback_ledger",
        "source_replay": replay.get("result_path") or replay.get("pack_path") or "",
        "source_pack": replay.get("pack"),
        "created_at": int(time.time()),
        "feedback_count": len(feedback),
        "mode": "review_only",
        "writes_performed": False,
        "memory_ingestion_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "tag_counts": dict(sorted(tag_counts.items())),
        "route_tag_counts": {
            task_type: dict(sorted(counts.items()))
            for task_type, counts in sorted(route_counts.items())
        },
        "feedback": feedback,
        "workbench_preview": {
            "mode": "preview_only",
            "writes_performed": False,
            "memory_ingestion_performed": False,
            "support_pattern_import_performed": False,
            "reflection_create_performed": False,
            "inspected_turn_count": len(feedback),
            "candidates": candidates,
        },
    }


def _feedback_for_row(row: dict[str, Any]) -> dict[str, Any]:
    judgment = row.get("routed_judgment") or {}
    raw_judgment = row.get("raw_judgment") or {}
    trace_judgment = row.get("trace_judgment") or {}
    trace = row.get("trace") or {}
    route = row.get("route") or {}
    verifier = trace.get("verifier_flags") or judgment
    tags = _tags(row, judgment, raw_judgment, trace_judgment)
    return {
        "feedback_id": f"feedback_{row.get('id', 'unknown')}",
        "answer_id": str(row.get("id", "")),
        "trace_id": str(trace.get("turn_id") or ""),
        "task_type": str(row.get("task_type") or trace.get("task_type") or "unknown"),
        "route": route,
        "scaffold_profile": str(route.get("profile") or trace.get("scaffold_profile") or ""),
        "overall": _overall(row, judgment),
        "scores": {
            "groundedness": _coverage_score(verifier.get("receipt_hits"), trace.get("evidence_anchors")),
            "usefulness": _scaled(judgment.get("usefulness_score")),
            "tone_fit": _tone_score(judgment),
            "receipt_use": _coverage_score(verifier.get("receipt_hits"), trace.get("evidence_anchors")),
            "overclaim_risk": _overclaim_risk(judgment),
            "trace_quality": _scaled(trace_judgment.get("score")),
            "next_step_clarity": 5 if "next useful move" in " ".join(verifier.get("concept_hits") or []).lower() else 3,
        },
        "tags": tags,
        "human_note": "",
        "promotion_decision": "pending_review" if _needs_review(tags) else "none",
        "review_required": _needs_review(tags),
    }


def _tags(
    row: dict[str, Any],
    judgment: dict[str, Any],
    raw_judgment: dict[str, Any],
    trace_judgment: dict[str, Any],
) -> list[str]:
    tags: list[str] = []
    if raw_judgment and not raw_judgment.get("passed"):
        tags.append("raw_failed")
    if judgment.get("passed"):
        tags.append("routed_passed")
    else:
        tags.append("routed_failed")
    if row.get("combined_passed"):
        tags.append("combined_passed")
    if trace_judgment.get("passed"):
        tags.append("strong_trace")
    else:
        tags.append("weak_trace")
    if row.get("repaired"):
        tags.append("repair_used")
    if row.get("fallback_used"):
        tags.append("fallback_used")
    if judgment.get("forbidden_hits"):
        tags.append("overpromised")
    if judgment.get("leakage_hits"):
        tags.append("process_leakage")
    if judgment.get("weirdness_hits"):
        tags.append("weirdness_flag")
    if _coverage_score(judgment.get("receipt_hits"), (row.get("trace") or {}).get("evidence_anchors")) < 4:
        tags.append("missing_receipts")
    if row.get("delta", 0) > 0:
        tags.append("routed_improved")
    return sorted(set(tags))


def _learning_candidates(
    feedback: list[dict[str, Any]],
    tag_counts: Counter[str],
    route_counts: dict[str, Counter[str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if tag_counts.get("fallback_used", 0) >= 3:
        candidates.append(_candidate(
            candidate_id="local_router_feedback_fallback_review",
            summary=f"{tag_counts['fallback_used']} replay rows needed fallback routing.",
            proposed_action="Review primary route/scaffold choices before changing model policy.",
            risk="Fallback use is an eval signal, not proof that the fallback should become default.",
            surface="reflections",
            action="review_feedback_pattern",
            endpoint="/v1/reflections",
            draft={
                "subject": "local_router_fallback_usage",
                "observation": f"{tag_counts['fallback_used']} replay rows used fallback routing.",
                "interpretation": "Some primary scaffold choices may still be brittle even when final answers pass.",
                "alternatives": [
                    "The fallback rows may reflect narrow replay-pack artifacts.",
                    "Some fallback use may be acceptable if the primary route remains bounded.",
                ],
                "confidence": 0.55,
                "time_window": "local-router curated replay v1",
                "suggested_experiment": (
                    "Review the fallback rows before changing default routing or scaffold policy."
                ),
            },
            evidence=[_evidence("tag_count", "fallback_used", f"fallback_used={tag_counts['fallback_used']}")],
        ))
    for task_type, counts in sorted(route_counts.items()):
        if counts.get("missing_receipts", 0) >= 2:
            candidates.append(_candidate(
                candidate_id=f"local_router_feedback_{task_type}_receipts",
                summary=f"{task_type} had {counts['missing_receipts']} rows with weaker receipt coverage.",
                proposed_action="Review task anchors before relaxing verifier thresholds.",
                risk="Do not turn weak receipt coverage into memory or identity claims.",
                surface="support_patterns",
                action="review_support_pattern",
                endpoint="/v1/support-patterns/import",
                draft={
                    "candidate_id": f"support_{task_type}_receipt_boundary",
                    "candidate_type": "background_consolidation_support_pattern",
                    "category": "local_router_feedback",
                    "candidate_kind": "receipt_boundary",
                    "summary": f"For {task_type}, ask for or use concrete receipts before synthesis when coverage is weak.",
                    "suggested_response_rule": "Ask for concrete receipts or narrow the claim before rendering broad synthesis.",
                    "risk": "Review-only. This is a scaffold suggestion, not a confirmed fact.",
                    "source_signal": "local_router_feedback_ledger",
                    "evidence": [],
                },
                evidence=[_evidence("route_tag_count", task_type, f"missing_receipts={counts['missing_receipts']}")],
            ))
    return candidates


def _candidate(
    *,
    candidate_id: str,
    summary: str,
    proposed_action: str,
    risk: str,
    surface: str,
    action: str,
    draft: dict[str, Any],
    evidence: list[dict[str, str]],
    endpoint: str | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_type": "background_consolidation_candidate",
        "category": "local_router_feedback",
        "candidate_kind": "reviewed_feedback_pattern",
        "summary": summary,
        "proposed_action": proposed_action,
        "risk": risk,
        "review_required": True,
        "memory_write_allowed": False,
        "confirmed_fact": False,
        "review_route": {
            "surface": surface,
            "action": action,
            "endpoint": endpoint or surface,
            "requires_adapter": True,
            "draft": draft,
        },
        "evidence": evidence,
    }


def _evidence(evidence_type: str, reference_id: str, summary: str) -> dict[str, str]:
    return {
        "evidence_type": evidence_type,
        "reference_id": reference_id,
        "summary": summary,
    }


def _coverage_score(hits: Any, expected: Any) -> int:
    total = max(1, len(expected or []))
    return min(5, round((len(hits or []) / total) * 5))


def _scaled(value: Any) -> int:
    try:
        return min(5, max(0, round(float(value) * 5)))
    except (TypeError, ValueError):
        return 0


def _tone_score(judgment: dict[str, Any]) -> int:
    if judgment.get("leakage_hits") or judgment.get("weirdness_hits"):
        return 2
    if judgment.get("truncated"):
        return 1
    return 4


def _overclaim_risk(judgment: dict[str, Any]) -> int:
    risk = 0
    if judgment.get("forbidden_hits"):
        risk += 3
    if judgment.get("weirdness_hits"):
        risk += 1
    if judgment.get("leakage_hits"):
        risk += 1
    return min(5, risk)


def _overall(row: dict[str, Any], judgment: dict[str, Any]) -> str:
    if not row.get("combined_passed"):
        return "dislike"
    if row.get("repaired") or row.get("fallback_used") or float(judgment.get("score") or 0) < 0.75:
        return "mixed"
    return "like"


def _needs_review(tags: list[str]) -> bool:
    review_tags = {"routed_failed", "weak_trace", "repair_used", "fallback_used", "missing_receipts", "overpromised"}
    return any(tag in review_tags for tag in tags)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review-only feedback ledger from local-router replay JSON.")
    parser.add_argument("replay", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    ledger = build_feedback_ledger(replay)
    if not args.no_write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = args.out or OUT_DIR / f"local_router_feedback_ledger_{int(time.time())}.json"
        out_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        ledger["result_path"] = str(out_path)
    if args.json:
        print(json.dumps(ledger, indent=2))
    else:
        print(f"Feedback rows: {ledger['feedback_count']}")
        print(f"Tags: {json.dumps(ledger['tag_counts'], sort_keys=True)}")
        print(f"Workbench candidates: {len(ledger['workbench_preview']['candidates'])}")
        if "result_path" in ledger:
            print(f"Wrote {ledger['result_path']}")


if __name__ == "__main__":
    main()
