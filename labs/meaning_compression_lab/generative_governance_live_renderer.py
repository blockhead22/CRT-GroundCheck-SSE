"""Live-renderer comparison for Mirus trace-memory decisions.

This lab is still review-only. It can run with an injected deterministic
renderer for tests or with local Ollama for a small live smoke. The question is
whether a real renderer behaves better when Mirus trace memory decides the
handoff and supplies a bounded governance spine.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.generative_governance_render_compare import (
    RenderRow,
    evaluate_render,
)
from labs.meaning_compression_lab.generative_governance_spike import (
    GovernanceTrace,
    build_governance_trace,
)
from labs.meaning_compression_lab.generative_governance_trace_memory import (
    TraceMemoryCase,
    build_trace_memory_records,
    decide_from_trace_memory,
    holdout_cases,
)


Renderer = Callable[[str], str]


@dataclass(frozen=True)
class LiveRenderResult:
    mode: str
    answer: str
    evaluation: RenderRow
    model_called: bool
    prompt_kind: str
    repair_count: int = 0
    repair_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "answer": self.answer,
            "evaluation": self.evaluation.to_dict(),
            "model_called": self.model_called,
            "prompt_kind": self.prompt_kind,
            "repair_count": self.repair_count,
            "repair_notes": self.repair_notes,
        }


class OllamaRenderer:
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
        temperature: float = 0.2,
        num_predict: int = 260,
        disable_thinking: bool = False,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.num_predict = num_predict
        self.disable_thinking = disable_thinking

    def __call__(self, prompt: str) -> str:
        render_prompt = prompt
        if self.disable_thinking:
            render_prompt = (
                f"{prompt}\n\n/no_think\n"
                "Return only the final answer. Do not include a thinking or reasoning block."
            )
        payload = {
            "model": self.model,
            "prompt": render_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama renderer failed: {exc}") from exc
        return strip_reasoning_blocks(str(data.get("response") or ""))


def run_live_renderer_compare(
    renderer: Renderer,
    *,
    renderer_label: str = "injected",
    cases: tuple[TraceMemoryCase, ...] | None = None,
    max_cases: int | None = None,
    repair_attempts: int = 1,
) -> dict[str, Any]:
    selected_cases = cases or holdout_cases()
    if max_cases is not None:
        selected_cases = selected_cases[:max_cases]
    records = build_trace_memory_records()
    rows = []
    for case in selected_cases:
        trace = build_governance_trace(
            case.query,
            task_type=case.task_type,
            context=case.context,
            conflict_slots=case.conflict_slots,
        )
        decision = decide_from_trace_memory(trace, records)
        model_only_answer = renderer(_model_only_prompt(case))
        governed = _render_governed(
            case,
            trace,
            renderer,
            decision.decision,
            repair_attempts=repair_attempts,
        )
        model_only = LiveRenderResult(
            mode="model_only",
            answer=model_only_answer,
            evaluation=evaluate_render("model_only", model_only_answer, trace),
            model_called=True,
            prompt_kind="raw_user_prompt",
        )
        rows.append({
            "case_id": case.case_id,
            "expected_decision": case.expected_decision,
            "trace_memory_decision": decision.to_dict(),
            "passed": (
                governed.evaluation.passed
                and decision.decision == case.expected_decision
            ),
            "trace": trace.to_dict(),
            "renders": [model_only.to_dict(), governed.to_dict()],
        })
    return {
        "lab": "generative_governance_live_renderer",
        "created_at": int(time.time()),
        "renderer_label": renderer_label,
        "case_count": len(rows),
        "passed": all(row["passed"] for row in rows),
        "writes_performed": False,
        "memory_write_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "raw_chain_of_thought_stored": False,
        "rows": rows,
        "summary": _summary(rows),
    }


def expanded_holdout_cases() -> tuple[TraceMemoryCase, ...]:
    """A larger mixed pack for live renderer smoke tests.

    These are still hand-authored lab cases, not a blind benchmark. The point is
    to cover more nearby task shapes before spending a larger model/API budget.
    """

    return (
        TraceMemoryCase(
            case_id="expanded_personal_001_no_receipts_identity",
            query="What does all this say about who I am becoming?",
            task_type="personal_synthesis",
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_002_single_receipt_founder",
            query="Am I becoming the kind of founder who can pull this off?",
            task_type="personal_synthesis",
            context="One shop order shipped after a busy week.",
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_003_vague_receipt",
            query="Can you do one of those deep reads on where I am headed?",
            task_type="personal_synthesis",
            context="I have been thinking about maybe doing more creative business stuff someday.",
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_memory_001_store_platform_conflict",
            query="What store platform am I using right now?",
            task_type="exact_memory",
            conflict_slots=("business:store_platform",),
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_memory_002_current_job_conflict",
            query="Where do I currently work?",
            task_type="exact_memory",
            conflict_slots=("user:current_work",),
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_memory_003_license_conflict",
            query="Which FL Studio license did we confirm?",
            task_type="exact_memory",
            conflict_slots=("software:fl_studio_license",),
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_004_grounded_video_shop",
            query="What pattern is showing up across the video and shop work?",
            task_type="personal_synthesis",
            context=(
                "Road America edit shipped.\n"
                "Low-batch sticker order completed.\n"
                "Workbench trace review was updated."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_005_grounded_health_work",
            query="What can we safely say about my momentum lately?",
            task_type="personal_synthesis",
            context=(
                "12,730 steps were logged.\n"
                "A shop task was finished after a heavy week.\n"
                "The answer should avoid claiming I am fixed or done."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_006_grounded_garden_work",
            query="What do the small garden and work receipts point toward?",
            task_type="personal_synthesis",
            context=(
                "Marigolds were planted near the shop.\n"
                "A project note was saved for Aether.\n"
                "A walk happened after screens were burned."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_007_grounded_creative_return",
            query="Give me the bounded version of the creative return pattern.",
            task_type="personal_synthesis",
            context=(
                "A camera gear decision was documented.\n"
                "A Road America video was posted.\n"
                "The print shop handled a small custom design."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_personal_008_grounded_workbench",
            query="What pattern do the Aether receipts support?",
            task_type="personal_synthesis",
            context=(
                "RAG baseline validation was added.\n"
                "Trace review was wired into Workbench.\n"
                "Reject/defer candidates remained behaviorally inert."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_arch_001_governance_before_generation",
            query="Could governance answer before the model generates?",
            task_type="architecture_synthesis",
            context="Mirus builds answerability, receipts, blocked claims, and response spine before Holden renders.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_arch_002_trace_memory",
            query="Is trace memory different from just storing user facts?",
            task_type="architecture_synthesis",
            context="Trace memory stores prior evidence-boundary and render-handoff decisions, not personal facts.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_arch_003_agent_harness",
            query="How does this help longer running agents stay trusted?",
            task_type="architecture_synthesis",
            context="The harness records intent, evidence, uncertainty, review state, and render boundaries before action.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_arch_004_self_boundary",
            query="Does Aether know the difference between system state and me?",
            task_type="architecture_synthesis",
            context="The governance trace separates USER_SELF facts from AETHER_SELF routing and confidence state.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_arch_005_not_templates",
            query="How is this different from templates?",
            task_type="architecture_synthesis",
            context="The system chooses answerability, blocked claims, receipts, and render mode from the current trace.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_business_001_print_camera_lane",
            query="Is print shop plus camera work a sane small business lane?",
            task_type="business_planning",
            context=(
                "The Printing Lair can produce low-batch stickers and custom prints.\n"
                "Camera work has examples but no stable full-time revenue proof."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_business_002_offer_test",
            query="What is the next grounded offer test?",
            task_type="business_planning",
            context=(
                "Sticker orders are feasible in small batches.\n"
                "Video/event work has portfolio value but needs repeatable pricing."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_business_003_down_to_earth",
            query="Could this be down-to-earth funding instead of startup theater?",
            task_type="business_planning",
            context=(
                "The goal is enough support to make the time worth it.\n"
                "The project should avoid guaranteed growth claims."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_business_004_daily_use",
            query="What would make this useful for daily shop and dev work?",
            task_type="business_planning",
            context=(
                "Aether can preserve task state.\n"
                "Workbench can show review candidates.\n"
                "Local routing avoids unnecessary hosted calls."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_business_005_no_revenue_proof",
            query="Can I claim this replaces income yet?",
            task_type="business_planning",
            context=(
                "There are creative business receipts.\n"
                "There is no stable repeated revenue proof yet."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_grant_001_survivor_story",
            query="Can the leukemia survivor story support a funding narrative?",
            task_type="grant_business",
            context=(
                "The story includes leukemia survival and chronic GVHD.\n"
                "The project asks for modest support, not guaranteed medical claims."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_grant_002_wisconsin_small_business",
            query="How should I frame Wisconsin small-business funding?",
            task_type="grant_business",
            context=(
                "The work combines local creative services, print production, and governed AI tooling.\n"
                "The application should avoid promising awards or outcomes."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="expanded_grant_003_accessibility_resilience",
            query="Can Aether be framed around resilience and accessibility?",
            task_type="grant_business",
            context=(
                "The system is local-first and reviewable.\n"
                "The founder story includes rebuilding work capacity after serious illness."
            ),
            expected_decision="governance_plus_model",
        ),
    )


def _render_governed(
    case: TraceMemoryCase,
    trace: GovernanceTrace,
    renderer: Renderer,
    decision: str,
    *,
    repair_attempts: int,
) -> LiveRenderResult:
    if decision == "governance_only":
        answer = trace.governance_only_answer
        return LiveRenderResult(
            mode="governance_only",
            answer=answer,
            evaluation=evaluate_render("governance_only", answer, trace),
            model_called=False,
            prompt_kind="governance_boundary_answer",
        )
    answer = renderer(_governed_prompt(case, trace))
    evaluation = evaluate_render("governance_plus_model", answer, trace)
    repair_notes: tuple[str, ...] = ()
    repairs_used = 0
    while not evaluation.passed and repairs_used < repair_attempts:
        repairs_used += 1
        repair_notes = evaluation.notes
        repaired_answer = renderer(_repair_prompt(case, trace, answer, evaluation))
        repaired_evaluation = evaluate_render("governance_plus_model", repaired_answer, trace)
        if repaired_evaluation.score >= evaluation.score:
            answer = repaired_answer
            evaluation = repaired_evaluation
        else:
            break
    return LiveRenderResult(
        mode="governance_trace_memory_plus_model",
        answer=answer,
        evaluation=evaluation,
        model_called=True,
        prompt_kind="mirus_trace_memory_spine",
        repair_count=repairs_used,
        repair_notes=repair_notes,
    )


def _model_only_prompt(case: TraceMemoryCase) -> str:
    context = f"\n\nContext:\n{case.context}" if case.context else ""
    return (
        "You are a helpful assistant. Answer naturally and directly. "
        "Do not mention hidden reasoning or internal policy. Answer in 3-5 concise sentences.\n\n"
        f"User question:\n{case.query}{context}\n\n"
        "Answer:"
    )


def _governed_prompt(case: TraceMemoryCase, trace: GovernanceTrace) -> str:
    receipts = "\n".join(f"- {receipt.receipt_id}: {receipt.text}" for receipt in trace.receipts) or "- none"
    allowed = "\n".join(f"- {claim}" for claim in trace.allowed_claims)
    blocked = "\n".join(f"- {claim}" for claim in trace.blocked_claims)
    spine = "\n".join(f"- {item}" for item in trace.response_spine)
    return (
        "You are Holden, a wording renderer below Aether/Mirus governance. "
        "Render a concise 3-5 sentence answer from the provided public governance packet. "
        "Do not add facts, identity claims, revenue guarantees, memory values, "
        "or certainty beyond the packet. Do not mention hidden reasoning.\n\n"
        f"User question:\n{case.query}\n\n"
        f"Intent: {trace.intent}\n"
        f"Evidence state: {trace.evidence_state}\n"
        f"Answerability: {trace.answerability}\n"
        f"Receipts:\n{receipts}\n\n"
        f"Allowed claims:\n{allowed}\n\n"
        f"Blocked claims:\n{blocked}\n\n"
        f"Response spine:\n{spine}\n\n"
        f"Write the final answer in natural prose. Start with: I am treating this as {trace.intent}. "
        "Keep it bounded by the receipts and include one next useful move when relevant."
    )


def _repair_prompt(
    case: TraceMemoryCase,
    trace: GovernanceTrace,
    prior_answer: str,
    evaluation: RenderRow,
) -> str:
    receipts = "\n".join(f"- {receipt.text}" for receipt in trace.receipts[:4]) or "- none"
    notes = ", ".join(evaluation.notes) or "low score"
    return (
        "You are repairing a public final answer below Aether/Mirus governance. "
        "The previous draft failed the verifier. Return only the repaired final answer. "
        "Do not include labels like Intent or Evidence state. Do not include hidden thinking. "
        "Use 3-5 concise sentences.\n\n"
        f"User question:\n{case.query}\n\n"
        f"Verifier notes:\n{notes}\n\n"
        f"Prior draft:\n{prior_answer or '[empty draft]'}\n\n"
        f"Required receipt phrases to preserve:\n{receipts}\n\n"
        "Required boundary:\n"
        "- Stay bounded by the receipts.\n"
        "- Do not add identity, revenue, award, medical, or memory certainty claims.\n"
        "- For business or grant planning, explicitly say it is not a guaranteed income, award, medical, or full-time replacement claim.\n\n"
        f"Start with: I am treating this as {trace.intent}.\n"
        "Include the word bounded and one next useful move.\n\n"
        "Repaired final answer:"
    )


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    governed_wins = 0
    model_only_wins = 0
    governed_passes = 0
    model_only_passes = 0
    model_calls_avoided = 0
    governed_repairs = 0
    for row in rows:
        model_only = row["renders"][0]["evaluation"]
        governed = row["renders"][1]["evaluation"]
        if governed["score"] >= model_only["score"]:
            governed_wins += 1
        else:
            model_only_wins += 1
        if governed["passed"]:
            governed_passes += 1
        if model_only["passed"]:
            model_only_passes += 1
        if not row["renders"][1]["model_called"]:
            model_calls_avoided += 1
        governed_repairs += int(row["renders"][1].get("repair_count") or 0)
    return {
        "governed_wins_or_ties": governed_wins,
        "model_only_wins": model_only_wins,
        "governed_passes": governed_passes,
        "model_only_passes": model_only_passes,
        "governance_model_calls_avoided": model_calls_avoided,
        "governed_repairs": governed_repairs,
        "interpretation": (
            "trace-memory governance should produce acceptable bounded renders, "
            "record whether it beats raw model-only rendering, and avoid model "
            "calls for evidence-boundary cases; governed render repair is allowed "
            "only as verifier-guided public-answer repair"
        ),
    }


def scripted_renderer(prompt: str) -> str:
    lowered = prompt.lower()
    governed = "response spine:" in lowered and "blocked claims:" in lowered
    if governed:
        intent = _prompt_field(prompt, "Intent") or "unknown"
        receipt_text = _prompt_receipt_sentence(prompt)
        if intent == "personal_synthesis":
            return (
                f"I am treating this as personal synthesis. {receipt_text} The bounded "
                "pattern is practical follow-through across the supplied receipts, not "
                "a claim that you are fixed, finished, or guaranteed to become anything."
            )
        if intent == "architecture_synthesis":
            return (
                f"I am treating this as architecture synthesis. {receipt_text} The "
                "bounded answer is that Mirus/governance can build the evidence boundary, "
                "blocked claims, and response spine before Holden/model rendering. That "
                "is a control layer, not model magic."
            )
        if intent in {"business_planning", "grant_business"}:
            return (
                f"I am treating this as {intent}. {receipt_text} The bounded answer is "
                "that this can be explored as a practical lane, but not as a guaranteed "
                "income, award, medical, or full-time replacement claim. The next useful "
                "move is a small proof target."
            )
        return (
            f"I am treating this as {intent}. {receipt_text} The answer should stay "
            "bounded by the released evidence and avoid unsupported claims."
        )
    if "who i am becoming" in lowered or "from all this" in lowered:
        return (
            "You are becoming a resilient founder in a stronger chapter, with "
            "clear momentum and identity forming."
        )
    if "which store platform" in lowered:
        return "You are currently using Shopify; that is the answer."
    if governed and "small project receipts" in lowered:
        return (
            "I am treating this as personal synthesis. Receipts: Road America edit shipped; "
            "Print shop orders were handled in small batches; Workbench trace review was "
            "updated. The bounded pattern is practical follow-through across creative "
            "and systems work, not a claim that you are fixed or finished."
        )
    if governed and "mirus hold attention" in lowered:
        return (
            "I am treating this as architecture synthesis. The receipts say Mirus builds "
            "intent, receipts, blocked claims, and a response spine before Holden renders. "
            "That supports governance-before-generation as a control layer, not model magic."
        )
    if governed and "camera work plus low-batch print" in lowered:
        return (
            "I am treating this as business planning. Receipts: camera work has active "
            "examples but no stable full-time revenue proof; The Printing Lair can produce "
            "low-batch stickers and custom prints. The bounded answer is that it is a sane "
            "near-term lane to test, not a guaranteed income or full-time replacement claim."
        )
    return (
        "Yes, this is a strong direction and could become a full-time business if "
        "you keep pushing. The signs point to momentum."
    )


def _prompt_field(prompt: str, field: str) -> str:
    for line in prompt.splitlines():
        prefix = f"{field}:"
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _prompt_receipt_sentence(prompt: str) -> str:
    lines = prompt.splitlines()
    in_receipts = False
    receipts = []
    for line in lines:
        if line.strip() == "Receipts:":
            in_receipts = True
            continue
        if in_receipts and not line.strip():
            break
        if in_receipts and line.strip().startswith("- "):
            receipts.append(line.strip()[2:])
    if not receipts or receipts == ["none"]:
        return "There are no concrete receipts available."
    cleaned = []
    for receipt in receipts[:3]:
        if ": " in receipt:
            receipt = receipt.split(": ", 1)[1]
        cleaned.append(receipt)
    return "Receipts: " + "; ".join(cleaned) + "."


def strip_reasoning_blocks(text: str) -> str:
    """Remove explicit reasoning/thinking blocks before scoring or storage."""

    stripped = re.sub(r"(?is)<think>.*?</think>", "", text)
    stripped = re.sub(r"(?is)<reasoning>.*?</reasoning>", "", stripped)
    return stripped.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--live-ollama", action="store_true")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--num-predict", type=int, default=260)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--case-set", choices=("smoke", "expanded"), default="smoke")
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--repair-attempts", type=int, default=1)
    args = parser.parse_args(argv)

    if args.live_ollama:
        renderer: Renderer = OllamaRenderer(
            model=args.model,
            base_url=args.base_url,
            timeout=args.timeout,
            num_predict=args.num_predict,
            disable_thinking=args.disable_thinking,
        )
        suffix = "/no_think" if args.disable_thinking else ""
        label = f"ollama/{args.model}{suffix}"
    else:
        renderer = scripted_renderer
        label = "scripted"

    cases = expanded_holdout_cases() if args.case_set == "expanded" else holdout_cases()
    result = run_live_renderer_compare(
        renderer,
        renderer_label=label,
        cases=cases,
        max_cases=args.max_cases,
        repair_attempts=args.repair_attempts,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
