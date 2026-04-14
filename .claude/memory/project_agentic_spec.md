---
name: CRT Agentic Write Operations Spec
description: Approved philosophical spec for making CRT agentic (post, message, API calls, file ops) — gates, memories, checkpoints defined
type: project
---

Philosophical spec for agentic CRT was written and approved on 2026-03-21. Located at `.claude/plans/breezy-singing-hopcroft.md`.

Key decisions:
- **Intent/direction gates** always run on actions; **memory gates** only when relevant memory exists (no memory = skip, not fail)
- Actions always create memories: **action receipts** (forensic, immutable, SSE Lossless) + **implied beliefs** (epistemic, subject to contradiction tracking)
- 4-tier checkpoint system: auto-execute, quick confirm, full review, blocked pending resolution
- Belief/speech separation: when posting on user's behalf, "I" is the user — gate checks against user-stated beliefs
- The system is a **semantic agent, not a moral one** — gates check coherence with felt intent, not external ethics

**Why:** Nick wants CRT to evolve from mirror to actor while preserving user sovereignty and epistemic honesty. The spec maps all 7 CRT principles to agentic write operations.

**How to apply:** This is the foundation for any agentic implementation work. No code was written — this is spec only. Implementation should follow the action lifecycle: classify → plan → gate → checkpoint → execute → memory write-back → audit.
