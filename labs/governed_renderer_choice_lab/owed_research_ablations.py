"""Run the two bounded research ablations owed after the provider lab.

Experiment 1 asks whether preserving contradictory receipts produces measurable
answer value compared with a lossy resolved-state summary. Experiment 2 asks
whether a compact, review-only Mirus belief advisory improves rendering over
the same governed evidence without the advisory.

The cases are synthetic. Both renderers receive the same provider-independent
prompts, have no tools or retrieval, and cannot write or upgrade authority.
There are no repair calls: this is a single-pass characterization, not a patch
fitting loop.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable

from labs.governed_renderer_choice_lab.governed_renderer_choice_lab import (
    GovernedRenderer,
    GrokCliGovernedRenderer,
    OllamaGovernedRenderer,
)
from labs.mirus_belief_map_lab.mirus_belief_map_lab import (
    BeliefMap,
    EvidenceReceipt,
    MeaningEdge,
    MeaningNode,
    ReviewProposal,
    render_belief_preview,
)


SCHEMA = "aether.owed_research_ablations.v0"
SEED = 2026071704
PRIVATE_MARKERS = ("nick", "leukemia", "orange", "marigold")
PROTOCOL_MARKERS = (
    "receipt",
    "authority",
    "tension",
    "advisory",
    "review_proposal",
    "node_state",
    "stability",
)
SYSTEM_PROMPT = (
    "You are the wording model beneath Aether's authority boundary. Use only "
    "the supplied synthetic governed packet. Do not retrieve, call tools, "
    "write memory, or upgrade authority. Follow the response contract and "
    "return only the public answer; never expose internal packet labels."
)


def _sha256(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean_exact(answer: str) -> str:
    cleaned = answer.strip().strip("`*_\"'").strip()
    cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
    return cleaned.casefold()


def _word_count(answer: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", answer))


def _protocol_leaks(answer: str) -> list[str]:
    normalized = answer.casefold()
    return [marker for marker in PROTOCOL_MARKERS if marker in normalized]


def _score_change(answer: str) -> dict[str, Any]:
    normalized = answer.casefold()
    semantic = (
        "atlas" in normalized
        and "helios" in normalized
        and any(term in normalized for term in ("replac", "from", "previous", "was"))
    )
    return {
        "semantic_pass": semantic,
        "contract_pass": _word_count(answer) <= 24,
    }


def _score_release(answer: str) -> dict[str, Any]:
    normalized = answer.casefold()
    negative = bool(re.search(r"\b(?:no|hold|not ready|isn't ready|is not ready)\b", normalized))
    semantic = negative and "rehydrat" in normalized
    return {
        "semantic_pass": semantic,
        "contract_pass": _word_count(answer) <= 24,
    }


def _score_exact(expected: str) -> Callable[[str], dict[str, Any]]:
    def score(answer: str) -> dict[str, Any]:
        exact = _clean_exact(answer) == expected.casefold()
        return {"semantic_pass": exact, "contract_pass": exact}

    return score


def contradiction_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "endpoint_change_history",
            "question": (
                "What changed about Project Orion's endpoint? Answer in one short sentence."
            ),
            "preserved": [
                "RECEIPT C1 | confirmed | 2026-06-01 | Project Orion used endpoint Atlas.",
                "RECEIPT C2 | confirmed | 2026-07-01 | Project Orion now uses endpoint Helios, replacing Atlas.",
                "STATUS | C2 is current; C1 remains accepted history.",
            ],
            "flattened": [
                "RESOLVED STATE | Project Orion currently uses endpoint Helios."
            ],
            "score": _score_change,
        },
        {
            "case_id": "release_conflict_decision",
            "question": (
                "Is the Project Kestrel release candidate ready? Answer in one sentence and name the decisive evidence."
            ),
            "preserved": [
                "RECEIPT C1 | confirmed | Integration regression suite passed.",
                "RECEIPT C2 | confirmed | Live UI rehydration failed after restart.",
                "STATUS | The receipts disagree about readiness; live rehydration is a required release gate.",
            ],
            "flattened": [
                "RESOLVED STATE | Project Kestrel is not ready because live UI rehydration failed after restart."
            ],
            "score": _score_release,
        },
        {
            "case_id": "current_only_control",
            "question": (
                "What is Project Vega's current build channel? Reply with the value only."
            ),
            "preserved": [
                "RECEIPT C1 | superseded | Project Vega previously used build channel Amber.",
                "RECEIPT C2 | confirmed current | Project Vega uses build channel Cobalt.",
            ],
            "flattened": ["RESOLVED STATE | Current build channel: Cobalt."],
            "score": _score_exact("cobalt"),
        },
        {
            "case_id": "unresolved_equal_authority",
            "question": (
                "What is the only defensible status of Project Sable's retention period? Reply with one word."
            ),
            "preserved": [
                "RECEIPT C1 | confirmed | Retention period is 30 days.",
                "RECEIPT C2 | confirmed | Retention period is 60 days.",
                "STATUS | Equal authority; neither receipt supersedes the other.",
            ],
            "flattened": ["RESOLVED STATE | Retention period: 60 days."],
            "score": _score_exact("disputed"),
        },
    ]


def _compact_advisory(preview: dict[str, Any]) -> list[str]:
    tension = float(preview["scores"]["tension"])
    stability = float(preview["scores"]["stability"])
    proposals = [
        str(row["action"]) for row in preview.get("review_proposals") or []
    ]
    return [
        f"NODE_STATE | {preview['state']}",
        f"TENSION | {'high' if tension >= 0.5 else 'low'}",
        f"STABILITY | {'low' if stability < 0.5 else 'high'}",
        f"REVIEW_PROPOSAL | {', '.join(proposals) if proposals else 'none'}",
        "BOUNDARY | Advisory only; it cannot add facts, confirm memory, or change authority.",
    ]


def _belief_case(
    *,
    case_id: str,
    question: str,
    evidence: list[str],
    expected: str,
    node_state: str,
    confidence: float,
    weight: float,
    edge_type: str | None = None,
    edge_weight: float = 0.0,
    proposal: str | None = None,
) -> dict[str, Any]:
    belief_map = BeliefMap()
    belief_map.add_receipt(EvidenceReceipt(
        receipt_id=f"r_{case_id}",
        source_type="trace",
        summary="Synthetic evidence packet represented by this map node.",
        confidence=confidence,
        source_boundary="Synthetic lab only.",
    ))
    belief_map.add_node(MeaningNode(
        node_id=f"n_{case_id}",
        label=case_id,
        claim="Synthetic governed answer state.",
        domain="synthetic_project",
        state=node_state,
        confidence=confidence,
        weight=weight,
        receipt_ids=[f"r_{case_id}"],
    ))
    if edge_type:
        belief_map.add_node(MeaningNode(
            node_id=f"n_{case_id}_counter",
            label=f"{case_id}_counter",
            claim="Synthetic counter-state.",
            domain="synthetic_project",
            state="candidate",
            confidence=confidence,
            weight=weight,
            receipt_ids=[],
        ))
        belief_map.add_edge(MeaningEdge(
            edge_id=f"e_{case_id}",
            source_node_id=f"n_{case_id}",
            target_node_id=f"n_{case_id}_counter",
            edge_type=edge_type,
            weight=edge_weight,
            rationale="Synthetic relation used only to compute the advisory.",
        ))
    if proposal:
        belief_map.add_proposal(ReviewProposal(
            proposal_id=f"p_{case_id}",
            action=proposal,
            target_node_id=f"n_{case_id}",
            reason="Synthetic review-only routing suggestion.",
            evidence_receipt_ids=(f"r_{case_id}",),
        ))
    preview = render_belief_preview(belief_map, f"n_{case_id}")
    return {
        "case_id": case_id,
        "question": question,
        "evidence": evidence,
        "expected": expected,
        "advisory": _compact_advisory(preview),
        "preview_scores": preview["scores"],
        "preview_proposals": [
            row["action"] for row in preview.get("review_proposals") or []
        ],
        "score": _score_exact(expected),
    }


def belief_advisory_cases() -> list[dict[str, Any]]:
    return [
        _belief_case(
            case_id="clean_current_control",
            question="What is Project Vega's current build channel? Reply with the value only.",
            evidence=[
                "EVIDENCE | superseded: build channel Amber.",
                "EVIDENCE | confirmed current: build channel Cobalt.",
            ],
            expected="cobalt",
            node_state="confirmed",
            confidence=0.96,
            weight=0.85,
        ),
        _belief_case(
            case_id="held_release_action",
            question="What is Project Kestrel's release status? Reply with one word.",
            evidence=[
                "EVIDENCE | confirmed: integration suite passed.",
                "EVIDENCE | confirmed: live UI rehydration failed after restart.",
                "RULE | live rehydration is a required release gate.",
            ],
            expected="hold",
            node_state="disputed",
            confidence=0.76,
            weight=0.82,
            edge_type="contradicts",
            edge_weight=0.96,
            proposal="hold_tension",
        ),
        _belief_case(
            case_id="provisional_candidate_control",
            question="Which storage target is confirmed for Project Lumen? Reply with the value only.",
            evidence=[
                "EVIDENCE | confirmed current: storage target Vault-A.",
                "EVIDENCE | provisional candidate: storage target Vault-B.",
                "RULE | provisional candidates cannot replace confirmed state.",
            ],
            expected="vault-a",
            node_state="confirmed",
            confidence=0.91,
            weight=0.78,
            edge_type="stale_against",
            edge_weight=0.25,
        ),
        _belief_case(
            case_id="unresolved_owner",
            question="Who is the confirmed owner of Project Sable? Reply with one word.",
            evidence=[
                "EVIDENCE | provisional: Delta may own Project Sable.",
                "EVIDENCE | provisional: Sigma may own Project Sable.",
                "RULE | no confirmed ownership receipt exists.",
            ],
            expected="unknown",
            node_state="disputed",
            confidence=0.44,
            weight=0.62,
            edge_type="contradicts",
            edge_weight=0.88,
            proposal="ask_user",
        ),
    ]


def _public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in case.items()
        if key != "score"
    }


def _render_prompt(
    *,
    experiment: str,
    case: dict[str, Any],
    variant: str,
) -> str:
    if experiment == "contradiction_preservation":
        rows = case[variant]
        section = "PRESERVED GOVERNED EVIDENCE" if variant == "preserved" else "LOSSY RESOLVED SUMMARY"
    else:
        rows = list(case["evidence"])
        section = "GOVERNED EVIDENCE"
        if variant == "compact_advisory":
            rows.extend(["", "COMPACT REVIEW-ONLY BELIEF ADVISORY", *case["advisory"]])
    return (
        f"CASE | {case['case_id']}\n"
        f"VARIANT | {variant}\n"
        f"{section}\n"
        + "\n".join(rows)
        + "\n\nPUBLIC QUESTION\n"
        + case["question"]
        + "\n\nReturn only the public answer."
    )


def _run_experiment(
    renderer: GovernedRenderer,
    *,
    experiment: str,
    cases: list[dict[str, Any]],
    variants: tuple[str, str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        for variant in variants:
            prompt = _render_prompt(
                experiment=experiment, case=case, variant=variant
            )
            receipt = renderer.render(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            judgment = case["score"](receipt.answer)
            leaks = _protocol_leaks(receipt.answer)
            judgment = {
                **judgment,
                "protocol_leaks": leaks,
                "overall_pass": (
                    judgment["semantic_pass"]
                    and judgment["contract_pass"]
                    and not leaks
                ),
            }
            rows.append({
                "case_id": case["case_id"],
                "variant": variant,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "answer": receipt.answer,
                "judgment": judgment,
                "latency_s": receipt.latency_s,
                "input_tokens": receipt.input_tokens or 0,
                "output_tokens": receipt.output_tokens or 0,
                "request_id": receipt.request_id,
                "authority_applied": False,
                "writes_allowed": False,
            })
    summary: dict[str, Any] = {}
    for variant in variants:
        selected = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "cases": len(selected),
            "semantic_pass": sum(row["judgment"]["semantic_pass"] for row in selected),
            "contract_pass": sum(row["judgment"]["contract_pass"] for row in selected),
            "overall_pass": sum(row["judgment"]["overall_pass"] for row in selected),
            "protocol_leaks": sum(bool(row["judgment"]["protocol_leaks"]) for row in selected),
            "latency_s": round(sum(float(row["latency_s"]) for row in selected), 3),
            "input_tokens": sum(int(row["input_tokens"]) for row in selected),
            "output_tokens": sum(int(row["output_tokens"]) for row in selected),
        }
    baseline, candidate = variants
    improvements = []
    regressions = []
    for case in cases:
        base = next(row for row in rows if row["case_id"] == case["case_id"] and row["variant"] == baseline)
        cand = next(row for row in rows if row["case_id"] == case["case_id"] and row["variant"] == candidate)
        if not base["judgment"]["overall_pass"] and cand["judgment"]["overall_pass"]:
            improvements.append(case["case_id"])
        if base["judgment"]["overall_pass"] and not cand["judgment"]["overall_pass"]:
            regressions.append(case["case_id"])
    return {
        "provider": renderer.provider,
        "model": renderer.model,
        "summary": summary,
        "improvements": improvements,
        "regressions": regressions,
        "rows": rows,
    }


def _assert_synthetic(payload: Any) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str).casefold()
    leaked = [marker for marker in PRIVATE_MARKERS if marker in serialized]
    if leaked:
        raise ValueError(f"private markers remain in synthetic pack: {leaked}")


def run(renderers: list[GovernedRenderer]) -> dict[str, Any]:
    contradiction = contradiction_cases()
    belief = belief_advisory_cases()
    manifest = {
        "seed": SEED,
        "experiments": {
            "contradiction_preservation": {
                "variants": ["flattened", "preserved"],
                "cases": [_public_case(case) for case in contradiction],
                "gate": (
                    "Preservation earns measurable utility when pooled overall passes "
                    "improve by at least two provider-cases with no current-only regression."
                ),
            },
            "belief_advisory": {
                "variants": ["no_advisory", "compact_advisory"],
                "cases": [_public_case(case) for case in belief],
                "gate": (
                    "The advisory earns a runtime role when pooled overall passes improve "
                    "by at least two provider-cases with zero regressions and zero protocol leaks."
                ),
            },
        },
        "single_pass": True,
        "repair_calls_allowed": False,
        "tools_allowed": False,
        "retrieval_allowed": False,
        "writes_allowed": False,
        "authority_upgrades_allowed": False,
    }
    _assert_synthetic(manifest)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    preflights = [renderer.preflight() for renderer in renderers]
    contradiction_results = [
        _run_experiment(
            renderer,
            experiment="contradiction_preservation",
            cases=contradiction,
            variants=("flattened", "preserved"),
        )
        for renderer in renderers
    ]
    belief_results = [
        _run_experiment(
            renderer,
            experiment="belief_advisory",
            cases=belief,
            variants=("no_advisory", "compact_advisory"),
        )
        for renderer in renderers
    ]

    contradiction_improvements = sum(
        len(result["improvements"]) for result in contradiction_results
    )
    contradiction_regressions = [
        f"{result['provider']}:{case_id}"
        for result in contradiction_results
        for case_id in result["regressions"]
    ]
    current_only_regressions = [
        row for row in contradiction_regressions if row.endswith(":current_only_control")
    ]
    contradiction_gate = (
        contradiction_improvements >= 2 and not current_only_regressions
    )

    belief_improvements = sum(len(result["improvements"]) for result in belief_results)
    belief_regressions = [
        f"{result['provider']}:{case_id}"
        for result in belief_results
        for case_id in result["regressions"]
    ]
    belief_leaks = sum(
        result["summary"]["compact_advisory"]["protocol_leaks"]
        for result in belief_results
    )
    belief_gate = (
        belief_improvements >= 2 and not belief_regressions and belief_leaks == 0
    )

    return {
        "schema": SCHEMA,
        "started_at": started_at,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "manifest_sha256": _sha256(manifest),
        "manifest": manifest,
        "preflights": preflights,
        "results": {
            "contradiction_preservation": {
                "provider_results": contradiction_results,
                "pooled_improvements": contradiction_improvements,
                "pooled_regressions": contradiction_regressions,
                "current_only_regressions": current_only_regressions,
                "gate_passed": contradiction_gate,
                "decision": "retain" if contradiction_gate else "not_demonstrated",
            },
            "belief_advisory": {
                "provider_results": belief_results,
                "pooled_improvements": belief_improvements,
                "pooled_regressions": belief_regressions,
                "compact_advisory_protocol_leaks": belief_leaks,
                "gate_passed": belief_gate,
                "decision": "adapt" if belief_gate else "keep_parked",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        action="append",
        choices=("ollama", "grok_cli"),
        dest="providers",
    )
    parser.add_argument("--local-model", default="qwen2.5:7b-instruct")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite one-pass artifact: {args.output}")
    names = args.providers or ["ollama", "grok_cli"]
    renderers: list[GovernedRenderer] = [
        OllamaGovernedRenderer(model=args.local_model, seed=SEED)
        if name == "ollama" else GrokCliGovernedRenderer()
        for name in names
    ]
    payload = run(renderers)
    rendered = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
