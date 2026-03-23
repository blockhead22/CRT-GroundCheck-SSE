# CRT/Aether

**A truth-preserving memory governance layer for local LLMs. No silent overwrites.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LLM: qwen3:14b](https://img.shields.io/badge/LLM-qwen3%3A14b-purple.svg)](https://ollama.ai/)
[![Status: Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)](#current-status-march-2026)

---

## The Core Thesis

LLM output is vocal cords, not truth. Memory is the source of belief.

Most AI assistants with "memory" do key-value storage that silently overwrites on update. Tell it you work at Google, then later say Microsoft, and the old fact vanishes without a trace. No contradiction surfaced. No audit trail. No way to know why the answer changed.

CRT (Contradiction-aware Reconciliation and Trust) governs the gap between what the model says and what it actually knows. The generator is commodity — local or cloud, swappable. The memory governance and truth-preserving control structure around generation is the product.

Aether is the personal assistant built on CRT.

---

## The Three Laws

Every subsystem in CRT is governed by three design laws. These are not enforced by a single module — they are structural properties that emerge from how the systems interact.

**1. The mouth should never outweigh the self.**
Belief lives in memory, speech is provisional. If the LLM generates a claim that contradicts stored beliefs, the system trusts its memory over its own output. Fallback-sourced memories (things the LLM inferred rather than was told) are capped at low trust.

**2. Contradictions are preserved unless resolution is earned.**
A contradiction is a signal, not a bug. Maybe the user switched jobs. Maybe they misspoke. The system cannot know which, so it preserves both versions and tracks the tension until the user resolves it or the reflection system identifies overwhelming evidence.

**3. Structure should emerge, not be hardcoded.**
Behavior arises from memory, reflection, and compression dynamics — not if/else rules. Trust evolves through mathematical equations. Compression tiers adapt to significance scores. Routing decisions flow from confidence thresholds, not static routing tables.

---

## Architecture Overview

### The Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Frontend** | React, TypeScript, Vite |
| **Local LLM** | Ollama (qwen3:14b on consumer GPU — tested on RTX 3060) |
| **Embeddings** | all-MiniLM-L6-v2 (sentence-transformers, 384D) |
| **ML** | XGBoost (belief/policy classifiers), PyTorch (DNNT) |
| **Cloud** | OpenAI API (gpt-4o-mini), Claude via cookie session |
| **Storage** | SQLite (memory, auth, ledger, profile) |

### 3-Tier Cloud Routing

The CRT control plane stays local regardless of who generates the response.

| Tier | Provider | Role |
|------|----------|------|
| **Tier 0 (Local)** | Always runs | Regex extraction, embedding search, trust math, DNNT inference |
| **Tier 1** | OpenAI gpt-4o-mini | Slot classification, NLI contradiction check, generation fallback |
| **Tier 2** | Claude (cookie session) | Reflection validation, generation escalation for complex queries |

Cloud generation fallback: local times out, OpenAI catches it, Claude escalates if needed. Memory, contradiction checks, verification, routing policy, and traceability stay under local CRT control.

### DNNT

A 6.2M parameter micro-transformer that learns to mimic LLM reasoning. Falls back to the full LLM when confidence drops below 0.6. Runtime components in `personal_agent/dnnt/` include inference with trust-gated collection, background learning from collapse trails, and optional SentencePiece BPE tokenizer.

### Request Lifecycle

```
User message
   |
   v
IntentRouter -- classifies intent (fact, question, correction, task, service_action, chat)
   |
   +-- [task / service_action] --> LLM Tool Loop
   |                                picks tools -> sees results -> reasons -> next step
   |                                chains calls until goal met or budget exhausted (8-15 calls)
   |
   +-- [self-referential] -------> Self-Model Handler
   |                                answers from self-model + system knowledge (70+ patterns)
   |
   +-- [fact / question / correction / chat]
   |
   v
Fact Extraction -- Tier A: regex hard slots | Tier B: LLM open-world tuples
   |
   v
CRT Memory Retrieval -- scores by: similarity x recency x (0.7*trust + 0.3*confidence)
   |
   v
Contradiction Detection -- drift: D_mean = 1 - sim(z_new, z_prior)
   |                        ML classifier (XGBoost) + LLM drift assessor
   |                        types: conflict | evolution | refinement | temporal | correction
   v
Reconstruction Gates -- unresolved contradictions in queried slots -> block
   |                     ask for clarification instead of confabulating
   v
LLM Response -- grounded in trust-weighted context
   |
   v
GroundCheck -- verifies every claim against memory (~1.2ms mean, ~2ms p95)
   |
   v
Trust Evolution -- aligned memories gain trust, contradicted ones degrade
```

---

## Key Features

### Trust-Weighted Memory
Memories carry evolving trust scores with asymmetric earn/decay dynamics. Trust increases slowly through consistency, degrades faster on contradiction. Confidence (how certain it sounded) is frozen at creation; trust (how validated over time) evolves continuously. Retrieval blends both, weighted 70% toward trust.

### Contradiction Ledger
Append-only. When a contradiction is detected, both versions survive. A ledger entry records what changed, how much drift was measured, when it happened, and the resolution status. Resolution happens only when the user explicitly resolves it or the reflection system finds overwhelming evidence.

### Mid-Stream Verification
Fact-checks the model WHILE it generates, not just after. GroundCheck provides sub-2ms post-generation semantic verification. Claims that contradict stored beliefs are caught before reaching the user.

### Self-Referential Routing
Questions about the agent itself route to a dedicated handler that builds answers from the self-model and system knowledge. Covers 70+ patterns with recency awareness and grounded architectural answers.

### Heartbeat Loop
Periodic self-reflection: trust decay, memory compression, blind spot tracking, gate failure analysis, and self-model updates across 7 slots (uncertainty domains, correction patterns, trust trajectory, known blindspots, growing confidence, user relationship, response style).

### Adaptive Compression
V(t)-driven tier system. High-significance memories get lossless verbatim storage. Routine information compresses to efficient sketches. Intermediate memories get adaptive blends. Uses 10D/64D/384D embeddings depending on tier.

### ViLT (Verification-In-the-Loop Training)
Amplifies loss on contradictions weighted by trust scores. Proved that real-time verification feedback can teach a model to respect user-specific facts — if the model has enough capacity. SmolLM-135M + LoRA achieved 88% accuracy in 200 steps on an RTX 3060.

### Slot-Level Exclusivity
Exclusive slots (like `favorite_color`) are enforced at ingestion. No silent accumulation of conflicting values.

### Settings Dashboard
Frontend settings page with cloud feature toggles, usage tracking, daily limits, profile management, and known facts display.

### User-Scoped Memory
Thread-level provenance with global cross-thread profile overlay. Three fact surfaces: thread-local, global, and effective (canonical read surface with defined precedence).

---

## Quick Start

### Prerequisites

- Python 3.11+ (3.13 tested)
- Node.js 18+
- [Ollama](https://ollama.ai/) with a model pulled (e.g., `ollama pull qwen3:14b`)
- Windows PowerShell for provided startup scripts (backend runs on any OS with manual invocation)

### Install and Run

```powershell
# Clone and install
git clone <repo-url> AI_round2
cd AI_round2

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Start everything (API + portal)
pwsh ./start_services.ps1

# Or start just the API
.\start_api.ps1
# Or directly:
python crt_api.py   # -> http://127.0.0.1:8123

# Frontend (separate terminal)
cd frontend
npm install
npm run dev          # -> http://localhost:5173
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required: which Ollama model to use
CRT_OLLAMA_MODEL=qwen3:14b

# Optional: Cloud providers (leave unset for local-only mode)
# OPENAI_API_KEY=sk-...
# CLAUDE_SESSION_COOKIE=...

# Optional: Server binding
# CRT_HOST=127.0.0.1
# PORT=8123
```

### Runtime Configuration

Primary runtime config lives in `crt_runtime_config.json`:

- `product_mode`: `local_only` or `hybrid_verified`
- `generation_stack.cloud`: provider, model, timeout, privacy controls
- `generation_stack.cloud.allowed_channels` / `denied_channels`: channel-level cloud policy
- `generation_stack.cloud.slot_denylist`: slot-level cloud redaction
- `assistant_profile`: deterministic identity and purpose responses

Default mode: `hybrid_verified` with cloud generation disabled until explicitly enabled.

---

## API Endpoints

Server: `python crt_api.py` on `http://127.0.0.1:8123`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/send` | POST | Send a message, get response with full metadata |
| `/api/chat/stream` | POST | SSE streaming response |
| `/api/contradictions` | GET | List open contradictions for a thread |
| `/api/contradictions/next` | GET | Next contradiction needing resolution |
| `/api/contradictions/resolve` | POST | Resolve a contradiction (OVERRIDE/PRESERVE) |
| `/api/memory` | GET | List memories for a thread |
| `/api/memory/store` | POST | Deterministic direct memory write with governed metadata |
| `/api/memory/recent` | GET | Recent memories with authority, channel, origin, kind |
| `/api/memory/usage/summary` | GET | Aggregated memory hit/usage counts |
| `/api/memory/{id}/events` | GET | Append-only event log for a memory item |
| `/api/facts` | GET | List structured facts |
| `/api/facts/structured` | GET | Structured facts (thread, global, or effective scope) |
| `/api/facts/search` | GET | Search structured facts |
| `/api/profile` | GET | Canonical effective personal profile |
| `/api/thread/reset` | POST | Reset a thread's memory and ledger |
| `/api/heartbeat/config` | GET/PUT | Configure proactive engagement |

---

## Programmatic Usage

```python
from personal_agent.crt_rag import CRTEnhancedRAG

# CRT memory with contradiction tracking
rag = CRTEnhancedRAG()
rag.query("I work at Microsoft", thread_id="demo")
rag.query("I work at Amazon", thread_id="demo")
result = rag.query("Where do I work?", thread_id="demo")
# -> Discloses conflict instead of silently picking one
```

```python
# GroundCheck -- verify LLM claims against memory
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()
memories = [Memory(id="m1", text="User works at Microsoft")]
result = verifier.verify("You work at Amazon", memories)
print(result.passed)          # False
print(result.hallucinations)  # ["Amazon"]
```

---

## Governed Memory

Each memory item carries structured provenance:

- **authority**: `provisional`, `confirmed`, or `locked`
- **channel**: `webchat`, `telegram`, `moltbook`, `system`, or `unknown`
- **origin**: message id, URL, post id, or other provenance marker
- **kind**: `user_fact`, `ops`, `preference`, `identity_constant`, `evolution_observation`, `evolution_proposal`, `hypothesis`, or `observation`

Hard rules enforced in code:
- Social/Moltbook writes are always quarantined as `provisional`
- System/model-output narration defaults to provisional
- Only authoritative `user_fact` memories can answer user-fact slots
- Promotion is explicit and append-only; memories are deprecated, not deleted

---

## Trust Evolution

When a new memory aligns with an existing one, trust increases:

$$\tau_{\text{new}} = \text{clip}\big(\tau_{\text{current}} + \eta_{\text{pos}} \cdot (1 - D_{\text{mean}}),\ 0,\ 1\big)$$

When a contradiction is detected, trust degrades:

$$\tau_{\text{new}} = \text{clip}\big(\tau_{\text{current}} \cdot (1 - \eta_{\text{neg}} \cdot D_{\text{mean}}),\ 0,\ 1\big)$$

The asymmetry is deliberate: negative learning rate (0.15) exceeds positive (0.10). It is easier to lose trust than to gain it.

Drift detection thresholds:

| Drift Range | Meaning | Action |
|---|---|---|
| D < 0.15 | Aligned | Reinforce trust |
| 0.15 - 0.28 | Ambiguous | Soft update, belief evolves slowly |
| D > 0.28 | Contradiction | Ledger entry created, reconstruction gates armed |

---

## Testing

```bash
# Full suite
pytest -ra

# Core stress tests
pytest tests/test_adversarial_prompts.py tests/test_boundary_violations.py tests/test_contradiction_stress.py -v

# 50-turn adversarial stress test (requires running API server)
python tools/agent_adversarial_driver.py --url http://127.0.0.1:8123 --mode auto --turns 50
```

### Historical Benchmarks (Feb 2026)

| Suite | Result |
|-------|--------|
| Adversarial + Boundary + Contradiction | 84/84 passed |
| Coherence, Temporal, Uncertainty, Facts | 73/73 passed |
| GroundCheck Performance (1000 runs) | 1.17ms mean, 2.09ms p95 |
| GroundCheck vs SelfCheckGPT | 2,634x faster |
| Agent Adversarial Stress Test (50-turn) | 15/19 attacks handled (79%) |
| Direct Contradiction Detection (9 slots) | 9/9 (100%) |
| Gaslighting Resistance | 4/5 handled |
| Blindside / Identity Wipe Resistance | 2/5 handled |

---

## ViLT Experiments

| Model | Trainable Params | Steps | Accuracy | Notes |
|---|---|---|---|---|
| DNNT v2.2 | 6.2M | 200 | 62% | Capacity ceiling, mode collapse |
| DNNT v3 | 6.2M | 500 | 62% | Anti-gaming fixes applied, capacity bottleneck persisted |
| SmolLM-135M + LoRA | 1.8M (1.4%) | 200 | 88% | No mode collapse. 0.52 GB VRAM. |
| Qwen2.5-1.5B + LoRA | 4.4M (0.28%) | 200 | 88% | GC pass 62% to 75%. 3.05 GB VRAM. |

```bash
# Train ViLT
python scripts/vilt_pretrained.py

# Interactive chat with verification
python scripts/vilt_chat.py
python scripts/vilt_chat.py --facts data/my_facts.json
```

---

## Project Structure

```
.
|-- crt_api.py                   # FastAPI server entry point
|-- start_services.ps1           # Single startup entrypoint (API + portal)
|-- start_api.ps1                # API-only startup
|-- crt_runtime_config.json      # Runtime configuration
|-- personal_agent/              # Core CRT engine
|   |-- crt_core.py              #   Trust math, drift, SSE mode selection
|   |-- crt_memory.py            #   Trust-weighted memory, belief/speech separation
|   |-- crt_ledger.py            #   Contradiction ledger (append-only)
|   |-- crt_rag.py               #   CRT-Enhanced RAG (integrates everything)
|   |-- model_router.py          #   Local vs cloud routing
|   |-- hybrid_llm_client.py     #   Local-first generation with cloud escalation
|   |-- anthropic_client.py      #   Anthropic API client
|   |-- task_agent.py            #   LLM tool loop (iterative agentic execution)
|   |-- memory_compression.py    #   Trust-aware compression lifecycle
|   |-- two_tier_facts.py        #   Hard slots + open-world tuples
|   |-- intent_router.py         #   Intent classification (15 types)
|   |-- ml_contradiction_detector.py  # XGBoost + heuristic fallback
|   |-- self_model.py            #   7-slot self-model for introspection
|   |-- reflection_system.py     #   Post-response confidence assessment
|   |-- thinking_loop.py         #   Autonomous background contemplation
|   |-- stream_verifier.py       #   Mid-stream verification
|   |-- trust_decay.py           #   Time-based trust decay
|   |-- user_profile.py          #   Global cross-thread user profile
|   |-- dnnt/                    #   DNNT micro-transformer
|   +-- ...
|-- routes/                      # FastAPI route handlers
|   |-- chat.py, memory.py, contradictions.py, auth.py, ...
|-- frontend/                    # React/TypeScript UI (Vite)
|-- packages/groundcheck/        # Vendored semantic verification library
|-- sse/                         # Semantic String Engine
|-- scripts/                     # ViLT training scripts
|-- tools/                       # Stress tests and validation utilities
|-- tests/                       # Pytest test suite
|-- models/                      # Trained models (DNNT, ViLT LoRA adapters)
|-- docs/                        # Technical documentation (15+ pages)
|-- schemas/                     # JSON schemas for runtime config
+-- artifacts/                   # Calibrated thresholds, trained models
```

---

## Current Status (March 2026)

### Working

- Memory governance: trust-weighted storage, belief/speech separation, slot-level exclusivity
- Contradiction ledger: detection, preservation, disclosure, user-driven resolution
- GroundCheck: sub-2ms post-generation semantic verification
- Mid-stream verification: fact-checks during generation
- 3-tier cloud routing: local, OpenAI, Claude with seamless timeout recovery
- Cloud-only generation mode: model selector lets users choose Local, GPT-4o, or Claude as primary generator
- Self-referential routing: 70+ patterns, grounded in self-model
- Heartbeat loop: trust decay, memory compression, self-reflection
- Adaptive compression: significance-scored tier system
- Settings dashboard: profile, cloud toggles, known facts, usage tracking
- LLM tool loop: iterative agentic execution with checkpoint confirmation
- Governed memory: authority levels, channel routing, provenance tracking

### Session 3 (March 22, 2026)

- **Slot-level exclusivity enforcement at ingestion** — exclusive slots (`favorite_color`, `name`, `birthday`) now allow only one active value. Old values are demoted to 0.4x trust with `superseded` provenance, not deleted.
- **Cloud generation fallback** — local timeout cascades to OpenAI, then Claude. The CRT pipeline (memory, contradictions, verification, trust) stays local regardless of which generator produces the response.
- **Cloud-only generation mode** — model selector in chat UI lets users swap between Local, GPT-4o, and Claude as primary generator. Selection persists via settings.
- **Claude Tier 2 fully configured** — cookie provider, settings toggles, daily limits, and token tracking all wired end-to-end.
- **Greeting gate bypass** — greetings no longer fire `contradiction_disclosure`, eliminating false positives on simple hellos.
- **Trust re-boost blocked on demoted memories** — once a memory is demoted via slot exclusivity, it cannot regain trust through re-boost.
- **Name persistence chain fixed** — resolved 4 bugs: double-FACT wrapping, `display_name` not reaching the LLM, no deterministic injection, and profile propagation failure.
- **Self-referential routing expanded** — 70+ patterns now recognized, up from ~40.
- **Cloud fallback catches gate failures** — if local generation fails at the gate level, cloud fallback engages instead of returning an error.
- **Health poll intervals reduced** — health checks moved from 5s to 15s, copilot polls from 2s to 5s, cutting idle network traffic significantly.
- **Generic opener removed** — all prompt templates no longer include a canned opening line, producing more natural responses.

### Not Yet Complete

- **XGBoost classifiers**: Not yet trained. Heuristic fallback is active and functional but less precise.
- **Reflection-to-behavior loop**: Stores reflections but does not yet act on them. The loop is not closed.
- **Blindside resistance**: Identity wipe attacks succeed 3/5 times in adversarial testing.
- **Library extraction (Phase C)**: GroundCheck, crt-ledger, crt-trust, crt-gates not yet published as standalone packages.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **A: Natural Agent** | Complete | Natural responses, open-world fact learning, provenance-aware answers |
| **B: Hybrid Routing** | Complete | Local/cloud generation with automatic escalation and redaction |
| **B.5: Agentic Execution** | In Progress | Tool loop, self-reflection, visible reasoning, checkpointed actions |
| **C: Library Extraction** | Planned | Extract groundcheck, crt-ledger, crt-trust, crt-gates as standalone packages |
| **D: Launch** | Planned | PyPI publish, landing page, hosted API option |

See [ROADMAP.md](ROADMAP.md) for the full planning document with weekly priorities and long-term architecture goals.

---

## Documentation

The `docs/` directory contains detailed technical writeups:

- [Three Laws](docs/THREE_LAWS.md) — Design laws and their implementation
- [Architecture](docs/ARCHITECTURE.md) — System architecture
- [Request Lifecycle](docs/REQUEST_LIFECYCLE.md) — Full request flow
- [Memory Lifecycle](docs/MEMORY_LIFECYCLE.md) — Memory creation, evolution, compression
- [Cloud Routing](docs/CLOUD_ROUTING.md) — 3-tier routing design
- [Compression](docs/COMPRESSION.md) — Adaptive compression system
- [Self-Model](docs/SELF_MODEL.md) — Self-referential routing and introspection
- [Configuration](docs/CONFIGURATION.md) — Runtime configuration reference
- [Quick Start](docs/QUICK_START.md) — Getting started guide
- [ViLT Technical Writeup](docs/VILT_TECHNICAL_WRITEUP.md) — Verification-in-the-loop training
- [CRT White Paper](docs/CRT_WHITE_PAPER.md) — Theoretical foundations
- [What Makes CRT Different](docs/WHAT_MAKES_CRT_DIFFERENT.md) — Comparison with other approaches
- [Adversarial Stress Test Report](docs/ADVERSARIAL_STRESS_TEST_REPORT.md) — 50-turn attack results
- [Testing Patterns](docs/TESTING_PATTERNS.md) — Test design and methodology

---

## License

MIT — see [LICENSE](LICENSE)
