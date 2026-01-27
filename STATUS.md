# Project Status

**Last Updated:** 2026-01-27  
**Current Phase:** Pattern Fixes (Path to 80%)

---

## Recent Completions

| Phase | Description | Date |
|-------|-------------|------|
| ✅ Phase 1 | Self-questioning, caveat injection, feature flags | 2026-01-26 |
| ✅ Phase 1.1 | Wired CRTMath call sites, fixed paraphrase detection | 2026-01-26 |
| ✅ Phase 2.0 | Context-Aware Memory (domain/temporal detection) | 2026-01-26 |
| ✅ Phase 2.4 | Denial detection (Turn 23 working) | 2026-01-27 |

---

## Current Testing Metrics (2026-01-27)

| Test | Score | Target | Status |
|------|-------|--------|--------|
| **adversarial_crt_challenge.py** | **77.1% (27/35)** | 80% | ⚠️ 2.9% away |
| **crt_stress_test.py** | 91.7% eval, 80% detection | 90%+ | ✅ PASSING |
| **False Positives** | 0 | 0 | ✅ PASSING |
| **Caveat Violations** | 1 | ≤2 | ✅ PASSING |

### Adversarial Challenge Phase Breakdown

| Phase | Score | Notes |
|-------|-------|-------|
| BASELINE | 100% (5/5) | ✅ Perfect |
| TEMPORAL | 70% (3.5/5) | ⚠️ Improved |
| SEMANTIC | 80% (4/5) | ✅ Good |
| IDENTITY | 100% (5/5) | ✅ Perfect |
| NEGATION | 90% (4.5/5) | ✅ Good |
| DRIFT | 50% (2.5/5) | ❌ Needs work |
| STRESS | 50% (2.5/5) | ❌ Needs work |

---

## Progress Timeline

| Date | Score | Change | Key Fix |
|------|-------|--------|---------|
| Start | 65.7% (23/35) | — | Baseline |
| 2026-01-26 | 71.4% (25/35) | +5.7% | Direct/hedged corrections, numeric drift |
| **2026-01-27** | **77.1% (27/35)** | **+5.7%** | **Denial detection, retraction logic** |

---

## Known Issues

| Issue | Status | Notes |
|-------|--------|-------|
| `ContradictionType.DENIAL` missing | ❌ | Enum constant doesn't exist, causes AttributeError |
| Turn 13 numeric (8 vs 12 years) | ⚠️ | Inconsistent detection |
| DRIFT phase (50%) | ❌ | Gradual value shifts not detected |
| STRESS phase (50%) | ❌ | Rapid-fire contradictions need tuning |

---

## Next Actions (to hit 80%)

1. [ ] Add `ContradictionType.DENIAL` to enum in crt_ledger.py
2. [ ] Debug Turn 24 retraction in full test context
3. [ ] Improve DRIFT phase detection (+1 turn needed)
4. [ ] Target: 80% = 28/35 turns

---

## Phase Roadmap

```
✅ Phase 1      Self-questioning, caveat injection, feature flags
✅ Phase 1.1    Wire up CRTMath call sites  
✅ Phase 2.0    Context-Aware Memory (domain/temporal)
✅ Phase 2.4    Denial detection
⏳ Current      Pattern fixes to hit 80%
📋 Phase 1.2    Advanced Testing Suite (after 80%)
📋 Phase 2      UX Enhancements
📋 Phase 3      Vector-store-per-fact
```

---

## Quick Validation Commands

```powershell
# Adversarial test (primary)
python tools/adversarial_crt_challenge.py --turns 35

# Full stress test (requires Ollama)
python tools/crt_stress_test.py --turns 30

# Pytest suite
python -m pytest tests/ -v --tb=short
```

---

## Key Artifacts

| File | Purpose |
|------|---------|
| `artifacts/TEST_RESULTS_2026-01-27.md` | Latest test run summary |
| `artifacts/adversarial_challenge_20260127_*.json` | Raw adversarial results |
| `artifacts/crt_stress_run.20260127_*.jsonl` | Raw stress test results |
| `.github/prompts/_project-context.prompt.md` | AI agent context file |
