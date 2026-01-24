# NL Resolution Fix - Summary

## Problem Statement

The NL (Natural Language) resolution feature was only passing 1 out of 6 test patterns in the stress test. The feature should allow users to resolve contradictions using natural language statements like:

1. "X is correct" - e.g., "Google is correct, I switched jobs"
2. "Actually..." - e.g., "Actually, I moved to Austin last month"
3. "I meant..." - e.g., "I meant 30, I mistyped before"
4. "changed to..." - e.g., "I've changed to tea recently"
5. "explicit confirm" - e.g., "Yes, I got married, that's correct now"
6. "keep OLD value" - e.g., "No wait, blue was right, ignore the red"

## Root Cause Analysis

The issue was found in `/home/runner/work/AI_round2/AI_round2/personal_agent/crt_rag.py` in the `_detect_and_resolve_nl_resolution` method (lines 1330-1527).

### Issues Found:

1. **Too-specific resolution patterns**: The pattern for "changed to" was restricted to `r'\bchanged\s+(jobs|to|companies)\b'`, which wouldn't match "changed to tea" or other non-job-related changes.

2. **Missing patterns**: No patterns for "ignore" or "was right" which are needed for the "keep OLD value" test case.

3. **Fact extraction limitation**: The `extract_fact_slots` function doesn't support all fact types:
   - ✓ Supports: employer, location, age, favorite_color, etc.
   - ✗ Missing: general preferences (coffee vs tea), marital status (single vs married), etc.

4. **Critical bug at line 1404**: When `extract_fact_slots` returned no common slots between old and new memories (empty `contra_slots`), the code would skip the contradiction entirely with `continue`, never reaching the fuzzy matching fallback.

```python
contra_slots = set(old_facts.keys()) & set(new_facts.keys())
if not contra_slots:
    continue  # ❌ This skipped contradictions without extracted fact slots!
```

## Solution Implemented

### 1. Expanded Resolution Patterns

Added more general patterns and new ones:

```python
resolution_patterns = [
    r'\b(is|was)\s+(correct|right|accurate)\b',
    r'\bactually\b',
    r'\bi\s+meant\b',
    r'\bswitched\s+(jobs|to|companies)\b',
    r'\bchanged\s+to\b',  # ✓ NEW: More general "changed to"
    r'\bchanged\s+(jobs|companies)\b',  # Specific "changed jobs"
    r'\bmoved\s+to\b',
    r'\bnow\s+(work|working|at)\b',
    r'\bcorrect\s+(one|version|answer|status|value|info|statement)\b',
    r'\b(that|this)(?:\s*\'s|\s+is)\s+(correct|right|accurate)\b',
    r'\bignore\s+(the|that)\b',  # ✓ NEW: "ignore the red"
    r'\b(no|wait)\b.*\b(was|is)\s+(right|correct)\b',  # ✓ NEW: "no wait, X was right"
]
```

### 2. Removed Blocking Continue Statement

Removed the early `continue` at line 1404 that was skipping contradictions without extracted slots:

```python
contra_slots = set(old_facts.keys()) & set(new_facts.keys())
# ✓ REMOVED: if not contra_slots: continue
```

### 3. Added Unstructured Matching Fallback

Added a new branch to handle contradictions when `extract_fact_slots` doesn't extract any facts:

```python
if not shared:
    # ... existing fuzzy matching for extracted slots ...
    if contra_slots:
        # Use extracted fact values for matching
    else:
        # ✓ NEW: Unstructured matching fallback
        # Extract unique words from old and new memories
        # Find which unique words appear in resolution text
        # Choose memory based on which words match
```

The unstructured matching:
1. Extracts all words from old and new memory texts (excluding stopwords)
2. Finds words unique to each memory
3. Checks which unique words appear in the resolution statement
4. If both appear, chooses based on which appears first
5. Creates a synthetic `_unstructured_` slot for the matching logic

### 4. Updated Resolution Logic

Modified the resolution matching logic to handle the synthetic `_unstructured_` slot:

```python
if slot == '_unstructured_':
    # Compare full memory texts to determine which to keep
    if user_fact == old_mem.text:
        chosen_memory_id = contra.old_memory_id
    elif user_fact == new_mem.text:
        chosen_memory_id = contra.new_memory_id
else:
    # Normal slot-based matching (existing code)
```

## Testing

Created two verification tests:

1. **test_nl_resolution_fix.py**: Verifies all 6 resolution patterns are detected correctly
   - ✅ All 6 patterns pass

2. **test_unstructured_matching.py**: Verifies unstructured matching logic works correctly
   - ✅ Coffee vs Tea: Correctly chooses "tea" (new value)
   - ✅ Single vs Married: Correctly chooses "married" (new value)
   - ✅ Blue vs Red: Correctly chooses "blue" (old value) when resolution says "blue was right, ignore the red"

## Expected Impact

With these fixes, the NL Resolution test should now pass **6/6 (100%)** instead of **1/6 (17%)**:

| Pattern | Before | After | Fix Applied |
|---------|--------|-------|-------------|
| "X is correct" | ❌ | ✅ | Unstructured matching |
| "Actually..." | ✅ | ✅ | Already worked |
| "I meant..." | ❌ | ✅ | Unstructured matching |
| "changed to..." | ❌ | ✅ | Fixed pattern + unstructured matching |
| "explicit confirm" | ❌ | ✅ | Unstructured matching |
| "keep OLD value" | ❌ | ✅ | New patterns + unstructured matching |

The overall stress test score should improve from **6/7 (86%)** to **7/7 (100%)**.

## Files Modified

- `personal_agent/crt_rag.py`: 
  - Lines 1348-1360: Expanded resolution patterns
  - Lines 1402-1487: Added unstructured matching fallback
  - Lines 1492-1537: Updated resolution logic for synthetic slot

## Notes

- The fix maintains backward compatibility with existing fact-slot-based resolution
- The unstructured matching is a fallback that only activates when fact extraction fails
- The synthetic `_unstructured_` slot is internal and not exposed to users
- All existing functionality remains intact, we only added new capabilities
