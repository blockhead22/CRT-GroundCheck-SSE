"""Bounded-fetch integration using inferred slots instead of declared slots."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from typing import Any, Callable

from labs.meaning_compression_lab.bounded_fetch_eval import (
    Answerer,
    FROZEN_PROFILE_SHA256,
    aggregate as aggregate_model_rows,
    load_frozen_profiles,
    ollama_answer,
    score_case,
)
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.slot_request_inference import infer_slot_request
from labs.meaning_compression_lab.untouched_fetch_cases import (
    FetchCase,
    UNTOUCHED_FETCH_CASES,
)


def infer_case(case: FetchCase) -> dict[str, Any]:
    available_slots = sorted(
        {
            memory.slot
            for memory in case.scenario.memories
            if memory.slot
        }
    )
    inference = infer_slot_request(case.probe.query, available_slots)
    return {
        "available_slots": available_slots,
        "inference": inference,
    }


def clarification_for(case: FetchCase, candidates: list[dict[str, Any]]) -> str:
    labels = [
        candidate["slot"].replace("_", " ").replace(".", " ")
        for candidate in candidates[:2]
    ]
    if labels:
        return "I need clarification about whether you mean " + " or ".join(labels) + "."
    return "I need clarification about which stored fact you mean."


def run(
    *,
    timeout: int = 90,
    write_results: bool = True,
    cases: tuple[FetchCase, ...] = UNTOUCHED_FETCH_CASES,
    embedder: Callable | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    profiles = load_frozen_profiles()
    model_results = []

    for model, profile in profiles["profiles"].items():
        dose = int(profile["default_dose"])
        rows = []
        blocked = []
        for case in cases:
            inferred = infer_case(case)
            inference = inferred["inference"]
            if inference.status != "resolved":
                blocked.append(
                    {
                        "scenario": case.scenario.name,
                        "query": case.probe.query,
                        "inference": inference.to_dict(),
                        "clarification": clarification_for(
                            case,
                            [candidate.__dict__ for candidate in inference.candidates],
                        ),
                    }
                )
                continue

            inferred_case = replace(
                case,
                requested_slot=inference.requested_slots[0],
            )
            row = score_case(
                inferred_case,
                model=model,
                dose=dose,
                timeout=timeout,
                embedder=embedder,
                answerer=answerer,
            )
            row["slot_inference"] = inference.to_dict()
            row["oracle_slot_for_audit"] = case.requested_slot
            row["inferred_slot_correct"] = (
                inference.requested_slots[0] == case.requested_slot
            )
            rows.append(row)

        model_results.append(
            {
                "model": model,
                "profile_dose": dose,
                "aggregate": aggregate_model_rows(rows),
                "automated_rows": rows,
                "blocked_for_clarification": blocked,
            }
        )

    automated = sum(len(row["automated_rows"]) for row in model_results)
    blocked = sum(len(row["blocked_for_clarification"]) for row in model_results)
    out = {
        "lab": "inferred_slot_bounded_fetch",
        "profile_sha256": FROZEN_PROFILE_SHA256,
        "case_count": len(cases),
        "aggregate": {
            "total_model_cases": len(model_results) * len(cases),
            "automated_cases": automated,
            "blocked_for_clarification": blocked,
            "confidently_wrong_slots": sum(
                not item["inferred_slot_correct"]
                for row in model_results
                for item in row["automated_rows"]
            ),
            "automated_semantic": sum(
                row["aggregate"]["semantic"] for row in model_results
            ),
            "automated_contract": sum(
                row["aggregate"]["contract"] for row in model_results
            ),
            "automated_severe": sum(
                row["aggregate"]["severe_failures"] for row in model_results
            ),
        },
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"inferred_bounded_fetch_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nInferred-Slot Bounded Fetch")
    print("=" * 80)
    for row in out["model_results"]:
        agg = row["aggregate"]
        print(
            f"{row['model']:<24} automated={len(row['automated_rows'])}/6 "
            f"contract={agg['contract']}/{agg['case_count']} "
            f"clarify={len(row['blocked_for_clarification'])}"
        )
    agg = out["aggregate"]
    print(
        f"\nAutomated {agg['automated_cases']}/{agg['total_model_cases']} | "
        f"contract {agg['automated_contract']}/{agg['automated_cases']} | "
        f"wrong slots {agg['confidently_wrong_slots']} | "
        f"clarifications {agg['blocked_for_clarification']}"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(timeout=args.timeout, write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

