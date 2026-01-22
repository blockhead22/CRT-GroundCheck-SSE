# Temporal Guard Rails - Feature Documentation

## Overview

Added intelligent filtering to distinguish between permanent facts and temporary activities, preventing the system from storing ephemeral statements as durable identity facts.

## Problem Statement

User feedback highlighted that the system could confuse temporary activities with permanent facts:

> "a user might say im working on homework and suddenly the system is confused about working on homework and working at walmart"

The concern: Users speak conversationally and vaguely. The system needs to do the "heavy lifting" to determine what should be stored permanently.

## Solution

Implemented `_is_temporal_statement()` guard rail in `user_profile.py` that filters statements before extracting facts.

### What Gets Filtered (NOT Stored)

**Temporal Activities:**
- "I'm working on homework tonight"
- "I'm currently reviewing code"
- "I'm studying for exams this week"
- "I'm doing some freelance work today"
- "I'm learning about Python recently"

**Pattern:** Temporal marker + Temporary activity verb

### What Gets Stored (Permanent Facts)

**Durable Identity Facts:**
- "I work at Walmart" (permanent employer)
- "I work for myself as a freelance web developer" (permanent occupation)
- "I graduated from MIT" (historical fact)
- "My name is Nick" (identity)
- "I live in Seattle" (location)

**Pattern:** Statements without temporal context, using identity-establishing language

## Implementation Details

### Temporal Markers Detected
```python
temporal_markers = [
    'tonight', 'today', 'this week', 'this month', 'this year',
    'right now', 'at the moment', 'currently',
    'this morning', 'this afternoon', 'this evening',
    'these days', 'lately', 'recently',
]
```

### Temporary Activity Verbs
```python
temporary_activities = [
    'working on', 'studying', 'reviewing', 'reading about',
    'learning about', 'practicing', 'preparing for',
    'doing some', 'helping with', 'finishing up',
]
```

### Special Pattern: "working on"

The phrase "working on" is always treated as temporary UNLESS accompanied by "work at/for":
- "I'm working on homework" → Filtered (temporary)
- "I work at Google" → Stored (permanent)
- "I work for myself" → Stored (permanent)

## Examples

### Scenario 1: User mentions temporary activity
```
User: "I'm working on homework tonight"
System: [Filters statement, does NOT store]
Profile: No change

User: "What do I do?"
System: "You work at Walmart" (previously stored fact)
```

### Scenario 2: User mentions permanent fact
```
User: "I work at Walmart"
System: [Stores as permanent employer fact]
Profile: employer = "Walmart"

User: "I work for myself as a freelance developer"
System: [Stores as second permanent employer fact]
Profile: employer = ["Walmart", "self-employed"]
```

### Scenario 3: Mixed conversation
```
User: "I work at Walmart"
System: [Stores employer fact]

User: "I'm currently reviewing code for a side project"
System: [Filters temporal activity]

User: "What am I working on?"
System: [Can discuss current context without storing it permanently]

User: "What do I do?"
System: "You work at Walmart"
```

## Design Philosophy

### "Heavy Lifting" Principle

The user expects conversational flexibility without micromanaging what gets stored. The guard rails provide this by:

1. **Allowing vague permanent statements** - "I work at..." is stored even if casual
2. **Filtering clear temporal context** - "tonight", "today" signals temporary
3. **Defaulting to storage** - If unclear, store it (user can correct)
4. **Pattern-based intelligence** - "working on" vs "work at" distinction

### Trade-offs

**Conservative Filtering:**
- ✅ Prevents cluttering profile with temporary activities
- ❌ Might occasionally filter something user wanted stored

**User Override:**
- Users can be explicit: "FACT: employer = ..." to bypass filtering
- System prioritizes structured fact declarations

**Future Enhancement:**
- Could add confidence scoring instead of binary filter
- Could track temporal facts separately (conversation memory vs profile)

## Testing

### Test Coverage

**`tests/test_temporal_guard_rails.py`:**
- `test_temporal_detection_examples()` - Validates detection logic
- `test_temporal_guard_rails()` - End-to-end scenario testing

**Test Cases:**
1. Temporal activities are filtered ✓
2. Permanent facts are stored ✓
3. Multiple employers coexist ✓
4. "working on" patterns filtered ✓

### Results
```
✅ 6/6 temporal guard rail tests PASSED
✅ 6/6 existing Nick bug tests PASSED
✅ 0 regressions in existing tests
```

## Integration Points

### Where Guard Rails Apply

**User Profile (`user_profile.py`):**
- `update_from_text()` calls `_is_temporal_statement()` before extraction
- Filtered statements return empty dict (no facts extracted)

**Thread-Local Memory:**
- Guard rails do NOT apply to thread-specific conversation memory
- Temporal activities can still be discussed in conversation context

**Global Profile:**
- Guard rails ONLY apply to global cross-thread facts
- Ensures profile contains only durable identity information

## Performance Impact

**Minimal Overhead:**
- Simple string matching (no ML)
- O(n*m) where n=statement length, m=markers (~20)
- Typical: <1ms per statement

**No Database Impact:**
- Filtering happens before database operations
- Reduces unnecessary writes (performance win)

## Future Enhancements

1. **Confidence Scoring:** Instead of binary filter, assign confidence
2. **User Preferences:** Allow users to configure filtering sensitivity
3. **Temporal Context Storage:** Store recent activities separately from profile
4. **Learning:** Adapt patterns based on user corrections

## Backwards Compatibility

**Fully Compatible:**
- Existing facts unchanged
- Existing API unchanged
- Only affects new fact extraction
- Can be disabled by using structured fact format: "FACT: slot = value"

---

**Status:** ✅ Production Ready
**Version:** Added in commit 1564f5c
**Related:** NICK_FREELANCE_BUG_FIX_SUMMARY.md
