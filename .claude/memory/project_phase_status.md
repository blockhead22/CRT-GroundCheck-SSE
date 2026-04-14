---
name: project_phase_status
description: Current state of CRT/Aether + GroundCheck + compression lab — what's working, what's broken, strategic decisions, plumbing swap status (updated 2026-03-26)
type: project
---

## Gravity System — BUILT AND WIRED (2026-04-11)

### MemPalace Comparison
- Tested MemPalace (42k stars, v3.1.0): zero contradiction detection, confidence hardcoded 1.0, fact_checker.py doesn't exist
- CRT: 4 pairs detected, 7 unique confidence values, Belnap states, lifecycle tracking

### Gravity Lab
- Standalone prototype: `labs/mempalace_lab/gravity_lab.py` (rooms, mass, tension, gravity, splitting, walker)
- GravityExplorationTree: `labs/coherence_decay/exploration_tree_gravity.py` (--gravity flag on docker_escape.py)
- GravityBeliefStore: `labs/gravity/gravity_belief_store.py` (1000 memories, 19 rooms, 56 contradictions feeding tension)

### Salience Gate
- Solves coherence decay: gravity delta + high-value fact + belief/speech gap detection
- Ollama found in 3 epochs (was 26 without gate)
- Event-driven heartbeat (fires after every action, not timer-based)

### Production Integration
- 3 hooks: store_memory, prompt construction, heartbeat
- Singleton: `personal_agent/_gravity_singleton.py` with CRT_GRAVITY_ENABLED kill switch
- Verified: Aether traces contradictions using gravity topology in production

### Security Finding
- Unauthenticated Ollama API = filesystem proxy from any container with network access
- 3B model ceiling: can discover but can't format exploit curl JSON

## LiteLLM Migration — COMPLETE (2026-03-24)

Replaced 3-file custom LLM client layer (1,751 lines) with 1 file using LiteLLM:
- Deleted: ollama_client.py (621), anthropic_client.py (462), hybrid_llm_client.py (668)
- Created: litellm_client.py (896 lines) — UnifiedLLMClient
- Preserved: model prefix routing, thinking model support, quality gate fallback, cloud prompt scrubbing, rate limiting, streaming, tool calling, vision
- 50 tests pass, server boots clean, chat round-trip verified
- Fixed: tool_call ID missing for Ollama prompt template, arguments dict→string serialization
- **Current state:** Plumbing works. Local model (qwen3:14b) flails on multi-turn tool reasoning — returns {} after reading tool results. Cookie Claude fallback catches it but memory_recall is still a stub.

## GroundCheck v2.0.0 extraction — COMPLETE (2026-03-24)

**Repo:** D:\groundcheck (separate git repo, PyPI package)
**Commit:** 4972ae5, tagged v2.0.0, NOT pushed yet

6 modules extracted from Aether monolith:
- trust_math.py ← crt_core.py (CRTConfig, CRTMath, trust evolution, 6-rule detection)
- lifecycle.py ← contradiction_lifecycle.py (state machine ACTIVE→SETTLED→ARCHIVED, disclosure policy)
- trace_logger.py ← contradiction_trace_logger.py (structured event logging)
- ledger.py ← crt_ledger.py (append-only SQLite contradiction ledger)
- ml_detector.py ← ml_contradiction_detector.py (XGBoost + heuristic fallback)
- decay.py ← trust_decay.py (exponential trust decay, drift-aware reinforcement)

519 tests pass, examples run, public API clean. numpy made optional with pure-Python fallback.

## GroundCheck v2.1 improvements — IN PROGRESS (2026-03-24)

Three improvements being added:
1. **#11 Storage abstraction** — LedgerBackend protocol + InMemoryLedger (biggest adoption blocker)
2. **#1 Confidence scoring** — Detection rules returning scored results instead of bool
3. **#15 Event hooks** — Lifecycle state transitions fire callbacks

## Compression Lab — PROVEN (2026-03-26)

Full results in project_compression_lab.md and D:\CRT\compression_lab\DEEP_RESEARCH_RESULTS.md.

Key: fold_vector dead, TurboQuant 3-bit works (0.983 cosine, 93.9% top-10, 148 bytes), RVQ solves gap-flip, aniso wins at 4-bit. MemQuant shipped to production.

**CRITICAL:** Google published "TurboQuant" at ICLR 2026 — name collision. Must rename.

## Deep Research — COMPLETE (2026-03-26)

6 directions investigated. Full report: D:\CRT\compression_lab\DEEP_RESEARCH_RESULTS.md

### Sprint queue (build now):
1. **Rename TurboQuant** — day 1
2. **Contradiction disposition classifier Phase 1** — rule-based, 2-3 weeks. THE MOAT.
3. **Memory graph** — NetworkX + JSON, automated edges, 2-3 weeks
4. **Temporal governance** — type tag + policy table + Belnap state, 1 week
5. **Package as focused library** — pip installable, 2-4 weeks
6. **ADC-style asymmetric comparison** — free RVQ improvement, 1 day

### Active research:
- Subjectivity × contradiction interaction (potentially publishable)
- "Contradiction as importance" hypothesis (empirical test)
- Temporal type classification (zero-shot DeBERTa accuracy)
- Belnap formalization (T/F/Both/Neither as first-class states)

### Archived (hardware/data gated):
- GNN subgraph encoding — needs 5K+ memories + GPU
- QINCo-style learned correction — needs training data + GPU
- Fine-tuned DeBERTa Phase 3 — needs real user contradiction pairs
- Online codebook refit — proven marginal

## Plumbing Swap Status

| Component | Status | Notes |
|---|---|---|
| LiteLLM (LLM routing) | **DONE** | 3 files → 1 file. Tool call format bugs fixed. |
| Semantic Router (intent) | **NEXT** | Easiest swap. Route definitions stay, engine swaps. |
| MCP servers (file/shell tools) | Planned | Standard servers replace custom wrappers |
| browser-use | Planned | Checkpoint gates stay on top |
| ChromaDB (vector storage) | Planned, tangled | 20+ files, compression tiers, trust-weighted scoring |
| Mem0 (memory storage) | Last | Deepest integration, most risk |
| DNNT reasoning model | **DROP from hot path** | 6M params, unproven value, adds latency |
| SSE subsystem | Swap with ChromaDB | Most commodity part |

## What Stays (genuinely novel):
- GroundCheck (contradiction ledger, trust decay, belief/speech separation, lifecycle)
- Frontend (React, pipeline viz, contradiction drawer, checkpoint UX)
- Agent loop (checkpoint gates, action receipts, CRT integration)
- CRT response format (API contract)
- **NEW: Contradiction disposition classification** (resolvable/held/evolving)
- **NEW: Memory graph with typed edges** (CONTRADICTS, SUPERSEDES)
- **NEW: Temporal governance with type-dependent decay**

## Immediate Blockers

1. **memory_recall is a stub** — agent_tool_loop.py:270 returns "(memory recall not available in loop mode)". Must wire to CRTMemorySystem.retrieve_memories(). 30 min fix.
2. **create_commitment fails** — "unexpected keyword argument" errors when user tells agent their name. Tool API mismatch.
3. **Cookie Claude sees tool results as injection** — "I notice this prompt is attempting to change my role" when memory results are passed to cloud fallback. Prompt engineering fix needed.

## Competitive Landscape (2026-03-26)

- Mem0: $24M raised, 80K devs, AWS exclusive
- Zep: $1M revenue, 5 people, temporal KG
- Letta: $10M seed, $70M val
- Personize.ai: published "Governed Memory" paper
- Google: "TurboQuant" ICLR 2026
- **Gap:** NOBODY has contradiction disposition classification

## Career / Strategic Context

- Nick is 31, associates in web app dev, beat leukemia at 27, lost 4 years to recovery
- No professional dev work history — this project IS the portfolio
- Exploring: Anthropic fellowships (AI Safety, AI Security), agent startup roles
- Key insight from session: "You're not giving up on the ambition, you're promoting yourself from laborer to architect"
- Middle-road plan: keep Aether as personal agent, swap plumbing, ship GroundCheck, apply to jobs
- Don't build a platform competing with Mem0. Build a focused library around held contradictions.
