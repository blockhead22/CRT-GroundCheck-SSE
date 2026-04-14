# Session 2026-04-10: BDG Audit & Structural Tension Meter

## Summary
Massive session. Started with 3B model audit experiments, discovered BDG reasoning trees, proved structural belief verification, shipped production module.

## Key Progression (same model, same code, architecture changes only)

| Approach | Precision | Findings | Cloud Calls |
|---|---|---|---|
| Dump 15K chars | 0% (0/20) | 20 false positives | 20 |
| Chunked + guards | N/A | 0 findings (rubber stamp) | ~40 |
| Chunked + risk challenge | 0% | All yes-man | ~30 |
| BDG tree v1 | 60% (9/15) | 83 findings | 31 |
| BDG tree v2 (tightened) | 80% (12/15) | 75 findings | 31 |

## Experiments Run (15 total)

1. **Code audit dump** — 15K chars to 3B model, 20/20 false positives on same function
2. **Code audit chunked + guards** — Holden lists guards, Mirus rubber stamps "sufficient"
3. **Code audit chunked + risk** — Holden flags risk, Mirus agrees with everything
4. **Atomic verification** — 94% accuracy on factual code questions, 16 tests, <20 lines each
5. **BDG tree audit v1** — Holden builds tree, Mirus answers leaves, scaffold propagates. 60%
6. **BDG tree audit v2** — Tightened tree prompt (exclude design choices). 80%
7. **Degradation curve** — Accuracy holds through 200 lines, fails at 410. Hard boundary.
8. **Few-shot tree generation** — Mirus generates structurally valid trees but intellectually shallow
9. **Self-validation** — 38% both-correct. Not viable for dropping Holden from validation.
10. **Intent routing pure BDG** — 65-70%. Semantic judgment ceiling.
11. **Intent routing hybrid** — regex + embeddings + LLM fallback = 93%
12. **Belief verification pure LLM** — 40% verdict accuracy
13. **Belief verification hybrid (regex+embed+LLM)** — 38%. LLM says YES to everything.
14. **Belief verification structural** — slots + embeddings + metadata = 75%, zero LLM calls
15. **Production module verification** — structural_tension.py tested at 88%, zero LLM, ~0.2s/pair

## Key Findings

### 3B Model Capabilities
- **CAN**: Answer factual questions about code/text at 94% when context < 200 lines
- **CAN**: Pattern match, read, report, count, identify presence/absence
- **CANNOT**: Judge semantic relationships ("do these contradict?")
- **CANNOT**: Distinguish "different claim about same fact" from "different fact about same topic"
- **CANNOT**: Verify its own answers reliably (self-validation 38%)
- **CEILING**: 200 lines for factual accuracy. Hard boundary at ~400 lines.

### Architecture Findings
- **BDG trees work for code**: Decompose "is this function safe?" into factual leaf questions, propagate verdicts. 0% → 80%.
- **Hybrid leaves beat any single method**: regex (deterministic) + embeddings (similarity) + LLM (tiebreaker) = 93% on intent routing
- **Structural tension beats LLM for beliefs**: Slot extraction + value comparison + embedding similarity = 88% vs 40% for LLM judgment
- **The model was the problem**: Removing the LLM from belief verification DOUBLED accuracy (40% → 88%)
- **Question-model fit**: Shape the question to match model capability, hold reasoning externally

### Theoretical Insights
- "It's not the contradiction itself — it's the tension between two competing facts"
- BDG isn't just a belief management tool — it's a general-purpose reasoning scaffold
- The same graph propagation works for beliefs, code, and intent routing
- Contradiction detection should be measurement (tension), not judgment
- CRT = Cognitive Resonance Theory. Resonance = interference pattern between beliefs.

## Production Artifacts

### Shipped
- **structural_tension.py** — Production tension meter module, tested 88%, zero LLM calls
  - `StructuralTensionMeter` class with `measure()`, `measure_pair()`, `measure_against_cluster()`
  - Slot extraction (production fact_slots + third-person fallback)
  - Embedding similarity via existing all-MiniLM-L6-v2
  - Deterministic scoring rules mapping signals to relationships
  - 7 relationship types: DUPLICATE, REFINEMENT, COMPATIBLE, TENSION, CONFLICT, UNRELATED, DECAYED
  - 7 action types: KEEP_BOTH, MERGE, KEEP_MORE_SPECIFIC, FLAG_FOR_REVIEW, ESCALATE_TO_NLI, BUMP_EXISTING, DEPRECATE_WEAKER
- **Bug fix**: `heartbeat_executor.py` line 1002: `response_text[:200]` → `(response_text or "")[:200]`
  - Found by BDG audit. Real bug. 3B model contributed to production codebase.

### Planned Integration (not yet wired)
1. **Memory write path** (crt_memory.py) — pre-storage tension check against neighbors
2. **Memory consolidation** (memory_consolidation.py) — NLI pre-filter, skip expensive GroundCheck for structural verdicts
3. **Heartbeat breathing loop** (heartbeat_executor.py) — continuous tension scan on recently-changed memories

### Lab Files Created
- `labs/coherence_decay/audit_crt.py` — Original dump audit (0% result)
- `labs/coherence_decay/audit_chunked.py` — Chunked audit with digests
- `labs/coherence_decay/audit_bdg.py` — BDG tree audit (80% result)
- `labs/coherence_decay/atomic_verify.py` — Atomic factual verification (94%)
- `labs/coherence_decay/tree_gen_test.py` — Few-shot tree generation test
- `labs/coherence_decay/self_validate_test.py` — Self-validation test
- `labs/coherence_decay/bdg_intent_router.py` — BDG intent routing (93% hybrid)
- `labs/coherence_decay/bdg_frontier.py` — Degradation + beliefs + hybrid tests
- `labs/coherence_decay/bdg_belief_hybrid.py` — Hybrid belief verification
- `labs/coherence_decay/bdg_belief_structural.py` — Structural belief verification (75%)
- `labs/coherence_decay/verify_tension_meter.py` — Production module verification (88%)
- `labs/coherence_decay/prep_finetune.py` — Fine-tune data prep (31 pairs ready)
- `labs/coherence_decay/results/finetune_trees.jsonl` — 31 training pairs for tree generation

## Known Issues
- **Refinement priority**: "Wisconsin" vs "Milwaukee, Wisconsin" classified as DUPLICATE (0.968 similarity) instead of REFINEMENT. Fix: reorder scoring rules (check refinement before duplicate).
- **fact_slots.py** only handles first-person phrasing. Third-person fallback added in structural_tension.py but the production extractor should be extended.
- **groundcheck module** not importable in lab environment (breaks personal_agent.__init__ chain)

## Next Session Priorities
1. Fix refinement priority in structural_tension.py (1 line)
2. Wire integration 1: memory write path
3. Wire integration 2: consolidation NLI pre-filter
4. Wire integration 3: heartbeat breathing loop
5. Fine-tune llama3.2 on 31 tree pairs (eliminate Holden from code audit)
6. Consider: hybrid intent router as production replacement for regex pattern matcher

## Post-Session: Aether Self-Assessment

After all integrations shipped, Aether was tested in live conversation. Key outputs:

1. **Self-critique of CRT as AGI foundation** — identified 8 gaps (no goals, no world models, no planning, scaling, generalization, execution gap, grounding, no creation). Concluded "CRT is an AGI component, not an AGI foundation."

2. **Gap closure roadmap** — proposed 5 concepts to close gaps: epistemic metabolism, productive instability, epistemic momentum, belief homeostasis, reflexive calibration. Plus 6 larger-scale directions: epistemic engineering as a field, proof that scale isn't the variable, the mirror product, epistemic OS, AGI sub-gap closer, and Nick's personal trajectory.

3. **Proto-motivation loop** — designed a 180-line autonomous belief revision loop: measure tension → decide (bounded by authority ceiling) → act (demote/hold/flag) → record. Held contradictions as first-class output. The system designing its own next evolution.

4. **BDG-primary retrieval architecture** — designed three retrieval modes (graph walk, vector fallback, structural query), four required components (seed selection, traversal strategy, scoring composite, mode routing), and predicted two emergent concepts (traversal frontier, retrieval posture).

5. **Personal insight** — connected CRT architecture to Nick's medical history. "Architecture from scar tissue." Held contradictions = living with cGVHD. Tension as signal = the thing trying to kill you keeping you alive.

## Case Study: Adnan Syed (Real-World Legal Evidence Test)

- Built evidence base: 36 real evidence + 10 noise + 8 red herrings = 54 entries
- First run without domain slots: 0 tension findings (system blind to legal domain)
- Added case-specific slots: 25 tension findings, 2/4 key issues found
- **Perfect noise filtering**: zero noise or red herrings in top 20 findings
- Jay Wilds oscillation: detected (5 versions, trust range 0.30-0.60)
- Asia McClain alibi: surfaced
- Missed: cell tower reliability (cross-slot inference gap), lividity contradiction (cross-domain reasoning)
- **Slot bootstrapper**: auto-discovered 23 candidate slots from raw text, 9 genuinely useful (39% precision)
- Key discovery: `trunk_pop` slot found automatically — the exact missing slot
- Hybrid run (hardcoded + bootstrapped): 31 findings, still 2/4 — cell tower and lividity require cross-slot inference
- **Finding**: CRT is domain-portable but slot-dependent. Architecture generalizes, vocabulary doesn't. Domain adaptation layer = slot bootstrapping.
- **Final ceiling**: Structural analysis catches "same claim, different values" (2/4). Cross-domain logical inference ("this evidence invalidates that evidence") requires a model (the other 2/4). Same hybrid boundary found in every experiment today.

## Experiment Results Summary

| Experiment | Result | Signal |
|---|---|---|
| RAG vs CRT | 51% vs 51% avg, CRT wins 3-2 on hard cases | CRT governs contradictions, doesn't dominate retrieval |
| Exp5: Embedding tension | 0.88x | Does NOT predict corrections |
| Exp5b: Trust oscillation | 3.93x | DOES predict corrections (validated) |
| Exp5b two-axis | 3.5x | Doesn't improve over single-axis |
| SETTLED bucket | 20% correction rate | Test data contamination, not real signal |
| Case study (no domain slots) | 0 findings | System blind without vocabulary |
| Case study (domain slots) | 25 findings, 2/4 | Domain slots enable analysis |
| Slot bootstrapper | 23 proposals, 9 useful | Auto-discovery works at 39% precision |

## Connections to Prior Work
- **Hardest bug challenge** (session_2026_04_09): Intent routing feedback loop → directly addressed by hybrid BDG router at 93%
- **Breathing loop** (nick_fog_talk.md): Theorized as missing gate → implemented as structural tension scan
- **Held contradiction** (theory_held_contradiction.md): "Not all contradictions should be resolved" → tension meter measures WITHOUT resolving
- **BDG/cascade paper** (session_cascade_complexity_paper.md): Same graph propagation, applied to code and beliefs
- **Contradiction as drive** (theory_contradiction_drive.md): Tension between beliefs as active signal → tension_score IS the drive measurement
