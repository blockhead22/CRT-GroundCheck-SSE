"""Aether Local Router v0 eval.

This turns the scaffold experiments into a small routing policy: classify the
request, choose a local model and prompt profile, run the stricter verifier, and
repair once when needed.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from labs.meaning_compression_lab.attention_profile_eval import (
    CASES_WITH_GRANT,
    PROFILE_BUILDERS,
)
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import (
    SpiralCase,
    call_ollama,
    judge_answer,
    repair_prompt,
)


CLAIM = (
    "A local Aether router should improve reliability by selecting a model and "
    "scaffold profile from task type, then accepting only verifier-passing output."
)

DEFAULT_EXECUTOR = "qwen2.5:7b-instruct"
SYNTHESIS_DRAFT_MODEL = "qwen3:14b"
CODER_MODEL = "qwen2.5-coder:14b"

Runner = Callable[[str, str, int], str]


@dataclass(frozen=True)
class RouteDecision:
    task_type: str
    model: str
    profile: str
    reason: str
    fallback_model: str | None = None
    fallback_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "model": self.model,
            "profile": self.profile,
            "reason": self.reason,
            "fallback_model": self.fallback_model,
            "fallback_profile": self.fallback_profile,
        }


def classify_request(case_or_query: SpiralCase | str) -> str:
    query = case_or_query.query if isinstance(case_or_query, SpiralCase) else case_or_query
    name = case_or_query.name if isinstance(case_or_query, SpiralCase) else ""
    text = f"{name} {query}".lower()

    if "grant" in text or "business" in text or "r&d" in text:
        return "grant_business"
    if "code" in text or "implementation" in text or "debug" in text:
        return "code_reasoning"
    if "what's my" in text or "where do i" in text or "current" in text:
        return "exact_memory"
    if "mechanism" in text or "architecture" in text or "local model" in text:
        return "architecture_synthesis"
    return "personal_synthesis"


def route_for_task(task_type: str) -> RouteDecision:
    if task_type == "exact_memory":
        return RouteDecision(
            task_type=task_type,
            model=DEFAULT_EXECUTOR,
            profile="semantic_spine",
            reason="Strict current-state answers need the steadier governed executor.",
        )
    if task_type == "grant_business":
        return RouteDecision(
            task_type=task_type,
            model=DEFAULT_EXECUTOR,
            profile="section_lock",
            reason="Grant/business framing benefits from compact sections and measurable limits.",
            fallback_model=DEFAULT_EXECUTOR,
            fallback_profile="semantic_spine",
        )
    if task_type == "code_reasoning":
        return RouteDecision(
            task_type=task_type,
            model=CODER_MODEL,
            profile="section_lock",
            reason="Code tasks should start with the installed coder model and explicit structure.",
            fallback_model=DEFAULT_EXECUTOR,
            fallback_profile="section_lock",
        )
    if task_type == "architecture_synthesis":
        return RouteDecision(
            task_type=task_type,
            model=DEFAULT_EXECUTOR,
            profile="semantic_spine",
            reason="Architecture synthesis needs mechanisms and overclaim gates more than persona.",
            fallback_model=DEFAULT_EXECUTOR,
            fallback_profile="section_lock",
        )
    return RouteDecision(
        task_type=task_type,
        model=DEFAULT_EXECUTOR,
        profile="section_lock",
        reason="Personal synthesis currently works best with explicit receipts/pattern/limits sections.",
        fallback_model=DEFAULT_EXECUTOR,
        fallback_profile="semantic_spine",
    )


def run_route(
    case: SpiralCase,
    *,
    timeout: int,
    runner: Runner,
) -> dict[str, Any]:
    task_type = classify_request(case)
    decision = route_for_task(task_type)
    answer, judgment, repaired = _run_once(
        case,
        model=decision.model,
        profile=decision.profile,
        timeout=timeout,
        runner=runner,
    )
    fallback_used = False
    fallback_answer = None
    fallback_judgment = None

    if not judgment["passed"] and decision.fallback_model and decision.fallback_profile:
        fallback_answer, fallback_judgment, fallback_repaired = _run_once(
            case,
            model=decision.fallback_model,
            profile=decision.fallback_profile,
            timeout=timeout,
            runner=runner,
        )
        if fallback_judgment["passed"] or fallback_judgment["score"] > judgment["score"]:
            answer = fallback_answer
            judgment = fallback_judgment
            repaired = fallback_repaired
            fallback_used = True

    return {
        "case": case.name,
        "query": case.query,
        "route": decision.to_dict(),
        "answer": answer,
        "judgment": judgment,
        "repaired": repaired,
        "fallback_used": fallback_used,
        "fallback_answer": fallback_answer,
        "fallback_judgment": fallback_judgment,
    }


def run_router_eval(
    *,
    timeout: int = 300,
    write_results: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    run_model = runner or call_ollama
    rows = [run_route(case, timeout=timeout, runner=run_model) for case in CASES_WITH_GRANT]
    out = {
        "lab": "local_router_eval",
        "claim": CLAIM,
        "case_count": len(rows),
        "aggregate": {
            "pass_count": sum(1 for row in rows if row["judgment"]["passed"]),
            "avg_score": round(sum(row["judgment"]["score"] for row in rows) / len(rows), 3),
            "avg_contract_score": round(sum(row["judgment"]["contract_score"] for row in rows) / len(rows), 3),
            "avg_usefulness_score": round(sum(row["judgment"]["usefulness_score"] for row in rows) / len(rows), 3),
            "fallback_count": sum(1 for row in rows if row["fallback_used"]),
            "repair_count": sum(1 for row in rows if row["repaired"]),
        },
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"local_router_eval_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    aggregate = out["aggregate"]
    print("\nAether Local Router Eval")
    print("=" * 80)
    print(out["claim"])
    print(
        f"Pass: {aggregate['pass_count']}/{out['case_count']} | "
        f"avg score {aggregate['avg_score']:.3f} | "
        f"contract {aggregate['avg_contract_score']:.3f} | "
        f"useful {aggregate['avg_usefulness_score']:.3f} | "
        f"repairs {aggregate['repair_count']} | fallbacks {aggregate['fallback_count']}"
    )
    for row in out["rows"]:
        route = row["route"]
        judgment = row["judgment"]
        print("-" * 80)
        print(
            f"{row['case']}: {route['task_type']} -> {route['model']} / {route['profile']} "
            f"pass={judgment['passed']} score={judgment['score']:.3f} "
            f"repaired={row['repaired']} fallback={row['fallback_used']}"
        )
        print(
            f"  receipts={judgment['receipt_hits']} concepts={judgment['concept_hits']} "
            f"hard=trunc:{judgment['truncated']} leak:{judgment['leakage_hits']} "
            f"weird:{judgment['weirdness_hits']} forbidden:{judgment['forbidden_hits']}"
        )
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def _run_once(
    case: SpiralCase,
    *,
    model: str,
    profile: str,
    timeout: int,
    runner: Runner,
) -> tuple[str, dict[str, Any], bool]:
    prompt = PROFILE_BUILDERS[profile](case)
    answer = runner(prompt, model, timeout)
    judgment = judge_answer(answer, case)
    repaired = False
    if profile != "raw" and not judgment["passed"]:
        answer = runner(repair_prompt(case, answer, judgment), model, timeout)
        judgment = judge_answer(answer, case)
        repaired = True
    return answer, judgment, repaired


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aether local router eval.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run_router_eval(timeout=args.timeout, write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
