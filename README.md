# CRT + GroundCheck + SSE

**Contradiction-preserving memory for AI agents. No silent overwrites.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 577 passed](https://img.shields.io/badge/tests-577%20passed-brightgreen.svg)](#test-results)

---

## The Problem

Every large language model today has the same blind spot: **it treats memory as disposable.**

Tell ChatGPT a fact. Contradict that fact three messages later. The model silently adopts the new version. The old fact vanishes with no trace, no acknowledgment that something changed, no question about which version is true.

This is not a bug in any one product. It is a structural property of how LLMs work. Transformers process token sequences. They have no persistent identity, no evolving model of the user, no mechanism to detect that what the user said on Tuesday conflicts with what they said on Thursday. Context windows give the illusion of memory, but they are finite, stateless, and disposable.

As long as that is true, an AI cannot be a genuine personal assistant. A system that silently replaces what it knew yesterday cannot build trust. And without trust, there is no relationship.

**CRT exists to fix that.**

---

## What This Is

CRT-GroundCheck-SSE is a **mathematical framework for AI memory** that treats contradictions as first-class data instead of errors to be hidden. It wraps any local LLM (via Ollama) in three interlocking systems:

| System | Role |
|--------|------|
| **CRT** (Cognitive-Reflective Transformer) | A mathematical trust and drift framework. Every memory carries a trust score that evolves over time through equations — rising when validated, falling when contradicted. Reconstruction gates block the LLM from answering confidently when unresolved conflicts exist. |
| **GroundCheck** | A hallucination verification layer. Every word the LLM produces is checked against stored memories in real time. Mean latency: **1.17 ms** — 2,634× faster than SelfCheckGPT. |
| **SSE** (Semantic String Engine) | Claim extraction with character-level provenance. It is architecturally impossible for SSE to delete, merge, or silently resolve a contradiction. The boundary is enforced at the code level, not by policy. |

If you tell the system *"I work at Microsoft"* and later say *"I work at Google"*, both facts survive. A contradiction ledger records the tension. When you later ask *"Where do I work?"*, reconstruction gates detect the unresolved conflict and **surface the contradiction for you to decide** — instead of confidently giving the wrong answer.

---

## Scope

- Append-only memory where no claim is ever silently overwritten or discarded
- Trust scores that evolve mathematically — earned through consistency, degraded by contradiction, resistant to noise proportional to evidence history
- Contradictions preserved as first-class entities with full lifecycle tracking, not errors to be hidden
- Inline hallucination verification fast enough to gate every response in real time
- Reconstruction gates that block confident answers when the epistemic state can't support them
- The beginning of a topological model of how beliefs relate to, depend on, and invalidate each other
- Memory that compresses over time without losing the structure that makes it trustworthy
- A system that learns how *you specifically* communicate — and calibrates accordingly
- Infrastructure moving toward model-agnostic and storage-agnostic, so the trust layer isn't coupled to any single LLM or database
- GroundCheck architected to stand on its own — a sub-2ms verification layer any LLM pipeline could use

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

These thresholds were empirically tuned across 577+ adversarial stress tests, including deliberate attempts to trick the system into silent overwrites. The ML contradiction detector (XGBoost) and LLM drift assessor (Ollama) provide additional classification beyond pure cosine distance, categorizing contradictions as: conflict, evolution, refinement, temporal, or correction.

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
   │
   ▼
IntentRouter ── classifies intent (fact, question, correction, task, chat)
   │
   ▼
Fact Extraction ── Tier A: regex hard slots (name, employer, location, age)
   │                Tier B: LLM open-world tuples (hobbies, preferences, anything)
   ▼
CRT Memory Retrieval ── scores by: similarity × recency × (α·trust + (1-α)·confidence)
   │
   ▼
Contradiction Detection ── drift: D_mean = 1 - sim(z_new, z_prior)
   │                       ML classifier (XGBoost) + LLM drift assessor
   │                       types: conflict | evolution | refinement | temporal | correction
   ▼
Reconstruction Gates ── unresolved contradictions in queried slots → block
   │                    ask for clarification instead of confabulating
   ▼
LLM Response ── grounded in trust-weighted context
   │
   ▼
GroundCheck ── verifies every claim against memory (1.17 ms mean)
   │
   ▼
Trust Evolution ── aligned memories gain trust, contradicted ones degrade
```

### Additional Systems

**Disclosure Policy** — Facts with medium confidence (0.4–0.9) get routed to clarification instead of binary accept/reject. A budget system prevents overwhelming the user with questions.

**Reflection System** — Post-response assessment: did the answer make sense? Should something be revisited? Feeds into the thinking loop.

**Thinking Loop** — Autonomous background contemplation. The system periodically reviews its own memories, identifies tensions, and evolves its understanding.

**Heartbeat System** — Proactive engagement. Instead of only responding when spoken to, the system can initiate check-ins based on learned patterns.

**Episodic Memory** — Session summaries, preference tracking, concept linking. Builds a longitudinal understanding of the user.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/blockhead22/CRT-GroundCheck-SSE.git
cd CRT-GroundCheck-SSE
pip install -e .
pip install -e groundcheck/

# (Optional) Install Ollama for LLM features
# https://ollama.ai/ → then: ollama pull llama3.2

# Interactive demo
python Rag-Demo.py

# API server
python crt_api.py                              # → http://127.0.0.1:8123

# Frontend
cd frontend && npm install && npm run dev      # → http://localhost:5173
```

### Prerequisites
- Python 3.10+
- `pip install -r requirements.txt`
- Optional: [Ollama](https://ollama.ai/) with a local model for LLM features

---

## Architecture

```
personal_agent/
├── crt_core.py              # Mathematical framework (trust, drift, SSE mode selection)
├── crt_memory.py            # Trust-weighted memory with belief/speech separation
├── crt_ledger.py            # Contradiction ledger (no silent overwrites)
├── crt_rag.py               # CRT-Enhanced RAG engine (integrates everything)
├── fact_slots.py            # Deterministic regex fact extraction (Tier A)
├── two_tier_facts.py        # Hard slots + open-world tuples (Tier A + B)
├── fact_store.py            # Structured slot-based storage
├── intent_router.py         # Intent classification (15 types)
├── ml_contradiction_detector.py  # XGBoost-based contradiction detection
├── llm_drift_assessor.py    # LLM-powered semantic drift classification
├── resolution_patterns.py   # Natural language resolution pattern matching
├── disclosure_policy.py     # Yellow-zone routing with budget
├── evidence_packet.py       # Research provenance tracking
├── reflection_system.py     # Post-response confidence assessment
├── thinking_loop.py         # Autonomous background contemplation
├── continuous_loops.py      # 24/7 reflection + personality loops
├── heartbeat_system.py      # Proactive engagement scheduler
├── agent_loop.py            # ReAct pattern agent with tool orchestration
├── ollama_client.py         # Local LLM integration (Ollama)
├── training_loop.py         # Conservative learned model training
└── episodic_memory.py       # Session summaries, preferences, concept linking

groundcheck/groundcheck/
├── verifier.py              # Main grounding verification
├── fact_extractor.py        # Claim extraction from LLM output
├── semantic_matcher.py      # Multi-tier semantic matching
├── semantic_contradiction.py # NLI-based contradiction detection
└── neural_extractor.py      # Hybrid regex + neural NER

sse/
├── client.py                # Boundary-enforced SSE client
├── contradictions.py        # Heuristic + NLI contradiction detection
├── interaction_layer.py     # Navigator with boundary violations
├── coherence.py             # Disagreement graph tracking
└── extractor.py             # Claim extraction with char offsets

crt_api.py                   # FastAPI server (5700+ lines)
frontend/                    # React + Tailwind + Framer Motion UI
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
| `/api/facts` | GET | List structured facts |
| `/api/episodic/context` | GET | Get user context (preferences, patterns) |
| `/api/thread/reset` | POST | Reset a thread's memory and ledger |
| `/api/heartbeat/config` | GET/PUT | Configure proactive engagement |

---

## Testing

```bash
# Full suite (577 tests)
pytest

# Core stress tests (adversarial + boundary + contradiction)
pytest tests/test_adversarial_prompts.py tests/test_boundary_violations.py tests/test_contradiction_stress.py -v

# GroundCheck performance
python groundcheck/stress_test_performance.py   # 1000 verifications, <2ms p95

# Adversarial challenge (no Ollama required)
python tools/adversarial_crt_challenge.py --turns 35
```

### Test Results

| Suite | Result |
|-------|--------|
| pytest (full) | **577 passed** / 8 failed (98.6%) |
| Adversarial + Boundary + Contradiction | **84/84 passed** |
| Coherence, Temporal, Uncertainty, Facts | **73/73 passed** |
| GroundCheck Performance (1000 runs) | **1.17ms mean, 2.09ms p95** |
| GroundCheck vs SelfCheckGPT | **2,634× faster** |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CRT_OLLAMA_MODEL` | `llama3.2:latest` | Ollama model for main LLM |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | LLM request timeout |
| `USE_MYSQL` | `false` | Use MySQL auth backend instead of SQLite |

Runtime config: `crt_runtime_config.json` — assistant name, personality, feature flags.

Calibrated thresholds: `artifacts/calibrated_thresholds.json` — auto-loaded for contradiction detection tuning.

---

## Project Structure

```
.
├── crt_api.py              # FastAPI server
├── Rag-Demo.py             # Interactive CLI demo
├── personal_agent/         # Core CRT system (40+ modules)
├── groundcheck/            # Hallucination verification library
├── sse/                    # Semantic String Engine
├── belief_revision/        # Belief revision bench (policy learning)
├── frontend/               # React UI
├── tools/                  # Stress tests and validation utilities
├── tests/                  # 577+ pytest tests
├── schemas/                # JSON schemas for runtime config
├── artifacts/              # Calibrated thresholds, trained models
├── data/                   # Training data
└── models/                 # ML model artifacts
```

---

## License

MIT — see [LICENSE](LICENSE)
