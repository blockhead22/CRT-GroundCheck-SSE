# Quick Reference Card

**Status:** 71.4% achieved (25/35) | **Target:** 80% (28/35) | **Gap:** 3 turns

---

## Critical File Locations

| What | Where | Key Lines |
|------|-------|-----------|
| Pattern definitions | [personal_agent/fact_slots.py](personal_agent/fact_slots.py) | 78-120 |
| Extract functions | [personal_agent/fact_slots.py](personal_agent/fact_slots.py) | 200-280 |
| Numeric contradiction | [personal_agent/crt_core.py](personal_agent/crt_core.py) | ~920-950 |
| Main detection flow | [personal_agent/crt_rag.py](personal_agent/crt_rag.py) | 1800-2100 |
| Denial methods | [personal_agent/crt_rag.py](personal_agent/crt_rag.py) | 2250-2280 |
| NL resolution patterns | [personal_agent/resolution_patterns.py](personal_agent/resolution_patterns.py) | 20-25 |
| Test harness | [tools/adversarial_crt_challenge.py](tools/adversarial_crt_challenge.py) | Main |

---

## Quick Test Commands

```powershell
# Single turn
python tools/adversarial_crt_challenge.py --turns 7

# Range
python tools/adversarial_crt_challenge.py --turns 7-10

# All 35
python tools/adversarial_crt_challenge.py --turns 35

# With UTF-8
$env:PYTHONIOENCODING="utf-8"; python tools/adversarial_crt_challenge.py --turns 35
```

---

## Current Score Breakdown

```
BASELINE (5/5):     100% ✅
TEMPORAL (3.5/5):    70% ⚠️  
SEMANTIC (4/5):      80% ✅
IDENTITY (5/5):     100% ✅
NEGATION (2.5/5):    50% ❌
DRIFT (2.5/5):       50% ❌
STRESS (2.5/5):      50% ❌
────────────────────────────
TOTAL (25/35):      71.4%
TARGET (28/35):      80.0%
REMAINING:           3 turns
```

---

## Turns Status

### Already Passing (25 turns) ✅
Baseline: 1, 2, 4, 5, 6  
Temporal: 7, 8, 9, 10  
Semantic: 11, 12, 13, 14, 15  
Identity: 16, 17, 18, 19, 20  
Negation: 21, 22  
Drift: 27, 28  
Stress: 30  

### Known Failures (10 turns) ❌
- **Turn 23** - DENIAL "I never said I had a PhD"
- **Turn 24** - RETRACTION "Actually, I do have a PhD"
- **Unknown** - Database/edge case issue
- Others: 3, 25, 29, 31, 32, 34, 35, 36

---

## Implementation Path (70 minutes total)

### Phase 1: Turn 23 (10 min)
```python
# File: crt_rag.py line ~1940
denied_fact = self._detect_denial_in_text(user_query)
if denied_fact:
    # Find matching previous fact
    # Record as DENIAL contradiction
```

### Phase 2: Turn 24 (10 min)
```python
# File: crt_rag.py line ~1960
if self._is_retraction_of_denial(user_query):
    # Find recent DENIAL entry
    # Record as RETRACTION_OF_DENIAL
```

### Phase 3: Unknown Turn (30-50 min)
```powershell
# Run test 5 times, note which turn varies
for ($i=1; $i -le 5; $i++) {
    python tools/adversarial_crt_challenge.py --turns 35
}
```

---

## Key Bug Fixes Applied

| Bug | Location | Fix | Impact |
|-----|----------|-----|--------|
| Slot matching OR | crt_rag.py:1920 | Changed to AND | ⬆️ Eliminated cross-slot matching |
| Early return | crt_rag.py:1925 | Added continue | ⬆️ Checks all slots per turn |
| Broad "actually" | resolution_patterns.py:21 | Added context | ⬆️ Fixed Turn 7 misclassification |

---

## Common Pitfalls

| Issue | Symptom | Fix |
|-------|---------|-----|
| Wrong variable | Function undefined | Check imports at top |
| OR logic | Wrong slots match | Change to AND logic |
| Early return | Blocks iteration | Add continue statement |
| Broad pattern | False positives | Add regex context |
| DB persistence | Score varies | Run with clean DB |
| Unicode errors | Terminal mojibake | Set PYTHONIOENCODING |

---

## Success Checklist

Before Commit:
- [ ] Test passes in isolation (`--turns 23`)
- [ ] No regressions on baseline (`--turns 1-5`)
- [ ] Full test run shows ≥ previous score
- [ ] No debug print statements remain
- [ ] All imports present
- [ ] Code follows existing patterns
- [ ] Comments explain logic

---

## Database

### Location
```
d:\AI_round2\crt_memory.db        # Facts and memories
d:\AI_round2\crt_ledger.db        # Contradictions
```

### Check State
```python
from personal_agent.memory_vault import ContradictionLedger
ledger = ContradictionLedger()
print(f"Total contradictions: {len(ledger.get_all())}")
```

### Clean for Testing
```powershell
Remove-Item crt_memory.db -ErrorAction SilentlyContinue
Remove-Item crt_ledger.db -ErrorAction SilentlyContinue
```

---

## Documentation References

| Doc | Purpose | Read Time |
|-----|---------|-----------|
| [SESSION_COMPLETE.md](SESSION_COMPLETE.md) | **This session overview** | 15 min |
| [NEXT_STEPS.md](NEXT_STEPS.md) | **Implementation guide** | 10 min |
| [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) | Code structure & details | 20 min |
| [PATTERN_FIXES_SESSION.md](PATTERN_FIXES_SESSION.md) | Full history & debugging | 30 min |
| [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) | Continuation guide | 15 min |

---

## Call Stack: How Turn 7 Works

```
USER INPUT (Turn 7): "Wait, I'm actually 34, not 32. I always forget my age."

1. Store memory
   → memory_id=7, text="Wait, I'm actually 34, not 32..."

2. Extract facts  
   → age=34 (from "actually 34")

3. Check contradictions
   → _check_all_fact_contradictions_ml()
   → Find previous memory (Turn 2: age=32)
   
4. Pattern detection
   → detect_correction_type(user_query)
   → extract_direct_correction() matches pattern
   → Returns ("direct_correction", "32", "34")
   
5. Slot matching
   → old_val="32", prev_value="32" ✅ MATCH
   → new_val="34", new_value="34" ✅ MATCH
   → slot_matches = True
   
6. Record contradiction
   → type="REVISION"
   → confidence=0.95
   → RETURN TRUE

RESULT: Turn 7 = ✅ DETECTED
```

---

## Important Notes

⚠️ **Database state matters** - Contradictions persist between test runs  
⚠️ **Pattern order matters** - Check specific before general  
⚠️ **Regex can be tricky** - Test patterns in isolation first  
⚠️ **AND not OR** - Slot matching requires both old and new to match  
⚠️ **Continue not return** - Let loop complete unless truly done  

---

## Next Agent: Start Here

1. Read this page (2 min)
2. Run test: `python tools/adversarial_crt_challenge.py --turns 35`
3. Verify current score = 71.4%
4. Read [NEXT_STEPS.md](NEXT_STEPS.md) (10 min)
5. Implement Turn 23 denial (10 min)
6. Implement Turn 24 retraction (10 min)
7. Find unknown turn (20-50 min)
8. Verify score ≥ 80%
9. Create final summary

**Total time estimate: 90 minutes**  
**Confidence of success: HIGH**

---

**Created:** 2026-01-26  
**Session Score:** 71.4% (25/35)  
**Target Score:** 80% (28/35)  
**Ready for:** Next iteration
