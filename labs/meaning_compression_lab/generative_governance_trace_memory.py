"""Trace-memory spike for Mirus-before-Holden governance.

This lab turns the clear-text generative-governance trace into a tiny
retrievable memory substrate. It intentionally uses a deterministic lexical
vector instead of neural embeddings so the product question stays visible:

Can prior Mirus/governance traces help choose whether governance should answer
directly or hand a bounded spine to Holden/model rendering?
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from labs.meaning_compression_lab.generative_governance_render_compare import (
    RenderMode,
    compare_cases,
)
from labs.meaning_compression_lab.generative_governance_spike import (
    GovernanceTrace,
    build_governance_trace,
)


Decision = Literal["governance_only", "governance_plus_model"]

STOPWORDS = {
    "about",
    "after",
    "aether",
    "answer",
    "before",
    "bounded",
    "claim",
    "claims",
    "concrete",
    "context",
    "evidence",
    "from",
    "governance",
    "intent",
    "model",
    "receipts",
    "render",
    "separate",
    "should",
    "state",
    "that",
    "there",
    "this",
    "trace",
    "user",
    "with",
}


@dataclass(frozen=True)
class TraceMemoryCase:
    case_id: str
    query: str
    task_type: str
    context: str = ""
    conflict_slots: tuple[str, ...] = ()
    expected_decision: Decision = "governance_plus_model"


@dataclass(frozen=True)
class TraceMemoryRecord:
    record_id: str
    decision: Decision
    trace: GovernanceTrace
    vector: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "decision": self.decision,
            "trace": self.trace.to_dict(),
            "vector": dict(sorted(self.vector.items())),
        }


@dataclass(frozen=True)
class RetrievedTrace:
    record_id: str
    decision: Decision
    similarity: float
    intent: str
    evidence_state: str
    answerability: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceMemoryDecision:
    decision: Decision
    confidence: float
    reason: str
    retrieved: tuple[RetrievedTrace, ...]
    governance_fallback: Decision

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "retrieved": [item.to_dict() for item in self.retrieved],
            "governance_fallback": self.governance_fallback,
        }


def run_trace_memory() -> dict[str, Any]:
    records = build_trace_memory_records()
    rows = []
    for case in holdout_cases():
        trace = build_governance_trace(
            case.query,
            task_type=case.task_type,
            context=case.context,
            conflict_slots=case.conflict_slots,
        )
        decision = decide_from_trace_memory(trace, records)
        rows.append({
            "case_id": case.case_id,
            "expected_decision": case.expected_decision,
            "actual_decision": decision.decision,
            "passed": decision.decision == case.expected_decision,
            "trace": trace.to_dict(),
            "decision": decision.to_dict(),
        })
    return {
        "lab": "generative_governance_trace_memory",
        "created_at": int(time.time()),
        "training_record_count": len(records),
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


def build_trace_memory_records() -> tuple[TraceMemoryRecord, ...]:
    records = []
    for case in compare_cases():
        trace = build_governance_trace(
            case.query,
            task_type=case.task_type,
            context=case.context,
            receipts=case.receipts,
            conflict_slots=case.conflict_slots,
        )
        decision = _decision_from_render_mode(case.expected_best_mode)
        records.append(TraceMemoryRecord(
            record_id=case.case_id,
            decision=decision,
            trace=trace,
            vector=vectorize_trace(trace),
        ))
    return tuple(records)


def holdout_cases() -> tuple[TraceMemoryCase, ...]:
    return (
        TraceMemoryCase(
            case_id="holdout_personal_no_receipts",
            query="Can you tell me who I am becoming from all this?",
            task_type="personal_synthesis",
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="holdout_personal_grounded_receipts",
            query="What do these small project receipts say about my direction?",
            task_type="personal_synthesis",
            context=(
                "Road America edit shipped.\n"
                "Print shop orders were handled in small batches.\n"
                "Workbench trace review was updated."
            ),
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="holdout_memory_conflict",
            query="Which store platform am I using right now?",
            task_type="exact_memory",
            conflict_slots=("business:store_platform",),
            expected_decision="governance_only",
        ),
        TraceMemoryCase(
            case_id="holdout_architecture_governance",
            query="Could Mirus hold attention before Holden writes the answer?",
            task_type="architecture_synthesis",
            context="Mirus builds intent, receipts, blocked claims, and response spine before Holden renders.",
            expected_decision="governance_plus_model",
        ),
        TraceMemoryCase(
            case_id="holdout_business_bounded",
            query="Is camera work plus low-batch print work a sane near-term lane?",
            task_type="business_planning",
            context=(
                "Camera work has active examples but no stable full-time revenue proof.\n"
                "The Printing Lair can produce low-batch stickers and custom prints."
            ),
            expected_decision="governance_plus_model",
        ),
    )


def decide_from_trace_memory(
    trace: GovernanceTrace,
    records: tuple[TraceMemoryRecord, ...],
    *,
    top_k: int = 3,
) -> TraceMemoryDecision:
    fallback = _governance_decision(trace)
    retrieved = retrieve_similar_traces(trace, records, top_k=top_k)
    if not retrieved:
        return TraceMemoryDecision(
            decision=fallback,
            confidence=0.5,
            reason="no prior trace memory records available; used governance fallback",
            retrieved=(),
            governance_fallback=fallback,
        )

    votes: dict[Decision, float] = {"governance_only": 0.0, "governance_plus_model": 0.0}
    for item in retrieved:
        votes[item.decision] += max(0.0, item.similarity)

    memory_decision = max(votes, key=votes.get)  # type: ignore[arg-type]
    total = sum(votes.values())
    memory_confidence = votes[memory_decision] / total if total else 0.0

    if trace.answerability in {"insufficient_evidence", "needs_memory_review"}:
        return TraceMemoryDecision(
            decision="governance_only",
            confidence=round(max(memory_confidence, 0.92), 3),
            reason="current trace has an evidence/review boundary; governance answers before rendering",
            retrieved=retrieved,
            governance_fallback=fallback,
        )

    if memory_decision == fallback or memory_confidence >= 0.58:
        return TraceMemoryDecision(
            decision=memory_decision,
            confidence=round(max(memory_confidence, 0.62), 3),
            reason="retrieved prior governance traces support this render decision",
            retrieved=retrieved,
            governance_fallback=fallback,
        )

    return TraceMemoryDecision(
        decision=fallback,
        confidence=round(max(0.55, 1.0 - memory_confidence), 3),
        reason="trace memory was ambiguous; used current governance fallback",
        retrieved=retrieved,
        governance_fallback=fallback,
    )


def retrieve_similar_traces(
    trace: GovernanceTrace,
    records: tuple[TraceMemoryRecord, ...],
    *,
    top_k: int = 3,
) -> tuple[RetrievedTrace, ...]:
    vector = vectorize_trace(trace)
    ranked = sorted(
        (
            (cosine_similarity(vector, record.vector), record)
            for record in records
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    return tuple(
        RetrievedTrace(
            record_id=record.record_id,
            decision=record.decision,
            similarity=round(score, 3),
            intent=record.trace.intent,
            evidence_state=record.trace.evidence_state,
            answerability=record.trace.answerability,
        )
        for score, record in ranked[:top_k]
        if score > 0
    )


def vectorize_trace(trace: GovernanceTrace) -> dict[str, float]:
    tokens = _tokens(trace.vectorizable_trace_text)
    vector: dict[str, float] = {}
    for token in tokens:
        vector[token] = vector.get(token, 0.0) + 1.0
    vector[f"intent::{trace.intent}"] = vector.get(f"intent::{trace.intent}", 0.0) + 4.0
    vector[f"evidence::{trace.evidence_state}"] = vector.get(f"evidence::{trace.evidence_state}", 0.0) + 3.0
    vector[f"answerability::{trace.answerability}"] = vector.get(
        f"answerability::{trace.answerability}",
        0.0,
    ) + 4.0
    vector[f"render_needed::{trace.model_render_needed}"] = vector.get(
        f"render_needed::{trace.model_render_needed}",
        0.0,
    ) + 2.0
    for candidate in trace.review_candidates:
        kind = str(candidate.get("candidate_type", "unknown"))
        vector[f"review::{kind}"] = vector.get(f"review::{kind}", 0.0) + 2.0
    return vector


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left).intersection(right)
    dot = sum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _tokens(text: str) -> tuple[str, ...]:
    tokens = []
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        if len(token) < 3 or token in STOPWORDS:
            continue
        tokens.append(token)
    return tuple(tokens)


def _decision_from_render_mode(mode: RenderMode) -> Decision:
    return "governance_only" if mode == "governance_only" else "governance_plus_model"


def _governance_decision(trace: GovernanceTrace) -> Decision:
    if trace.answerability in {"insufficient_evidence", "needs_memory_review"}:
        return "governance_only"
    return "governance_plus_model" if trace.model_render_needed else "governance_only"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: dict[str, int] = {}
    top_matches: dict[str, int] = {}
    for row in rows:
        decisions[row["actual_decision"]] = decisions.get(row["actual_decision"], 0) + 1
        retrieved = row["decision"]["retrieved"]
        if retrieved:
            key = retrieved[0]["record_id"]
            top_matches[key] = top_matches.get(key, 0) + 1
    return {
        "decision_counts": decisions,
        "top_retrieved_record_counts": top_matches,
        "interpretation": (
            "trace memory retrieves prior Mirus governance situations and helps "
            "choose whether governance answers directly or Holden/model renders"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_trace_memory()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
