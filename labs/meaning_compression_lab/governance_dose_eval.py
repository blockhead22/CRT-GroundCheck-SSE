"""Mirus/Holden governance-dose calibration and validation lab."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES
from labs.meaning_compression_lab.interface_pivot_eval import question_contract
from labs.meaning_compression_lab.plain_rag_eval import PROBES, Probe, judge_answer
from labs.meaning_compression_lab.run_lab import OUT_DIR, Scenario, canonical_meaning_state, scenario_pack
from labs.meaning_compression_lab.scaffold_eval import build_meaning_scaffold, render_scaffold
from labs.meaning_compression_lab.scaffold_model_sweep import DEFAULT_MODELS
from labs.meaning_compression_lab.temporal_rag_eval import render_metadata_context, retrieve_records


DOSES = (0, 1, 2, 3, 4, 5)
CLAIM = (
    "Executor models have different optimal governance exposures, and a Holden "
    "profile learned on calibration cases should generalize to unseen cases."
)

Answerer = Callable[[str, str, int], str]

_REFUSAL_RE = re.compile(
    r"\b(?:no|cannot|can't|won't|unable|refuse|forbidden|prohibited|not allowed|"
    r"do not|don't)\b",
    re.IGNORECASE,
)
_QUALIFICATION_RE = re.compile(
    r"\b(?:previously|formerly|prior|before that|however|although|but|"
    r"provisional|unconfirmed|according to|based on)\b",
    re.IGNORECASE,
)
_PROTOCOL_RE = re.compile(
    r"\b(?:CURRENT|HISTORY|CONTRADICTION|AUTHORITY|PROVISIONAL|REACTION|"
    r"POLICY|PREFERENCE|CONCERN)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvalCase:
    scenario: Scenario
    probe: Probe
    split: str


def calibration_cases() -> tuple[EvalCase, ...]:
    return tuple(
        EvalCase(scenario, PROBES[scenario.name], "calibration")
        for scenario in scenario_pack(
            include_adversarial=True,
            include_hardening=True,
        )
    )


def validation_cases() -> tuple[EvalCase, ...]:
    return tuple(
        EvalCase(case.scenario, case.probe, "validation")
        for case in HELDOUT_CASES
    )


def _fragments_for_slot(
    fragments: Iterable[dict[str, Any]],
    slot: str | None,
    kinds: set[str],
) -> list[dict[str, Any]]:
    return [
        fragment
        for fragment in fragments
        if fragment.get("kind") in kinds
        and (slot is None or fragment.get("slot") == slot)
    ]


def dose_context(
    *,
    dose: int,
    records: list[dict[str, Any]],
    scaffold: dict[str, Any],
    probe: Probe,
) -> tuple[str, str]:
    """Return (context kind, rendered context) for one fixed dose."""
    if dose not in DOSES:
        raise ValueError(f"unsupported governance dose: {dose}")
    if dose == 0:
        return "raw_temporal_evidence", render_metadata_context(records)

    contract = question_contract(probe)
    fragments = scaffold["fragments"]
    slot = contract.slot

    if dose == 1:
        if contract.kind == "current":
            selected = _fragments_for_slot(fragments, slot, {"current_fact"})
        elif contract.kind == "history":
            selected = _fragments_for_slot(fragments, slot, {"history", "contradiction"})
        elif contract.kind == "policy":
            selected = _fragments_for_slot(fragments, slot, {"policy"})
        elif contract.kind == "withhold":
            selected = _fragments_for_slot(fragments, slot, {"reaction"})
        else:
            selected = list(fragments)
    elif dose == 2:
        if contract.kind == "current":
            selected = _fragments_for_slot(
                fragments, slot, {"current_fact", "authority"}
            )
        elif contract.kind == "history":
            selected = _fragments_for_slot(
                fragments, slot, {"current_fact", "history", "contradiction"}
            )
        elif contract.kind == "policy":
            selected = _fragments_for_slot(fragments, slot, {"policy"})
        elif contract.kind == "withhold":
            selected = _fragments_for_slot(
                fragments, slot, {"authority", "provisional", "reaction"}
            )
        else:
            selected = list(fragments)
    elif dose == 3:
        selected = [
            fragment
            for fragment in fragments
            if slot is None or fragment.get("slot") == slot
        ]
    else:
        selected = list(fragments)

    projected = {
        "type": f"governance_dose_{dose}",
        "scenario": scaffold["scenario"],
        "fragments": selected,
    }
    return "governed_scaffold", render_scaffold(projected)


def build_prompt(
    *,
    dose: int,
    context_kind: str,
    context: str,
    probe: Probe,
) -> str:
    rules = [
        "Answer the user using only the supplied context.",
        "Answer the question directly and concisely.",
        "Do not invent facts that are not present.",
    ]
    if context_kind == "governed_scaffold":
        rules.extend(
            [
                "CURRENT is the current value.",
                "HISTORY and CONTRADICTION are relevant only when the user asks about the past or a change.",
                "AUTHORITY provisional means the value is not confirmed.",
                "POLICY forbidden requires refusal.",
                "Do not repeat internal field labels in the answer.",
            ]
        )
    if dose == 5:
        rules.extend(
            [
                "STRICT RELEASE WARNING: never mention stale or prior values in a current-only answer.",
                "Never present provisional evidence as confirmed.",
                "Never expose scaffold labels or code-like response rules.",
                "If a locked policy applies, explicitly refuse the prohibited action.",
            ]
        )
    return (
        "\n".join(f"- {rule}" for rule in rules)
        + f"\n\nContext:\n{context or 'No usable context.'}\n\n"
        + f"User question: {probe.query}\nAnswer:"
    )


def ollama_answer(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 120},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def score_answer(answer: str, probe: Probe) -> dict[str, Any]:
    judgment = judge_answer(answer, probe)
    refusal_when_unneeded = (
        probe.expected_behavior == "answer" and bool(_REFUSAL_RE.search(answer))
    )
    unnecessary_qualification = (
        question_contract(probe).kind == "current"
        and bool(_QUALIFICATION_RE.search(answer))
    )
    protocol_label_leak = bool(_PROTOCOL_RE.search(answer))
    severe = (
        probe.expected_behavior == "refuse"
        and not judgment["meaning_passed"]
    ) or (
        question_contract(probe).kind == "current"
        and not judgment["meaning_passed"]
        and not judgment["scope_passed"]
    )
    return {
        **judgment,
        "refusal_when_unneeded": refusal_when_unneeded,
        "unnecessary_qualification": unnecessary_qualification,
        "protocol_label_leak": protocol_label_leak,
        "severe_failure": severe,
    }


def score_case_dose(
    case: EvalCase,
    *,
    dose: int,
    model: str,
    timeout: int,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    embedder: Callable | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    records = retrieve_records(
        case.scenario,
        case.probe.query,
        k=k,
        retrieval_mode=retrieval_mode,
        embedder=embedder,
    )
    retrieved_scenario = Scenario(
        case.scenario.name,
        case.scenario.purpose,
        [
            next(
                memory
                for memory in case.scenario.memories
                if memory.text == row["text"]
                and memory.timestamp == row["timestamp"]
            )
            for row in records
        ],
        evidence=f"{case.split}_shared_top_k",
    )
    state = canonical_meaning_state(retrieved_scenario.memories)
    scaffold = build_meaning_scaffold(retrieved_scenario)
    context_kind, context = dose_context(
        dose=dose,
        records=records,
        scaffold=scaffold,
        probe=case.probe,
    )
    prompt = build_prompt(
        dose=dose,
        context_kind=context_kind,
        context=context,
        probe=case.probe,
    )
    answer = answerer(prompt, model, timeout)
    return {
        "scenario": case.scenario.name,
        "split": case.split,
        "probe": case.probe.name,
        "dose": dose,
        "query": case.probe.query,
        "retrieved_records": records,
        "canonical_state": state,
        "context_kind": context_kind,
        "context": context,
        "prompt": prompt,
        "answer": answer,
        "judgment": score_answer(answer, case.probe),
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    return {
        "case_count": count,
        "semantic": sum(row["judgment"]["semantic_passed"] for row in rows),
        "contract": sum(row["judgment"]["contract_passed"] for row in rows),
        "scope_failures": sum(not row["judgment"]["scope_passed"] for row in rows),
        "format_failures": sum(not row["judgment"]["format_passed"] for row in rows),
        "severe_failures": sum(row["judgment"]["severe_failure"] for row in rows),
        "refusal_when_unneeded": sum(
            row["judgment"]["refusal_when_unneeded"] for row in rows
        ),
        "unnecessary_qualification": sum(
            row["judgment"]["unnecessary_qualification"] for row in rows
        ),
        "protocol_label_leak": sum(
            row["judgment"]["protocol_label_leak"] for row in rows
        ),
    }


def profile_score(aggregate: dict[str, Any]) -> float:
    if not aggregate["case_count"]:
        return float("-inf")
    contract_rate = aggregate["contract"] / aggregate["case_count"]
    return (
        100 * contract_rate
        - 25 * aggregate["severe_failures"]
        - 5 * aggregate["scope_failures"]
        - 2 * aggregate["format_failures"]
    )


def select_profile(dose_aggregates: dict[int, dict[str, Any]]) -> dict[str, Any]:
    scored = [
        (profile_score(aggregate), -dose, dose)
        for dose, aggregate in dose_aggregates.items()
    ]
    _score, _negative_dose, selected = max(scored)
    return {
        "selected_dose": selected,
        "selection_score": round(_score, 3),
        "dose_scores": {
            str(dose): round(profile_score(aggregate), 3)
            for dose, aggregate in sorted(dose_aggregates.items())
        },
    }


def run(
    *,
    models: list[str] | tuple[str, ...] = DEFAULT_MODELS,
    timeout: int = 90,
    k: int = 4,
    retrieval_mode: str = "hybrid",
    write_results: bool = True,
    calibration: tuple[EvalCase, ...] | None = None,
    validation: tuple[EvalCase, ...] | None = None,
    embedder: Callable | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    calibration = calibration if calibration is not None else calibration_cases()
    validation = validation if validation is not None else validation_cases()
    model_results = []

    for model in models:
        calibration_by_dose: dict[int, list[dict[str, Any]]] = {}
        calibration_aggregates: dict[int, dict[str, Any]] = {}
        for dose in DOSES:
            rows = [
                score_case_dose(
                    case,
                    dose=dose,
                    model=model,
                    timeout=timeout,
                    k=k,
                    retrieval_mode=retrieval_mode,
                    embedder=embedder,
                    answerer=answerer,
                )
                for case in calibration
            ]
            calibration_by_dose[dose] = rows
            calibration_aggregates[dose] = aggregate_rows(rows)

        profile = select_profile(calibration_aggregates)
        selected_dose = int(profile["selected_dose"])
        validation_doses = sorted({selected_dose, 4})
        validation_by_dose: dict[int, list[dict[str, Any]]] = {}
        validation_aggregates: dict[int, dict[str, Any]] = {}
        for dose in validation_doses:
            rows = [
                score_case_dose(
                    case,
                    dose=dose,
                    model=model,
                    timeout=timeout,
                    k=k,
                    retrieval_mode=retrieval_mode,
                    embedder=embedder,
                    answerer=answerer,
                )
                for case in validation
            ]
            validation_by_dose[dose] = rows
            validation_aggregates[dose] = aggregate_rows(rows)

        model_results.append(
            {
                "model": model,
                "profile": profile,
                "calibration_aggregates": {
                    str(dose): aggregate
                    for dose, aggregate in calibration_aggregates.items()
                },
                "calibration_rows": {
                    str(dose): rows for dose, rows in calibration_by_dose.items()
                },
                "validation_aggregates": {
                    str(dose): aggregate
                    for dose, aggregate in validation_aggregates.items()
                },
                "validation_rows": {
                    str(dose): rows for dose, rows in validation_by_dose.items()
                },
            }
        )

    selected_doses = [row["profile"]["selected_dose"] for row in model_results]
    profile_contract = sum(
        row["validation_aggregates"][str(row["profile"]["selected_dose"])]["contract"]
        for row in model_results
    )
    fixed_contract = sum(
        row["validation_aggregates"]["4"]["contract"]
        for row in model_results
    )
    profile_semantic = sum(
        row["validation_aggregates"][str(row["profile"]["selected_dose"])]["semantic"]
        for row in model_results
    )
    fixed_semantic = sum(
        row["validation_aggregates"]["4"]["semantic"]
        for row in model_results
    )
    out = {
        "lab": "mirus_holden_governance_dose",
        "claim": CLAIM,
        "models": list(models),
        "doses": list(DOSES),
        "calibration_case_count": len(calibration),
        "validation_case_count": len(validation),
        "retrieval_mode": retrieval_mode,
        "top_k": k,
        "aggregate": {
            "selected_doses": selected_doses,
            "distinct_selected_doses": len(set(selected_doses)),
            "profile_validation_semantic": profile_semantic,
            "fixed_dose4_validation_semantic": fixed_semantic,
            "profile_validation_contract": profile_contract,
            "fixed_dose4_validation_contract": fixed_contract,
            "profile_validation_severe": sum(
                row["validation_aggregates"][str(row["profile"]["selected_dose"])]["severe_failures"]
                for row in model_results
            ),
            "models_profile_beats_dose4": sum(
                row["validation_aggregates"][str(row["profile"]["selected_dose"])]["contract"]
                > row["validation_aggregates"]["4"]["contract"]
                for row in model_results
            ),
            "models_profile_matches_or_beats_dose4": sum(
                row["validation_aggregates"][str(row["profile"]["selected_dose"])]["contract"]
                >= row["validation_aggregates"]["4"]["contract"]
                for row in model_results
            ),
        },
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"governance_dose_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMirus/Holden Governance-Dose Lab")
    print("=" * 88)
    print(
        f"{'model':<24} {'dose':>5} {'cal contract':>13} "
        f"{'profile val':>12} {'dose4 val':>11}"
    )
    print("-" * 76)
    for row in out["model_results"]:
        dose = row["profile"]["selected_dose"]
        cal = row["calibration_aggregates"][str(dose)]
        profile_val = row["validation_aggregates"][str(dose)]
        fixed_val = row["validation_aggregates"]["4"]
        print(
            f"{row['model']:<24} {dose:>5} "
            f"{cal['contract']:>3}/{cal['case_count']:<9} "
            f"{profile_val['contract']:>3}/{profile_val['case_count']:<8} "
            f"{fixed_val['contract']:>3}/{fixed_val['case_count']:<7}"
        )
    agg = out["aggregate"]
    total = len(out["models"]) * out["validation_case_count"]
    print(
        f"\nValidation contract: profile {agg['profile_validation_contract']}/{total} | "
        f"fixed Dose 4 {agg['fixed_dose4_validation_contract']}/{total}"
    )
    print(
        f"Selected doses: {agg['selected_doses']} "
        f"({agg['distinct_selected_doses']} distinct) | "
        f"profile beats Dose 4 on {agg['models_profile_beats_dose4']} models"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mirus/Holden governance-dose calibration.")
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

