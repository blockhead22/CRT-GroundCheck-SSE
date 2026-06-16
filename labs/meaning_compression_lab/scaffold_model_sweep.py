"""Cross-model sweep for the CRT meaning scaffold eval."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.run_lab import OUT_DIR, scenario_pack
from labs.meaning_compression_lab.scaffold_eval import run as run_scaffold_eval


DEFAULT_MODELS = (
    "qwen2.5:7b-instruct",
    "phi3:3.8b",
    "llama3.2:latest",
    "mistral:latest",
)

CLAIM = (
    "Compressed meaning scaffolds should improve local model continuity behavior "
    "across executor families, not only for one prompt/model pairing."
)


def summarize_model(model: str, result: dict[str, Any]) -> dict[str, Any]:
    aggregate = result["aggregate"]
    failures = []
    for row in result["scenarios"]:
        raw_passed = bool(row["raw_judgment"]["passed"])
        scaffold_passed = bool(row["scaffold_judgment"]["passed"])
        if not scaffold_passed or raw_passed != scaffold_passed:
            failures.append(
                {
                    "scenario": row["scenario"],
                    "probe": row["probe"],
                    "raw_passed": raw_passed,
                    "scaffold_passed": scaffold_passed,
                    "raw_answer": row["raw_answer"],
                    "scaffold_answer": row["scaffold_answer"],
                }
            )

    return {
        "model": model,
        "case_count": aggregate["case_count"],
        "raw_pass_count": aggregate["raw_pass_count"],
        "scaffold_pass_count": aggregate["scaffold_pass_count"],
        "crt_pass_count": aggregate["crt_pass_count"],
        "delta_pass_count": aggregate["scaffold_pass_count"] - aggregate["raw_pass_count"],
        "raw_pass_rate": aggregate["raw_pass_rate"],
        "scaffold_pass_rate": aggregate["scaffold_pass_rate"],
        "avg_scaffold_compression_ratio": aggregate["avg_scaffold_compression_ratio"],
        "failure_count": sum(1 for row in result["scenarios"] if not row["scaffold_judgment"]["passed"]),
        "failures": failures,
    }


def aggregate_sweep(model_rows: list[dict[str, Any]]) -> dict[str, Any]:
    model_count = len(model_rows)
    if not model_rows:
        return {
            "model_count": 0,
            "models_with_scaffold_advantage": 0,
            "avg_raw_pass_rate": 0.0,
            "avg_scaffold_pass_rate": 0.0,
            "avg_delta_pass_count": 0.0,
        }
    return {
        "model_count": model_count,
        "models_with_scaffold_advantage": sum(
            1 for row in model_rows if row["scaffold_pass_count"] > row["raw_pass_count"]
        ),
        "models_with_perfect_scaffold": sum(1 for row in model_rows if row["failure_count"] == 0),
        "avg_raw_pass_rate": round(sum(row["raw_pass_rate"] for row in model_rows) / model_count, 3),
        "avg_scaffold_pass_rate": round(sum(row["scaffold_pass_rate"] for row in model_rows) / model_count, 3),
        "avg_delta_pass_count": round(sum(row["delta_pass_count"] for row in model_rows) / model_count, 3),
        "avg_scaffold_compression_ratio": round(
            sum(row["avg_scaffold_compression_ratio"] for row in model_rows) / model_count,
            3,
        ),
    }


def run(
    *,
    models: list[str] | tuple[str, ...] = DEFAULT_MODELS,
    timeout: int = 90,
    include_adversarial: bool = True,
    write_results: bool = True,
    runner: Callable[..., dict[str, Any]] = run_scaffold_eval,
) -> dict[str, Any]:
    scenarios = scenario_pack(include_adversarial=include_adversarial)
    model_rows = []
    raw_results = {}
    for model in models:
        result = runner(
            mode="ollama",
            model=model,
            timeout=timeout,
            write_results=False,
            scenarios=scenarios,
        )
        model_rows.append(summarize_model(model, result))
        raw_results[model] = result

    out = {
        "lab": "meaning_scaffold_model_sweep",
        "claim": CLAIM,
        "models": list(models),
        "include_adversarial": include_adversarial,
        "scenario_count": len(scenarios),
        "aggregate": aggregate_sweep(model_rows),
        "model_results": model_rows,
        "raw_results": raw_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"scaffold_model_sweep_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMeaning Scaffold Model Sweep")
    print("=" * 80)
    print(out["claim"])
    agg = out["aggregate"]
    print(
        f"Models: {agg['model_count']} | "
        f"Scaffold advantage: {agg['models_with_scaffold_advantage']}/{agg['model_count']} | "
        f"Perfect scaffold: {agg.get('models_with_perfect_scaffold', 0)}/{agg['model_count']}"
    )
    print(
        f"Avg raw rate: {agg['avg_raw_pass_rate']:.3f} | "
        f"Avg scaffold rate: {agg['avg_scaffold_pass_rate']:.3f} | "
        f"Avg delta cases: {agg['avg_delta_pass_count']:.3f} | "
        f"Avg scaffold ratio: {agg['avg_scaffold_compression_ratio']:.3f}\n"
    )
    print(f"{'model':<24} {'raw':>7} {'scaf':>7} {'delta':>7} {'fail':>6}")
    print("-" * 64)
    for row in out["model_results"]:
        print(
            f"{row['model']:<24} "
            f"{row['raw_pass_count']:>2}/{row['case_count']:<4} "
            f"{row['scaffold_pass_count']:>2}/{row['case_count']:<4} "
            f"{row['delta_pass_count']:>7} "
            f"{row['failure_count']:>6}"
        )
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cross-model CRT meaning scaffold sweep.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="Ollama model names to evaluate.",
    )
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-adversarial", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        models=args.models,
        timeout=args.timeout,
        include_adversarial=not args.no_adversarial,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
