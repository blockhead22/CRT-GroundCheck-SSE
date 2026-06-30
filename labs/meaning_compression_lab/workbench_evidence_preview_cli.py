"""Emit Workbench review-only evidence previews from RAG-suite artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from labs.meaning_compression_lab.workbench_evidence_adapter import (
    load_rag_suite_result_for_workbench_preview,
    load_rag_suite_result_for_workbench_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_path", type=Path, help="RAG-suite result JSON to adapt.")
    parser.add_argument(
        "--kind",
        choices=("preview", "review"),
        default="preview",
        help="Emit learner preview or raw evidence review metadata.",
    )
    parser.add_argument("--output", type=Path, help="Optional output JSON path. Defaults to stdout.")
    args = parser.parse_args()

    payload = (
        load_rag_suite_result_for_workbench_review(args.result_path)
        if args.kind == "review"
        else load_rag_suite_result_for_workbench_preview(args.result_path)
    )
    text = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
