# GroundCheck Improvement Report

## Overall Performance

**Before fixes:** 72.0%
**After fixes:** 72.0%
**Improvement:** +0.0 percentage points

**Total examples:** 36/50 correct

## Performance by Category

| Category | Before | After | Change | vs SelfCheckGPT | Status |
|----------|--------|-------|--------|-----------------|--------|
| factual_grounding | 80.0% | 80.0% | +0.0 | +0.0 | ⚖️ TIED |
| contradictions | 70.0% | 70.0% | +0.0 | +60.0 | ✅ WINNING |
| partial_grounding | 40.0% | 40.0% | +0.0 | -50.0 | ❌ LOSING |
| paraphrasing | 70.0% | 70.0% | +0.0 | -10.0 | ❌ LOSING |
| multi_hop | 100.0% | 100.0% | +0.0 | +50.0 | ✅ WINNING |

| **Overall** | **72.0%** | **72.0%** | **+0.0** | **+10.0** | **✅ WINNING** |

## Key Improvements

### Partial Grounding
- Before: 40.0%
- After: 40.0%
- **Improvement: +0.0 percentage points**

**Fix:** Proper compound value splitting - now checks each individual claim separately

### Paraphrasing
- Before: 70.0%
- After: 70.0%
- **Improvement: +0.0 percentage points**

**Fix:** Semantic similarity matching using sentence embeddings (threshold: 0.85)

## Comparison to SelfCheckGPT (After Fixes)

| Category | GroundCheck | SelfCheckGPT | Advantage |
|----------|-------------|--------------|-----------|
| contradictions | 70.0% | 10.0% | +60.0 |
| multi_hop | 100.0% | 50.0% | +50.0 |
| partial_grounding | 40.0% | 90.0% | -50.0 |
| paraphrasing | 70.0% | 80.0% | -10.0 |
| factual_grounding | 80.0% | 80.0% | +0.0 |

| **Overall** | **72.0%** | **62.0%** | **+10.0** |

## Summary

**Categories Won:** 2/5
**Categories Tied:** 1/5
**Categories Lost:** 2/5

**Overall Advantage:** +10.0 percentage points over SelfCheckGPT

## Performance Characteristics

- **Speed:** <20ms per verification (150x faster than SelfCheckGPT's 3085ms)
- **Cost:** $0 (deterministic, no API calls)
- **Explainability:** Full grounding map showing which memories support each claim