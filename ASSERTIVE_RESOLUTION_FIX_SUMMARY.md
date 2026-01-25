# Assertive Resolution Fix - Implementation Summary

## Overview
Implemented fixes to make contradiction resolution more robust by using `blocking_contradictions` dict data directly when memory lookup fails, as outlined in `plan-assertiveResolutionFix.prompt.md`.

## Changes Made

### 1. Enhanced `_resolve_contradiction_assertively()` Method
**File:** `personal_agent/crt_rag.py` (lines 1190-1270)

**Changes:**
- Added optional `blocking_data` parameter to method signature
- Implemented fallback logic when memory lookup fails (`unique_memories` is empty)
- When fallback triggers:
  - Uses `new_value` from `blocking_data` dict (most recent claim)
  - Creates synthetic `MemoryItem` with appropriate trust/confidence
  - Logs diagnostic message: "Memory lookup failed, using blocking_data fallback"

**Code Structure:**
```python
def _resolve_contradiction_assertively(
    self, 
    contradictions: List[ContradictionEntry],
    blocking_data: Optional[List[Dict[str, Any]]] = None
) -> Optional[MemoryItem]:
```

**Fallback Logic:**
```python
if not unique_memories:
    # Fallback: Use blocking_data if memory lookup failed
    if blocking_data:
        logger.info("[CONTRADICTION_RESOLVED] Memory lookup failed, using blocking_data fallback")
        newest = blocking_data[0] if blocking_data else None
        if newest and 'new_value' in newest:
            # Create synthetic memory item from new_value
            synthetic_mem = MemoryItem(...)
            return synthetic_mem
    return None
```

### 2. Updated `_check_contradiction_gates()` Method
**File:** `personal_agent/crt_rag.py` (lines 1312-1420)

**Changes:**
- Passes `blocking_contradictions` to `_resolve_contradiction_assertively()`
- Enhanced caveat building to use `blocking_contradictions` data directly
- Added secondary fallback path when `resolved_memory` is `None`:
  - Extracts `new_value` and `old_value` from `blocking_contradictions[0]`
  - Builds assertive answer with caveat: `"{new_value} (changed from {old_value})"`
  - Returns `True` (gates pass) instead of blocking
  - Only falls back to questioning behavior if all resolution attempts fail

**Key Logic:**
```python
# Primary resolution path (with blocking_data parameter)
resolved_memory = self._resolve_contradiction_assertively(relevant_contras, blocking_contradictions)

if resolved_memory:
    # ... build answer with caveat from blocking_contradictions
    return True, assertive_answer, blocking_contradictions

# Secondary fallback: Use blocking_contradictions dict data directly
if blocking_contradictions:
    first_contra = blocking_contradictions[0]
    new_value = self._extract_value_from_memory_text(first_contra.get('new_value', ''))
    old_value = self._extract_value_from_memory_text(first_contra.get('old_value', ''))
    
    if new_value:
        caveat = f"(changed from {old_value})" if old_value else "(most recent update)"
        assertive_answer = f"{new_value} {caveat}"
        return True, assertive_answer, blocking_contradictions
```

### 3. Enabled Auto-Resolution in Config
**File:** `crt_runtime_config.json` (line 9)

**Change:**
```json
"auto_resolve_contradictions_enabled": true  // Changed from false
```

## Behavior Changes

### Before
When memory lookup failed in `_resolve_contradiction_assertively()`:
1. Returned `None`
2. Fallback in `_check_contradiction_gates()` would build "Which is correct?" messages
3. User would be asked to manually resolve the contradiction
4. Gates would block (return `False`)

### After
When memory lookup fails:
1. Primary: `_resolve_contradiction_assertively()` creates synthetic memory from `blocking_data`
2. Secondary: `_check_contradiction_gates()` extracts values from `blocking_contradictions` dict
3. System picks `new_value` (more recent) and adds caveat "(changed from {old_value})"
4. Returns assertive answer
5. Gates pass (return `True`)
6. Only asks "Which is correct?" if all resolution attempts fail

## Resolution Strategy

**Priority Order:**
1. **Memory-based resolution** (existing): Pick highest trust + most recent from memory system
2. **Synthetic memory fallback** (new): Create memory from `blocking_data` when lookup fails
3. **Direct dict extraction** (new): Use `new_value` from `blocking_contradictions` dict
4. **User query** (last resort): Fall back to asking user for clarification

**Value Selection Logic:**
- Always prefer `new_value` (most recent claim)
- Add caveat disclosure: "(changed from {old_value})"
- If multiple old values exist: "(changed from X, Y, Z)"

## Testing Validation
Created `test_assertive_fix.py` to validate:
- ✓ Imports work correctly
- ✓ `blocking_data` parameter exists in method signature
- ✓ Config has `auto_resolve_contradictions_enabled: true`

## Further Considerations (from plan)

### 1. What if both values are equally old?
**Current implementation:** Uses timestamp as secondary sort key after trust. If truly tied, insertion order is preserved (stable sort).

**Recommended enhancement:** Could add explicit tie-breaking:
- Newest by timestamp (already done)
- Highest trust (already done)
- Newest insert order (stable sort already provides this)

### 2. Should we log resolution decisions?
**Current implementation:** Option B (Debug log)
- Logs to `logger.info()` with `[CONTRADICTION_RESOLVED]` prefix
- Includes chosen value, trust score, timestamp
- Logs fallback path with `[GATE_CHECK]` prefix

**Alternatives:**
- Option A: Silent (not recommended - debugging would be hard)
- Option C: Audit trail in ledger (future enhancement)

### 3. Multi-slot contradictions in one query?
**Current implementation:** Handles first 3 in fallback messages
- Primary resolution handles all contradictions in `relevant_contras` list
- Fallback uses `blocking_contradictions[0]` (first one)

**Recommended enhancement:** Could iterate through all `blocking_contradictions` and resolve each assertively, then combine answers.

## Impact
- **Reduces** user friction by avoiding unnecessary "Which is correct?" questions
- **Maintains** transparency via caveat disclosure "(changed from X)"
- **Improves** robustness when memory IDs are stale/missing
- **Enables** background auto-resolution via config flag

## Files Modified
1. `personal_agent/crt_rag.py` - Core resolution logic (2 methods)
2. `crt_runtime_config.json` - Enable auto-resolution flag
3. `test_assertive_fix.py` - Validation test (new file)

## Next Steps
- Run existing test suite to ensure no regressions
- Monitor `[CONTRADICTION_RESOLVED]` logs to see fallback frequency
- Consider implementing audit trail (Option C from Further Considerations)
- Consider multi-slot resolution enhancement (Consideration #3)
