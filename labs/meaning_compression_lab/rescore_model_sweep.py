"""Re-score a saved model sweep without making new model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from labs.meaning_compression_lab.plain_rag_eval import PROBES, judge_answer
from labs.meaning_compression_lab.scaffold_eval import aggregate
from labs.meaning_compression_lab.scaffold_model_sweep import aggregate_sweep, summarize_model


def rescore_sweep(saved: dict) -> dict:
    raw_results = saved["raw_results"]
    model_rows = []
    for model, result in raw_results.items():
        for row in result["scenarios"]:
            probe = PROBES[row["scenario"]]
            row["raw_judgment"] = judge_answer(row["raw_answer"], probe)
            row["scaffold_judgment"] = judge_answer(row["scaffold_answer"], probe)
            row["crt_judgment"] = judge_answer(row["crt_answer"], probe)
        result["aggregate"] = aggregate(result["scenarios"])
        model_rows.append(summarize_model(model, result))

    saved["model_results"] = model_rows
    saved["aggregate"] = aggregate_sweep(model_rows)
    saved["rescored"] = True
    saved["grader"] = {
        "legacy": "exact expected tokens plus exclusions",
        "semantic": "meaning/behavior plus scope exclusions",
        "format": "no internal scaffold syntax",
        "contract": "semantic and format",
    }
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score a saved scaffold sweep.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rescored = rescore_sweep(json.loads(args.source.read_text(encoding="utf-8")))
    out_path = args.out or args.source.with_name(f"{args.source.stem}_rescored.json")
    out_path.write_text(json.dumps(rescored, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(rescored["aggregate"], indent=2))


if __name__ == "__main__":
    main()
