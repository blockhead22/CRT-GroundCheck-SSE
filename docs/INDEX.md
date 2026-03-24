# CRT/Aether Documentation

**Current version:** v2.7 (March 24, 2026)

Aether is a personal AI assistant built on CRT (Contradiction-aware Reconciliation and Trust) — a memory governance engine that preserves contradictions, tracks belief evolution, and maintains trust scores across every fact it learns. Unlike conventional AI memory (which silently overwrites), CRT treats disagreement as signal.

---

## Quick Navigation

**New here?** Start with [Quick Start](QUICK_START.md) and [Three Laws](THREE_LAWS.md).
**Want the theory?** Read the [CRT White Paper](CRT_WHITE_PAPER.md).
**Building on top?** See the [API Contract](specs/API_CONTRACT.md) and [Configuration](CONFIGURATION.md).

---

## Core Architecture

| Document | Description |
|----------|-------------|
| [Three Laws](THREE_LAWS.md) | The three design laws governing every subsystem: belief > speech, preserve contradictions, emergent structure |
| [Architecture](ARCHITECTURE.md) | 7-tier subsystem overview: Memory, Verification, Reflection, Compression, Routing, ViLT, CRT-as-Critic |
| [Request Lifecycle](REQUEST_LIFECYCLE.md) | Full request flow from user input through intent routing, fact extraction, memory retrieval, gates, generation, and trust evolution |
| [What Makes CRT Different](WHAT_MAKES_CRT_DIFFERENT.md) | Comparison with ChatGPT memory, RAG, MemGPT, and other approaches |

## Memory & Trust Subsystems

| Document | Description |
|----------|-------------|
| [Memory Lifecycle](MEMORY_LIFECYCLE.md) | Memory creation, trust scoring, confidence vs trust, compression tiers, deprecation policy |
| [Compression](COMPRESSION.md) | V(t)-driven semantic compression, significance scoring, tier transitions (10D/64D/384D) |
| [Dynamic Slot Discovery](SLOT_DISCOVERY.md) | v2.1 — Learned slot types from contradiction patterns. Replaces hardcoded EXCLUSIVE_SLOTS with emergent structure |
| [Belief Synthesis & Volatility](BELIEF_SYNTHESIS.md) | v2.5 — Worldview answers from belief trajectories, trust-weighted clustering, volatility-gated context budget |

## Intelligence & Routing

| Document | Description |
|----------|-------------|
| [Semantic Intent Router](SEMANTIC_INTENT_ROUTER.md) | v2.2 — Embedding-based intent classification with 140+ prototypes, hybrid routing, self-improvement via corrections |
| [Task Triage & Acknowledgment](TASK_TRIAGE.md) | v2.4 — "Pause to think" step with instant acknowledgment, capability-aware re-routing, post-task memory |
| [Sub-Agents & Orchestration](SUB_AGENTS.md) | v2.6 — 8 specialized agents, dependency graph decomposition, parallel execution, weakest-link trust propagation |
| [Intuition Check](INTUITION_CHECK.md) | v2.7 — Lightweight gpt-4o-mini side-channel: clarify ambiguous input, suggest next steps, reconnect after idle |
| [Cloud Routing](CLOUD_ROUTING.md) | 3-tier routing (Local, OpenAI Tier 1, Claude Tier 2), escalation policy, fallback logic |
| [Self-Model](SELF_MODEL.md) | 7-slot self-awareness system, heartbeat reflection, personality checkpoints, behavioral directives |

## Agent Capabilities

| Document | Description |
|----------|-------------|
| [Desktop Control](DESKTOP_CONTROL.md) | v2.3 — ReAct vision loop: screenshot, analyze, act, verify. Coordinate scaling, safety system, memory-grounded vision |
| [Action Execution Layer](ACTION_EXECUTION.md) | v1.9 — File read/write, shell exec, git ops, action receipts, checkpoint gating with diff/command preview |
| [Commitments & Scheduling](COMMITMENTS.md) | v2.0 — Reminders, recurring tasks, natural language time parsing, browser notifications, proactive triggers |
| [System Info & Heartbeat](SYSTEM_HEARTBEAT.md) | v1.8+ — System awareness (CPU/RAM/GPU), 24/7 heartbeat scheduler, self-reflection, behavioral triggers |
| [Skill System](SKILL_SYSTEM.md) | v1.7 — SKILL.md-based service integration, install pipeline, trust levels, LLM tool loop execution |

## Getting Started

| Document | Description |
|----------|-------------|
| [Quick Start](QUICK_START.md) | Installation, environment setup, frontend/backend startup, first conversation walkthrough |
| [CRT White Paper](CRT_WHITE_PAPER.md) | Theoretical foundations: trust math, contradiction theory, epistemic governance |
| [Configuration](CONFIGURATION.md) | Runtime config reference, JSON schema, environment variables, product modes |

## Training & Verification

| Document | Description |
|----------|-------------|
| [ViLT Technical Writeup](VILT_TECHNICAL_WRITEUP.md) | Verification-In-the-Loop Training: trust-weighted loss, GroundCheck mid-training, SmolLM/Qwen results |

## Testing & Quality

| Document | Description |
|----------|-------------|
| [Testing Patterns](TESTING_PATTERNS.md) | Test design principles, adversarial categories, stress test methodology |
| [Testing Methods](TESTING_METHODS.md) | Unit/integration/stress test approaches |
| [Adversarial Stress Test Report](ADVERSARIAL_STRESS_TEST_REPORT.md) | 50-turn attack results: 79% handled, gaslighting/identity wipe analysis |
| [Anti-Patterns](ANTI_PATTERNS.md) | What NOT to do: silent overwrites, hardcoded routes, trust leaks |

## Frozen Specs (v0.9.0, Feb 2026)

These specifications are frozen and represent the baseline API contract. New endpoints added since v1.7 are documented in the individual feature guides above.

| Document | Description |
|----------|-------------|
| [API Contract](specs/API_CONTRACT.md) | 99 endpoint definitions and Pydantic models (frozen Feb 8, 2026) |
| [Architecture Spec](specs/ARCHITECTURE.md) | Detailed architecture specification |
| [Freeze Manifest](specs/FREEZE_MANIFEST.md) | Defines what is frozen for stability |
| [Innovation Pillars](specs/INNOVATION_PILLARS.md) | Philosophical pillars for design decisions |

## Project Meta

| Document | Description |
|----------|-------------|
| [Changelog](../CHANGELOG.md) | Version-by-version feature, fix, and polish history |
| [Roadmap](../ROADMAP.md) | Done, in progress, and backlog items |

## Archive

Superseded documents moved to `archive/`:
- `IMPLEMENTATION_PLAN.md` — superseded by [ROADMAP.md](../ROADMAP.md)
- `PATTERN_FIXES_SESSION.md` — Jan 2026 session notes
- `SESSION_COMPLETE.md` — Jan 2026 session wrap-up
- `SYSTEM_ASSESSMENT.md` — Jan 2026 architecture snapshot
- `TECHNICAL_REFERENCE.md` — content migrated to active docs

---

## Access Layer Model

All agent capabilities follow this gating hierarchy:

```
Layer 1: Read system info     → no gate (heartbeat, passive)
Layer 2: Read files/projects  → low gate (first access checkpoint, then trusted)
Layer 3: Write files/code     → high gate (always checkpoint, show diff)
Layer 4: Shell execution      → highest gate (always checkpoint, show command)
Layer 5: External APIs        → per-service gate (skill system)
Layer 6: Desktop control      → action-level gate (safe = free, dangerous = checkpoint)
```

## Design Laws

1. **The mouth should never outweigh the self** — what the model says is weighted less than what it knows
2. **Contradictions are preserved unless resolution is earned** — disagreement is signal, not error
3. **Structure should emerge, not be hardcoded** — slot types, routing rules, and behaviors are learned
