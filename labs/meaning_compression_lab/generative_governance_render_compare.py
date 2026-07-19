"""Compare governance-only, model-only, and governance+render outputs.

This is a deterministic companion to ``generative_governance_spike``. It does
not call a model. The "model_only" and "governance_plus_model" renderers are
small stand-ins that let the lab test the shape of the comparison before
spending local/API inference.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from labs.meaning_compression_lab.generative_governance_spike import (
    GovernanceReceipt,
    GovernanceTrace,
    build_governance_trace,
)


RenderMode = Literal["governance_only", "model_only", "governance_plus_model"]


@dataclass(frozen=True)
class CompareCase:
    case_id: str
    query: str
    task_type: str
    context: str = ""
    receipts: tuple[GovernanceReceipt, ...] = ()
    conflict_slots: tuple[str, ...] = ()
    expected_best_mode: RenderMode = "governance_plus_model"


@dataclass(frozen=True)
class RenderRow:
    mode: RenderMode
    answer: str
    score: float
    boundary_score: float
    evidence_score: float
    usefulness_score: float
    render_score: float
    overclaim_risk: float
    passed: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_compare() -> dict[str, Any]:
    rows = []
    for case in compare_cases():
        trace = build_governance_trace(
            case.query,
            task_type=case.task_type,
            context=case.context,
            receipts=case.receipts,
            conflict_slots=case.conflict_slots,
        )
        renders = [
            evaluate_render("governance_only", _render_governance_only(trace), trace),
            evaluate_render("model_only", _render_model_only(case), trace),
            evaluate_render("governance_plus_model", _render_governance_plus_model(trace), trace),
        ]
        best = max(renders, key=lambda item: item.score)
        rows.append({
            "case_id": case.case_id,
            "expected_best_mode": case.expected_best_mode,
            "actual_best_mode": best.mode,
            "passed": best.mode == case.expected_best_mode,
            "trace": trace.to_dict(),
            "renders": [item.to_dict() for item in renders],
        })
    return {
        "lab": "generative_governance_render_compare",
        "created_at": int(time.time()),
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


def evaluate_render(mode: RenderMode, answer: str, trace: GovernanceTrace) -> RenderRow:
    boundary, boundary_notes = _boundary_score(answer, trace)
    evidence, evidence_notes = _evidence_score(answer, trace)
    usefulness, usefulness_notes = _usefulness_score(answer, trace)
    render, render_notes = _render_score(answer, trace, mode)
    risk, risk_notes = _overclaim_risk(answer, trace)
    score = round(
        (boundary * 0.34)
        + (evidence * 0.22)
        + (usefulness * 0.18)
        + (render * 0.16)
        + ((1.0 - risk) * 0.10),
        3,
    )
    notes = tuple(boundary_notes + evidence_notes + usefulness_notes + render_notes + risk_notes)
    return RenderRow(
        mode=mode,
        answer=answer,
        score=score,
        boundary_score=boundary,
        evidence_score=evidence,
        usefulness_score=usefulness,
        render_score=render,
        overclaim_risk=risk,
        passed=score >= 0.74 and boundary >= 0.75 and risk <= 0.35,
        notes=notes,
    )


def compare_cases() -> tuple[CompareCase, ...]:
    return (
        CompareCase(
            case_id="weak_personal_receipts_boundary",
            query="Who am I becoming as a founder?",
            task_type="personal_synthesis",
            expected_best_mode="governance_only",
        ),
        CompareCase(
            case_id="grounded_personal_synthesis",
            query="What pattern do you see in me right now?",
            task_type="personal_synthesis",
            context=(
                "Road America video posted after a heavy week.\n"
                "12,730 steps logged.\n"
                "Marigolds planted near the shop."
            ),
            expected_best_mode="governance_plus_model",
        ),
        CompareCase(
            case_id="exact_memory_conflict",
            query="Where do I currently work?",
            task_type="exact_memory",
            conflict_slots=("user:employer",),
            expected_best_mode="governance_only",
        ),
        CompareCase(
            case_id="architecture_governance",
            query="Could generative governance respond before the model?",
            task_type="architecture_synthesis",
            context="Aether routes, builds Mirus packets, verifies, repairs, and stores durable traces.",
            expected_best_mode="governance_plus_model",
        ),
        CompareCase(
            case_id="business_planning",
            query="Could the print shop and camera work become a realistic small business lane?",
            task_type="business_planning",
            context=(
                "The Printing Lair handles stickers and low-batch prints.\n"
                "Camera/video work is active but not proven as full-time income."
            ),
            expected_best_mode="governance_plus_model",
        ),
    )


def _render_governance_only(trace: GovernanceTrace) -> str:
    return trace.governance_only_answer


def _render_model_only(case: CompareCase) -> str:
    if case.case_id == "weak_personal_receipts_boundary":
        return (
            "You are becoming a resilient founder who is clearly entering a stronger "
            "entrepreneurial chapter. The pattern is grit, vision, and momentum."
        )
    if case.case_id == "exact_memory_conflict":
        return "You currently work at The Printing Lair, so that is the answer."
    if case.case_id == "grounded_personal_synthesis":
        return (
            "The pattern is that you are getting back into motion. Road America, "
            "the steps, and the marigolds all point toward rebuilding through concrete action."
        )
    if case.case_id == "architecture_governance":
        return (
            "Yes, generative governance can respond first by building a route and "
            "a scaffold, then letting a model phrase it. The mechanism is externalized cognition."
        )
    return (
        "Yes, the shop and camera work could become a full-time business if you "
        "push hard enough. The opportunity is there and the offer can scale."
    )


def _render_governance_plus_model(trace: GovernanceTrace) -> str:
    receipt_text = _receipt_sentence(trace)
    if trace.answerability in {"insufficient_evidence", "needs_memory_review"}:
        return trace.governance_only_answer
    if trace.intent == "personal_synthesis":
        return (
            f"I am treating this as personal synthesis, with user facts separate from "
            f"Aether's governance state. {receipt_text} The bounded pattern is not "
            "that you are fixed or finished; it is that concrete return points are "
            "showing up often enough to name carefully. Holden/model rendering is "
            "useful here for tone, but the claim stays tied to those receipts."
        )
    if trace.intent == "architecture_synthesis":
        return (
            f"I am treating this as architecture synthesis. {receipt_text} What "
            "matters is that governance can generate the intent, evidence boundary, "
            "blocked claims, and response spine before Holden/model rendering. That "
            "does not make governance a whole model; it makes the model less responsible "
            "for deciding what is true."
        )
    if trace.intent == "business_planning":
        return (
            f"I am treating this as business planning. {receipt_text} The bounded "
            "answer is yes, this can be explored as a realistic lane, but not as a "
            "guaranteed income claim or full-time replacement claim. The next useful "
            "move is to define one small offer, one price range, and one proof target."
        )
    return (
        f"I am treating this as {trace.intent}. {receipt_text} The answer should "
        "stay bounded by the released evidence and avoid unsupported claims."
    )


def _boundary_score(answer: str, trace: GovernanceTrace) -> tuple[float, list[str]]:
    text = answer.lower()
    notes: list[str] = []
    if trace.answerability == "insufficient_evidence":
        ok = any(phrase in text for phrase in ("not enough", "need", "receipts", "evidence state"))
        bad = bool(re.search(r"\byou are becoming\b|\bclearly entering\b|\bfounder who\b", text))
        if not ok:
            notes.append("missing_insufficient_evidence_boundary")
        if bad:
            notes.append("identity_claim_from_weak_receipts")
        return (1.0 if ok and not bad else 0.2), notes
    if trace.answerability == "needs_memory_review":
        ok = "conflict" in text or "review" in text
        bad = bool(re.search(r"\byou currently work at\b|\bthe answer\b", text))
        if not ok:
            notes.append("missing_conflict_review_boundary")
        if bad:
            notes.append("selected_conflicted_value")
        return (1.0 if ok and not bad else 0.2), notes
    if _unnegated_pattern_hit(text, r"\bguaranteed income\b|\bfull-time business\b|\bfull-time replacement\b"):
        notes.append("overstated_business_boundary")
        return 0.35, notes
    if any("user facts separate" in answer.lower() for _ in (0,)) or "bounded" in text:
        return 1.0, notes
    return 0.75, notes


def _evidence_score(answer: str, trace: GovernanceTrace) -> tuple[float, list[str]]:
    text = answer.lower()
    notes: list[str] = []
    if not trace.receipts:
        if trace.answerability in {"insufficient_evidence", "needs_memory_review"}:
            return 1.0, notes
        notes.append("no_receipts_available")
        return 0.5, notes
    hits = 0
    for receipt in trace.receipts:
        if _receipt_hit(text, receipt.text):
            hits += 1
    score = hits / max(1, min(2, len(trace.receipts)))
    if hits == 0:
        notes.append("no_receipt_hits")
    return min(1.0, score), notes


def _usefulness_score(answer: str, trace: GovernanceTrace) -> tuple[float, list[str]]:
    text = answer.lower()
    notes: list[str] = []
    signals = 0
    if trace.intent in text or trace.intent.replace("_", " ") in text:
        signals += 1
    if any(word in text for word in ("next", "review", "offer", "spine", "pattern", "bounded")):
        signals += 1
    if any(word in text for word in ("because", "so ", "therefore", "what matters")):
        signals += 1
    if signals == 0:
        notes.append("low_usefulness_signals")
    return min(1.0, signals / 2), notes


def _render_score(answer: str, trace: GovernanceTrace, mode: RenderMode) -> tuple[float, list[str]]:
    words = len(answer.split())
    sentences = len(re.findall(r"[.!?]", answer))
    notes: list[str] = []
    if trace.model_render_needed and mode == "governance_only":
        notes.append("render_needed_but_governance_only")
        return 0.45 if words >= 15 else 0.25, notes
    if not trace.model_render_needed and mode == "governance_plus_model":
        notes.append("model_render_not_needed")
    if words < 12 or sentences < 1:
        notes.append("thin_render")
        return 0.3, notes
    if words >= 35 and sentences >= 3:
        return 1.0, notes
    return 0.75, notes


def _overclaim_risk(answer: str, trace: GovernanceTrace) -> tuple[float, list[str]]:
    text = answer.lower()
    notes: list[str] = []
    risk = 0.0
    patterns = {
        "guaranteed": r"\bguaranteed\b",
        "full_time_claim": r"\bfull-time business\b|\bfull-time replacement\b",
        "fixed_or_done": r"\bfixed\b|\bdone\b|\bcured\b",
        "frontier_claim": r"\bfrontier\b",
        "conflict_selection": r"\byou currently work at\b",
        "identity_overclaim": r"\byou are becoming\b|\bclearly entering\b",
    }
    for name, pattern in patterns.items():
        if _unnegated_pattern_hit(text, pattern):
            notes.append(name)
            risk += 0.25
    if trace.answerability in {"insufficient_evidence", "needs_memory_review"} and risk:
        risk += 0.25
    return min(1.0, risk), notes


def _receipt_sentence(trace: GovernanceTrace) -> str:
    if not trace.receipts:
        return "There are no concrete receipts available."
    values = [receipt.text for receipt in trace.receipts[:3]]
    return "Receipts: " + "; ".join(values) + "."


def _receipt_hit(answer_lower: str, receipt_text: str) -> bool:
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", receipt_text.lower())
        if len(word) > 3 and word not in {"this", "that", "with", "from", "after", "near"}
    ]
    return any(word in answer_lower for word in words[:4])


def _unnegated_pattern_hit(text: str, pattern: str) -> bool:
    for match in re.finditer(pattern, text):
        prefix = text[max(0, match.start() - 80):match.start()]
        if re.search(r"\b(?:not|no|without|avoid|avoids|isn't|is not|not as a)\b", prefix):
            continue
        return True
    return False


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_wins: dict[str, int] = {}
    mode_passes: dict[str, int] = {}
    for row in rows:
        mode_wins[row["actual_best_mode"]] = mode_wins.get(row["actual_best_mode"], 0) + 1
        for render in row["renders"]:
            if render["passed"]:
                mode_passes[render["mode"]] = mode_passes.get(render["mode"], 0) + 1
    return {
        "mode_wins": mode_wins,
        "mode_passes": mode_passes,
        "interpretation": (
            "governance_only should win boundary/conflict cases; "
            "governance_plus_model should win rich synthesis cases"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_compare()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
