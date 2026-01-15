# Semantic Anchor Implementation - Complete

**Date:** January 15, 2026  
**Status:** ✅ Core implementation complete, ready for M2 integration testing

---

## What We Built

### 1. Core Semantic Anchor Module ([personal_agent/crt_semantic_anchor.py](personal_agent/crt_semantic_anchor.py))

**SemanticAnchor dataclass** - Binds contradiction follow-ups to their context:
- **Identity**: contradiction_id, turn_number
- **Conflict structure**: old/new memory IDs, text, contradiction type
- **Semantic binding**: slot name, values, drift vector
- **Question context**: clarification prompt, expected answer type
- **Resolution**: user answer, method, timestamp

**Key functions:**
- `generate_clarification_prompt()` - Type-aware question generation
- `parse_user_answer()` - Keyword-based resolution parsing
- `is_resolution_grounded()` - Validation gate for resolutions

### 2. Ledger Integration ([personal_agent/crt_ledger.py](personal_agent/crt_ledger.py))

**New methods:**
- `create_semantic_anchor()` - Generate anchor from contradiction entry
- `_determine_expected_answer_type()` - Map contradiction type to answer format

**Enhanced classification:**
- Fixed `_classify_contradiction()` to detect REFINEMENT/REVISION/TEMPORAL/CONFLICT
- Uses keyword detection, containment checks, seniority pairs, semantic similarity

### 3. API Integration ([crt_api.py](crt_api.py))

**ContradictionWorkItem model:**
- Added `semantic_anchor` field (optional Dict)

**Updated endpoints:**
- `GET /api/contradictions/next` - Returns semantic anchor with work items
- `POST /api/contradictions/respond` - Uses anchor to parse user answers
  - Parses answer using `parse_user_answer()`
  - Validates grounding with `is_resolution_grounded()`
  - Falls back to request params if parsing fails

**_work_item_for_entry() enhancement:**
- Retrieves memory texts for old/new contradictions
- Creates semantic anchor on-the-fly
- Serializes to dict for API response

### 4. Test Harness ([crt_stress_test.py](crt_stress_test.py))

**M2 smoke test updates:**
- Validates semantic anchor presence in `/next` responses
- Logs anchor metadata in verbose mode
- Warns if anchor creation fails (degraded mode)

### 5. Validation Tests ([test_semantic_anchor_flow.py](test_semantic_anchor_flow.py))

**Test coverage:**
- ✅ Semantic anchor creation and serialization
- ✅ Type-aware question generation (4 types tested)
- ✅ Answer parsing with memory ID extraction
- ✅ Grounding validation (positive/negative cases)

---

## How It Works

### Type-Aware Question Generation

Each contradiction type gets a specialized prompt:

**REFINEMENT** (Seattle → Bellevue):
```
I have two values for location: 'Seattle' and 'Bellevue'. 
Did you mean to be more specific, or are both correct?
```

**REVISION** (Microsoft → Amazon + "actually"):
```
You told me employer = 'Microsoft', but now you said 'Amazon'. 
Which is correct?
```

**TEMPORAL** (Senior → Principal):
```
I have employer = 'Senior Engineer' from earlier, and now 'Principal Engineer'. 
Did the situation change over time, or which is current?
```

**CONFLICT** (Microsoft vs Google):
```
I have conflicting values for employer: 'Microsoft' vs 'Google'. 
These can't both be true - which is correct?
```

### Answer Parsing

Keyword-based parsing extracts resolution intent:

| User Answer | Detected Method | Chosen Memory |
|-------------|----------------|---------------|
| "The new one is correct" | `user_chose_new` | new_memory_id |
| "The first one was right" | `user_chose_old` | old_memory_id |
| "Both are true" | `both_true_temporal` | None |
| "Actually both wrong" | `both_wrong` | None |
| "Amazon is correct" | `user_clarified` | (extracts value) |

### Grounding Validation

Before accepting a resolution, we check:
1. **Memory ID consistency**: If method is `user_chose_old`, chosen_id must be old_memory_id
2. **Slot value coherence**: If slot-based, parsed value should relate to old/new values
3. **Confidence threshold**: Must be ≥ 0.3 to be considered grounded

---

## API Flow Example

**1. User creates contradiction:**
```python
POST /api/chat/send
{
  "query": "I work at Microsoft",
  "thread_id": "user_123"
}

POST /api/chat/send
{
  "query": "Actually, I work at Amazon, not Microsoft",
  "thread_id": "user_123"
}
```

**2. System detects contradiction:**
- Creates ledger entry (type=REVISION, drift=0.65)
- Classification: "revision" (keyword "Actually")

**3. Client polls for next contradiction:**
```python
GET /api/contradictions/next?thread_id=user_123
```

**Response:**
```json
{
  "has_item": true,
  "item": {
    "ledger_id": "contra_123",
    "contradiction_type": "revision",
    "suggested_question": "You told me employer = 'Microsoft', but now...",
    "semantic_anchor": {
      "contradiction_id": "contra_123",
      "contradiction_type": "revision",
      "old_memory_id": "mem_456",
      "new_memory_id": "mem_789",
      "old_text": "I work at Microsoft",
      "new_text": "Actually, I work at Amazon",
      "slot_name": "employer",
      "old_value": "Microsoft",
      "new_value": "Amazon",
      "clarification_prompt": "You told me employer = 'Microsoft'...",
      "expected_answer_type": "choose_one"
    }
  }
}
```

**4. User responds:**
```python
POST /api/contradictions/respond
{
  "thread_id": "user_123",
  "ledger_id": "contra_123",
  "answer": "The new one is correct, I work at Amazon",
  "resolve": true
}
```

**Backend parsing:**
1. Retrieves anchor from contradiction entry
2. Calls `parse_user_answer(anchor, "The new one is correct...")`
3. Result: `{"resolution_method": "user_chose_new", "chosen_memory_id": "mem_789", "confidence": 0.8}`
4. Validates with `is_resolution_grounded()` → True
5. Resolves contradiction with parsed method/memory

---

## What's Next

### Immediate Testing (Item #9)
- Start API server on port 8123
- Run M2 smoke test: `crt_stress_test.py --m2-smoke --m2-followup-verbose`
- Verify anchor appears in `/next` response
- Check that parsing happens in `/respond` logs

### Expected Outcomes
- **Success scenario**: M2 followup success rate increases from 12% → 40%+
- **Diagnostic scenario**: Failures now show which parsing/grounding check failed
- **Gate pass rate**: May temporarily drop (stricter validation) before improving

### Known Limitations
1. **Answer parsing is keyword-based** - Can be fooled by adversarial phrasing
2. **No learned model yet** - Future: train on resolution corpus
3. **Turn number tracking** - Currently hardcoded to 0, needs proper tracking
4. **Slot extraction** - Not yet wired into anchor creation from real memory

### Next Enhancements (Future Work)
- Add learned answer parser (train on stress test resolution logs)
- Wire slot extraction from `crt_slots.py` into anchor creation
- Add anchor metadata to audit trail (why was this resolution accepted?)
- Create dedicated M2 resolution gate (like existing response gates)

---

## Testing Commands

**Unit tests:**
```bash
python test_semantic_anchor_flow.py
```

**M2 smoke test:**
```bash
python crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 \
  --thread-id m2_smoke --m2-smoke --m2-followup-verbose
```

**Full stress test with M2:**
```bash
python crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 \
  --thread-id m2_test --reset-thread --turns 100 \
  --m2-followup --m2-followup-max 10
```

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| personal_agent/crt_semantic_anchor.py | **NEW** - Core semantic anchor module | 268 |
| personal_agent/crt_ledger.py | Added anchor creation methods | +60 |
| crt_api.py | Added anchor to API responses, parsing logic | +80 |
| crt_stress_test.py | Added anchor validation to M2 smoke test | +10 |
| test_semantic_anchor_flow.py | **NEW** - Validation tests | 240 |

**Total:** ~660 lines of new/modified code

---

## Success Metrics

**Before semantic anchors:**
- M2 followup success: 12% (3/25 in stress tests)
- Gate rejection of followups: 88% (correct - weak grounding)
- Contradiction types: All treated as CONFLICT
- Answer parsing: None (used raw request params)

**After semantic anchors (expected):**
- M2 followup success: 40-60% (grounded parsing)
- Type-aware questions: 4 distinct phrasings
- Resolution grounding: Validated before acceptance
- Failure diagnosis: Can see which step failed (parse/ground/classify)

**Ultimate goal (with learned model):**
- M2 followup success: 80%+ 
- Answer parsing confidence: 0.9+
- Zero silent acceptance of ungrounded resolutions
