"""Run local-router replay ablations against the same pack."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.attention_profile_eval import PROFILE_BUILDERS
from labs.meaning_compression_lab.local_router_cli import build_case, build_trace, judge_trace
from labs.meaning_compression_lab.local_router_eval import _run_once, route_for_task, run_route
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import call_ollama, judge_answer, raw_prompt


DEFAULT_PACK = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_curated_v1.json")
MODES = ("raw_no_scaffold", "routed_no_repair", "routed_no_fallback", "full")


def run_ablation(
    *,
    pack_path: Path = DEFAULT_PACK,
    timeout: int = 300,
    max_cases: int | None = None,
    case_ids: tuple[str, ...] = (),
    modes: tuple[str, ...] = MODES,
    write_results: bool = True,
) -> dict[str, Any]:
    pack = json.loads(pack_path.read_text(encoding="utf-8-sig"))
    selected = list(pack.get("cases") or [])
    if case_ids:
        wanted = set(case_ids)
        selected = [item for item in selected if item.get("id") in wanted]
    cases = selected[:max_cases] if max_cases else selected
    rows = [_run_case_modes(item, timeout=timeout, modes=modes) for item in cases]
    out = {
        "lab": "local_router_ablation",
        "pack": pack.get("pack"),
        "pack_path": str(pack_path),
        "case_count": len(rows),
        "modes": list(modes),
        "case_ids": list(case_ids),
        "aggregate": _aggregate(rows, modes),
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"local_router_ablation_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def _run_case_modes(item: dict[str, Any], *, timeout: int, modes: tuple[str, ...]) -> dict[str, Any]:
    case = build_case(
        str(item.get("prompt") or ""),
        task_type=str(item.get("task_type") or ""),
        anchors=tuple(item.get("expected_receipts") or ()),
        concepts=tuple(item.get("required_concepts") or ()),
    )
    decision = route_for_task(case.spine["task_type"])
    results = {}
    for mode in modes:
        if mode == "raw_no_scaffold":
            answer = call_ollama(raw_prompt(case), decision.model, timeout)
            judgment = judge_answer(answer, case)
            results[mode] = {
                "answer": answer,
                "judgment": judgment,
                "repaired": False,
                "fallback_used": False,
                "trace_judgment": None,
            }
        elif mode == "routed_no_repair":
            answer = call_ollama(PROFILE_BUILDERS[decision.profile](case), decision.model, timeout)
            judgment = judge_answer(answer, case)
            trace = build_trace(case, {"route": decision.to_dict(), "judgment": judgment, "repaired": False, "fallback_used": False}, source=f"local_router_ablation:{item.get('id')}:{mode}")
            results[mode] = {
                "answer": answer,
                "judgment": judgment,
                "repaired": False,
                "fallback_used": False,
                "trace_judgment": judge_trace(trace, judgment),
            }
        elif mode == "routed_no_fallback":
            answer, judgment, repaired = _run_once(
                case,
                model=decision.model,
                profile=decision.profile,
                timeout=timeout,
                runner=call_ollama,
            )
            trace = build_trace(case, {"route": decision.to_dict(), "judgment": judgment, "repaired": repaired, "fallback_used": False}, source=f"local_router_ablation:{item.get('id')}:{mode}")
            results[mode] = {
                "answer": answer,
                "judgment": judgment,
                "repaired": repaired,
                "fallback_used": False,
                "trace_judgment": judge_trace(trace, judgment),
            }
        elif mode == "full":
            routed = run_route(case, timeout=timeout, runner=call_ollama)
            trace = build_trace(case, routed, source=f"local_router_ablation:{item.get('id')}:{mode}")
            results[mode] = {
                "answer": routed["answer"],
                "judgment": routed["judgment"],
                "repaired": routed["repaired"],
                "fallback_used": routed["fallback_used"],
                "trace_judgment": judge_trace(trace, routed["judgment"]),
            }
        else:
            raise ValueError(f"unknown ablation mode: {mode}")
    return {
        "id": item.get("id"),
        "task_type": item.get("task_type"),
        "route": decision.to_dict(),
        "modes": results,
    }


def _aggregate(rows: list[dict[str, Any]], modes: tuple[str, ...]) -> dict[str, Any]:
    out = {}
    for mode in modes:
        judgments = [row["modes"][mode]["judgment"] for row in rows]
        traces = [row["modes"][mode].get("trace_judgment") for row in rows]
        trace_rows = [trace for trace in traces if trace is not None]
        failures = [
            row for row in rows
            if not row["modes"][mode]["judgment"].get("passed")
            or (row["modes"][mode].get("trace_judgment") and not row["modes"][mode]["trace_judgment"].get("passed"))
        ]
        by_task_type = Counter(str(row.get("task_type") or "unknown") for row in failures)
        out[mode] = {
            "answer_pass_count": sum(1 for judgment in judgments if judgment.get("passed")),
            "answer_avg_score": round(sum(float(judgment.get("score") or 0) for judgment in judgments) / max(1, len(judgments)), 3),
            "trace_pass_count": sum(1 for trace in trace_rows if trace.get("passed")),
            "trace_avg_score": round(sum(float(trace.get("score") or 0) for trace in trace_rows) / max(1, len(trace_rows)), 3) if trace_rows else None,
            "repair_count": sum(1 for row in rows if row["modes"][mode].get("repaired")),
            "fallback_count": sum(1 for row in rows if row["modes"][mode].get("fallback_used")),
            "failure_count": len(failures),
            "failures_by_task_type": dict(sorted(by_task_type.items())),
        }
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nLocal Router Ablation")
    print("=" * 80)
    print(f"Pack: {out['pack']} | Cases: {out['case_count']}")
    for mode, aggregate in out["aggregate"].items():
        print(
            f"{mode}: answer {aggregate['answer_pass_count']}/{out['case_count']} "
            f"avg {aggregate['answer_avg_score']:.3f} trace {aggregate['trace_pass_count']}/{out['case_count']} "
            f"repairs {aggregate['repair_count']} fallbacks {aggregate['fallback_count']} "
            f"failures {aggregate['failure_count']}"
        )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local-router ablation replay.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--mode", action="append", choices=MODES)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run_ablation(
        pack_path=args.pack,
        timeout=args.timeout,
        max_cases=args.max_cases,
        case_ids=tuple(args.case_id or ()),
        modes=tuple(args.mode or MODES),
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
