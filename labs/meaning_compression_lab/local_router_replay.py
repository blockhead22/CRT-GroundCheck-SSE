"""Run a raw-vs-routed replay pack through the local router."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.local_router_cli import build_case
from labs.meaning_compression_lab.local_router_eval import route_for_task, run_route
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import call_ollama, judge_answer, raw_prompt


DEFAULT_PACK = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_v0.json")


def run_replay(
    *,
    pack_path: Path = DEFAULT_PACK,
    timeout: int = 300,
    max_cases: int | None = None,
    write_results: bool = True,
) -> dict[str, Any]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    rows = []
    cases = pack["cases"][:max_cases] if max_cases else pack["cases"]
    for item in cases:
        case = build_case(
            item["prompt"],
            task_type=item["task_type"],
            anchors=tuple(item.get("expected_receipts") or ()),
            concepts=tuple(item.get("required_concepts") or ()),
        )
        route = route_for_task(item["task_type"])
        raw_answer = call_ollama(raw_prompt(case), route.model, timeout)
        raw_judgment = judge_answer(raw_answer, case)
        routed = run_route(case, timeout=timeout, runner=call_ollama)
        rows.append(
            {
                "id": item["id"],
                "source": item["source"],
                "task_type": item["task_type"],
                "prompt": item["prompt"],
                "reference_response_excerpt": item.get("reference_response_excerpt", ""),
                "route": routed["route"],
                "raw_answer": raw_answer,
                "raw_judgment": raw_judgment,
                "routed_answer": routed["answer"],
                "routed_judgment": routed["judgment"],
                "repaired": routed["repaired"],
                "fallback_used": routed["fallback_used"],
                "delta": round(routed["judgment"]["score"] - raw_judgment["score"], 3),
            }
        )

    out = {
        "lab": "local_router_replay",
        "pack": pack.get("pack"),
        "pack_path": str(pack_path),
        "case_count": len(rows),
        "aggregate": _aggregate(rows),
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"local_router_replay_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    agg = out["aggregate"]
    _safe_print("\nLocal Router Replay")
    _safe_print("=" * 80)
    _safe_print(f"Pack: {out['pack']} | Cases: {out['case_count']}")
    _safe_print(
        f"Raw pass {agg['raw_pass_count']}/{out['case_count']} avg {agg['raw_avg_score']:.3f} | "
        f"Routed pass {agg['routed_pass_count']}/{out['case_count']} avg {agg['routed_avg_score']:.3f} | "
        f"delta {agg['avg_delta']:+.3f}"
    )
    _safe_print(f"Repairs: {agg['repair_count']} | Fallbacks: {agg['fallback_count']}")
    for row in out["rows"]:
        raw = row["raw_judgment"]
        routed = row["routed_judgment"]
        _safe_print("-" * 80)
        _safe_print(
            f"{row['id']} [{row['task_type']}] delta {row['delta']:+.3f} "
            f"raw={raw['score']:.3f}/{raw['passed']} routed={routed['score']:.3f}/{routed['passed']}"
        )
        _safe_print(f"  route={row['route']['model']} / {row['route']['profile']} repaired={row['repaired']} fallback={row['fallback_used']}")
        _safe_print(f"  routed hard flags: trunc={routed['truncated']} leak={routed['leakage_hits']} weird={routed['weirdness_hits']} forbidden={routed['forbidden_hits']}")
        _safe_print(f"  prompt: {_one_line(row['prompt'], 180)}")
    if "result_path" in out:
        _safe_print(f"\nWrote {out['result_path']}")


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "raw_pass_count": 0,
            "routed_pass_count": 0,
            "raw_avg_score": 0.0,
            "routed_avg_score": 0.0,
            "avg_delta": 0.0,
            "repair_count": 0,
            "fallback_count": 0,
        }
    return {
        "raw_pass_count": sum(1 for row in rows if row["raw_judgment"]["passed"]),
        "routed_pass_count": sum(1 for row in rows if row["routed_judgment"]["passed"]),
        "raw_avg_score": round(sum(row["raw_judgment"]["score"] for row in rows) / len(rows), 3),
        "routed_avg_score": round(sum(row["routed_judgment"]["score"] for row in rows) / len(rows), 3),
        "avg_delta": round(sum(row["delta"] for row in rows) / len(rows), 3),
        "repair_count": sum(1 for row in rows if row["repaired"]),
        "fallback_count": sum(1 for row in rows if row["fallback_used"]),
    }


def _one_line(text: str, limit: int) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run raw-vs-routed local replay.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run_replay(
        pack_path=args.pack,
        timeout=args.timeout,
        max_cases=args.max_cases,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
