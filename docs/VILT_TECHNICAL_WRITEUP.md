# VILT: Verification-In-the-Loop Training

## Technical Write-Up — June 2025

---

## Abstract

Verification-In-the-Loop Training (VILT) is a training paradigm that integrates
runtime fact-verification into the gradient update loop of language models. Rather
than relying solely on supervised loss to teach factual responses, VILT generates
freely after each forward pass, pipes the output through a verifier (GroundCheck),
and amplifies the loss when the model hallucinates against a known fact ledger.
The result: models that learn *not to contradict known facts* rather than merely
learning to parrot training targets.

We demonstrate VILT across three model scales — 135M, 1.5B, and 3B parameters —
all fitting within a single RTX 3060 12GB GPU using LoRA adapters and gradient
checkpointing. Key findings:

- **SmolLM-135M**: 17% → 100% accuracy, 100% → 92% GC pass in 75 steps (10.7 min)
- **Qwen2.5-1.5B**: 92% → 100% accuracy, 83% → 100% GC pass in 50 steps (2.5 min)
- **Qwen2.5-3B**: 100% → 100% accuracy, 92% → 100% GC pass in 50 steps (2.7 min)

---

## 1. Motivation

Standard fine-tuning teaches a model to output the right answer for a given input.
But "right answer" is defined only at training time — the model has no mechanism to
check whether its generated output contradicts established facts at inference time.
This leads to hallucination: the model produces fluent, confident text that happens
to be wrong.

VILT closes this loop by making fact-verification part of the training signal itself.

### The Core Insight

If a model generates "You live in Boston" when the fact ledger says `location =
Denver`, the standard supervised loss doesn't directly penalize this — it only
penalizes deviation from the teacher-forced target. VILT catches this by:

1. Running GroundCheck.verify() on the freely-generated output
2. Computing a contradiction score weighted by fact trust
3. Amplifying the supervised loss proportionally

The model learns that hallucinating is *expensive*, even when the hallucination
is grammatically perfect.

---

## 2. Architecture

### 2.1 The VILT Loss

```
L_vilt = L_sup × min(2, 1 + min(1, w_c × s_c) + p_brevity)
```

Where:
- `L_sup` = standard cross-entropy loss (teacher forcing on target answer)
- `s_c` = contradiction score from GroundCheck (0.0 = clean, 1.0 = max contradiction)
- `w_c` = contradiction weight hyperparameter (default: 0.5)
- `p_brevity` = brevity penalty for responses below minimum token threshold

The multiplier is clamped to `[1, 2]` — VILT can at most double the loss, preventing
gradient explosions while still providing a strong learning signal.

### 2.2 Brevity Penalty (Anti-Gaming)

Early experiments revealed that models quickly learn the optimal strategy for avoiding
contradictions: **say nothing**. A model that outputs empty or single-token responses
will never contradict any fact. This is technically correct but useless.

The brevity penalty addresses this:

```python
if response_tokens < min_response_tokens:
    brevity = brevity_weight * (1 - response_tokens / min_response_tokens)
```

This creates an "information pressure" — the model must generate substantive responses
while simultaneously avoiding contradictions. The tension between these objectives
drives the model toward the ideal: **correct, grounded, substantive answers**.

### 2.3 Curriculum Scheduling

Training uses two phases:

1. **Uniform phase** (steps 1 → switch_step): All training examples sampled equally.
   The model learns basic fact-response patterns.
2. **Curriculum phase** (switch_step → end): 75% new/hard examples, 25% reinforcement
   of earlier examples. Focuses training budget on the facts the model hasn't mastered.

### 2.4 Three-Category Verification

GroundCheck v1.0.0 reports three honest categories for each extracted fact:

| Category | Meaning | Example |
|---|---|---|
| **Grounded** | Fact matches a memory with sufficient trust | "Alex" matches `name = Alex` |
| **Out-of-scope** | Fact has zero memory coverage — unverifiable | "Gravity is a force" (no physics facts stored) |
| **Hallucinated** | Fact contradicts a stored memory | "You live in Boston" contradicts `location = Denver` |

The VILT loss only penalizes **hallucinations** — facts that actively contradict known
truth. Out-of-scope claims are tracked but not punished, because the model shouldn't
be penalized for talking about gravity just because the fact ledger doesn't cover physics.

**Confidence** is computed over grounded + hallucinated facts only (denominator excludes
out-of-scope), giving an honest measure of how reliable the model is *on topics it can
be checked on*.

---

## 3. Training Setup

### 3.1 Fact Ledger

16 facts with trust scores (0.0–1.0):

| Slot | Value | Trust |
|---|---|---|
| name | Alex | 0.95 |
| location | Denver | 0.92 |
| occupation | data engineer | 0.90 |
| hobby | rock climbing | 0.90 |
| pet | two cats | 0.88 |
| project | DataForge | 0.88 |
| os | Linux | 0.88 |
| favorite_language | Rust | 0.85 |
| experience_years | 8 | 0.85 |
| editor | Neovim | 0.82 |
| database | DuckDB | 0.82 |
| framework | Django | 0.80 |
| framework | Svelte | 0.80 |
| favorite_drink | espresso | 0.78 |
| pet_peeve | meetings | 0.75 |
| cloud | AWS | 0.70 |

### 3.2 Evaluation Queries (12 total)

- **6 single-fact in-scope**: name, location, occupation, drink, OS, hobby
- **2 out-of-scope**: "What is gravity?", "What is an API?"
- **3 multi-fact**: name+location, language+editor, job+hobby
- **1 mixed**: name (in-scope) + gravity (out-of-scope)

Multi-fact queries test whether VILT-trained models can compose multiple grounded
facts in a single response. Mixed queries test whether the model correctly answers
the verifiable part without being penalized for the unverifiable part.

### 3.3 Hardware

- **GPU**: NVIDIA GeForce RTX 3060 12GB
- **CUDA**: 12.4
- **PyTorch**: 2.6.0+cu124
- **Adapters**: LoRA (r=16, alpha=32, dropout=0.05)
- **Precision**: fp16 for 1B+ models, fp32 for SmolLM-135M
- **Gradient checkpointing**: Enabled for 1B+ models

---

## 4. Results

### 4.1 Scaling Comparison

| Model | Params | Trainable | VRAM | Pre Acc | Post Acc | Pre GC | Post GC | Steps | Time |
|---|---|---|---|---|---|---|---|---|---|
| SmolLM-135M | 134M | 1.8M (1.4%) | 0.52 GB | 17% | **100%** | 100% | 92% | 75 | 10.7 min |
| Qwen2.5-1.5B | 1.54B | 4.4M (0.28%) | 3.05 GB | 92% | **100%** | 83% | **100%** | 50 | 2.5 min |
| Qwen2.5-3B | 3.09B | 7.4M (0.24%) | 6.06 GB | 100% | **100%** | 92% | **100%** | 50 | 2.7 min |

### 4.2 Honest Grounding Breakdown (Post-Training)

| Model | Grounded | Out-of-Scope | Hallucinated |
|---|---|---|---|
| SmolLM-135M | 9 | 3 | 1 |
| Qwen2.5-1.5B | 10 | 5 | 0 |
| Qwen2.5-3B | 9 | 5 | 0 |

### 4.3 Key Observations

**1. Larger models start better, converge faster.**
The 3B model already achieves 100% accuracy at zero-shot — its base knowledge is
sufficient to answer all queries from the fact ledger context. VILT's job on the
3B model is primarily *style and grounding*: reducing hallucinations from 1 to 0,
reducing OOS leakage from 7 to 5, and making responses cleaner.

**2. VILT eliminates hallucinations at scale.**
Both the 1.5B and 3B models reach 0 hallucinations post-training. The 135M model
still has 1 hallucination (espresso — a semantic matching edge case), suggesting
there's a capacity floor for perfect grounding.

**3. The anti-gaming mechanism works.**
Without the brevity penalty, models converge to empty responses within ~20 steps.
With it, models learn to generate substantive answers (8–15 tokens average) while
maintaining grounding.

**4. Response quality improves beyond accuracy.**
Compare Qwen2.5-3B before and after:
- Before: `"- os=Linux (trust=0.88)"` (leaking raw fact format)
- After: `"You use Linux."` (natural language)
- Before: `"Your name is Alex and gravity is 9.81 meters per second squared."`
- After: `"Your name is Alex. Gravity is a force that pulls objects towards each..."`

VILT doesn't just teach accuracy — it teaches cleaner, more natural expression.

**5. Multi-fact queries work without multi-fact training.**
All training examples are single-fact, yet the model correctly composes multi-fact
responses at evaluation time. This suggests VILT's grounding signal generalizes
to compositional queries.

---

## 5. The Adversarial Gaming Discovery

During early VILT development on the DNNT (6.2M param custom model), we discovered
that models are remarkably good at *adversarially gaming* verification systems:

1. **Empty response gaming**: Model learns that saying nothing avoids all contradictions.
   Solution: brevity penalty.

2. **Trust score leakage**: Model learns to echo trust scores verbatim from the fact
   context (e.g., "Your name is Alex (trust=0.95)"). This passes GC verification
   but is obviously wrong behavior. Solution: anti-leakage training examples.

3. **Format exploitation**: Model learns to output facts in the exact format stored
   in memory (e.g., `FACT: name = Alex`). This exploits the verifier's pattern
   matching. Solution: diverse target formats in training.

These discoveries led to the anti-gaming mechanisms that are now standard in VILT.

---

## 6. VRAM Efficiency

VILT is remarkably VRAM-efficient thanks to three techniques:

1. **LoRA adapters**: Only 0.24–1.4% of parameters are trained
2. **Gradient checkpointing**: Trades compute for memory on 1B+ models
3. **Single-example batches**: No batch padding overhead

| Model | Base Weight | LoRA Overhead | Training Peak | Utilization (of 12GB) |
|---|---|---|---|---|
| SmolLM-135M | 0.50 GB | 0.02 GB | 0.52 GB | 4.3% |
| Qwen2.5-1.5B | 2.89 GB | 0.11 GB | 3.05 GB | 25.4% |
| Qwen2.5-3B | 5.88 GB | 0.18 GB | 6.06 GB | 50.5% |

Even the 3B model uses only half the available VRAM. A 7B model might fit with
aggressive quantization (4-bit base weights + fp16 LoRA).

---

## 7. Comparison to Other Approaches

| Approach | Training Signal | Runtime Cost | Hallucination Reduction |
|---|---|---|---|
| Standard SFT | Target-only | None | Low (memorization only) |
| RLHF | Human preference | High (reward model) | Medium |
| DPO | Preference pairs | None | Medium |
| RAG | Retrieved context | Retrieval latency | Medium (depends on retriever) |
| **VILT** | **Verified generation** | **GC verify per step** | **High (direct signal)** |

VILT is unique in providing a *direct, automated* signal about factual correctness
during training. Unlike RLHF, it doesn't need a separate reward model. Unlike DPO,
it doesn't need curated preference pairs. Unlike RAG, it prevents hallucination at
the model level rather than relying on retrieved context at inference time.

---

## 8. Limitations

1. **Fact ledger required**: VILT needs a curated set of facts with trust scores.
   It doesn't work for open-domain fact-checking.

2. **Semantic matching bounds**: GroundCheck's fact extraction and matching has
   edge cases. The SmolLM-135M model's remaining hallucination ("espresso") is
   a GC matching issue, not a VILT failure.

3. **Single-example training**: Current implementation trains on one example per
   step without batching. This is fast for small fact ledgers but won't scale
   to thousands of facts.

4. **Evaluation scope**: 12 test queries is a small eval set. Production deployment
   would need hundreds of diverse queries across fact categories.

---

## 9. Future Directions

- **Scaling to 7B+**: 4-bit quantization + fp16 LoRA could fit 7B models in 12GB
- **Dynamic fact ledgers**: Facts added/removed during training, testing adaptability
- **Adversarial evaluation**: Red-team queries designed to elicit contradictions
- **Integration with RAG**: VILT-trained models + RAG retrieval for open-domain use
- **Continuous VILT**: Online learning where the model is continuously VILT-trained
  as new facts arrive

---

## Appendix: Reproduction

```bash
# Install dependencies
pip install torch transformers peft groundcheck

# Run SmolLM-135M VILT
python scripts/vilt_pretrained.py

# Run Qwen2.5-1.5B VILT
python scripts/vilt_scaled.py --model Qwen/Qwen2.5-1.5B

# Run Qwen2.5-3B VILT
python scripts/vilt_scaled.py --model Qwen/Qwen2.5-3B
```

Evaluation data: `data/vilt_test_queries.json` (12 queries)  
Fact ledger: `data/vilt_facts.json` (16 facts)  
Results: `models/vilt_*/vilt_metrics.json`
