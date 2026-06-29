"""CLI wrapper for Aether Local Router v0.

This is intentionally a thin prototype: it routes arbitrary prompts through the
current local policy without integrating into the main Aether runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.local_router_eval import (
    PROFILE_BUILDERS,
    classify_request,
    route_for_task,
    run_route,
)
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import SpiralCase, call_ollama

TRACE_DIR = OUT_DIR / "traces"


def build_case(
    query: str,
    *,
    task_type: str | None = None,
    context: str = "",
    anchors: tuple[str, ...] = (),
    concepts: tuple[str, ...] = (),
) -> SpiralCase:
    inferred_task = task_type or classify_request(query)
    default_anchors, default_concepts, forbidden = _defaults_for_task(inferred_task)
    evidence_anchors = anchors or default_anchors
    required_concepts = concepts or default_concepts
    context_lines = [line.strip() for line in context.splitlines() if line.strip()]
    raw_memories = tuple(context_lines) or (
        "No external memory context was supplied. Answer only from the user prompt and the router contract.",
    )
    spine = {
        "task_type": inferred_task,
        "user_request": query,
        "router_meaning": "AI request router for local model selection, scaffold selection, verifier checks, and repair. It is not a network router.",
        "project_terms": _project_terms_for_task(inferred_task),
        "supplied_context": context_lines,
        "evidence_anchors": list(evidence_anchors),
        "required_concepts": list(required_concepts),
        "disallowed_inferences": list(forbidden),
        "disallowed_topic_drift": ["network router", "packet routing", "secure file transfer", "network performance"],
        "measurement_policy": "Do not invent numeric performance percentages. Only claim measurable directions unless a metric is supplied in context.",
        "output_scaffold": _output_scaffold_for_task(inferred_task),
    }
    return SpiralCase(
        name=f"cli_{inferred_task}",
        query=query,
        raw_memories=raw_memories,
        spine=spine,
        expected_receipts=evidence_anchors,
        required_concepts=required_concepts,
        forbidden_claims=forbidden,
        min_words=80,
    )


def run_cli_request(
    query: str,
    *,
    task_type: str | None = None,
    context: str = "",
    anchors: tuple[str, ...] = (),
    concepts: tuple[str, ...] = (),
    timeout: int = 300,
    write_result: bool = True,
) -> dict[str, Any]:
    case = build_case(
        query,
        task_type=task_type,
        context=context,
        anchors=anchors,
        concepts=concepts,
    )
    result = run_route(case, timeout=timeout, runner=call_ollama)
    trace = build_trace(case, result, source="local_router_cli")
    trace_judgment = judge_trace(trace, result["judgment"])
    out = {
        "lab": "local_router_cli",
        "case": case.name,
        "query": query,
        "route": result["route"],
        "answer": result["answer"],
        "judgment": result["judgment"],
        "trace": trace,
        "trace_judgment": trace_judgment,
        "repaired": result["repaired"],
        "fallback_used": result["fallback_used"],
        "context_supplied": bool(context.strip()),
    }
    if write_result:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        run_id = int(time.time())
        path = OUT_DIR / f"local_router_cli_{run_id}.json"
        trace_path = TRACE_DIR / f"local_router_trace_{run_id}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
        out["trace_path"] = str(trace_path)
    return out


def build_trace(case: SpiralCase, result: dict[str, Any], *, source: str) -> dict[str, Any]:
    route = result["route"]
    judgment = result["judgment"]
    verifier_flags = {
        "passed": judgment["passed"],
        "truncated": judgment["truncated"],
        "leakage_hits": judgment["leakage_hits"],
        "weirdness_hits": judgment["weirdness_hits"],
        "forbidden_hits": judgment["forbidden_hits"],
        "receipt_hits": judgment["receipt_hits"],
        "concept_hits": judgment["concept_hits"],
    }
    learning_candidates = _learning_candidates(case, judgment, result)
    return {
        "trace_schema": "aether.local_router.trace.v0",
        "turn_id": f"{source}:{case.name}:{int(time.time())}",
        "conversation_id": source,
        "timestamp": int(time.time()),
        "source": source,
        "user_request_summary": _one_line(case.query, 240),
        "task_type": route["task_type"],
        "route_selected": route,
        "model_selected": route["model"],
        "scaffold_profile": route["profile"],
        "retrieved_memory_ids": [],
        "retrieved_chat_ids": [],
        "mirus_packet_summary": {
            "task_type": case.spine.get("task_type"),
            "supplied_context_count": len(case.spine.get("supplied_context") or []),
            "evidence_anchor_count": len(case.expected_receipts),
            "required_concept_count": len(case.required_concepts),
            "disallowed_inference_count": len(case.forbidden_claims),
            "output_scaffold": case.spine.get("output_scaffold", []),
        },
        "evidence_anchors": list(case.expected_receipts),
        "allowed_inferences": list(case.spine.get("allowed_inferences") or []),
        "disallowed_inferences": list(case.forbidden_claims),
        "draft_quality_score": judgment["score"],
        "contract_score": judgment["contract_score"],
        "usefulness_score": judgment["usefulness_score"],
        "verifier_flags": verifier_flags,
        "repair_attempts": 1 if result["repaired"] else 0,
        "fallback_used": result["fallback_used"],
        "final_confidence": _confidence_for_score(judgment["score"], judgment["passed"]),
        "contradiction_notes": _contradiction_notes(judgment),
        "learning_candidates": learning_candidates,
        "promotion_status": "pending_review" if learning_candidates else "none",
        "raw_chain_of_thought_stored": False,
    }


def judge_trace(trace: dict[str, Any], answer_judgment: dict[str, Any] | None = None) -> dict[str, Any]:
    required = (
        "trace_schema",
        "turn_id",
        "conversation_id",
        "timestamp",
        "user_request_summary",
        "task_type",
        "route_selected",
        "model_selected",
        "scaffold_profile",
        "mirus_packet_summary",
        "evidence_anchors",
        "disallowed_inferences",
        "draft_quality_score",
        "verifier_flags",
        "repair_attempts",
        "fallback_used",
        "final_confidence",
        "contradiction_notes",
        "learning_candidates",
        "promotion_status",
        "raw_chain_of_thought_stored",
    )
    missing = [field for field in required if field not in trace]
    route = trace.get("route_selected") or {}
    route_consistent = (
        bool(route)
        and route.get("task_type") == trace.get("task_type")
        and route.get("model") == trace.get("model_selected")
        and route.get("profile") == trace.get("scaffold_profile")
    )
    verifier_flags = trace.get("verifier_flags") or {}
    verifier_present = all(
        key in verifier_flags
        for key in ("passed", "truncated", "leakage_hits", "weirdness_hits", "forbidden_hits", "receipt_hits", "concept_hits")
    )
    no_raw_cot = trace.get("raw_chain_of_thought_stored") is False
    has_learning_when_failed = True
    if answer_judgment and not answer_judgment.get("passed"):
        has_learning_when_failed = bool(trace.get("learning_candidates"))
    score = round(
        (0.35 if not missing else max(0.0, 0.35 - (0.03 * len(missing))))
        + (0.2 if route_consistent else 0.0)
        + (0.2 if verifier_present else 0.0)
        + (0.15 if no_raw_cot else 0.0)
        + (0.1 if has_learning_when_failed else 0.0),
        3,
    )
    return {
        "passed": score >= 0.8 and no_raw_cot and not missing,
        "score": score,
        "missing_fields": missing,
        "route_consistent": route_consistent,
        "verifier_present": verifier_present,
        "no_raw_chain_of_thought": no_raw_cot,
        "has_learning_when_failed": has_learning_when_failed,
    }


def print_cli_report(out: dict[str, Any]) -> None:
    route = out["route"]
    judgment = out["judgment"]
    trace_judgment = out["trace_judgment"]
    print("\nAether Local Router CLI")
    print("=" * 80)
    print(f"task_type: {route['task_type']}")
    print(f"model: {route['model']}")
    print(f"profile: {route['profile']}")
    print(f"passed: {judgment['passed']}")
    print(
        f"score: {judgment['score']:.3f} "
        f"(contract {judgment['contract_score']:.3f}, useful {judgment['usefulness_score']:.3f})"
    )
    print(f"repaired: {out['repaired']}")
    print(f"fallback_used: {out['fallback_used']}")
    print(f"trace_score: {trace_judgment['score']:.3f} passed={trace_judgment['passed']}")
    print(f"hard_flags: trunc={judgment['truncated']} leak={judgment['leakage_hits']} weird={judgment['weirdness_hits']} forbidden={judgment['forbidden_hits']}")
    if "result_path" in out:
        print(f"result_path: {out['result_path']}")
    if "trace_path" in out:
        print(f"trace_path: {out['trace_path']}")
    print("\nanswer:\n")
    print(out["answer"])


def _defaults_for_task(task_type: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if task_type == "grant_business":
        return (
            ("local", "CRT", "Aether"),
            ("measurable", "low-cost", "business", "verifier", "AI request router"),
            ("guaranteed", "frontier", "medical", "autonomous truth", "network router"),
        )
    if task_type == "architecture_synthesis":
        return (
            ("Mirus", "Holden", "SSE", "CRT"),
            ("mechanism", "spine", "verifier", "overclaim"),
            ("conscious", "frontier-level", "globally smarter", "proof"),
        )
    if task_type == "code_reasoning":
        return (
            ("code", "test", "risk"),
            ("implementation", "verification", "next useful move"),
            ("guaranteed", "production-ready"),
        )
    if task_type == "exact_memory":
        return (
            ("current", "evidence"),
            ("answer", "limits"),
            ("guaranteed", "certain without evidence"),
        )
    return (
        ("receipts", "evidence"),
        ("pattern", "limits", "next useful move"),
        ("fixed", "cured", "guaranteed", "done"),
    )


def _output_scaffold_for_task(task_type: str) -> list[str]:
    if task_type == "grant_business":
        return ["need", "low-cost assets", "measurable claim", "business fit", "limits"]
    if task_type == "architecture_synthesis":
        return ["mechanism", "what works", "what to avoid", "verifier", "limits"]
    if task_type == "code_reasoning":
        return ["problem", "implementation", "risks", "verification", "next useful move"]
    return ["receipts", "pattern", "limits", "next useful move"]


def _project_terms_for_task(task_type: str) -> dict[str, str]:
    if task_type == "architecture_synthesis":
        return {
            "Mirus": "belief-state and evidence packet layer",
            "Holden": "speech/rendering layer downstream of belief",
            "SSE": "Semantic String Engine / semantic spine",
            "CRT": "Contradiction-resilient trust / contradiction and overclaim governance",
        }
    if task_type == "grant_business":
        return {
            "AI request router": "local policy for model selection, scaffold selection, verifier checks, and repair",
            "CRT/Aether": "local reliability scaffold, not a network router",
        }
    return {}


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _one_line(text: str, limit: int) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def _confidence_for_score(score: float, passed: bool) -> str:
    if passed and score >= 0.8:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def _contradiction_notes(judgment: dict[str, Any]) -> list[str]:
    notes = []
    if judgment["forbidden_hits"]:
        notes.append(f"Forbidden or overclaim language detected: {', '.join(judgment['forbidden_hits'])}.")
    if judgment["weirdness_hits"]:
        notes.append(f"Drift or weirdness detected: {', '.join(judgment['weirdness_hits'])}.")
    if judgment["leakage_hits"]:
        notes.append(f"Process or role leakage detected: {', '.join(judgment['leakage_hits'])}.")
    if judgment["truncated"]:
        notes.append("Answer appears truncated.")
    return notes or ["No contradiction or drift flags were raised by the verifier."]


def _learning_candidates(case: SpiralCase, judgment: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    if not judgment["passed"]:
        candidates.append(
            {
                "kind": "router_failure_pattern",
                "summary": f"{case.name} failed verifier with score {judgment['score']:.3f}.",
                "evidence": {
                    "forbidden_hits": judgment["forbidden_hits"],
                    "weirdness_hits": judgment["weirdness_hits"],
                    "leakage_hits": judgment["leakage_hits"],
                    "truncated": judgment["truncated"],
                },
                "recommended_action": "Review prompt profile, evidence anchors, and repair policy before promotion.",
                "promotion_status": "pending_review",
            }
        )
    if result["repaired"]:
        candidates.append(
            {
                "kind": "repair_signal",
                "summary": f"{case.name} required a repair pass.",
                "evidence": {"route": result["route"], "final_score": judgment["score"]},
                "recommended_action": "Review whether the primary scaffold should be tightened.",
                "promotion_status": "pending_review",
            }
        )
    if result["fallback_used"]:
        candidates.append(
            {
                "kind": "fallback_signal",
                "summary": f"{case.name} improved after fallback routing.",
                "evidence": {"route": result["route"], "final_score": judgment["score"]},
                "recommended_action": "Review route policy for this task type.",
                "promotion_status": "pending_review",
            }
        )
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Route one prompt through Aether Local Router v0.")
    parser.add_argument("prompt", nargs="*", help="Prompt text. If omitted, stdin is used.")
    parser.add_argument("--task-type", choices=["exact_memory", "personal_synthesis", "architecture_synthesis", "grant_business", "code_reasoning"])
    parser.add_argument("--context", default="", help="Optional context text.")
    parser.add_argument("--context-file", type=Path, help="Optional file containing context text.")
    parser.add_argument("--anchors", default="", help="Comma-separated expected evidence anchors.")
    parser.add_argument("--concepts", default="", help="Comma-separated required concepts.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query = " ".join(args.prompt).strip() or sys.stdin.read().strip()
    if not query:
        raise SystemExit("No prompt supplied.")
    context = args.context
    if args.context_file:
        context = args.context_file.read_text(encoding="utf-8")
    out = run_cli_request(
        query,
        task_type=args.task_type,
        context=context,
        anchors=_parse_csv(args.anchors),
        concepts=_parse_csv(args.concepts),
        timeout=args.timeout,
        write_result=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_cli_report(out)


if __name__ == "__main__":
    main()
