---
name: Repo Split — crt-core (public) vs AI_round2 (private) + Claude Code reference
description: UNIVERSAL PRIORITY. How code splits between public framework and private product. What goes where. Dev workflow. Extraction rules. Claude Code source patterns mapped to the split.
type: feedback
---

## The Split

**crt-core** (`D:/crt-core`, public, https://github.com/blockhead22/crt-core) — the library. Reusable building blocks. No database, no UI, no LLM calls. Anyone can install and use.

**AI_round2** (`D:/AI_round2`, private) — the product. Aether. All wiring, frontend, prompt engineering, trained models, production data. Imports crt-core as a dependency.

**src/src/** (`D:/AI_round2/src/src/`, reference only) — leaked Claude Code source. TypeScript. Not imported, not executed. Used as architectural reference for runtime patterns.

**Why:** Open the framework, keep the product. The threat isn't IP theft, it's obscurity. The framework generates adoption and credibility. The product generates revenue.

## What lives where

### crt-core (public) — SHIPPED
- 6 immune agents (template_detector, speech_leak_detector, premature_resolution_guard, memory_corruption_guard, gap_auditor, continuity_auditor)
- GovernanceLayer (4-tier dispatcher: SAFE/FLAG/HEDGE/ESCALATE)
- 9 tests, README, pyproject.toml, MIT license

### crt-core (public) — NEXT EXTRACTION
- Belief region math (was "memory splats") — Gaussian representations with uncertainty
- Trust evolution (decay, reinforcement, correction curves)
- Contradiction lifecycle (Active → Settling → Settled → Archived)
- Belief/speech engine (auditable gap)
- Belief classifier (fact vs position, built 2026-04-01)
- BDG (belief dependency graph)
- GovernedTask primitive (task type + belief context + authority ceiling + TTL + checkpoint policy) — generic lifecycle, no wiring
- Concurrent tool executor interface (`is_concurrent_safe` per tool definition) — pattern only, no specific tools

### AI_round2 (private) — NEVER MOVES
- Prompt prefix / epistemology axioms (Aether's personality)
- Cookie orchestrator / brain provider wiring (ClaudeCliBrain, AnthropicBrain, etc.)
- Trained model weights (DNNT, belief head, vilt)
- Production databases (memory, run logs, variance data)
- Frontend (React UI, pipeline visualization)
- Full chat route pipeline (130+ modules)
- Channel integrations (Telegram, Discord, Electron)
- Session state, compaction wiring, agent run log integration
- Deferred tool loading wiring (which tools defer, ToolSearch integration)
- Coordinator/swarm mode (worker spawning, scratchpad, task notifications)
- Suspend/resume serialization (diff_write, ask_user, remaining_iterations)
- Permission classifier integration (AI-powered, denial history tracking)

## Claude Code patterns — where they land

These are runtime patterns from `src/src/` that CRT should absorb. Each maps to one side of the split:

| Pattern | Goes to crt-core? | Goes to AI_round2? | Notes |
|---|---|---|---|
| `isConcurrencySafe()` per tool | Interface/protocol yes | Wiring yes | crt-core defines the protocol, AI_round2 implements per-tool |
| Task taxonomy (6 types) | GovernedTask base yes | Type registry, disk buffering | crt-core owns lifecycle states, AI_round2 owns execution |
| Coordinator/worker | No | Yes | Product-specific orchestration |
| Deferred tool loading | No | Yes | Prompt assembly is product wiring |
| Selective reinjection post-compact | No | Yes | Compaction policy is product-specific |
| Lifecycle hooks at compaction | Hook interface yes | Wiring yes | crt-core defines hook points, AI_round2 fires governance |
| Permission classifier | No | Yes | LLM call + denial history = product |
| Bridge/remote sessions | No | Yes | Product infrastructure |
| Speculation pipeline | No | Yes | Product UX optimization |
| Epistemic worker packets | BeliefPacket type yes | Serialization yes | crt-core defines the packet, AI_round2 wires handoffs |

**Rule of thumb:** If it's a *protocol, interface, or data structure* with no LLM/DB/UI dependency → crt-core. If it's *wiring, policy, or integration* → AI_round2.

## Dev workflow

1. Develop in AI_round2. Always. Nothing changes.
2. When something stabilizes and is generic, extract a clean version to crt-core.
3. crt-core NEVER imports from AI_round2. AI_round2 imports from crt-core.
4. Public repo stays clean — small surface, tested, documented.
5. Private repo stays fast and messy — nobody sees it.
6. pytest in crt-core before every push. GitHub Actions runs CI.
7. Semver tags when solid (0.1.0 = governance, 0.2.0 = memory, etc.)
8. `src/src/` is reference material — never import, never execute, never commit to either repo.

## Extraction rules

Before moving code to crt-core:
- Strip all `personal_agent.*` imports — make dependencies injectable
- No SQLite assumptions — the library is storage-agnostic
- No LLM calls — the library provides structure, the product provides the model
- Every public function has a test
- README updated with new module docs

**How to apply:** Every time code is written or a feature is built, ask: "Is this product-specific wiring, or is this a reusable epistemic pattern?" If reusable, it belongs in crt-core eventually. If it touches the database, the prompt, the UI, or a specific LLM provider, it stays in AI_round2.
