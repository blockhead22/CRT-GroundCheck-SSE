"""CLI for DNNT background learning."""

from __future__ import annotations

import argparse
import json

from .background_learning import (
    BackgroundLearningConfig,
    run_background_learning_forever,
    run_background_learning_once,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DNNT background learner")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--poll-interval-sec", type=int, default=180, help="Loop sleep interval")
    parser.add_argument("--min-new-examples", type=int, default=24, help="Minimum examples before training")
    parser.add_argument("--max-steps", type=int, default=200, help="Maximum training steps per cycle")
    parser.add_argument("--output-dir", type=str, default="models/dnnt", help="Model output directory")
    parser.add_argument(
        "--collected-examples-path",
        type=str,
        default="data/dnnt_collected_training_data.jsonl",
        help="JSONL path for trust-gated LLM outputs",
    )
    args = parser.parse_args()

    config = BackgroundLearningConfig(
        output_dir=args.output_dir,
        collected_examples_path=args.collected_examples_path,
        poll_interval_sec=args.poll_interval_sec,
        min_new_examples=args.min_new_examples,
        max_steps_per_cycle=args.max_steps,
    )

    if args.once:
        summary = run_background_learning_once(config=config)
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        return

    run_background_learning_forever(config=config)


if __name__ == "__main__":
    main()

