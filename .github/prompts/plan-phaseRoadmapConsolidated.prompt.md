# CRT-GroundCheck-SSE Phase Roadmap

**Last Updated:** 2026-01-27  
**Current Score:** 77.1% (27/35) adversarial, 91.7% stress test  
**Target:** 80% adversarial (28/35)

---

## Phase Overview

```
Phase 1:    Core Infrastructure                    ✅ COMPLETE
Phase 2:    Context & Intelligence                 ⏳ 77.1% → 80%
Phase 3:    Advanced Testing                       📋 PLANNED
Phase 4:    UX & Polish                            📋 PLANNED
Phase 5:    Experimental                           📋 PLANNED
```

---

## Phase 1: Core Infrastructure ✅ COMPLETE

| Sub-Phase | Description | Status |
|-----------|-------------|--------|
| 1.0 | Self-questioning, caveat injection, feature flags | ✅ Done |
| 1.1 | Wire up CRTMath call sites | ✅ Done |
| 1.2 | Negation detection | ✅ Done |
| 1.3 | Pattern fixes (direct/hedged corrections, numeric drift) | ✅ Done |

**Artifacts:** `plan-fixContradictionDetection.prompt.md`, `plan-phase12NegationDetection.prompt.md`, `plan-patternFixesFor80Percent.prompt.md`

---

## Phase 2: Context & Intelligence ⏳ IN PROGRESS

| Sub-Phase | Description | Status |
|-----------|-------------|--------|
| 2.0 | Context-Aware Memory (domain/temporal detection) | ✅ Done |
| 2.1 | Denial detection (Turn 23) | ✅ Done |
| 2.2 | Retraction detection (Turn 24) | ⚠️ Needs enum fix |
| 2.3 | Hit 80% adversarial target | ⏳ 77.1% → 80% |

### Immediate Tasks (2.2-2.3)

| Priority | Task | File | Expected Gain |
|----------|------|------|---------------|
| 1 | Add `ContradictionType.DENIAL` to enum | `crt_ledger.py` | Unblocks denial path |
| 2 | Debug Turn 24 retraction in full test | `crt_rag.py` | +1 turn |
| 3 | Improve DRIFT phase detection | `crt_core.py` | +1 turn |

**Target:** 80% = 28/35 turns (+1 from current)

**Artifacts:** `plan-phase20ContextAwareMemory.prompt.md`, `plan-turn23Turn24UnknownTurnImplementation.prompt.md`

---

## Phase 3: Advanced Testing 📋 PLANNED

| Sub-Phase | Description | Effort |
|-----------|-------------|--------|
| 3.0 | Test criteria taxonomy (TP/FP/TN/FN, F1 scores) | Small |
| 3.1 | Adversarial test agent (LLM-powered dynamic challenges) | Medium |
| 3.2 | Paragraph tests with buried contradictions | Medium |
| 3.3 | Stress test mode flags (`--mode hardcoded/adversarial/paragraph/full`) | Small |

**Entry Criteria:** 80% adversarial score achieved  
**Exit Criteria:** 80% adversarial pass rate, 70% paragraph pass rate

---

## Phase 4: UX & Polish 📋 PLANNED

| Sub-Phase | Description | Effort |
|-----------|-------------|--------|
| 4.0 | Emotion signals for SSE mode selection (gating only) | Small |
| 4.1 | Humble wrapper (policy-clean uncertainty phrases) | Small |
| 4.2 | Conversation windowing (`max_turns=5` for token optimization) | Medium |

**Entry Criteria:** Phase 3 complete  
**Dependencies:** None critical

---

## Phase 5: Experimental 📋 PLANNED

| Sub-Phase | Description | Effort |
|-----------|-------------|--------|
| 5.0 | Vector-store-per-fact (multi-dimensional vectors) | Large |
| 5.1 | Vector migration (convert existing memories) | Medium |
| 5.2 | Cognitive router (graph-based, only if specialists emerge) | Large |

**Entry Criteria:** Phases 1-4 stable  
**Risk:** May require significant refactoring

---

## Current Test Results (2026-01-27)

### Adversarial Challenge (77.1%)

| Phase | Score | Status |
|-------|-------|--------|
| BASELINE | 100% (5/5) | ✅ Perfect |
| TEMPORAL | 70% (3.5/5) | ⚠️ Improved |
| SEMANTIC | 80% (4/5) | ✅ Good |
| IDENTITY | 100% (5/5) | ✅ Perfect |
| NEGATION | 90% (4.5/5) | ✅ Good |
| DRIFT | 50% (2.5/5) | ❌ Needs work |
| STRESS | 50% (2.5/5) | ❌ Needs work |

### Stress Test (91.7%)

| Metric | Value |
|--------|-------|
| Gates Passed | 86.7% |
| Contradiction Detection | 80% (4/5) |
| False Positives | 0 |
| Caveat Violations | 1 |

---

## Known Issues

| Issue | Phase | Status |
|-------|-------|--------|
| `ContradictionType.DENIAL` missing | 2.2 | ❌ Blocks full denial path |
| Turn 13 numeric (8 vs 12 years) | 2.3 | ⚠️ Inconsistent |
| DRIFT phase (50%) | 2.3 | ❌ Gradual shifts not detected |
| STRESS phase (50%) | 2.3 | ❌ Rapid-fire needs tuning |

---

## Prompt File Cleanup

### Keep (Active)
- `_project-context.prompt.md` — Update with 77.1% score
- `plan-phaseRoadmapConsolidated.prompt.md` — This file (new)

### Archive (Completed)
- `plan-fixContradictionDetection.prompt.md`
- `plan-phase12NegationDetection.prompt.md`
- `plan-phase20ContextAwareMemory.prompt.md`
- `plan-patternFixesFor80Percent.prompt.md`
- `plan-turn23Turn24UnknownTurnImplementation.prompt.md`

---

## Quick Commands

```powershell
# Adversarial test (primary validation)
python tools/adversarial_crt_challenge.py --turns 35

# Stress test (requires Ollama)
python tools/crt_stress_test.py --turns 30

# Pytest suite
python -m pytest tests/ -v --tb=short
```
