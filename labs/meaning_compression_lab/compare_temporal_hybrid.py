"""Compare temporal metadata RAG results against a saved hybrid CRT sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.evaluation_contract import classify_severity


def compare(
    hybrid: dict[str, Any],
    temporal_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    temporal_by_model = {run["model"]: run for run in temporal_runs}
    rows = []

    for hybrid_row in hybrid["model_results"]:
        model = hybrid_row["model"]
        temporal = temporal_by_model[model]
        hybrid_result = hybrid["raw_results"][model]

        hybrid_semantic = sum(
            row["scaffold_judgment"]["semantic_passed"]
            for row in hybrid_result["scenarios"]
        )
        hybrid_contract = sum(
            row["scaffold_judgment"]["contract_passed"]
            for row in hybrid_result["scenarios"]
        )
        hybrid_severe = sum(
            classify_severity(row["scenario"], row["scaffold_judgment"])["severity"]
            == "severe_failure"
            for row in hybrid_result["scenarios"]
        )
        temporal_aggregate = temporal["aggregate"]
        case_count = hybrid_row["case_count"]

        rows.append(
            {
                "model": model,
                "case_count": case_count,
                "temporal_semantic": temporal_aggregate["semantic_pass_count"],
                "hybrid_semantic": hybrid_semantic,
                "semantic_delta_count": hybrid_semantic
                - temporal_aggregate["semantic_pass_count"],
                "semantic_delta_points": round(
                    100
                    * (
                        hybrid_semantic
                        - temporal_aggregate["semantic_pass_count"]
                    )
                    / case_count,
                    1,
                ),
                "temporal_contract": temporal_aggregate["contract_pass_count"],
                "hybrid_contract": hybrid_contract,
                "temporal_severe": temporal_aggregate["severe_failure_count"],
                "hybrid_severe": hybrid_severe,
            }
        )

    total_cases = sum(row["case_count"] for row in rows)
    temporal_semantic = sum(row["temporal_semantic"] for row in rows)
    hybrid_semantic = sum(row["hybrid_semantic"] for row in rows)
    temporal_contract = sum(row["temporal_contract"] for row in rows)
    hybrid_contract = sum(row["hybrid_contract"] for row in rows)

    return {
        "lab": "temporal_metadata_rag_vs_hybrid_crt",
        "case_count": total_cases,
        "models": rows,
        "aggregate": {
            "temporal_semantic": temporal_semantic,
            "hybrid_semantic": hybrid_semantic,
            "semantic_delta_count": hybrid_semantic - temporal_semantic,
            "semantic_delta_points": round(
                100 * (hybrid_semantic - temporal_semantic) / total_cases,
                1,
            ),
            "temporal_contract": temporal_contract,
            "hybrid_contract": hybrid_contract,
            "temporal_severe": sum(row["temporal_severe"] for row in rows),
            "hybrid_severe": sum(row["hybrid_severe"] for row in rows),
            "models_where_hybrid_wins": sum(
                row["semantic_delta_count"] > 0 for row in rows
            ),
            "models_where_temporal_wins": sum(
                row["semantic_delta_count"] < 0 for row in rows
            ),
            "models_tied": sum(
                row["semantic_delta_count"] == 0 for row in rows
            ),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# Temporal Metadata RAG vs. Hybrid CRT",
        "",
        "| Model | Temporal semantic | Hybrid semantic | Delta | Temporal severe | Hybrid severe |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["models"]:
        lines.append(
            f"| {row['model']} | {row['temporal_semantic']}/{row['case_count']} "
            f"| {row['hybrid_semantic']}/{row['case_count']} "
            f"| {row['semantic_delta_points']:+.1f} pts "
            f"| {row['temporal_severe']} | {row['hybrid_severe']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Temporal semantic: **{aggregate['temporal_semantic']}/{report['case_count']}**",
            f"- Hybrid semantic: **{aggregate['hybrid_semantic']}/{report['case_count']}**",
            f"- Hybrid delta: **{aggregate['semantic_delta_points']:+.1f} points**",
            f"- Temporal severe failures: **{aggregate['temporal_severe']}**",
            f"- Hybrid severe failures: **{aggregate['hybrid_severe']}**",
            f"- Hybrid wins: **{aggregate['models_where_hybrid_wins']} models**",
            f"- Temporal wins: **{aggregate['models_where_temporal_wins']} models**",
            "",
            "## Interpretation",
            "",
            "This comparison uses the current authored 19-case pack. It is preliminary.",
            "Model-specific reversals must not be hidden by the aggregate score.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("hybrid", type=Path)
    parser.add_argument("temporal", type=Path, nargs="+")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = compare(
        json.loads(args.hybrid.read_text(encoding="utf-8")),
        [
            json.loads(path.read_text(encoding="utf-8"))
            for path in args.temporal
        ],
    )
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

