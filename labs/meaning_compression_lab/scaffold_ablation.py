"""Ablation study for CRT meaning scaffold components."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any

from labs.meaning_compression_lab.plain_rag_eval import PROBES, Probe, judge_answer
from labs.meaning_compression_lab.run_lab import (
    OUT_DIR,
    Scenario,
    full_transcript_state,
    representation_size,
    scenario_pack,
)
from labs.meaning_compression_lab.scaffold_eval import (
    build_meaning_scaffold,
    ollama_scaffold_answer,
    render_scaffold,
    scaffold_answer,
)


CLAIM = (
    "A meaning scaffold should fail predictably when load-bearing fragments are removed."
)


@dataclass(frozen=True)
class Ablation:
    name: str
    description: str
    remove_kinds: tuple[str, ...] = ()
    use_query_contract: bool = True
    include_policy_plaintext: bool = True


ABLATIONS: tuple[Ablation, ...] = (
    Ablation("full", "Complete scaffold."),
    Ablation("no_current_facts", "Remove CURRENT fragments.", ("current_fact",)),
    Ablation("no_history", "Remove HISTORY fragments.", ("history",)),
    Ablation("no_contradictions", "Remove CONTRADICTION fragments.", ("contradiction",)),
    Ablation("no_authority", "Remove AUTHORITY fragments.", ("authority",)),
    Ablation("no_policies", "Remove POLICY fragments.", ("policy",)),
    Ablation("no_reaction", "Remove REACTION fragments.", ("reaction",)),
    Ablation("no_preferences", "Remove PREFERENCE fragments.", ("preference",)),
    Ablation("no_query_contract", "Remove the model-facing question contract.", use_query_contract=False),
    Ablation("no_policy_plaintext", "Render policy as code-like slot only.", include_policy_plaintext=False),
)


def ablate_scaffold(scaffold: dict[str, Any], ablation: Ablation) -> dict[str, Any]:
    remove = set(ablation.remove_kinds)
    return {
        **scaffold,
        "fragments": [
            fragment
            for fragment in scaffold["fragments"]
            if fragment.get("kind") not in remove
        ],
    }


def answer_from_ablation(
    scaffold: dict[str, Any],
    probe: Probe,
    ablation: Ablation,
    *,
    mode: str,
    model: str,
    timeout: int,
) -> str:
    if mode == "deterministic":
        return scaffold_answer(scaffold, probe)
    if mode == "ollama":
        return ollama_scaffold_answer(
            scaffold,
            probe,
            model=model,
            timeout=timeout,
            use_query_contract=ablation.use_query_contract,
            include_policy_plaintext=ablation.include_policy_plaintext,
        )
    raise ValueError(f"unknown mode: {mode}")


def score_scenario(
    scenario: Scenario,
    ablation: Ablation,
    *,
    mode: str,
    model: str,
    timeout: int,
) -> dict[str, Any] | None:
    probe = PROBES.get(scenario.name)
    if probe is None:
        return None

    scaffold = ablate_scaffold(build_meaning_scaffold(scenario), ablation)
    answer = answer_from_ablation(
        scaffold,
        probe,
        ablation,
        mode=mode,
        model=model,
        timeout=timeout,
    )
    scaffold_text = render_scaffold(
        scaffold,
        include_policy_plaintext=ablation.include_policy_plaintext,
    )
    full_size = representation_size(full_transcript_state(scenario))
    scaffold_size = len(scaffold_text.encode("utf-8"))
    judgment = judge_answer(answer, probe)
    return {
        "scenario": scenario.name,
        "probe": probe.name,
        "query": probe.query,
        "answer": answer,
        "passed": judgment["passed"],
        "judgment": judgment,
        "scaffold_size_bytes": scaffold_size,
        "full_transcript_size_bytes": full_size,
        "scaffold_compression_ratio": round(scaffold_size / full_size, 3) if full_size else 0.0,
        "scaffold": scaffold_text,
    }


def summarize_ablation(ablation: Ablation, rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)
    pass_count = sum(1 for row in rows if row["passed"])
    avg_ratio = (
        sum(row["scaffold_compression_ratio"] for row in rows) / case_count
        if rows
        else 0.0
    )
    return {
        "ablation": ablation.name,
        "description": ablation.description,
        "case_count": case_count,
        "pass_count": pass_count,
        "fail_count": case_count - pass_count,
        "pass_rate": round(pass_count / case_count, 3) if rows else 0.0,
        "avg_scaffold_compression_ratio": round(avg_ratio, 3),
        "failed_scenarios": [
            {
                "scenario": row["scenario"],
                "probe": row["probe"],
                "answer": row["answer"],
                "expected_contains": row["judgment"]["expected_contains"],
                "expected_excludes": row["judgment"]["expected_excludes"],
            }
            for row in rows
            if not row["passed"]
        ],
    }


def run(
    *,
    mode: str = "deterministic",
    model: str = "qwen2.5:7b-instruct",
    timeout: int = 90,
    include_adversarial: bool = True,
    include_hardening: bool = True,
    write_results: bool = True,
    ablations: tuple[Ablation, ...] = ABLATIONS,
) -> dict[str, Any]:
    scenarios = scenario_pack(
        include_adversarial=include_adversarial,
        include_hardening=include_hardening,
    )
    ablation_results = []
    raw_rows: dict[str, list[dict[str, Any]]] = {}
    for ablation in ablations:
        rows = [
            row
            for scenario in scenarios
            if (row := score_scenario(scenario, ablation, mode=mode, model=model, timeout=timeout))
            is not None
        ]
        raw_rows[ablation.name] = rows
        ablation_results.append(summarize_ablation(ablation, rows))

    full = next(row for row in ablation_results if row["ablation"] == "full")
    for row in ablation_results:
        row["delta_from_full"] = row["pass_count"] - full["pass_count"]

    out = {
        "lab": "meaning_scaffold_ablation",
        "claim": CLAIM,
        "mode": mode,
        "model": model if mode == "ollama" else None,
        "include_adversarial": include_adversarial,
        "include_hardening": include_hardening,
        "scenario_count": len(scenarios),
        "full_pass_count": full["pass_count"],
        "ablation_results": ablation_results,
        "raw_rows": raw_rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"scaffold_ablation_{mode}_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMeaning Scaffold Ablation")
    print("=" * 80)
    print(out["claim"])
    if out["mode"] == "ollama":
        print(f"Mode: ollama  Model: {out['model']}")
    else:
        print("Mode: deterministic")
    print(f"Scenarios: {out['scenario_count']}\n")
    print(f"{'ablation':<22} {'pass':>7} {'rate':>7} {'delta':>7} {'ratio':>7}")
    print("-" * 64)
    for row in out["ablation_results"]:
        print(
            f"{row['ablation']:<22} "
            f"{row['pass_count']:>2}/{row['case_count']:<4} "
            f"{row['pass_rate']:>7.3f} "
            f"{row['delta_from_full']:>7} "
            f"{row['avg_scaffold_compression_ratio']:>7.3f}"
        )
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CRT meaning scaffold ablation study.")
    parser.add_argument("--mode", choices=("deterministic", "ollama"), default="deterministic")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-adversarial", action="store_true")
    parser.add_argument("--no-hardening", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        mode=args.mode,
        model=args.model,
        timeout=args.timeout,
        include_adversarial=not args.no_adversarial,
        include_hardening=not args.no_hardening,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
