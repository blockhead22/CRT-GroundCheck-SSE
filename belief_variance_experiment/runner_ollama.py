"""Belief Variance Experiment — Ollama Runner
================================================
Samples local LLM responses across multiple temperatures with high
repetition to map belief topology. Uses Ollama's API directly.

Advantages over cloud:
  - Free
  - No rate limits
  - Open model = no RLHF mystery sauce = cleaner belief signal
  - Publishable: "belief topology of an open-weight model"

Usage:
    python runner_ollama.py [--model MODEL] [--reps N] [--max-concurrent N]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
from tqdm.asyncio import tqdm as atqdm

from prompts import ALL_PROMPTS, DOMAINS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]
DEFAULT_REPS = 30
DEFAULT_MODEL = "qwen3:14b"
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MAX_TOKENS = 200
SYSTEM_PROMPT = "Answer the following question directly and concisely in 1-3 sentences. Do not explain your reasoning."
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0

# Use a curated subset of 50 prompts (10 per domain) for local inference
USE_SUBSET = True
SUBSET_SIZE_PER_DOMAIN = 10

RESULTS_DIR = Path(__file__).parent / "results" / "raw"


# ---------------------------------------------------------------------------
# Prompt selection
# ---------------------------------------------------------------------------
def get_prompts(use_subset: bool = True, per_domain: int = 10) -> list[dict]:
    """Get prompts, optionally filtering to a curated subset.

    Selects the first N per domain — the prompt bank is ordered by
    signal quality so the first ones are the strongest.
    """
    if not use_subset:
        return ALL_PROMPTS

    from collections import Counter
    selected = []
    counts = Counter()
    for p in ALL_PROMPTS:
        if counts[p["domain"]] < per_domain:
            selected.append(p)
            counts[p["domain"]] += 1
    return selected


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------
def count_existing(prompt_id: str, temperature: float) -> int:
    """Count completed (non-error) repetitions for a prompt+temperature combo."""
    path = RESULTS_DIR / f"{prompt_id}_{temperature}.jsonl"
    if not path.exists():
        return 0
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not record.get("response", "").startswith("ERROR:"):
                    count += 1
            except json.JSONDecodeError:
                pass
    return count


def append_result(prompt_id: str, temperature: float, record: dict) -> None:
    """Append a single result to the appropriate JSONL file."""
    path = RESULTS_DIR / f"{prompt_id}_{temperature}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Ollama API call with retry
# ---------------------------------------------------------------------------
async def call_ollama(
    session: aiohttp.ClientSession,
    model: str,
    prompt_text: str,
    temperature: float,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Make a single Ollama API call with exponential backoff retry."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": MAX_TOKENS,
        },
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with semaphore:
                async with session.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
                    data = await resp.json()

            content = data.get("message", {}).get("content", "")
            # Strip <think> blocks if present (qwen3 thinking mode)
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            eval_count = data.get("eval_count", 0)
            prompt_eval_count = data.get("prompt_eval_count", 0)

            return {
                "response": content,
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": prompt_eval_count,
                    "completion_tokens": eval_count,
                    "total_tokens": prompt_eval_count + eval_count,
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

    return {"response": "ERROR: max retries exceeded", "finish_reason": "error", "usage": {}}


# ---------------------------------------------------------------------------
# Task generation
# ---------------------------------------------------------------------------
def build_task_list(prompts: list[dict], num_reps: int) -> list[tuple[dict, float, int]]:
    """Build task list, skipping completed (non-error) results."""
    tasks = []
    for prompt in prompts:
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
    prompts: list[dict],
    num_reps: int,
    max_concurrent: int,
) -> None:
    """Run the full experiment against Ollama."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tasks = build_task_list(prompts, num_reps)
    if not tasks:
        print("All tasks already completed. Nothing to do.")
        return

    total_possible = len(prompts) * len(TEMPERATURES) * num_reps
    already_done = total_possible - len(tasks)
    print(f"Total tasks: {total_possible}")
    print(f"Already completed: {already_done}")
    print(f"Remaining: {len(tasks)}")
    print()

    # Ollama handles one request at a time internally for most models,
    # but we can queue a few to keep the pipeline full
    semaphore = asyncio.Semaphore(max_concurrent)

    pbar = atqdm(total=len(tasks), desc="Sampling", unit="req")

    async with aiohttp.ClientSession() as session:
        async def process_task(prompt: dict, temperature: float, rep: int) -> None:
            result = await call_ollama(session, model, prompt["text"], temperature, semaphore)
            record = {
                "prompt_id": prompt["id"],
                "domain": prompt["domain"],
                "temperature": temperature,
                "repetition": rep,
                **result,
            }
            append_result(prompt["id"], temperature, record)
            pbar.update(1)

        # Process sequentially in batches to avoid overwhelming Ollama
        # Ollama can only run one inference at a time per model
        for prompt, temp, rep in tasks:
            await process_task(prompt, temp, rep)

    pbar.close()
    print("\nExperiment complete!")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Belief Variance Experiment — Ollama Runner")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS,
                        help=f"Repetitions per prompt per temp (default: {DEFAULT_REPS})")
    parser.add_argument("--max-concurrent", type=int, default=1,
                        help="Max concurrent requests (default: 1, Ollama is sequential)")
    parser.add_argument("--all-prompts", action="store_true",
                        help="Use all 200 prompts instead of curated 50")
    parser.add_argument("--per-domain", type=int, default=SUBSET_SIZE_PER_DOMAIN,
                        help=f"Prompts per domain in subset mode (default: {SUBSET_SIZE_PER_DOMAIN})")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompt")
    args = parser.parse_args()

    # Check Ollama is running
    try:
        import urllib.request
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5)
    except Exception:
        print(f"ERROR: Ollama not reachable at {OLLAMA_URL}")
        print("Start it with: ollama serve")
        sys.exit(1)

    prompts = get_prompts(use_subset=not args.all_prompts, per_domain=args.per_domain)

    # Clean out error-only results from previous bad runs
    if RESULTS_DIR.exists():
        cleaned = 0
        for path in RESULTS_DIR.glob("*.jsonl"):
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            good_lines = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                    if not r.get("response", "").startswith("ERROR:"):
                        good_lines.append(line)
                    else:
                        cleaned += 1
                except json.JSONDecodeError:
                    cleaned += 1
            if len(good_lines) < len(lines):
                path.write_text("\n".join(good_lines) + "\n" if good_lines else "",
                                encoding="utf-8")
        if cleaned > 0:
            print(f"Cleaned {cleaned} error responses from previous runs.\n")

    tasks = build_task_list(prompts, args.reps)

    # Time estimate
    est_seconds_per_call = 3.0  # rough for 14B model
    est_total_seconds = len(tasks) * est_seconds_per_call
    est_hours = est_total_seconds / 3600

    domain_counts = {}
    for p in prompts:
        domain_counts[p["domain"]] = domain_counts.get(p["domain"], 0) + 1

    print("=" * 60)
    print("  BELIEF VARIANCE EXPERIMENT — OLLAMA")
    print("=" * 60)
    print(f"  Model:            {args.model}")
    print(f"  Prompts:          {len(prompts)} ({', '.join(f'{d}={c}' for d,c in sorted(domain_counts.items()))})")
    print(f"  Temperatures:     {TEMPERATURES}")
    print(f"  Reps per combo:   {args.reps}")
    print(f"  Remaining calls:  {len(tasks):,}")
    print(f"  Est. time:        {est_hours:.1f} hours ({est_total_seconds/60:.0f} min)")
    print(f"  Cost:             $0.00 (local)")
    print("=" * 60)

    if not args.yes:
        response = input("\nProceed? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    start = time.time()
    asyncio.run(run_experiment(args.model, prompts, args.reps, args.max_concurrent))
    elapsed = time.time() - start
    print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
