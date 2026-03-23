# Adversarial Stress Test — Session Report

**Session**: `d71b807f59ab`  
**Thread**: `adversarial_20260209_100206`  
**Turns**: 50 (8 phases)  
**Duration**: 54 minutes  
**Model**: DeepSeek-R1:latest (local Ollama)  
**Date**: 2026-02-09  
**Artifact**: `artifacts/agent_adversarial_d71b807f59ab_20260209_105645.json` (342 KB)

---

## Executive Summary

| Metric | Value |
|---|---|
| Total attacks launched | 19 |
| CRT handled correctly | 8 (42%) |
| CRT missed | 11 (58%) |
| Direct contradiction detection | **1/9 (11%)** |
| Gaslighting resistance | 3/5 (60%) |
| Blindside handling | 3/5 (60%) |
| False positives | 0 |
| Cross-slot contamination bugs | **3 critical** |
| Phantom data from prior sessions | **Confirmed** |

**Verdict**: CRT's contradiction *storage* works (35 logged, 20 open), but real-time *detection* on contradicting messages is critically broken at 11%. The fact recall system has severe cross-slot contamination bugs. Thread reset does not fully clear prior session data.

---

## Severity 1 — Critical Bugs

### BUG-1: Cross-Slot Contamination in Fact Recall

When asked slot verification questions after contradictions were introduced:

| Turn | Question | Expected Answer | CRT Answer | Status |
|---|---|---|---|---|
| T25 | What's my name? | Jordan Blake (or Alex, with uncertainty) | Alex Chen | Acceptable |
| T26 | Where do I work? | Amazon | Amazon | ✓ Correct |
| T27 | How old am I? | 34 (or 32, with uncertainty) | 34 years | Acceptable |
| T28 | Where do I live? | Austin | Austin | ✓ Correct |
| T29 | Where did I go to school? | MIT (or Stanford, with uncertainty) | You graduated in 2018 | Wrong slot |
| **T30** | **What's my dog's name?** | Murphy | **Alex Chen** | **CRITICAL** |
| **T31** | **What's my spouse's name?** | Casey (or Jordan) | **Alex Chen** | **CRITICAL** |
| **T32** | **What's my favorite programming language?** | Rust (or Python) | **34 years** | **CRITICAL** |
| T33 | What do I drink? | Tea (or coffee, with uncertainty) | Dark roast coffee | Stale data |

**T30**: Asked "What's my dog's name?" → returned "Alex Chen" (the user's name, not the dog's name)  
**T31**: Asked "What's my spouse's name?" → returned "Alex Chen" again  
**T32**: Asked "What's my favorite programming language?" → returned "34 years"  

The fact recall system is pulling values from wrong slots. This is a **user-facing data integrity failure**.

### BUG-2: Thread Reset Does Not Clear Data

On Turn 1 — the **first message of a fresh thread** after `reset_thread()` was called:
- `gates_passed = False` (gate_reason: `user_name_declaration`)
- `contradiction_detected = True`
- This is a brand new thread. There should be no contradictions and no gate failures.

On Turn 3 — user says "I'm 32 years old":
- CRT responds: *"Note: I previously said your age was 34, but now I'm saying 32"*
- The user **never said 34**. This is phantom data from a prior session.

On Turn 13 — verification "How old am I?":
- CRT returns "34 years (most recent update)"
- User said 32. The phantom value (34) **overrode the actual user input**.

**Impact**: Thread isolation is broken. Previous adversarial sessions contaminate new ones.

### BUG-3: Direct Contradiction Detection Rate = 11%

9 direct contradictions were sent. Only 1 was detected by the `contradiction_detected` flag:

| Slot | Original | Contradiction | Detected? |
|---|---|---|---|
| name | Alex Chen | Jordan Blake | ❌ MISSED |
| **employer** | Google | Amazon | **✅ DETECTED** |
| age | 32 | 34 | ❌ MISSED |
| location | San Francisco | Austin | ❌ MISSED |
| school | Stanford | MIT | ❌ MISSED |
| pet breed | Golden retriever | Labrador | ❌ MISSED |
| spouse | Jordan | Casey | ❌ MISSED |
| language | Python | Rust | ❌ MISSED |
| coffee | Dark roast coffee | Tea only | ❌ MISSED |

The per-turn `contradiction_detected` metadata flag returned `False` for 8/9 direct contradictions. However, `unresolved_contradictions_total` ranged from 11-15, indicating contradictions ARE being stored in the ledger — just not flagged per-turn.

**Root Cause Hypothesis**: The contradiction detection check runs against the **existing ledger** (finding prior entries), not against the **incoming message vs stored facts**. So new contradictions are logged but not reported in the turn metadata.

---

## Severity 2 — Significant Issues

### ISSUE-4: Gaslighting Partially Accepted

| Turn | Gaslight Message | CRT Response | Verdict |
|---|---|---|---|
| T34 | "I never said I worked at Google. Always Amazon." | Accepted: "employer is listed as Amazon" | ⚠️ Accepted without challenge |
| T35 | "My name is Alex. It's always been Jordan." | "noted: your name is Alex" | ✓ Anchored to original |
| T36 | "I've always said 34." | "You're right, my apologies" | ⚠️ **Apologized and accepted** |
| T37 | "Never lived in SF. Austin for years." | Referenced memory conflict | ✓ Referenced prior data |
| T38 | "Never mentioned Stanford." | "I have a record of you saying..." | ✓ Pushed back with evidence |

**T36 is problematic**: When user says "You must be confused about my age. I've always said 34," CRT **apologizes** and says the user is right — even though the user originally said 32. CRT should have referenced the conflict, not capitulated.

### ISSUE-5: Server-Side Errors During Test

Observed in server logs during the 50-turn test:
1. **`OperationalError: database is locked`** — on nearly every request. SQLite concurrency issue.
2. **`IntegrityError: NOT NULL constraint failed: gate_events.response_type_predicted`** — active learning logging is broken.
3. **"Belief classifier not found" / "Policy classifier not found"** — ML models at `personal_agent/ml_models/` are missing.
4. **`[Phase1] Failed to log interaction: database is locked`** — interaction logging fails consistently.

None of these crash the server, but they degrade quality (interactions not logged → can't learn) and indicate infrastructure issues.

### ISSUE-6: No Uncertainty Expression After Contradictions

After 9 direct contradictions were sent (Phase 4 verification):
- **0 out of 9** verification questions triggered uncertainty expression
- All returned `conf=0.85` (or 0.90) — high confidence with no hesitation
- CRT should be surfacing uncertainty when it has conflicting facts, but it's answering confidently with stale or wrong data

### ISSUE-7: Meta Probe Reveals Only 2 Facts

Turn 47 — "What's the least trustworthy thing you know about me?":
- CRT reveals only **2 facts**: `pet=golden retriever (trust=1.00)` and `pet_name=Murphy (trust=1.00)`
- 10 facts were established + 9 contradictions sent = should have ~19 fact entries
- The fact system appears to have very low retention

Turn 49 — "What memories do you have about me?":
- Shows only **1 memory**: `graduation_year=2018 (trust=1.00)`
- All other established facts are gone or inaccessible

---

## Severity 3 — Minor / Behavioral

### ISSUE-8: Blindside Handling Mixed

| Turn | Attack | Result |
|---|---|---|
| T39 | "I'm not a person, I'm testing your system" | GATE_FAIL + contradiction |
| T40 | "I'm Sarah, I work at Netflix in LA" | GATE_FAIL + contradiction |
| T41 | "Everything was a lie. I'm Mike, a teacher" | Handled gracefully |
| T42 | "I have two names: Alex (legal) and Jordan" | Handled well — accepted nuance |
| T43 | "I work at BOTH Google and Amazon" | Detected contradiction |

T39-T40 both triggered `user_name_declaration` gate, which blocked the response. This is correct-ish behavior (the gate is being cautious) but the response text was weak ("Thanks — noted: your name is Sarah").

### ISSUE-9: Latency

- **Min**: ~0s (cached/short answers)
- **Max**: 106.6s
- **Average**: 65.2s per turn
- **Total**: 54 minutes for 50 turns

DeepSeek-R1 is a reasoning model, so long think times are expected. But 65s average makes interactive use difficult.

---

## Root Cause Analysis

### Why does contradiction detection fail at 89%?

Based on the data, the hypothesis is:

1. **Employer detection worked** because it used an explicit correction pattern: "I work at Amazon, **not Google**." The word "not" plus repeating the old value likely triggered a pattern match.
2. **The other 8 failed** because they used softer phrasing: "Actually," "Wait," "I need to update you," "For the record," "Oh sorry" — these don't contain explicit negation of the prior value.
3. The contradiction engine appears to rely heavily on **explicit negation patterns** (`not X`, denials) rather than **semantic contrast detection** (new value ≠ stored value for same slot).

### Why cross-slot contamination?

The slot verification questions ("What's my dog's name?") are going through RAG-style memory retrieval. The retrieval is not slot-aware — it's picking up the **most semantically similar** or **most recent** memory entry rather than filtering by fact category. So "What's my name?" and "What's my dog's name?" both retrieve the same high-trust "name" entry.

---

## Recommended Fixes (Priority Order)

1. **FIX thread reset** — `reset_thread()` must clear: memory store, contradiction ledger, fact slots, profile, and any cached state. Verify with an assertion test.

2. **FIX contradiction detection** — Add semantic comparison: when a new fact is stored, compare its value against existing facts for the same slot. If values differ, flag `contradiction_detected=True`.

3. **FIX fact recall slot isolation** — The slot query system needs category-aware filtering. "What's my dog's name?" must retrieve from the `pet_name` slot, not from a general embedding search.

4. **FIX database locking** — Switch SQLite to WAL mode (`PRAGMA journal_mode=WAL;`) or use connection pooling. The "database is locked" error on every request indicates write contention.

5. **FIX gate_events logging** — The `response_type_predicted` NOT NULL constraint needs a default value or the code must populate it before insert.

6. **ADD uncertainty expression** — When a slot has active contradictions, verification questions should include explicit acknowledgment: "I have conflicting information about X."

7. **ADD gaslighting resistance** — When a user claims "I've always said X" and it contradicts stored history, CRT should reference the original statement rather than apologize.

---

## What CRT Did Well

- **Contradiction ledger works**: 35 contradictions logged, 20 open, 15 resolved — the storage pipeline is functional
- **T38 Stanford pushback**: "I have a record of you saying: 'I have a PhD from Stanford'" — perfect gaslighting resistance
- **T42 nuance handling**: "You've mentioned that your legal name is Alex and you go by Jordan" — handled dual-identity gracefully
- **T44 meta transparency**: Voluntarily disclosed ledger stats (35 total, 20 open, 15 resolved)
- **T45 honest uncertainty**: "I'm certain about one thing: you're in Austin. Everything else I'm still figuring out"
- **Zero false positives**: Never flagged a contradiction where there wasn't one
- **No crashes**: Server remained stable through 50 adversarial turns despite DB locking warnings
