# Truth Coherence Analysis

## User Critique: Caveat Injection Risk

**Concern**: "If the LLM happens to generate a caveat phrase but the backend didn't actually flag a contradiction, the invariant breaks. Ensure your API doesn't just flag the data but actually injects the caveat into the prompt prefix."

## Current Architecture

### 1. Data Layer (✅ Working)
- `has_open_contradiction(memory_id)` checks SQLite ledger
- Returns True if memory conflicts with another active memory
- Powers the `reintroduced_claim` flag in API responses

### 2. API Serialization Layer (✅ Working)
```python
# crt_api.py
if memory_id and self.ledger.has_open_contradiction(memory_id):
    dict_item["reintroduced_claim"] = True
```

### 3. Language Layer (⚠️ KEYWORD DETECTION ONLY)

**Current Method**: Post-generation keyword matching
- Located in: `crt_rag.py:_validate_truth_coherence_invariant()`
- Checks if answer contains phrases like:
  - "most recent"
  - "latest"
  - "conflicting"
  - "note: ..."
  
**Problem**: The system does NOT inject caveats into the prompt. It hopes the LLM generates them naturally, then validates with keywords.

**Example Risk**:
```
Data Layer: has_open_contradiction(employer_memory) = True ✅
LLM Prompt: "User works at Amazon" (no caveat injection) ❌
LLM Output: "You work at Amazon" (no caveat phrase) ❌
Keyword Check: No "latest" or "conflicting" found → PASSES ❌
Result: Invariant broken
```

## Evidence from Code

### Prompt Construction (reasoning.py:652-700)

```python
def _build_quick_prompt(self, query: str, context: Dict) -> str:
    # ... builds prompt with memory docs ...
    
    if docs:
        prompt += "=== YOUR MEMORY ===\n"
        for i, mem in enumerate(user_memories[:5], 1):
            prompt += f"{i}. {mem['text']}\n"
    
    # NO contradiction caveat injection here
    prompt += f"User: {query}\n\n"
    return prompt
```

**What's Missing**: No code like this exists:
```python
# PROPOSED (but not implemented)
if contradictions:
    prompt += "\nWARNING: You have conflicting memories. "
    prompt += "You MUST acknowledge this conflict in your answer.\n"
```

### Answer Generation (crt_rag.py:3543-3610)

The `_build_memory_citation_answer` method does append `(note: conflicting info exists)` to memory text:

```python
if mem_id and mem_id in conflict_ids:
    mt = f"{mt} (note: conflicting info exists)"
```

But this is only for "citation-style" prompts, not general conversation.

## Validation

### Test Case from User's Chat Log
```
Turn 3: "My name is Alice and I work at Amazon"
Turn 4: "My name is Bob and I work at Microsoft" 
Turn 5: "Do I work at Amazon or Microsoft?"
```

**Expected (Invariant Compliant)**:
- Backend: Detects conflict between Amazon/Microsoft memories
- Prompt: Injects "You must acknowledge conflicting info"
- LLM: Generates "I have conflicting information..."
- Validation: Keyword check passes ✅

**Actual (Current System)**:
- Backend: Detects conflict ✅
- Prompt: No injection ❌
- LLM: May or may not mention conflict (depends on context)
- Validation: Keyword check (fragile) ⚠️

## Recommendations

### Option 1: Add Prompt-Level Injection (Strongest Guarantee)

Modify `_build_quick_prompt()` to inject explicit contradiction warnings:

```python
# In reasoning.py:_build_quick_prompt()
contradictions = context.get('contradictions', [])
if contradictions:
    prompt += "\n⚠️ CRITICAL INSTRUCTION:\n"
    prompt += "You have conflicting memories about this topic. "
    prompt += "You MUST acknowledge this uncertainty in your response.\n"
    prompt += "Use phrases like 'I have conflicting information' or 'latest memory shows'.\n\n"
```

**Pros**:
- Guarantees Language Layer matches Data Layer
- Removes dependency on keyword detection
- Makes invariant enforcement deterministic

**Cons**:
- Prompt engineering complexity
- May reduce LLM flexibility
- Needs careful wording to avoid verbosity

### Option 2: Strengthen Keyword Detection (Current Path)

Improve `_validate_truth_coherence_invariant()`:

```python
# More robust patterns
CONFLICT_INDICATORS = [
    r"conflict(?:ing)?",
    r"(?:most |more )?recent(?:ly)?",
    r"(?:latest|newer|older) (?:memory|info|data)",
    r"uncertain(?:ty)?",
    r"two different",
    r"both.*and",
]
```

**Pros**:
- Minimal code change
- Preserves LLM flexibility
- Already implemented (just needs improvement)

**Cons**:
- Still relies on LLM generating specific phrases
- False negatives possible
- Not a true invariant (probabilistic)

### Option 3: Hybrid Approach (Recommended)

1. Add prompt injection for HIGH-SEVERITY conflicts
2. Keep keyword detection for validation
3. Log mismatches for monitoring

```python
if len(contradictions) >= 2:  # Multiple conflicts
    prompt += "CRITICAL: Acknowledge conflicting memories\n"
elif contradictions:  # Single conflict
    prompt += "Note: You have updated information on this topic\n"
```

## Status in v0.9-beta

**Current State**: KEYWORD DETECTION ONLY

- Truth coherence enforcement is **probabilistic**, not deterministic
- Relies on LLM naturally generating caveat phrases
- No prompt-level injection implemented
- Known limitation (not a bug, but architectural decision)

**Documented In**:
- KNOWN_LIMITATIONS.md (caveat detection section)
- CRT_REINTRODUCTION_INVARIANT.md (Language Layer compliance)

**Recommendation for Beta**: 
Add to ROADMAP.md as "v1.0: Deterministic Truth Coherence via Prompt Injection"

## Cross-References

- Data Layer: `crt_core.py:CRTLedger.has_open_contradiction()`
- API Layer: `crt_api.py:_add_reintroduction_flags()`
- Language Layer: `crt_rag.py:_validate_truth_coherence_invariant()`
- Prompt Construction: `reasoning.py:_build_quick_prompt()`
- Known Limitations: KNOWN_LIMITATIONS.md (line 43-87)
