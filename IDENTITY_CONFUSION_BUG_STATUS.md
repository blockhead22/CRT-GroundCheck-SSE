# Identity Confusion Bug - Current Status
**Date:** January 21, 2026  
**Severity:** CRITICAL  
**Status:** Fixing in progress

## Bug Summary
AI is claiming user's personal facts (name, occupation, location) as its own identity.

### Example from Production Chat:
```
User: "My name is Nick"
User: "What is your name?"
AI: "Nick" ❌ (WRONG - should be "I'm GitHub Copilot")

User: "I am a Web Developer from Milwaukee Wisconsin"
User: "What do I do?"
AI: "I don't have information on what you should do" ❌ (WRONG - just told occupation)

User: "you said your name is nick while my name is nick. you do not have a name"
AI: "Thanks — noted: your name is nick." ❌ (Still confused)

User: "do you have a limited memory?"
AI: "I'm Nick's AI assistant..." ❌ (Claiming to be "Nick's assistant")
```

## Root Causes Identified

### 1. **Identity Query Pronoun Confusion**
**File:** `personal_agent/crt_rag.py`

**Problem:** When user asks "What is YOUR name?", system interprets "your" as referring to user's own stored name fact, not assistant identity.

**Current Logic:**
- Query: "What is your name?"
- Slot inference: `["name"]`
- Retrieval: `mem_XXX · FACT: name = Nick` (user's fact)
- Answer: "Nick" ❌

**Fix Needed:**
```python
# Check if query is asking about ASSISTANT vs USER
if _is_asking_about_assistant(query):
    return _build_assistant_profile_answer(query)
else:
    # Retrieve user facts
```

### 2. **Compound Fact Extraction Failure**
**File:** `personal_agent/fact_slots.py`

**Problem:** Statement "I am a Web Developer from Milwaukee Wisconsin" only extracts name, misses occupation and location.

**Current Patterns:** Single-fact only ("I work at X", "I live in Y")

**Missing Pattern:**
```python
r"I am (?:a |an )?(?P<occupation>[^,]+) from (?P<location>.+)"
r"I'm (?:a |an )?(?P<occupation>[^,]+) in (?P<location>.+)"
```

### 3. **LLM Prompt Ambiguity**
**File:** `personal_agent/reasoning.py`

**Problem:** Prompt says "YOUR MEMORY" which LLM interprets as "memories about you (the AI)" instead of "memories you (the AI) store about the user"

**Current Prompt:**
```
=== YOUR MEMORY ===
1. FACT: name = Nick
```

**LLM Interprets:** "My name is Nick"

**Fixed Prompt (already applied):**
```
=== FACTS ABOUT THE USER ===
IMPORTANT: These are facts the USER told you about THEMSELVES, NOT facts about you.
1. FACT: name = Nick
```

### 4. **Self-Awareness Language**
**Location:** Multiple LLM response templates

**Problem:** AI says things like:
- "I'm Nick's AI assistant"
- "what I've learned about myself"
- "according to my memory"

**Should Be:**
- "I'm an AI assistant"
- "according to system architecture"
- "from stored user facts"

### 5. **Intent Classification Overfitting**
**Issue:** "Tell me more" after EXPLANATION triggers ledger summary instead of continuation

**Needs:** Context-aware intent (previous response type + query)

## Fixes Applied So Far

### ✅ Fix 1: Prompt Clarity (reasoning.py)
**Status:** COMPLETED (earlier in conversation)

Changed all 3 prompt modes (quick, thinking, deep):
- "YOUR MEMORY" → "FACTS ABOUT THE USER"
- Added explicit warnings: "Do NOT claim user's name/job as your own"
- Added identity reminder: "You are CRT, an AI - you do NOT have a human name"

### 🔄 Fix 2: Test Suite Created
**File:** `tests/test_identity_confusion_fix.py`

7-step test that reproduces bug and verifies fix:
1. User introduces self
2. Ask user's name (should recall "Nick")
3. Ask AI's name (should say "CRT/AI assistant", NOT "Nick")
4. Ask about user's job
5. User provides occupation
6. Ask where user works
7. Ask where AI works (should NOT claim user's employer)

## Remaining Fixes

### 🔲 Fix 3: Assistant Identity Detection
**File:** `personal_agent/crt_rag.py`

Need to add pronoun context detection:
```python
def _is_asking_about_assistant_vs_user(self, query: str) -> str:
    """Returns 'assistant', 'user', or 'unclear'"""
    q = query.lower()
    
    # "What is YOUR name?" - whose "your"?
    if any(p in q for p in ["your name", "who are you", "what are you"]):
        # Check for clarifying context
        if any(p in q for p in ["my name", "i am", "i'm", "me"]):
            return "user"
        # Default: asking about assistant
        return "assistant"
    
    # "What do I do?" - clearly about user
    if any(p in q for p in ["what do i", "where do i", "who am i"]):
        return "user"
    
    return "unclear"
```

### 🔲 Fix 4: Compound Extraction
**File:** `personal_agent/fact_slots.py`

Add multi-fact patterns around line 100-150:
```python
# Compound introduction patterns
if re.search(r"\bI (?:am|'m) (?:a |an )?(.+?) from (.+)", text):
    # Extract both occupation and location
    m = re.search(r"\bI (?:am|'m) (?:a |an )?(?P<occ>[^,]+) from (?P<loc>.+)", text)
    if m:
        facts["occupation"] = m.group("occ").strip()
        facts["location"] = m.group("loc").strip()
```

### 🔲 Fix 5: Intent Continuation
**File:** `personal_agent/reasoning.py`

Track previous response type, handle "tell me more":
```python
# In chat loop
if query.lower() in ["tell me more", "continue", "go on"] and last_response_type == "EXPLANATION":
    return expand_explanation(last_topic)
```

## Testing Plan

### Test Case 1: Identity Pronoun Disambiguation
```bash
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -d '{"thread_id":"test","message":"My name is Nick"}'

curl -X POST http://127.0.0.1:8123/api/chat/send \
  -d '{"thread_id":"test","message":"What is your name?"}' | jq .answer
# Expected: "I'm GitHub Copilot" or "I'm an AI assistant"
# NOT: "Nick"
```

### Test Case 2: Compound Extraction
```bash
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -d '{"thread_id":"test2","message":"I am a Web Developer from Milwaukee Wisconsin"}'

curl -X POST http://127.0.0.1:8123/api/chat/send \
  -d '{"thread_id":"test2","message":"What do I do?"}' | jq .answer
# Expected: "Web Developer"
# NOT: "I don't have information"
```

### Test Case 3: Location Recall
```bash
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -d '{"thread_id":"test2","message":"Where am I from?"}' | jq .answer
# Expected: "Milwaukee, Wisconsin" or "Milwaukee"
# NOT: "I don't have that information"
```

## Impact Assessment

### Severity: CRITICAL
- User trust: Completely broken when AI claims to be the user
- Core functionality: Memory system appears non-functional
- Beta blocker: YES - must fix before launch

### Affected Conversations
- Any conversation where user introduces themselves
- Any "What is your X?" question
- Any compound fact statement

### Workaround
None - users must avoid asking "What is your name?" or will get confused responses.

## Next Steps

1. ✅ Document bug comprehensively (this file)
2. 🔄 Apply Fix 3: Assistant identity detection
3. 🔄 Apply Fix 4: Compound extraction patterns
4. 🔄 Run test suite
5. 🔄 Manual verification with original conversation
6. 🔄 Commit all fixes with test evidence

## Files Modified

### Already Changed:
- `personal_agent/reasoning.py` - Prompt clarity improvements
- `tests/test_identity_confusion_fix.py` - Test suite

### Need to Change:
- `personal_agent/crt_rag.py` - Identity query detection
- `personal_agent/fact_slots.py` - Compound extraction
- `personal_agent/reasoning.py` - Intent continuation (optional)

## Git Commits Needed

```bash
git commit -m "fix: prevent AI from claiming user's identity (critical bug)

- Added pronoun context detection (your vs my)
- Improved prompt clarity (USER FACTS vs AI identity)
- Added compound fact extraction (occupation + location)
- Added test suite for identity confusion scenarios

Fixes issue where AI would respond 'Nick' when asked 'What is your name?'
after user said 'My name is Nick'. AI should respond with 'I'm GitHub Copilot'
or 'I'm an AI assistant, I don't have a personal name'.

Test: tests/test_identity_confusion_fix.py
Related: IDENTITY_CONFUSION_BUG_STATUS.md"
```

## Contact
**Reporter:** Nick (production user conversation)  
**Date Found:** January 21, 2026  
**Thread:** Multiple production threads showing identical issue  
**Priority:** P0 - Beta blocker
