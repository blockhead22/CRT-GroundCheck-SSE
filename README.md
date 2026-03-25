# CRT/Aether

**Memory governance for AI agents. No silent overwrites. No hallucinated facts. No gaslighting.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)](#current-status)

---

## The Problem

Every AI agent with "memory" does the same thing: key-value storage that silently overwrites on update. Tell it you work at Google, then later mention Microsoft, and the old fact vanishes. No contradiction surfaced. No audit trail. No way to know why the answer changed.

This is fine for chatbots. It's dangerous for agents that act on your behalf — scheduling meetings, writing emails, managing files, making decisions based on what they "know" about you.

**CRT (Contradiction-aware Reconciliation and Trust)** is a memory governance layer that treats this as a solved problem. Every fact has a trust score that evolves over time. Contradictions are preserved, not overwritten. The system verifies its own output against stored beliefs before responding. The LLM's voice is not treated as truth — memory is.

**Aether** is the personal AI agent built on CRT. It can read files, browse the web, control the desktop, run shell commands, and manage multi-step tasks — all governed by the same truth-preserving memory layer.

---

## What Makes This Different

| Problem | How most agents handle it | How CRT handles it |
|---------|--------------------------|-------------------|
| User contradicts themselves | Last write wins, old fact deleted | Both versions preserved in an append-only ledger until explicitly resolved |
| LLM hallucinates a fact about the user | Stored as truth | Verified against memory in <2ms (GroundCheck). Contradictions caught before reaching the user |
| Trust in a memory | Binary (exists or doesn't) | Continuous score (0.0-1.0) that evolves — harder to gain than lose |
| "Where do I work?" when user said both Google and Microsoft | Picks one randomly | Discloses the conflict: "You've mentioned both — which is current?" |
| Agent confidently states wrong info | No mechanism to catch it | Belief/speech separation: what the LLM generates is checked against what the system actually believes |

### The Three Design Laws

1. **Mouth ≠ Self.** LLM output is speech, not belief. Memory always outranks generation.
2. **Contradictions are signals, not bugs.** Maybe the user switched jobs. Maybe they misspoke. The system preserves both versions until resolution is earned.
3. **Structure emerges, not hardcoded.** Trust evolves through math. Compression adapts to significance. Routing flows from confidence thresholds, not static rules.

---

## Architecture

```
User message
  |
  v
Intent Router (regex -> local LLM -> cloud LLM, self-improving)
  |
  +-- [task] --> Agent Tool Loop (ReAct pattern)
  |               LLM picks tools -> executes -> sees results -> next step
  |               Checkpoint gates for destructive actions (file write, shell exec)
  |
  +-- [conversational / question / fact]
  |
  v
Fact Extraction (regex hard slots + LLM open-world tuples)
  |
  v
CRT Memory (trust-weighted retrieval, contradiction detection)
  |
  v
Response Synthesis (LLM interprets results with context, not raw dump)
  |
  v
GroundCheck Verification (~1.2ms mean, ~2ms p95)
  |
  v
Trust Evolution (aligned facts gain trust, contradictions degrade it)
```

### Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, SQLite |
| Frontend | React, TypeScript, Vite |
| Local LLM | Ollama (qwen3:14b, tested on RTX 3060) |
| Embeddings | all-MiniLM-L6-v2 (384D, runs on CPU) |
| Cloud fallback | OpenAI gpt-4o-mini, Claude API |
| Verification | GroundCheck (custom, sub-2ms semantic verification) |
| Browser | Playwright (DOM-first, vision fallback) |
| Desktop | pyautogui + mss + vision provider |

### Key Design Decision: Control Plane Stays Local

The LLM that generates text can be local or cloud — that's a cost/quality tradeoff the user controls. But memory governance, contradiction detection, verification, trust math, and routing decisions **always run locally**. The system never sends your belief state to a cloud provider.

---

## Trust Math

Memories carry evolving trust scores with asymmetric dynamics:

**Trust gain** (when new evidence aligns):
```
t_new = clip(t + 0.10 * (1 - drift), 0, 1)
```

**Trust decay** (when contradiction detected):
```
t_new = clip(t * (1 - 0.15 * drift), 0, 1)
```

The asymmetry is deliberate: **it's easier to lose trust than to gain it** (decay rate 0.15 > gain rate 0.10). This mirrors how human trust works — one lie erodes trust faster than ten truths build it.

Drift is measured as `D = 1 - cosine_similarity(new_embedding, prior_embedding)`:

| Drift | Meaning | Action |
|-------|---------|--------|
| < 0.15 | Aligned | Reinforce trust |
| 0.15 - 0.28 | Ambiguous | Soft update, belief evolves slowly |
| > 0.28 | Contradiction | Ledger entry created, reconstruction gates armed |

---

## Capabilities

### Memory Governance (the core)
- **Trust-weighted storage** with belief/speech separation
- **Append-only contradiction ledger** — both versions survive, resolution is explicit
- **GroundCheck verification** — sub-2ms post-generation semantic check (2,634x faster than SelfCheckGPT)
- **Reconstruction gates** — if unresolved contradictions exist in a queried slot, the system asks for clarification instead of confabulating
- **Adaptive compression** — high-significance memories get full embeddings (384D), routine facts compress to sketches (10D)
- **Heartbeat loop** — periodic trust decay, compression lifecycle, blind spot tracking, self-model updates

### Agent Tool System
- **LLM-driven tool loop** (ReAct pattern) — reads files, browses web, runs shell commands, manages git
- **17 registered tools** with safety layers (read-only, gated, checkpointed)
- **Browser agent** — Playwright-based, DOM-first with safety gates (blocked domains, blocked form fields, rate limits)
- **Desktop agent** — pyautogui + vision for GUI automation
- **Checkpoint gates** — destructive actions require user confirmation
- **Task plans** — multi-step work tracked across messages with progress UI

### Hybrid Routing
- **3-tier intent classification**: regex (instant, free) -> local LLM -> cloud LLM
- **Self-improving**: successful task completions auto-generate new regex patterns over time
- **User-selectable mode**: local-only, cloud-only, or hybrid
- **Response synthesis**: LLM interprets tool results with context instead of dumping raw output

### Self-Referential Routing
- 70+ question patterns about the agent itself ("what are you?", "how do you remember things?")
- Answers grounded in actual self-model state, not hallucinated

---

## Benchmarks

| Test | Result |
|------|--------|
| Adversarial + Boundary + Contradiction | 84/84 passed |
| Core functionality (coherence, temporal, uncertainty) | 73/73 passed |
| GroundCheck latency (1000 runs) | 1.17ms mean, 2.09ms p95 |
| GroundCheck vs SelfCheckGPT | 2,634x faster |
| Direct contradiction detection (9 exclusive slots) | 9/9 (100%) |
| 50-turn adversarial stress test | 15/19 attacks handled (79%) |
| Gaslighting resistance | 4/5 handled |

### ViLT Experiments (Verification-in-the-Loop Training)

Proved that real-time verification feedback can teach small models to respect user-specific facts:

| Model | Params | Accuracy | VRAM | Notes |
|-------|--------|----------|------|-------|
| SmolLM-135M + LoRA | 1.8M | 88% | 0.52 GB | No mode collapse |
| Qwen2.5-1.5B + LoRA | 4.4M | 88% | 3.05 GB | GroundCheck pass rate: 75% |

---

## Quick Start

```bash
# Prerequisites: Python 3.11+, Node.js 18+, Ollama with a model pulled
ollama pull qwen3:14b

# Clone and install
git clone <repo-url> && cd AI_round2
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt

# Start the API
python crt_api.py  # -> http://127.0.0.1:8123

# Start the frontend (separate terminal)
cd frontend && npm install && npm run dev  # -> http://localhost:5173
```

Optional cloud providers (set in `.env`):
```bash
OPENAI_API_KEY=sk-...        # gpt-4o-mini for governance + fallback generation
CLAUDE_SESSION_COOKIE=...    # Claude for complex reasoning escalation
```

---

## Project Structure

```
personal_agent/           # Core CRT engine (113 modules)
  crt_memory.py           #   Trust-weighted memory, belief/speech separation
  crt_ledger.py           #   Append-only contradiction ledger
  crt_core.py             #   Trust math, drift detection
  crt_rag.py              #   Integrates memory + trust + retrieval + gates
  agent_tool_loop.py      #   LLM-driven ReAct tool loop
  hybrid_llm_client.py    #   Local-first generation with cloud fallback
  tool_registry.py        #   Unified tool definitions (17 tools)
  response_synthesis.py   #   LLM interprets results before responding
  browser_agent.py        #   Playwright browser automation
  desktop_agent.py        #   pyautogui desktop control
  plan_engine.py          #   Multi-step task planning
  dnnt/                   #   6.2M param micro-transformer

packages/groundcheck/     # Semantic verification library (<2ms)
routes/                   # FastAPI endpoints (25 route modules)
frontend/                 # React/TypeScript UI (Vite, glassmorphism dark theme)
tests/                    # 117 test files
tools/                    # Stress tests, adversarial drivers, calibration
docs/                     # 35+ technical writeups
```

---

## Current Status (March 2026, v3.1)

**Shipped:** CRT memory governance, contradiction ledger, GroundCheck, trust evolution, 3-tier cloud routing, hybrid intent router, response synthesis, agent tool loop, browser agent, desktop agent, task plans, Telegram integration, settings dashboard, 7 continuous background loops.

**In progress:** Stabilizing the agent tool loop (Ollama compatibility with complex tool results), per-tool model configuration, local vision model integration.

**Backlog:** GroundCheck PyPI extraction, multi-user scaffolding, voice I/O, persistence hardening.

See [CHANGELOG.md](CHANGELOG.md) and [ROADMAP.md](ROADMAP.md) for full history.

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [Three Laws](docs/THREE_LAWS.md) | Design philosophy |
| [Architecture](docs/ARCHITECTURE.md) | System design and data flow |
| [Request Lifecycle](docs/REQUEST_LIFECYCLE.md) | Full message pipeline |
| [Memory Lifecycle](docs/MEMORY_LIFECYCLE.md) | Memory creation, evolution, compression |
| [CRT White Paper](docs/CRT_WHITE_PAPER.md) | Theoretical foundations |
| [Agent Loop](docs/AGENT_LOOP.md) | Tool-calling loop architecture |
| [Cloud Routing](docs/CLOUD_ROUTING.md) | 3-tier routing strategy |
| [Browser Control](docs/BROWSER_CONTROL.md) | Web automation |
| [Desktop Control](docs/DESKTOP_CONTROL.md) | Desktop agent |
| [Task Plans](docs/TASK_PLANS.md) | Multi-step work planning |
| [ViLT Writeup](docs/VILT_TECHNICAL_WRITEUP.md) | Verification-in-the-loop training |
| [Adversarial Report](docs/ADVERSARIAL_STRESS_TEST_REPORT.md) | 50-turn attack results |

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built by a solo developer. Memory governance, contradiction tracking, and trust evolution are original work. The agent infrastructure (tool calling, browser automation, desktop control) uses standard patterns. The novel contribution is the truth-preserving layer that governs all of it.*
