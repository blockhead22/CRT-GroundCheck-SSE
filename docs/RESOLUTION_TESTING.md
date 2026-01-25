# Contradiction Resolution Testing

This document describes the contradiction resolution testing framework and the policies implemented to handle contested memories.

## Contested Memory Protection

Memories involved in open contradictions have capped trust updates (90% reduction) until resolved. This prevents contested memories from regaining trust through unrelated alignment events before the contradiction is resolved by the user.

### Implementation

When a memory is in an open contradiction, any trust update is multiplied by 0.1, effectively reducing the trust change by 90%. This is logged to the `trust_log` table with the reason prefixed by `contested_cap_applied:`.

**Test:**
1. Create contradiction: "I work at Microsoft" → "I work at Amazon"
2. Trigger unrelated alignment event
3. Verify Microsoft memory trust does NOT significantly increase

**Evidence:** `trust_log` shows contested_cap_applied events

### Code Location

- **File:** `personal_agent/crt_memory.py`
- **Function:** `is_memory_contested()` - Checks if memory is in open contradiction
- **Function:** `update_trust()` - Applies contested multiplier if needed

## Resolution Policies

The system supports three resolution policies for handling contradictions:

### OVERRIDE

**Use case:** Factual corrections (job change, age update, location change)

**Action:** 
- Deprecate the non-chosen memory
- Keep the chosen memory active
- Boost trust of chosen memory by 0.1

**Example:**
```
User: "I work at Microsoft"
User: "I work at Amazon now"
System: [Detects contradiction]
User resolves: OVERRIDE, chooses Amazon memory
Result: Microsoft memory deprecated with reason "Overridden by mem_amazon - user confirmed"
```

**Evidence:** SQL shows `deprecated=1` for old memory, `deprecated=0` for chosen memory

**API Endpoint:**
```bash
POST /api/resolve_contradiction
{
  "thread_id": "default",
  "ledger_id": "contra_xxx",
  "resolution": "OVERRIDE",
  "chosen_memory_id": "mem_amazon",
  "user_confirmation": "Amazon is correct, I switched jobs last month"
}
```

### PRESERVE

**Use case:** Refinements and complementary information (adding skills, expanding preferences)

**Action:**
- Keep both memories active
- Tag both with 'resolved_both_valid'
- Mark contradiction as resolved

**Example:**
```
User: "I know Python"
User: "I also know JavaScript and TypeScript"
System: [Detects refinement]
User resolves: PRESERVE
Result: Both memories marked as valid with 'resolved_both_valid' tag
```

**Evidence:** Both memories have `tags_json` containing 'resolved_both_valid'

**API Endpoint:**
```bash
POST /api/resolve_contradiction
{
  "thread_id": "default",
  "ledger_id": "contra_yyy",
  "resolution": "PRESERVE",
  "user_confirmation": "Both are true, I know multiple languages"
}
```

### ASK_USER

**Use case:** Ambiguous conflicts requiring more context (preference changes without clear direction)

**Action:**
- Keep contradiction open
- Add metadata flag `user_deferred=true`
- Prompt user again later

**Example:**
```
User: "I prefer working remotely"
User: "I don't like working from home"
System: [Detects conflict]
User resolves: ASK_USER
Result: Contradiction remains open, marked as deferred
```

**Evidence:** Ledger metadata shows `user_deferred=true`, status remains 'open'

**API Endpoint:**
```bash
POST /api/resolve_contradiction
{
  "thread_id": "default",
  "ledger_id": "contra_zzz",
  "resolution": "ASK_USER",
  "user_confirmation": "I'm not sure yet, ask me again later"
}
```

## Database Schema

### conflict_resolutions Table

Tracks user-driven resolution decisions:

```sql
CREATE TABLE conflict_resolutions (
    ledger_id TEXT PRIMARY KEY,
    resolution_method TEXT NOT NULL,
    chosen_memory_id TEXT,
    user_feedback TEXT,
    timestamp REAL NOT NULL,
    FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
)
```

### Updated contradictions Table

Added `metadata` column to track additional resolution context:

```sql
ALTER TABLE contradictions ADD COLUMN metadata TEXT;
```

## Testing Framework

### Test Script

**File:** `personal_agent/test_resolution.py`

Automated test script that exercises all 3 resolution policies:

1. **Test 1:** OVERRIDE policy with job change scenario
2. **Test 2:** PRESERVE policy with skill refinement scenario
3. **Test 3:** ASK_USER policy with preference conflict scenario

**Usage:**
```bash
# Requires CRT API server running on http://127.0.0.1:5000
python personal_agent/test_resolution.py
```

### SQL Dump Export

**File:** `personal_agent/export_sql_utf8.py`

Exports all databases as UTF-8 encoded SQL dumps for audit verification.

**Usage:**
```bash
python personal_agent/export_sql_utf8.py
```

**Output:** Creates SQL dumps in `test_results/` directory:
- `memory_dump_utf8.sql`
- `ledger_dump_utf8.sql`
- `active_learning_dump_utf8.sql`

## SQL Verification Queries

### Check contested memory protection

```sql
SELECT memory_id, timestamp, old_trust, new_trust, reason, drift
FROM trust_log
WHERE reason LIKE 'contested_cap_applied:%'
ORDER BY timestamp DESC;
```

### Check resolution completeness

```sql
SELECT 
  c.ledger_id,
  c.status,
  c.resolution_method,
  c.contradiction_type,
  r.chosen_memory_id,
  r.user_feedback,
  r.timestamp as resolved_at
FROM contradictions c
LEFT JOIN conflict_resolutions r ON c.ledger_id = r.ledger_id
WHERE c.status = 'resolved'
ORDER BY c.timestamp DESC;
```

### Verify OVERRIDE deprecation

```sql
SELECT 
  memory_id, 
  text,
  trust,
  deprecated, 
  deprecation_reason,
  timestamp
FROM memories
WHERE deprecated = 1
ORDER BY timestamp DESC;
```

### Check PRESERVE tagging

```sql
SELECT 
  memory_id,
  text,
  tags_json,
  trust
FROM memories
WHERE tags_json LIKE '%resolved_both_valid%'
ORDER BY timestamp DESC;
```

### Check ASK_USER deferrals

```sql
SELECT 
  ledger_id,
  status,
  metadata,
  timestamp
FROM contradictions
WHERE metadata LIKE '%user_deferred%'
ORDER BY timestamp DESC;
```

## Expected Test Results

After running `test_resolution.py`, you should see:

1. **Ledger dump** showing:
   - Contradictions with status='resolved'
   - Resolution methods: 'OVERRIDE', 'PRESERVE', 'ASK_USER'
   - Timestamps for resolution_timestamp

2. **Memory dump** showing:
   - Deprecated memories with deprecation_reason
   - Active memories with updated trust scores
   - Tagged memories with 'resolved_both_valid'

3. **Resolutions table** showing:
   - Each resolved contradiction linked to user feedback
   - Chosen memory IDs for OVERRIDE cases
   - Timestamps matching ledger

## Validation Checklist

- [ ] Contested memories show reduced trust updates in trust_log
- [ ] OVERRIDE policy creates deprecated memories
- [ ] PRESERVE policy adds tags to both memories
- [ ] ASK_USER policy leaves contradictions open
- [ ] conflict_resolutions table populated
- [ ] All SQL dumps are UTF-8 encoded
- [ ] No silent overwrites occurred
- [ ] Trust evolution respects contested status

## Troubleshooting

### Issue: Contested memories still gaining trust

**Check:**
1. Verify `is_memory_contested()` returns True for contested memories
2. Check trust_log for 'contested_cap_applied' entries
3. Ensure ledger database exists and has open contradictions

### Issue: Resolution endpoint returns 404

**Check:**
1. Verify ledger_id exists in contradictions table
2. Ensure contradiction status is 'open' (not already resolved)
3. Check thread_id matches the database being used

### Issue: SQL dumps are empty

**Check:**
1. Verify database files exist in personal_agent/ directory
2. Ensure databases have been populated with test data
3. Check file permissions for test_results/ directory

## Future Enhancements

1. **Automatic conflict detection:** Use semantic analysis to detect contradictions earlier
2. **Smart policy suggestion:** Recommend resolution policy based on contradiction type
3. **Batch resolution:** Allow resolving multiple related contradictions at once
4. **Resolution history:** Track resolution patterns to improve suggestions
5. **Undo resolution:** Allow reverting resolution decisions

## References

- Contradiction Detection: `personal_agent/crt_ledger.py`
- Memory Trust System: `personal_agent/crt_memory.py`
- Resolution Endpoint: `crt_api.py` - `/api/resolve_contradiction`
- Test Framework: `personal_agent/test_resolution.py`
