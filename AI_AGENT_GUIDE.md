# AI Agent Continuation Guide

**For:** Future AI agents working on CRT contradiction detection  
**Date:** 2026-01-26  
**Current Score:** 71.4% (25/35 turns)  
**Target:** 80% (28/35 turns) 

---

## Quick Start for New Agents

### 1. Understand the Problem
- **Goal:** Detect contradictions in user statements about personal facts
- **Test:** 35-turn adversarial challenge with increasing difficulty
- **Metric:** Turn-by-turn accuracy (1.0 = detected, 0.0 = missed, 0.5 = manual eval)
- **Current state:** 71.4% accuracy, need 3 more turns for 80%

### 2. Understand What Works (Don't Break It)
These are **PASSING** and should not be changed:
- ✅ **BASELINE phase:** 100% - User establishes basic facts
- ✅ **IDENTITY phase:** 100% - Handles third-party references correctly
- ✅ **SEMANTIC phase:** 80% - Handles synonyms and detail additions
- ✅ **Direct corrections:** Implemented Jan 26 - "I'm actually X, not Y"
- ✅ **Hedged corrections:** Implemented Jan 26 - "I said X but it's closer to Y"
- ✅ **Numeric drift:** Implemented Jan 26 - >20% difference detection

### 3. Understand What's Broken (Fix These)
These FAIL and need work:
- ❌ **Turn 23 (denial_of_fact):** "I never said I had a PhD" - needs denial detection
- ❌ **Turn 24 (retraction_of_denial):** "Actually no, I do have a PhD" - needs retraction tracking
- ❌ **1 unknown turn:** Varies by test data ordering

### 4. Run Tests to Verify Your Changes
```bash
# Quick test (9 turns)
cd D:\AI_round2
$env:PYTHONIOENCODING="utf-8"
python tools/adversarial_crt_challenge.py --turns 9

# Full test (35 turns) 
python tools/adversarial_crt_challenge.py --turns 35

# Watch specific turns
python tools/adversarial_crt_challenge.py --turns 35 | findstr "TURN 23|TURN 24|OVERALL"
```

---

## Architecture Overview

### How Contradiction Detection Works

```
User Input (Turn N)
    ↓
[Store as memory in crt_memory.db]
    ↓
[Call _check_all_fact_contradictions_ml()]
    ├─ Extract facts from current query
    ├─ For each fact slot:
    │  ├─ Find previous memories with same slot
    │  ├─ RUN PATTERN CHECKS (Priority 1)
    │  │  ├─ detect_correction_type() → direct or hedged correction
    │  │  └─ Skip to next slot if pattern found but doesn't match this slot
    │  ├─ RUN NUMERIC DRIFT CHECK (Priority 2)
    │  │  └─ Return early if >20% difference detected
    │  └─ RUN CONTEXTUAL CHECK (Priority 3)
    │     └─ is_true_contradiction_contextual()
    │
    └─ Record result in crt_ledger.db
```

### Key Files & Their Roles

| File | Purpose | Key Methods |
|------|---------|-------------|
| `fact_slots.py` | Extract facts from text | `extract_fact_slots()`, `detect_correction_type()` |
| `crt_core.py` | Contradiction math | `_is_numeric_contradiction()`, `is_true_contradiction_contextual()` |
| `crt_rag.py` | Main detection flow | `_check_all_fact_contradictions_ml()` |
| `crt_memory.py` | Persistence layer | Memory storage & retrieval |
| `crt_ledger.py` | Contradiction tracking | Ledger for audit trail |
| `resolution_patterns.py` | NL resolution rules | Patterns for "X is correct, not Y" |

---

## The 8.6% Gap: Reaching 80%

### Turn 23: Denial of Fact
**Input:** "I never said I had a PhD. I have a Master's degree."  
**Challenge:** Detect that this contradicts Turn 3's "I have a PhD from Stanford"

**What's implemented:**
- `_detect_denial_in_text()` method exists but not integrated
- Can detect patterns like "I never said X", "I don't have X"

**What's missing:**
- Integration into main detection flow
- Logic to match the denied fact against stored memories
- Distinction between testing denials ("I was testing you") vs. real corrections

**How to fix:**
1. Call `_detect_denial_in_text()` in `_check_all_fact_contradictions_ml()`
2. Extract the fact being denied (e.g., "PhD")
3. Find matching memory with that fact
4. Check context - if user says "I was testing you", this is testing, not real denial
5. Record as DENIAL type contradiction

**Code location:** `personal_agent/crt_rag.py` lines ~2300-2400

---

### Turn 24: Retraction of Denial
**Input:** "Actually no, I do have a PhD. I was testing you."  
**Challenge:** Recognize this retracts Turn 23's denial and reverts to Turn 3's original statement

**What's implemented:**
- `_is_retraction_of_denial()` method exists but incomplete
- Can detect "Actually no, I do have X" patterns

**What's missing:**
- Tracking that Turn 23 was a denial
- Logic to link retraction back to original fact
- Lifecycle management: mark Turn 23's Master's claim as expired

**How to fix:**
1. In `_is_retraction_of_denial()`, look at recent DENIAL contradictions
2. Extract the fact being reaffirmed (e.g., "PhD")
3. Find the contradiction entry for Turn 23
4. Mark it as RESOLVED with resolution type RETRACTION
5. Update trust scores to favor the original fact again

**Code location:** `personal_agent/crt_rag.py` lines ~2380-2450

---

### Unknown 3rd Turn
The exact third turn varies between test runs due to:
- Database persistence issues (old test data interferes)
- Random turn ordering in some test scenarios
- Semi-manual evaluation for DRIFT and STRESS phases

**Investigation:**
1. Run test multiple times and log which turn is failing
2. Check if it's consistently the same turn or varies
3. If varies, likely a database cleanup issue

**Solution:** Implement proper thread isolation in `adversarial_crt_challenge.py`:
```python
# Currently uses thread_id="adversarial_challenge"
# This should isolate per-test, but may need validation
```

---

## Common Pitfalls & How to Avoid Them

### Pitfall 1: Early Returns Block Iteration
**Problem:** When checking multiple slots per memory, returning early on one slot prevents checking others
```python
# BAD: Blocks other slots
for slot in slots:
    for prev_mem in previous_memories:
        if found_contradiction:
            return True  # Oops! Never checks other slots
```

**Solution:** Use `continue` to skip only the current iteration
```python
# GOOD: Checks all slots
for slot in slots:
    for prev_mem in previous_memories:
        if found_contradiction_for_this_slot:
            return True  # OK, we're done with this slot
        # Continue checking other memories for this slot
```

### Pitfall 2: Slot Matching Must Be Precise
**Problem:** Matching only one value (old OR new) causes false positives
```python
# BAD: "32" matches in wrong slots
old_val="32", new_val="34"
for slot in ['age', 'programming_years', 'height']:  # All have numbers!
    if new_val in slot_value:  # 34 matches many slots
        return True  # Wrong slot!
```

**Solution:** Match BOTH old and new values
```python
# GOOD: Both must match
slot_matches = (
    old_val matches prev_value AND
    new_val matches new_value
)
```

### Pitfall 3: Broad Patterns Match Unintended Phrases
**Problem:** Pattern `r'\bactually\b'` matches 60+ different phrases
```python
# BAD: Matches everything with "actually"
'actually'  # Matches: "I'm actually 34" (self-correction, not resolution)
            # Matches: "Actually it's X" (might be resolution)
            # Matches: "Actually no" (might be retraction)
```

**Solution:** Require more context
```python
# GOOD: Only matches specific resolution patterns
r'\bactually,?\s*(it\'s|it\s+is|that\'s|that\s+is)\s+'
r'\bactually,?\s+\w+\s+is\s+(correct|right|accurate)\b'
```

### Pitfall 4: Database Persistence Interferes with Tests
**Problem:** `crt_memory.db` and `crt_ledger.db` persist between test runs
```bash
# Run 1: Creates memory "age=32" from Turn 2
# Run 2: Same test, but sees old "age=34" from previous run
# Result: Turn 7's comparison is wrong (finds old data instead of fresh data)
```

**Solution:** Use thread isolation or clear database before test
```python
# In adversarial_crt_challenge.py
rag.memory.clear_thread_memories(thread_id)  # Clear old data

# OR use unique thread_id per run
thread_id = f"test_{datetime.now().timestamp()}"
```

---

## Pattern Implementation Checklist

When adding a new pattern, verify:

- [ ] Regex tested in isolation on target input
- [ ] Extraction function returns (old_value, new_value) tuple
- [ ] Integration into `_check_all_fact_contradictions_ml()` with proper priority
- [ ] Slot matching checks BOTH old and new values
- [ ] No early returns block other slot checking
- [ ] Test passes on specific target turn
- [ ] No false positives on other turns
- [ ] Full adversarial test (35 turns) shows improvement or no regression

---

## Testing Strategy

### Level 1: Unit Test (5 minutes)
```python
from personal_agent.fact_slots import detect_correction_type

# Test direct correction
result = detect_correction_type("Wait, I'm actually 34, not 32")
assert result == ("direct_correction", "32", "34")

# Test hedged correction
result = detect_correction_type("I said 10 years but it's closer to 12")
assert result == ("hedged_correction", "10", "12")
```

### Level 2: Integration Test (2 minutes)
```bash
# Quick test on specific turns
python tools/adversarial_crt_challenge.py --turns 9
# Check: Do Turn 7 and Turn 9 show "CORRECT - detected contradiction"?
```

### Level 3: Regression Test (30 seconds)
```bash
# Make sure nothing broke
python tools/adversarial_crt_challenge.py --turns 35 | findstr "OVERALL"
# Check: Is score same or better than before?
```

---

## Debugging Guide

### Symptom: Turn X shows "MISSED" but should detect contradiction
**Steps:**
1. Add print statement in `_check_all_fact_contradictions_ml()` at the start
2. Run just that turn: `python tools/adversarial_crt_challenge.py --turns X`
3. Check if function is even called
4. If called, add prints before/after each detection method
5. Find which method should have fired but didn't

### Symptom: False positive (turn shows "DETECTED" but shouldn't)
**Steps:**
1. Run turn alone and note which slot matched
2. Add slot matching debug output
3. Verify both old and new values actually match
4. If only one matches, fix the matching logic

### Symptom: Test hangs or crashes
**Checks:**
1. Is there an infinite loop in pattern matching?
2. Are vectors being computed? (slow on first run)
3. Any regex with catastrophic backtracking?
4. Memory limits exceeded from database queries?

---

## The Contradiction Type Taxonomy

When implementing detection, classify as:

| Type | Example | When to Use |
|------|---------|-------------|
| **REVISION** | "I'm 34, not 32" | Explicit self-correction |
| **CONFLICT** | "I work at Google" vs "I work at Microsoft" | Disagreement on fact |
| **TEMPORAL** | Timeline math doesn't add up | Graduate 2018, started job 3 years ago |
| **REFINEMENT** | "32, well 32 and a half" | Progressive clarification |
| **DENIAL** | "I never said I had a PhD" | Explicit disavowal |

---

## Performance Considerations

- **Pattern matching:** O(1) per pattern (regex search)
- **Fact extraction:** O(n) where n = number of slots in text
- **Memory lookup:** O(m) where m = total previous memories
- **Full turn:** O(n × m × k) where k = number of patterns
  - Typical: 5 slots × 50 memories × 20 patterns = 5000 ops = ~10ms

For optimization:
- Cache vector embeddings (don't recompute)
- Index memories by slot (faster lookup)
- Compile regex patterns once at startup

---

## Reference Links in Codebase

| Concept | File | Lines |
|---------|------|-------|
| Correction detection | fact_slots.py | 78-280 |
| Numeric drift | crt_core.py | 900-950 |
| Main detection flow | crt_rag.py | 1802-2100 |
| Denial/retraction stubs | crt_rag.py | 2300-2450 |
| NL resolution rules | resolution_patterns.py | 15-50 |

---

## Success Criteria for 80%

Need to detect **3 more turns** (28/35 total):
1. **Turn 23** - Denial detection working ✅
2. **Turn 24** - Retraction detection working ✅
3. **Turn X** - TBD based on investigation

Once all three fixed:
- Run full test: `python tools/adversarial_crt_challenge.py --turns 35`
- Expected: `OVERALL SCORE: 28.0/35 (80.0%)`
- Mark as Phase 1.3 COMPLETE

---

## Contact Points for Future Work

| If You Want To... | Go To File | Key Methods |
|-------------------|-----------|-------------|
| Add new pattern | fact_slots.py | Add to PATTERNS list, implement extraction function |
| Improve detection flow | crt_rag.py | Modify `_check_all_fact_contradictions_ml()` |
| Change contradiction math | crt_core.py | Modify `is_true_contradiction_contextual()` |
| Improve memory retrieval | crt_rag.py | Modify `_extract_facts_contextual()` |
| Track new contradiction type | crt_ledger.py | Add to ContradictionType enum |

---

## Session Logs and Artifacts

**This session's work:**
- [PATTERN_FIXES_SESSION.md](PATTERN_FIXES_SESSION.md) - Complete implementation details
- [STATUS_UPDATED.md](STATUS_UPDATED.md) - Current metrics and next steps
- [artifacts/adversarial_challenge_*.json](artifacts/) - Test run results

**To examine test results:**
```bash
# Latest test output
$latest = Get-ChildItem artifacts/adversarial_challenge_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -m json.tool $latest.FullName | less
```

---

## Final Notes

- **Database:** Using SQLite, stored in `personal_agent/` directory
- **No external dependencies:** Test runs without Ollama, Pinecone, etc.
- **Reproducibility:** Use same random seed for consistent test ordering
- **Documentation:** Keep comments updated as you make changes
- **Testing:** Always run full 35-turn test before committing

**Good luck! You've got this. 71.4% → 80% is very doable.** 🚀
