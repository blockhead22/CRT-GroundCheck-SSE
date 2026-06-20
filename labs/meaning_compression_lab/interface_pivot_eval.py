"""Frozen CRT interface-pivot ablation.

Compares the full scaffold, query-shaped projection, and projection plus a
deterministic release gate over identical retrieved evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES, HeldOutCase
from labs.meaning_compression_lab.heldout_shared_evidence_eval import records_to_scenario
from labs.meaning_compression_lab.plain_rag_eval import Probe, judge_answer
from labs.meaning_compression_lab.run_lab import OUT_DIR, canonical_meaning_state
from labs.meaning_compression_lab.scaffold_eval import (
    build_meaning_scaffold,
    ollama_scaffold_answer,
    render_scaffold,
)
from labs.meaning_compression_lab.scaffold_model_sweep import DEFAULT_MODELS
from labs.meaning_compression_lab.temporal_rag_eval import retrieve_records


CLAIM = (
    "Query-shaped state projection plus deterministic release validation should "
    "remove model/scaffold interface failures without changing retrieval or state."
)

ScaffoldAnswerer = Callable[[dict[str, Any], Probe, str, int], str]

_INTERNAL_FORMAT_RE = re.compile(
    r"\b(?:CURRENT|HISTORY|CONTRADICTION|AUTHORITY|PROVISIONAL|REACTION|"
    r"POLICY|PREFERENCE|CONCERN)\s+[A-Za-z0-9_.-]+\s*(?:=|:)",
    re.IGNORECASE,
)
_REFUSAL_RE = re.compile(
    r"\b(?:no|cannot|can't|won't|refuse|forbidden|prohibited|not allowed|"
    r"do not|don't)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QuestionContract:
    kind: str
    slot: str | None = None


_CURRENT_SLOTS = {
    "current_name": "name",
    "current_employer": "employer",
    "current_favorite_color": "favorite_color",
    "current_project": "current_project",
    "current_home_city": "home_city",
    "confirmed_store_platform": "store_platform",
}

_HISTORY_SLOTS = {
    "previous_employer": "employer",
    "previous_camera_system": "camera_system",
    "name_correction_status": "name",
}

_POLICY_SLOTS = {
    "locked_force_push_policy": "git.force_push_main",
    "destructive_command_policy": "shell.destructive_without_confirmation",
    "production_db_mock_policy": "db.production_write_without_sqlite_mock",
}


def question_contract(probe: Probe) -> QuestionContract:
    if probe.name in _CURRENT_SLOTS:
        return QuestionContract("current", _CURRENT_SLOTS[probe.name])
    if probe.name in _HISTORY_SLOTS:
        return QuestionContract("history", _HISTORY_SLOTS[probe.name])
    if probe.name in _POLICY_SLOTS or probe.expected_behavior == "refuse":
        return QuestionContract("policy", _POLICY_SLOTS.get(probe.name))
    if probe.expected_behavior == "withhold":
        return QuestionContract("withhold")
    return QuestionContract("general")


def project_scaffold(
    scaffold: dict[str, Any],
    probe: Probe,
) -> dict[str, Any]:
    contract = question_contract(probe)
    fragments = scaffold["fragments"]

    if contract.kind == "current":
        projected = [
            fragment
            for fragment in fragments
            if fragment.get("slot") == contract.slot
            and fragment.get("kind") in {"current_fact", "authority"}
        ]
    elif contract.kind == "history":
        projected = [
            fragment
            for fragment in fragments
            if fragment.get("slot") == contract.slot
            and fragment.get("kind")
            in {"current_fact", "history", "contradiction", "authority"}
        ]
    elif contract.kind == "policy":
        projected = [
            fragment
            for fragment in fragments
            if fragment.get("kind") == "policy"
            and (contract.slot is None or fragment.get("slot") == contract.slot)
        ]
    elif contract.kind == "withhold":
        projected = [
            fragment
            for fragment in fragments
            if fragment.get("kind") in {"authority", "provisional", "reaction"}
        ]
    else:
        projected = list(fragments)

    return {
        "type": "meaning_scaffold_projection",
        "scenario": scaffold["scenario"],
        "question_contract": {
            "kind": contract.kind,
            "slot": contract.slot,
        },
        "fragments": projected,
    }


def _values_for_slot(
    state: dict[str, Any],
    slot: str,
    *,
    exclude: str | None = None,
) -> list[str]:
    values: list[str] = []
    values.extend(str(value) for value in state["history"].get(slot, []))
    values.extend(str(value) for value in state["provisional"].get(slot, []))
    return list(
        dict.fromkeys(
            value
            for value in values
            if value and (exclude is None or value.lower() != exclude.lower())
        )
    )


def validate_and_repair(
    draft: str,
    *,
    probe: Probe,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Apply at most one deterministic release repair."""
    contract = question_contract(probe)
    answer = (draft or "").strip()
    violations: list[str] = []
    repaired = answer

    if contract.kind == "current" and contract.slot:
        current = state["facts"].get(contract.slot)
        if not current:
            return {
                "status": "blocked",
                "released_answer": "",
                "repair_applied": False,
                "repair_reason": "missing_confirmed_current_value",
                "violations": ["missing_current_value"],
            }
        current_text = str(current)
        if current_text.lower() not in answer.lower():
            violations.append("missing_current_value")
        leaked = [
            value
            for value in _values_for_slot(state, contract.slot, exclude=current_text)
            if value.lower() in answer.lower()
        ]
        if leaked:
            violations.append("leaked_noncurrent_value")
        if _INTERNAL_FORMAT_RE.search(answer):
            violations.append("internal_scaffold_syntax")
        if violations:
            repaired = current_text

    elif contract.kind == "policy" and contract.slot:
        forbidden = state["policies"].get(contract.slot) == "forbidden"
        if forbidden and not _REFUSAL_RE.search(answer):
            violations.append("missing_policy_refusal")
            repaired = _policy_repair(contract.slot)
        elif _INTERNAL_FORMAT_RE.search(answer):
            violations.append("internal_scaffold_syntax")
            repaired = _policy_repair(contract.slot)

    elif _INTERNAL_FORMAT_RE.search(answer):
        violations.append("internal_scaffold_syntax")
        return {
            "status": "blocked",
            "released_answer": "",
            "repair_applied": False,
            "repair_reason": "unsupported_deterministic_repair",
            "violations": violations,
        }

    return {
        "status": "repaired" if violations else "released",
        "released_answer": repaired,
        "repair_applied": bool(violations),
        "repair_reason": ",".join(violations) if violations else None,
        "violations": violations,
    }


def _policy_repair(slot: str) -> str:
    if slot == "git.force_push_main":
        return "No. Do not force push to main."
    if slot == "shell.destructive_without_confirmation":
        return "No. Do not run destructive shell commands without explicit confirmation."
    if slot == "db.production_write_without_sqlite_mock":
        return "No. Use an isolated SQLite mock test before production database write-path changes."
    return "No. A locked policy forbids that action."


def _default_answerer(
    scaffold: dict[str, Any],
    probe: Probe,
    model: str,
    timeout: int,
) -> str:
    return ollama_scaffold_answer(
        scaffold,
        probe,
        model=model,
        timeout=timeout,
    )


def score_case(
    case: HeldOutCase,
    *,
    model: str,
    timeout: int,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    embedder: Callable | None = None,
    answerer: ScaffoldAnswerer = _default_answerer,
) -> dict[str, Any]:
    records = retrieve_records(
        case.scenario,
        case.probe.query,
        k=k,
        retrieval_mode=retrieval_mode,
        embedder=embedder,
    )
    retrieved_scenario = records_to_scenario(case, records)
    state = canonical_meaning_state(retrieved_scenario.memories)
    full_scaffold = build_meaning_scaffold(retrieved_scenario)
    projected_scaffold = project_scaffold(full_scaffold, case.probe)

    full_answer = answerer(full_scaffold, case.probe, model, timeout)
    projected_answer = answerer(projected_scaffold, case.probe, model, timeout)
    gate = validate_and_repair(
        projected_answer,
        probe=case.probe,
        state=state,
    )
    gated_answer = gate["released_answer"]

    return {
        "scenario": case.scenario.name,
        "probe": case.probe.name,
        "query": case.probe.query,
        "retrieved_records": records,
        "canonical_state": state,
        "full_scaffold": render_scaffold(full_scaffold),
        "projected_scaffold": render_scaffold(projected_scaffold),
        "question_contract": projected_scaffold["question_contract"],
        "full_answer": full_answer,
        "projected_answer": projected_answer,
        "gated_answer": gated_answer,
        "full_judgment": judge_answer(full_answer, case.probe),
        "projected_judgment": judge_answer(projected_answer, case.probe),
        "gated_judgment": judge_answer(gated_answer, case.probe),
        "gate": gate,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    out = {"case_count": count}
    for arm, judgment_key in (
        ("full", "full_judgment"),
        ("projected", "projected_judgment"),
        ("gated", "gated_judgment"),
    ):
        out[f"{arm}_semantic"] = sum(
            row[judgment_key]["semantic_passed"] for row in rows
        )
        out[f"{arm}_contract"] = sum(
            row[judgment_key]["contract_passed"] for row in rows
        )
    out["repair_count"] = sum(row["gate"]["repair_applied"] for row in rows)
    out["blocked_count"] = sum(row["gate"]["status"] == "blocked" for row in rows)
    out["false_repair_count"] = sum(
        row["gate"]["repair_applied"]
        and row["projected_judgment"]["contract_passed"]
        for row in rows
    )
    return out


def run(
    *,
    models: list[str] | tuple[str, ...] = DEFAULT_MODELS,
    timeout: int = 90,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    write_results: bool = True,
    cases: tuple[HeldOutCase, ...] = HELDOUT_CASES,
    embedder: Callable | None = None,
    answerer: ScaffoldAnswerer = _default_answerer,
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
                answerer=answerer,
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

    total = sum(row["aggregate"]["case_count"] for row in model_results)
    aggregate_row = {
        "total_case_count": total,
        "full_semantic": sum(row["aggregate"]["full_semantic"] for row in model_results),
        "projected_semantic": sum(row["aggregate"]["projected_semantic"] for row in model_results),
        "gated_semantic": sum(row["aggregate"]["gated_semantic"] for row in model_results),
        "full_contract": sum(row["aggregate"]["full_contract"] for row in model_results),
        "projected_contract": sum(row["aggregate"]["projected_contract"] for row in model_results),
        "gated_contract": sum(row["aggregate"]["gated_contract"] for row in model_results),
        "repair_count": sum(row["aggregate"]["repair_count"] for row in model_results),
        "blocked_count": sum(row["aggregate"]["blocked_count"] for row in model_results),
        "false_repair_count": sum(row["aggregate"]["false_repair_count"] for row in model_results),
    }
    out = {
        "lab": "crt_interface_pivot_ablation",
        "claim": CLAIM,
        "models": list(models),
        "case_count": len(cases),
        "retrieval_mode": retrieval_mode,
        "top_k": k,
        "aggregate": aggregate_row,
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"interface_pivot_ablation_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nCRT Interface Pivot Ablation")
    print("=" * 80)
    print(f"{'model':<24} {'full':>8} {'project':>8} {'gated':>8} {'repairs':>8}")
    print("-" * 64)
    for row in out["model_results"]:
        agg = row["aggregate"]
        print(
            f"{row['model']:<24} "
            f"{agg['full_semantic']:>2}/{agg['case_count']:<4} "
            f"{agg['projected_semantic']:>2}/{agg['case_count']:<4} "
            f"{agg['gated_semantic']:>2}/{agg['case_count']:<4} "
            f"{agg['repair_count']:>8}"
        )
    agg = out["aggregate"]
    print(
        f"\nSemantic full/projected/gated: "
        f"{agg['full_semantic']}/{agg['total_case_count']} | "
        f"{agg['projected_semantic']}/{agg['total_case_count']} | "
        f"{agg['gated_semantic']}/{agg['total_case_count']}"
    )
    print(
        f"Contract full/projected/gated: "
        f"{agg['full_contract']}/{agg['total_case_count']} | "
        f"{agg['projected_contract']}/{agg['total_case_count']} | "
        f"{agg['gated_contract']}/{agg['total_case_count']}"
    )
    print(
        f"Repairs: {agg['repair_count']} | blocked: {agg['blocked_count']} | "
        f"false repairs: {agg['false_repair_count']}"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen CRT interface pivot ablation.")
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

