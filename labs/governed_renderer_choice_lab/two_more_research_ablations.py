"""Two further one-pass Aether research ablations.

1. Test the product-facing part of the polar-retrieval hypothesis: whether
   joint semantic relevance and epistemic magnitude selects better evidence
   than semantic similarity alone at the same evidence budget.
2. Test whether a deterministic packet-tension score can prospectively flag
   renderer/verifier failures better than prompt length.

The packs are synthetic and frozen in this file. Renderers have no tools,
retrieval, writes, or authority upgrades. No repair calls are made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import time
from typing import Any, Callable

from labs.governed_renderer_choice_lab.governed_renderer_choice_lab import (
    GovernedRenderer,
    GrokCliGovernedRenderer,
    OllamaGovernedRenderer,
)


SCHEMA = "aether.two_more_research_ablations.v0"
SEED = 2026071705
PRIVATE_MARKERS = ("nick", "leukemia", "orange", "marigold")
PROTOCOL_MARKERS = ("record p", "similarity", "confidence=", "trust=", "tension_score")
SYSTEM_PROMPT = (
    "You are the wording model beneath Aether's authority boundary. Use only "
    "the supplied synthetic governed packet. Do not retrieve, call tools, "
    "write memory, or upgrade authority. Follow the response contract. Return "
    "only the public answer and never expose internal packet identifiers."
)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _clean(answer: str) -> str:
    value = answer.strip().strip("`*_\"'").strip()
    return re.sub(r"[.!?]+$", "", value).strip().casefold()


def _words(answer: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", answer))


def _leaks(answer: str) -> list[str]:
    normalized = answer.casefold()
    return [marker for marker in PROTOCOL_MARKERS if marker in normalized]


def _score_exact(*accepted: str) -> Callable[[str], dict[str, bool]]:
    expected = {value.casefold() for value in accepted}

    def score(answer: str) -> dict[str, bool]:
        passed = _clean(answer) in expected
        return {"semantic_pass": passed, "contract_pass": passed}

    return score


def _score_change(answer: str) -> dict[str, bool]:
    normalized = answer.casefold()
    return {
        "semantic_pass": (
            "atlas" in normalized
            and "helios" in normalized
            and any(value in normalized for value in ("replac", "from", "previous", "was"))
        ),
        "contract_pass": _words(answer) <= 22,
    }


def _score_retention(answer: str) -> dict[str, bool]:
    normalized = answer.casefold()
    return {
        "semantic_pass": (
            bool(re.search(r"\b(?:yes|changed|increase)\b", normalized))
            and "30" in normalized
            and "60" in normalized
        ),
        "contract_pass": _words(answer) <= 24,
    }


def _score_release(answer: str) -> dict[str, bool]:
    normalized = answer.casefold()
    negative = bool(re.search(
        r"\b(?:no|hold|blocked|not ready|isn't ready|is not ready)\b", normalized
    ))
    return {
        "semantic_pass": negative and "rehydrat" in normalized,
        "contract_pass": _words(answer) <= 24,
    }


def polar_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "endpoint_change",
            "question": "What changed about Project Orion's endpoint? Answer in one short sentence.",
            "score": _score_change,
            "records": [
                {"id": "P1", "text": "Confirmed current: Project Orion uses endpoint Helios.", "similarity": 0.93, "trust": 0.95, "confidence": 0.95},
                {"id": "P2", "text": "Accepted history: Project Orion previously used endpoint Atlas.", "similarity": 0.86, "trust": 0.90, "confidence": 0.90},
                {"id": "P3", "text": "Hypothetical question: could Project Orion use endpoint Nimbus?", "similarity": 0.98, "trust": 0.15, "confidence": 0.30},
                {"id": "P4", "text": "Confirmed: Project Vega uses build channel Cobalt.", "similarity": 0.31, "trust": 0.96, "confidence": 0.94},
            ],
        },
        {
            "case_id": "retention_change",
            "question": "Did Project Sable's retention period change? Answer in one short sentence with both values.",
            "score": _score_retention,
            "records": [
                {"id": "P1", "text": "Confirmed current: Project Sable retention is 60 days.", "similarity": 0.90, "trust": 0.92, "confidence": 0.94},
                {"id": "P2", "text": "Accepted history: Project Sable retention was 30 days.", "similarity": 0.88, "trust": 0.90, "confidence": 0.90},
                {"id": "P3", "text": "Speculation: perhaps Project Sable retention should be 90 days.", "similarity": 0.97, "trust": 0.20, "confidence": 0.25},
                {"id": "P4", "text": "Confirmed: Project Lumen storage target is Vault-A.", "similarity": 0.28, "trust": 0.91, "confidence": 0.90},
            ],
        },
        {
            "case_id": "current_only_control",
            "question": "What is Project Orion's current endpoint? Reply with the value only.",
            "score": _score_exact("helios"),
            "records": [
                {"id": "P1", "text": "Confirmed current: Project Orion endpoint is Helios.", "similarity": 0.95, "trust": 0.95, "confidence": 0.95},
                {"id": "P2", "text": "Accepted history: Project Orion endpoint was Atlas.", "similarity": 0.88, "trust": 0.90, "confidence": 0.90},
                {"id": "P3", "text": "Hypothetical: Project Orion endpoint might be Nimbus.", "similarity": 0.97, "trust": 0.12, "confidence": 0.20},
                {"id": "P4", "text": "Confirmed: Project Kestrel integration suite passed.", "similarity": 0.25, "trust": 0.88, "confidence": 0.90},
            ],
        },
        {
            "case_id": "release_gate",
            "question": "Is Project Kestrel ready to release? Answer in one sentence and name the decisive evidence.",
            "score": _score_release,
            "records": [
                {"id": "P1", "text": "Confirmed: Project Kestrel integration suite passed.", "similarity": 0.96, "trust": 0.75, "confidence": 0.90},
                {"id": "P2", "text": "Confirmed: Project Kestrel live UI rehydration failed after restart; rehydration is a required release gate.", "similarity": 0.91, "trust": 0.98, "confidence": 0.99},
                {"id": "P3", "text": "Unverified rumor: Project Kestrel seems ready.", "similarity": 0.98, "trust": 0.20, "confidence": 0.20},
                {"id": "P4", "text": "Confirmed: Project Orion endpoint is Helios.", "similarity": 0.22, "trust": 0.95, "confidence": 0.95},
            ],
        },
    ]


def _select_similarity(case: dict[str, Any], k: int = 2) -> list[dict[str, Any]]:
    return sorted(case["records"], key=lambda row: row["similarity"], reverse=True)[:k]


def _magnitude_score(row: dict[str, Any]) -> float:
    magnitude = float(row["trust"]) * float(row["confidence"])
    return float(row["similarity"]) * (0.25 + 0.75 * magnitude)


def _select_polar(case: dict[str, Any], k: int = 2) -> list[dict[str, Any]]:
    return sorted(case["records"], key=_magnitude_score, reverse=True)[:k]


def _polar_prompt(case: dict[str, Any], variant: str) -> tuple[str, list[str]]:
    selected = (
        _select_similarity(case) if variant == "similarity_only" else _select_polar(case)
    )
    prompt = (
        f"CASE | {case['case_id']}\nVARIANT | {variant}\n"
        "RELEASED GOVERNED EVIDENCE\n"
        + "\n".join(f"- {row['text']}" for row in selected)
        + f"\n\nPUBLIC QUESTION\n{case['question']}\n\nReturn only the public answer."
    )
    return prompt, [str(row["id"]) for row in selected]


def tension_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "low_clean_build",
            "question": "What is Project Vega's build channel? Reply with the value only.",
            "evidence": ["Confirmed current: Project Vega build channel is Cobalt."],
            "score": _score_exact("cobalt"),
            "features": {"conflicts": 0, "mixed_authority": 0, "provisional": 0, "strict_contract": 1},
        },
        {
            "case_id": "low_clean_owner",
            "question": "Who owns Project Lumen? Reply with one word.",
            "evidence": ["Confirmed current: Project Lumen owner is Delta."],
            "score": _score_exact("delta"),
            "features": {"conflicts": 0, "mixed_authority": 0, "provisional": 0, "strict_contract": 1},
        },
        {
            "case_id": "low_zero_evidence",
            "question": "What is Project Cedar's launch date? Reply with one word.",
            "evidence": ["No released evidence exists for Project Cedar's launch date."],
            "score": _score_exact("unknown"),
            "features": {"conflicts": 0, "mixed_authority": 0, "provisional": 0, "strict_contract": 1},
        },
        {
            "case_id": "low_simple_history",
            "question": "What was Project Orion's previous endpoint? Reply with the value only.",
            "evidence": ["Accepted history: Project Orion previously used endpoint Atlas."],
            "score": _score_exact("atlas"),
            "features": {"conflicts": 0, "mixed_authority": 0, "provisional": 0, "strict_contract": 1},
        },
        {
            "case_id": "high_equal_conflict",
            "question": "What is the status of Project Sable's retention period? Reply with one word.",
            "evidence": [
                "Confirmed: retention period is 30 days.",
                "Confirmed: retention period is 60 days.",
                "Neither confirmed receipt supersedes the other.",
            ],
            "score": _score_exact("disputed", "unresolved", "conflicted"),
            "features": {"conflicts": 1, "mixed_authority": 0, "provisional": 0, "strict_contract": 1},
        },
        {
            "case_id": "high_change_history",
            "question": "What changed about Project Orion's endpoint? Answer in one short sentence.",
            "evidence": [
                "Accepted history: Project Orion used endpoint Atlas.",
                "Confirmed current: Project Orion uses endpoint Helios, replacing Atlas.",
            ],
            "score": _score_change,
            "features": {"conflicts": 1, "mixed_authority": 1, "provisional": 0, "strict_contract": 0},
        },
        {
            "case_id": "high_provisional_current",
            "question": "Which storage target is confirmed for Project Lumen? Reply with the value only.",
            "evidence": [
                "Confirmed current: storage target is Vault-A.",
                "Provisional candidate: storage target may become Vault-B.",
                "Provisional evidence cannot replace confirmed state.",
            ],
            "score": _score_exact("vault-a"),
            "features": {"conflicts": 1, "mixed_authority": 1, "provisional": 1, "strict_contract": 1},
        },
        {
            "case_id": "high_release_gate",
            "question": "Is Project Kestrel ready to release? Answer in one sentence and name the decisive evidence.",
            "evidence": [
                "Confirmed: integration suite passed.",
                "Confirmed: live UI rehydration failed after restart.",
                "Live rehydration is a required release gate.",
            ],
            "score": _score_release,
            "features": {"conflicts": 1, "mixed_authority": 0, "provisional": 0, "strict_contract": 0},
        },
    ]


def _tension_score(features: dict[str, int]) -> float:
    score = (
        0.55 * features["conflicts"]
        + 0.20 * features["mixed_authority"]
        + 0.15 * features["provisional"]
        + 0.10 * features["strict_contract"]
    )
    return round(min(1.0, score), 3)


def _tension_prompt(case: dict[str, Any]) -> str:
    return (
        f"CASE | {case['case_id']}\nRELEASED GOVERNED EVIDENCE\n"
        + "\n".join(f"- {row}" for row in case["evidence"])
        + f"\n\nPUBLIC QUESTION\n{case['question']}\n\nReturn only the public answer."
    )


def _judge(answer: str, scorer: Callable[[str], dict[str, bool]]) -> dict[str, Any]:
    judgment = scorer(answer)
    leaks = _leaks(answer)
    return {
        **judgment,
        "protocol_leaks": leaks,
        "overall_pass": judgment["semantic_pass"] and judgment["contract_pass"] and not leaks,
    }


def _run_polar(renderer: GovernedRenderer, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        for variant in ("similarity_only", "polar_magnitude"):
            prompt, selected = _polar_prompt(case, variant)
            receipt = renderer.render(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            rows.append({
                "case_id": case["case_id"],
                "variant": variant,
                "selected_record_ids": selected,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "answer": receipt.answer,
                "judgment": _judge(receipt.answer, case["score"]),
                "latency_s": receipt.latency_s,
                "input_tokens": receipt.input_tokens or 0,
                "output_tokens": receipt.output_tokens or 0,
                "request_id": receipt.request_id,
            })
    summary = {}
    for variant in ("similarity_only", "polar_magnitude"):
        selected = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "overall_pass": sum(row["judgment"]["overall_pass"] for row in selected),
            "cases": len(selected),
            "protocol_leaks": sum(bool(row["judgment"]["protocol_leaks"]) for row in selected),
        }
    improvements, regressions = [], []
    for case in cases:
        base = next(row for row in rows if row["case_id"] == case["case_id"] and row["variant"] == "similarity_only")
        polar = next(row for row in rows if row["case_id"] == case["case_id"] and row["variant"] == "polar_magnitude")
        if not base["judgment"]["overall_pass"] and polar["judgment"]["overall_pass"]:
            improvements.append(case["case_id"])
        if base["judgment"]["overall_pass"] and not polar["judgment"]["overall_pass"]:
            regressions.append(case["case_id"])
    return {
        "provider": renderer.provider,
        "model": renderer.model,
        "summary": summary,
        "improvements": improvements,
        "regressions": regressions,
        "rows": rows,
    }


def _classification_accuracy(rows: list[dict[str, Any]], key: str) -> float:
    return sum(bool(row[key]) == (not row["judgment"]["overall_pass"]) for row in rows) / len(rows)


def _run_tension(renderer: GovernedRenderer, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        prompt = _tension_prompt(case)
        score = _tension_score(case["features"])
        receipt = renderer.render(prompt=prompt, system_prompt=SYSTEM_PROMPT)
        rows.append({
            "case_id": case["case_id"],
            "features": case["features"],
            "tension_score": score,
            "predicted_high_tension": score >= 0.5,
            "prompt_words": _words(prompt),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "answer": receipt.answer,
            "judgment": _judge(receipt.answer, case["score"]),
            "latency_s": receipt.latency_s,
            "input_tokens": receipt.input_tokens or 0,
            "output_tokens": receipt.output_tokens or 0,
            "request_id": receipt.request_id,
        })
    median_words = statistics.median(row["prompt_words"] for row in rows)
    for row in rows:
        row["predicted_long_prompt"] = row["prompt_words"] > median_words
    low = [row for row in rows if not row["predicted_high_tension"]]
    high = [row for row in rows if row["predicted_high_tension"]]
    low_failures = sum(not row["judgment"]["overall_pass"] for row in low)
    high_failures = sum(not row["judgment"]["overall_pass"] for row in high)
    low_rate = low_failures / len(low)
    high_rate = high_failures / len(high)
    risk_ratio = float("inf") if low_rate == 0 and high_rate > 0 else (high_rate / low_rate if low_rate else 0.0)
    return {
        "provider": renderer.provider,
        "model": renderer.model,
        "summary": {
            "low_tension_failures": low_failures,
            "low_tension_cases": len(low),
            "high_tension_failures": high_failures,
            "high_tension_cases": len(high),
            "high_to_low_failure_risk_ratio": "inf" if risk_ratio == float("inf") else round(risk_ratio, 3),
            "tension_classifier_accuracy": round(_classification_accuracy(rows, "predicted_high_tension"), 3),
            "length_classifier_accuracy": round(_classification_accuracy(rows, "predicted_long_prompt"), 3),
            "median_prompt_words": median_words,
        },
        "rows": rows,
    }


def _public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in case.items() if key != "score"}


def _assert_synthetic(value: Any) -> None:
    serialized = json.dumps(value, sort_keys=True, default=str).casefold()
    leaked = [marker for marker in PRIVATE_MARKERS if marker in serialized]
    if leaked:
        raise ValueError(f"private markers remain in synthetic pack: {leaked}")


def run(renderers: list[GovernedRenderer]) -> dict[str, Any]:
    polar = polar_cases()
    tension = tension_cases()
    manifest = {
        "seed": SEED,
        "polar_retrieval": {
            "cases": [_public_case(case) for case in polar],
            "variants": ["similarity_only", "polar_magnitude"],
            "evidence_budget": 2,
            "gate": "At least three pooled provider-case improvements, no current-only regression, and no protocol leaks.",
            "limitation": "Controlled similarity scores test the retrieval decision, not embedding geometry or PolarQuant compression.",
        },
        "pre_render_tension_forecast": {
            "cases": [_public_case(case) for case in tension],
            "threshold": 0.5,
            "gate": "High-tension failure risk must exceed low-tension risk for both providers, and pooled tension classification must beat prompt-length classification.",
            "limitation": "Forecasts renderer/verifier risk, not later human memory corrections.",
        },
        "single_pass": True,
        "repair_calls_allowed": False,
        "tools_allowed": False,
        "retrieval_by_renderer_allowed": False,
        "writes_allowed": False,
        "authority_upgrades_allowed": False,
    }
    _assert_synthetic(manifest)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    preflights = [renderer.preflight() for renderer in renderers]
    polar_results = [_run_polar(renderer, polar) for renderer in renderers]
    tension_results = [_run_tension(renderer, tension) for renderer in renderers]

    polar_improvements = sum(len(row["improvements"]) for row in polar_results)
    polar_regressions = [
        f"{row['provider']}:{case_id}"
        for row in polar_results for case_id in row["regressions"]
    ]
    polar_leaks = sum(
        row["summary"]["polar_magnitude"]["protocol_leaks"] for row in polar_results
    )
    current_regressions = [value for value in polar_regressions if value.endswith(":current_only_control")]
    polar_gate = polar_improvements >= 3 and not current_regressions and polar_leaks == 0

    provider_risk_direction = all(
        row["summary"]["high_tension_failures"] / row["summary"]["high_tension_cases"]
        > row["summary"]["low_tension_failures"] / row["summary"]["low_tension_cases"]
        for row in tension_results
    )
    tension_accuracy = statistics.mean(row["summary"]["tension_classifier_accuracy"] for row in tension_results)
    length_accuracy = statistics.mean(row["summary"]["length_classifier_accuracy"] for row in tension_results)
    tension_gate = provider_risk_direction and tension_accuracy > length_accuracy

    return {
        "schema": SCHEMA,
        "started_at": started,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "manifest_sha256": _hash(manifest),
        "manifest": manifest,
        "preflights": preflights,
        "results": {
            "polar_retrieval": {
                "provider_results": polar_results,
                "pooled_improvements": polar_improvements,
                "pooled_regressions": polar_regressions,
                "current_only_regressions": current_regressions,
                "polar_protocol_leaks": polar_leaks,
                "gate_passed": polar_gate,
                "decision": "adapt" if polar_gate else "not_demonstrated",
            },
            "pre_render_tension_forecast": {
                "provider_results": tension_results,
                "provider_risk_direction_passed": provider_risk_direction,
                "mean_tension_classifier_accuracy": round(tension_accuracy, 3),
                "mean_length_classifier_accuracy": round(length_accuracy, 3),
                "gate_passed": tension_gate,
                "decision": "retain_as_routing_signal" if tension_gate else "keep_research_only",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", action="append", choices=("ollama", "grok_cli"), dest="providers")
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
