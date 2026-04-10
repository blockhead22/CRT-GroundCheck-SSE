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
    raw_mode: bool = False,
) -> tuple[str, list[float]]:
    """Generate from Ollama, return (text, entropy_per_token).

    When raw_mode=True, sends the prompt as a raw prefix (no chat
    template wrapping) so the model continues it naturally. This is
    critical for burst generation — the model sees prompt + prior
    output as one text and picks up where it left off.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "raw": raw_mode,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }
    # Only include system when not in raw mode (raw mode ignores it)
    if system and not raw_mode:
        payload["system"] = system

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
    NUM_SAMPLES = 2  # Keep low for speed; 2 samples still detects variance
    samples = []

    for _ in range(NUM_SAMPLES):
        text, _ = await ollama_generate(
            session, model, context_prefix, system,
            max_tokens=len(generated_text.split()) + 10,
            temperature=0.7,
            raw_mode=True,
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
    assistant_prefix: str | None = None,
) -> tuple[str, list[float]]:
    """Generate from OpenAI API with logprobs.

    When assistant_prefix is provided, adds it as a prior assistant
    message so the model continues from that point (prefill pattern).
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    if assistant_prefix:
        messages.append({"role": "assistant", "content": assistant_prefix})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "logprobs": True,
        "top_logprobs": 5,
    }

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


async def anthropic_generate(
    prompt: str,
    system: str = "",
    model: str = "claude-opus-4-6",
    max_tokens: int = 200,
    temperature: float = 0.3,
) -> tuple[str, list[float]]:
    """Generate from Anthropic API or Claude CLI fallback."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if api_key:
        # Direct API path
        headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        if system:
            payload["system"] = system

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise RuntimeError(f"Anthropic error {resp.status}: {error}")
                data = await resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
    else:
        # CLI fallback — uses existing Claude Code auth
        text = await _claude_cli_generate(prompt, system, model, max_tokens)

    entropy_per_token = []  # No logprobs from Anthropic
    return text, entropy_per_token


async def _claude_cli_generate(
    prompt: str,
    system: str = "",
    model: str = "claude-opus-4-6",
    max_tokens: int = 200,
) -> str:
    """Generate via Claude Code CLI using existing auth."""
    import subprocess

    cli_path = os.getenv(
        "CLAUDE_CODE_EXECPATH",
        r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
    )

    full_prompt = prompt
    if system:
        full_prompt = f"[System: {system}]\n\n{prompt}\n\n[Respond in {max_tokens} tokens or less. Be concise.]"

    try:
        result = subprocess.run(
            [cli_path, "-p", full_prompt, "--model", model, "--max-turns", "1"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI error: {result.stderr[:300]}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("Claude CLI timeout after 120s")


# ---------------------------------------------------------------------------
# Provider routing helper
# ---------------------------------------------------------------------------
async def _route_generate(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
) -> tuple[str, list[float]]:
    """Route generation to the appropriate provider."""
    provider = model_cfg["provider"]
    model_name = model_cfg["name"]

    if provider == "ollama":
        return await ollama_generate(session, model_name, prompt, system, max_tokens)
    elif provider == "anthropic":
        return await anthropic_generate(prompt, system, model_name, max_tokens)
    elif provider == "openai":
        return await openai_generate(prompt, system, model_name, max_tokens)
    else:
        raise RuntimeError(f"Unknown provider: {provider}")


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

    text, entropy = await _route_generate(
        session, model_cfg, prompt_text, system, max_tokens
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


async def _plan_next_burst(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt_text: str,
    full_text: str,
    system: str = "",
) -> str:
    """L5: Ask the model to analyze what's missing and plan the next burst.

    This is the Mythos-style move — instead of blindly continuing,
    the system introspects on what it has vs. what's needed, then
    generates a focused directive for the next burst.
    """
    plan_prompt = (
        f"Original task:\n{prompt_text}\n\n"
        f"What has been written so far:\n{full_text}\n\n"
        f"Analyze what has been covered and what is still MISSING or INCOMPLETE. "
        f"In 1-2 sentences, state exactly what the next section should focus on. "
        f"Be specific. Do not repeat what's done."
    )

    plan_text, _ = await _route_generate(
        session, model_cfg, plan_prompt, system, max_tokens=60
    )

    return plan_text.strip()


async def _burst_generate(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt_text: str,
    full_text: str,
    system: str,
    max_tokens: int,
    plan: str | None = None,
) -> tuple[str, list[float]]:
    """Generate a burst, using the best continuation method per provider.

    For Ollama: raw prefix mode — model sees prompt+output as one stream.
    For OpenAI: assistant prefill — model continues from prior output.
    For Anthropic/CLI: re-anchor with instructions (best we can do).
    """
    provider = model_cfg["provider"]

    if provider == "ollama":
        # Raw prefix: model sees this as one continuous text and continues it
        if plan:
            prefix = f"{prompt_text}\n\n{full_text}\n\n[Next: {plan}]\n\n"
        else:
            prefix = f"{prompt_text}\n\n{full_text}"
        return await ollama_generate(
            session, model_cfg["name"], prefix, system, max_tokens,
            raw_mode=True,
        )
    elif provider == "openai":
        # Assistant prefill: OpenAI continues from assistant's prior output
        messages_prompt = prompt_text
        if plan:
            messages_prompt += f"\n\n[Next section should focus on: {plan}]"
        return await openai_generate(
            messages_prompt, system, model_cfg["name"], max_tokens,
            assistant_prefix=full_text,
        )
    else:
        # Anthropic/CLI: instruction-based re-anchor (no raw mode available)
        if plan:
            context = (
                f"{prompt_text}\n\n"
                f"[Here is what you have written so far:]\n{full_text}\n\n"
                f"[PLAN for next section: {plan}]\n\n"
                f"[Write ONLY the next part. Do not repeat what was already written.]"
            )
        else:
            context = (
                f"{prompt_text}\n\n"
                f"[Continue from where you left off. Here is what you have written so far:]\n"
                f"{full_text}\n\n"
                f"[Continue writing the next part. Do not repeat what was already written.]"
            )
        return await _route_generate(session, model_cfg, context, system, max_tokens)


async def generate_burst(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    prompt_text: str,
    strategy_cfg: dict,
    system: str = "",
) -> tuple[str, list[SpanResult], int, int]:
    """L2/L3/L4/L5: Burst generation with re-anchoring and optional checks.

    Key design: uses provider-native continuation (Ollama raw prefix,
    OpenAI assistant prefill) so the model CONTINUES from prior output
    instead of re-answering the prompt each time.
    """
    burst_size = strategy_cfg["burst_size"]
    max_tokens = strategy_cfg["max_tokens"]
    do_entropy = strategy_cfg["entropy_check"]
    do_contradiction = strategy_cfg["contradiction_check"]
    do_plan = strategy_cfg.get("plan_next", False)

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

        if full_text:
            reanchors += 1

            # L5: Plan what to write next based on gap analysis
            plan = None
            if do_plan:
                plan = await _plan_next_burst(
                    session, model_cfg, prompt_text, full_text, system
                )

            text, entropy = await _burst_generate(
                session, model_cfg, prompt_text, full_text,
                system, this_burst, plan=plan,
            )
        else:
            # First burst — normal generation
            text, entropy = await _route_generate(
                session, model_cfg, prompt_text, system, this_burst
            )

        if not text.strip():
            break  # Model produced nothing, probably done

        was_rerun = False
        rerun_reason = None

        # Entropy estimation (L3+): probe uncertainty via multi-sample variance
        if do_entropy and model_cfg["provider"] == "ollama":
            prefix = f"{prompt_text}\n\n{full_text}" if full_text else prompt_text
            entropy = await ollama_entropy_probe(
                session, model_cfg["name"], prefix, text, system,
            )

        # Entropy check (L3+): if entropy too high, re-run with grounding
        if do_entropy and entropy:
            mean_ent = sum(entropy) / len(entropy)
            if mean_ent > ENTROPY_RERUN_THRESHOLD:
                reruns += 1
                was_rerun = True
                rerun_reason = f"entropy={mean_ent:.2f} > {ENTROPY_RERUN_THRESHOLD}"

                # Re-run with stronger system prompt grounding
                grounded_system = (
                    (system + "\n\n" if system else "")
                    + "IMPORTANT: Stay strictly factual. Only state things "
                    "you are confident about. Do not speculate."
                )
                if model_cfg["provider"] == "ollama":
                    prefix = f"{prompt_text}\n\n{full_text}" if full_text else prompt_text
                    text, entropy = await ollama_generate(
                        session, model_cfg["name"], prefix, grounded_system,
                        this_burst, raw_mode=True,
                    )
                else:
                    text, entropy = await _route_generate(
                        session, model_cfg,
                        f"{prompt_text}\n\n[Stay factual. Prior output:]\n{full_text}\n\n[Continue carefully.]",
                        system, this_burst,
                    )

        # Contradiction check (L4): compare new span against prior spans
        if do_contradiction and len(spans) > 0 and text.strip():
            contradiction_detected = _simple_contradiction_check(full_text, text)
            if contradiction_detected:
                reruns += 1
                was_rerun = True
                rerun_reason = (rerun_reason or "") + " + contradiction_detected"

                consistency_system = (
                    (system + "\n\n" if system else "")
                    + "IMPORTANT: You must stay consistent with everything "
                    "you have already written. Do not contradict prior statements."
                )
                if model_cfg["provider"] == "ollama":
                    prefix = f"{prompt_text}\n\n{full_text}" if full_text else prompt_text
                    text, entropy = await ollama_generate(
                        session, model_cfg["name"], prefix, consistency_system,
                        this_burst, raw_mode=True,
                    )
                else:
                    text, entropy = await _route_generate(
                        session, model_cfg,
                        f"{prompt_text}\n\n[Stay consistent with:]\n{full_text}\n\n[Continue without contradicting.]",
                        system, this_burst,
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
