"""Baseline comparison for CRT meaning-compression claims.

This is intentionally deterministic. It compares CRT-style governed state
against simpler memory baselines on the same scenarios used by run_lab.py.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.run_lab import (
    OUT_DIR,
    SCENARIOS,
    Scenario,
    canonical_meaning_state,
    crt_compressed_state,
    invariants_for,
    naive_summary_state,
    project_meaning_state,
    scenario_from_crt_memory_db,
    scenario_pack,
    score_projected,
    slot_only_state,
)


BASELINE_CLAIM = (
    "CRT should preserve governed meaning layers better than latest-only slots, "
    "naive summary, or plain retrieval."
)


def crt_governed_projection(scenario: Scenario) -> dict[str, Any]:
    return project_meaning_state(crt_compressed_state(scenario))


def latest_only_projection(scenario: Scenario) -> dict[str, Any]:
    return project_meaning_state(slot_only_state(scenario))


def summary_only_projection(scenario: Scenario) -> dict[str, Any]:
    return project_meaning_state(naive_summary_state(scenario))


def plain_retrieval_projection(scenario: Scenario) -> dict[str, Any]:
    """Simulate raw retrieval without governed state.

    It can surface current-looking values from memory text, including provisional
    claims, but it does not preserve history, contradictions, authority, policy
    locks, or response rules.
    """
    facts: dict[str, str] = {}
    preferences: dict[str, str] = {}

    for mem in sorted(scenario.memories, key=lambda m: m.timestamp):
        if not mem.slot or not mem.value:
            continue
        if mem.kind in {"user_fact", "observation"}:
            facts[mem.slot] = mem.value
        elif mem.kind == "preference":
            preferences[mem.slot] = mem.value

    return project_meaning_state(
        {
            "type": "plain_retrieval",
            "facts": facts,
            "history": {},
            "contradictions": [],
            "authority": {},
            "policies": {},
            "concerns": [],
            "preferences": preferences,
        }
    )


BASELINES: dict[str, Callable[[Scenario], dict[str, Any]]] = {
    "crt_governed": crt_governed_projection,
    "latest_only_slots": latest_only_projection,
    "plain_retrieval": plain_retrieval_projection,
    "summary_only": summary_only_projection,
}


def verdict(score: float) -> str:
    if score >= 0.999:
        return "pass"
    if score >= 0.40:
        return "partial"
    return "fail"


def score_baseline(scenario: Scenario, baseline: str, projected: dict[str, Any]) -> dict[str, Any]:
    expected = canonical_meaning_state(scenario.memories)
    invariants = invariants_for(expected)
    score, rows = score_projected(projected, invariants)
    dimensions: dict[str, list[float]] = {}
    for row in rows:
        dimensions.setdefault(row["dimension"], []).append(1.0 if row["passed"] else 0.0)

    return {
        "scenario": scenario.name,
        "baseline": baseline,
        "score": round(score, 3),
        "verdict": verdict(score),
        "dimension_scores": {
            dimension: round(sum(values) / len(values), 3)
            for dimension, values in sorted(dimensions.items())
        },
        "failed_invariants": [row["invariant"] for row in rows if not row["passed"]],
    }


def score_scenario(scenario: Scenario) -> dict[str, Any]:
    rows = [
        score_baseline(scenario, name, builder(scenario))
        for name, builder in BASELINES.items()
    ]
    rows.sort(key=lambda row: row["score"], reverse=True)
    return {
        "name": scenario.name,
        "evidence": scenario.evidence,
        "purpose": scenario.purpose,
        "baselines": rows,
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_baseline: dict[str, list[dict[str, Any]]] = {}
    for scenario in rows:
        for row in scenario["baselines"]:
            by_baseline.setdefault(row["baseline"], []).append(row)

    aggregate_rows = []
    for baseline, baseline_rows in by_baseline.items():
        aggregate_rows.append(
            {
                "baseline": baseline,
                "avg_score": round(sum(row["score"] for row in baseline_rows) / len(baseline_rows), 3),
                "pass_count": sum(1 for row in baseline_rows if row["verdict"] == "pass"),
                "partial_count": sum(1 for row in baseline_rows if row["verdict"] == "partial"),
                "fail_count": sum(1 for row in baseline_rows if row["verdict"] == "fail"),
                "case_count": len(baseline_rows),
            }
        )
    aggregate_rows.sort(key=lambda row: (row["avg_score"], row["pass_count"]), reverse=True)
    return aggregate_rows


def run(
    *,
    write_results: bool = True,
    scenarios: list[Scenario] | None = None,
) -> dict[str, Any]:
    scenario_set = scenarios if scenarios is not None else SCENARIOS
    scenario_rows = [score_scenario(scenario) for scenario in scenario_set]
    out = {
        "lab": "meaning_compression_baseline_eval",
        "claim": BASELINE_CLAIM,
        "scenario_count": len(scenario_set),
        "baseline_count": len(BASELINES),
        "aggregate": aggregate(scenario_rows),
        "scenarios": scenario_rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"baseline_eval_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nCRT Meaning Baseline Eval")
    print("=" * 80)
    print(out["claim"])
    print(f"Scenarios: {out['scenario_count']}  Baselines: {out['baseline_count']}\n")

    print("Aggregate")
    print("-" * 80)
    print(f"{'baseline':<20} {'avg':>7} {'pass':>6} {'partial':>8} {'fail':>6}")
    for row in out["aggregate"]:
        print(
            f"{row['baseline']:<20} "
            f"{row['avg_score']:>7.3f} "
            f"{row['pass_count']:>6} "
            f"{row['partial_count']:>8} "
            f"{row['fail_count']:>6}"
        )

    print("\nPer Scenario")
    print("-" * 80)
    for scenario in out["scenarios"]:
        verdicts = ", ".join(
            f"{row['baseline']}={row['verdict']}({row['score']:.3f})"
            for row in scenario["baselines"]
        )
        print(f"{scenario['name']:<24} {verdicts}")

    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CRT meaning baseline comparison.")
    parser.add_argument("--no-write", action="store_true", help="Do not write a result JSON file.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of table report.")
    parser.add_argument("--include-adversarial", action="store_true", help="Include the adversarial starter scenario pack.")
    parser.add_argument("--include-hardening", action="store_true", help="Include layer-specific scaffold hardening probes.")
    parser.add_argument("--crt-db", type=Path, help="Optional CRT memory SQLite DB to replay as an extra scenario.")
    parser.add_argument("--thread-id", help="Optional thread_id filter for --crt-db replay.")
    args = parser.parse_args()

    scenarios = scenario_pack(
        include_adversarial=args.include_adversarial,
        include_hardening=args.include_hardening,
    )
    if args.crt_db:
        scenarios.append(scenario_from_crt_memory_db(args.crt_db, thread_id=args.thread_id))
    out = run(write_results=not args.no_write, scenarios=scenarios)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
