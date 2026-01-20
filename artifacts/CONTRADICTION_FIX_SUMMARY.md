# Contradiction Detection Fix - Root Cause Analysis

## Problem Statement
80-turn stress tests showed 0 contradictions detected despite 9 explicit contradictions being introduced (turns 11-20).

## Root Cause Found

### Issue 1: Per-Thread Ledger Databases (NOT the root cause, but confusing)
- Each thread gets its own ledger database: `crt_ledger_{thread_id}.db`
- Contradictions ARE being written to per-thread databases
- Checking `crt_ledger.db` showed 0 because stress tests use `adaptive_fixed_001` thread

### Issue 2: Test Design Flaw (ACTUAL ROOT CAUSE)
**The stress test introduces contradictions WITHOUT establishing baseline facts first.**

Example from stress test turn 11:
```
User: "Actually, my name is Jordan Chen, not Alex."
```

**Problem**: There was NO prior "my name is Alex" statement in the conversation!

The contradiction detection logic (lines 1075-1135 in crt_rag.py) requires:
1. Extract new fact from current message → "Jordan Chen"
2. Find prior memories with same slot → **NONE FOUND** (no prior name was ever stated)
3. If no prior exists, skip contradiction recording

**Result**: 0 contradictions logged because there were no prior facts to contradict.

## Evidence

### Test with proper baseline:
```python
# Turn 1: Establish fact
requests.post('/api/chat/send', json={'message': 'My name is Jordan'})
# Turn 2: Contradict it
requests.post('/api/chat/send', json={'message': 'Actually my name is Alex'})
```

**Result**: `contradiction_detected: true`, ledger entry created with drift=0.311

### Database verification:
```sql
sqlite3 crt_ledger_debug_name_005.db "SELECT ledger_id, summary FROM contradictions"
-- Result:
contra_1768852933032_5506|User name changed: My name is Jordan... vs Actually my name is Alex...|open
```

## What's Working

1. ✅ Name contradiction detection (lines 1071-1135)
2. ✅ Generic fact contradiction detection (lines 2234-2318)
3. ✅ `ledger.record_contradiction()` writes to database
4. ✅ Drift calculation (0.311 for Jordan→Alex)
5. ✅ `contradiction_detected: true` returned in metadata
6. ✅ Contradiction type classification (REVISION vs CONFLICT)
7. ✅ Affects_slots tracking ("name")

## What's Broken

1. ❌ Stress test doesn't establish baseline facts before contradicting them
2. ❌ Stress test prompts like "My name is Jordan, not Alex" expect system to infer "Alex" was claimed (it wasn't)
3. ❌ `/api/contradictions` endpoint returns 404 (needs implementation)

## Fix Required

### Option A: Fix Stress Test (RECOMMENDED)
Update `tools/adaptive_stress_test.py` intro phase (turns 1-10) to explicitly state facts:
- Turn 2: "My name is Alex Thompson"
- Turn 3: "I work at Vertex Analytics"
- Turn 4: "My favorite language is Rust"

Then contradiction phase (turns 11-20) can properly contradict:
- Turn 11: "My name is Jordan Chen" (contradicts turn 2)
- Turn 12: "I work at DataCore" (contradicts turn 3)
- Turn 13: "Python is my favorite" (contradicts turn 4)

### Option B: Add Implicit Contradiction Detection
Enhance contradiction detection to parse "X not Y" patterns and create synthetic prior memory for "Y". This is complex and error-prone.

## Next Steps

1. ✅ Verified contradiction detection works with proper baseline
2. ⏭️ Update stress test to establish facts before contradicting
3. ⏭️ Rerun 80-turn test with corrected prompts
4. ⏭️ Verify contradictions logged > 0
5. ⏭️ Implement `/api/contradictions` endpoint to return ledger data

## Code Locations

- Name contradiction detection: `personal_agent/crt_rag.py:1071-1135`
- Generic contradiction detection: `personal_agent/crt_rag.py:2234-2318`
- Ledger write: `personal_agent/crt_ledger.py:438-461`
- Per-thread database init: `crt_api.py:386-395`
- Stress test prompts: `tools/adaptive_stress_test.py:_intro_phase_prompt, _contradiction_phase_prompt`
