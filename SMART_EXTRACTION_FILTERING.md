# Smart Fact Extraction: Identity vs Conversation

## Your Question

> "I could talk about anything it will try to extract facts correct? So I could discuss code or code projects I'm working on.... or is that too much?"

## Answer: No, It's Smart About What to Extract!

The system uses **two layers of filtering** to distinguish between:
- ✅ **Permanent identity facts** (store these!)
- ❌ **Temporary activities** (skip these)
- ❌ **Technical discussions** (skip these)

## What Gets Extracted

### ✅ PERMANENT IDENTITY FACTS (Stored)

**Personal Identity:**
- "My name is Nick Block"
- "I have two dogs and a cat"
- "My favorite colors are blue and green"

**Employment & Career:**
- "I work full-time at Google as a senior engineer"
- "I own a SaaS startup called CodeHelper"
- "I specialize in React development"

**Skills & Preferences:**
- "I prefer TypeScript over JavaScript"
- "I have 5 years of experience in web development"
- "I'm fluent in Spanish"

**Long-term Projects:**
- "I'm building a SaaS startup"
- "I run a consulting business"

## What Gets Skipped

### ❌ TEMPORARY ACTIVITIES (Not Stored)

**Current Tasks:**
- "I'm working on debugging a React component tonight" ← temporal + activity
- "I'm currently refactoring the API layer" ← "currently" = temporary
- "I need to fix the authentication bug" ← to-do item

**Implementation Work:**
- "I'm implementing a new feature using GraphQL"
- "I'm building a function that returns user data"
- "I'm trying to fix this error"

### ❌ TECHNICAL DISCUSSIONS (Not Stored)

**Code Behavior:**
- "The function returns undefined when the API fails"
- "This component throws an error on mount"
- "The endpoint returns a 500 status code"

**Questions/Help:**
- "Can you help me debug this React component?"
- "How do I fix this TypeScript error?"
- "What should I do about this API issue?"

## How It Works

### Layer 1: Temporal Filter (Python, Fast)

Checks for markers indicating temporary content:

```python
# Temporal markers
temporal_markers = ['tonight', 'today', 'currently', 'right now']

# Temporary activities
temporary_activities = ['working on', 'debugging', 'refactoring', 
                       'implementing', 'trying to', 'need to']

# Code discussion markers
code_markers = ['function', 'component', 'api', 'endpoint', 
               'error', 'bug', 'returns', 'undefined']
```

**Rules:**
1. Temporal marker + activity verb = SKIP ("working on X tonight")
2. Multiple code markers + no "I" statement = SKIP (technical description)
3. Implementation phrases + "I'm" = SKIP ("I'm implementing using GraphQL")
4. Questions about code = SKIP ("Can you help debug this?")

### Layer 2: LLM Prompt (Intelligent)

The LLM is instructed to extract ONLY permanent identity facts:

```
🎯 ONLY extract facts that are:
✅ Permanent aspects of the user's identity
✅ Durable relationships or possessions
✅ Long-term preferences or characteristics

❌ DO NOT extract:
❌ Temporary activities
❌ Technical discussions
❌ Current tasks or to-do items
❌ Questions or requests
```

## Examples in Action

### Example 1: Mixed Conversation
**You:** "I'm debugging a React component for my startup. I specialize in React development."

**Extracted:**
- ✅ `occupation: "React developer"` (permanent skill)
- ❌ Skips "debugging a React component" (temporary activity)

### Example 2: Code Discussion
**You:** "The API endpoint returns undefined. I work at Google."

**Extracted:**
- ✅ `employer: "Google"` (permanent employment)
- ❌ Skips "API endpoint returns undefined" (technical discussion)

### Example 3: Project vs Business
**You:** "I'm working on a weekend project using TypeScript. I'm building a SaaS startup."

**Extracted:**
- ✅ `business: "SaaS startup"` (long-term business)
- ❌ Skips "weekend project" (temporary activity)
- Maybe `programming_language_preference: "TypeScript"` (if LLM sees pattern)

## Testing Results

Ran 11 test cases covering all scenarios:

```
✅ 11/11 PASSED

Permanent identity: 4/4 extracted correctly
Temporary activities: 4/4 skipped correctly  
Technical discussions: 3/3 skipped correctly
```

## Configuration

The filtering is automatic, but you can adjust:

```python
# Stricter filtering (extract less)
profile.is_temporal_statement()  # Already comprehensive

# More lenient (extract more)
# Edit temporal_markers list in user_profile.py
```

## Summary

**You can talk about ANYTHING:**
- Code projects ✅
- Debug sessions ✅
- Technical questions ✅
- Implementation work ✅

**The system is smart enough to:**
- Extract permanent identity facts
- Skip temporary activities
- Ignore technical discussions
- Keep your profile clean

**Result:** Your profile stores WHO YOU ARE, not WHAT YOU'RE WORKING ON RIGHT NOW.

---

### Quick Test

Try saying:
1. "I'm debugging a TypeScript error" → Skipped
2. "I prefer TypeScript over JavaScript" → Extracted!
3. "I work at Google" → Extracted!
4. "I need to fix the API" → Skipped
5. "I own a consulting business" → Extracted!

The system knows the difference! 🎯
