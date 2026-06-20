"""Produce an audited category report for the completed scaffold sweep."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CATEGORIES = {
    "state_construction_error": {
        ("qwen2.5:7b-instruct", "store_platform_authority_boundary"),
        ("phi3:3.8b", "store_platform_authority_boundary"),
        ("mistral:latest", "store_platform_authority_boundary"),
    },
    "executor_scope_leak": {
        ("qwen2.5:7b-instruct", "camera_history_inventory"),
        ("phi3:3.8b", "camera_history_inventory"),
        ("mistral:latest", "identity_flip"),
        ("mistral:latest", "employer_correction"),
        ("mistral:latest", "favorite_color_social_then_confirmed"),
        ("mistral:latest", "project_revert"),
        ("mistral:latest", "location_correction"),
        ("mistral:latest", "tool_inferred_location_noise"),
    },
    "judge_contract_strictness": {
        ("qwen2.5:7b-instruct", "favorite_color_reaction_rule"),
        ("phi3:3.8b", "destructive_command_policy"),
        ("phi3:3.8b", "favorite_color_reaction_rule"),
        ("llama3.2:latest", "favorite_color_reaction_rule"),
        ("llama3.2:latest", "production_db_mock_policy"),
        ("mistral:latest", "destructive_command_policy"),
        ("mistral:latest", "production_db_mock_policy"),
    },
    "executor_content_loss": {
        ("llama3.2:latest", "concern_preference"),
        ("llama3.2:latest", "name_contradiction_status"),
    },
}

RATIONALE = {
    "state_construction_error": "A provisional observation was incorrectly emitted as authoritative history/contradiction state.",
    "executor_scope_leak": "The requested value was present, but an excluded current/prior value leaked into the answer.",
    "judge_contract_strictness": "The answer was semantically acceptable but missed exact tokens required by the deterministic judge.",
    "executor_content_loss": "The model copied scaffold syntax or dropped required answer content.",
}


def analyze_sweep(sweep: dict) -> dict:
    category_by_key = {
        key: category for category, keys in CATEGORIES.items() for key in keys
    }
    failures = []
    observed = set()
    for model, result in sweep["raw_results"].items():
        for row in result["scenarios"]:
            if row["scaffold_judgment"]["passed"]:
                continue
            key = (model, row["scenario"])
            observed.add(key)
            if key not in category_by_key:
                raise ValueError(f"Unclassified failure: {key}")
            category = category_by_key[key]
            failures.append({
                "model": model,
                "scenario": row["scenario"],
                "probe": row["probe"],
                "category": category,
                "rationale": RATIONALE[category],
                "answer": row["scaffold_answer"],
            })
    stale = set(category_by_key) - observed
    if stale:
        raise ValueError(f"Stale classifications: {sorted(stale)}")
    counts = Counter(row["category"] for row in failures)
    return {
        "source_lab": sweep["lab"],
        "scenario_count": sweep["scenario_count"],
        "failure_count": len(failures),
        "category_counts": dict(sorted(counts.items())),
        "recommended_patch_order": [
            "Fix provisional observations entering authoritative history/contradiction state.",
            "Rerun store_platform_authority_boundary across all models.",
            "Separate semantic correctness from exact-token judge compliance.",
            "Tighten current/history answer scope and rerun scope-leak cases.",
            "Address remaining model-specific content loss.",
        ],
        "failures": failures,
    }


def render_markdown(report: dict, source: Path) -> str:
    lines = [
        "# Meaning Scaffold Sweep Failure Analysis", "",
        f"Source: `{source.as_posix()}`", "",
        f"Reviewed failures: **{report['failure_count']}** across **{report['scenario_count']}** scenarios.", "",
        "## Category Counts", "",
    ]
    lines += [f"- `{name}`: {count}" for name, count in report["category_counts"].items()]
    lines += ["", "## Recommended Patch Order", ""]
    lines += [f"{i}. {item}" for i, item in enumerate(report["recommended_patch_order"], 1)]
    lines += ["", "## Failures", ""]
    for row in report["failures"]:
        lines += [
            f"- **{row['model']} / {row['scenario']}** — `{row['category']}`",
            f"  - {row['rationale']}",
            f"  - Answer: `{row['answer']}`",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sweep", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    report = analyze_sweep(json.loads(args.sweep.read_text(encoding="utf-8")))
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(render_markdown(report, args.sweep), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
