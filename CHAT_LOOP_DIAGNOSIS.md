# Chat Loop Issues - Diagnosis & Fixes

**Date:** January 21, 2026  
**Context:** User reported poor chat quality with fact extraction failures and missing contradiction badges

---

## Issues Identified

### 1. ❌ Ollama Not Running
**Symptom:**
```
[Ollama error: Failed to connect to Ollama...]
```

**Impact:**
- No natural language caveats for contradicted claims
- Falls back to raw/unpolished responses
- System can't generate inline disclosure phrases

**Fix:** ✅ Started Ollama server (`ollama serve`)

---

### 2. ❌ Poor Fact Extraction

**User Input:**
> "I run a sticker shop called The Printing Lair, and am a Web Developer by degree."

**What System Extracted:**
- `name = Nick Block` ← only this!

**What Should Be Extracted:**
- `employer = self-employed (The Printing Lair)`
- `title = Web Developer`
- `name = Nick Block`

**Root Cause:**
`fact_slots.py` patterns only matched:
- "I work at X" / "I work for X"
- "My role/title is X"

Missing patterns for:
- Self-employment ("I run X", "I work for myself")
- Business names ("called X")
- Occupation phrasing ("Web Developer by degree")

**Fix:** ✅ Added patterns in [personal_agent/fact_slots.py](personal_agent/fact_slots.py):
- `I run [business] called [name]`
- `I work for myself` / `self-employed`
- `[title] by degree/trade/profession`
- `I am a [title]`

---

### 3. ⚠️ Name Contradiction Logic (Partial Issue)

**Observed:**
- "Alex Chen" → "Nick" → "Nick Block"
- System treated "Nick" and "Nick Block" as same (prefix matching)
- No contradiction badge shown

**Current Logic:**
```python
same_or_prefix = (
    prev_norm == new_norm
    or (prev_norm and new_norm and prev_norm.startswith(new_norm))
    or (prev_norm and new_norm and new_norm.startswith(prev_norm))
)
```

**Why:** Designed to avoid false positives on "Nick" vs "Nicholas" or "Nick Block".

**Trade-off:**
- ✅ Good: Avoids noisy conflicts for nickname variations
- ⚠️ Limitation: Won't flag "Nick" → "Nick Block" as contradiction
- ✅ Good: Still flags "Alex Chen" → "Nick" (completely different)

**Status:** Working as designed, but could be refined if needed.

---

### 4. ❌ Generic/Confusing Responses

**Examples:**
- "You work with me, right?" ← weird self-reference
- "You're an employer, correct?" ← misunderstood "self-employed"
- "I've got 'pet' and 'pet_name' stored away" ← user never mentioned pets

**Root Causes:**
1. **Limited memory retrieval:** Only 1 memory in provenance (should show multiple)
2. **Fact extraction failures:** Missing employer/title → can't answer "What do I do?"
3. **Possible LLM hallucination:** Without Ollama, system may use fallback logic poorly

**Mitigation:**
- ✅ Ollama running (better LLM generation)
- ✅ Improved fact extraction (more context for answers)
- Needs testing: Verify retrieval count increases

---

### 5. ❓ Missing Contradiction Badges

**Expected (from Demo Mode):**
Turn 3: "Where do I work?"
- Should show: `⚠️ CONTRADICTED CLAIMS (2)` badge
- Should include caveat: "TechFlow (most recent update)"

**Observed in User's Chat:**
- No badges visible
- No inline caveats

**Possible Causes:**
1. Ollama not running → no caveat generation
2. Facts not extracted → no contradictions detected
3. UI not receiving `reintroduced_claims_count` metadata

**Next Steps:**
- ✅ Ollama started
- ✅ Fact extraction fixed
- ⏳ Need to test with new fact patterns

---

## Summary of Fixes Applied

| Issue | Status | Fix |
|-------|--------|-----|
| Ollama not running | ✅ Fixed | Started `ollama serve` |
| Self-employment not extracted | ✅ Fixed | Added "I run X" patterns |
| Business name not captured | ✅ Fixed | Added "called X" extraction |
| Occupation not extracted | ✅ Fixed | Added "by degree/profession" |
| Generic responses | ⚠️ Partial | Better extraction → better context |
| Missing badges | ⏳ Testing | Depends on above fixes |
| Name contradictions | ℹ️ By Design | Prefix matching prevents noise |

---

## Testing Checklist

**Before next conversation:**
1. ✅ Verify Ollama running: `http://localhost:11434/api/tags`
2. ✅ Verify API running: `http://127.0.0.1:8123/health`
3. ⏳ Test fact extraction with new patterns
4. ⏳ Run Demo Mode 5-turn script
5. ⏳ Verify badges appear on Turn 3
6. ⏳ Verify X-Ray shows contradicted memories

**Test Commands:**
```powershell
# Check Ollama
Invoke-RestMethod "http://localhost:11434/api/tags"

# Test fact extraction via API
$body = @{
  thread_id = "test_" + (Get-Random)
  message = "I run The Printing Lair and am a Web Developer."
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" `
  -Method POST -Body $body -ContentType "application/json"

# Run Demo Mode (in UI)
Click "🎬 Demo" button → Send turns 1-3 → Check for badge
```

---

## Remaining Issues

### Known Limitations (Acceptable for Beta)
1. **Caveat detection:** Keyword-based (can be gamed)
2. **Name prefix matching:** "Nick" === "Nick Block" (avoids noise)
3. **Limited provenance:** UI sometimes shows only 1 memory (investigate retrieval)

### Needs Investigation
1. **Why only 1 memory in provenance?** Should show all retrieved memories
2. **Why "pet" hallucination?** User never mentioned pets
3. **Memory alignment score accuracy**

---

## Next Actions

1. ⏳ **Test updated fact extraction** with real user messages
2. ⏳ **Run full Demo Mode** (5 turns) to verify badges
3. ⏳ **Document provenance count** issue (why only 1 memory?)
4. ⏳ **Check retrieval logic** in `crt_rag.py`

---

**Files Modified:**
- [personal_agent/fact_slots.py](personal_agent/fact_slots.py) - Added self-employment & occupation patterns

**Services Started:**
- Ollama server (port 11434)
- CRT API (port 8123)

**Commit:** `fix: improve fact extraction for self-employment and occupations`
