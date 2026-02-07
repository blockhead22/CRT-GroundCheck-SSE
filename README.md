# CRT + GroundCheck + SSE

**Contradiction-preserving memory for AI agents. No silent overwrites.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 577 passed](https://img.shields.io/badge/tests-577%20passed-brightgreen.svg)](#test-results)

---

## What This Is

Three integrated systems that give any LLM persistent, auditable memory where contradictions are **signals, not bugs**:

| System | Purpose |
|--------|---------|
| **CRT** (Cognitive-Reflective Transformer) | Trust-weighted memory layer with contradiction ledger, reconstruction gates, and belief evolution |
| **GroundCheck** | Hallucination verification — checks LLM outputs against stored memories at 1.17ms mean latency |
| **SSE** (Semantic String Engine) | Claim extraction with character-level provenance, boundary-enforced (physically cannot delete contradictions) |

Every other AI memory system silently overwrites contradictory information, then confidently presents uncertain facts as truth. CRT preserves the tension, tracks what changed and when, and blocks confident answers when the system is genuinely uncertain.

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

# Run interactive demo
python Rag-Demo.py

# Start the API server
python crt_api.py
# → http://127.0.0.1:8123

# Start frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

### Prerequisites
- Python 3.10+
- `pip install -r requirements.txt`
- Optional: [Ollama](https://ollama.ai/) with a local model for LLM features

---

## How It Works

```
User message
   │
   ▼
IntentRouter ── classifies intent (fact, question, correction, task, chat)
   │
   ▼
Fact Extraction ── Tier A: regex (name, employer, location, age)
   │                Tier B: LLM (hobbies, preferences, open-world)
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
GroundCheck ── verifies output claims against memory (1.17ms mean)
   │
   ▼
Trust Evolution ── aligned memories gain trust, contradicted ones degrade
```

### Key Concepts

**Trust vs. Confidence** — Confidence is how certain something sounded at creation. Trust is how validated it has proven over time. These evolve independently via mathematical equations.

**Contradiction Ledger** — When the user says "I work at Google" after "I work at Microsoft," both memories stay alive. A ledger entry records old memory, new memory, drift measurements, timestamps, and resolution status. Nothing is deleted.

**Reconstruction Gates** — Before the LLM responds to a query touching contradicted facts, gates check for unresolved contradictions. If found, the system blocks the confident response and asks for clarification.

**Natural Language Resolution** — Users resolve contradictions naturally: *"Google is correct, I switched jobs."* Detected via pattern matching and routed to the resolution engine.

**Disclosure Policy** — Facts with medium confidence (0.4–0.9) get routed to clarification instead of binary accept/reject. A budget system prevents overwhelming the user with questions.

---

## Architecture

```
personal_agent/
├── crt_core.py              # Mathematical framework (trust, drift, SSE mode selection)
├── crt_memory.py            # Trust-weighted memory with belief/speech separation
├── crt_ledger.py            # Contradiction ledger (no silent overwrites)
├── crt_rag.py               # CRT-Enhanced RAG engine (the brain)
├── fact_slots.py            # Deterministic regex fact extraction (Tier A)
├── two_tier_facts.py        # Hard slots + open-world tuples (Tier A + B)
├── fact_store.py            # Structured slot-based storage
├── intent_router.py         # Intent classification (15 types)
├── ml_contradiction_detector.py  # XGBoost-based detection
├── llm_drift_assessor.py    # LLM-powered semantic drift classification
├── resolution_patterns.py   # NL resolution pattern matching
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

crt_api.py                   # FastAPI server
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
# GroundCheck verification
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()
memories = [Memory(id="m1", text="User works at Microsoft")]
result = verifier.verify("You work at Amazon", memories)
print(result.passed)          # False
print(result.hallucinations)  # ["Amazon"]
```

```python
# Intent classification
from personal_agent.intent_router import IntentRouter

router = IntentRouter()
result = router.classify("Write me some Python code")
print(result.intent)      # Intent.TASK_CODE
print(result.confidence)  # 0.9
```

---

## API Endpoints

Start the server: `python crt_api.py` (runs on `http://127.0.0.1:8123`)

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
| `/api/episodic/preferences` | GET | Get learned preferences |
| `/api/thread/reset` | POST | Reset a thread's memory and ledger |
| `/api/heartbeat/config` | GET/PUT | Configure proactive engagement |

---

## Testing

```bash
# Full test suite (577 tests)
pytest

# Core stress tests (adversarial + boundary + contradiction)
pytest tests/test_adversarial_prompts.py tests/test_boundary_violations.py tests/test_contradiction_stress.py -v

# GroundCheck stress tests
python groundcheck/stress_test_performance.py   # 1000 verifications, <2ms p95
python groundcheck/stress_test_semantic.py      # Paraphrase handling

# CRT stress test (requires Ollama + API server running)
python tools/crt_stress_test.py --turns 30

# Adversarial challenge (no Ollama required)
python tools/adversarial_crt_challenge.py --turns 35
```

### Test Results (2026-02-06)

| Suite | Result |
|-------|--------|
| pytest (full) | **577 passed** / 8 failed (98.6%) |
| Adversarial + Boundary + Contradiction | **84/84 passed** |
| Coherence, Temporal, Uncertainty, Facts | **73/73 passed** |
| GroundCheck Performance (1000 runs) | **1.17ms mean, 2.09ms p95** |
| GroundCheck vs SelfCheckGPT | **2,634x faster** |

---

## Frontend

React + TypeScript + Tailwind + Framer Motion UI:

- Multi-thread chat with real-time contradiction tracking
- Interactive onboarding tutorial
- Live contradiction ledger with trust scores
- Memory visualization (stable vs. candidate facts)
- Side-by-side comparison: regular AI vs. CRT behavior

```bash
cd frontend && npm install && npm run dev
# → http://localhost:5173 (requires API server running)
```

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
