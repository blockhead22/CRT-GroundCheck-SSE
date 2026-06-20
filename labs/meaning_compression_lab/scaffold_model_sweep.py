"""Cross-model sweep for the CRT meaning scaffold eval."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
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

class LiveSweepReporter:
    """Readable append-only terminal stream for long model sweeps."""

    def __init__(self, *, stream: io.TextIOBase | None = None, show_scaffold: bool = True):
        self.stream = stream or sys.stdout
        self.show_scaffold = show_scaffold
        self.started_at = time.monotonic()
        self.model = ""
        self.model_index = 0
        self.model_count = 0
        self.raw_pass = 0
        self.scaffold_pass = 0
        self.completed = 0

    def start_sweep(self, *, models: list[str], scenario_count: int) -> None:
        self.model_count = len(models)
        self._write(
            "\nCRT Meaning Scaffold — Live Sweep\n"
            + "=" * 72
            + f"\n{len(models)} models × {scenario_count} cases"
            + "\nLegend: RAW = retrieved transcript fragments; SCAFFOLD = governed meaning state\n"
        )

    def start_model(self, model: str, index: int) -> None:
        self.model = model
        self.model_index = index
        self.raw_pass = 0
        self.scaffold_pass = 0
        self.completed = 0
        self._write(
            f"\n{'#' * 72}\n"
            f"MODEL {index}/{self.model_count}: {model}\n"
            f"{'#' * 72}\n"
        )

    def finish_model(self, summary: dict[str, Any]) -> None:
        self._write(
            f"\nMODEL COMPLETE: {self.model}\n"
            f"  RAW {summary['raw_pass_count']}/{summary['case_count']}  |  "
            f"SCAFFOLD {summary['scaffold_pass_count']}/{summary['case_count']}  |  "
            f"DELTA +{summary['delta_pass_count']}\n"
        )

    def __call__(self, event: dict[str, Any]) -> None:
        event_type = event["type"]
        if event_type == "case_started":
            self._write(
                f"\n[{event['case_index']}/{event['case_count']}] {event['scenario']}\n"
                f"Why: {event['purpose']}\n"
                f"Question: {event['query']}\n"
            )
            if self.show_scaffold:
                self._write("Governed state:\n")
                for line in str(event["scaffold"]).splitlines():
                    self._write(f"  {line}\n")
            self._write("Running RAW arm...\n")
        elif event_type == "answer_completed":
            arm = str(event["arm"]).upper()
            judgment = event["judgment"]
            passed = bool(judgment["passed"])
            marker = "PASS" if passed else "FAIL"
            answer = _one_line(event["answer"], limit=240)
            self._write(f"{arm}: {answer}\n{arm} VERDICT: {marker}")
            reason = _judgment_reason(judgment)
            if reason:
                self._write(f" — {reason}")
            self._write("\n")
            if event["arm"] == "raw":
                self._write("Running SCAFFOLD arm...\n")
        elif event_type == "case_completed":
            row = event["row"]
            self.completed += 1
            self.raw_pass += int(bool(row["raw_judgment"]["passed"]))
            self.scaffold_pass += int(bool(row["scaffold_judgment"]["passed"]))
            elapsed = time.monotonic() - self.started_at
            self._write(
                f"RUNNING SCORE: RAW {self.raw_pass}/{self.completed}  |  "
                f"SCAFFOLD {self.scaffold_pass}/{self.completed}  |  "
                f"elapsed {_duration(elapsed)}\n"
                + "-" * 72
                + "\n"
            )

    def _write(self, text: str) -> None:
        self.stream.write(text)
        self.stream.flush()


def _one_line(value: Any, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _judgment_reason(judgment: dict[str, Any]) -> str:
    reasons = []
    if not judgment.get("contains_ok", True):
        missing = judgment.get("expected_contains") or []
        if missing:
            reasons.append("missing " + ", ".join(map(str, missing)))
    if not judgment.get("excludes_ok", True):
        excluded = judgment.get("expected_excludes") or []
        if excluded:
            reasons.append("leaked " + ", ".join(map(str, excluded)))
    return "; ".join(reasons)


def _duration(seconds: float) -> str:
    whole = max(0, int(seconds))
    minutes, secs = divmod(whole, 60)
    return f"{minutes}m {secs:02d}s" if minutes else f"{secs}s"


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
        "raw_semantic_pass_count": aggregate.get("raw_semantic_pass_count"),
        "scaffold_semantic_pass_count": aggregate.get("scaffold_semantic_pass_count"),
        "scaffold_contract_pass_count": aggregate.get("scaffold_contract_pass_count"),
        "scaffold_format_pass_count": aggregate.get("scaffold_format_pass_count"),
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
    out = {
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
    if all(row.get("scaffold_semantic_pass_count") is not None for row in model_rows):
        total_cases = sum(row["case_count"] for row in model_rows)
        out.update(
            {
                "raw_semantic_pass_count": sum(row["raw_semantic_pass_count"] for row in model_rows),
                "scaffold_semantic_pass_count": sum(row["scaffold_semantic_pass_count"] for row in model_rows),
                "scaffold_contract_pass_count": sum(row["scaffold_contract_pass_count"] for row in model_rows),
                "scaffold_format_pass_count": sum(row["scaffold_format_pass_count"] for row in model_rows),
                "total_case_count": total_cases,
            }
        )
    return out


def run(
    *,
    models: list[str] | tuple[str, ...] = DEFAULT_MODELS,
    timeout: int = 90,
    include_adversarial: bool = True,
    include_hardening: bool = False,
    write_results: bool = True,
    runner: Callable[..., dict[str, Any]] = run_scaffold_eval,
    live_reporter: LiveSweepReporter | None = None,
) -> dict[str, Any]:
    scenarios = scenario_pack(
        include_adversarial=include_adversarial,
        include_hardening=include_hardening,
    )
    model_rows = []
    raw_results = {}
    model_list = list(models)
    if live_reporter:
        live_reporter.start_sweep(models=model_list, scenario_count=len(scenarios))
    for model_index, model in enumerate(model_list, start=1):
        if live_reporter:
            live_reporter.start_model(model, model_index)
        runner_kwargs = dict(
            mode="ollama",
            model=model,
            timeout=timeout,
            write_results=False,
            scenarios=scenarios,
        )
        if live_reporter:
            runner_kwargs["event_callback"] = live_reporter
        result = runner(**runner_kwargs)
        summary = summarize_model(model, result)
        model_rows.append(summary)
        raw_results[model] = result
        if live_reporter:
            live_reporter.finish_model(summary)

    out = {
        "lab": "meaning_scaffold_model_sweep",
        "claim": CLAIM,
        "models": model_list,
        "include_adversarial": include_adversarial,
        "include_hardening": include_hardening,
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
    if "scaffold_semantic_pass_count" in agg:
        print(
            f"Three-part grader — semantic: "
            f"{agg['scaffold_semantic_pass_count']}/{agg['total_case_count']} | "
            f"format: {agg['scaffold_format_pass_count']}/{agg['total_case_count']} | "
            f"full contract: {agg['scaffold_contract_pass_count']}/{agg['total_case_count']}\n"
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
    parser.add_argument("--include-hardening", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--live", action="store_true", help="Stream a readable case-by-case terminal report.")
    parser.add_argument(
        "--live-no-scaffold",
        action="store_true",
        help="With --live, hide the governed-state lines for a more compact view.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    live_reporter = (
        LiveSweepReporter(show_scaffold=not args.live_no_scaffold)
        if args.live
        else None
    )
    out = run(
        models=args.models,
        timeout=args.timeout,
        include_adversarial=not args.no_adversarial,
        include_hardening=args.include_hardening,
        write_results=not args.no_write,
        live_reporter=live_reporter,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
