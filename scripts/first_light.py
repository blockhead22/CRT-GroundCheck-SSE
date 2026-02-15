"""
First Light — End-to-end DNNT distillation loop.

One script. One cycle. Prove the architecture works.

Flow:
  1. Init a fresh DNNT (or load existing)
  2. Ask it a question → it flops (low confidence)
  3. TrustGate routes to GPT-4o-mini via GitHub Models
  4. TrustGate scores the response (trust > threshold, no contradictions)
  5. Accepted → fine-tune DNNT on that single example
  6. Ask the SAME question again → measure confidence improvement
  7. Log every step with timestamps

Usage:
    cd d:\\AI_round2
    .venv\\Scripts\\python.exe scripts/first_light.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import torch

from personal_agent.dnnt.model import DNNTMicroTransformer, DNNTConfig, SimpleTokenizer, expand_model_vocab
from personal_agent.dnnt.trainer import ReasoningTrainer, TrainingConfig, ReasoningDataset
from personal_agent.dnnt.data_extractor import TrainingExample
from personal_agent.dnnt.trust_gate import TrustGate, TrustGateConfig
from personal_agent.dnnt.github_models_provider import GitHubModelsClient


# ── Config ──────────────────────────────────────────────────────────────
MODEL_DIR = PROJECT_ROOT / "models" / "dnnt_firstlight"
LOG_PATH = PROJECT_ROOT / "data" / "first_light_log.jsonl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Test questions — things a tiny model will definitely flop on
TEST_QUESTIONS = [
    {
        "query": "Why do cats hate water?",
        "facts": [],
    },
    {
        "query": "What is photosynthesis?",
        "facts": [],
    },
    {
        "query": "Who invented the internet?",
        "facts": [],
    },
    {
        "query": "Why is the sky blue?",
        "facts": [],
    },
    {
        "query": "What is my name?",
        "facts": ["name=Nick (trust=0.95)", "role=developer (trust=0.88)"],
    },
]


def log_event(event: dict) -> None:
    """Append a timestamped event to the log file."""
    event["timestamp"] = time.time()
    event["iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    # Also print
    tag = event.get("event", "???")
    detail = event.get("detail", "")
    print(f"  [{tag}] {detail}")


def init_model() -> tuple[DNNTMicroTransformer, SimpleTokenizer]:
    """Load existing model or create fresh one."""
    model_pt = MODEL_DIR / "model.pt"
    if model_pt.exists():
        log_event({"event": "model_load", "detail": f"Loading from {MODEL_DIR}"})
        config = DNNTConfig.load(str(MODEL_DIR / "config.json"))
        model = DNNTMicroTransformer(config)
        model.load_state_dict(torch.load(model_pt, map_location=DEVICE))
        model = model.to(DEVICE)

        tok_path = MODEL_DIR / "tokenizer.json"
        tokenizer = SimpleTokenizer.load(str(tok_path)) if tok_path.exists() else SimpleTokenizer()
        log_event({"event": "model_loaded", "detail": f"{model.n_params:,} params on {DEVICE}"})
        return model, tokenizer

    log_event({"event": "model_init", "detail": "Creating fresh DNNT"})
    config = DNNTConfig(
        vocab_size=8000,
        hidden_dim=256,
        num_layers=4,
        num_heads=4,
        max_seq_length=512,
    )
    model = DNNTMicroTransformer(config).to(DEVICE)
    tokenizer = SimpleTokenizer(vocab_size=config.vocab_size)
    log_event({"event": "model_created", "detail": f"{model.n_params:,} params, {DEVICE}"})
    return model, tokenizer


@torch.no_grad()
def probe_model(
    model: DNNTMicroTransformer,
    tokenizer: SimpleTokenizer,
    query: str,
    facts: list[str],
    label: str = "probe",
) -> tuple[str, str, float]:
    """Run query through model and return (thinking, response, confidence)."""
    model.eval()

    facts_str = "\n".join(f"- {f}" for f in facts) if facts else "(no facts)"
    prompt = f"<query>{query}</query>\n<facts>\n{facts_str}\n</facts>\n<think>"

    tokens = tokenizer.encode(prompt, add_special_tokens=True)
    input_ids = torch.tensor([tokens], device=DEVICE)

    output_ids = model.generate(
        input_ids,
        max_new_tokens=128,
        temperature=0.7,
        stop_tokens=[
            tokenizer.special_tokens.get("</response>", 11),
            tokenizer.special_tokens.get("<eos>", 2),
        ],
    )

    output_text = tokenizer.decode(output_ids[0].tolist())

    # Extract sections
    thinking = _extract(output_text, "<think>", "</think>")
    response = _extract(output_text, "<response>", "</response>")

    # Perplexity-based confidence
    gen_start = input_ids.shape[1]
    logits, _ = model(output_ids)
    if output_ids.shape[1] > gen_start:
        gen_logits = logits[:, gen_start - 1 : -1, :]
        gen_targets = output_ids[:, gen_start:]
        if gen_logits.shape[1] > 0 and gen_targets.shape[1] > 0:
            min_len = min(gen_logits.shape[1], gen_targets.shape[1])
            loss = torch.nn.functional.cross_entropy(
                gen_logits[:, :min_len].reshape(-1, gen_logits.size(-1)),
                gen_targets[:, :min_len].reshape(-1),
                reduction="mean",
            )
            ppl = torch.exp(loss).item()
            confidence = max(0.0, min(1.0, 1.0 - (ppl - 1) / 50))
        else:
            confidence = 0.0
    else:
        confidence = 0.0

    log_event({
        "event": label,
        "query": query,
        "response_preview": (response or output_text)[:120],
        "confidence": round(confidence, 4),
        "detail": f"conf={confidence:.4f} | resp_len={len(response)}",
    })

    return thinking, response, confidence


def _extract(text: str, start_tag: str, end_tag: str) -> str:
    try:
        if start_tag in text:
            s = text.index(start_tag) + len(start_tag)
            e = text.index(end_tag, s) if end_tag in text[s:] else len(text)
            return text[s:e].strip()
    except Exception:
        pass
    return ""


def call_teacher(
    client: GitHubModelsClient,
    query: str,
    facts: list[str],
) -> tuple[str, str]:
    """Call 4o-mini and return (thinking, response)."""
    log_event({"event": "teacher_call", "detail": f"Asking {client.model}: {query[:60]}"})
    thinking, response = client.chat(query, facts)
    log_event({
        "event": "teacher_response",
        "detail": f"Got {len(response)} chars",
        "thinking_preview": thinking[:100],
        "response_preview": response[:120],
    })
    return thinking, response


def trust_gate_check(
    facts: list[str],
    meta: dict | None = None,
) -> tuple[bool, str]:
    """Run TrustGate on the example."""
    gate = TrustGate(TrustGateConfig(
        min_fact_trust=0.55,
        max_unresolved_contradictions=0,
        require_groundcheck_pass=False,
        reject_if_corrected_within_turns=0,
    ))
    accepted, reason = gate.should_accept(facts=facts, meta=meta or {})
    log_event({
        "event": "trust_gate",
        "accepted": accepted,
        "reason": reason,
        "detail": f"{'ACCEPTED' if accepted else 'REJECTED'}: {reason}",
    })
    return accepted, reason


def train_on_example(
    model: DNNTMicroTransformer,
    tokenizer: SimpleTokenizer,
    example: TrainingExample,
    steps: int = 50,
    lr: float = 1e-4,
) -> dict:
    """Fine-tune the model on a single example. Return loss stats."""
    log_event({
        "event": "train_start",
        "detail": f"Fine-tuning on 1 example for {steps} steps (lr={lr})",
    })

    # Expand vocab if needed
    expand_model_vocab(model, tokenizer, [example.to_training_format()])

    # Build dataset
    dataset = ReasoningDataset([example], tokenizer, max_length=512)
    loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False)
    batch = next(iter(loader))

    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    losses = []
    for step in range(steps):
        input_ids = batch["input_ids"].to(DEVICE)
        labels = batch["labels"].to(DEVICE)
        _, loss = model(input_ids, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        optimizer.zero_grad()
        losses.append(loss.item())

        if (step + 1) % 10 == 0:
            breakdown = model.get_last_loss_breakdown()
            log_event({
                "event": "train_step",
                "step": step + 1,
                "loss": round(losses[-1], 4),
                "detail": f"step {step+1}/{steps} loss={losses[-1]:.4f}",
                "breakdown": {k: round(v, 4) for k, v in breakdown.items()},
            })

    # Save checkpoint
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(MODEL_DIR))
    tokenizer.save(str(MODEL_DIR / "tokenizer.json"))

    stats = {
        "initial_loss": round(losses[0], 4),
        "final_loss": round(losses[-1], 4),
        "loss_delta": round(losses[0] - losses[-1], 4),
        "steps": steps,
    }
    log_event({
        "event": "train_complete",
        "detail": f"loss {stats['initial_loss']:.4f} → {stats['final_loss']:.4f} (Δ={stats['loss_delta']:.4f})",
        **stats,
    })
    return stats


def run_cycle(
    model: DNNTMicroTransformer,
    tokenizer: SimpleTokenizer,
    client: GitHubModelsClient,
    query: str,
    facts: list[str],
    train_steps: int = 50,
) -> dict:
    """Run one full distillation cycle for a single query."""
    print(f"\n{'='*60}")
    print(f"  QUERY: {query}")
    print(f"  FACTS: {facts}")
    print(f"{'='*60}")

    cycle_log: dict = {"query": query, "facts": facts}

    # Step 1: Probe DNNT (expect low confidence)
    _, pre_response, pre_conf = probe_model(model, tokenizer, query, facts, label="pre_probe")
    cycle_log["pre_confidence"] = pre_conf
    cycle_log["pre_response"] = pre_response[:200]

    # Step 2: Call teacher
    thinking, response = call_teacher(client, query, facts)
    cycle_log["teacher_thinking"] = thinking[:300]
    cycle_log["teacher_response"] = response[:300]

    # Step 3: TrustGate check
    accepted, reason = trust_gate_check(facts)
    cycle_log["trust_gate_accepted"] = accepted
    cycle_log["trust_gate_reason"] = reason

    if not accepted:
        log_event({
            "event": "cycle_skip",
            "detail": f"TrustGate rejected: {reason}. Skipping training.",
        })
        cycle_log["trained"] = False
        return cycle_log

    # Step 4: Build training example
    example = TrainingExample(
        query=query,
        facts=facts,
        thinking=thinking,
        response=response,
    )

    # Step 5: Train
    train_stats = train_on_example(model, tokenizer, example, steps=train_steps)
    cycle_log["train_stats"] = train_stats

    # Step 6: Re-probe (measure improvement)
    _, post_response, post_conf = probe_model(model, tokenizer, query, facts, label="post_probe")
    cycle_log["post_confidence"] = post_conf
    cycle_log["post_response"] = post_response[:200]

    # Step 7: Summary
    delta = post_conf - pre_conf
    cycle_log["confidence_delta"] = round(delta, 4)
    cycle_log["trained"] = True

    summary_msg = (
        f"Confidence: {pre_conf:.4f} → {post_conf:.4f} (Δ={delta:+.4f}) | "
        f"Loss: {train_stats['initial_loss']:.4f} → {train_stats['final_loss']:.4f}"
    )
    log_event({"event": "cycle_complete", "detail": summary_msg})
    print(f"\n  ✓ {summary_msg}")

    return cycle_log


def main():
    print("=" * 60)
    print("  FIRST LIGHT — DNNT Distillation Loop")
    print("  One question. One teacher. One student. Prove it works.")
    print("=" * 60)

    log_event({"event": "session_start", "detail": "First Light distillation session"})

    # Init
    model, tokenizer = init_model()
    client = GitHubModelsClient(model="gpt-4o-mini", max_retries=3, retry_delay=30.0)

    log_event({
        "event": "teacher_ready",
        "detail": f"Teacher: {client.model} via GitHub Models API",
    })

    # Run cycles
    results = []
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─'*60}")
        print(f"  Cycle {i}/{len(TEST_QUESTIONS)}")
        print(f"{'─'*60}")

        cycle = run_cycle(
            model, tokenizer, client,
            query=q["query"],
            facts=q["facts"],
            train_steps=50,
        )
        results.append(cycle)

        # Brief pause between cycles to be kind to rate limits
        if i < len(TEST_QUESTIONS):
            time.sleep(2)

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)

    trained_cycles = [r for r in results if r.get("trained")]
    if trained_cycles:
        avg_pre = sum(r["pre_confidence"] for r in trained_cycles) / len(trained_cycles)
        avg_post = sum(r["post_confidence"] for r in trained_cycles) / len(trained_cycles)
        avg_delta = avg_post - avg_pre

        print(f"  Cycles completed:   {len(results)}")
        print(f"  Cycles trained:     {len(trained_cycles)}")
        print(f"  Avg pre-confidence: {avg_pre:.4f}")
        print(f"  Avg post-confidence:{avg_post:.4f}")
        print(f"  Avg improvement:    {avg_delta:+.4f}")
    else:
        print("  No training cycles completed (all rejected by TrustGate)")

    api_stats = client.stats()
    print(f"\n  Teacher API calls:  {api_stats['total_calls']}")
    print(f"  Total tokens:       {api_stats['total_input_tokens'] + api_stats['total_output_tokens']}")
    print(f"  API errors:         {api_stats['errors']}")

    print(f"\n  Model saved to:     {MODEL_DIR}")
    print(f"  Full log at:        {LOG_PATH}")
    print("=" * 60)

    log_event({
        "event": "session_complete",
        "detail": f"{len(trained_cycles)} trained, avg_delta={avg_delta:+.4f}" if trained_cycles else "0 trained",
        "api_stats": api_stats,
    })


if __name__ == "__main__":
    main()
