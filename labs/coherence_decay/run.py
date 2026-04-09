"""Coherence Decay Experiment — One-Click Runner

Usage:
    python run.py --smoke              # Quick test: 2 prompts, local models only
    python run.py --local-only         # Full run, local models only (no API cost)
    python run.py                      # Full run, all models including cloud
    python run.py --score-only FILE    # Re-score existing results
    python run.py --analyze-only FILE  # Re-analyze existing scored results
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add lab dir to path
sys.path.insert(0, str(Path(__file__).parent))

from generate import run_experiment
from score import score_run
from analyze import analyze


def main():
    parser = argparse.ArgumentParser(description="Coherence Decay — Full Pipeline")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test")
    parser.add_argument("--local-only", action="store_true", help="Skip cloud models")
    parser.add_argument("--models", nargs="+", help="Specific model tiers")
    parser.add_argument("--strategies", nargs="+", help="Specific strategies")
    parser.add_argument("--domains", nargs="+", help="Specific domains")
    parser.add_argument("--score-only", type=str, help="Score existing results file")
    parser.add_argument("--analyze-only", type=str, help="Analyze existing scored file")
    args = parser.parse_args()

    # Score-only mode
    if args.score_only:
        print(f"\nScoring {args.score_only}...")
        scored_file = score_run(args.score_only)
        print(f"\nAnalyzing {scored_file}...")
        analyze(scored_file)
        return

    # Analyze-only mode
    if args.analyze_only:
        print(f"\nAnalyzing {args.analyze_only}...")
        analyze(args.analyze_only)
        return

    # Full pipeline: generate → score → analyze
    from config import MODELS

    models = args.models
    if args.local_only:
        models = [m for m in (models or list(MODELS.keys())) if MODELS[m]["provider"] == "ollama"]

    print("\n" + "=" * 60)
    print("COHERENCE DECAY EXPERIMENT")
    print("=" * 60)
    print(f"Mode: {'smoke' if args.smoke else 'full'}")
    print(f"Cloud: {'disabled' if args.local_only else 'enabled'}")
    print("=" * 60)

    # Step 1: Generate
    print("\n[1/3] GENERATION")
    results, results_file = asyncio.run(run_experiment(
        models=models,
        strategies=args.strategies,
        domains=args.domains,
        smoke=args.smoke,
    ))

    # Step 2: Score
    print("\n[2/3] SCORING")
    scored_file = score_run(results_file)

    # Step 3: Analyze
    print("\n[3/3] ANALYSIS")
    analyze(scored_file)

    print(f"\nAll outputs in: {results_file.parent}")
    print("Done.")


if __name__ == "__main__":
    main()
