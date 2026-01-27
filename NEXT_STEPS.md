# Quick Start: Next Steps to Reach 80%

**Current Score:** 71.4% (25/35 turns)  
**Target Score:** 80% (28/35 turns)  
**Gap:** Need to detect 3 more turns  
**Turns Identified:** Turn 23 (denial), Turn 24 (retraction)  
**Unknown Turn:** TBD (varies, possibly database-related)

---

## Turn 23: Denial Detection

**Input Text:**
```
"I never said I had a PhD. I have a Master's degree."
```

**Expected Output:**
```
CORRECT - Turn 23: ASSERTION denial_of_fact contradiction detected
  Previous memory (Turn 3): "I have a PhD in Computer Science"
  New assertion: "I never said I had a PhD"
  Contradiction type: DENIAL
```

**Implementation Path:**

1. **File:** `personal_agent/crt_rag.py`
2. **Method:** Update `_check_all_fact_contradictions_ml()` 
3. **New Logic:**
   ```python
   # Add after pattern detection section (around line 1940)
   
   # ===== PRIORITY 3: DENIAL DETECTION =====
   denied_fact = self._detect_denial_in_text(user_query)
   if denied_fact:
       # Try to find this fact in previous memories
       for prev_mem in previous_user_memories:
           prev_facts = extract_fact_slots(prev_mem.text) or {}
           for slot, prev_fact in prev_facts.items():
               prev_value_str = str(prev_fact.value).lower().strip()
               
               # Check if denied fact matches this previous fact
               if denied_fact.lower() in prev_value_str:
                   contradiction_entry = {
                       "memory_id": new_memory.memory_id,
                       "previous_memory_id": prev_mem.memory_id,
                       "slot": slot,
                       "old_value": prev_value_str,
                       "new_value": f"DENIED: {denied_fact}",
                       "contradiction_type": "DENIAL",
                       "confidence": 0.95,
                       "reason": f"User denied claiming '{denied_fact}' but memory shows '{prev_value_str}'",
                   }
                   return True, contradiction_entry
   ```

4. **Test Command:**
   ```powershell
   python tools/adversarial_crt_challenge.py --turns 23-24
   ```

5. **Success Criteria:**
   - Turn 23 shows: `CORRECT - Turn 23: ASSERTION denial_of_fact contradiction detected`
   - Score for this range should be 1/2 (at least Turn 23)

---

## Turn 24: Retraction Detection

**Input Text:**
```
"Actually no, I do have a PhD. I was testing you."
```

**Expected Output:**
```
CORRECT - Turn 24: ASSERTION retraction_of_denial contradiction detected
  Previous assertion (Turn 23): "I never said I had a PhD"
  New assertion: "Actually, I do have a PhD"
  Contradiction type: RETRACTION_OF_DENIAL
  Links to: Turn 3 (original PhD claim)
```

**Implementation Path:**

1. **File:** `personal_agent/crt_rag.py`
2. **Method:** Update `_check_all_fact_contradictions_ml()`
3. **New Logic:**
   ```python
   # Add after denial detection section (around line 1965)
   
   # ===== PRIORITY 4: RETRACTION OF DENIAL =====
   if self._is_retraction_of_denial(user_query):
       # Look specifically for the most recent DENIAL type contradiction
       recent_denials = [
           m for m in self.contradiction_ledger.get_all()
           if m["contradiction_type"] == "DENIAL"
           and m["memory_id"] < new_memory.memory_id  # Before current turn
       ]
       
       if recent_denials:
           # Get the most recent denial
           last_denial = sorted(recent_denials, key=lambda x: x["memory_id"])[-1]
           
           # Create retraction entry
           contradiction_entry = {
               "memory_id": new_memory.memory_id,
               "previous_memory_id": last_denial["memory_id"],
               "slot": last_denial["slot"],
               "old_value": last_denial["new_value"],  # What was denied
               "new_value": last_denial["old_value"],  # Original fact restored
               "contradiction_type": "RETRACTION_OF_DENIAL",
               "confidence": 0.95,
               "reason": f"User retracted denial: now affirms '{last_denial['old_value']}'",
           }
           return True, contradiction_entry
   ```

4. **Test Command:**
   ```powershell
   python tools/adversarial_crt_challenge.py --turns 23-24
   ```

5. **Success Criteria:**
   - Turn 23: `CORRECT - denial`
   - Turn 24: `CORRECT - retraction_of_denial`
   - Score for this range: 2/2

---

## Finding the Unknown 3rd Turn

**Strategy:**

1. **Run multiple test iterations:**
   ```powershell
   # Run 5 times to see which turn varies
   for ($i=1; $i -le 5; $i++) {
       Write-Host "=== RUN $i ===" 
       python tools/adversarial_crt_challenge.py --turns 35 | Select-String "OVERALL|SCORE|Turn"
   }
   ```

2. **Database state investigation:**
   ```powershell
   # Check if contradictions from previous runs persist
   python -c "
   from personal_agent.memory_vault import ContradictionLedger
   ledger = ContradictionLedger()
   print(f'Total contradictions: {len(ledger.get_all())}')
   for c in ledger.get_all()[-5:]:
       print(f'  Turn {c[\"memory_id\"]}: {c[\"slot\"]} = {c[\"contradiction_type\"]}')
   "
   ```

3. **Common candidates:**
   - **Turn 10 (first Temporal phase):** Maybe timing context issue
   - **Turn 15 (Semantic drift):** Multi-meaning variations  
   - **Turn 25 (second Stress):** Complex compound contradictions
   - **Turn 30 (late Stress):** Database state corruption

4. **Fix approach:**
   - Clean database before test: Delete all contradictions/memories
   - Run test in isolation (no other processes)
   - Use fresh Python session: `-n` flag or subprocess
   - Add explicit cleanup in test harness

---

## Testing Strategy

### Quick Test (Single Turn)
```powershell
python tools/adversarial_crt_challenge.py --turns 23
```
Expected: One line showing result for Turn 23

### Range Test (Related Turns)
```powershell
python tools/adversarial_crt_challenge.py --turns 7-10
```
Expected: 4 turns (our fixed 7 & 9 should be passing)

### Full Test (All 35)
```powershell
python tools/adversarial_crt_challenge.py --turns 35
```
Expected: Score breakdown by phase

### Debugging Test (With Verbose Output)
```powershell
# Temporarily add to crt_rag.py:
# logger.info(f"[DENIAL_CHECK] Text: {user_query[:100]}...")
# logger.info(f"[DENIAL_CHECK] Denial detected: {denied_fact}")

python tools/adversarial_crt_challenge.py --turns 23
```

---

## Code Locations Reference

### If you need to modify:
- **Denial logic:** [crt_rag.py](personal_agent/crt_rag.py) lines ~2300-2350
- **Retraction logic:** [crt_rag.py](personal_agent/crt_rag.py) lines ~2350-2400
- **Detect functions:** [crt_rag.py](personal_agent/crt_rag.py) lines ~2250-2280
- **Pattern extraction:** [fact_slots.py](personal_agent/fact_slots.py) lines ~200-280
- **Main detection flow:** [crt_rag.py](personal_agent/crt_rag.py) lines ~1800-2100

### Database cleanup (if needed):
```python
# In tools/adversarial_crt_challenge.py, before loop:
import os
if os.path.exists("crt_memory.db"):
    os.remove("crt_memory.db")
if os.path.exists("crt_ledger.db"):
    os.remove("crt_ledger.db")
```

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| **Wrong variable names** | `denied_fact` undefined | Use exact names from extracted methods |
| **Early return blocks iteration** | Turn 24 never detected | Add `continue` instead of `return` for non-matches |
| **Pattern too broad** | False positives on other turns | Make pattern more specific with context |
| **Slot matching with OR** | Wrong slot matches | Change to `old_matches AND new_matches` |
| **Database persistence** | Score varies between runs | Clear DB before test or use session isolation |
| **Missing imports** | `detect_correction_type` undefined | Add to imports at top of file |
| **Unicode in logs** | Terminal errors | Use `$env:PYTHONIOENCODING="utf-8"` |

---

## Success Metrics

### Minimum (28/35 for 80%)
- ✅ Turn 23 detecting as DENIAL
- ✅ Turn 24 detecting as RETRACTION_OF_DENIAL  
- ✅ One additional turn fixed
- 📊 Score: 80% (28/35)

### Target (Beyond 80%)
- ✅ Turn 23, 24, + 1 unknown
- ✅ No regressions on existing passes
- ✅ All code clean and documented
- 📊 Score: 82%+ (29/35)

---

## Session Handoff Checklist

Before you start the next session:
- [ ] Read [PATTERN_FIXES_SESSION.md](PATTERN_FIXES_SESSION.md) for implementation history
- [ ] Review [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) for code structure  
- [ ] Check current database state: `crt_memory.db`, `crt_ledger.db`
- [ ] Run baseline test: `python tools/adversarial_crt_challenge.py --turns 35`
- [ ] Verify current score matches 71.4%
- [ ] Implement Turn 23 denial detection
- [ ] Test Turn 23 in isolation
- [ ] Implement Turn 24 retraction detection
- [ ] Test Turn 23-24 together
- [ ] Run full test to identify 3rd turn
- [ ] Fix 3rd turn
- [ ] Verify score >= 80%
- [ ] Clean up debug logs
- [ ] Create final summary

---

**Last Updated:** 2026-01-26  
**Estimated Time to 80%:** 30-45 minutes  
**Blocker Issues:** None (all methods implemented, just need integration)  
**Help Available:** See [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) for debugging guide
