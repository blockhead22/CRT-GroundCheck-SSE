#!/usr/bin/env python3
"""500-turn eval harness launcher.

Usage:
    python run_eval.py                      # 500 turns, seeds 0-2, 5 baselines
    python run_eval.py --smoke              # 20 turns, seed 0 only (quick check)
    python run_eval.py --with-crt           # include live CRTSystem via Ollama
    python run_eval.py --n-turns 100 --seeds 0 1
    python run_eval.py --scenario contradiction_stress --with-crt
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_eval")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CRT long-horizon eval harness")
    p.add_argument("--n-turns", type=int, default=500, help="Turns per scenario×system×seed")
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    p.add_argument("--smoke", action="store_true", help="Quick smoke: 20 turns, seed 0")
    p.add_argument("--with-crt", action="store_true", help="Include live CRTSystem (needs Ollama)")
    p.add_argument("--scenario", choices=["contradiction_stress", "correction_recovery",
                                          "hallucination_probe", "noise_drift"],
                   help="Run a single scenario instead of all four")
    p.add_argument("--out", type=Path, default=None, help="Output directory (auto-named if omitted)")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--fail-fast", action="store_true")
    p.add_argument("--production", action="store_true",
                   help="Score production data (no new conversations)")
    p.add_argument("--memory-db", type=str, default=None,
                   help="Path to crt_memory_shared.db (for --production)")
    p.add_argument("--agent-db", type=str, default=None,
                   help="Path to agent_runs.db (for --production)")
    p.add_argument("--capability-probe", action="store_true",
                   help="Run capability lab probes against a local model")
    p.add_argument("--model", type=str, default=None,
                   help="Model name for --capability-probe (default: gemma3:latest)")
    p.add_argument("--categories", type=str, default=None,
                   help="Comma-separated categories for --capability-probe")
    return p.parse_args()


def run_production(args: argparse.Namespace) -> None:
    """Score production databases without running new conversations."""
    import json
    from eval.production_scorer import ProductionScorer

    memory_db = args.memory_db or str(ROOT / "personal_agent" / "crt_memory_shared.db")
    agent_db = args.agent_db or str(ROOT / "personal_agent" / "agent_runs.db")

    logger.info("Production scoring mode")
    logger.info("  memory_db : %s", memory_db)
    logger.info("  agent_db  : %s", agent_db)

    scorer = ProductionScorer(
        memory_db_path=memory_db,
        agent_runs_db_path=agent_db,
    )
    results = scorer.score_all()

    # Print results
    print(json.dumps(results, indent=2, default=str))

    # Summary table
    print("\n-- Production Health Scores -----------------------------------------")
    print(f"{'Dimension':<25} {'Score':>8}  Recommendations")
    print("-" * 70)
    for key in ["retrieval", "trust_evolution", "gate_accuracy",
                "drift_health", "governance_bridge", "agent_performance"]:
        entry = results.get(key, {})
        sc = entry.get("score", float("nan"))
        recs = entry.get("recommendations", [])
        sc_str = f"{sc:.3f}" if not (isinstance(sc, float) and math.isnan(sc)) else "  --"
        rec_str = recs[0] if recs else "OK"
        print(f"{key:<25} {sc_str:>8}  {rec_str}")
    print()

    # Optionally write to file
    if args.out:
        out_path = Path(args.out) / "production_scores.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        logger.info("Written to %s", out_path)


def run_capability_probe(args: argparse.Namespace) -> None:
    """Run capability lab probes against a local model."""
    import json
    from personal_agent.capability_lab import CapabilityLab

    model = args.model or "gemma3:latest"
    cat_list = None
    if args.categories:
        cat_list = [c.strip() for c in args.categories.split(",") if c.strip()]

    logger.info("Capability probe: model=%s, categories=%s", model, cat_list or "all")

    lab = CapabilityLab()
    results = lab.probe_model(model, categories=cat_list)

    # Print full JSON
    print(json.dumps(results, indent=2, default=str))

    # Summary table
    print("\n-- Capability Scores -----------------------------------------------")
    print(f"{'Category':<25} {'Score':>8}  {'Passed':>8}  {'Total':>8}")
    print("-" * 60)
    for cat, info in results.get("categories", {}).items():
        print(f"{cat:<25} {info['score']:>8.3f}  {info['passed']:>8}  {info['total']:>8}")
    overall = results.get("overall_score", 0)
    print("-" * 60)
    print(f"{'OVERALL':<25} {overall:>8.3f}")
    print()

    if args.out:
        out_path = Path(args.out) / f"capability_{model.replace(':', '_')}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        logger.info("Written to %s", out_path)


def main() -> None:
    args = parse_args()

    if args.capability_probe:
        return run_capability_probe(args)

    if args.production:
        return run_production(args)

    if args.smoke:
        args.n_turns = 20
        args.seeds = [0]
        logger.info("Smoke mode: 20 turns, seed 0")

    # ── import harness ────────────────────────────────────────────────────────
    from eval.runner import EvalRunner, EvalConfig
    from eval.scenarios import ALL_SCENARIOS
    from eval.baselines import ALL_SYSTEMS
    from eval.report import generate_report

    # ── scenario filter ───────────────────────────────────────────────────────
    scenario_map = {s.name: s for s in ALL_SCENARIOS}
    if args.scenario:
        match = [s for s in ALL_SCENARIOS if args.scenario in s.name]
        if not match:
            logger.error("Scenario %r not found. Available: %s", args.scenario,
                         ", ".join(scenario_map))
            sys.exit(1)
        scenarios = match
    else:
        scenarios = list(ALL_SCENARIOS)

    # ── system list ───────────────────────────────────────────────────────────
    systems = list(ALL_SYSTEMS)

    if args.with_crt:
        logger.info("Initialising CRTSystem with Ollama…")
        try:
            from personal_agent.litellm_client import get_default_llm_client
            import os
            model = os.environ.get("CRT_OLLAMA_MODEL", "llama3.2:latest")
            llm = get_default_llm_client(model)
            from eval.baselines.crt_system import CRTSystem
            systems.append(CRTSystem(llm_client=llm))
            logger.info("CRTSystem added (model=%s)", model)
        except Exception as e:
            logger.error("Failed to init CRTSystem: %s — continuing without it", e)

    # ── config ────────────────────────────────────────────────────────────────
    cfg = EvalConfig(
        n_turns=args.n_turns,
        seeds=args.seeds,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        log_every_n=max(1, args.n_turns // 10),
    )

    total_turns = len(scenarios) * len(systems) * len(args.seeds) * args.n_turns
    logger.info(
        "Starting eval: %d scenario(s) × %d system(s) × %d seed(s) × %d turns = %d total turns",
        len(scenarios), len(systems), len(args.seeds), args.n_turns, total_turns,
    )
    for s in scenarios:
        logger.info("  scenario : %s", s.name)
    for s in systems:
        logger.info("  system   : %s", s.name)

    # ── output dir ────────────────────────────────────────────────────────────
    if args.out is not None:
        out_dir = args.out
    elif args.smoke:
        out_dir = ROOT / "eval_results_smoke"
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = ROOT / f"eval_results_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output → %s", out_dir)

    # ── run ───────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    runner = EvalRunner(cfg)
    matrix = runner.run_matrix(scenarios, systems, seeds=args.seeds)
    elapsed = time.perf_counter() - t0

    if matrix.errors:
        logger.warning("%d error(s) during run:", len(matrix.errors))
        for e in matrix.errors:
            logger.warning("  %s × %s × seed=%s: %s",
                           e["scenario"], e["system"], e["seed"], e["error"])

    # ── report ────────────────────────────────────────────────────────────────
    try:
        generate_report(matrix, output_dir=out_dir)
        report_path = out_dir / "README_eval.md"
        logger.info("Report written → %s", report_path)
    except Exception as e:
        logger.error("Report generation failed: %s", e)

    # ── summary ───────────────────────────────────────────────────────────────
    logger.info("Done in %.1fs  (%.1f turns/sec)", elapsed, total_turns / max(elapsed, 0.001))
    logger.info("Results: %s", out_dir)

    # Print EIS summary table to stdout
    try:
        print("\n── Epistemic Improvement Score (EIS) — higher is better ─────────")
        header_systems = [s.name for s in systems]
        print(f"{'Scenario':<30}", end="")
        for sn in header_systems:
            print(f"  {sn:>18}", end="")
        print()
        print("-" * (30 + 20 * len(header_systems)))
        for sc in scenarios:
            print(f"{sc.name:<30}", end="")
            for sy in systems:
                mb = matrix.mean_bundle(sc.name, sy.name)
                v = mb.epistemic_improvement_score if mb else float("nan")
                print(f"  {v:>18.3f}", end="")
            print()
        print()
    except Exception:
        pass


if __name__ == "__main__":
    main()
