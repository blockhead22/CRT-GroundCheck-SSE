"""Map local-router lab traces into Workbench Trace-drawer shape.

The adapter is intentionally pure and conservative. It makes lab traces visible
in the Workbench trace vocabulary without treating lab evidence anchors as
confirmed memory or storing raw chain-of-thought.
"""

from __future__ import annotations

from typing import Any


def adapt_local_router_trace_for_workbench(trace: dict[str, Any]) -> dict[str, Any]:
    """Return a Workbench-renderable trace summary for a local-router trace."""
    verifier = trace.get("verifier_flags") or {}
    route = trace.get("route_selected") or {}
    passed = bool(verifier.get("passed"))
    repair_attempts = int(trace.get("repair_attempts") or 0)
    fallback_used = bool(trace.get("fallback_used"))
    return {
        "query": trace.get("user_request_summary", ""),
        "status": "resolved" if passed else "needs_review",
        "turn_id": trace.get("turn_id", ""),
        "conversation_id": trace.get("conversation_id", ""),
        "model": trace.get("model_selected") or route.get("model", ""),
        "generation_model": trace.get("model_selected") or route.get("model", ""),
        "route_decision": _route_decision(trace),
        "completion": {
            "source": "local_router_lab",
            "needs_stronger_model": not passed,
            "generation_model": trace.get("model_selected") or route.get("model", ""),
            "route_decision": _route_decision(trace),
            "guidance_kind": trace.get("scaffold_profile") or route.get("profile", ""),
            "guidance_repaired": repair_attempts > 0,
            "guidance_repair_failed": repair_attempts > 0 and not passed,
        },
        "plan": _plan(trace),
        "packets": _packets(trace),
        "tool_runs": [],
        "local_router_trace": {
            "trace_schema": trace.get("trace_schema"),
            "source": trace.get("source"),
            "task_type": trace.get("task_type"),
            "draft_quality_score": trace.get("draft_quality_score"),
            "contract_score": trace.get("contract_score"),
            "usefulness_score": trace.get("usefulness_score"),
            "final_confidence": trace.get("final_confidence"),
            "promotion_status": trace.get("promotion_status"),
            "raw_chain_of_thought_stored": trace.get("raw_chain_of_thought_stored"),
            "fallback_used": fallback_used,
            "repair_attempts": repair_attempts,
        },
    }


def _route_decision(trace: dict[str, Any]) -> dict[str, Any]:
    route = trace.get("route_selected") or {}
    confidence = _confidence_score(trace.get("final_confidence"))
    fallback_model = route.get("fallback_model") or ""
    return {
        "selected_route": f"local_router_{trace.get('task_type') or route.get('task_type') or 'unknown'}",
        "candidate_routes": [
            {
                "route": f"local_router_{route.get('task_type') or trace.get('task_type') or 'unknown'}",
                "confidence": confidence,
                "reason": route.get("reason", "local_router_trace_replay"),
            }
        ],
        "selected_model_policy": f"lab_profile_{trace.get('scaffold_profile') or route.get('profile') or 'unknown'}",
        "tool_policy": "no_tools_lab_replay",
        "repair_policy": _repair_policy(trace),
        "escalation_allowed": False,
        "escalation_reason": None,
        "route_reason": route.get("reason", "local_router_trace_replay"),
        "route_confidence": confidence,
        "risk_level": "low" if (trace.get("verifier_flags") or {}).get("passed") else "review",
        "memory_write_allowed": False,
        "silent_escalation_allowed": False,
        "model_recommendation": {
            "current_selected_model": trace.get("model_selected") or route.get("model", ""),
            "recommended_model_policy": "observational_lab_result",
            "recommended_model": trace.get("model_selected") or route.get("model", ""),
            "fallback_model": fallback_model,
            "confidence": str(trace.get("final_confidence") or "unknown"),
            "latency_caveat": "lab trace only; no automatic model switching",
            "evidence_path": "labs/meaning_compression_lab/results/traces",
            "observational_only": True,
            "model_selection_changed": False,
        },
    }


def _repair_policy(trace: dict[str, Any]) -> str:
    route = trace.get("route_selected") or {}
    if route.get("fallback_model") or route.get("fallback_profile"):
        return "repair_once_then_fallback"
    return "repair_once"


def _plan(trace: dict[str, Any]) -> dict[str, Any]:
    verifier = trace.get("verifier_flags") or {}
    coverage = _coverage(trace)
    passed = bool(verifier.get("passed"))
    return {
        "status": "resolved" if passed else "needs_review",
        "coverage": coverage,
        "unresolved_clauses": _unresolved_clauses(trace),
        "clauses": [
            {
                "clause_id": "c_route",
                "text": "Select local model and scaffold profile",
                "status": "resolved",
                "candidate_slots": [],
                "reason_code": "route_selected",
            },
            {
                "clause_id": "c_mirus",
                "text": "Compile Mirus packet and evidence anchors",
                "status": "resolved",
                "candidate_slots": [],
                "reason_code": "mirus_packet_compiled",
            },
            {
                "clause_id": "c_verifier",
                "text": "Verify answer against anchors, concepts, and disallowed claims",
                "status": "resolved" if passed else "needs_review",
                "candidate_slots": [],
                "reason_code": "verifier_passed" if passed else "verifier_needs_review",
            },
        ],
    }


def _packets(trace: dict[str, Any]) -> list[dict[str, Any]]:
    verifier = trace.get("verifier_flags") or {}
    passed = bool(verifier.get("passed"))
    return [
        _packet(
            request_id="r_route",
            clause_id="c_route",
            clause_text="Select local model and scaffold profile",
            slot_id="lab:route",
            mode="trace_metadata",
            release="answerable",
            reason="route_selected",
            planner_slot="route",
        ),
        _packet(
            request_id="r_mirus",
            clause_id="c_mirus",
            clause_text="Compile Mirus packet and evidence anchors",
            slot_id="lab:mirus_packet",
            mode="trace_metadata",
            release="answerable",
            reason="evidence_anchor_packet_available",
            planner_slot="mirus_packet",
        ),
        _packet(
            request_id="r_verifier",
            clause_id="c_verifier",
            clause_text="Verify answer against anchors, concepts, and disallowed claims",
            slot_id="lab:verifier",
            mode="trace_metadata",
            release="answerable" if passed else "conflict",
            reason="verifier_passed" if passed else _verifier_failure_reason(verifier),
            planner_slot="verifier",
        ),
    ]


def _packet(
    *,
    request_id: str,
    clause_id: str,
    clause_text: str,
    slot_id: str,
    mode: str,
    release: str,
    reason: str,
    planner_slot: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "clause_id": clause_id,
        "clause_text": clause_text,
        "planner_slot": planner_slot,
        "slot_id": slot_id,
        "mode": mode,
        "release": release,
        "reason": reason,
        "evidence": [],
    }


def _coverage(trace: dict[str, Any]) -> float:
    verifier = trace.get("verifier_flags") or {}
    anchor_count = len(trace.get("evidence_anchors") or [])
    concept_count = int((trace.get("mirus_packet_summary") or {}).get("required_concept_count") or 0)
    total = max(1, anchor_count + concept_count)
    hits = len(verifier.get("receipt_hits") or []) + len(verifier.get("concept_hits") or [])
    return round(min(1.0, hits / total), 3)


def _unresolved_clauses(trace: dict[str, Any]) -> list[str]:
    verifier = trace.get("verifier_flags") or {}
    unresolved = []
    for key in ("forbidden_hits", "leakage_hits", "weirdness_hits"):
        values = verifier.get(key) or []
        if values:
            unresolved.append(f"{key}: {', '.join(str(value) for value in values)}")
    if verifier.get("truncated"):
        unresolved.append("answer_truncated")
    if not verifier.get("passed") and not unresolved:
        unresolved.append("quality_or_coverage_below_gate")
    return unresolved


def _verifier_failure_reason(verifier: dict[str, Any]) -> str:
    for key in ("forbidden_hits", "leakage_hits", "weirdness_hits"):
        if verifier.get(key):
            return key
    if verifier.get("truncated"):
        return "answer_truncated"
    return "quality_or_coverage_below_gate"


def _confidence_score(value: Any) -> float:
    if value == "high":
        return 0.9
    if value == "medium":
        return 0.65
    if value == "low":
        return 0.35
    return 0.5
