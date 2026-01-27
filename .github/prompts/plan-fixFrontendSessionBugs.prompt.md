# Plan: Fix Frontend Session Bugs

**Date:** 2026-01-27  
**Source:** Live frontend testing session  
**Priority:** High — these are user-facing bugs

---

## Bugs Identified

| # | Bug | Input | Expected | Actual |
|---|-----|-------|----------|--------|
| 1 | Name extraction malformed | "Hi I'm Nick Block" | `name = Nick Block` | `name = Nick and my` |
| 2 | Occupation not recalled | "I'm a Web Developer, Print Maker..." | All roles stored/retrieved | Only favorite_color returned |
| 3 | Color contradiction not detected | "orange" → "yellow" | Contradiction flagged | Silent overwrite |
| 4 | Multi-value not merged | "both yellow and orange" | `[yellow, orange]` | Only yellow kept |
| 5 | Project info ignored | CRT phase roadmap pasted | Some acknowledgment | Responded about favorite color |

---

## Bug 1: Name Extraction Malformed

**Symptom:** "Hi I'm Nick Block" → `name = Nick and my`

**Root Cause:** Regex pattern in `fact_slots.py` is capturing wrong groups or has a bug with "I'm" parsing.

**File:** `personal_agent/fact_slots.py`

**Debug Steps:**
```python
from personal_agent.fact_slots import extract_fact_slots
result = extract_fact_slots("Hi I'm Nick Block")
print(result)  # Check what's being extracted
```

**Likely Fix:** Find the name extraction pattern and fix the group capture:
```python
# Current (broken):
r"(?:i'm|i am|my name is)\s+(\w+)"  # Only captures "Nick"?

# Or pattern is matching something else entirely
```

---

## Bug 2: Occupation Not Recalled

**Symptom:** User stated roles, but "Who am I?" only returns favorite_color.

**Root Cause Options:**
1. Occupation facts not being extracted
2. Occupation facts not being stored
3. Retrieval not finding occupation memories
4. Response generation ignoring non-favorite_color facts

**Debug Steps:**
```python
# Check extraction
from personal_agent.fact_slots import extract_fact_slots
result = extract_fact_slots("I'm a Web Developer, Print Maker and cinematographer.")
print(result)  # Should have occupation slots

# Check memory storage
# Look at the database for this thread
```

**File:** `personal_agent/fact_slots.py` (extraction) or `personal_agent/crt_rag.py` (retrieval)

---

## Bug 3: Color Contradiction Not Detected

**Symptom:** "favorite color is orange" then "favorite color is yellow" — no contradiction flagged.

**This is the CORE CRT feature that's broken.**

**Root Cause Options:**
1. Same-slot update not triggering contradiction check
2. Drift threshold too high (values semantically different but not flagged)
3. Paraphrase gate suppressing (shouldn't for different colors)
4. Detection flow not reached for simple fact updates

**Debug Steps:**
```python
# Simulate the contradiction check
from personal_agent.crt_rag import CRTEnhancedRAG

rag = CRTEnhancedRAG()
# Store orange
rag.query("My favorite color is orange", thread_id="test")
# Store yellow - should trigger contradiction
result = rag.query("My favorite color is yellow", thread_id="test")
print(result.get("contradiction_detected"))
```

**Expected Flow:**
1. Extract `favorite_color = yellow`
2. Find prior `favorite_color = orange`
3. Compare: "orange" vs "yellow" → different values, same slot
4. Trigger contradiction → record in ledger → add caveat to response

**File:** `personal_agent/crt_rag.py` — `_check_all_fact_contradictions_ml()`

---

## Bug 4: Multi-Value Not Merged

**Symptom:** "actually both are my favorites its yellow and orange" → only yellow kept.

**Root Cause:** Phase 2.0 context-aware memory added the schema for multi-value, but the merge logic isn't implemented.

**Expected Behavior:**
- Detect "both X and Y" pattern
- Store as array: `favorite_color = [yellow, orange]`
- Or store as two separate facts with same slot

**File:** `personal_agent/fact_slots.py` — add "both X and Y" extraction pattern

**Pattern to Add:**
```python
MULTI_VALUE_PATTERNS = [
    r"both\s+(\w+)\s+and\s+(\w+)",
    r"(\w+)\s+and\s+(\w+)\s+are\s+(?:both\s+)?my\s+favorites?",
]
```

---

## Bug 5: Project Info Ignored

**Symptom:** User pasted CRT phase roadmap, system responded about favorite color.

**Root Cause:** 
- No "project" slot extractor
- Long text not parsed for semantic content
- Retrieval prioritized recent short facts

**This is lower priority** — the system isn't designed to store arbitrary project info.

**Potential Fix:** Add a `project_info` or `work_context` slot, but this is a feature request, not a bug.

---

## Priority Order

| Priority | Bug | Impact | Effort |
|----------|-----|--------|--------|
| 1 | Color contradiction not detected | Core feature broken | Medium |
| 2 | Name extraction malformed | User-facing bug | Small |
| 3 | Occupation not recalled | Memory retrieval broken | Medium |
| 4 | Multi-value not merged | Feature gap | Medium |
| 5 | Project info ignored | Feature request | Large |

---

## Implementation Plan

### Step 1: Debug Contradiction Detection (Bug 3)
1. Add logging to `_check_all_fact_contradictions_ml()`
2. Trace why "orange" → "yellow" doesn't trigger
3. Check if extraction, comparison, or recording is failing
4. Fix the broken step

### Step 2: Fix Name Extraction (Bug 1)
1. Find the regex pattern for name extraction
2. Test with "Hi I'm Nick Block"
3. Fix the capture group

### Step 3: Debug Occupation Retrieval (Bug 2)
1. Verify extraction works
2. Check if stored in DB
3. Check retrieval query
4. Fix whichever step is broken

### Step 4: Add Multi-Value Pattern (Bug 4)
1. Add "both X and Y" extraction pattern
2. Modify storage to handle arrays
3. Test merge behavior

---

## Quick Validation

After fixes, test this exact sequence:
```
1. "Hi I'm Nick Block"           → name = Nick Block
2. "My favorite color is orange" → favorite_color = orange
3. "I'm a Web Developer"         → occupation = Web Developer
4. "My favorite color is yellow" → CONTRADICTION DETECTED
5. "Who am I?"                   → Returns name, color, occupation
6. "Both yellow and orange"      → favorite_color = [yellow, orange]
```
