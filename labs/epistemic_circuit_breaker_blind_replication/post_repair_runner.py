"""Run the untouched first blind pack against a repaired target exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from labs.epistemic_circuit_breaker_blind_replication import blind_evaluator
from labs.epistemic_circuit_breaker_blind_replication.blind_evaluator import (
    score_case,
    summarize,
)
from labs.epistemic_circuit_breaker_blind_replication.blind_pack_generator import sha256


SCHEMA = "aether.epistemic_circuit_breaker_post_repair_result.v0"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--first-result", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite post-repair result: {args.output}")

    sealed = json.loads(args.seal.read_text(encoding="utf-8"))
    pack = sealed["pack"]
    if sha256(pack) != sealed["pack_sha256"]:
        raise ValueError("blind pack seal mismatch")
    evaluator_path = Path(blind_evaluator.__file__).resolve()
    evaluator_hash = file_sha256(evaluator_path)
    if evaluator_hash != sealed["evaluator_sha256"]:
        raise ValueError("the sealed first-reveal evaluator changed")

    first_result_hash = file_sha256(args.first_result)
    target_hash = file_sha256(args.target)
    runner_hash = file_sha256(Path(__file__))
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
    expected_accepts = int(summary["expected_actions"].get("accept", 0))
    gates = {
        "untouched_pack": True,
        "untouched_first_evaluator": True,
        "original_failure_preserved": first_result_hash
        == "c913372cbda6ce7c3dd32c7827f53f2a14ab70375ce1a150f092737eef230335",
        "analytical_construction_valid": summary["independent_construction_valid"]
        == summary["cases"],
        "exact_action_regression": summary["exact_action_matches"] == summary["cases"],
        "exact_reason_regression": summary["exact_reason_matches"] == summary["cases"],
        "greedy_action_regression": summary["greedy_action_matches"] == summary["cases"],
        "no_unsafe_commit": summary["strategies"]["target_exact"]["unsafe_commits"] == 0,
        "benign_acceptance_preserved": summary["strategies"]["target_exact"]["benign_accepts"]
        == expected_accepts,
        "origin_trace_preserved": summary["origin_matches"] == summary["cases"],
        "independent_cut_agreement": summary["exact_cut_matches"] == summary["cases"],
    }
    result = {
        "schema": SCHEMA,
        "started_at": started,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pack_sha256": sealed["pack_sha256"],
        "original_target_sha256": sealed["target_sha256"],
        "repaired_target_sha256": target_hash,
        "first_evaluator_sha256": evaluator_hash,
        "post_repair_runner_sha256": runner_hash,
        "first_result_sha256": first_result_hash,
        "repair_scope": [
            "required-authority precommit enforcement",
            "strict provenance-chain validation",
            "magnitude-before-composition signed-channel safety",
            "explicit advisory no-write quarantine semantics",
        ],
        "summary": summary,
        "gates": gates,
        "overall_gate_passed": all(gates.values()),
        "remaining_failures": failures,
        "results": rows,
        "limitations": [
            "This is a regression on a revealed pack, not a second blind generalization result.",
            "The graph structures and analytical expectations remain synthetic.",
            "Near-limit calibration sensitivity remains measured rather than solved.",
            "Quarantine remains advisory no-write containment, so cut utility is not realized.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "path": str(args.output),
        "repaired_target_sha256": target_hash,
        "overall_gate_passed": result["overall_gate_passed"],
        "summary": summary,
        "remaining_failures": len(failures),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

