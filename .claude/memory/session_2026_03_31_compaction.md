---
name: session_2026_03_31_compaction
description: Belief-aware compaction system shipped — trust-tiered context compression, compaction decay enforcement, memory consolidation pass, all integrated and tested
type: project
---

## Session: 2026-03-31 (night)

### Belief-Aware Compaction — SHIPPED

Three interconnected features built, tested, and integrated:

**1. Belief-Aware Compaction** (`personal_agent/belief_compaction.py`)
- `compact_context()` produces a `BeliefSnapshot` instead of a content summary
- Trust tiers: locked→always verbatim, trust>0.8→verbatim, 0.5-0.8→summary, <0.5→slot_only/dropped
- Active contradiction pairs preserved regardless of trust (both sides kept)
- Provenance tracked: `observation_type` = "direct" | "survived_compaction"
- `compaction_generation` counter increments each pass
- Token budget enforced with epistemic priority ordering
- No LLM calls — rule-based compression from existing fact_tuples
- `render_belief_snapshot()` produces structured output with sections: high-confidence, active tensions, summary, compressed

**2. Compaction Decay Enforcement** (`personal_agent/compaction_decay.py`)
- Compaction is a trust-degrading event — memories that weren't preserved verbatim lose trust
- Decay factors: summary=0.05, slot_only=0.10, dropped=0.15
- Repeated compaction amplifies: `MULTIPLIER^(count-1)`, capped at 3x
- Tool-receipt and model-output source_kinds flagged for re-verification (review_after=now+24h)
- All changes logged to trust_log with reason="compaction_decay"
- Updates last_compacted, compaction_count, observation_type on memory records

**3. Memory Consolidation Pass** (`personal_agent/memory_consolidation.py`)
- Batch NLI contradiction sweep across ALL memories (not just store-time)
- O(n·k) via embedding nearest-neighbor pre-filter (k=10 neighbors, similarity>0.4)
- Disposition classification: resolvable→auto-deprecate weaker, held→BDG edge, evolving→temporal markers
- Auto-resolution only when evidence is overwhelming (lower trust AND older AND model_output vs principal)
- Updates belnap_state="both" for held contradictions
- Everything logged to contradiction ledger

### Schema Changes
- 3 new columns on `memories`: `last_compacted`, `compaction_count`, `observation_type`
- 2 new tables: `compaction_events` (audit trail), `compaction_provenance` (per-memory per-compaction)

### Integration Points
- `context_feed.py`: new `build_compacted_context()` function
- `idle_scheduler.py`: consolidation runs every 6h during idle
- `governance.py`: `govern_compaction()` — escalates if locked memory summarized or contradiction pair dropped
- `routes/compaction.py`: 3 endpoints (POST run compaction, POST run consolidation, GET history)
- `routes/register.py`: compaction_router registered

### Test Results
- Phase A (schema): 3 columns + 2 tables created correctly
- Phase B (compaction): 21 memories, trust tiering correct (locked=verbatim, high=verbatim, low=slot_only)
- Phase C (decay): 13 memories decayed, 11 flagged for reverification, trust_log entries correct
- Phase D (consolidation): 7 pairs checked, pipeline runs clean, NLI integration working
- Phase E (integration): routes registered, governance hook catches locked-memory violations

### Key Insight
**Why:** Claude Code has 6 compaction strategies, all epistemically blind. They lose provenance, trust scores, and contradiction topology through compression. This is CRT's #1 differentiator opportunity — compaction that knows what it lost.

### Context
Built after deep-diving Claude Code's leaked source. GPT's hard filter: "does this feature make the epistemic thesis more visible, more measurable, or more useful?" Compaction was the unanimous #1 priority.
