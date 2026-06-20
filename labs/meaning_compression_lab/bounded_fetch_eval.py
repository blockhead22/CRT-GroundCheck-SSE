"""Untouched validation of frozen Holden profiles with one bounded fetch."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.governance_dose_eval import (
    build_prompt,
    dose_context,
    ollama_answer,
    score_answer,
)
from labs.meaning_compression_lab.interface_pivot_eval import question_contract
from labs.meaning_compression_lab.run_lab import Memory, OUT_DIR, Scenario, canonical_meaning_state
from labs.meaning_compression_lab.scaffold_eval import build_meaning_scaffold
from labs.meaning_compression_lab.temporal_rag_eval import retrieve_records
from labs.meaning_compression_lab.untouched_fetch_cases import (
    FetchCase,
    UNTOUCHED_FETCH_CASES,
)


PROFILE_PATH = Path(__file__).with_name("holden_profiles_20260619.json")
FROZEN_PROFILE_SHA256 = "3261623e79ab22333289bd2319cfa0ac4fb5976b9fb88103ca8096bbd827bbd3"
Answerer = Callable[[str, str, int], str]


def load_frozen_profiles(path: Path = PROFILE_PATH) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != FROZEN_PROFILE_SHA256:
        raise RuntimeError(
            f"Holden profile artifact changed: expected {FROZEN_PROFILE_SHA256}, got {digest}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def records_to_memories(case: FetchCase, records: list[dict[str, Any]]) -> list[Memory]:
    return [
        next(
            memory
            for memory in case.scenario.memories
            if memory.text == row["text"] and memory.timestamp == row["timestamp"]
        )
        for row in records
    ]


def evidence_sufficiency(
    case: FetchCase,
    state: dict[str, Any],
) -> dict[str, Any]:
    contract = question_contract(case.probe)
    slot = case.requested_slot

    if contract.kind == "current":
        value = state["facts"].get(slot)
        authority = state["authority"].get(slot)
        sufficient = bool(value) and authority in {"confirmed", "locked"}
        reason = None if sufficient else "missing_confirmed_current_value"
    elif contract.kind == "history":
        history = state["history"].get(slot) or []
        contradictions = [
            row for row in state["contradictions"] if row.get("slot") == slot
        ]
        sufficient = len(history) >= 2 or bool(contradictions)
        reason = None if sufficient else "missing_history_pair"
    elif contract.kind == "policy" or case.probe.expected_behavior == "refuse":
        sufficient = state["policies"].get(slot) == "forbidden"
        reason = None if sufficient else "missing_locked_policy"
    else:
        sufficient = bool(state["facts"].get(slot))
        reason = None if sufficient else "missing_target_slot"

    return {
        "sufficient": sufficient,
        "requested_slots": [] if sufficient else [slot],
        "reason_code": reason,
    }


def fetch_requested_slot(
    case: FetchCase,
    slot: str,
    *,
    k: int = 4,
) -> list[dict[str, Any]]:
    matching = [
        memory
        for memory in case.scenario.memories
        if memory.slot == slot
    ]
    matching.sort(key=lambda memory: memory.timestamp, reverse=True)
    return [
        {
            "rank": index,
            "score": 1.0,
            "semantic_score": None,
            "lexical_score": None,
            "slot_bonus": 1.0,
            "recency_score": None,
            "retrieval_mode": "authorized_slot_fetch",
            "text": memory.text,
            "timestamp": memory.timestamp,
            "source": memory.channel,
            "kind": memory.kind,
            "authority": memory.authority,
            "slot": memory.slot,
            "value": memory.value,
            "prior_value": memory.prior_value,
        }
        for index, memory in enumerate(matching[:k], start=1)
    ]


def merge_records(
    initial: list[dict[str, Any]],
    fetched: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for row in [*initial, *fetched]:
        identity = (row["text"], row["timestamp"], row.get("slot"))
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(row)
    return merged


def score_case(
    case: FetchCase,
    *,
    model: str,
    dose: int,
    timeout: int,
    initial_k: int = 2,
    retrieval_mode: str = "hybrid",
    embedder: Callable | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    initial = retrieve_records(
        case.scenario,
        case.probe.query,
        k=initial_k,
        retrieval_mode=retrieval_mode,
        embedder=embedder,
    )
    initial_memories = records_to_memories(case, initial)
    initial_state = canonical_meaning_state(initial_memories)
    request = evidence_sufficiency(case, initial_state)

    fetched: list[dict[str, Any]] = []
    fetch_count = 0
    if not request["sufficient"]:
        fetch_count = 1
        fetched = fetch_requested_slot(case, request["requested_slots"][0])

    final_records = merge_records(initial, fetched)
    final_memories = records_to_memories(case, final_records)
    final_state = canonical_meaning_state(final_memories)
    final_check = evidence_sufficiency(case, final_state)

    if not final_check["sufficient"]:
        answer = "I do not have enough confirmed evidence to answer that."
        prompt = None
        context = None
        context_kind = None
    else:
        final_scenario = Scenario(
            case.scenario.name,
            case.scenario.purpose,
            final_memories,
            evidence="untouched_bounded_fetch",
        )
        scaffold = build_meaning_scaffold(final_scenario)
        context_kind, context = dose_context(
            dose=dose,
            records=final_records,
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
        "probe": case.probe.name,
        "model": model,
        "profile_dose": dose,
        "expected_fetch": case.expected_fetch,
        "initial_records": initial,
        "initial_state": initial_state,
        "evidence_request": {
            "status": "sufficient" if request["sufficient"] else "insufficient_evidence",
            **request,
        },
        "fetch_count": fetch_count,
        "fetched_records": fetched,
        "final_records": final_records,
        "final_state": final_state,
        "final_sufficiency": final_check,
        "context_kind": context_kind,
        "context": context,
        "prompt": prompt,
        "answer": answer,
        "judgment": score_answer(answer, case.probe),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    return {
        "case_count": count,
        "semantic": sum(row["judgment"]["semantic_passed"] for row in rows),
        "contract": sum(row["judgment"]["contract_passed"] for row in rows),
        "severe_failures": sum(row["judgment"]["severe_failure"] for row in rows),
        "correct_fetch_decisions": sum(
            (row["fetch_count"] == 1) == row["expected_fetch"] for row in rows
        ),
        "unnecessary_fetches": sum(
            row["fetch_count"] == 1 and not row["expected_fetch"] for row in rows
        ),
        "missed_fetches": sum(
            row["fetch_count"] == 0 and row["expected_fetch"] for row in rows
        ),
        "fetches_over_limit": sum(row["fetch_count"] > 1 for row in rows),
        "final_evidence_sufficient": sum(
            row["final_sufficiency"]["sufficient"] for row in rows
        ),
    }


def run(
    *,
    timeout: int = 90,
    initial_k: int = 2,
    retrieval_mode: str = "hybrid",
    write_results: bool = True,
    cases: tuple[FetchCase, ...] = UNTOUCHED_FETCH_CASES,
    embedder: Callable | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    profile_artifact = load_frozen_profiles()
    model_results = []
    for model, profile in profile_artifact["profiles"].items():
        dose = int(profile["default_dose"])
        rows = [
            score_case(
                case,
                model=model,
                dose=dose,
                timeout=timeout,
                initial_k=initial_k,
                retrieval_mode=retrieval_mode,
                embedder=embedder,
                answerer=answerer,
            )
            for case in cases
        ]
        model_results.append(
            {
                "model": model,
                "profile_dose": dose,
                "aggregate": aggregate(rows),
                "scenarios": rows,
            }
        )

    total = sum(row["aggregate"]["case_count"] for row in model_results)
    out = {
        "lab": "frozen_holden_bounded_fetch",
        "profile_sha256": FROZEN_PROFILE_SHA256,
        "initial_top_k": initial_k,
        "retrieval_mode": retrieval_mode,
        "case_count": len(cases),
        "aggregate": {
            "total_case_count": total,
            "semantic": sum(row["aggregate"]["semantic"] for row in model_results),
            "contract": sum(row["aggregate"]["contract"] for row in model_results),
            "severe_failures": sum(row["aggregate"]["severe_failures"] for row in model_results),
            "correct_fetch_decisions": sum(
                row["aggregate"]["correct_fetch_decisions"] for row in model_results
            ),
            "unnecessary_fetches": sum(
                row["aggregate"]["unnecessary_fetches"] for row in model_results
            ),
            "missed_fetches": sum(row["aggregate"]["missed_fetches"] for row in model_results),
            "fetches_over_limit": sum(
                row["aggregate"]["fetches_over_limit"] for row in model_results
            ),
            "final_evidence_sufficient": sum(
                row["aggregate"]["final_evidence_sufficient"] for row in model_results
            ),
            "models_perfect_contract": sum(
                row["aggregate"]["contract"] == row["aggregate"]["case_count"]
                for row in model_results
            ),
        },
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"bounded_fetch_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nFrozen Holden Bounded-Fetch Validation")
    print("=" * 80)
    print(f"{'model':<24} {'dose':>5} {'semantic':>10} {'contract':>10} {'fetch':>8}")
    print("-" * 66)
    for row in out["model_results"]:
        agg = row["aggregate"]
        print(
            f"{row['model']:<24} {row['profile_dose']:>5} "
            f"{agg['semantic']:>3}/{agg['case_count']:<6} "
            f"{agg['contract']:>3}/{agg['case_count']:<6} "
            f"{agg['correct_fetch_decisions']:>3}/{agg['case_count']:<4}"
        )
    agg = out["aggregate"]
    print(
        f"\nAggregate semantic {agg['semantic']}/{agg['total_case_count']} | "
        f"contract {agg['contract']}/{agg['total_case_count']} | "
        f"severe {agg['severe_failures']}"
    )
    print(
        f"Fetch decisions {agg['correct_fetch_decisions']}/{agg['total_case_count']} | "
        f"unnecessary {agg['unnecessary_fetches']} | missed {agg['missed_fetches']} | "
        f"over limit {agg['fetches_over_limit']}"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate frozen Holden profiles with one bounded fetch.")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--initial-top-k", type=int, default=2)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        timeout=args.timeout,
        initial_k=args.initial_top_k,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

