#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo-root imports work when called as script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.agentic_eval.orchestrator import AgenticEvalOrchestrator, OrchestratorConfig


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Agentic AI-vs-AI conversational evaluation harness for CRT + GroundCheck.",
    )
    ap.add_argument("--api-base-url", default="http://127.0.0.1:8123")
    ap.add_argument("--ollama-base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--output-dir", default="artifacts/agentic_eval")
    ap.add_argument("--objectives-path", default="tools/agentic_eval/agentic_eval_objectives.v1.json")
    ap.add_argument("--campaigns", type=int, default=3)
    ap.add_argument("--max-turns", type=int, default=120)
    ap.add_argument("--min-turns", type=int, default=40)
    ap.add_argument("--memory-probe-limit", type=int, default=30)
    ap.add_argument("--attacker-model", default=None)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--attacker-temp", type=float, default=0.25)
    ap.add_argument("--judge-temp", type=float, default=0.15)
    ap.add_argument("--probe-attempts", type=int, default=2)
    ap.add_argument("--probe-timeout-seconds", type=float, default=45.0)
    ap.add_argument("--no-autodiscover-models", action="store_true")
    ap.add_argument("--stop-on-hard-fail", action="store_true")
    return ap


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = OrchestratorConfig(
        api_base_url=str(args.api_base_url),
        ollama_base_url=str(args.ollama_base_url),
        output_dir=str(args.output_dir),
        objectives_path=str(args.objectives_path),
        campaigns=max(1, int(args.campaigns)),
        max_turns=max(1, int(args.max_turns)),
        min_turns=max(1, int(args.min_turns)),
        memory_probe_limit=max(5, int(args.memory_probe_limit)),
        continue_after_hard_fail=not bool(args.stop_on_hard_fail),
        autodiscover_models=not bool(args.no_autodiscover_models),
        attacker_model=(str(args.attacker_model).strip() if args.attacker_model else None),
        judge_model=(str(args.judge_model).strip() if args.judge_model else None),
        attacker_temp=float(args.attacker_temp),
        judge_temp=float(args.judge_temp),
        probe_attempts=max(1, int(args.probe_attempts)),
        probe_timeout_seconds=max(10.0, float(args.probe_timeout_seconds)),
    )
    orchestrator = AgenticEvalOrchestrator(cfg)
    result = orchestrator.run()
    print(json.dumps(result, indent=2, ensure_ascii=True))

    verdict = str((result.get("run_summary") or {}).get("verdict") or "")
    if verdict in {"PASS", "WARN"}:
        return 0
    if verdict == "FAIL_SOFT":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
