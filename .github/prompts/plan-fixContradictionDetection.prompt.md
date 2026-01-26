# Plan: Fix Contradiction Detection Rate (20% → 100%)

The current system over-suppresses contradictions via the paraphrase gate and high drift threshold. The patch needs to catch numeric, entity swap, and boolean flip contradictions without reintroducing false positives.

## Current State

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| Contradiction Detection | 100% (5/5) | 20% (1/5) | ❌ 4 missed |
| Caveat Violations | ≤2 | 0 | ✅ Passed |

### What Was Detected
- Turn 11: "Microsoft vs Amazon" — explicit negation ("not Microsoft") triggered detection

### What Was Missed
| Turn | Contradiction | Root Cause |
|------|---------------|------------|
| 13 | "8 years vs 12 years" (numeric) | Paraphrase gate: numbers overlap as "key elements" |
| 23 | "8 years vs 10 years since college" (temporal inference) | Temporal inference not detected |
| 25 | "Stanford vs MIT for undergrad" (entity swap) | No explicit negation; classified as REFINEMENT |
| 28 | "Remote preference vs office preference" (boolean flip) | Moderate drift falls in paraphrase zone |

## Steps

### Step 1: Lower `theta_contra` threshold
**File:** `groundcheck/crt_math.py`
**Change:** `theta_contra: float = 0.42` → `theta_contra: float = 0.28`
**Rationale:** Catch moderate-drift contradictions that are currently being missed

### Step 2: Fix numeric comparison in `_is_likely_paraphrase()`
**File:** `groundcheck/crt_math.py`
**Change:** Add explicit numeric mismatch check — different numbers (8 vs 12) should NOT be treated as overlapping key elements
**Current problem:**
```python
def extract_key_elements(text):
    numbers = set(re.findall(r'\d+', text))  # extracts 8, 12
    # ...
    overlap = len(keys_new & keys_prior) / max(len(keys_new | keys_prior), 1)
    if overlap > 0.7:
        return True  # SUPPRESSES contradiction
```
**Fix needed:** If numbers differ, return False immediately (not a paraphrase)

### Step 3: Narrow the paraphrase drift range
**File:** `groundcheck/crt_math.py`
**Change:** Drift range from `0.25-0.55` to `0.35-0.50`
**Rationale:** More contradictions escape the paraphrase gate; only truly similar texts get suppressed

### Step 4: Add entity swap detection
**File:** `groundcheck/crt_math.py` or `groundcheck/reasoning.py`
**Change:** When same slot (e.g., `undergrad_school`) has different named entity values without explicit negation, flag as contradiction
**Pattern:** slot match + value mismatch + both values are proper nouns → contradiction

### Step 5: Add boolean/preference inversion detection
**File:** `groundcheck/crt_math.py`
**Change:** Pattern match for preference inversions:
- "prefer X" vs "prefer Y" where X ≠ Y → contradiction
- "prefer X" vs "hate X" → contradiction
- "like X" vs "dislike X" → contradiction

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| False positives returning | Keep paraphrase gate but make it smarter — only suppress true synonyms |
| ML model mismatch | May need to update XGBoost classifier training data |
| Breaking existing tests | Run full stress test after each step |

## Execution Strategy

1. **Apply Step 1 first** (threshold change) — re-run stress test
2. **If detection < 80%**, apply Steps 2-3 (paraphrase fixes)
3. **If detection < 100%**, apply Steps 4-5 (entity/boolean detection)
4. **Verify caveat violations stay at 0** after each change

## Files to Modify

- `groundcheck/crt_math.py` — Steps 1, 2, 3, 5
- `groundcheck/reasoning.py` — Step 4 (optional, if slot-based detection needed)
- `groundcheck/ml_contradiction_detector.py` — Optional retraining

## Success Criteria

- [ ] Contradiction detection rate: 100% (5/5)
- [ ] Caveat violations: ≤2
- [ ] No regression in eval pass rate (currently 91.7%)
- [ ] Reintroduction invariant maintained
