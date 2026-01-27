# Project Status

**Last Updated:** 2026-01-26  
**Current Phase:** 1.2 (Advanced Testing Suite)

---

## Recent Completions

| Phase | Description | Date |
|-------|-------------|------|
| ✅ Phase 1 | Self-questioning, caveat injection, feature flags | 2026-01-26 |
| ✅ Phase 1.1 | Wired CRTMath call sites, fixed paraphrase detection | 2026-01-26 |
| ✅ Phase 2.0 | Context-Aware Memory (domain/temporal detection) | 2026-01-26 |

---

## Current Testing Metrics

| Test | Score | Target | Status |
|------|-------|--------|--------|
| **crt_stress_test.py** | 91.7% eval, 80% detection | 90%+ | ✅ PASSING |
| **adversarial_crt_challenge.py** | 65.7% (23/35) | 80% | ❌ NOT PASSING |
| **False Positives** | 0 | 0 | ✅ PASSING |
| **Caveat Violations** | 0 | ≤2 | ✅ PASSING |

### Adversarial Challenge Phase Breakdown

| Phase | Score | Notes |
|-------|-------|-------|
| BASELINE | 100% (5/5) | ✅ Perfect |
| TEMPORAL | 30-50% | ⚠️ Needs work |
| SEMANTIC | 80% (4/5) | ✅ Good |
| IDENTITY | 100% (5/5) | ✅ Perfect |
| NEGATION | 50-70% | ⚠️ Inconsistent |
| DRIFT | 50% | ⚠️ Manual eval |
| STRESS | 50% | ⚠️ Manual eval |

---

## Known Issues

| Pattern | Example | Status |
|---------|---------|--------|
| `direct_correction` | "I'm actually 34, not 32" | ❌ Not caught |
| `hedged_correction` | "I think I said 10 years but it's closer to 12" | ❌ Not caught |
| `retraction_of_denial` | PhD → Master's → PhD reversion | ❌ Not caught |
| Numeric contradictions | "8 years vs 12 years" | ⚠️ Inconsistent |

---

## Phase Roadmap

```
✅ Phase 1      Self-questioning, caveat injection, feature flags
✅ Phase 1.1    Wire up CRTMath call sites  
✅ Phase 2.0    Context-Aware Memory (domain/temporal)
📋 Phase 1.2    Advanced Testing Suite (adversarial agent, paragraph tests)
📋 Phase 2      UX Enhancements (emotion signals, humble wrapper)
📋 Phase 3      Vector-store-per-fact (experimental)
```

---

## Next Actions

1. [ ] Add `direct_correction` detection rules to fact_slots.py
2. [ ] Add `hedged_correction` detection rules
3. [ ] Build `adversarial_test_agent.py` for dynamic challenges
4. [ ] Add paragraph test scenarios with buried contradictions
5. [ ] Target: 80% adversarial challenge pass rate

---

## Quick Validation Commands

```powershell
# Primary adversarial test (no Ollama required)
python tools/adversarial_crt_challenge.py --turns 35

# Full stress test (requires Ollama)
python tools/crt_stress_test.py --turns 30

# Run all pytest tests
python -m pytest tests/ -v --tb=short
```

---

## Key Files Modified Recently

| File | Change | Date |
|------|--------|------|
| `personal_agent/domain_detector.py` | NEW - domain detection module | 2026-01-26 |
| `personal_agent/fact_slots.py` | Added temporal/domain extraction | 2026-01-26 |
| `personal_agent/crt_memory.py` | Added temporal/domain columns | 2026-01-26 |
| `personal_agent/crt_core.py` | Added `is_true_contradiction_contextual()` | 2026-01-26 |
| `personal_agent/crt_rag.py` | Added domain-aware retrieval, bug fix for None contradiction_entry | 2026-01-26 |
| `personal_agent/reasoning.py` | Fixed unicode emoji crash | 2026-01-26 |
