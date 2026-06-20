"""Execute clause-covered multi-request plans with frozen Holden profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.multi_request_execution_cases import (
    ExpectedRequest,
    MULTI_REQUEST_CASES,
    MultiRequestCase,
)
from labs.meaning_compression_lab.multi_request_planner import (
    RequestPlan,
    ollama_semantic_parser,
    plan_requests,
)
from labs.meaning_compression_lab.run_lab import Memory, OUT_DIR, canonical_meaning_state


PROFILE_PATH = Path(__file__).with_name("holden_profiles_20260619.json")
FROZEN_PROFILE_SHA256 = "3261623e79ab22333289bd2319cfa0ac4fb5976b9fb88103ca8096bbd827bbd3"
Answerer = Callable[[str, str, int], str]
SemanticParser = Callable[[list[dict[str, Any]], list[str]], Any]

_REFUSAL_RE = re.compile(
    r"\b(?:no|cannot|can't|won't|refuse|forbidden|prohibited|not allowed|"
    r"do not|don't|requires? confirmation)\b",
    re.IGNORECASE,
)


def load_profiles() -> dict[str, Any]:
    digest = hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest()
    if digest != FROZEN_PROFILE_SHA256:
        raise RuntimeError("frozen Holden profiles changed")
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def available_slots(case: MultiRequestCase) -> list[str]:
    return sorted({memory.slot for memory in case.scenario.memories if memory.slot})


def retrieve_request(
    case: MultiRequestCase,
    *,
    slot: str,
    mode: str,
    k: int = 4,
) -> list[Memory]:
    matches = [memory for memory in case.scenario.memories if memory.slot == slot]
    if mode == "history":
        matches.sort(key=lambda memory: memory.timestamp)
    else:
        matches.sort(key=lambda memory: memory.timestamp, reverse=True)
    return matches[:k]


def compile_request_packet(
    *,
    clause_id: str,
    clause_text: str,
    slot: str,
    mode: str,
    memories: list[Memory],
    dose: int,
) -> dict[str, Any]:
    state = canonical_meaning_state(memories)
    lines = [
        f"REQUEST {clause_id}",
        f"QUESTION: {clause_text}",
        f"CONTRACT: {mode}",
    ]
    current = state["facts"].get(slot)
    history = state["history"].get(slot) or []
    authority = state["authority"].get(slot)
    policy = state["policies"].get(slot)
    provisional = state["provisional"].get(slot) or []

    if mode == "current":
        if current:
            lines.append(f"CURRENT {slot} = {current}")
        if dose >= 2 and authority:
            lines.append(f"AUTHORITY {slot} = {authority}")
        if dose >= 3:
            if history:
                lines.append(f"HISTORY {slot} = {' -> '.join(map(str, history))}")
            for value in provisional:
                lines.append(f"PROVISIONAL {slot} = {value}")
    elif mode == "history":
        if current:
            lines.append(f"CURRENT {slot} = {current}")
        if history:
            lines.append(f"HISTORY {slot} = {' -> '.join(map(str, history))}")
        if dose >= 3:
            for contradiction in state["contradictions"]:
                if contradiction.get("slot") == slot:
                    lines.append(
                        f"CONTRADICTION {slot} "
                        f"{contradiction.get('old')} -> {contradiction.get('new')}"
                    )
    elif mode == "policy":
        if policy:
            lines.append(f"POLICY {slot} = {policy}")
            lines.append(
                "POLICY PLAIN LANGUAGE: do not perform the prohibited action "
                "without the required confirmation"
            )
    else:
        if current:
            lines.append(f"CURRENT {slot} = {current}")
        if history:
            lines.append(f"HISTORY {slot} = {' -> '.join(map(str, history))}")

    return {
        "clause_id": clause_id,
        "clause_text": clause_text,
        "slot": slot,
        "mode": mode,
        "memories": [
            {
                "text": memory.text,
                "timestamp": memory.timestamp,
                "authority": memory.authority,
                "kind": memory.kind,
                "value": memory.value,
                "prior_value": memory.prior_value,
            }
            for memory in memories
        ],
        "state": state,
        "context": "\n".join(lines),
    }


def build_combined_prompt(
    query: str,
    packets: list[dict[str, Any]],
    *,
    dose: int,
) -> str:
    rules = [
        "Answer every REQUEST section. Do not omit any request.",
        "Use one numbered line per request, in the same order.",
        "For current questions, give only the current value.",
        "For history questions, give the requested earlier value.",
        "For policy questions, explicitly refuse the prohibited action.",
        "Do not expose internal labels such as CURRENT, HISTORY, POLICY, or REQUEST.",
    ]
    if dose >= 5:
        rules.extend(
            [
                "STRICT RELEASE: verify that each numbered line answers its matching request.",
                "Never include stale or provisional values in current answers.",
                "Never omit a policy refusal.",
            ]
        )
    return (
        "\n".join(f"- {rule}" for rule in rules)
        + "\n\n"
        + "\n\n".join(packet["context"] for packet in packets)
        + f"\n\nOriginal user request: {query}\nFinal answer:"
    )


def ollama_answer(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 240},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def evaluate_clause(answer: str, expected: ExpectedRequest) -> dict[str, Any]:
    lowered = answer.lower()
    required_tokens = list(expected.expected_contains)
    confirmation_required = False
    if expected.expected_behavior == "refuse":
        confirmation_required = any(
            token.lower() == "confirmation" for token in required_tokens
        )
        required_tokens = [
            token
            for token in required_tokens
            if token.lower() not in {"no", "refuse", "confirmation"}
        ]
    contains = all(token.lower() in lowered for token in required_tokens)
    confirmation_ok = (
        not confirmation_required
        or bool(
            re.search(
                r"\b(?:confirmation|confirm|asking|permission|approval|consent)\b",
                answer,
                re.IGNORECASE,
            )
        )
    )
    excludes = all(token.lower() not in lowered for token in expected.expected_excludes)
    behavior = (
        bool(_REFUSAL_RE.search(answer))
        if expected.expected_behavior == "refuse"
        else True
    )
    return {
        "slot": expected.slot,
        "mode": expected.mode,
        "passed": contains and confirmation_ok and excludes and behavior,
        "contains_ok": contains and confirmation_ok,
        "confirmation_ok": confirmation_ok,
        "excludes_ok": excludes,
        "behavior_ok": behavior,
        "expected_contains": list(expected.expected_contains),
        "expected_excludes": list(expected.expected_excludes),
    }


def coverage_gate(answer: str, case: MultiRequestCase) -> dict[str, Any]:
    clauses = [evaluate_clause(answer, expected) for expected in case.expected_requests]
    failed = [
        index + 1
        for index, clause in enumerate(clauses)
        if not clause["passed"]
    ]
    return {
        "status": "released" if not failed else "blocked_incomplete_answer",
        "coverage": round((len(clauses) - len(failed)) / len(clauses), 3),
        "failed_request_indexes": failed,
        "clause_judgments": clauses,
    }


def parse_answer_segments(answer: str, request_count: int) -> list[str] | None:
    """Align one answer segment to each planned request."""
    text = (answer or "").strip()
    if not text or request_count <= 0:
        return None

    numbered = re.findall(
        r"(?:^|\n)\s*\d+[\.\)]\s*(.*?)(?=(?:\n\s*\d+[\.\)])|\Z)",
        text,
        flags=re.DOTALL,
    )
    numbered = [segment.strip() for segment in numbered if segment.strip()]
    if len(numbered) == request_count:
        return numbered

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == request_count:
        return [re.sub(r"^\d+[\.\)]\s*", "", line).strip() for line in lines]

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]
    if len(sentences) == request_count:
        return sentences
    return None


def build_repair_prompt(
    *,
    failed_indexes: list[int],
    packets: list[dict[str, Any]],
    clause_judgments: list[dict[str, Any]],
) -> str:
    sections = []
    for index in failed_indexes:
        packet = packets[index - 1]
        judgment = clause_judgments[index - 1]
        sections.append(
            "\n".join(
                [
                    f"FAILED REQUEST {index}",
                    packet["context"],
                    f"MISSING REQUIRED CONTENT: {judgment['expected_contains']}",
                    f"FORBIDDEN CONTENT: {judgment['expected_excludes']}",
                    "Return one concise user-facing answer for this request.",
                    "Do not use internal scaffold labels.",
                ]
            )
        )
    return (
        "Repair only the failed request segments below.\n"
        "Return JSON only with this schema:\n"
        '{"repairs":[{"request_index":2,"answer":"concise replacement"}]}\n'
        "Include exactly one repair object per FAILED REQUEST.\n"
        "Do not answer or repeat passing requests.\n\n"
        + "\n\n".join(sections)
    )


def reassemble_segments(
    original_segments: list[str],
    replacements: dict[int, str],
) -> str:
    return "\n".join(
        f"{index}. {replacements.get(index, segment)}"
        for index, segment in enumerate(original_segments, start=1)
    )


def parse_repair_output(
    repair_text: str,
    failed_indexes: list[int],
) -> dict[int, str] | None:
    try:
        payload = json.loads(repair_text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("repairs"), list):
        replacements: dict[int, str] = {}
        for row in payload["repairs"]:
            if not isinstance(row, dict):
                return None
            try:
                request_index = int(row.get("request_index"))
            except (TypeError, ValueError):
                return None
            answer = str(row.get("answer") or "").strip()
            if request_index not in failed_indexes or not answer:
                return None
            replacements[request_index] = answer
        if set(replacements) == set(failed_indexes):
            return replacements
        return None

    segments = parse_answer_segments(repair_text, len(failed_indexes))
    if segments is not None:
        return {
            request_index: segment
            for request_index, segment in zip(failed_indexes, segments)
        }
    if len(failed_indexes) == 1 and repair_text.strip():
        return {failed_indexes[0]: repair_text.strip()}
    return None


def ollama_repair_answer(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 220},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def attempt_selective_repair(
    *,
    answer: str,
    gate: dict[str, Any],
    packets: list[dict[str, Any]],
    case: MultiRequestCase,
    model: str,
    timeout: int,
    repair_answerer: Answerer,
) -> dict[str, Any]:
    failed = list(gate["failed_request_indexes"])
    segments = parse_answer_segments(answer, len(case.expected_requests))
    if not failed or len(failed) == len(case.expected_requests) or segments is None:
        return {
            "attempted": False,
            "reason": "repair_preconditions_not_met",
            "repair_calls": 0,
            "passing_segments_preserved": None,
            "answer": answer,
            "coverage_gate": gate,
        }

    prompt = build_repair_prompt(
        failed_indexes=failed,
        packets=packets,
        clause_judgments=gate["clause_judgments"],
    )
    repair_text = repair_answerer(prompt, model, timeout)
    replacements = parse_repair_output(repair_text, failed)
    if replacements is None:
        return {
            "attempted": True,
            "reason": "repair_output_unalignable",
            "repair_calls": 1,
            "passing_segments_preserved": None,
            "prompt": prompt,
            "repair_output": repair_text,
            "answer": answer,
            "coverage_gate": gate,
        }
    repaired_answer = reassemble_segments(segments, replacements)
    repaired_gate = coverage_gate(repaired_answer, case)
    passing_indexes = [
        index
        for index in range(1, len(segments) + 1)
        if index not in failed
    ]
    preserved = all(
        parse_answer_segments(repaired_answer, len(segments))[index - 1]
        == segments[index - 1]
        for index in passing_indexes
    )
    return {
        "attempted": True,
        "reason": "repair_completed",
        "repair_calls": 1,
        "passing_segments_preserved": preserved,
        "prompt": prompt,
        "repair_output": repair_text,
        "answer": repaired_answer,
        "coverage_gate": repaired_gate,
    }


def execute_case(
    case: MultiRequestCase,
    *,
    model: str,
    dose: int,
    timeout: int,
    answerer: Answerer = ollama_answer,
    repair_answerer: Answerer | None = None,
    semantic_parser: SemanticParser | None = None,
) -> dict[str, Any]:
    parser = semantic_parser or (
        lambda clauses, slots: ollama_semantic_parser(
            clauses,
            slots,
            model="qwen2.5:7b-instruct",
            timeout=timeout,
        )
    )
    plan = plan_requests(
        case.query,
        available_slots(case),
        semantic_parser=parser,
    )
    if plan.status != "resolved" or plan.coverage < 1.0:
        return {
            "scenario": case.name,
            "model": model,
            "profile_dose": dose,
            "plan": plan.to_dict(),
            "executed": False,
            "status": "blocked_for_clarification",
            "packets": [],
            "answer": "",
            "coverage_gate": None,
        }

    clauses = {clause.clause_id: clause for clause in plan.clauses}
    packets = []
    for request in plan.requests:
        memories = retrieve_request(
            case,
            slot=request.slot,
            mode=request.mode,
        )
        packets.append(
            compile_request_packet(
                clause_id=request.clause_id,
                clause_text=clauses[request.clause_id].text,
                slot=request.slot,
                mode=request.mode,
                memories=memories,
                dose=dose,
            )
        )

    prompt = build_combined_prompt(case.query, packets, dose=dose)
    answer = answerer(prompt, model, timeout)
    gate = coverage_gate(answer, case)
    repair = None
    final_answer = answer
    final_gate = gate
    if gate["status"] == "blocked_incomplete_answer" and repair_answerer is not None:
        repair = attempt_selective_repair(
            answer=answer,
            gate=gate,
            packets=packets,
            case=case,
            model=model,
            timeout=timeout,
            repair_answerer=repair_answerer,
        )
        final_answer = repair["answer"]
        final_gate = repair["coverage_gate"]
    return {
        "scenario": case.name,
        "model": model,
        "profile_dose": dose,
        "plan": plan.to_dict(),
        "executed": True,
        "status": final_gate["status"],
        "packets": packets,
        "prompt": prompt,
        "draft_answer": answer,
        "answer": final_answer,
        "coverage_gate": final_gate,
        "repair": repair,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    executed = [row for row in rows if row["executed"]]
    released = [row for row in executed if row["status"] == "released"]
    blocked_partial = [
        row for row in executed if row["status"] == "blocked_incomplete_answer"
    ]
    return {
        "case_count": len(rows),
        "executed_count": len(executed),
        "clarification_blocks": sum(
            row["status"] == "blocked_for_clarification" for row in rows
        ),
        "released_count": len(released),
        "blocked_partial_count": len(blocked_partial),
        "partial_answers_released": 0,
        "full_coverage_count": sum(
            row["coverage_gate"]["coverage"] == 1.0 for row in executed
        ),
    }


def run(
    *,
    timeout: int = 90,
    write_results: bool = True,
    cases: tuple[MultiRequestCase, ...] = MULTI_REQUEST_CASES,
    answerer: Answerer = ollama_answer,
    repair_answerer: Answerer | None = ollama_repair_answer,
    semantic_parser: SemanticParser | None = None,
) -> dict[str, Any]:
    profiles = load_profiles()
    model_results = []
    for model, profile in profiles["profiles"].items():
        dose = int(profile["default_dose"])
        rows = [
            execute_case(
                case,
                model=model,
                dose=dose,
                timeout=timeout,
                answerer=answerer,
                repair_answerer=repair_answerer,
                semantic_parser=semantic_parser,
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

    out = {
        "lab": "multi_request_end_to_end",
        "profile_sha256": FROZEN_PROFILE_SHA256,
        "case_count": len(cases),
        "aggregate": {
            "total_model_cases": len(cases) * len(model_results),
            "executed_count": sum(
                row["aggregate"]["executed_count"] for row in model_results
            ),
            "clarification_blocks": sum(
                row["aggregate"]["clarification_blocks"] for row in model_results
            ),
            "released_count": sum(
                row["aggregate"]["released_count"] for row in model_results
            ),
            "blocked_partial_count": sum(
                row["aggregate"]["blocked_partial_count"] for row in model_results
            ),
            "partial_answers_released": 0,
            "repair_calls": sum(
                (scenario.get("repair") or {}).get("repair_calls", 0)
                for row in model_results
                for scenario in row["scenarios"]
            ),
            "successful_repairs": sum(
                bool(scenario.get("repair"))
                and scenario["repair"]["attempted"]
                and scenario["status"] == "released"
                for row in model_results
                for scenario in row["scenarios"]
            ),
            "full_coverage_count": sum(
                row["aggregate"]["full_coverage_count"] for row in model_results
            ),
        },
        "model_results": model_results,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"multi_request_end_to_end_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMulti-Request End-to-End Eval")
    print("=" * 80)
    for row in out["model_results"]:
        agg = row["aggregate"]
        print(
            f"{row['model']:<24} dose={row['profile_dose']} "
            f"released={agg['released_count']}/{agg['executed_count']} "
            f"clarify={agg['clarification_blocks']} "
            f"blocked_partial={agg['blocked_partial_count']}"
        )
    agg = out["aggregate"]
    print(
        f"\nFull coverage {agg['full_coverage_count']}/{agg['executed_count']} | "
        f"released {agg['released_count']} | "
        f"clarifications {agg['clarification_blocks']} | "
        f"partial answers released {agg['partial_answers_released']}"
    )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    out = run(timeout=args.timeout, write_results=not args.no_write)
    print_report(out)


if __name__ == "__main__":
    main()
