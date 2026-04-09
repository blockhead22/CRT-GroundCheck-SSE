"""Coherence Decay Experiment — Generation Harness

Generates responses at each strategy level (L0-L4) across model tiers.
Captures per-span entropy, token probabilities, and generation metadata.
"""

import asyncio
import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import aiohttp

from config import (
    OLLAMA_URL, MODELS, STRATEGIES, DOMAINS, PROMPTS_DIR, RAW_DIR,
    TEMPERATURE, ENTROPY_HIGH_THRESHOLD, ENTROPY_RERUN_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class SpanResult:
    """One burst/span of generation."""
    span_index: int
    text: str
    token_count: int
    entropy_mean: float
    entropy_max: float
    entropy_per_token: list[float] = field(default_factory=list)
    was_rerun: bool = False
    rerun_reason: Optional[str] = None


@dataclass
class GenerationResult:
    """Full generation for one prompt × model × strategy."""
    prompt_id: str
    domain: str
    model_tier: str
    model_name: str
    strategy: str
    full_text: str
    spans: list[SpanResult]
    total_tokens: int
    total_time_ms: float
    reanchors: int
    reruns: int
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ollama generation with logprobs
# ---------------------------------------------------------------------------
async def ollama_generate(
    session: aiohttp.ClientSession,
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
    temperature: float = 0.3,
) -> tuple[str, list[float]]:
    """Generate from Ollama, return (text, entropy_per_token).

    Uses /api/generate with raw mode for logprob access.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }

    url = f"{OLLAMA_URL}/api/generate"
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {error}")
            data = await resp.json()
    except asyncio.TimeoutError:
        raise RuntimeError(f"Ollama timeout after 300s for model {model}")

    text = data.get("response", "")

    # Ollama doesn't expose per-token logprobs in standard API
    # We estimate entropy by running the generation and measuring via
    # a follow-up eval pass if needed. For now, use response metadata.
    #
    # Approximation: use eval_count / eval_duration as a fluency proxy,
    # and we'll add proper entropy via the scoring pass.
    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 1)
    prompt_eval_count = data.get("prompt_eval_count", 0)

    # Placeholder entropy — will be computed in scoring pass via
    # token-by-token evaluation
    entropy_per_token = []

    return text, entropy_per_token


async def ollama_entropy_probe(
    session: aiohttp.ClientSession,
    model: str,
    context_prefix: str,
    generated_text: str,
    system: str = "",
) -> list[float]:
    """Estimate per-token entropy by asking the model to evaluate
    the generated text token by token.

    We do this by feeding prefix + generated tokens and checking if
    the model would produce the same output. Multiple samples at
    low temperature give us a variance signal.

    Simpler approach: Run the same prompt N times at temp=0.7 and
    measure output variance as entropy proxy.
    """
    NUM_SAMPLES = 3
    samples = []

    for _ in range(NUM_SAMPLES):
        text, _ = await ollama_generate(
            session, model, context_prefix, system,
            max_tokens=len(generated_text.split()) + 10,
            temperature=0.7,
        )
        samples.append(text)

    # Compute per-word agreement as entropy proxy
    # Split all samples into words, measure agreement at each position
    word_lists = [s.split() for s in samples]
    min_len = min(len(w) for w in word_lists) if word_lists else 0

    entropy_proxy = []
    for i in range(min_len):
        words_at_pos = [wl[i] if i < len(wl) else "" for wl in word_lists]
        unique = len(set(w.lower().strip(".,!?;:") for w in words_at_pos))
        # More unique words = higher entropy
        # Normalize: 1 unique = 0 entropy, N unique = log2(N)
        ent = math.log2(unique) if unique > 1 else 0.0
        entropy_proxy.append(ent)

    return entropy_proxy


async def openai_generate(
    prompt: str,
    system: str = "",
    model: str = "gpt-4o-mini",
    max_tokens: int = 200,
    temperature: float = 0.3,
) -> tuple[str, list[float]]:
    """Generate from OpenAI API with logprobs."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system} if system else None,
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "logprobs": True,
        "top_logprobs": 5,
    }
    # Remove None system message
    payload["messages"] = [m for m in payload["messages"] if m is not None]

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"OpenAI error {resp.status}: {error}")
            data = await resp.json()

    choice = data["choices"][0]
    text = choice["message"]["content"]

    # Extract real per-token entropy from logprobs
    entropy_per_token = []
    if choice.get("logprobs") and choice["logprobs"].get("content"):
        for token_info in choice["logprobs"]["content"]:
            top_lps = token_info.get("top_logprobs", [])
            if top_lps:
                # Compute entropy from top-k probabilities
                probs = [math.exp(lp["logprob"]) for lp in top_lps]
                total = sum(probs)
                probs = [p / total for p in probs]  # Normalize
                ent = -sum(p * math.log2(p) for p in probs if p > 0)
                entropy_per_token.append(ent)

    return text, entropy_per_token


# ---------------------------------------------------------------------------
# Strategy execution
# ---------------------------------------------------------------------------
async def generate_free_run(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt_text: str,
    max_tokens: int,
    system: str = "",
) -> tuple[str, list[SpanResult]]:
    """L0/L1: Single generation, no intervention."""
    t0 = time.time()

    if model_cfg["provider"] == "ollama":
        text, entropy = await ollama_generate(
            session, model_cfg["name"], prompt_text, system, max_tokens
        )
    else:
        text, entropy = await openai_generate(
            prompt_text, system, model_cfg["name"], max_tokens
        )

    span = SpanResult(
        span_index=0,
        text=text,
        token_count=len(text.split()),  # Approximate
        entropy_mean=sum(entropy) / len(entropy) if entropy else 0.0,
        entropy_max=max(entropy) if entropy else 0.0,
        entropy_per_token=entropy,
    )

    return text, [span]


async def generate_burst(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt_text: str,
    strategy_cfg: dict,
    system: str = "",
) -> tuple[str, list[SpanResult], int, int]:
    """L2/L3/L4: Burst generation with re-anchoring and optional checks."""
    burst_size = strategy_cfg["burst_size"]
    max_tokens = strategy_cfg["max_tokens"]
    do_entropy = strategy_cfg["entropy_check"]
    do_contradiction = strategy_cfg["contradiction_check"]

    spans = []
    full_text = ""
    total_generated = 0
    reanchors = 0
    reruns = 0
    span_idx = 0

    while total_generated < max_tokens:
        remaining = max_tokens - total_generated
        this_burst = min(burst_size, remaining)
        if this_burst <= 0:
            break

        # Build context: original prompt + summary of what we've generated so far
        if full_text:
            reanchors += 1
            context = (
                f"{prompt_text}\n\n"
                f"[Continue from where you left off. Here is what you have written so far:]\n"
                f"{full_text}\n\n"
                f"[Continue writing the next part. Do not repeat what was already written.]"
            )
        else:
            context = prompt_text

        if model_cfg["provider"] == "ollama":
            text, entropy = await ollama_generate(
                session, model_cfg["name"], context, system, this_burst
            )
        else:
            text, entropy = await openai_generate(
                context, system, model_cfg["name"], this_burst
            )

        if not text.strip():
            break  # Model produced nothing, probably done

        was_rerun = False
        rerun_reason = None

        # Entropy check (L3+): if entropy too high, re-run with grounding
        if do_entropy and entropy:
            mean_ent = sum(entropy) / len(entropy)
            if mean_ent > ENTROPY_RERUN_THRESHOLD:
                reruns += 1
                was_rerun = True
                rerun_reason = f"entropy={mean_ent:.2f} > {ENTROPY_RERUN_THRESHOLD}"

                # Re-run with tighter grounding
                grounded_context = (
                    f"{prompt_text}\n\n"
                    f"[Important: Stay strictly factual. Here is what you have written so far:]\n"
                    f"{full_text}\n\n"
                    f"[Continue carefully. Only state things you are confident about.]"
                )
                if model_cfg["provider"] == "ollama":
                    text, entropy = await ollama_generate(
                        session, model_cfg["name"], grounded_context, system, this_burst
                    )
                else:
                    text, entropy = await openai_generate(
                        grounded_context, system, model_cfg["name"], this_burst
                    )

        # Contradiction check (L4): compare new span against prior spans
        if do_contradiction and len(spans) > 0 and text.strip():
            # Simple heuristic: check for negation patterns against prior text
            # Full NLI would go here in production
            contradiction_detected = _simple_contradiction_check(full_text, text)
            if contradiction_detected:
                reruns += 1
                was_rerun = True
                rerun_reason = (rerun_reason or "") + " + contradiction_detected"

                grounded_context = (
                    f"{prompt_text}\n\n"
                    f"[You previously stated:]\n{full_text}\n\n"
                    f"[Continue, but make sure you do NOT contradict anything above. "
                    f"Stay consistent with all prior statements.]"
                )
                if model_cfg["provider"] == "ollama":
                    text, entropy = await ollama_generate(
                        session, model_cfg["name"], grounded_context, system, this_burst
                    )
                else:
                    text, entropy = await openai_generate(
                        grounded_context, system, model_cfg["name"], this_burst
                    )

        span = SpanResult(
            span_index=span_idx,
            text=text,
            token_count=len(text.split()),
            entropy_mean=sum(entropy) / len(entropy) if entropy else 0.0,
            entropy_max=max(entropy) if entropy else 0.0,
            entropy_per_token=entropy,
            was_rerun=was_rerun,
            rerun_reason=rerun_reason,
        )
        spans.append(span)
        full_text += text
        total_generated += len(text.split())
        span_idx += 1

    return full_text, spans, reanchors, reruns


def _simple_contradiction_check(prior_text: str, new_text: str) -> bool:
    """Basic contradiction detection via negation patterns.

    This is intentionally simple — a real implementation would use
    NLI or embedding-based comparison. For the experiment, we want
    to measure whether even basic contradiction gating helps.
    """
    prior_lower = prior_text.lower()
    new_lower = new_text.lower()

    # Check for explicit negation of prior claims
    negation_patterns = [
        ("is ", "is not "), ("was ", "was not "), ("are ", "are not "),
        ("has ", "has no "), ("can ", "cannot "), ("will ", "will not "),
        ("does ", "does not "),
    ]

    for pos, neg in negation_patterns:
        # Find claims in prior text, check if negated in new
        for sentence in prior_lower.split("."):
            sentence = sentence.strip()
            if pos in sentence:
                claim_fragment = sentence.split(pos, 1)[1].split()[0:3]
                claim_str = " ".join(claim_fragment)
                if claim_str and neg + claim_str in new_lower:
                    return True

    return False


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------
async def run_single(
    session: aiohttp.ClientSession,
    model_tier: str,
    model_cfg: dict,
    strategy_name: str,
    strategy_cfg: dict,
    prompt_data: dict,
    domain: str,
) -> GenerationResult:
    """Run one prompt × model × strategy combination."""

    prompt_text = prompt_data["prompt"]
    system = "You are a helpful assistant. Follow the instructions precisely."

    t0 = time.time()

    reanchors = 0
    reruns = 0

    if strategy_cfg["burst_size"] is None:
        # Free-run strategy
        full_text, spans = await generate_free_run(
            session, model_cfg, prompt_text,
            strategy_cfg["max_tokens"], system,
        )
    else:
        # Burst strategy
        full_text, spans, reanchors, reruns = await generate_burst(
            session, model_cfg, prompt_text, strategy_cfg, system,
        )

    elapsed_ms = (time.time() - t0) * 1000

    return GenerationResult(
        prompt_id=prompt_data["id"],
        domain=domain,
        model_tier=model_tier,
        model_name=model_cfg["name"],
        strategy=strategy_name,
        full_text=full_text,
        spans=[asdict(s) for s in spans],
        total_tokens=sum(s.token_count for s in spans),
        total_time_ms=elapsed_ms,
        reanchors=reanchors,
        reruns=reruns,
    )


async def run_experiment(
    models: list[str] | None = None,
    strategies: list[str] | None = None,
    domains: list[str] | None = None,
    smoke: bool = False,
):
    """Run the full experiment matrix."""

    models = models or list(MODELS.keys())
    strategies = strategies or list(STRATEGIES.keys())
    domains = domains or DOMAINS

    # Load prompts
    all_prompts = {}
    for domain in domains:
        prompt_file = PROMPTS_DIR / f"{domain}.json"
        with open(prompt_file) as f:
            data = json.load(f)
        all_prompts[domain] = data["prompts"]
        if smoke:
            all_prompts[domain] = all_prompts[domain][:2]  # Just 2 prompts in smoke mode

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    total_runs = sum(
        len(all_prompts[d]) for d in domains
    ) * len(models) * len(strategies)

    print(f"\n{'='*60}")
    print(f"Coherence Decay Experiment")
    print(f"{'='*60}")
    print(f"Models:     {models}")
    print(f"Strategies: {strategies}")
    print(f"Domains:    {domains}")
    print(f"Total runs: {total_runs}")
    print(f"{'='*60}\n")

    results = []
    completed = 0

    async with aiohttp.ClientSession() as session:
        for model_tier in models:
            model_cfg = MODELS[model_tier]

            # Check model availability
            if model_cfg["provider"] == "ollama":
                try:
                    async with session.get(f"{OLLAMA_URL}/api/tags") as resp:
                        if resp.status != 200:
                            print(f"  [SKIP] Ollama not reachable for {model_tier}")
                            continue
                        tags = await resp.json()
                        available = [m["name"] for m in tags.get("models", [])]
                        if model_cfg["name"] not in available:
                            # Try without tag
                            base_name = model_cfg["name"].split(":")[0]
                            if not any(base_name in m for m in available):
                                print(f"  [SKIP] Model {model_cfg['name']} not found. Available: {available}")
                                continue
                except Exception as e:
                    print(f"  [SKIP] Ollama connection failed: {e}")
                    continue

            for strategy_name in strategies:
                strategy_cfg = STRATEGIES[strategy_name]

                for domain in domains:
                    for prompt_data in all_prompts[domain]:
                        completed += 1
                        label = f"[{completed}/{total_runs}] {model_tier}/{strategy_name}/{domain}/{prompt_data['id']}"
                        print(f"  Running {label}...", end=" ", flush=True)

                        try:
                            result = await run_single(
                                session, model_tier, model_cfg,
                                strategy_name, strategy_cfg,
                                prompt_data, domain,
                            )
                            results.append(asdict(result))
                            tokens = result.total_tokens
                            ms = result.total_time_ms
                            print(f"OK ({tokens} tokens, {ms:.0f}ms)")
                        except Exception as e:
                            print(f"FAIL: {e}")
                            results.append({
                                "prompt_id": prompt_data["id"],
                                "domain": domain,
                                "model_tier": model_tier,
                                "model_name": model_cfg["name"],
                                "strategy": strategy_name,
                                "error": str(e),
                            })

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_file = RAW_DIR / f"run_{timestamp}.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Done. {len(results)} results saved to {out_file}")
    print(f"{'='*60}")

    return results, out_file


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Coherence Decay — Generation Harness")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test (2 prompts per domain)")
    parser.add_argument("--models", nargs="+", help="Model tiers to test", choices=list(MODELS.keys()))
    parser.add_argument("--strategies", nargs="+", help="Strategies to test", choices=list(STRATEGIES.keys()))
    parser.add_argument("--domains", nargs="+", help="Domains to test", choices=DOMAINS)
    parser.add_argument("--local-only", action="store_true", help="Skip cloud models")
    args = parser.parse_args()

    models = args.models
    if args.local_only:
        models = [m for m in (models or list(MODELS.keys())) if MODELS[m]["provider"] == "ollama"]

    asyncio.run(run_experiment(
        models=models,
        strategies=args.strategies,
        domains=args.domains,
        smoke=args.smoke,
    ))
