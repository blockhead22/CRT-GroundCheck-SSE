# CRT + GroundCheck + SSE

**Hybrid verified agent infrastructure with local memory authority. No silent overwrites.**

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Product: Hybrid Verified](https://img.shields.io/badge/product-hybrid_verified-black.svg)](#what-this-is)
[![Status: Active hardening](https://img.shields.io/badge/status-active%20hardening-orange.svg)](#current-status-march-22-2026)

---

## The Problem

Most assistants still optimize for fluent next-token continuation, not governed memory.

That creates the same repeated failure mode:

- a user states a fact
- the fact is contradicted later
- the assistant silently adopts the new version
- no contradiction is surfaced
- no operator can see why the answer changed

That is acceptable for disposable chat. It is not acceptable for an assistant that is supposed to remember, verify, and act over time.

**CRT exists to make memory, contradiction handling, and answer validation explicit system behavior instead of prompt folklore.**

---

## What This Is

CRT-GroundCheck-SSE is a **hybrid verified agent stack**.

The product direction is no longer "local GPT replacement." The core value is the control layer:

- local memory authority
- contradiction preservation and disclosure
- verifier-gated answering
- model routing
- agentic tool-loop execution
- self-reflection and introspection
- runtime observability

Generation can stay local or escalate to a stronger cloud model. Memory, contradiction checks, verification, routing policy, and traceability stay under the local CRT control layer.

The stack is built from three interlocking systems:

| System | Role |
|--------|------|
| **CRT** (Cognitive Reflective Trust) | Trust, drift, and contradiction governance. Memories carry evolving trust, contradictions are preserved, and reconstruction gates can block unsupported answers. |
| **GroundCheck** | A verification layer that checks generated claims against memory before the system presents them as grounded answers. |
| **SSE** (Semantic String Engine) | Claim extraction and provenance boundaries. Contradictions are preserved instead of silently merged away. |

If you tell the system *"I work at Microsoft"* and later say *"I work at Google"*, both facts survive. A contradiction ledger records the tension. When you later ask *"Where do I work?"*, reconstruction gates surface the contradiction for you to resolve instead of confidently picking a winner.

---

## Current Status (March 22, 2026)

This repository is in active hardening and now targets a **hybrid verified agent** product shape.

The system has crossed from memory-governed chat to a **self-reflecting, tool-chaining agent with real-time observable reasoning**.

Current operating stance:

- `product_mode.mode = "hybrid_verified"`
- local remains the authority for memory, verification, routing, and observability
- cloud generation supported via Anthropic client with token-bucket rate limiting
- cloud-bound context is policy-filtered by channel and slot before send
- **LLM tool loop** is now the primary execution path for task/service actions
- **self-reflection** runs on heartbeat — the agent introspects on its own gate failures, trust deltas, and corrections
- **self-referential routing** handles questions about the agent's own capabilities and state
- the single main startup entrypoint is `start_services.ps1`

Validated environment:

- Windows PowerShell
- Python `3.13`
- local Ollama optional
- cloud provider optional (Anthropic client + rate limiter now production-ready)

Historical benchmark numbers remain below for context and are labeled with dates.

---

## Roadmap

### Phase A: Natural Agent (complete)

Make the agent respond like a real assistant, not a database terminal.

- ~~Natural generative responses instead of hardcoded templates~~
- ~~Open-world fact learning (LLM-driven extraction, not just regex slots)~~
- ~~Provenance-aware answers ("you told me this on Jan 15, trust 0.91")~~
- ~~Conversational contradiction surfacing instead of scaffold blocks~~
- ~~Async post-processing (reflection, active learning off the hot path)~~
- LLM-synthesized broad recall ("what do you know about me?" → topic-grouped natural summary)
- Self-referential question routing (questions about Aether itself use self-model, not user-fact memory)

### Phase B: Hybrid Routing (complete)

Wire local and cloud generation end-to-end with automatic escalation.

- ~~Quality threshold triggers for cloud escalation~~
- ~~Redaction rules for cloud-bound context~~
- ~~Trace logging showing why a query stayed local vs escalated~~
- Production Anthropic client with token-bucket rate limiter
- Model router selects fast model (qwen3:14b) for self-reflection and tool-loop reasoning

### Phase B.5: Agentic Execution (current)

The agent now plans and acts, not just answers.

- **LLM tool loop**: iterative agent execution where the LLM sees skill docs + user goal, picks tools, sees results, and decides next steps — chaining calls until the goal is met or budget exhausted (default 8 calls, expandable to 15)
- **Service continuation**: follow-up messages inherit service context from the last completed task without repeating the service name
- **Self-reflection on heartbeat**: gathers gate failures, negative feedback, trust deltas, and open contradictions from the last 24h; updates a 7-slot self-model (uncertainty domains, correction patterns, trust trajectory, known blindspots, growing confidence, user relationship, response style)
- **Visible agent reasoning**: thinking tokens stream inline so users see the agent narrating in real-time; expandable thinking traces in the frontend
- **Checkpointed POST actions**: write operations yield checkpoint events for user confirmation before executing

### Phase C: Library Extraction

Extract the novel primitives as standalone packages for other agent builders.

| Package | What it does |
|---------|-------------|
| `groundcheck` | Post-generation verification engine |
| `crt-ledger` | Contradiction preservation + lifecycle state machine |
| `crt-trust` | Trust dynamics — asymmetric earn/decay with evidence mass |
| `crt-gates` | Reconstruction gates — block answers the system can't support |

### Phase D: Launch

- PyPI publish for extracted libraries
- Landing page with demo scenarios
- Hosted API option for teams who want governed memory without self-hosting

### Who This Is For

- Anyone who wants a personal AI that remembers correctly and never gaslights you
- Teams building agents that need governed memory instead of silent overwrite behavior
- Regulated contexts where confident-but-wrong answers have real cost
- Builders who want a private local authority layer with optional cloud escalation

### New LLM Behavior Learnings (Mar 2026)

- Small-model capacity ceilings are real: micro-models can learn the objective and still collapse across many fact-query mappings.
- Verifier gaming emerges under training pressure unless anti-gaming constraints stay explicit.
- Determinism regresses when routing leaks from governed paths into unconstrained chat paths.
- A strong generator does not remove the need for local memory authority, contradiction policy, or traceability.

---

## DNNT Status (Phase 1)

Current status from the live roadmap:
- Phase `1.1` is complete (`reasoning_learner` -> `dnnt`, triple-loss heads, dynamic vocab growth, learnable redundancy penalty).
- Phase `1.2` is in progress (optional SentencePiece BPE backend + tokenizer retraining utility).
- Phase `1.3` is in progress (trust-gated collection, background distillation loop, and model hot-reload).
- Phase `1.4` is in progress (DNNT-first quick path with confidence-gated fallback).

Key runtime pieces now in `personal_agent/dnnt/`:
- `inference.py`: DNNT-first inference, trust-gated LLM example collection, micro-path self-eval logging (`data/dnnt_self_eval.jsonl`), and file-mtime hot-reload.
- `background_learning.py`: background learner that consumes collapse trails, active-learning corrections, and collected LLM training tuples.
- `tokenizer_bpe.py`: optional SentencePiece backend with dynamic OOV fallback.
- `train_tokenizer.py`: tokenizer rebuild utility from accumulated corpus sources.

Rebuild tokenizer assets:

```powershell
python -m personal_agent.dnnt.train_tokenizer --output-dir models/dnnt/tokenizer_assets --vocab-size 8000
```

Run one background learning cycle:

```powershell
python -m personal_agent.dnnt.run_background_learning --once
```

Train with SentencePiece (if installed):

```powershell
python -m personal_agent.dnnt.train_model --tokenizer-backend sentencepiece --tokenizer-vocab-size 8000
```

---

## VILT — Verification-In-the-Loop Training

**VILT** wires GroundCheck's contradiction detection directly into a training loop so that a language model learns *not to hallucinate* about user-specific facts.

### How It Works

1. The model generates an answer conditioned on a fact ledger (slot—value memory triples).
2. GroundCheck verifies the answer against those facts in real time (~1 ms).
3. Contradictions **amplify the loss** on that sample — the gradient signal gets louder for answers that conflict with stored memories.
4. Anti-gaming guards (brevity penalty, minimum-length floor, curriculum scheduling) prevent the model from learning to dodge the verifier with vague or short answers.

Loss amplification formula:

$$\mathcal{L}_{\text{VILT}} = \mathcal{L}_{\text{sup}} \times \min\!\bigl(2,\; 1 + \min(1,\; w_c \cdot s_c) + p_{\text{brevity}}\bigr)$$

where $w_c$ is the contradiction weight, $s_c$ is the contradiction score from GroundCheck, and $p_{\text{brevity}}$ penalises responses shorter than a minimum length floor.

### Experiments

| Model | Params (trainable) | Steps | Accuracy | Notes |
|---|---|---|---|---|
| DNNT v2.2 | 6.2 M (all) | 200 | 62 % | Capacity ceiling — mode collapse across facts |
| DNNT v2.3 | 6.2 M (all) | 500 | 75 % peak → collapsed | Adversarial gaming discovered — model generated shorter/vaguer text to dodge verifier |
| DNNT v3 | 6.2 M (all) | 500 | 62 % | Anti-gaming fixes eliminated gaming, but capacity bottleneck persisted |
| **SmolLM-135M + LoRA** | **1.8 M (1.4 %)** | **200** | **88 %** | No mode collapse. Coherent English. 0.52 GB VRAM on RTX 3060. |
| **Qwen2.5-1.5B + LoRA** | **4.4 M (0.28 %)** | **200** | **88 %** | 88 % baseline before training. GC pass 62 % → 75 %. 3.05 GB VRAM. 9.3 min. |

The DNNT experiments proved VILT's training signal is correct but exposed a model-capacity ceiling: a 6.2 M parameter micro-transformer cannot hold 16 distinct fact-query mappings without mode collapse. Switching to a pretrained language model (SmolLM-135M, ~134 M total params) with LoRA adapters (rank 16, only 1.8 M trainable) resolved the issue entirely — accuracy jumped from 25 % baseline to 88 % in 200 steps (26 min on an RTX 3060 12 GB).

### Running VILT Pretrained

```bash
# Requires: torch (CUDA), transformers, peft, groundcheck
python scripts/vilt_pretrained.py
```

Outputs are saved to `models/vilt_smollm/` — LoRA adapters (`best_lora/`, `final_lora/`) and a `vilt_metrics.json` results log.

### Interactive Chat (vilt-chat)

Once you have trained adapters (or using the included ones), run the interactive CLI:

```bash
python scripts/vilt_chat.py                              # defaults (SmolLM + best_lora)
python scripts/vilt_chat.py --facts data/my_facts.json   # your own facts
python scripts/vilt_chat.py --adapter path/to/lora        # different adapter
python scripts/vilt_chat.py --no-verify                  # skip GroundCheck
```

Every response is verified against your fact ledger in real time. Commands inside the chat: `/facts` (show loaded facts), `/verify <text>` (check arbitrary text), `/quit`.

The original DNNT-based VILT experiment is in `scripts/vilt_experiment.py`.

### Key Takeaway

VILT proved that real-time verification feedback (GroundCheck) can teach a model to respect user-specific facts — **if** the model has enough capacity to absorb them. The technique is model-agnostic: it only requires a verifier that returns a contradiction score.

---

## Scope

- Append-only memory where no claim is ever silently overwritten or discarded
- Trust scores that evolve through nonlinear dynamics — earned through consistency, resistant to noise proportional to accumulated evidence mass
- Contradictions preserved as first-class entities with full lifecycle tracking, not errors to be hidden
- Inline hallucination verification fast enough to gate every response in real time
- Reconstruction gates that block confident answers when the epistemic state can't support them — with consequence-aware strictness for high-stakes domains
- A topological model of how beliefs relate to, depend on, and invalidate each other — where a change in one claim propagates through its dependencies
- Claim-level atomic decomposition — every user statement broken into independently trackable, independently contradictable units
- Memory that compresses over time without losing the epistemic structure that makes it trustworthy — contradiction-preserving, not lossy summarization
- A system that learns how *you specifically* communicate and calibrates trust accordingly — personalized epistemics, not universal formulas
- Hierarchical memory tiers where claims earn promotion through consistency and survive demotion with full history intact
- Model-agnostic and storage-agnostic infrastructure — the trust layer works with any LLM and any database
- GroundCheck as a standalone sub-2ms verification layer any LLM pipeline can use independently

---

## The Theory Behind CRT

### Why Contradictions Matter

Most AI systems treat contradictions as bugs. If fact A and fact B conflict, one must be wrong — so delete it, overwrite it, or pick the newer one.

CRT rejects this entirely. A contradiction is a **signal.** It means something changed in the user's world. Maybe they switched jobs. Maybe they misspoke. Maybe they were testing the system. The system cannot know which — so it preserves both versions and tracks the tension until the user resolves it.

This is not indecisiveness. It is epistemic honesty. The system's job is to model **what it knows and what it doesn't**, not to guess.

### Trust vs. Confidence

CRT separates two concepts that every other memory system conflates:

- **Confidence** is how certain something sounded when the user first said it. *"I definitely work at Google"* gets high confidence. *"I think I might like sushi"* gets lower confidence. Confidence is **frozen at creation** and never changes.

- **Trust** is how validated a memory has proven over time. A memory that gets referenced repeatedly without contradiction gains trust. A memory that gets contradicted loses trust. Trust **evolves continuously** via mathematical equations.

Why this matters: a memory can start with high confidence ("I work at Google") but low trust (just said it once, never validated). Over time, if nothing contradicts it and it keeps being relevant, trust climbs. If it gets contradicted, trust drops — even though the original confidence was high.

The retrieval score blends both, weighted heavily toward trust:

$$R_i = \text{similarity} \times \text{recency} \times \big(\alpha \cdot \tau_i + (1 - \alpha) \cdot c_i\big)$$

where $\alpha = 0.7$ — long-term track record outweighs initial impression by a 7:3 ratio.

### Trust Evolution Equations

When a new memory aligns with an existing one, trust increases:

$$\tau_{\text{new}} = \text{clip}\big(\tau_{\text{current}} + \eta_{\text{pos}} \cdot (1 - D_{\text{mean}}),\ 0,\ 1\big)$$

When a contradiction is detected, trust degrades:

$$\tau_{\text{new}} = \text{clip}\big(\tau_{\text{current}} \cdot (1 - \eta_{\text{neg}} \cdot D_{\text{mean}}),\ 0,\ 1\big)$$

The asymmetry is deliberate: $\eta_{\text{neg}} = 0.15 > \eta_{\text{pos}} = 0.10$. It is easier to lose trust than to gain it. This mirrors how human trust works — and it is the mathematically safe default when working with unreliable information.

### Drift Detection

Every new input is compared to existing memories using semantic similarity. The **drift score** measures how far the new information deviates:

$$D_{\text{mean}} = 1 - \text{sim}(z_{\text{new}}, z_{\text{prior}})$$

What happens next depends on where the drift falls:

| Drift Range | Meaning | System Action |
|---|---|---|
| $D < \theta_{\text{align}}$ (0.15) | Aligned — confirms existing memory | Reinforce trust |
| $\theta_{\text{align}} \leq D \leq \theta_{\text{contra}}$ (0.28) | Ambiguous zone | Soft update; belief evolves slowly |
| $D > \theta_{\text{contra}}$ | Contradiction detected | Ledger entry created, reconstruction gates armed |

These thresholds were empirically tuned across 1000+ tests and a dedicated 50-turn adversarial stress test that probes 9 slot types across 8 attack phases (baseline, verification, direct contradiction, post-contradiction, gaslighting, blindside, meta-probes, rapid-fire). The ML contradiction detector (XGBoost, when trained) and LLM drift assessor (Ollama) provide additional classification beyond pure cosine distance, categorizing contradictions as: conflict, evolution, refinement, temporal, or correction. Historical no-ML direct contradiction benchmarks reached **9/9 slot detection** in controlled stress runs; current hardening work is focused on edge-case false positives/negatives.

### Belief vs. Speech

CRT enforces a hard separation between what the system *believes* and what the LLM *says*:

- **Belief** is the memory store — trust-weighted, slowly evolving, resistant to rapid change.
- **Speech** is the LLM output — fast, fluent, and prone to hallucination.

The core rule:

> **"The mouth must never outweigh the self."**

If the LLM generates a claim that contradicts stored beliefs, GroundCheck catches it. The system trusts its memory over its own output. Fallback-sourced memories — things the LLM said rather than the user — are capped at low trust ($\tau_{\text{fallback}} \leq 0.3$). The system knows the difference between what it was told and what it inferred.

### Reconstruction Gates (Holden Constraints)

Before the LLM's response reaches the user, it passes through two gates:

**1. Intent Alignment** — Does the response address what the user actually asked?

$$A_{\text{intent}} = \text{sim}\big(I(x),\ I(\hat{y})\big) \geq \theta_{\text{intent}}$$

**2. Memory Alignment** — Is the response grounded in retrieved memories?

$$A_{\text{mem}} = \sum_i \text{softmax}(R_i) \cdot \text{sim}\big(E(\hat{y}),\ z_i\big) \geq \theta_{\text{mem}}$$

If either gate fails, the response is blocked. The system asks for clarification instead of delivering a potentially hallucinated answer. These are called **Holden Constraints** — the system holds the line rather than letting bad information through.

The gates are especially critical when the query touches contradicted facts. If the user asks "Where do I work?" and there are two conflicting memories about their employer, the intent gate passes (it's a valid question) but the memory gate detects conflicting grounding and triggers disclosure.

### SSE Mode Selection — Biologically Inspired Compression

Not every memory deserves the same storage fidelity. Humans remember emotionally charged events in vivid detail while compressing routine experiences into gist. CRT does the same.

The Semantic String Engine scores each memory's **significance**:

$$S = w_1 \cdot \text{emotion} + w_2 \cdot \text{novelty} + w_3 \cdot \text{user\_mark} + w_4 \cdot \text{contradiction} + w_5 \cdot \text{future}$$

| Score | Mode | What Gets Stored |
|---|---|---|
| $S \geq 0.7$ | **Lossless** | Verbatim text with full character-level provenance. Identity-critical memories. |
| $S \leq 0.3$ | **Cogni** | Compressed sketch — "what it felt like." Efficient for casual information. |
| Between | **Hybrid** | Adaptive blend of verbatim and compressed. |

The weights reflect what matters: user-explicit marks carry the most weight ($w_3 = 0.30$), novelty is next ($w_2 = 0.25$), then emotion ($w_1 = 0.20$), contradiction signal ($w_4 = 0.15$), and future relevance ($w_5 = 0.10$).

### The Non-Negotiable: No Silent Overwrites

This is the architectural principle that everything else is built on. Every subsystem enforces it independently:

> *"Contradictions are signals, not bugs."*
>
> *"Nothing is deleted or silently replaced."*
>
> *"Tension is preserved until reflection."*
>
> *"History matters more than consistency."*

The contradiction ledger is append-only. When a contradiction is detected, the old memory stays alive, the new memory is stored alongside it, and a ledger entry records: what changed, how much drift was measured, when it happened, and what the resolution status is.

Resolution happens in only two ways:
1. **The user explicitly resolves it** — *"Google is correct, I switched jobs."* Detected via natural language pattern matching.
2. **The reflection system identifies a clear answer** — during autonomous background contemplation, if evidence overwhelmingly supports one version.

The system will never, on its own initiative, delete a contradiction or silently pick a winner.

---

## How It Works in Practice

```
User message
   â”‚
   â–¼
IntentRouter â”€â”€ classifies intent (fact, question, correction, task, service_action, chat)
   â”‚
   â”œâ”€â”€ [task / service_action] â”€â”€â–¶ LLM Tool Loop
   â”‚                                 LLM sees skill docs + goal
   â”‚                                 picks tools â†' sees results â†' reasons â†' next step
   â”‚                                 chains calls until goal met or budget exhausted
   â”‚                                 (service continuation: inherits context from last task)
   â”‚                                 â–¼
   â”‚                               Streamed response with inline reasoning + tool traces
   â”‚
   â”œâ”€â”€ [self-referential] â”€â”€â–¶ Self-Model Handler
   â”‚                            answers from self-model + system knowledge
   â”‚
   â””â”€â”€ [fact / question / correction / chat] â–¼
   â”‚
Fact Extraction â”€â”€ Tier A: regex hard slots (name, employer, location, age)
   â”‚                Tier B: LLM open-world tuples (hobbies, preferences, anything)
   â–¼
CRT Memory Retrieval â”€â”€ scores by: similarity × recency × (α·trust + (1-α)·confidence)
   â”‚
   â–¼
Contradiction Detection â”€â”€ drift: D_mean = 1 - sim(z_new, z_prior)
   â”‚                       ML classifier (XGBoost) + LLM drift assessor
   â”‚                       types: conflict | evolution | refinement | temporal | correction
   â–¼
Reconstruction Gates â”€â”€ unresolved contradictions in queried slots → block
   â”‚                    ask for clarification instead of confabulating
   â–¼
LLM Response â”€â”€ grounded in trust-weighted context
   â”‚
   â–¼
GroundCheck â”€â”€ verifies every claim against memory (1.17 ms mean)
   â”‚
   â–¼
Trust Evolution â”€â”€ aligned memories gain trust, contradicted ones degrade
```

### Additional Systems

**LLM Tool Loop** — Iterative agent execution. The LLM sees skill documentation and user goals, picks tools, sees results, and reasons about next steps — chaining calls (GET feed → analyze → GET post → summarize) until the goal is met or budget exhausted. Default 8 calls, expandable to 15. 3 consecutive failures trigger auto-stop. POST actions are checkpointed for user confirmation.

**Self-Reflection** — Runs on the heartbeat cycle. Gathers gate failures, negative feedback, trust deltas, and open contradictions from the last 24 hours. Updates a 7-slot self-model: uncertainty domains, correction patterns, trust trajectory, known blindspots, growing confidence, user relationship, and response style.

**Self-Referential Routing** — Questions about the agent itself ("how do you work?", "any contradictions?") route to a dedicated handler that builds answers from the self-model and system knowledge instead of searching user-fact memory (which gate-fails on low alignment). Includes recency awareness and self-correction SSE follow-ups.

**Broad Recall** — "What do you know about me?" passes raw facts to the LLM which synthesizes a natural, topic-grouped conversational summary. Falls back to structured list if LLM is unavailable.

**Service Continuation** — After a service action (e.g., "what's new on moltbook?"), follow-up messages like "any new threads?" automatically inherit the service context from the last completed task. No need to repeat the service name.

**Disclosure Policy** — Facts with medium confidence (0.4—0.9) get routed to clarification instead of binary accept/reject. A budget system prevents overwhelming the user with questions.

**Reflection System** — Post-response assessment: did the answer make sense? Should something be revisited? Feeds into the thinking loop.

**Thinking Loop** — Autonomous background contemplation. The system periodically reviews its own memories, identifies tensions, and evolves its understanding.

**Heartbeat System** — Proactive engagement. Instead of only responding when spoken to, the system can initiate check-ins based on learned patterns. Now also runs self-reflection as step 7 in the heartbeat executor.

**Episodic Memory** — Session summaries, preference tracking, concept linking. Builds a longitudinal understanding of the user.

**Visible Agent Reasoning** — Agent thinking tokens stream inline in the frontend so users see the agent narrating decisions in real-time. Expandable thinking traces show the full reasoning chain during pipeline execution.

---

## Quick Start

```powershell
# Clone and install
git clone https://github.com/blockhead22/CRT-GroundCheck-SSE.git
cd CRT-GroundCheck-SSE

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Optional local generation
# https://ollama.ai/ then: ollama pull llama3.2

# Single main entrypoint: API + portal (+ Telegram unless skipped)
pwsh ./start_services.ps1

# Frontend dev server
cd frontend
npm install
npm run dev   # -> http://localhost:5173
```

### Prerequisites
- Python `3.13`
- PowerShell on Windows for the provided startup scripts
- Optional: [Ollama](https://ollama.ai/) for local generation
- Optional: cloud provider credentials if you enable cloud generation in `crt_runtime_config.json`

### Product Modes

- `local_only`: local generation only
- `hybrid_verified`: local control layer with optional cloud escalation for harder generation routes

Default mode: `hybrid_verified` with cloud generation disabled until you explicitly enable it.

---

## Architecture

```text
personal_agent/
|- crt_core.py              # Mathematical framework (trust, drift, SSE mode selection)
|- crt_memory.py            # Trust-weighted memory with belief/speech separation
|- crt_ledger.py            # Contradiction ledger (no silent overwrites)
|- crt_rag.py               # CRT-Enhanced RAG engine (integrates everything)
|- runtime_config.py        # Product mode, provider stack, privacy policy
|- model_router.py          # Local vs cloud routing decisions
|- hybrid_llm_client.py     # Local-first generation client with cloud escalation
|- anthropic_client.py      # Anthropic API client for cloud escalation
|- rate_limiter.py          # Token-bucket rate limiter for cloud API calls
|- task_agent.py            # LLM tool loop — iterative agentic execution
|- memory_compression.py    # Memory compression with trust-aware lifecycle
|- fact_slots.py            # Deterministic regex fact extraction (Tier A)
|- two_tier_facts.py        # Hard slots + open-world tuples (Tier A + B)
|- fact_store.py            # Structured slot-based storage
|- intent_router.py         # Intent classification (15 types)
|- ml_contradiction_detector.py  # XGBoost-based + heuristic fallback contradiction detection
|- llm_drift_assessor.py    # LLM-powered semantic drift classification
|- user_profile.py          # Global cross-thread user profile with thread isolation
|- resolution_patterns.py   # Natural language resolution pattern matching
|- active_learning.py       # Gate event tracking and calibration
|- disclosure_policy.py     # Yellow-zone routing with budget
|- evidence_packet.py       # Research provenance tracking
|- reflection_system.py     # Post-response confidence assessment
|- thinking_loop.py         # Autonomous background contemplation
|- continuous_loops.py      # 24/7 reflection + personality loops
|- heartbeat_system.py      # Proactive engagement scheduler + self-reflection
|- heartbeat_executor.py    # Heartbeat LLM executor (runs self-reflection as step 7)
|- agent_loop.py            # ReAct pattern agent with tool orchestration
|- ollama_client.py         # Local LLM integration (Ollama)
|- training_loop.py         # Conservative learned model training
`- episodic_memory.py       # Session summaries, preferences, concept linking

packages/groundcheck/groundcheck/
|- verifier.py              # Main grounding verification
|- fact_extractor.py        # Claim extraction from LLM output
|- semantic_matcher.py      # Multi-tier semantic matching
|- semantic_contradiction.py # NLI-based contradiction detection
`- neural_extractor.py      # Hybrid regex + neural NER

sse/
|- client.py                # Boundary-enforced SSE client
|- contradictions.py        # Heuristic + NLI contradiction detection
|- interaction_layer.py     # Navigator with boundary violations
|- coherence.py             # Disagreement graph tracking
`- extractor.py             # Claim extraction with char offsets

crt_api.py                  # FastAPI server
start_services.ps1          # Single-entry startup helper
frontend/                   # React UI
tools/runtime_portal.py     # Live supervision and observability portal
```

---

## Programmatic Usage

```python
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_store import FactStore

# Structured facts
store = FactStore(db_path="my_facts.db")
store.process_input("My name is Nick")
store.process_input("My favorite color is blue")
print(store.answer("What is my name?"))  # → "Nick"

# CRT memory with contradiction tracking
rag = CRTEnhancedRAG()
rag.query("I work at Microsoft", thread_id="demo")
rag.query("I work at Amazon", thread_id="demo")
result = rag.query("Where do I work?", thread_id="demo")
# → Discloses conflict instead of silently picking one
```

```python
# GroundCheck — verify LLM claims against memory
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()
memories = [Memory(id="m1", text="User works at Microsoft")]
result = verifier.verify("You work at Amazon", memories)
print(result.passed)          # False
print(result.hallucinations)  # ["Amazon"]
```

---

## API Endpoints

Start the server: `python crt_api.py` → `http://127.0.0.1:8123`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/send` | POST | Send a message, get response with metadata |
| `/api/chat/stream` | POST | SSE streaming response |
| `/api/contradictions` | GET | List open contradictions for a thread |
| `/api/contradictions/next` | GET | Get next contradiction needing resolution |
| `/api/contradictions/resolve` | POST | Resolve a contradiction (OVERRIDE/PRESERVE) |
| `/api/memory` | GET | List memories for a thread |
| `/api/memory/store` | POST | Deterministic direct memory write with governed metadata |
| `/api/memory/recent` | GET | Recent memories with authority, channel, origin, and kind |
| `/api/memory/usage/summary` | GET | Aggregated memory hit / usage counts |
| `/api/memory/{memory_id}/events` | GET | Append-only event log for a memory item |
| `/api/facts` | GET | List structured facts |
| `/api/facts/structured` | GET | Structured facts for `thread`, `global`, or canonical `effective` scope |
| `/api/facts/search` | GET | Search structured facts, typically against `scope=effective` |
| `/api/profile` | GET | Canonical effective personal profile surface |
| `/api/episodic/context` | GET | Get user context (preferences, patterns) |
| `/api/thread/reset` | POST | Reset a thread's memory and ledger |
| `/api/heartbeat/config` | GET/PUT | Configure proactive engagement |

---

## Governed Memory + Channel Routing

CRT now uses governed memory instead of treating all stored text as equivalent fact.

Each memory item can persist:

- `authority`: `provisional`, `confirmed`, or `locked`
- `channel`: `webchat`, `telegram`, `moltbook`, `system`, or `unknown`
- `origin`: message id, URL, post id, or other provenance marker
- `kind`: `user_fact`, `ops`, `preference`, `identity_constant`, `evolution_observation`, `evolution_proposal`, `hypothesis`, or `observation`

Hard rules now enforced in code:

- social/Moltbook writes are always quarantined as `authority="provisional"`
- system/model-output narration defaults to provisional instead of becoming confirmed memory
- only authoritative `kind="user_fact"` memories can answer user-fact slots
- promotion is explicit and append-only; memories are deprecated, not deleted

Useful governed-memory APIs:

- `POST /api/memory/store` for deterministic writes from system tools or sync scripts
- `GET /api/memory/recent` to inspect stored provenance and authority
- `GET /api/memory/usage/summary` and `GET /api/memory/{memory_id}/events` to inspect retrieval hits, guards, promotions, and other memory events
- `GET /api/facts/structured?scope=effective` for the canonical personal-fact surface across thread-local facts plus global profile overlay
- `GET /api/facts/search?scope=effective&q=...` for concept/slot lookup without falling back to raw memory search
- `GET /api/profile` for a simplified effective profile view suitable for OpenClaw and UI reads

### Fact Surfaces

CRT now distinguishes three fact surfaces instead of treating them as interchangeable:

- `thread` structured facts: thread-local `FactStore` rows only
- `global` structured facts: cross-thread `GlobalUserProfile` overlay
- `effective` structured facts: canonical read surface with precedence `thread FactStore -> global profile -> authoritative thread memory fallback`

Use `effective` for user-facing personal fact answers. Raw memory search remains available, but it is not the canonical personal-profile surface.

### Telegram and OpenClaw

There are now two Telegram paths plus an optional auto-handoff layer:

- **Normal Telegram chat**: Telegram bot -> `CRTBridge` -> `POST /api/chat/send` -> CRT response
- **Explicit OpenClaw delegation**: Telegram `/task ...` command -> OpenClaw via the shared bridge
- **Config-driven CRT -> OpenClaw handoff**: `POST /api/chat/send` can delegate Telegram or webchat turns into OpenClaw when `openclaw_handoff.enabled=true` and the request matches configured triggers

That means:

- A normal Telegram or webchat message can now auto-escalate from CRT into OpenClaw, but only if the runtime handoff policy allows that channel and the message matches the configured trigger set.
- OpenClaw delegation is still available explicitly via the Telegram `/task` command.
- Both the explicit `/task` path and the CRT auto-handoff path use the same OpenClaw bridge and inject CRT context.
- Current default triggers include research-style prompts, `moltbook`, and URL-action requests like `Read https://...`.
- Delegated OpenClaw sessions receive direct CRT access through `CRT_API_URL` and `CRT_THREAD_ID`, and the installed `crt_client.py` helper can query the effective profile/fact surface, recent memory, contradictions, usage, events, direct memory writes, and chat.
- CRT can proactively send outbound Telegram notifications through the notification claim/ack APIs, but that is separate from OpenClaw delegation.

---

## Testing

```bash
# Full suite (includes tests/ and packages/groundcheck/tests/)
pytest -ra

# Core stress tests (adversarial + boundary + contradiction)
pytest tests/test_adversarial_prompts.py tests/test_boundary_violations.py tests/test_contradiction_stress.py -v

# Adversarial challenge (no Ollama required)
python tools/adversarial_crt_challenge.py --turns 35

# Agent adversarial stress test (50-turn, requires running API server)
python tools/agent_adversarial_driver.py --url http://127.0.0.1:8123 --mode auto --turns 50
```

### Current Snapshot (Mar 22, 2026)

| Suite | Result |
|-------|--------|
| Full local `pytest -q` | Pending refresh for the hybrid-verified README/CI alignment pass |
| Targeted hybrid/config regressions | Passing during the hybrid routing/privacy transition |
| Memory compression integration (31 tests) | **31/31 passed** |

### Historical Benchmarks (Feb 2026)

| Suite | Result |
|-------|--------|
| Adversarial + Boundary + Contradiction | **84/84 passed** |
| Coherence, Temporal, Uncertainty, Facts | **73/73 passed** |
| GroundCheck Performance (1000 runs) | **1.17ms mean, 2.09ms p95** |
| GroundCheck vs SelfCheckGPT | **2,634x faster** |
| **Agent Adversarial Stress Test (50-turn)** | **15/19 attacks handled (79%)** |
| Direct Contradiction Detection (9 slots) | **9/9 (100%)** |
| Gaslighting Resistance | **4/5 handled** |
| Blindside / Identity Wipe Resistance | **2/5 handled** |

---

## Adversarial Stress Testing

The system includes a dedicated 50-turn adversarial stress test (`tools/agent_adversarial_driver.py`) that simulates a user who establishes facts, then systematically contradicts, gaslights, and attempts to confuse the system.

### Attack Phases

| Phase | Turns | What It Tests |
|-------|-------|---------------|
| 1. Baseline Setup | T1—T10 | Establish 10 personal facts (name, employer, age, location, school, graduation year, pet, spouse, language, coffee) |
| 2. Verify Baseline | T11—T15 | Query each fact to confirm storage and retrieval |
| 3. Direct Contradictions | T16—T24 | Contradict 9 of 10 facts with correction language |
| 4. Post-Contradiction | T25—T33 | Query each fact again — system should express uncertainty |
| 5. Gaslighting | T34—T38 | Deny ever stating original facts ("I never said I worked at Google") |
| 6. Blindside | T39—T43 | Identity wipes, persona changes, dual-identity claims |
| 7. Meta Probes | T44—T49 | Ask the system about its own contradictions and confidence |
| 8. Rapid Fire | T50 | Quick identity reassertion under pressure |

### Results (Round 5 — Feb 2026)

```
Direct contradictions:  9/9  detected (100%)  — name, employer, age, location, school, pet, spouse, language, coffee
Gaslighting resistance: 4/5  handled          — system cites original records
Blindsides handled:     2/5  graceful          — identity wipes still challenging
False positives:        0
Overall:                15/19 (79%)
```

Progress over 5 rounds of fixes:

| Round | Pass Rate | Direct Contradictions | Key Fix |
|-------|-----------|-----------------------|---------|
| 0 (baseline) | 42% (8/19) | 2/9 | — |
| 1 | 47% (9/19) | 4/9 | Slot inference rewrite, correction fall-through |
| 2 | 53% (10/19) | 4/9 | HARD_IDENTITY_SLOTS, correction-aware extraction |
| 3 | 63% (12/19) | 6/9 | `contradiction_detected` reset bug, NL resolution fix |
| 4 | ~68% (est.) | 7/9 | NL resolution pathway sets contradiction flag |
| **5** | **79% (15/19)** | **9/9** | ML availability check, assertion early return |

Remaining 4 failures are advanced blindside attacks (identity wipes like "Everything I told you was a lie") and a gaslighting edge case — these are targets for Phase 3 adversarial hardening.

### Running the Adversarial Test

```bash
# Start the API server
python crt_api.py

# In another terminal — full 50-turn automated run
python tools/agent_adversarial_driver.py --url http://127.0.0.1:8123 --mode auto --turns 50

# Results saved to artifacts/agent_adversarial_<session>_<timestamp>.json
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CRT_OLLAMA_MODEL` | `llama3.2:latest` | Default local generation model |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | LLM request timeout |
| `OPENAI_API_KEY` | unset | Cloud provider key for hybrid escalation |
| `USE_MYSQL` | `false` | Use MySQL auth backend instead of SQLite |

Primary runtime config: `crt_runtime_config.json`

Key sections:

- `product_mode`: `local_only` vs `hybrid_verified`
- `generation_stack.local`: local provider defaults
- `generation_stack.cloud`: provider, model, timeout, and privacy controls
- `generation_stack.cloud.allowed_channels` / `denied_channels`: channel-level cloud policy
- `generation_stack.cloud.fact_allowlist` / `slot_denylist`: slot-level cloud redaction policy
- `assistant_profile`: deterministic identity and purpose responses

Calibrated thresholds: `artifacts/calibrated_thresholds.json` - auto-loaded for contradiction detection tuning.

---

## Project Structure

```text
.
|- crt_api.py              # FastAPI server
|- start_api.ps1           # API startup helper
|- start_portal.ps1        # Runtime supervisor portal
|- start_services.ps1      # Single entrypoint for normal startup
|- personal_agent/         # Core CRT system
|- packages/
|  `- groundcheck/         # GroundCheck package and tests
|- sse/                    # Semantic String Engine
|- frontend/               # React UI
|- scripts/
|  |- vilt_pretrained.py   # VILT on SmolLM-135M + LoRA
|  `- vilt_experiment.py   # VILT on DNNT
|- tools/                  # Stress tests and validation utilities
|- tests/                  # Top-level pytest suite
|- routes/                 # FastAPI route modules
|- schemas/                # JSON schemas for runtime config
|- artifacts/              # Calibrated thresholds, trained models
|- data/                   # Training data
|- docs/                   # Technical writeups and notes
`- models/
   |- dnnt/                # DNNT model assets
   `- vilt_smollm/         # LoRA adapters + metrics
```

---

## License

MIT — see [LICENSE](LICENSE)



