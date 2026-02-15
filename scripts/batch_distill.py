"""
Batch Distillation — Fix catastrophic forgetting with proper training.

Three-phase approach:
  Phase 1: Collect all training data from GPT-4o-mini (no training yet)
  Phase 2: Train SentencePiece BPE tokenizer on full corpus
  Phase 3: Train DNNT from scratch on shuffled batches at low LR

This replaces the sequential single-example training that caused EOS collapse.

Usage:
    cd d:\\AI_round2
    .venv\\Scripts\\python.exe scripts/batch_distill.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import torch

from personal_agent.dnnt.model import DNNTMicroTransformer, DNNTConfig
from personal_agent.dnnt.trainer import ReasoningTrainer, TrainingConfig, ReasoningDataset
from personal_agent.dnnt.data_extractor import TrainingExample
from personal_agent.dnnt.trust_gate import TrustGate, TrustGateConfig
from personal_agent.dnnt.github_models_provider import GitHubModelsClient
from personal_agent.dnnt.tokenizer_bpe import SentencePieceTokenizer

# ── Paths ──────────────────────────────────────────────────────────────
MODEL_DIR = PROJECT_ROOT / "models" / "dnnt_v2"
CORPUS_PATH = PROJECT_ROOT / "data" / "distillation_corpus.jsonl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ── Training Corpus ────────────────────────────────────────────────────
# 50 diverse questions covering general knowledge, science, tech, and personal facts
QUESTIONS = [
    # General knowledge (20)
    ("What is gravity?", []),
    ("How does electricity work?", []),
    ("What causes thunder?", []),
    ("How do computers store data?", []),
    ("What is DNA?", []),
    ("Why do we dream?", []),
    ("How does WiFi work?", []),
    ("What is machine learning?", []),
    ("Why do leaves change color in autumn?", []),
    ("How does a battery work?", []),
    ("What is an atom?", []),
    ("How do airplanes fly?", []),
    ("What causes earthquakes?", []),
    ("How does the human brain work?", []),
    ("What is blockchain?", []),
    ("Why does ice float on water?", []),
    ("How do vaccines work?", []),
    ("What is quantum computing?", []),
    ("Why do we need sleep?", []),
    ("How does GPS work?", []),
    # Science & nature (10)
    ("What is photosynthesis?", []),
    ("Why is the sky blue?", []),
    ("How do magnets work?", []),
    ("What causes tides?", []),
    ("How does sound travel?", []),
    ("What is a black hole?", []),
    ("Why do stars twinkle?", []),
    ("How does evolution work?", []),
    ("What is the speed of light?", []),
    ("How do volcanoes form?", []),
    # Tech & computing (10)
    ("What is an API?", []),
    ("How does encryption work?", []),
    ("What is a neural network?", []),
    ("How does a database index work?", []),
    ("What is containerization in software?", []),
    ("How does garbage collection work in programming?", []),
    ("What is the difference between TCP and UDP?", []),
    ("How does version control work?", []),
    ("What is a hash function?", []),
    ("How does HTTP work?", []),
    # Personal facts (10) — these have trust-scored facts
    ("What is my name?", ["name=Nick (trust=0.95)", "role=developer (trust=0.88)"]),
    ("Where do I live?", ["location=Wisconsin (trust=0.92)", "name=Nick (trust=0.95)"]),
    ("What do I do for work?", ["role=freelance full-stack developer (trust=0.88)", "name=Nick (trust=0.95)"]),
    ("What projects am I working on?", ["project=CRT-GroundCheck-SSE (trust=0.95)", "project=CogniForge (trust=0.90)", "project=GroundCheck (trust=0.92)", "name=Nick (trust=0.95)"]),
    ("What is my favorite programming language?", ["favorite_language=Python (trust=0.90)", "name=Nick (trust=0.95)"]),
    ("Who am I?", ["name=Nick (trust=0.95)", "role=freelance full-stack developer (trust=0.88)", "location=Wisconsin (trust=0.92)"]),
    ("What do you know about me?", ["name=Nick (trust=0.95)", "role=freelance full-stack developer (trust=0.88)", "location=Wisconsin (trust=0.92)", "project=CRT-GroundCheck-SSE (trust=0.95)"]),
    ("What tech stack do I use?", ["stack=React, Python, Node.js (trust=0.88)", "name=Nick (trust=0.95)"]),
    ("Tell me about my main project.", ["project=CRT-GroundCheck-SSE: trust-weighted memory system for AI agents (trust=0.95)", "name=Nick (trust=0.95)"]),
    ("Say my name.", ["name=Nick (trust=0.95)"]),
]


def phase1_collect(client: GitHubModelsClient, gate: TrustGate) -> list[TrainingExample]:
    """Phase 1: Collect all training data from teacher. No training yet."""
    print("\n" + "=" * 60)
    print("  PHASE 1: Collecting training data from GPT-4o-mini")
    print("=" * 60)

    # Load existing corpus if resuming
    existing: list[TrainingExample] = []
    existing_queries: set[str] = set()
    if CORPUS_PATH.exists():
        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ex = TrainingExample(
                        query=data["query"],
                        facts=data.get("facts", []),
                        thinking=data.get("thinking", ""),
                        response=data["response"],
                        confidence=data.get("confidence", 0.7),
                    )
                    existing.append(ex)
                    existing_queries.add(ex.query)
                except Exception:
                    continue
        print(f"  Loaded {len(existing)} existing examples from corpus")

    # Collect new examples
    new_examples: list[TrainingExample] = []
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)

    for i, (query, facts) in enumerate(QUESTIONS, 1):
        if query in existing_queries:
            print(f"  [{i}/{len(QUESTIONS)}] SKIP (already collected): {query[:50]}")
            continue

        print(f"  [{i}/{len(QUESTIONS)}] {query[:50]}...", end="", flush=True)

        try:
            thinking, response = client.chat(query, facts)
        except Exception as e:
            print(f" ERROR: {e}")
            time.sleep(30)
            continue

        # TrustGate check
        accepted, reason = gate.should_accept(facts=facts)
        if not accepted:
            print(f" REJECTED: {reason}")
            continue

        example = TrainingExample(
            query=query,
            facts=facts,
            thinking=thinking,
            response=response,
            confidence=0.85,
        )
        new_examples.append(example)

        # Append to corpus file immediately (resumable)
        with open(CORPUS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")

        print(f" OK ({len(response)} chars)")

        # Rate limit kindness
        if i < len(QUESTIONS):
            time.sleep(1.5)

    all_examples = existing + new_examples
    print(f"\n  Total corpus: {len(all_examples)} examples ({len(new_examples)} new)")
    return all_examples


def phase2_tokenizer(examples: list[TrainingExample]) -> SentencePieceTokenizer:
    """Phase 2: Train SentencePiece BPE tokenizer on full corpus."""
    print("\n" + "=" * 60)
    print("  PHASE 2: Training SentencePiece BPE tokenizer")
    print("=" * 60)

    # Collect all training text
    texts = [ex.to_training_format() for ex in examples]
    print(f"  Corpus size: {len(texts)} documents, {sum(len(t) for t in texts):,} chars")

    # Check if tokenizer already exists (resume)
    tokenizer_dir = str(MODEL_DIR / "tokenizer_assets")
    tokenizer_model = Path(tokenizer_dir) / "tokenizer_sentencepiece.model"
    if tokenizer_model.exists():
        print(f"  Loading existing tokenizer from {tokenizer_dir}")
        tokenizer = SentencePieceTokenizer(str(tokenizer_model))
    else:
        # Train tokenizer
        tokenizer = SentencePieceTokenizer.train_from_texts(
            texts=texts,
            model_dir=tokenizer_dir,
            vocab_size=4000,  # Smaller vocab for small corpus — will grow dynamically
        )

    # Verify encoding roundtrip
    test_text = examples[0].to_training_format()
    encoded = tokenizer.encode(test_text, add_special_tokens=True)
    decoded = tokenizer.decode(encoded)

    # Check special tokens survived
    for tag in ["<query>", "</query>", "<think>", "</think>", "<response>", "</response>"]:
        assert tag in decoded, f"Special token {tag} lost in roundtrip!"

    print(f"  Vocab size: {tokenizer.vocab_size}")
    print(f"  Test encode/decode roundtrip: {'PASS' if test_text[:50] in decoded else 'WARN (partial)'}")
    print(f"  Avg tokens per example: {sum(len(tokenizer.encode(t)) for t in texts) / len(texts):.0f}")

    # Compare to char tokenizer
    from personal_agent.dnnt.model import SimpleTokenizer
    char_tok = SimpleTokenizer()
    char_lens = [len(char_tok.encode(t)) for t in texts]
    bpe_lens = [len(tokenizer.encode(t)) for t in texts]
    ratio = sum(char_lens) / max(sum(bpe_lens), 1)
    print(f"  Compression ratio vs char tokenizer: {ratio:.1f}x")

    return tokenizer


def phase3_train(
    examples: list[TrainingExample],
    tokenizer: SentencePieceTokenizer,
) -> DNNTMicroTransformer:
    """Phase 3: Train DNNT from scratch on shuffled batches."""
    print("\n" + "=" * 60)
    print("  PHASE 3: Training DNNT from scratch (batch mode)")
    print("=" * 60)

    # Split train/val (90/10)
    import random
    random.seed(42)
    shuffled = list(examples)
    random.shuffle(shuffled)
    split = max(1, int(len(shuffled) * 0.9))
    train_examples = shuffled[:split]
    val_examples = shuffled[split:] if split < len(shuffled) else []

    print(f"  Train: {len(train_examples)} examples")
    print(f"  Val:   {len(val_examples)} examples")

    # Create fresh model
    config = DNNTConfig(
        vocab_size=max(tokenizer.vocab_size, 4000),
        hidden_dim=256,
        num_layers=4,
        num_heads=4,
        max_seq_length=512,
    )
    model = DNNTMicroTransformer(config).to(DEVICE)
    print(f"  Model: {model.n_params:,} params on {DEVICE}")

    # Training config — key changes from before:
    # - batch_size=8 (not 1) — shuffled mini-batches
    # - lr=5e-5 (not 1e-4) — 2x lower to prevent catastrophic updates
    # - Many epochs over the full dataset — 50 examples needs 150+ epochs to converge
    steps_per_epoch = max(1, len(train_examples) // 4)
    num_epochs = 150
    max_steps = steps_per_epoch * num_epochs

    train_config = TrainingConfig(
        batch_size=4,
        learning_rate=3e-4,
        weight_decay=0.01,
        max_steps=max_steps,
        save_every=max(200, max_steps // 5),
        eval_every=max(50, max_steps // 15),
        log_every=max(25, max_steps // 30),
        device=DEVICE,
        mixed_precision=(DEVICE == "cuda"),
        output_dir=str(MODEL_DIR),
        max_seq_length=512,
    )

    print(f"  LR: {train_config.learning_rate}")
    print(f"  Batch size: {train_config.batch_size}")
    print(f"  Max steps: {max_steps} (~{num_epochs} epochs)")
    print()

    # Train
    trainer = ReasoningTrainer(
        config=train_config,
        tokenizer=tokenizer,
        train_examples=train_examples,
        val_examples=val_examples,
        model=model,
    )
    trainer.train()

    # Save final model + tokenizer
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(MODEL_DIR))
    tokenizer.save(str(MODEL_DIR / "tokenizer.json"))

    return model


def test_generation(model: DNNTMicroTransformer, tokenizer) -> None:
    """Test model generation quality after training."""
    print("\n" + "=" * 60)
    print("  GENERATION TEST")
    print("=" * 60)

    model.eval()
    test_cases = [
        ("What is my name?", ["name=Nick (trust=0.95)", "role=developer (trust=0.88)"]),
        ("What is gravity?", []),
        ("Where do I live?", ["location=Wisconsin (trust=0.92)", "name=Nick (trust=0.95)"]),
        ("What is an API?", []),
        ("What projects am I working on?", ["project=CRT-GroundCheck-SSE (trust=0.95)", "project=CogniForge (trust=0.90)", "name=Nick (trust=0.95)"]),
    ]

    for query, facts in test_cases:
        facts_str = "\n".join(f"- {f}" for f in facts) if facts else "(no facts)"
        prompt = f"<query>{query}</query>\n<facts>\n{facts_str}\n</facts>\n<think>"

        tokens = tokenizer.encode(prompt, add_special_tokens=True)
        input_ids = torch.tensor([tokens], device=DEVICE)

        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=150,
                temperature=0.5,
                top_k=40,
                top_p=0.9,
                stop_tokens=[
                    tokenizer.special_tokens.get("</response>", 11),
                    tokenizer.special_tokens.get("<eos>", 2),
                ],
            )

        output_text = tokenizer.decode(output_ids[0].tolist())

        # Extract thinking and response
        thinking = ""
        response = ""
        if "<think>" in output_text and "</think>" in output_text:
            s = output_text.index("<think>") + len("<think>")
            e = output_text.index("</think>")
            thinking = output_text[s:e].strip()
        if "<response>" in output_text:
            s = output_text.index("<response>") + len("<response>")
            e = output_text.index("</response>") if "</response>" in output_text[s:] else len(output_text)
            response = output_text[s:e].strip()

        # EOS probability check
        logits, _ = model(input_ids)
        probs = torch.softmax(logits[0, -1, :], dim=-1)
        eos_prob = probs[model.config.eos_token_id].item()

        print(f"\n  Q: {query}")
        print(f"  Thinking: {thinking[:100] if thinking else '(empty)'}")
        print(f"  Response: {response[:100] if response else '(empty)'}")
        print(f"  EOS prob: {eos_prob:.4f} ({'OK' if eos_prob < 0.5 else 'HIGH'})")


def main():
    print("=" * 60)
    print("  BATCH DISTILLATION — Fixing catastrophic forgetting")
    print("  BPE tokenizer + shuffled batches + lower LR")
    print("=" * 60)

    start = time.time()

    # Init teacher + gate
    client = GitHubModelsClient(model="gpt-4o-mini", max_retries=3, retry_delay=30.0)
    gate = TrustGate(TrustGateConfig(
        min_fact_trust=0.55,
        max_unresolved_contradictions=0,
        require_groundcheck_pass=False,
    ))

    # Phase 1: Collect
    examples = phase1_collect(client, gate)
    if not examples:
        print("ERROR: No training examples collected. Check API connection.")
        return

    # Phase 2: Tokenizer
    tokenizer = phase2_tokenizer(examples)

    # Phase 3: Train
    model = phase3_train(examples, tokenizer)

    # Test
    test_generation(model, tokenizer)

    # Summary
    elapsed = time.time() - start
    stats = client.stats()
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total time:     {elapsed/60:.1f} minutes")
    print(f"  Examples:       {len(examples)}")
    print(f"  API calls:      {stats['total_calls']}")
    print(f"  Total tokens:   {stats['total_input_tokens'] + stats['total_output_tokens']}")
    print(f"  Model saved to: {MODEL_DIR}")
    print(f"  Tokenizer:      SentencePiece BPE (vocab={tokenizer.vocab_size})")
    print("=" * 60)


if __name__ == "__main__":
    main()
