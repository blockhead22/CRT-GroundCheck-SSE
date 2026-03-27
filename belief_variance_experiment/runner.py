"""
Belief Variance Experiment — Experiment Runner
================================================
Samples LLM responses across multiple temperatures with high repetition
to map belief topology. Uses AsyncOpenAI for parallel execution with
rate-limit-aware semaphore.

Usage:
    python runner.py [--model MODEL] [--reps N] [--max-concurrent N] [--yes]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from openai import AsyncOpenAI
from tqdm.asyncio import tqdm as atqdm

from prompts import ALL_PROMPTS, DOMAINS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]
DEFAULT_REPS = 100
DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOKENS = 200
SYSTEM_PROMPT = "Answer the following question directly and concisely in 1-3 sentences."
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds

RESULTS_DIR = Path(__file__).parent / "results" / "raw"


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------
# Approximate token costs for common models (per 1M tokens, USD)
COST_TABLE = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


def estimate_cost(model: str, num_prompts: int, num_temps: int, num_reps: int) -> float:
    """Rough cost estimate in USD."""
    costs = COST_TABLE.get(model, COST_TABLE["gpt-4o-mini"])
    # Estimate ~50 input tokens per request, ~100 output tokens per response
    total_requests = num_prompts * num_temps * num_reps
    input_tokens = total_requests * 50
    output_tokens = total_requests * 100
    cost = (input_tokens / 1_000_000) * costs["input"] + (
        output_tokens / 1_000_000
    ) * costs["output"]
    return cost


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------
def count_existing(prompt_id: str, temperature: float) -> int:
    """Count completed repetitions for a prompt+temperature combo."""
    path = RESULTS_DIR / f"{prompt_id}_{temperature}.jsonl"
    if not path.exists():
        return 0
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                count += 1
    return count


def append_result(prompt_id: str, temperature: float, record: dict) -> None:
    """Append a single result to the appropriate JSONL file."""
    path = RESULTS_DIR / f"{prompt_id}_{temperature}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------
async def call_api(
    client: AsyncOpenAI,
    model: str,
    prompt_text: str,
    temperature: float,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Make a single API call with exponential backoff retry."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ]
    for attempt in range(MAX_RETRIES):
        try:
            async with semaphore:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=MAX_TOKENS,
                )
            choice = response.choices[0]
            return {
                "response": choice.message.content,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {
                    "response": f"ERROR: {type(e).__name__}: {e}",
                    "finish_reason": "error",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            await asyncio.sleep(delay)
    # Unreachable, but for safety:
    return {"response": "ERROR: max retries exceeded", "finish_reason": "error", "usage": {}}


# ---------------------------------------------------------------------------
# Task generation
# ---------------------------------------------------------------------------
def build_task_list(num_reps: int) -> list[tuple[dict, float, int]]:
    """
    Build the full list of (prompt, temperature, repetition) tasks,
    skipping any that already have results on disk.
    Returns list of (prompt_dict, temperature, rep_number) tuples.
    """
    tasks = []
    for prompt in ALL_PROMPTS:
        for temp in TEMPERATURES:
            existing = count_existing(prompt["id"], temp)
            for rep in range(existing, num_reps):
                tasks.append((prompt, temp, rep))
    return tasks


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
async def run_experiment(
    model: str,
    num_reps: int,
    max_concurrent: int,
) -> None:
    """Run the full experiment."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tasks = build_task_list(num_reps)
    if not tasks:
        print("All tasks already completed. Nothing to do.")
        return

    total_possible = len(ALL_PROMPTS) * len(TEMPERATURES) * num_reps
    already_done = total_possible - len(tasks)
    print(f"Total tasks: {total_possible}")
    print(f"Already completed: {already_done}")
    print(f"Remaining: {len(tasks)}")
    print()

    client = AsyncOpenAI()  # Uses OPENAI_API_KEY env var
    semaphore = asyncio.Semaphore(max_concurrent)

    # Progress bar
    pbar = atqdm(total=len(tasks), desc="Sampling", unit="req")

    async def process_task(prompt: dict, temperature: float, rep: int) -> None:
        result = await call_api(client, model, prompt["text"], temperature, semaphore)
        record = {
            "prompt_id": prompt["id"],
            "domain": prompt["domain"],
            "temperature": temperature,
            "repetition": rep,
            **result,
        }
        append_result(prompt["id"], temperature, record)
        pbar.update(1)

    # Launch tasks in batches to avoid event loop overhead
    BATCH_SIZE = 500
    for i in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[i:i + BATCH_SIZE]
        coros = [process_task(p, t, r) for p, t, r in batch]
        await asyncio.gather(*coros)
    pbar.close()

    print("\nExperiment complete!")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Belief Variance Experiment Runner")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS, help=f"Repetitions per prompt per temperature (default: {DEFAULT_REPS})")
    parser.add_argument("--max-concurrent", type=int, default=50, help="Max concurrent API calls (default: 50)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    # Build task list for cost estimation
    tasks = build_task_list(args.reps)
    remaining_prompts = len(set(t[0]["id"] for t in tasks))
    remaining_temps = len(set(t[1] for t in tasks))

    # Cost estimate (rough, based on remaining tasks)
    num_remaining = len(tasks)
    per_request_input = 50  # tokens
    per_request_output = 100  # tokens
    costs = COST_TABLE.get(args.model, COST_TABLE["gpt-4o-mini"])
    est_cost = (
        (num_remaining * per_request_input / 1_000_000) * costs["input"]
        + (num_remaining * per_request_output / 1_000_000) * costs["output"]
    )

    print("=" * 60)
    print("  BELIEF VARIANCE EXPERIMENT")
    print("=" * 60)
    print(f"  Model:            {args.model}")
    print(f"  Prompts:          {len(ALL_PROMPTS)}")
    print(f"  Temperatures:     {TEMPERATURES}")
    print(f"  Reps per combo:   {args.reps}")
    print(f"  Max concurrent:   {args.max_concurrent}")
    print(f"  Remaining calls:  {num_remaining:,}")
    print(f"  Estimated cost:   ${est_cost:.2f}")
    print("=" * 60)

    if not args.yes:
        response = input("\nProceed? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    start = time.time()
    asyncio.run(run_experiment(args.model, args.reps, args.max_concurrent))
    elapsed = time.time() - start
    print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
