"""Evaluate the sealed circuit breaker against an implementation-blind pack.

This evaluator deliberately reimplements conservative magnitude safety and the
small-graph cut oracle rather than calling the target's safety/oracle helpers.
Only the target's public prospective receipt is evaluated.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
AETHER_CORE = ROOT / "aether-core"
if str(AETHER_CORE) not in sys.path:
    sys.path.insert(0, str(AETHER_CORE))

from labs.epistemic_circuit_breaker_lab.epistemic_circuit_breaker_lab import (  # noqa: E402
    prospective_receipt,
)
from labs.epistemic_circuit_breaker_blind_replication.blind_pack_generator import (  # noqa: E402
    SCHEMA as PACK_SCHEMA,
    canonical_json,
    sha256,
)


RESULT_SCHEMA = "aether.epistemic_circuit_breaker_blind_result.v0"
RHO_LIMIT = 0.99
IMPACT_LIMIT = 6.0
IMPACT_STEPS = 24


def _matrix(
    case: dict[str, Any],
    *,
    removed: Iterable[str] = (),
    weight_scale: float = 1.0,
) -> tuple[np.ndarray, dict[str, int]]:
    nodes = case["graph"]["nodes"]
    index = {node["node_id"]: position for position, node in enumerate(nodes)}
    gains = {node["node_id"]: float(node["gain"]) for node in nodes}
    matrix = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    removed_ids = set(removed)
    for edge in case["graph"]["edges"]:
        if edge["edge_id"] in removed_ids:
            continue
        # Conservative magnitude composition: parallel opposing dependencies
        # remain two channels rather than cancelling before the risk check.
        matrix[index[edge["target"]], index[edge["source"]]] += (
            abs(float(edge["weight"]))
            * weight_scale
            * gains[edge["target"]]
        )
    return matrix, index


def independent_safety(
    case: dict[str, Any],
    *,
    removed: Iterable[str] = (),
    weight_scale: float = 1.0,
) -> dict[str, Any]:
    matrix, index = _matrix(case, removed=removed, weight_scale=weight_scale)
    values = np.linalg.eigvals(matrix) if matrix.size else []
    radius = float(max((abs(value) for value in values), default=0.0))
    state = np.zeros(len(index), dtype=np.float64)
    state[index[case["proposal"]["source_node_id"]]] = 1.0
    total = 0.0
    peak = 0.0
    for _ in range(IMPACT_STEPS):
        magnitude = float(np.abs(state).sum())
        total += magnitude
        peak = max(peak, magnitude)
        state = matrix @ state
        if float(np.abs(state).sum()) < 1e-10:
            break
        if float(np.abs(state).sum()) > 1e9:
            total = float("inf")
            peak = float("inf")
            break
    stable = radius < RHO_LIMIT
    within_budget = total <= IMPACT_LIMIT
    return {
        "spectral_radius": round(radius, 8),
        "total_impact": round(total, 8),
        "peak_impact": round(peak, 8),
        "stable": stable,
        "within_impact_budget": within_budget,
        "safe": stable and within_budget,
    }


def _reachable(
    case: dict[str, Any], source: str, target: str, removed: Iterable[str]
) -> bool:
    removed_ids = set(removed)
    adjacency: dict[str, list[str]] = {}
    for edge in case["graph"]["edges"]:
        if edge["edge_id"] not in removed_ids:
            adjacency.setdefault(edge["source"], []).append(edge["target"])
    frontier = [source]
    seen = {source}
    while frontier:
        node = frontier.pop(0)
        if node == target:
            return True
        for successor in adjacency.get(node, []):
            if successor not in seen:
                seen.add(successor)
                frontier.append(successor)
    return False


def protected_paths_preserved(case: dict[str, Any], removed: Iterable[str]) -> bool:
    return all(
        _reachable(case, pair[0], pair[1], removed)
        for pair in case["graph"]["protected_paths"]
    )


def independent_cut(case: dict[str, Any]) -> dict[str, Any] | None:
    if independent_safety(case)["safe"]:
        return {"edge_ids": [], "cost": 0.0, "state": independent_safety(case)}
    candidates = sorted(
        [edge for edge in case["graph"]["edges"] if not edge["protected"]],
        key=lambda edge: edge["edge_id"],
    )
    best: tuple[tuple[float, int, tuple[str, ...]], dict[str, Any]] | None = None
    for size in range(1, len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            edge_ids = tuple(sorted(edge["edge_id"] for edge in subset))
            if not protected_paths_preserved(case, edge_ids):
                continue
            state = independent_safety(case, removed=edge_ids)
            if not state["safe"]:
                continue
            cost = round(sum(float(edge["removal_cost"]) for edge in subset), 8)
            rank = (cost, size, edge_ids)
            row = {"edge_ids": list(edge_ids), "cost": cost, "state": state}
            if best is None or rank < best[0]:
                best = (rank, row)
    return best[1] if best else None


def independent_precheck(case: dict[str, Any]) -> str | None:
    proposal = case["proposal"]
    events = case["events"]
    if not proposal["assertive"]:
        return "non_assertive_input"
    if not proposal["route_write_allowed"]:
        return "route_write_disallowed"
    if any(not str(event["provenance_root"]).strip() for event in events):
        return "invalid_provenance"
    if int(proposal["commit_session"]) > int(proposal["witness_valid_until"]):
        return "stale_authority_witness"
    roots = {str(event["provenance_root"]) for event in events}
    if len(roots) < int(proposal["required_independent_sources"]):
        return "insufficient_independent_sources"
    root_authority: dict[str, int] = {}
    for event in events:
        root = str(event["provenance_root"])
        root_authority[root] = max(root_authority.get(root, 0), int(event["authority"]))
    derived = min(
        int(proposal["route_authority_cap"]),
        max(root_authority.values(), default=0),
    )
    if derived < int(proposal["required_authority"]):
        return "insufficient_authority"
    return None


def independent_decision(case: dict[str, Any]) -> dict[str, Any]:
    reason = independent_precheck(case)
    before = independent_safety(case)
    if reason:
        return {"action": "reject", "reason": reason, "before": before, "cut": None}
    if case["proposal"]["held_conflict"]:
        return {
            "action": "hold",
            "reason": "unresolved_equal_authority_contradiction",
            "before": before,
            "cut": None,
        }
    if before["safe"]:
        return {
            "action": "accept",
            "reason": "safe_authorized_commit",
            "before": before,
            "cut": None,
        }
    cut = independent_cut(case)
    if cut is None:
        return {"action": "reject", "reason": "no_safe_quarantine", "before": before, "cut": None}
    return {
        "action": "quarantine",
        "reason": "feedback_instability" if not before["stable"] else "broad_aggregate_impact",
        "before": before,
        "cut": cut,
    }


def baseline_actions(case: dict[str, Any], independent: dict[str, Any]) -> dict[str, str]:
    precheck = independent_precheck(case)
    provenance_action = "reject" if precheck else "accept"
    if precheck:
        threshold_action = "reject"
    elif case["proposal"]["held_conflict"]:
        threshold_action = "hold"
    elif independent["before"]["safe"]:
        threshold_action = "accept"
    else:
        threshold_action = "reject"
    return {
        "allow_all": "accept",
        "reject_all": "reject",
        "provenance_freshness": provenance_action,
        "risk_threshold_reject": threshold_action,
    }


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["blind_expectation"]
    independent = independent_decision(case)
    exact = prospective_receipt(case, algorithm="exact")
    greedy = prospective_receipt(case, algorithm="greedy")
    baseline = baseline_actions(case, independent)
    expected_cut = (independent.get("cut") or {}).get("edge_ids", [])
    exact_cut = (exact.get("quarantine") or {}).get("edge_ids", [])
    greedy_cut = (greedy.get("quarantine") or {}).get("edge_ids", [])
    perturbations = {
        str(scale): independent_safety(case, weight_scale=scale)
        for scale in (0.9, 1.0, 1.1)
    }
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "expected": expected,
        "independent": independent,
        "target_exact": exact,
        "target_greedy": greedy,
        "baselines": baseline,
        "perturbations": perturbations,
        "checks": {
            "analytical_construction_valid": (
                independent["action"] == expected["action"]
                and independent["reason"] == expected["reason_class"]
            ),
            "exact_action": exact["action"] == expected["action"],
            "exact_reason": exact["reason"] == expected["reason_class"],
            "greedy_action": greedy["action"] == expected["action"],
            "origin": exact["causal_origin_event_id"] == expected["origin_event_id"],
            "exact_cut": exact_cut == expected_cut,
            "greedy_cut": greedy_cut == expected_cut,
            "exact_no_unsafe_commit": not (
                exact["action"] == "accept" and expected["action"] != "accept"
            ),
            "greedy_no_unsafe_commit": not (
                greedy["action"] == "accept" and expected["action"] != "accept"
            ),
            "exact_benign_preserved": not (
                expected["action"] == "accept" and exact["action"] != "accept"
            ),
            "greedy_benign_preserved": not (
                expected["action"] == "accept" and greedy["action"] != "accept"
            ),
        },
    }


def _strategy_metrics(rows: list[dict[str, Any]], strategy: str) -> dict[str, int]:
    if strategy in {"target_exact", "target_greedy"}:
        action_for = lambda row: row[strategy]["action"]
    else:
        action_for = lambda row: row["baselines"][strategy]
    hazardous = [row for row in rows if row["expected"]["action"] != "accept"]
    benign = [row for row in rows if row["expected"]["action"] == "accept"]
    return {
        "expected_action_matches": sum(
            action_for(row) == row["expected"]["action"] for row in rows
        ),
        "unsafe_commits": sum(action_for(row) == "accept" for row in hazardous),
        "benign_accepts": sum(action_for(row) == "accept" for row in benign),
        "nonaccepts": sum(action_for(row) != "accept" for row in rows),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, Any] = {}
    for category in sorted({row["category"] for row in rows}):
        selected = [row for row in rows if row["category"] == category]
        by_category[category] = {
            "cases": len(selected),
            "exact_action_matches": sum(row["checks"]["exact_action"] for row in selected),
            "greedy_action_matches": sum(row["checks"]["greedy_action"] for row in selected),
            "independent_construction_valid": sum(
                row["checks"]["analytical_construction_valid"] for row in selected
            ),
        }
    benign = [row for row in rows if row["expected"]["action"] == "accept"]
    return {
        "cases": len(rows),
        "expected_actions": dict(Counter(row["expected"]["action"] for row in rows)),
        "independent_construction_valid": sum(
            row["checks"]["analytical_construction_valid"] for row in rows
        ),
        "exact_action_matches": sum(row["checks"]["exact_action"] for row in rows),
        "exact_reason_matches": sum(row["checks"]["exact_reason"] for row in rows),
        "greedy_action_matches": sum(row["checks"]["greedy_action"] for row in rows),
        "exact_cut_matches": sum(row["checks"]["exact_cut"] for row in rows),
        "greedy_cut_matches": sum(row["checks"]["greedy_cut"] for row in rows),
        "origin_matches": sum(row["checks"]["origin"] for row in rows),
        "benign_robust_at_all_scales": sum(
            all(state["safe"] for state in row["perturbations"].values())
            for row in benign
        ),
        "strategies": {
            strategy: _strategy_metrics(rows, strategy)
            for strategy in (
                "allow_all",
                "reject_all",
                "provenance_freshness",
                "risk_threshold_reject",
                "target_greedy",
                "target_exact",
            )
        },
        "by_category": by_category,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite blind result: {args.output}")
    sealed = json.loads(args.seal.read_text(encoding="utf-8"))
    pack = sealed["pack"]
    if pack.get("schema") != PACK_SCHEMA:
        raise ValueError("unexpected blind pack schema")
    if sha256(pack) != sealed["pack_sha256"]:
        raise ValueError("blind pack seal mismatch")
    evaluator_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    target_hash = hashlib.sha256(args.target.read_bytes()).hexdigest()
    if evaluator_hash != sealed["evaluator_sha256"]:
        raise ValueError("evaluator changed after pack freeze")
    if target_hash != sealed["target_sha256"]:
        raise ValueError("target changed after pack freeze")
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rows = [score_case(case) for case in pack["cases"]]
    summary = summarize(rows)
    failures = [
        {
            "case_id": row["case_id"],
            "category": row["category"],
            "expected_action": row["expected"]["action"],
            "actual_action": row["target_exact"]["action"],
            "expected_reason": row["expected"]["reason_class"],
            "actual_reason": row["target_exact"]["reason"],
        }
        for row in rows
        if not row["checks"]["exact_action"] or not row["checks"]["exact_reason"]
    ]
    gates = {
        "independent_construction_valid": summary["independent_construction_valid"] == summary["cases"],
        "target_action_generalization": summary["exact_action_matches"] == summary["cases"],
        "target_no_unsafe_commit": summary["strategies"]["target_exact"]["unsafe_commits"] == 0,
        "target_benign_preserved": summary["strategies"]["target_exact"]["benign_accepts"]
        == summary["expected_actions"].get("accept", 0),
        "origin_trace": summary["origin_matches"] == summary["cases"],
        "independent_cut_agreement": summary["exact_cut_matches"] == summary["cases"],
        "blind_pack_hash": True,
        "frozen_evaluator_hash": True,
        "frozen_target_hash": True,
    }
    result = {
        "schema": RESULT_SCHEMA,
        "started_at": started,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "seal_file": str(args.seal),
        "pack_sha256": sealed["pack_sha256"],
        "generator_sha256": sealed["generator_sha256"],
        "evaluator_sha256": evaluator_hash,
        "target_sha256": target_hash,
        "summary": summary,
        "gates": gates,
        "overall_gate_passed": all(gates.values()),
        "first_reveal_failures": failures,
        "results": rows,
        "limitations": [
            "The pack is implementation-blind but still synthetic and authored inside the same research program.",
            "Analytical expectations rely on a conservative magnitude model supplied by the evaluator.",
            "Weight perturbation is uniform scaling, not learned calibration error.",
            "A risk-threshold reject baseline does not preserve a quarantined partial update because the target currently records quarantine as no-write.",
            "No production, personal, provider, or durable-memory state is used.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "path": str(args.output),
        "overall_gate_passed": result["overall_gate_passed"],
        "summary": summary,
        "failed_cases": len(failures),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

