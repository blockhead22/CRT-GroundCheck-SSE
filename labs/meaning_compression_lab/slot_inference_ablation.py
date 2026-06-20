"""Compare standalone slot inference against frozen declared-slot oracles."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from labs.meaning_compression_lab.interface_pivot_eval import question_contract
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.slot_request_inference import infer_slot_request
from labs.meaning_compression_lab.untouched_fetch_cases import (
    FetchCase,
    UNTOUCHED_FETCH_CASES,
)


def score_case(case: FetchCase) -> dict[str, Any]:
    available_slots = sorted(
        {
            memory.slot
            for memory in case.scenario.memories
            if memory.slot
        }
    )
    inference = infer_slot_request(case.probe.query, available_slots)
    expected_contract = question_contract(case.probe).kind
    inferred_slot = (
        inference.requested_slots[0]
        if inference.status == "resolved" and inference.requested_slots
        else None
    )
    return {
        "scenario": case.scenario.name,
        "query": case.probe.query,
        "available_slots": available_slots,
        "expected_slot": case.requested_slot,
        "expected_contract": expected_contract,
        "inference": inference.to_dict(),
        "slot_correct": inferred_slot == case.requested_slot,
        "contract_correct": inference.contract_kind == expected_contract,
        "confidently_wrong": (
            inference.status == "resolved"
            and inferred_slot != case.requested_slot
        ),
        "safe_abstention": inference.status in {"ambiguous", "unknown"},
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    return {
        "case_count": count,
        "resolved_correct": sum(
            row["inference"]["status"] == "resolved" and row["slot_correct"]
            for row in rows
        ),
        "confidently_wrong": sum(row["confidently_wrong"] for row in rows),
        "safe_abstentions": sum(row["safe_abstention"] for row in rows),
        "contract_correct": sum(row["contract_correct"] for row in rows),
    }


def run(
    *,
    cases: tuple[FetchCase, ...] = UNTOUCHED_FETCH_CASES,
    write_results: bool = True,
) -> dict[str, Any]:
    rows = [score_case(case) for case in cases]
    out = {
        "lab": "holden_slot_inference_ablation",
        "aggregate": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"slot_inference_ablation_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nHolden Slot-Inference Ablation")
    print("=" * 80)
    for row in out["scenarios"]:
        inference = row["inference"]
        inferred = (
            inference["requested_slots"][0]
            if inference["requested_slots"]
            else "-"
        )
        print(
            f"{row['scenario']:<38} "
            f"{inference['status']:<10} "
            f"{inferred:<40} "
            f"expected={row['expected_slot']}"
        )
    agg = out["aggregate"]
    print(
        f"\nResolved correctly: {agg['resolved_correct']}/{agg['case_count']} | "
        f"abstained: {agg['safe_abstentions']} | "
        f"confidently wrong: {agg['confidently_wrong']} | "
        f"contract: {agg['contract_correct']}/{agg['case_count']}"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

