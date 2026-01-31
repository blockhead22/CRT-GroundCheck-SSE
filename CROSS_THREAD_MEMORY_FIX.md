# Cross-Thread Memory Fix - Summary

## Problem
User reported that names (both user name and assistant name) were not persisting across conversation threads:
- Thread 1: "My name is Nick Block" + "Let's call you Aether" ✅ Worked in same thread
- Thread 2: Agent forgot both names ❌
- Thread 3: Agent made up wrong name "Alex" ❌

## Root Cause
**Two bugs in GlobalUserProfile storage:**

### Bug 1: Missing `active` Column in INSERT
**Location:** `personal_agent/user_profile.py` line ~247

**Issue:** INSERT statement was missing the `active` column:
```python
# BEFORE (broken):
INSERT INTO user_profile_multi (slot, value, normalized, timestamp, source_thread, confidence)
VALUES (?, ?, ?, ?, ?, ?)

# AFTER (fixed):
INSERT INTO user_profile_multi (slot, value, normalized, timestamp, source_thread, confidence, active)
VALUES (?, ?, ?, ?, ?, ?, 1)
```

### Bug 2: UNIQUE Constraint Conflict
**Location:** Database schema + `user_profile.py` line ~200

**Issue:** Table has UNIQUE constraint on `(slot, normalized)` without considering `active` flag:
```sql
CREATE TABLE user_profile_multi (
    ...
    UNIQUE(slot, normalized)  -- Prevents same value even if one is inactive
)
```

When code marked old values as `active=0` (inactive), they remained in the database. Attempting to insert the same value again violated the UNIQUE constraint.

**Solution:** DELETE inactive duplicates before inserting:
```python
# Check for inactive duplicate with same normalized value
if exact_match and not is_active:
    cursor.execute("DELETE FROM user_profile_multi WHERE id = ?", (match_id,))
    logger.info(f"[PROFILE_UPDATE] Deleted inactive duplicate: {slot} = {match_value}")
```

## Additional Enhancement: Assistant Name Support

**New Capability:** System can now extract and store assistant names.

**Added to `fact_slots.py`:**
- Pattern 1: "Let's call you Aether" / "I'll call you Claude"
- Pattern 2: "Your name is GPT" / "You're Aria"
- Pattern 3: "Call yourself Oracle" / "You should be called Nova"

**Added to `user_profile.py`:**
- `assistant_name` added to SINGLE_VALUE_SLOTS (lines 41-50)

## Testing
Created comprehensive test suite:
- `test_name_storage.py` - Verifies basic storage
- `test_assistant_name.py` - Tests extraction patterns
- `test_cross_thread_retrieval.py` - Simulates thread 2 asking for facts
- `test_full_cross_thread.py` - Complete scenario simulation
- `check_profile.py` - Database inspection utility

## Verification
After fixes, profile now stores 13 facts including:
- ✅ `name`: Nick Block
- ✅ `assistant_name`: Aether
- ✅ All facts persist across threads
- ✅ No duplicate storage
- ✅ Contradictions handled correctly (single-value slots replace old values)

## Files Modified
1. **personal_agent/user_profile.py**
   - Fixed INSERT statement to include `active` column
   - Added DELETE for inactive duplicates before insert
   - Added `assistant_name` to SINGLE_VALUE_SLOTS
   - Enhanced logging throughout storage logic

2. **personal_agent/fact_slots.py**
   - Added assistant name extraction patterns (3 patterns)
   - Integrated with existing name extraction infrastructure

## Impact
- ✅ User introduces themselves ONCE
- ✅ Assistant is named ONCE
- ✅ ALL future threads remember both
- ✅ No re-introduction needed
- ✅ No hallucinated wrong names

## Next Steps (Optional Improvements)
1. Add profile health check endpoint
2. Migration tool to backfill names from thread-local memories
3. Comprehensive unit tests for all fact slots
4. Integration test: Store → Retrieve → Inject → LLM full cycle
