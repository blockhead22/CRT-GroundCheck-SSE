"""Measure repeat variance on compressed held-tension packets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from labs.global_workspace_probe_lab.workspace_probe_lab import (
    _answer_from_model_text,
    _cases,
    build_compressed_model_prompt,
    verify_probe,
)
from labs.governed_renderer_choice_lab.governed_renderer_choice_lab import (
    GovernedRenderer,
    GrokCliGovernedRenderer,
    OllamaGovernedRenderer,
)
from labs.governed_renderer_choice_lab.workspace_capacity_extension import (
    SYSTEM_PROMPT,
)


SCHEMA = "aether.renderer_variance_extension.v0"
CASE_IDS = (
    "held_tension_local_model_wedge",
    "held_tension_archive_not_memory",
)


def run(renderers: list[GovernedRenderer], *, repetitions: int = 3) -> dict:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    cases = {case.case_id: case for case in _cases() if case.case_id in CASE_IDS}
    provider_results = []
    for renderer in renderers:
        preflight = renderer.preflight()
        rows = []
        for case_id in CASE_IDS:
            case = cases[case_id]
            prompt = build_compressed_model_prompt(case)
            for repetition in range(1, repetitions + 1):
                receipt = renderer.render(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                )
                answer = _answer_from_model_text(
                    case=case,
                    text=receipt.answer,
                    mode="compressed_workspace_model_render",
                    include_packet=True,
                    note=f"{renderer.provider} variance extension",
                )
                score = verify_probe(case, answer)
                rows.append({
                    "case_id": case_id,
                    "repetition": repetition,
                    "passed": score.passed,
                    "score": score.__dict__,
                    "answer_sha256": hashlib.sha256(
                        receipt.answer.encode("utf-8")
                    ).hexdigest(),
                    "latency_s": receipt.latency_s,
                    "input_tokens": receipt.input_tokens or 0,
                    "output_tokens": receipt.output_tokens or 0,
                    "request_id": receipt.request_id,
                })
        by_case = {}
        for case_id in CASE_IDS:
            selected = [row for row in rows if row["case_id"] == case_id]
            by_case[case_id] = {
                "runs": len(selected),
                "passed": sum(bool(row["passed"]) for row in selected),
                "unique_answer_hashes": len({row["answer_sha256"] for row in selected}),
                "mean_score": round(
                    sum(float(row["score"]["total"]) for row in selected)
                    / max(1, len(selected)),
                    4,
                ),
            }
        provider_results.append({
            "provider": renderer.provider,
            "model": renderer.model,
            "preflight": preflight,
            "summary": {
                "runs": len(rows),
                "passed": sum(bool(row["passed"]) for row in rows),
                "unique_answer_hashes": len({row["answer_sha256"] for row in rows}),
                "by_case": by_case,
                "total_latency_s": round(
                    sum(float(row["latency_s"]) for row in rows), 3
                ),
            },
            "results": rows,
        })
    return {
        "schema": SCHEMA,
        "started_at": started_at,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "profile": "synthetic_only",
        "mode": "compressed_packet_no_repair",
        "repetitions": repetitions,
        "answer_text_persisted": False,
        "results": provider_results,
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
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    names = args.providers or ["ollama", "grok_cli"]
    renderers: list[GovernedRenderer] = [
        OllamaGovernedRenderer(model=args.local_model)
        if name == "ollama" else GrokCliGovernedRenderer()
        for name in names
    ]
    payload = run(renderers, repetitions=max(1, args.repetitions))
    rendered = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

