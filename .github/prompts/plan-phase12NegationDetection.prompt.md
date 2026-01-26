# Phase 1.2: Add Negation Detection

## Assessment: Phase 1.1 Progress

| Metric | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| **Contradiction Detection** | 20% (1/5) | 57% (4/7) | 100% | 🟡 Improved but not complete |
| **False Positives** | 0 | 0 | 0 | ✅ Maintained |
| **Caveat Violations** | 0 | 0 | ≤2 | ✅ Maintained |

## What's Working

1. **Numeric mismatch check** — Programming years 10→12 caught (Turn 9)
2. **Entity swap detection** — Employer Google contradiction caught (Turn 22)
3. **Preference inversion** — PhD→Master's denial caught (Turn 23)
4. **Paraphrase gate tightening** — No false positives

## What's Still Missing (3 Cases)

| Turn | Input | Issue | Root Cause |
|------|-------|-------|------------|
| **7** | "I'm actually 34, not 32" | Age numeric contradiction | Input contains BOTH values — fact extraction sees "34" as new, but contradiction check may not find the old "32" memory |
| **21** | "I don't work at Google anymore" | Negation-based contradiction | No negation detection — "don't work at X" vs "work at X" isn't caught |
| **24** | Master's vs PhD retraction | Degree entity swap | Fact slot comparison may not be wired correctly for `education_level` |

---

## Fix Plan

### Priority 1: Add Negation Detection
**File:** `personal_agent/crt_core.py`
**Location:** After `_is_boolean_inversion` method (around line 650)

The biggest gap. "I don't work at Google" vs "I work at Google" should trigger.

```python
def _detect_negation_contradiction(self, text_new: str, text_prior: str) -> Tuple[bool, str]:
    """
    Detect negation-based contradictions.
    
    Patterns:
    - "I don't X" vs "I X"
    - "I no longer X" vs "I X"
    - "not X anymore" vs "X"
    """
    if not text_new or not text_prior:
        return False, ""
    
    text_new_lower = text_new.lower()
    text_prior_lower = text_prior.lower()
    
    # Negation patterns
    negation_patterns = [
        (r"(?:i\s+)?(?:don'?t|do\s+not|no\s+longer|not\s+anymore)\s+(\w+(?:\s+\w+){0,3})", "negated"),
        (r"(?:i\s+)?(?:stopped|quit|left|no\s+longer)\s+(\w+(?:\s+\w+){0,3})", "ceased"),
        (r"(?:i'm\s+not|i\s+am\s+not)\s+(\w+(?:\s+\w+){0,3})", "negated_state"),
    ]
    
    # Extract negated actions/states from new text
    negated_items = []
    for pattern, neg_type in negation_patterns:
        for match in re.finditer(pattern, text_new_lower):
            negated_items.append((match.group(1).strip(), neg_type))
    
    if not negated_items:
        return False, ""
    
    # Check if prior text affirms any of the negated items
    for item, neg_type in negated_items:
        # Clean item for matching
        item_words = item.split()[:3]  # First 3 words
        item_pattern = r'\b' + r'\s+'.join(re.escape(w) for w in item_words) + r'\b'
        
        # Check if prior affirms this (without negation)
        if re.search(item_pattern, text_prior_lower):
            # Verify prior doesn't also negate it
            prior_negated = any(
                re.search(p[0], text_prior_lower) 
                for p in negation_patterns
            )
            if not prior_negated:
                return True, f"Negation contradiction: '{item}' negated in new, affirmed in prior"
    
    return False, ""
```

### Priority 2: Wire Negation Check into detect_contradiction
**File:** `personal_agent/crt_core.py`
**Location:** In `detect_contradiction` method, after entity swap check (around line 520)

```python
# ...existing code...
# Rule 0a: Entity swap detection
entity_swap, entity_reason = self._detect_entity_swap(slot, value_new, value_prior, text_new, text_prior)
if entity_swap:
    return True, entity_reason

# Rule 0b: Negation contradiction detection
negation_detected, negation_reason = self._detect_negation_contradiction(text_new, text_prior)
if negation_detected:
    return True, negation_reason

# Rule 0c: Preference/boolean inversion detection
# ...existing code...
```

### Priority 3: Fix Fact Slot Wiring for Education
**File:** `personal_agent/crt_rag.py`
**Task:** Verify `education_level` slot changes pass proper `slot`, `value_new`, `value_prior` parameters to contradiction detection

---

## Execution Strategy

1. **Apply Priority 1 & 2** — negation detection is the biggest gap
2. **Re-run stress test** to measure improvement
3. **If still <80%**, investigate fact extraction layer for Turn 7 (age) and Turn 24 (education)

## Success Criteria

- [ ] Contradiction detection rate: ≥80% (target 100%)
- [ ] False positives: 0
- [ ] Caveat violations: ≤2
- [ ] Turn 21 negation ("don't work at Google") detected
