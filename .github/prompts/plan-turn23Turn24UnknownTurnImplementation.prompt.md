# Plan: Implement Turn 23, 24, and Unknown Turn Detection

**TL;DR:** Turn 23 (denial) and Turn 24 (retraction) detection methods already exist but aren't integrated into the main contradiction flow. This plan integrates them by adding two conditional checks to the 4-tier detection priority system. Finding the unknown 3rd turn requires identifying which turn varies by running tests multiple times or investigating database persistence issues.

---

## Context Summary

### Current State
- **Score:** 71.4% (25/35 turns)
- **Target:** 80% (28/35 turns)
- **Gap:** 3 turns remaining
- **Known:** Turn 23 (denial), Turn 24 (retraction)
- **Unknown:** 1 more turn (database/edge case)

### What Already Exists
- ✅ `_detect_denial_in_text()` method (line 256-302 in crt_rag.py) - READY
- ✅ `_is_retraction_of_denial()` method (line 304-350+ in crt_rag.py) - READY
- ✅ Main detection flow in `_check_all_fact_contradictions_ml()` (line 1802-2100) - EXISTS
- ✅ Current 4-tier priority system - IN PLACE

### What Needs to Happen
- ❌ Denial detection not integrated (needs insertion ~line 1970)
- ❌ Retraction integration incomplete (placeholder exists at line 1988, needs completion)
- ❌ Unknown turn not identified (needs investigation)
- ❌ Database persistence causing test variance (needs cleanup)

---

## Step 1: Integrate Denial Detection for Turn 23

### Objective
Detect when user denies a prior claim: "I never said I had a PhD"

### Test Case
```
Turn 23 Input: "I never said I had a PhD. I have a Master's degree."
Prior Memory (Turn 3): "I have a PhD in Machine Learning from Stanford. Graduated in 2018."
Expected: Contradiction type = DENIAL
Expected Confidence: 0.95+
```

### Implementation Details

**File:** `personal_agent/crt_rag.py`  
**Method:** `_check_all_fact_contradictions_ml()`  
**Insertion Point:** Around line 1970 (after contextual contradiction check, before retraction check)  
**Priority Level:** 4 (after patterns, numeric drift, contextual)

**Current Code Structure:**
```
1870-1920: Correction pattern detection (priority 1)
1930-1960: Numeric drift detection (priority 2)
1960-1988: Contextual contradiction check (priority 3)
1988-2005: Retraction of denial (priority 4) - PLACEHOLDER
2010-2050: Negation pattern detection (priority 5)
2050+:     ML-based detection
```

**What to Add (Line 1970-1988):**
```python
# ===== PRIORITY 4: DENIAL DETECTION (Turn 23) =====
is_denial, denied_value = self._detect_denial_in_text(user_query, slot)
if is_denial and denied_value:
    # Search for the denied fact in previous memories
    for prev_mem in previous_user_memories:
        prev_facts = extract_fact_slots(prev_mem.text) or {}
        prev_fact = prev_facts.get(slot)
        
        if prev_fact is None:
            continue
        
        # Check if denied value matches previous value
        prev_value_str = str(prev_fact.value).lower().strip()
        if denied_value.lower() in prev_value_str:
            # Found matching prior statement - this is a denial contradiction
            contradiction_entry = {
                "memory_id": new_memory.memory_id,
                "previous_memory_id": prev_mem.memory_id,
                "slot": slot,
                "old_value": prev_value_str,
                "new_value": f"DENIED: {denied_value}",
                "contradiction_type": "DENIAL",
                "confidence": 0.95,
                "reason": f"User denied having/claiming '{denied_value}' but prior statement shows '{prev_value_str}'",
            }
            logger.info(f"[DENIAL] Turn {new_memory.memory_id}: Denial of '{denied_value}' detected")
            return True, contradiction_entry
```

### Testing
```powershell
python tools/adversarial_crt_challenge.py --turns 23
```

Expected output:
```
TURN 23 | verdict: CORRECT - detected contradiction
  Score: 1.0/1.0
```

---

## Step 2: Complete Retraction Detection for Turn 24

### Objective
Detect when user retracts a prior denial: "Actually, I do have a PhD"

### Test Case
```
Turn 24 Input: "Actually no, I do have a PhD. I was testing you."
Prior Statement (Turn 23): "I never said I had a PhD"
Original Claim (Turn 3): "I have a PhD in Machine Learning"
Expected: Contradiction type = RETRACTION_OF_DENIAL
Expected Confidence: 0.95+
Expected Action: Restore original PhD claim value
```

### Implementation Details

**File:** `personal_agent/crt_rag.py`  
**Method:** `_check_all_fact_contradictions_ml()` - completion of existing placeholder  
**Location:** Line 1988-2005  
**Priority Level:** 4 (same as denial, but called AFTER denial detection)

**Current Placeholder Code (Line 1988):**
```python
is_retraction, retraction_reason = self._is_retraction_of_denial(
    new_text=user_query,
    prior_text=prev_mem.text,
    slot=slot
)
```

**What to Add After the Call:**
```python
if is_retraction and retraction_reason != "prior_not_denial":
    # User is retracting a prior denial - restore original value
    # Get the original value from before the denial
    original_value = None
    for mem in previous_user_memories:
        mem_facts = extract_fact_slots(mem.text) or {}
        mem_fact = mem_facts.get(slot)
        if mem_fact and mem.memory_id < prev_mem.memory_id:  # Before the denial
            original_value = str(mem_fact.value)
            break
    
    contradiction_entry = {
        "memory_id": new_memory.memory_id,
        "previous_memory_id": prev_mem.memory_id,
        "slot": slot,
        "old_value": f"DENIED: {retraction_reason}",
        "new_value": original_value or new_value_str,
        "contradiction_type": "RETRACTION_OF_DENIAL",
        "confidence": 0.95,
        "reason": f"User retracted prior denial of '{retraction_reason}', restoring '{original_value or new_value_str}'",
    }
    logger.info(f"[RETRACTION] Turn {new_memory.memory_id}: Retraction of denial detected")
    return True, contradiction_entry
```

### Testing
```powershell
python tools/adversarial_crt_challenge.py --turns 23-24
```

Expected output:
```
TURN 23 | verdict: CORRECT - detected contradiction
  Score: 1.0/1.0
TURN 24 | verdict: CORRECT - detected contradiction
  Score: 1.0/1.0
```

---

## Step 3: Identify the Unknown 3rd Turn

### Investigation Strategy

#### Phase 1: Determine Which Turn Varies
```powershell
# Run test 5 times and capture results
cd D:\AI_round2
$results = @()
for ($i=1; $i -le 5; $i++) {
    Write-Host "=== RUN $i ==="
    $output = python tools/adversarial_crt_challenge.py --turns 35
    $score_line = $output | Select-String "OVERALL SCORE"
    $results += $score_line
    Write-Host $score_line
}

Write-Host "`nSCORE VARIANCE:"
$results | Sort-Object | Get-Unique
```

If scores vary → Database persistence issue  
If scores consistent → Code logic issue specific to one turn

#### Phase 2: Check Most Likely Candidates
Based on phase breakdown, most likely candidates:
- **Turn 10** (TEMPORAL phase, 70% = 0.5 points missing)
- **Turn 11** (SEMANTIC phase, 80% = 0.5 points missing)
- **Turn 25** (NEGATION phase, 50% = 2.5 points missing - largest gap)

#### Phase 3: Database Persistence Investigation
```powershell
# Check current database state
cd D:\AI_round2
python -c "
from personal_agent.memory_vault import ContradictionLedger
ledger = ContradictionLedger()
contradictions = ledger.get_all()
print(f'Total contradictions in DB: {len(contradictions)}')
print('Recent contradictions:')
for c in contradictions[-5:]:
    print(f'  Turn {c[\"memory_id\"]}: {c[\"contradiction_type\"]} ({c[\"slot\"]})')
"
```

#### Phase 4: Clean Database and Re-test
```powershell
# Clear persistence and test
cd D:\AI_round2
Remove-Item crt_memory.db -ErrorAction SilentlyContinue
Remove-Item crt_ledger.db -ErrorAction SilentlyContinue
python tools/adversarial_crt_challenge.py --turns 35
```

If score increases after clean DB → Persistence issue  
If score same → Code logic issue

### Decision Tree
```
Run test 5 times
├─ Scores vary by ≥0.5 points
│  └─ PERSISTENCE ISSUE - Clear DB in test harness
│     └─ Add ledger.clear_thread_contradictions() call
│     └─ Re-test
│
└─ Scores consistent
   └─ CODE LOGIC ISSUE - Find failing turn
      └─ Run single turn tests for candidates (10, 11, 25)
      └─ Analyze detection logic for that turn
      └─ Implement specific fix
```

---

## Step 4: Stabilize Test Results via Database Cleanup

### Objective
Prevent old contradictions from previous runs interfering with new test sessions

### File
`tools/adversarial_crt_challenge.py`

### Location
Around line 430 (test initialization)

### Current Code
```python
# Initialize CRT
rag = CRTEnhancedRAG()

# Reset thread for clean test
try:
    rag.memory.clear_thread_memories(thread_id)
    print("[INIT] Thread memories cleared")
except Exception as e:
    print(f"[INIT] Could not clear thread: {e}")
```

### What to Add
```python
# Also clear contradictions ledger for clean state
try:
    from personal_agent.crt_ledger import ContradictionLedger
    ledger = ContradictionLedger()
    
    # Clear contradictions specific to this thread/session
    ledger.clear_thread_contradictions(thread_id)
    print("[INIT] Contradictions ledger cleared")
except Exception as e:
    print(f"[INIT] Could not clear ledger: {e}")
```

### Verification
```powershell
# Run test twice in same session - should get identical scores
python tools/adversarial_crt_challenge.py --turns 35
python tools/adversarial_crt_challenge.py --turns 35
# Should see same "OVERALL SCORE" line both times
```

---

## Step 5: Verify No Regressions and Score ≥ 80%

### Final Verification Checklist

```powershell
# 1. Run full test
cd D:\AI_round2
$env:PYTHONIOENCODING="utf-8"
python tools/adversarial_crt_challenge.py --turns 35
```

Verify:
- [ ] OVERALL SCORE shows ≥ 28.0/35 (80.0%)
- [ ] Turn 23 shows: "CORRECT - detected contradiction"
- [ ] Turn 24 shows: "CORRECT - detected contradiction"
- [ ] Baseline phase: 5.0/5 (100%) ← No regression
- [ ] Semantic phase: 4.0/5 (80%) ← No regression
- [ ] Identity phase: 5.0/5 (100%) ← No regression
- [ ] False positives: 0 ← No false positives introduced

```powershell
# 2. Verify previous passing turns still pass
python tools/adversarial_crt_challenge.py --turns 1-5
# Should see "CORRECT" for all 5 turns

python tools/adversarial_crt_challenge.py --turns 16-20
# Should see "CORRECT" for all 5 turns
```

Verify:
- [ ] All baseline turns (1-5) still pass
- [ ] All identity turns (16-20) still pass
- [ ] No score regression from 71.4%

```powershell
# 3. Run test 3 times to confirm stability
for ($i=1; $i -le 3; $i++) {
    python tools/adversarial_crt_challenge.py --turns 35 | Select-String "OVERALL SCORE"
}
```

Verify:
- [ ] All three runs show same score (±0.0)
- [ ] No variance from database persistence

---

## Implementation Order & Timeline

### Phase 1: Integration (20 min)
1. **Add denial detection code** (line 1970-1988 in crt_rag.py) - 5 min
2. **Complete retraction detection code** (line 1988-2005) - 5 min
3. **Test Turn 23 & 24 in isolation** (10 min)

### Phase 2: Investigation (30 min)
1. **Run variance test** (5 min) - 5×35 turn tests to identify variance
2. **Investigate database persistence** (10 min) - Check ledger state
3. **Test candidates** (10 min) - Single turn tests for likely candidates
4. **Implement cleanup** (5 min) - Add ledger clearing to test harness

### Phase 3: Verification (10 min)
1. **Run full test** (5 min) - Verify ≥28/35 (80%)
2. **Run stability tests** (5 min) - Run 3× to confirm consistent score

**Total Time:** ~60 minutes  
**Confidence:** 95%+

---

## Success Criteria

### Minimum Criteria (80% target)
- ✅ Turn 23 detecting denial (1.0 point)
- ✅ Turn 24 detecting retraction (1.0 point)
- ✅ 1 additional turn fixed (1.0 point)
- ✅ Final score: 28.0/35 (80.0%)

### Stretch Criteria (beyond 80%)
- ✅ 29+/35 (82%+) - Fix multiple unknown turns
- ✅ 0 false positives
- ✅ All baseline/identity/semantic phases stable
- ✅ Reproducible consistent score across test runs

### Regression Criteria (must not happen)
- ❌ Score < 25/35 (any regression)
- ❌ False positives > 0
- ❌ Baseline/Identity/Semantic scores decrease
- ❌ Database persistence issues remain

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Denial pattern matches wrong slot | Medium | Test Turn 23 in isolation first, verify memory lookups |
| Retraction doesn't find original value | Medium | Add logging to trace original value search, manual inspection |
| Unknown turn hard to find | High | Systematic testing (5 runs), check phase breakdown, DB state |
| Database causes score variance | High | Implement ledger cleanup, test stability 3× |
| Regression on existing turns | Low | Test baseline/identity/semantic separately before full run |

---

## Rollback Plan

If something breaks during implementation:

```powershell
# 1. Revert recent changes
git checkout -- personal_agent/crt_rag.py
git checkout -- tools/adversarial_crt_challenge.py

# 2. Verify rollback worked
python tools/adversarial_crt_challenge.py --turns 35
# Should show 71.4% (25/35) again

# 3. Identify what went wrong
# Review implementation against plan
# Check logs for "DENIAL" or "RETRACTION" entries

# 4. Re-implement more carefully
# Add only ONE change at a time
# Test each change before proceeding
```

---

## Notes for Implementation

1. **Denial detection order matters** - Check denial BEFORE retraction since retraction checks for prior denial
2. **Memory iteration is crucial** - Must find the specific memory that contains the denied claim
3. **Slot matching is critical** - Only match if denied value is found in that specific slot
4. **Confidence scores** - Set to 0.95+ for both denial and retraction (high confidence in detection)
5. **Logging is essential** - Add `logger.info()` calls to track detection for debugging
6. **Test isolation** - Run Turn 23 and 24 separately first, then together, then with full 35

---

## Questions for Refinement

Before implementing, clarify:

1. **Denial scope:** Should we handle compound denials? (e.g., "I don't have a PhD or a Master's")
2. **Retraction scope:** Should we handle partial retractions? (e.g., "I have a PhD in Computer Science, not ML")
3. **Unknown turn priority:** Should we spend ≥20 min investigating, or just implement Turn 23+24 and declare 80% if that's enough?
4. **Database cleanup:** Should we also clear vector embeddings, or just memories + ledger?
5. **Logging detail:** How verbose should debug logging be? (minimal vs. detailed for each detection attempt)

---

**Status:** Ready for implementation | **Confidence:** High (95%+) | **Est. Time:** 60 min
