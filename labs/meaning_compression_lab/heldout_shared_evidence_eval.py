"""Shared-evidence held-out comparison for temporal RAG versus hybrid CRT.

Retrieval runs once per case. The resulting top-k packet is then supplied to:

1. temporal metadata RAG, where the model resolves the evidence; and
2. hybrid CRT, where deterministic governed-state compilation happens first.

This prevents retrieval differences from being mistaken for governance gains.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.evaluation_contract import build_decision_trace
from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES, HeldOutCase
from labs.meaning_compression_lab.plain_rag_eval import judge_answer
from labs.meaning_compression_lab.run_lab import Memory, OUT_DIR, Scenario, canonical_meaning_state
from labs.meaning_compression_lab.scaffold_eval import (
    build_meaning_scaffold,
    ollama_scaffold_answer,
    render_scaffold,
)
from labs.meaning_compression_lab.scaffold_model_sweep import DEFAULT_MODELS
from labs.meaning_compression_lab.temporal_rag_eval import (
    build_prompt,
    ollama_answer,
    render_metadata_context,
    retrieve_records,
)


CLAIM = (
    "Given identical retrieved evidence, deterministic governed-state compilation "
    "should improve temporal, authority, contradiction, and policy answers."
)

Answerer = Callable[[str, str, int], str]
ScaffoldAnswerer = Callable[[dict[str, Any], Any, str, int], str]


def records_to_scenario(case: HeldOutCase, records: list[dict[str, Any]]) -> Scenario:
    """Rebuild a scenario from exactly the evidence shared with both arms."""
    return Scenario(
        name=case.scenario.name,
        purpose=case.scenario.purpose,
        evidence="heldout_shared_top_k",
        memories=[
            Memory(
                text=str(row["text"]),
                kind=str(row["kind"]),
                authority=str(row["authority"]),
                channel=str(row["source"]),
                timestamp=int(row["timestamp"]),
                slot=row.get("slot"),
                value=row.get("value"),
                prior_value=row.get("prior_value"),
            )
            for row in records
        ],
    )


def _default_scaffold_answerer(
    scaffold: dict[str, Any],
    probe: Any,
    model: str,
    timeout: int,
) -> str:
    return ollama_scaffold_answer(
        scaffold,
        probe,
        model=model,
        timeout=timeout,
    )


def _heldout_severity(case: HeldOutCase, judgment: dict[str, Any]) -> dict[str, str | None]:
    meaning = bool(judgment["meaning_passed"])
    scope = bool(judgment["scope_passed"])
    format_ok = bool(judgment["format_passed"])

    if meaning and scope and format_ok:
        return {"severity": "pass", "failure_layer": None}
    if meaning and scope:
        return {"severity": "degraded_pass", "failure_layer": "output_format"}

    authority_probe = case.probe.name in {
        "current_name",
        "current_employer",
        "current_project",
        "current_home_city",
        "confirmed_store_platform",
    }
    policy_probe = case.probe.expected_behavior == "refuse"
    if (authority_probe and not meaning and not scope) or (policy_probe and not meaning):
        return {
            "severity": "severe_failure",
            "failure_layer": "executor_interpretation",
        }
    if not meaning:
        return {"severity": "failure", "failure_layer": "executor_interpretation"}
    return {"severity": "failure", "failure_layer": "output_scope"}


def _trace(
    *,
    case: HeldOutCase,
    arm: str,
    records: list[dict[str, Any]],
    state: dict[str, Any] | None,
    selected_rule: str,
    context: str,
    answer: str,
    judgment: dict[str, Any],
) -> dict[str, Any]:
    trace = build_decision_trace(
        scenario=case.scenario.name,
        arm=arm,
        query=case.probe.query,
        retrieved_evidence=records,
        state_transformation=state,
        selected_rule=selected_rule,
        supplied_context=context,
        answer=answer,
        judgment=judgment,
    )
    trace.update(_heldout_severity(case, judgment))
    return trace


def score_case(
    case: HeldOutCase,
    *,
    model: str,
    timeout: int,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    embedder: Callable | None = None,
    temporal_answerer: Answerer = ollama_answer,
    scaffold_answerer: ScaffoldAnswerer = _default_scaffold_answerer,
) -> dict[str, Any]:
    records = retrieve_records(
        case.scenario,
        case.probe.query,
        k=k,
        retrieval_mode=retrieval_mode,
        embedder=embedder,
    )
    retrieved_text = "\n".join(str(row["text"]) for row in records).lower()
    missing_evidence = [
        marker
        for marker in case.required_evidence
        if marker.lower() not in retrieved_text
    ]

    temporal_context = render_metadata_context(records)
    temporal_prompt = build_prompt(records, case.probe)
    temporal_answer = temporal_answerer(temporal_prompt, model, timeout)
    temporal_judgment = judge_answer(temporal_answer, case.probe)

    retrieved_scenario = records_to_scenario(case, records)
    scaffold = build_meaning_scaffold(retrieved_scenario)
    scaffold_context = render_scaffold(scaffold)
    scaffold_answer = scaffold_answerer(
        scaffold,
        case.probe,
        model,
        timeout,
    )
    scaffold_judgment = judge_answer(scaffold_answer, case.probe)

    return {
        "scenario": case.scenario.name,
        "probe": case.probe.name,
        "query": case.probe.query,
        "retrieval_mode": retrieval_mode,
        "top_k": k,
        "required_evidence": list(case.required_evidence),
        "missing_required_evidence": missing_evidence,
        "retrieved_records": records,
        "temporal_answer": temporal_answer,
        "temporal_judgment": temporal_judgment,
        "scaffold": scaffold_context,
        "scaffold_answer": scaffold_answer,
        "scaffold_judgment": scaffold_judgment,
        "decision_traces": {
            "temporal_metadata_rag": _trace(
                case=case,
                arm="temporal_metadata_rag",
                records=records,
                state=None,
                selected_rule="model_resolves_temporal_metadata",
                context=temporal_context,
                answer=temporal_answer,
                judgment=temporal_judgment,
            ),
            "hybrid_crt": _trace(
                case=case,
                arm="hybrid_crt",
                records=records,
                state=canonical_meaning_state(retrieved_scenario.memories),
                selected_rule=f"scaffold:{case.probe.name}",
                context=scaffold_context,
                answer=scaffold_answer,
                judgment=scaffold_judgment,
            ),
        },
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    temporal_semantic = sum(row["temporal_judgment"]["semantic_passed"] for row in rows)
    hybrid_semantic = sum(row["scaffold_judgment"]["semantic_passed"] for row in rows)
    temporal_contract = sum(row["temporal_judgment"]["contract_passed"] for row in rows)
    hybrid_contract = sum(row["scaffold_judgment"]["contract_passed"] for row in rows)
    return {
        "case_count": count,
        "retrieval_complete_count": sum(not row["missing_required_evidence"] for row in rows),
        "temporal_semantic": temporal_semantic,
        "hybrid_semantic": hybrid_semantic,
        "semantic_delta_count": hybrid_semantic - temporal_semantic,
        "semantic_delta_points": round(
            100 * (hybrid_semantic - temporal_semantic) / count, 1
        ) if count else 0.0,
        "temporal_contract": temporal_contract,
        "hybrid_contract": hybrid_contract,
        "temporal_severe": sum(
            row["decision_traces"]["temporal_metadata_rag"]["severity"] == "severe_failure"
            for row in rows
        ),
        "hybrid_severe": sum(
            row["decision_traces"]["hybrid_crt"]["severity"] == "severe_failure"
            for row in rows
        ),
    }


def run(
    *,
    models: list[str] | tuple[str, ...] = DEFAULT_MODELS,
    timeout: int = 90,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    write_results: bool = True,
    cases: tuple[HeldOutCase, ...] = HELDOUT_CASES,
    embedder: Callable | None = None,
    temporal_answerer: Answerer = ollama_answer,
    scaffold_answerer: ScaffoldAnswerer = _default_scaffold_answerer,
) -> dict[str, Any]:
    model_results = []
    for model in models:
        rows = [
            score_case(
                case,
                model=model,
                timeout=timeout,
                k=k,
                retrieval_mode=retrieval_mode,
                embedder=embedder,
                temporal_answerer=temporal_answerer,
                scaffold_answerer=scaffold_answerer,
            )
            for case in cases
        ]
        model_results.append(
            {
                "model": model,
                "aggregate": aggregate(rows),
                "scenarios": rows,
            }
        )

    total_cases = sum(row["aggregate"]["case_count"] for row in model_results)
    temporal_semantic = sum(row["aggregate"]["temporal_semantic"] for row in model_results)
    hybrid_semantic = sum(row["aggregate"]["hybrid_semantic"] for row in model_results)
    out = {
        "lab": "heldout_shared_evidence_temporal_vs_hybrid",
        "claim": CLAIM,
        "models": list(models),
        "heldout_case_count": len(cases),
        "retrieval_mode": retrieval_mode,
        "top_k": k,
        "aggregate": {
            "total_case_count": total_cases,
            "temporal_semantic": temporal_semantic,
            "hybrid_semantic": hybrid_semantic,
            "semantic_delta_count": hybrid_semantic - temporal_semantic,
            "semantic_delta_points": round(
                100 * (hybrid_semantic - temporal_semantic) / total_cases,
                1,
            ) if total_cases else 0.0,
            "temporal_contract": sum(row["aggregate"]["temporal_contract"] for row in model_results),
            "hybrid_contract": sum(row["aggregate"]["hybrid_contract"] for row in model_results),
            "temporal_severe": sum(row["aggregate"]["temporal_severe"] for row in model_results),
            "hybrid_severe": sum(row["aggregate"]["hybrid_severe"] for row in model_results),
            "models_where_hybrid_wins": sum(
                row["aggregate"]["semantic_delta_count"] > 0 for row in model_results
            ),
            "models_where_temporal_wins": sum(
                row["aggregate"]["semantic_delta_count"] < 0 for row in model_results
            ),
            "models_tied": sum(
                row["aggregate"]["semantic_delta_count"] == 0 for row in model_results
            ),
        },
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"heldout_shared_evidence_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nHeld-Out Shared-Evidence Eval")
    print("=" * 80)
    print(f"Retrieval: {out['retrieval_mode']} top-{out['top_k']}")
    print(f"{'model':<24} {'temporal':>10} {'hybrid':>10} {'delta':>9} {'severe T/H':>12}")
    print("-" * 72)
    for row in out["model_results"]:
        agg = row["aggregate"]
        print(
            f"{row['model']:<24} "
            f"{agg['temporal_semantic']:>3}/{agg['case_count']:<6} "
            f"{agg['hybrid_semantic']:>3}/{agg['case_count']:<6} "
            f"{agg['semantic_delta_points']:>+8.1f} "
            f"{agg['temporal_severe']:>4}/{agg['hybrid_severe']:<4}"
        )
    agg = out["aggregate"]
    print(
        f"\nAggregate semantic: temporal {agg['temporal_semantic']}/{agg['total_case_count']} | "
        f"hybrid {agg['hybrid_semantic']}/{agg['total_case_count']} | "
        f"delta {agg['semantic_delta_points']:+.1f} points"
    )
    print(
        f"Severe failures: temporal {agg['temporal_severe']} | hybrid {agg['hybrid_severe']} | "
        f"hybrid wins {agg['models_where_hybrid_wins']}/4 models"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen held-out shared-evidence comparison.")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument(
        "--retrieval-mode",
        choices=("lexical", "embedding", "hybrid"),
        default="hybrid",
    )
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        models=args.models,
        timeout=args.timeout,
        k=args.top_k,
        retrieval_mode=args.retrieval_mode,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

