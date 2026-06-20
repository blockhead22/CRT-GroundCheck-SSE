"""Small real-model probe for the structured semantic fallback."""

from __future__ import annotations

import argparse
import json
import time

from labs.meaning_compression_lab.multi_request_planner import (
    ollama_semantic_parser,
    plan_requests,
)
from labs.meaning_compression_lab.run_lab import OUT_DIR


SLOTS = [
    "employer",
    "camera_system",
    "media.production_delete_without_confirmation",
    "current_project",
    "store_platform",
    "name",
    "file_naming",
]

PROBES = (
    {
        "name": "indirect_two_slot",
        "query": "Remind me who signs my paychecks these days, and what photography setup came before the Blackmagic.",
        "expected": {
            ("employer", "current"),
            ("camera_system", "history"),
        },
    },
    {
        "name": "resolved_plus_ambiguous",
        "query": "What project am I on now, and use the right name when you make the export.",
        "expected_resolved": {
            ("current_project", "current"),
        },
    },
)


def run(*, model: str = "qwen2.5:7b-instruct", timeout: int = 90, write_results: bool = True):
    rows = []
    for probe in PROBES:
        plan = plan_requests(
            probe["query"],
            SLOTS,
            semantic_parser=lambda clauses, slots: ollama_semantic_parser(
                clauses,
                slots,
                model=model,
                timeout=timeout,
            ),
        )
        actual = {(request.slot, request.mode) for request in plan.requests}
        rows.append(
            {
                "name": probe["name"],
                "query": probe["query"],
                "plan": plan.to_dict(),
                "actual": sorted([list(item) for item in actual]),
                "expected": sorted(
                    [list(item) for item in probe.get("expected", probe.get("expected_resolved", set()))]
                ),
                "passed": (
                    actual == probe["expected"]
                    if "expected" in probe
                    else probe["expected_resolved"].issubset(actual)
                ),
            }
        )
    out = {
        "lab": "multi_request_semantic_probe",
        "model": model,
        "passed": sum(row["passed"] for row in rows),
        "case_count": len(rows),
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"multi_request_semantic_probe_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    out = run(model=args.model, timeout=args.timeout, write_results=not args.no_write)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
