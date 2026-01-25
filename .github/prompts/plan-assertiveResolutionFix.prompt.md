# Plan: Assertive Resolution Fix

**TL;DR:** The resolution infrastructure exists but fails silently when memory lookup fails. The fix makes the fallback use `blocking_contradictions` dict data directly (which already has old/new values) instead of asking "which is correct?"

---

## Steps

### 1. Fix fallback in `_check_contradiction_gates()` in [crt_rag.py](personal_agent/crt_rag.py)

When `_resolve_contradiction_assertively()` returns `None`, instead of building "Which is correct?" messages, extract values from `blocking_contradictions` dict and pick the `new_value` (more recent) with caveat "(changed from {old_value})"

### 2. Make `_resolve_contradiction_assertively()` more robust in [crt_rag.py](personal_agent/crt_rag.py)

Add optional `blocking_data` parameter to use when memory lookup fails. Extract `new_value` and `old_value` from the dict instead of requiring memory IDs.

### 3. Enable `auto_resolve_contradictions_enabled` in [crt_runtime_config.json](crt_runtime_config.json)

Change from `false` to `true` to enable the assertive path by default.

---

## Further Considerations

1. **What if both values are equally old?** 
   - Recommend: Pick newest by timestamp, if tie → pick highest trust, if tie → pick newest insert order

2. **Should we log resolution decisions?** 
   - Option A: Silent 
   - Option B: Debug log 
   - Option C: Audit trail in ledger

3. **Multi-slot contradictions in one query?** 
   - Current: Handle first 3 
   - Alternative: Resolve all assertively
