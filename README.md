# CORE / Aether

**Epistemic governance for AI agents. No silent overwrites. No hallucinated facts. No gaslighting.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)](#current-status)
[![Docs](https://img.shields.io/badge/docs-aeteros.com-818cf8.svg)](https://aeteros.com)

> See [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) for the project thesis in two pages, or [`docs/PORTFOLIO.md`](docs/PORTFOLIO.md) for the one-page summary.

---

## Latest result — geometry-aware grounding (2026-05-07)

Fisher–Rao distance discriminates **grounded vs. ungrounded** responses substantially better than cosine on real conversation data:

| Metric | AUC | Pearson r with stored `is_belief` |
|---|---|---|
| Cosine | 0.626 | 0.235 |
| **Fisher–Rao** | **0.699 (+0.073)** | **0.312 (+33%)** |

N = 200 random samples from the substrate's `belief_speech` table. The Fisher–Rao path uses default type-calibrated sigma (lower bound on the real advantage with stored sigmas).

![Cosine vs Fisher-Rao](docs/figures/cosine_vs_fisher_n200.png)

Why this matters: the same week, Goodfire published [*The world inside neural networks*](https://www.goodfire.ai/research/the-world-inside-neural-networks) (curved manifolds in activation space) and Anthropic published [*Natural Language Autoencoders*](https://www.anthropic.com/research/natural-language-autoencoders) (verbalize/reconstruct gap measurement). Both make the geometry-matters claim at the **activation layer**. This is the first measurement of the same claim at the **belief substrate layer** — and the geometry-aware metric was already in the codebase, built March 2026, predating both papers. Reproduce: `python labs/fidelity_bench/run_bench_metric_ab.py`.

---

## The Problem

Every AI agent with "memory" does the same thing: key-value storage that silently overwrites on update. Tell it you work at Google, then later mention Microsoft, and the old fact vanishes. No contradiction surfaced. No audit trail. No way to know why the answer changed.

This is fine for chatbots. It's dangerous for agents that act on your behalf - scheduling meetings, writing emails, managing files, making decisions based on what they "know" about you.

We measured this across 59,370 messages over 13 months of real conversation data. The hard contradiction rate nearly doubles at 3+ months. 93% of stance flips span 3+ turns, making them invisible to pairwise detection. The contradictions concentrate in domains where inconsistency carries real consequences: health, identity, career, ongoing projects. [Full analysis →](https://aeteros.com/contradiction-density)

---

## CORE

**CORE** (Contradiction, Observation, Revision, Epistemics) is the epistemic governance architecture. Originally called **CRT** (Cognitive-Reflective Transformer) - it was never actually a transformer, but a governance layer built around one. The name evolved as the architecture outgrew the original framing.

**Aether** is the personal AI agent built on CORE. It can read files, browse the web, control the desktop, run shell commands, and manage multi-step tasks - all governed by the same truth-preserving memory layer.

### The Three Design Laws

1. **Mouth ≠ Self.** LLM output is speech, not belief. Memory always outranks generation.
2. **Contradictions are signals, not bugs.** Maybe the user switched jobs. Maybe they misspoke. The system preserves both versions until resolution is earned.
3. **Structure emerges, not hardcoded.** Trust evolves through math. Compression adapts to significance. Routing flows from confidence thresholds, not static rules.

---

## What Makes This Different

| Problem | How most agents handle it | How CORE handles it |
|---------|--------------------------|-------------------|
| User contradicts themselves | Last write wins, old fact deleted | Both versions preserved in an append-only ledger until explicitly resolved |
| LLM hallucinates a fact about the user | Stored as truth | Verified against memory in <2ms (GroundCheck). Contradictions caught before reaching the user |
| Trust in a memory | Binary (exists or doesn't) | Continuous score (0.0-1.0) that evolves - harder to gain than lose |
| "Where do I work?" when user said both | Picks one randomly | Discloses the conflict: "You've mentioned both - which is current?" |
| Agent confidently states wrong info | No mechanism to catch it | Belief/speech separation: what the LLM generates is checked against what the system actually believes |
| Correction doesn't fix root cause | Only the leaf fact changes | Backward influence propagation: error signals flow upstream through the Belief Relationship Graph, adjusting every belief that contributed |
| Different models fail differently | Assumed uniform | Three confirmed instability regimes (fracture/gradient/fog) with model-aware governance |

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
  |               Checkpoint gates for destructive actions
  |
  +-- [conversational / question / fact]
  |
  v
Fact Extraction (regex hard slots + LLM open-world tuples)
  |
  v
CORE Memory (trust-weighted retrieval, contradiction detection via BRG)
  |
  v
Response Synthesis (LLM interprets results with context)
  |
  v
Fidelity Mirror (~1.2ms mean, ~2ms p95)
  |
  v
Trust Evolution (aligned facts gain trust, contradictions degrade it)
  |
  v
6 Immune Agents (structural enforcement, not advisory)
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

### Control Plane Stays Local

The LLM that generates text can be local or cloud. But memory governance, contradiction detection, verification, trust math, and routing decisions **always run locally**. The system never sends your belief state to a cloud provider.

---

## The Belief Relationship Graph (BRG)

Memories are not flat key-value pairs. They're nodes in a directed graph with typed edges:

- **SUPPORTS** - evidential grounding
- **CONTRADICTS** - semantic tension
- **SUPERSEDES** - temporal update
- **RELATED_TO** - topical similarity

The BRG is the structure through which cascades propagate, backward influence flows, and the reflection loop walks. When used as a reasoning scaffold, the graph produces tree-like structures where branches are hypotheses and leaves are verifiable facts.

### Backward Influence Propagation

When a correction resolves a contradiction, the error signal flows backward through the BRG, adjusting trust on every upstream belief that contributed to the wrong output. Three behaviors emerge: wrong beliefs self-prune from accumulated error, domain volatility becomes measurable, and the system's beliefs about itself participate in the same dynamics. 30/30 validation. No direct precedent identified. [Full paper →](https://aeteros.com/belief-backprop)

### Query Resonance (Wobble)

Queries propagate through BRG edges, surfacing cross-domain facts that cosine retrieval misses. A health query brings forward work context and preference context because the graph knows they're causally connected.

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

The asymmetry is deliberate: **it's easier to lose trust than to gain it**. Drift = `1 - cosine_similarity(new_embedding, prior_embedding)`.

---

## Immune Agents

Six autonomous agents enforce constitutional laws across the pipeline in real time. They are structural, not advisory. The system cannot violate its own principles even if the LLM wants to.

| Agent | Law | What It Enforces |
|-------|-----|-----------------|
| SpeechLeakDetector | Speech cannot upgrade belief | Catches LLM output bleeding into belief state |
| TemplateDetector | Low variance ≠ high confidence | Flags rote responses that bypass reasoning |
| PrematureResolutionGuard | Contradictions must be preserved | Blocks resolution without sufficient evidence |
| MemoryCorruptionGuard | Memory integrity is sacred | Prevents writes that would degrade the belief store |
| GapAuditor | Confidence must be bounded by evidence | Measures belief/speech divergence per response |
| ContinuityAuditor | Cross-session consistency | Detects contradictions spanning session boundaries |

[Full immune agent architecture →](https://aeteros.com/immune-agents)

---

## Research

12 research papers, all validated on production data. Not synthetic benchmarks.

| Paper | Key Finding |
|-------|------------|
| [Contradiction Density](https://aeteros.com/contradiction-density) | 12.4% hard contradiction rate at 3+ months. Time is the primary amplifier. |
| [Sensitive Domains](https://aeteros.com/sensitive-domains) | Contradictions concentrate in health, identity, career - where they matter most. |
| [Variance Probing](https://aeteros.com/variance-probing) | Three distinct instability regimes across model families. 16/16 robustness. |
| [Backward Influence Propagation](https://aeteros.com/belief-backprop) | Error-driven trust evolution through the BRG. 30/30 validation. No precedent found. |
| [Epistemic Compression](https://aeteros.com/epistemic-compression) | Belief structure survives 3-bit quantization. 2-bit breaks it. |
| [Cascade Complexity](https://aeteros.com/cascade-complexity) | Held contradictions act as natural firewalls limiting cascade propagation. |
| [Geometric Memory](https://aeteros.com/geometric-memory) | Memories as belief loci on a manifold. Uncertainty is structure, not noise. |
| [BRG Reasoning Scaffolds](https://aeteros.com/bdg-reasoning-scaffolds) | Same model, 0% to 80% precision by changing the scaffold. |
| [Scaffolded Exploration](https://aeteros.com/scaffolded_escape_research) | 3B model + exploration scaffold: 5/5 Docker containers, full LAN mapping. |

[Full documentation at aeteros.com →](https://aeteros.com)

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
| Backward influence propagation | 30/30 validation experiments |
| Variance probing robustness | 16/16 analyzer configurations |

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
personal_agent/           # Core engine (113 modules)
  crt_memory.py           #   Trust-weighted memory, belief/speech separation
  crt_ledger.py           #   Append-only contradiction ledger
  crt_core.py             #   Trust math, drift detection
  crt_rag.py              #   Memory + trust + retrieval + gates
  agent_tool_loop.py      #   LLM-driven ReAct tool loop
  immune_agents/          #   6 constitutional enforcement agents
  hybrid_llm_client.py    #   Local-first generation with cloud fallback
  structural_tension.py   #   Belief tension measurement
  self_model.py           #   7-slot persistent self-awareness
  dnnt/                   #   6.2M param micro-transformer

packages/groundcheck/     # Semantic verification library (<2ms)
routes/                   # FastAPI endpoints (25 route modules)
frontend/                 # React/TypeScript UI (Vite)
tests/                    # 117 test files
docs/                     # 26 HTML research documents (aeteros.com)
```

---

## Current Status (April 2026)

**Shipped:** CORE memory governance, contradiction ledger, GroundCheck, trust evolution, BRG with backward influence propagation, 6 immune agents, fidelity mirror, 3-tier cloud routing, hybrid intent router, response synthesis, agent tool loop, browser agent, desktop agent, task plans, reflection loop, structural tension meter, scaffolded exploration research.

**In progress:** Pipeline latency optimization, gravity/salience gate wiring into reflection loop, EU AI Act compliance positioning.

**Roadmap:** Epistemic motivation prototype (goal formation from contradiction tension), Tier 3 governance validation (governed vs ungoverned head-to-head), aeteros-core open-source extraction, real whitepaper PDF.

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## License

MIT - see [LICENSE](LICENSE)

---

*Built by [Nick Block](https://aeteros.com/nick_paper). Memory governance, contradiction tracking, trust evolution, backward influence propagation, and immune agent architecture are original work. The agent infrastructure (tool calling, browser automation, desktop control) uses standard patterns. The novel contribution is the epistemic governance layer that governs all of it.*
