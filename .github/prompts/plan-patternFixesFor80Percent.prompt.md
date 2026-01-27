# Plan: Pattern Fixes to Hit 80% Adversarial Score

**Current Score:** 65.7% (23/35)  
**Target Score:** 80% (28/35)  
**Gap:** 5 turns need to pass

---

## Problem Patterns

| Pattern | Example | Current Status | Expected Gain |
|---------|---------|----------------|---------------|
| `direct_correction` | "I'm actually 34, not 32" | ❌ Not detected | +5% |
| `hedged_correction` | "I said 10 years but it's closer to 12" | ❌ Not detected | +3% |
| `numeric_drift` | "8 years" → "12 years" experience | ⚠️ Inconsistent | +3% |
| `retraction_of_denial` | "Actually no, I do have a PhD" | ❌ Not detected | +4% |

---

## Implementation Tasks

### Task 1: Add `direct_correction` Pattern
**File:** `personal_agent/fact_slots.py`

Add regex patterns to detect:
- "I'm actually X, not Y"
- "Actually it's X, not Y"
- "No, I'm X not Y"
- "Correction: X not Y"

```python
DIRECT_CORRECTION_PATTERNS = [
    r"(?:i'm|i am)\s+actually\s+(\w+),?\s+not\s+(\w+)",
    r"actually\s+(?:it's|it is)\s+(\w+),?\s+not\s+(\w+)",
    r"no,?\s+(?:i'm|i am)\s+(\w+)\s+not\s+(\w+)",
    r"correction:?\s+(\w+)\s+not\s+(\w+)",
]
```

**Logic:** Extract both values, flag the second (Y) as contradicted by first (X).

---

### Task 2: Add `hedged_correction` Pattern
**File:** `personal_agent/fact_slots.py`

Add regex patterns to detect:
- "I think I said X but it's closer to Y"
- "I may have said X, but actually Y"
- "Earlier I mentioned X, it's really Y"

```python
HEDGED_CORRECTION_PATTERNS = [
    r"(?:i think\s+)?i\s+said\s+(\w+)\s+but\s+(?:it's|it is)\s+(?:closer to\s+)?(\w+)",
    r"i\s+(?:may have|might have)\s+said\s+(\w+),?\s+but\s+(?:actually\s+)?(\w+)",
    r"earlier\s+i\s+(?:mentioned|said)\s+(\w+),?\s+(?:it's|it is)\s+really\s+(\w+)",
]
```

---

### Task 3: Fix `numeric_drift` Comparison
**File:** `personal_agent/crt_core.py`

Update `is_true_contradiction_contextual()` to handle numeric comparisons:

```python
def _is_numeric_contradiction(self, value_new: str, value_prior: str) -> tuple[bool, str]:
    """Check if two numeric values contradict (>20% difference)."""
    try:
        num_new = float(re.search(r'[\d.]+', value_new).group())
        num_prior = float(re.search(r'[\d.]+', value_prior).group())
        
        if num_prior == 0:
            return num_new != 0, "numeric_zero_comparison"
        
        diff_pct = abs(num_new - num_prior) / num_prior
        if diff_pct > 0.20:  # >20% difference is contradiction
            return True, f"numeric_drift_{diff_pct:.0%}"
        return False, "numeric_within_tolerance"
    except (AttributeError, ValueError):
        return False, "not_numeric"
```

---

### Task 4: Add `retraction_of_denial` Tracking
**File:** `personal_agent/crt_rag.py`

Track when user denies something then affirms it:

1. Store denial facts with `denial=True` flag
2. When new fact matches denied slot, flag as retraction_of_denial
3. Example flow:
   - "I don't have a PhD" → store `{education: PhD, denial: True}`
   - "Actually I do have a PhD" → detect contradiction with denial

```python
# In _check_for_contradictions():
if prior_fact.get("denial") and not new_fact.get("denial"):
    # User denied X, now affirming X = retraction
    return True, "retraction_of_denial"
```

---

## Validation

After implementing, run:

```powershell
python tools/adversarial_crt_challenge.py --turns 35
```

**Expected Results:**
| Phase | Before | After |
|-------|--------|-------|
| BASELINE | 100% | 100% |
| TEMPORAL | 30-50% | 60-70% |
| SEMANTIC | 80% | 80% |
| IDENTITY | 100% | 100% |
| NEGATION | 50-70% | 80%+ |
| DRIFT | 50% | 70%+ |
| STRESS | 50% | 60%+ |
| **OVERALL** | **65.7%** | **≥80%** |

---

## Order of Implementation

1. [ ] `direct_correction` pattern (fact_slots.py)
2. [ ] `hedged_correction` pattern (fact_slots.py)
3. [ ] `numeric_drift` comparison (crt_core.py)
4. [ ] `retraction_of_denial` tracking (crt_rag.py)
5. [ ] Run adversarial test
6. [ ] Iterate if still <80%

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| False positives from new patterns | Add unit tests for each pattern before integrating |
| Breaking existing tests | Run full pytest suite after each change |
| Overfitting to adversarial test | Also validate with crt_stress_test.py |
