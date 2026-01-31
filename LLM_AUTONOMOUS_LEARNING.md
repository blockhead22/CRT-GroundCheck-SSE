# LLM-Based Autonomous Fact Extraction

## Overview

The system now supports **intelligent, autonomous fact learning** using LLM-based extraction that goes far beyond regex patterns.

## What Changed

### Before (Regex-Only)
- ❌ Rigid single-value vs multi-value distinction
- ❌ Predefined slots only (`name`, `employer`, `location`, etc.)  
- ❌ Cannot handle multiple values: "My favorite colors are blue and green" → extracts nothing
- ❌ No context: "sick dog" stored as just "dog"
- ❌ No temporal understanding: "I used to work at X" extracts "X" as current employer

### After (LLM + Regex Hybrid)
- ✅ **Multiple values for ANY attribute**
  - "My favorite colors are blue and green" → 2 favorite_color facts
  - "I have a healthy dog and a sick cat" → 2 pet facts with health context
  
- ✅ **Rich contextual information**
  - Not just "Google" but "full-time at Google"
  - Not just "dog" but "healthy dog named Max"
  
- ✅ **Temporal understanding**
  - "I used to love woodworking" → mark hobby as deprecated
  - "Now I prefer pottery" → add new hobby
  
- ✅ **Open-world attributes**
  - LLM identifies what's important to remember
  - No need to predefine every possible slot
  
- ✅ **Graceful fallback**
  - LLM unavailable? Falls back to regex patterns
  - Maintains backward compatibility

## Examples

### 1. Multiple Values
```python
"I have two pets: a healthy dog named Max and a really sick cat named Luna"
```
**LLM Extracts:**
- `pet: "healthy dog named Max"` (confidence: 0.85)
- `pet: "sick cat named Luna"` (confidence: 0.82)
- Evidence spans preserved for each

**Regex Would Extract:** Nothing or just "Max" and "Luna" as pet_name

### 2. Multiple Jobs/Roles
```python
"I work full-time at Google and part-time as a consultant"
```
**LLM Extracts:**
- `employer: "Google"` with context "full-time"
- `occupation: "consultant"` with context "part-time"

**Regex Would Extract:** Only "Google" as employer

### 3. Temporal Statements
```python
"I used to love woodworking but now I prefer pottery"
```
**LLM Extracts:**
- `hobby: "woodworking"` with action=DEPRECATE
- `hobby: "pottery"` with action=ADD

**Regex Would Extract:** Both as current hobbies (contradiction)

### 4. Business Ownership + Employment
```python
"I own a small business called TechStartup and also work full-time at Microsoft"
```
**LLM Extracts:**
- `business: "TechStartup"` with context "small business, owner"
- `employer: "Microsoft"` with context "full-time"

**Regex Would Extract:** Maybe just "Microsoft"

## Technical Implementation

### Architecture
```
User input text
    ↓
┌─────────────────────────┐
│ GlobalUserProfile       │
│ .update_from_text()     │
└─────────────────────────┘
    ↓
    ├─→ LLM Extraction (if available)
    │   - Uses gpt-4o-mini for cost efficiency
    │   - JSON schema for structured output
    │   - Confidence scores per fact
    │   - Evidence spans for auditability
    │   - Actions: ADD, UPDATE, DEPRECATE, DENY
    │
    └─→ Regex Fallback (if LLM fails)
        - Predefined patterns from fact_slots.py
        - Known slots only
        - High confidence (0.9)
        - Backward compatible
```

### Database Schema Updates
```sql
CREATE TABLE user_profile_multi (
    id INTEGER PRIMARY KEY,
    slot TEXT NOT NULL,                -- e.g., 'pet', 'employer', 'hobby'
    value TEXT NOT NULL,               -- e.g., 'healthy dog named Max'
    normalized TEXT NOT NULL,          -- 'healthy dog named max' (for dedup)
    timestamp REAL NOT NULL,
    source_thread TEXT NOT NULL,
    confidence REAL DEFAULT 0.9,
    active INTEGER DEFAULT 1,          -- 0 = deprecated
    evidence_span TEXT,                -- Quote from text: "I have a healthy dog named Max"
    action TEXT DEFAULT 'add',         -- 'add', 'update', 'deprecate', 'deny'
    UNIQUE(slot, normalized)
)
```

### Key Methods

#### `_update_from_llm_tuples(text, thread_id)`
- Calls LLM to extract FactTuples
- Handles actions: ADD (new), UPDATE (refresh), DEPRECATE (mark inactive), DENY (reject)
- Stores evidence_span for each fact
- Confidence scores from LLM
- Falls back to regex on failure

#### `_update_from_regex_facts(text, thread_id)`  
- Legacy regex-based extraction
- Uses fact_slots.py patterns
- Respects SINGLE_VALUE_SLOTS for backward compat
- Always action='add'

## Configuration

```python
# Enable LLM extraction (requires OpenAI API key)
profile = GlobalUserProfile(use_llm_extraction=True)

# Disable LLM, use regex only
profile = GlobalUserProfile(use_llm_extraction=False)
```

## Cost & Performance

- **Model:** `gpt-4o-mini` (very cheap, ~$0.15/1M tokens)
- **Typical input:** 50-200 tokens per user message
- **Typical output:** 100-500 tokens (JSON facts)
- **Cost per extraction:** $0.000015 - $0.0001 (negligible)
- **Latency:** ~200-500ms
- **Fallback:** 0ms (instant regex patterns)

## Future Enhancements

1. **Profile-specific attributes:**
   - Learn user's preferred slot names over time
   - "I call my workplace 'the office'" → use `office` instead of `employer`

2. **Confidence-based prompting:**
   - Low confidence facts trigger clarifying questions
   - "I think you mentioned having a pet - what kind?"

3. **Contradiction resolution:**
   - When facts conflict, ask user to resolve
   - "You said blue was your favorite color, but now green - did it change or both?"

4. **Multi-entity support:**
   - Currently `entity="User"` for all facts
   - Could store facts about others: "My wife Sarah loves gardening"
   - `entity="Wife"`, `attribute="hobby"`, `value="gardening"`

5. **Local LLM fallback:**
   - Use local models (Ollama, etc.) when OpenAI unavailable
   - Trade accuracy for privacy/cost

## Migration Path

Existing users with regex-extracted facts:
- ✅ No migration needed
- ✅ Old facts remain valid
- ✅ New extractions use LLM when available
- ✅ System handles both formats seamlessly

## Testing

```bash
# Test LLM extraction (requires OPENAI_API_KEY)
python test_llm_extraction.py

# Test regex fallback (works without API key)
python test_llm_extraction.py  # auto-falls back if no key

# Test cross-thread persistence (still works)
python test_integration_final.py
```

## Summary

You were absolutely right: **the system needs to learn facts on its own**. 

The old regex system couldn't handle:
- ✅ Multiple favorite colors
- ✅ Multiple pets with different health statuses
- ✅ Part-time + full-time jobs simultaneously
- ✅ Business ownership + employment
- ✅ Contextual nuances ("sick dog" vs "healthy dog")

Now it can learn **autonomously** from natural language, capturing rich context that makes memory truly useful across conversations.
