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
    out = {
        "lab": "local_router_cli",
        "case": case.name,
        "query": query,
        "route": result["route"],
        "answer": result["answer"],
        "judgment": result["judgment"],
        "repaired": result["repaired"],
        "fallback_used": result["fallback_used"],
        "context_supplied": bool(context.strip()),
    }
    if write_result:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"local_router_cli_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_cli_report(out: dict[str, Any]) -> None:
    route = out["route"]
    judgment = out["judgment"]
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
    print(f"hard_flags: trunc={judgment['truncated']} leak={judgment['leakage_hits']} weird={judgment['weirdness_hits']} forbidden={judgment['forbidden_hits']}")
    if "result_path" in out:
        print(f"result_path: {out['result_path']}")
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
