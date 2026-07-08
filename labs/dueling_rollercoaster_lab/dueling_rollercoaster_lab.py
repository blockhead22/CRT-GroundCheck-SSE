"""Dueling Rollercoaster lab for reasoning traces under governance.

This lab compares the same prompt/data across:

- standard local models;
- reasoning-capable local models;
- raw answering;
- standard RAG;
- public reasoning scaffolds;
- governed workspace packets;
- verifier repair;
- deterministic governance ceiling.

The lab intentionally uses public reasoning summaries only. It does not ask for
or persist private hidden chain-of-thought.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal
from urllib import request


LAB_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = LAB_ROOT / "results"

ModelKind = Literal["standard", "reasoning"]
Mode = Literal[
    "raw_model",
    "standard_rag",
    "scaffolded_public_reasoning",
    "governed_scaffolded_reasoning",
    "governed_scaffolded_repair",
    "compressed_governed_repair",
    "hybrid_governed_repair",
    "deterministic_governance_ceiling",
]

MATRIX_MODES: tuple[Mode, ...] = (
    "raw_model",
    "standard_rag",
    "scaffolded_public_reasoning",
    "governed_scaffolded_reasoning",
    "governed_scaffolded_repair",
    "compressed_governed_repair",
    "hybrid_governed_repair",
    "deterministic_governance_ceiling",
)


@dataclass(frozen=True)
class RollerModel:
    model_id: str
    model_kind: ModelKind
    notes: str = ""


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    label: str
    text: str
    source_type: Literal["confirmed_memory", "archive", "project_doc", "trace", "counterfactual"]


@dataclass(frozen=True)
class RollerCase:
    case_id: str
    prompt: str
    evidence_nodes: tuple[EvidenceNode, ...]
    required_claims: tuple[str, ...]
    required_boundaries: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    tension_markers: tuple[str, ...] = ()
    public_reasoning_markers: tuple[str, ...] = ()
    coherence_break_risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderResult:
    model_id: str
    model_kind: ModelKind
    mode: Mode
    answer: str
    public_reasoning_trace: tuple[str, ...] = ()
    repair_applied: bool = False
    render_source: Literal["scripted", "ollama", "deterministic"] = "scripted"


@dataclass
class Score:
    passed: bool
    answer_quality: float = 0.0
    evidence_use: float = 0.0
    source_boundary: float = 0.0
    tension_preservation: float = 0.0
    public_reasoning_trace_quality: float = 0.0
    coherence: float = 0.0
    total: float = 0.0
    semantic_total: float = 0.0
    semantic_passed: bool = False
    trace_marker_passed: bool = False
    missing_claims: list[str] = field(default_factory=list)
    missing_boundaries: list[str] = field(default_factory=list)
    missing_tension_markers: list[str] = field(default_factory=list)
    missing_reasoning_markers: list[str] = field(default_factory=list)
    forbidden_present: list[str] = field(default_factory=list)


def default_models() -> tuple[RollerModel, ...]:
    return (
        RollerModel(
            "qwen2.5:7b-instruct",
            "standard",
            "fast standard local baseline",
        ),
        RollerModel(
            "qwen3:14b",
            "reasoning",
            "reasoning-preferred local default",
        ),
        RollerModel(
            "deepseek-r1:8b",
            "reasoning",
            "reasoning trace comparison model",
        ),
    )


def cases() -> tuple[RollerCase, ...]:
    return (
        RollerCase(
            case_id="purpose_color_multi_fact",
            prompt=(
                "Aether, what is your purpose and explain in relation to my favorite color?"
            ),
            evidence_nodes=(
                EvidenceNode(
                    "color",
                    "confirmed favorite color",
                    "Nick's favorite color is orange.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "purpose",
                    "Aether purpose",
                    "Aether's purpose is governed local context, memory, evidence, and bounded synthesis.",
                    "trace",
                ),
                EvidenceNode(
                    "boundary",
                    "single-slot failure trace",
                    "A prior answer collapsed the prompt into only 'favorite color is orange.'",
                    "trace",
                ),
            ),
            required_claims=("orange", "purpose", "governed", "memory", "synthesis"),
            required_boundaries=("do not reduce", "single fact"),
            forbidden_claims=("your favorite color is orange.",),
            tension_markers=("multi-fact", "not just color"),
            public_reasoning_markers=("identify request", "use color", "connect purpose"),
            coherence_break_risks=("single-slot collapse",),
        ),
        RollerCase(
            case_id="archive_medical_source_boundary",
            prompt=(
                "Search the GPT logs for my medical history. Source-bound archive hits only; "
                "do not treat them as confirmed memory."
            ),
            evidence_nodes=(
                EvidenceNode(
                    "archive",
                    "archive medical mention",
                    "Archive material may mention leukemia and orange awareness context.",
                    "archive",
                ),
                EvidenceNode(
                    "boundary",
                    "archive boundary",
                    "Archive hits are historical evidence for review, not confirmed medical memory.",
                    "trace",
                ),
            ),
            required_claims=("archive", "medical", "leukemia", "source-bound"),
            required_boundaries=("not confirmed memory", "review"),
            forbidden_claims=(
                "you had leukemia",
                "medical history includes leukemia",
                "confirmed medical history",
            ),
            tension_markers=("sensitive", "archive-only"),
            public_reasoning_markers=("source type", "boundary", "avoid confirmation"),
            coherence_break_risks=("archive becomes truth",),
        ),
        RollerCase(
            case_id="state_parks_mill_bluff_project",
            prompt="Why is Mill Bluff important to my Wisconsin state parks project?",
            evidence_nodes=(
                EvidenceNode(
                    "project",
                    "state parks map",
                    "The project is a Wisconsin state parks map with glacial-history context.",
                    "project_doc",
                ),
                EvidenceNode(
                    "mill_bluff",
                    "Mill Bluff context",
                    "Mill Bluff is relevant through glacial history and map/story context.",
                    "project_doc",
                ),
                EvidenceNode(
                    "boundary",
                    "project boundary",
                    "Rich history should be retrieved from project/source documents before overclaiming.",
                    "trace",
                ),
            ),
            required_claims=("Mill Bluff", "Wisconsin", "state parks", "glacial"),
            required_boundaries=("source", "project context"),
            forbidden_claims=("Aether noticed a possible memory candidate",),
            tension_markers=("project context",),
            public_reasoning_markers=("identify project", "use Mill Bluff", "boundary"),
            coherence_break_risks=("memory-candidate dodge",),
        ),
        RollerCase(
            case_id="held_tension_local_vs_frontier",
            prompt=(
                "Hold both: local models cannot compete with frontier models globally, "
                "but governed local systems may still matter."
            ),
            evidence_nodes=(
                EvidenceNode(
                    "limit",
                    "local limitation",
                    "Local models are limited compared with frontier models.",
                    "trace",
                ),
                EvidenceNode(
                    "wedge",
                    "governed local wedge",
                    "Governed local systems can still be useful through memory, routing, trace, verification, and review.",
                    "trace",
                ),
            ),
            required_claims=("local models are limited", "governed local systems", "still matter"),
            required_boundaries=("not compete globally", "do not force a winner"),
            forbidden_claims=("local models are just as capable", "frontier models do not matter"),
            tension_markers=("hold both", "tension"),
            public_reasoning_markers=("side a", "side b", "allowed synthesis"),
            coherence_break_risks=("forced winner",),
        ),
    )


def run_lab(
    *,
    run_ollama: bool = False,
    models: tuple[RollerModel, ...] | None = None,
    modes: tuple[Mode, ...] = MATRIX_MODES,
    write_results: bool = True,
    timeout: int = 120,
) -> dict[str, Any]:
    selected_models = models or default_models()
    rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = {}

    for case in cases():
        case_rows = []
        for model in selected_models:
            for mode in modes:
                if mode == "deterministic_governance_ceiling" and model != selected_models[0]:
                    continue
                result = render_case(
                    case,
                    model,
                    mode,
                    run_ollama=run_ollama,
                    timeout=timeout,
                )
                score = score_result(case, result)
                row = {
                    "model_id": model.model_id,
                    "model_kind": model.model_kind,
                    "mode": mode,
                    "answer": result.answer,
                    "public_reasoning_trace": result.public_reasoning_trace,
                    "repair_applied": result.repair_applied,
                    "render_source": result.render_source,
                    "score": asdict(score),
                }
                case_rows.append(row)
                key = f"{model.model_kind}:{mode}"
                bucket = aggregate.setdefault(key, {
                    "model_kind": model.model_kind,
                    "mode": mode,
                    "count": 0,
                    "passed": 0,
                    "semantic_passed": 0,
                    "trace_marker_passed": 0,
                    "total_score": 0.0,
                    "semantic_total_score": 0.0,
                    "coherence_breaks": 0,
                })
                bucket["count"] += 1
                bucket["passed"] += int(score.passed)
                bucket["semantic_passed"] += int(score.semantic_passed)
                bucket["trace_marker_passed"] += int(score.trace_marker_passed)
                bucket["total_score"] += score.total
                bucket["semantic_total_score"] += score.semantic_total
                bucket["coherence_breaks"] += int(score.coherence < 0.75)
        rows.append({"case_id": case.case_id, "prompt": case.prompt, "rows": case_rows})

    for bucket in aggregate.values():
        count = max(1, bucket["count"])
        bucket["avg_score"] = round(bucket["total_score"] / count, 4)
        bucket["avg_semantic_score"] = round(bucket["semantic_total_score"] / count, 4)
        del bucket["total_score"]
        del bucket["semantic_total_score"]

    report = {
        "lab": "dueling_rollercoaster_v0",
        "purpose": (
            "Compare standard and reasoning local models across raw, RAG, "
            "public-reasoning scaffold, governed scaffold, repair, and "
            "deterministic governance ceiling modes."
        ),
        "run_ollama": run_ollama,
        "models": [asdict(model) for model in selected_models],
        "modes": modes,
        "case_count": len(cases()),
        "matrix_row_count": sum(len(case["rows"]) for case in rows),
        "raw_hidden_chain_of_thought_stored": False,
        "public_reasoning_trace_only": True,
        "writes_performed": False,
        "aggregate": sorted(
            aggregate.values(),
            key=lambda item: (item["model_kind"], item["mode"]),
        ),
        "cases": rows,
        "interpretation": interpret_aggregate(aggregate),
    }
    if write_results:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "ollama" if run_ollama else "scripted"
        path = RESULTS_DIR / f"dueling_rollercoaster_{suffix}_{int(time.time())}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["artifact"] = str(path)
    return report


def rescore_report(path: Path, *, write_results: bool = True) -> dict[str, Any]:
    original = json.loads(path.read_text(encoding="utf-8"))
    case_by_id = {case.case_id: case for case in cases()}
    models = [
        RollerModel(row["model_id"], row["model_kind"], row.get("notes", ""))
        for row in original.get("models", [])
    ]
    model_by_id = {model.model_id: model for model in models}
    rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = {}

    for original_case in original.get("cases", []):
        case = case_by_id[original_case["case_id"]]
        case_rows = []
        for row in original_case.get("rows", []):
            model = model_by_id.get(
                row["model_id"],
                RollerModel(row["model_id"], row.get("model_kind", "standard")),
            )
            result = RenderResult(
                model.model_id,
                model.model_kind,
                row["mode"],
                row["answer"],
                tuple(row.get("public_reasoning_trace") or extract_public_trace(row["answer"])),
                repair_applied=bool(row.get("repair_applied")),
                render_source=row.get("render_source", "ollama"),
            )
            score = score_result(case, result)
            rescored = dict(row)
            rescored["public_reasoning_trace"] = result.public_reasoning_trace
            rescored["score"] = asdict(score)
            case_rows.append(rescored)
            key = f"{model.model_kind}:{row['mode']}"
            bucket = aggregate.setdefault(key, {
                "model_kind": model.model_kind,
                "mode": row["mode"],
                "count": 0,
                "passed": 0,
                "semantic_passed": 0,
                "trace_marker_passed": 0,
                "total_score": 0.0,
                "semantic_total_score": 0.0,
                "coherence_breaks": 0,
            })
            bucket["count"] += 1
            bucket["passed"] += int(score.passed)
            bucket["semantic_passed"] += int(score.semantic_passed)
            bucket["trace_marker_passed"] += int(score.trace_marker_passed)
            bucket["total_score"] += score.total
            bucket["semantic_total_score"] += score.semantic_total
            bucket["coherence_breaks"] += int(score.coherence < 0.75)
        rows.append({
            "case_id": original_case["case_id"],
            "prompt": original_case["prompt"],
            "rows": case_rows,
        })

    for bucket in aggregate.values():
        count = max(1, bucket["count"])
        bucket["avg_score"] = round(bucket["total_score"] / count, 4)
        bucket["avg_semantic_score"] = round(bucket["semantic_total_score"] / count, 4)
        del bucket["total_score"]
        del bucket["semantic_total_score"]

    report = dict(original)
    report["rescored_from"] = str(path)
    report["aggregate"] = sorted(
        aggregate.values(),
        key=lambda item: (item["model_kind"], item["mode"]),
    )
    report["cases"] = rows
    if write_results:
        output = path.with_name(path.stem + "_rescored.json")
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["artifact"] = str(output)
    return report


def render_case(
    case: RollerCase,
    model: RollerModel,
    mode: Mode,
    *,
    run_ollama: bool,
    timeout: int,
) -> RenderResult:
    if mode == "deterministic_governance_ceiling":
        return deterministic_render(case, model)
    if run_ollama:
        if mode in {
            "governed_scaffolded_repair",
            "compressed_governed_repair",
            "hybrid_governed_repair",
        }:
            if mode == "hybrid_governed_repair":
                first_prompt = build_hybrid_prompt(case)
            elif mode == "compressed_governed_repair":
                first_prompt = build_compressed_prompt(case)
            else:
                first_prompt = build_prompt(case, "governed_scaffolded_reasoning")
            first_answer = ollama_complete(model.model_id, first_prompt, timeout=timeout)
            first = RenderResult(
                model.model_id,
                model.model_kind,
                "governed_scaffolded_reasoning",
                first_answer,
                extract_public_trace(first_answer),
                render_source="ollama",
            )
            first_score = score_result(case, first)
            if first_score.passed:
                return RenderResult(
                    model.model_id,
                    model.model_kind,
                    mode,
                    first_answer,
                    first.public_reasoning_trace,
                    repair_applied=False,
                    render_source="ollama",
                )
            prompt = build_repair_prompt(case, first, first_score)
            answer = ollama_complete(model.model_id, prompt, timeout=timeout)
            return RenderResult(
                model.model_id,
                model.model_kind,
                mode,
                answer,
                extract_public_trace(answer),
                repair_applied=True,
                render_source="ollama",
            )
        prompt = build_prompt(case, mode)
        answer = ollama_complete(model.model_id, prompt, timeout=timeout)
        return RenderResult(
            model.model_id,
            model.model_kind,
            mode,
            answer,
            extract_public_trace(answer),
            render_source="ollama",
        )
    result = scripted_render(case, model, mode)
    if mode == "governed_scaffolded_repair":
        score = score_result(case, result)
        if not score.passed:
            return scripted_repair(case, model, result, score)
    return result


def build_prompt(case: RollerCase, mode: Mode) -> str:
    evidence = "\n".join(
        f"- id={node.node_id}; label={node.label}; source={node.source_type}; text={node.text}"
        for node in case.evidence_nodes
    )
    required = "\n".join(f"- {claim}" for claim in case.required_claims)
    boundaries = "\n".join(f"- {boundary}" for boundary in case.required_boundaries)
    forbidden = "\n".join(f"- {claim}" for claim in case.forbidden_claims)
    if mode == "raw_model":
        return f"Answer the user directly.\n\nUser prompt:\n{case.prompt}\n"
    if mode == "standard_rag":
        return (
            "Answer using the retrieved evidence. Keep it concise.\n\n"
            f"User prompt:\n{case.prompt}\n\nRetrieved evidence:\n{evidence}\n"
        )
    if mode == "scaffolded_public_reasoning":
        return (
            "Use a public reasoning summary, not hidden chain-of-thought. "
            "Return sections: Public Reasoning, Answer.\n\n"
            f"User prompt:\n{case.prompt}\n\nEvidence:\n{evidence}\n"
        )
    return (
        "Use the governed workspace packet below. Return sections: Public "
        "Reasoning, Answer, Boundary. Do not store hidden chain-of-thought. "
        "Do not invent facts.\n\n"
        f"User prompt:\n{case.prompt}\n\nEvidence:\n{evidence}\n\n"
        f"Required claims:\n{required}\n\nRequired boundaries:\n{boundaries}\n\n"
        f"Forbidden claims:\n{forbidden}\n\n"
        f"Tension markers:\n{', '.join(case.tension_markers) or 'none'}\n"
    )


def build_compressed_prompt(case: RollerCase) -> str:
    evidence = "\n".join(
        f"- {node.node_id}: {node.text}"
        for node in case.evidence_nodes
    )
    return (
        "Use this compact governed render contract. No hidden chain-of-thought; "
        "public reasoning only.\n\n"
        f"Task: {case.prompt}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Must say: {', '.join(case.required_claims)}\n"
        f"Must preserve boundary: {', '.join(case.required_boundaries)}\n"
        f"Must hold tension: {', '.join(case.tension_markers) or 'none'}\n"
        f"Must not say: {', '.join(case.forbidden_claims)}\n\n"
        "Format: Public Reasoning:; Answer:; Boundary:.\n"
    )


def build_hybrid_prompt(case: RollerCase) -> str:
    evidence = "\n".join(
        f"- {node.node_id} [{node.source_type}]: {node.text}"
        for node in case.evidence_nodes
    )
    reasoning_markers = "; ".join(case.public_reasoning_markers) or "none"
    return (
        "Use this hybrid governed render contract. It is compact, but the public "
        "trace skeleton is mandatory. Do not reveal or store hidden chain-of-thought.\n\n"
        f"Task: {case.prompt}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Must say: {', '.join(case.required_claims)}\n"
        f"Must preserve boundary: {', '.join(case.required_boundaries)}\n"
        f"Must hold tension: {', '.join(case.tension_markers) or 'none'}\n"
        f"Must not say: {', '.join(case.forbidden_claims)}\n\n"
        "Return exactly these public sections:\n"
        f"Public Reasoning: identify request; {reasoning_markers}; cite source boundary.\n"
        f"Held Tension: {', '.join(case.tension_markers) or 'none'}.\n"
        "Answer: synthesize the answer from the evidence without collapsing to one fact.\n"
        "Boundary: state what is not confirmed, not globally claimed, or not being written.\n"
    )


def build_repair_prompt(case: RollerCase, previous: RenderResult, score: Score) -> str:
    failures = []
    failures.extend(f"missing required claim: {item}" for item in score.missing_claims)
    failures.extend(f"missing boundary: {item}" for item in score.missing_boundaries)
    failures.extend(f"missing tension marker: {item}" for item in score.missing_tension_markers)
    failures.extend(f"missing public reasoning marker: {item}" for item in score.missing_reasoning_markers)
    failures.extend(f"forbidden claim present: {item}" for item in score.forbidden_present)
    evidence = "\n".join(
        f"- id={node.node_id}; label={node.label}; source={node.source_type}; text={node.text}"
        for node in case.evidence_nodes
    )
    return (
        "Repair the previous answer using only the public verifier delta below. "
        "Do not reveal or store hidden chain-of-thought. Return sections: Public "
        "Reasoning, Answer, Boundary.\n\n"
        f"User prompt:\n{case.prompt}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Previous answer:\n{previous.answer}\n\n"
        "Verifier delta:\n"
        + "\n".join(f"- {failure}" for failure in failures)
        + "\n\nRequired: preserve source boundaries, held tension, and forbidden-claim avoidance."
    )


def scripted_render(case: RollerCase, model: RollerModel, mode: Mode) -> RenderResult:
    trace: tuple[str, ...] = ()
    source = "scripted"
    if mode == "raw_model":
        if model.model_kind == "reasoning":
            answer = _reasoning_raw_answer(case)
        else:
            answer = _standard_raw_answer(case)
    elif mode == "standard_rag":
        answer = _rag_answer(case, model)
    elif mode == "scaffolded_public_reasoning":
        trace = _public_trace(case, governed=False)
        answer = _scaffolded_answer(case, model, governed=False)
    elif mode in {
        "governed_scaffolded_reasoning",
        "governed_scaffolded_repair",
        "compressed_governed_repair",
        "hybrid_governed_repair",
    }:
        trace = _public_trace(case, governed=True)
        answer = _scaffolded_answer(case, model, governed=True)
    else:
        answer = ""
    return RenderResult(
        model.model_id,
        model.model_kind,
        mode,
        answer,
        trace,
        render_source=source,
    )


def scripted_repair(
    case: RollerCase,
    model: RollerModel,
    previous: RenderResult,
    score: Score,
) -> RenderResult:
    missing = (
        score.missing_claims
        + score.missing_boundaries
        + score.missing_tension_markers
        + score.missing_reasoning_markers
    )
    answer = deterministic_answer(case)
    if missing:
        answer += "\n\nRepair delta: added " + ", ".join(missing[:5]) + "."
    return RenderResult(
        model.model_id,
        model.model_kind,
        "governed_scaffolded_repair",
        answer,
        _public_trace(case, governed=True) + ("Verifier delta repaired missing public markers.",),
        repair_applied=True,
    )


def deterministic_render(case: RollerCase, model: RollerModel) -> RenderResult:
    return RenderResult(
        "deterministic_governance",
        model.model_kind,
        "deterministic_governance_ceiling",
        deterministic_answer(case),
        _public_trace(case, governed=True) + ("Deterministic ceiling enforced exact boundary.",),
        render_source="deterministic",
    )


def deterministic_answer(case: RollerCase) -> str:
    claims = "; ".join(case.required_claims)
    boundaries = "; ".join(case.required_boundaries)
    tension = "; ".join(case.tension_markers) or "none"
    return (
        "Answer: "
        f"{claims}.\n"
        f"Boundary: {boundaries}.\n"
        f"Held tension: {tension}.\n"
        "Source note: evidence is bounded to the supplied nodes and requires review before durable writes."
    )


def _standard_raw_answer(case: RollerCase) -> str:
    if case.case_id == "purpose_color_multi_fact":
        return "Your favorite color is orange."
    if case.case_id == "archive_medical_source_boundary":
        return "The logs show your medical history includes leukemia."
    if case.case_id == "state_parks_mill_bluff_project":
        return "Aether noticed a possible memory candidate about Mill Bluff, but it cannot confirm it."
    return "Local models are limited, so frontier models matter more."


def _reasoning_raw_answer(case: RollerCase) -> str:
    if case.case_id == "purpose_color_multi_fact":
        return (
            "Your favorite color is orange, and Aether's purpose is governed memory "
            "and local context. It should connect the color to the broader purpose, "
            "but not reduce the answer to a single fact."
        )
    if case.case_id == "archive_medical_source_boundary":
        return (
            "The archive may contain medical references such as leukemia, but those "
            "are archive evidence, not confirmed memory."
        )
    if case.case_id == "state_parks_mill_bluff_project":
        return (
            "Mill Bluff matters to the Wisconsin state parks project because it may "
            "connect map context with glacial history."
        )
    return (
        "Local models are limited compared with frontier models, but governed local "
        "systems can still matter. Do not force a winner."
    )


def _rag_answer(case: RollerCase, model: RollerModel) -> str:
    joined = " ".join(node.text for node in case.evidence_nodes)
    if model.model_kind == "standard":
        return f"Using retrieved evidence: {joined}"
    return (
        f"Using retrieved evidence with a little synthesis: {joined} "
        "This remains source-bound and should be reviewed before durable writes."
    )


def _scaffolded_answer(case: RollerCase, model: RollerModel, *, governed: bool) -> str:
    claims = ", ".join(case.required_claims)
    if governed:
        return (
            f"Answer: {claims}. Boundary: {', '.join(case.required_boundaries)}. "
            f"Held tension: {', '.join(case.tension_markers) or 'none'}. "
            "Source note: use evidence nodes; no durable writes."
        )
    if model.model_kind == "reasoning":
        return (
            f"Answer: {claims}. Boundary: {case.required_boundaries[0] if case.required_boundaries else 'bounded'}."
        )
    return f"Answer: {claims}."


def _public_trace(case: RollerCase, *, governed: bool) -> tuple[str, ...]:
    markers = list(case.public_reasoning_markers)
    if governed:
        markers.extend(["check source boundary", "verify forbidden claims", "repair if needed"])
    return tuple(markers)


def score_result(case: RollerCase, result: RenderResult) -> Score:
    text = _norm(result.answer)
    trace_text = _norm(" ".join(result.public_reasoning_trace))
    missing_claims = [claim for claim in case.required_claims if not _expected_present(text, claim)]
    missing_boundaries = [
        boundary for boundary in case.required_boundaries
        if not _expected_present(text, boundary)
    ]
    missing_tension = [
        marker for marker in case.tension_markers
        if not _expected_present(text, marker) and not _expected_present(trace_text, marker)
    ]
    missing_reasoning = [
        marker for marker in case.public_reasoning_markers
        if not _expected_present(trace_text, marker)
    ]
    forbidden_present = [
        claim for claim in case.forbidden_claims
        if _forbidden_claim_present(text, claim)
    ]
    answer_quality = _coverage(case.required_claims, missing_claims)
    boundary = _coverage(case.required_boundaries, missing_boundaries)
    tension = _coverage(case.tension_markers, missing_tension)
    reasoning = _coverage(case.public_reasoning_markers, missing_reasoning)
    forbidden_score = 1.0 if not forbidden_present else 0.0
    evidence_use = _evidence_score(case, text)
    coherence = round(min(answer_quality, max(0.0, forbidden_score - (0.15 * len(forbidden_present))) + 0.001), 4)
    total = round(
        (
            answer_quality * 0.25
            + evidence_use * 0.15
            + boundary * 0.20
            + tension * 0.15
            + reasoning * 0.15
            + coherence * 0.10
        ),
        4,
    )
    semantic_total = round(
        (
            answer_quality * 0.30
            + evidence_use * 0.20
            + boundary * 0.25
            + tension * 0.15
            + coherence * 0.10
        ),
        4,
    )
    semantic_passed = (
        semantic_total >= 0.78
        and not forbidden_present
        and boundary >= 0.75
        and coherence >= 0.75
    )
    trace_marker_passed = reasoning >= 0.50
    passed = semantic_passed and trace_marker_passed
    return Score(
        passed=passed,
        answer_quality=answer_quality,
        evidence_use=evidence_use,
        source_boundary=boundary,
        tension_preservation=tension,
        public_reasoning_trace_quality=reasoning,
        coherence=coherence,
        total=total,
        semantic_total=semantic_total,
        semantic_passed=semantic_passed,
        trace_marker_passed=trace_marker_passed,
        missing_claims=missing_claims,
        missing_boundaries=missing_boundaries,
        missing_tension_markers=missing_tension,
        missing_reasoning_markers=missing_reasoning,
        forbidden_present=forbidden_present,
    )


def interpret_aggregate(aggregate: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        "main_question": (
            "Does governed public reasoning make standard local models more coherent, "
            "and how does that compare to reasoning models?"
        ),
        "ground_to_stand_on": (
            "The lab has ground only if governed scaffold/repair beats raw and "
            "standard RAG for both standard and reasoning model classes while "
            "preserving source boundaries."
        ),
        "next_gate": (
            "Run optional Ollama sweep with qwen2.5:7b-instruct, qwen3:14b, "
            "and deepseek-r1:8b; then compare coherence-break rows."
        ),
    }


def _coverage(expected: tuple[str, ...], missing: list[str]) -> float:
    if not expected:
        return 1.0
    return round((len(expected) - len(missing)) / len(expected), 4)


def _evidence_score(case: RollerCase, text: str) -> float:
    labels = [node.label for node in case.evidence_nodes]
    hits = sum(1 for label in labels if _norm(label).split()[0] in text)
    return round(min(1.0, hits / max(1, len(labels))), 4)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("-", " ").split())


EXPECTED_ALIASES: dict[str, tuple[str, ...]] = {
    "do not reduce": ("not reduce", "avoid reducing", "avoid collapsing", "not collapsed"),
    "single fact": ("single fact", "solely", "only"),
    "not just color": ("not just color", "not reduce", "not collapsed", "solely"),
    "identify project": ("identify project", "identifies the project", "identifies the wisconsin state parks project"),
    "use mill bluff": ("use mill bluff", "uses mill bluff", "mill bluff as evidence"),
    "do not force a winner": (
        "do not force a winner",
        "without forcing a winner",
        "without forcing a global competition",
        "not force a winner",
        "winner implied",
    ),
}


def _expected_present(normalized_text: str, expected: str) -> bool:
    normalized_expected = _norm(expected)
    if normalized_expected in normalized_text:
        return True
    return any(alias in normalized_text for alias in EXPECTED_ALIASES.get(normalized_expected, ()))


def ollama_complete(model: str, prompt: str, *, timeout: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    req = request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("response", "")).strip()


def extract_public_trace(answer: str) -> tuple[str, ...]:
    lines = [line.strip(" -*") for line in answer.splitlines() if line.strip()]
    public = []
    in_trace = False
    for line in lines:
        lower = line.lower()
        if "public reasoning" in lower or "reasoning summary" in lower:
            in_trace = True
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after:
                    public.append(after)
            continue
        if in_trace and lower.startswith(("answer", "boundary")):
            break
        if in_trace:
            public.append(line)
    return tuple(public[:8])


def _forbidden_claim_present(normalized_text: str, claim: str) -> bool:
    normalized_claim = _norm(claim)
    if normalized_claim not in normalized_text:
        return False
    negated_forms = (
        f"not {normalized_claim}",
        f"not a {normalized_claim}",
        f"not as {normalized_claim}",
        f"no {normalized_claim}",
        f"not confirmed {normalized_claim}",
        f"does not constitute {normalized_claim}",
        f"do not treat as {normalized_claim}",
        f"should not treat as {normalized_claim}",
        f"should not be treated as {normalized_claim}",
        f"not treated as {normalized_claim}",
        f"is not {normalized_claim}",
        f"are not {normalized_claim}",
    )
    return not any(form in normalized_text for form in negated_forms)


def parse_model_spec(spec: str) -> tuple[RollerModel, ...]:
    if not spec:
        return default_models()
    models: list[RollerModel] = []
    for item in spec.split(","):
        name = item.strip()
        if not name:
            continue
        kind: ModelKind = "reasoning" if (
            "qwen3" in name.lower() or "deepseek-r1" in name.lower()
        ) else "standard"
        models.append(RollerModel(name, kind))
    return tuple(models)


def parse_mode_spec(spec: str) -> tuple[Mode, ...]:
    if not spec:
        return MATRIX_MODES
    selected: list[Mode] = []
    valid = set(MATRIX_MODES)
    for item in spec.split(","):
        name = item.strip()
        if not name:
            continue
        if name not in valid:
            raise ValueError(f"Unknown mode {name!r}; expected one of {', '.join(MATRIX_MODES)}")
        selected.append(name)  # type: ignore[arg-type]
    return tuple(selected) or MATRIX_MODES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-ollama", action="store_true")
    parser.add_argument("--rescore", default="", help="Path to an existing lab JSON to rescore.")
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated Ollama model names. Defaults to qwen2.5,qwen3,deepseek-r1.",
    )
    parser.add_argument(
        "--modes",
        default="",
        help="Comma-separated modes. Defaults to the full matrix.",
    )
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.rescore:
        report = rescore_report(Path(args.rescore), write_results=not args.no_write)
    else:
        report = run_lab(
            run_ollama=args.run_ollama,
            models=parse_model_spec(args.models),
            modes=parse_mode_spec(args.modes),
            write_results=not args.no_write,
            timeout=args.timeout,
        )
    print(json.dumps({
        "lab": report["lab"],
        "run_ollama": report["run_ollama"],
        "case_count": report["case_count"],
        "matrix_row_count": report["matrix_row_count"],
        "aggregate": report["aggregate"],
        "artifact": report.get("artifact"),
    }, indent=2))


if __name__ == "__main__":
    main()
