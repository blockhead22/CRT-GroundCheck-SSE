---
name: Business Strategy & Open Source Plan
description: Full business thesis — governance-as-a-service, open/closed split, dev workflow, reversed CRT, phased execution. Decided 2026-04-01.
type: project
---

## Core Thesis

The product is not Aether (the assistant). Aether is the demo. The product is **epistemic governance for AI applications** — a middleware layer that sits between any LLM and any application, providing trust scoring, contradiction detection, belief/speech gap auditing, and immune agent governance.

**"Your AI agent doesn't know what it doesn't know. Ours does."**

## The Reversed CRT Insight

CRT was built to govern the AI's epistemics. The same system, rotated 180 degrees, governs the USER's information environment. Every CRT module has a reversed counterpart:

- SpeechLeakDetector → catches user consuming claims louder than their evidence
- TemplateDetector → catches user falling into formulaic thinking (opinion calcification)
- PrematureResolutionGuard → catches user collapsing genuine uncertainty too fast
- MemoryCorruptionGuard → detects new information silently overwriting long-held beliefs
- GapAuditor → tracks user's own belief/speech gap over time
- ContinuityAuditor → tracks when user's values drift without awareness

Memory splats track the user's belief landscape (tight = certain, wide = uncertain, converging = collision incoming). The engine is the same. The subject changes.

**Why:** "CRT was built to keep AI honest. Turns out humans need it more."

## Open / Closed Split

### Open (crt-core, MIT license, public repo)
- Immune agents (6 governance agents + GovernanceLayer)
- Belief/speech engine
- Memory splats + predictive contradiction
- Contradiction lifecycle
- Trust evolution math (decay, reinforcement, correction)
- Belief classifier (fact vs position)
- GroundCheck (grounding verification)
- Memory graph / BDG engine

### Closed (private repo, the product)
- Prompt prefix (the 6 epistemology axioms — Aether's personality)
- Provider wiring (Cookie orchestrator, brain providers, free Claude access)
- Trained model checkpoints (DNNT, belief head, vilt models)
- Production data (memory DBs, run logs, variance experiments)
- Frontend (React UI, pipeline visualization, contradiction drawer)
- Full integration wiring (130+ module pipeline, chat routes, session state)
- Channel integrations (Telegram, Discord, Electron)

## Dev & Release Workflow

Two repos:
- `crt-core` (public) — the framework, pip-installable
- Private repo — the product, imports crt-core

Workflow:
1. Develop in private. Always.
2. When something stabilizes, extract clean version to crt-core.
3. Public repo has pytest tests (save the terminal tests you already run).
4. GitHub Actions runs pytest on push (free for public repos).
5. Semver tags when solid. No schedule. Just tag.
6. Private repo depends on public via pip install.

No formal test lifecycle. Just save the tests you already write in the terminal.

## Business Phases

```
Phase 1: Open source crt-core (adoption, credibility, timestamp)
Phase 2: Hosted API — governance-as-a-service (revenue)
         → Per-call billing, like Stripe for trust scoring
         → Wrap any LLM output through immune agents + trust pipeline
         → Customer gets: trust scores, contradiction flags, governance verdicts, audit trail
Phase 3: Enterprise dashboard — "Datadog for AI epistemics" (scale)
         → Alerting when belief/speech gap widens
         → Trust decay monitoring
         → Contradiction resolution tracking
Phase 4: Reversed CRT — consumer epistemic mirror (moonshot)
         → User belief tracking, calcification detection, overwrite alerts
         → "Your Beliefs" page showing epistemic landscape
```

## Competitive Moat

Not the code (rebuildable). Not the ideas (describable). The moat is:
1. **Integration knowledge** — months of empirical work knowing how pieces connect
2. **Failure data** — Qwen3 fracture, Mistral gradient, template collapse blind spot, domain inversion. Baked into governance rules.
3. **Adoption before necessity** — when the first major agent-memory failure hits the news, be the standard already

## User Belief System (shipped 2026-04-01)

Phase 0 of the reversed CRT built today:
- `user_belief` memory kind added (distinct from `user_fact`)
- Belief classifier: regex-based, <1ms, 13/13 test accuracy
- Input classifier updated: "I think", "I believe", "I agree" now stored instead of discarded
- Storage path routes beliefs to `kind=user_belief` with wide sigma (2.0), slow decay (365d)
- BDG handles user_belief nodes with contradiction edges automatically
- `/api/beliefs` endpoint returns beliefs with trust scores, trajectories, contradictions
- LLM belief extraction prompt added for structured extraction

## Key Decision (2026-04-01)

Nick considered keeping repo closed. Decision: **open the framework, keep the product**. Reasoning: the threat isn't IP theft, it's obscurity. Being first only counts with a public timestamp. The competitive window is months-not-years before big labs implement similar ideas independently.
