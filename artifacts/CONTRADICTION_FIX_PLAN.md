# Contradiction Detection Fix Plan

**Problem**: 9 explicit contradictions introduced across 80 turns, 0 logged to ledger. Gates passed 100% of turns including when outputting factually wrong information.

**Evidence of Internal Detection**: Turn 72 shows `gate_reason: "gates_passed_with_contradiction_note"` - system had signals but didn't enforce.

---

## Phase 1: Trace the Execution Path (2 hours)

### 1.1 Find Classifier Invocation Points
```bash
# Where is the classifier actually called?
grep -rn "classify" personal_agent/crt_*.py
grep -rn "classifier" personal_agent/crt_*.py
grep -rn "predict" personal_agent/crt_classifier.py
```

**Goal**: Confirm classifier is invoked on every user message, not just some subset.

### 1.2 Find Ledger Write Points
```bash
# Where does contradiction data write to ledger?
grep -rn "ledger.add" personal_agent/crt_*.py
grep -rn "ledger.record" personal_agent/crt_*.py
grep -rn "write.*contradiction" personal_agent/crt_ledger.py
```

**Goal**: Find the code path from classifier result → ledger write.

### 1.3 Find Gate Decision Logic
```bash
# What determines gates_passed vs gates_failed?
grep -rn "gates_passed" personal_agent/crt_core.py
grep -rn "gate_reason" personal_agent/crt_core.py
grep -rn "contradiction_note" personal_agent/crt_core.py
```

**Goal**: Understand why `gates_passed_with_contradiction_note` didn't block output.

---

## Phase 2: Add Instrumentation Logging (1 hour)

### 2.1 Classifier Invocation Logging
Add to classifier invoke function:
```python
logger.info(f"[CLASSIFIER] Input: {current_msg[:100]}, Prediction: {prediction}, Confidence: {confidence}")
```

### 2.2 Ledger Write Logging
Add before ledger write:
```python
logger.info(f"[LEDGER_WRITE] Attempting to write contradiction: {contradiction_data}")
```

Add after ledger write:
```python
logger.info(f"[LEDGER_WRITE] Success. Total contradictions: {len(ledger.get_all())}")
```

### 2.3 Gate Decision Logging
Add to gate evaluation:
```python
logger.info(f"[GATE] Contradiction detected: {has_contradiction}, Threshold: {threshold}, Decision: {gate_reason}")
```

### 2.4 Run Minimal Test
```bash
# 5-turn test with explicit contradiction
python tools/adaptive_stress_test.py debug_contradiction_001 1 5
```

**Expected logs**:
- 5 classifier invocations
- If contradiction detected at turn 3, ledger write attempt
- Gate decision reasoning

---

## Phase 3: Hypotheses & Fixes (4 hours)

### Hypothesis 1: Classifier Not Invoked Per Turn
**Test**: Check if `[CLASSIFIER]` logs appear for every turn.

**If missing**:
```python
# In crt_core.py process_message() or equivalent:
def process_message(user_msg, context):
    # ADD THIS:
    contradiction_result = classifier.predict(user_msg, context)
    if contradiction_result['is_contradiction']:
        ledger.record_contradiction(contradiction_result)
    # ... rest of processing
```

### Hypothesis 2: Classifier Result Not Writing to Ledger
**Test**: Check if `[CLASSIFIER]` shows predictions but `[LEDGER_WRITE]` never appears.

**If true, find the gap**:
```python
# Search for where classifier result is consumed:
grep -A10 "classifier.predict" personal_agent/crt_core.py
```

**Expected pattern**:
```python
result = classifier.predict(...)
if result['is_contradiction']:
    ledger.add_contradiction(...)  # <-- This line may be missing
```

**Fix**: Add ledger write immediately after classifier prediction.

### Hypothesis 3: Ledger Write Gated by Unreachable Condition
**Test**: Check if ledger write is inside a conditional that's never true.

**Example bad pattern**:
```python
if confidence > 0.95:  # <-- Threshold too high
    ledger.add_contradiction(...)
```

**Fix**: Lower confidence threshold or remove gating.

### Hypothesis 4: Gate Threshold Allows "Noted" Without Blocking
**Test**: Check gate decision code for `contradiction_note` handling.

**Current behavior** (from evidence):
```python
# Seems to do this:
if has_contradiction:
    gate_reason = "gates_passed_with_contradiction_note"  # Still passes!
    return (output, True)  # True = gates passed
```

**Should be**:
```python
if has_contradiction:
    gate_reason = "gates_failed_contradiction_detected"
    return (None, False)  # False = gates FAILED, block output
```

**Fix location**: Search for where `gate_reason` is set:
```bash
grep -B5 -A5 "gates_passed_with_contradiction_note" personal_agent/crt_core.py
```

### Hypothesis 5: Contradiction Classifier Trained But Not Loaded
**Test**: Add loading verification:
```python
# At startup, log:
logger.info(f"[INIT] Classifier loaded: {classifier is not None}")
logger.info(f"[INIT] Classifier model path: {classifier.model_path}")
```

**If model not loaded**: Check `train_classifier.py` saved model path matches runtime load path.

---

## Phase 4: Validation (2 hours)

### 4.1 Fix Verification Test
After implementing fixes, run:
```bash
python tools/adaptive_stress_test.py fix_validation_001 1 30
```

**Success criteria**:
- Turn 11 name contradiction → ledger shows count = 1
- Turn 12 company contradiction → ledger shows count = 2
- Turn 28 ledger query shows count >= 2 (not 0)
- At least one turn with `gates_failed` (not 100% pass rate)

### 4.2 Check Ledger Query Endpoint
```bash
# Verify contradiction count is non-zero
curl http://127.0.0.1:8123/api/contradictions?thread_id=fix_validation_001
```

**Expected**: JSON with `total > 0`, not 404 error.

### 4.3 Full 80-Turn Retest
```bash
python tools/adaptive_stress_test.py fix_validation_002 50 80
```

**Success criteria**:
- Contradictions detected > 0 (ideally 5-9 out of 9 explicit contradictions)
- Gate failures > 0 (at least some blocking)
- Truth reintroduction failures < 110 (should be much lower)

---

## Phase 5: Root Cause Documentation (30 min)

Create `artifacts/CONTRADICTION_FIX_POSTMORTEM.md`:

```markdown
# Root Cause

**What was broken**: [Specific code path that failed]

**Why it failed**: [Condition that prevented execution]

**Evidence**: [Log excerpts showing the gap]

# Fix Applied

**Changed**: [File:line modified]

**Before**:
[Code snippet]

**After**:
[Code snippet]

# Validation

**Test**: fix_validation_002
**Result**: X/9 contradictions detected (up from 0/9)
**Gates**: Y% block rate (up from 0%)
```

---

## Critical Code Files to Examine

Priority order:
1. `personal_agent/crt_core.py` - Main processing loop, gate logic
2. `personal_agent/crt_classifier.py` - Contradiction detection invoke
3. `personal_agent/crt_ledger.py` - Ledger write path
4. `personal_agent/crt_memory.py` - Memory item trust/confidence updates
5. `crt_api.py` - API endpoint integration

---

## Time Budget

- Phase 1 (Trace): 2 hours
- Phase 2 (Instrument): 1 hour
- Phase 3 (Fix): 4 hours
- Phase 4 (Validate): 2 hours
- Phase 5 (Document): 30 min

**Total**: ~9.5 hours (1.5 days)

---

## Escape Hatch

If after Phase 3 you still have 0 contradictions logged:

**Nuclear option**: Bypass existing code and add explicit contradiction detection:

```python
# In crt_api.py /api/chat/send endpoint, after getting user message:

def detect_name_contradiction(user_msg, memory_context):
    # Hardcoded detector for "my name is X" pattern
    import re
    name_match = re.search(r"my name is (\w+)", user_msg, re.IGNORECASE)
    if name_match:
        claimed_name = name_match.group(1)
        # Check if different from stored name
        stored_name = memory_context.get('user_name')
        if stored_name and stored_name != claimed_name:
            return {
                'is_contradiction': True,
                'type': 'name_mismatch',
                'old_value': stored_name,
                'new_value': claimed_name
            }
    return None

# Use it:
contradiction = detect_name_contradiction(user_message, context)
if contradiction:
    ledger.add_contradiction(contradiction)
    # Force gate failure
    return {"answer": "[GATED: Contradiction detected]", "gates_passed": False}
```

This proves the ledger/gate infrastructure works. Then trace back to why the trained classifier isn't connecting.
