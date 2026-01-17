# RAG + Reasoning System Architecture

## System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER QUERY                               │
│            "Why do I wake up at 3 AM?"                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAG ENGINE                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 1: Retrieve Context                                  │  │
│  │  • Vector search (ChromaDB) → semantic similarity         │  │
│  │  • Memory system → learned user context                   │  │
│  │  • SSE → contradiction detection                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 2: Internal Hooks (INVISIBLE)                        │  │
│  │  • Log fusion event → lineage.jsonl                       │  │
│  │  • Track: query, memories used, facts retrieved           │  │
│  │  • Generate fusion_id for tracing                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  REASONING ENGINE                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Mode Detection (Auto or Manual)                           │  │
│  │  • Contradictions? → THINKING or DEEP                     │  │
│  │  • Complex query? → THINKING                              │  │
│  │  • Simple query? → QUICK                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│         ┌───────────────┼───────────────┐                       │
│         │               │               │                       │
│         ▼               ▼               ▼                       │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐                 │
│   │  QUICK  │    │ THINKING │    │   DEEP   │                 │
│   └─────────┘    └──────────┘    └──────────┘                 │
│         │               │               │                       │
│         │               │               │                       │
│  ┌──────▼───────────────▼───────────────▼──────────────────┐  │
│  │                                                           │  │
│  │  QUICK:                                                   │  │
│  │   → Direct answer                                         │  │
│  │   → No visible thinking                                   │  │
│  │   → Internal trace logged                                 │  │
│  │                                                           │  │
│  │  THINKING:                                                │  │
│  │   → Analyze query                                         │  │
│  │   → Identify sub-questions                                │  │
│  │   → Analyze contradictions                                │  │
│  │   → Plan approach                                         │  │
│  │   → Generate answer                                       │  │
│  │   → Show <thinking> to user                               │  │
│  │                                                           │  │
│  │  DEEP:                                                    │  │
│  │   → Decompose into sub-questions                          │  │
│  │   → Deep contradiction analysis                           │  │
│  │   → Create multi-step plan                                │  │
│  │   → Execute plan                                          │  │
│  │   → Synthesize comprehensive answer                       │  │
│  │   → Show <deep_reasoning> to user                         │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Reasoning Trace (INTERNAL)                                │  │
│  │  • Log all thinking steps                                 │  │
│  │  • Track duration of each step                            │  │
│  │  • Record confidence                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        RESPONSE                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Visible to User:                                          │  │
│  │  • answer: "You wake at 3 AM because..."                  │  │
│  │  • thinking: "<thinking>...</thinking>" (if not QUICK)    │  │
│  │  • confidence: 0.9                                        │  │
│  │  • mode: "thinking"                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Internal (for debugging/auditing):                        │  │
│  │  • fusion_id: "abc123"                                    │  │
│  │  • reasoning_trace: {...}                                 │  │
│  │  • retrieved_docs: [...]                                  │  │
│  │  • contradictions: [...]                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Fusion Tracking (Internal Hooks)

```
USER QUERY: "What time should I stop drinking coffee?"

┌─────────────────────────────────────────────────────────────┐
│ Step 1: Gather Context                                       │
├─────────────────────────────────────────────────────────────┤
│ Memories Retrieved:                                          │
│  ✓ "User prefers waking up at 6 AM"                         │
│  ✓ "User is sensitive to caffeine"                          │
│  ✓ "User has trouble sleeping after 11 PM"                  │
│                                                              │
│ Facts Retrieved (Vector Search):                             │
│  ✓ "Caffeine half-life is 5-6 hours..."                     │
│  ✓ "Avoid caffeine 6-8 hours before bed..."                 │
│                                                              │
│ Contradictions (SSE):                                        │
│  ✓ Doc A: "Caffeine affects vary by person"                 │
│  ✓ Doc B: "6-hour rule applies to most people"              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: INVISIBLE FUSION TRACKING                            │
├─────────────────────────────────────────────────────────────┤
│ Logged to: personal_agent/lineage.jsonl                      │
│                                                              │
│ {                                                            │
│   "fusion_id": "f7a2b8c1",                                  │
│   "timestamp": "2024-01-15T14:30:00",                       │
│   "session_id": "sess_xyz",                                 │
│   "query": "What time should I stop drinking coffee?",      │
│   "reasoning_mode": "thinking",                             │
│   "memories_used": [                                        │
│     "User prefers waking up at 6 AM",                       │
│     "User is sensitive to caffeine",                        │
│     "User has trouble sleeping after 11 PM"                 │
│   ],                                                         │
│   "facts_retrieved": [                                      │
│     {"text": "Caffeine half-life is 5-6 hours...",         │
│      "source": "sleep_science.txt",                        │
│      "score": 0.92},                                       │
│     {"text": "Avoid caffeine 6-8 hours before bed...",     │
│      "source": "health_guide.txt",                         │
│      "score": 0.88}                                        │
│   ],                                                         │
│   "contradictions_found": [                                 │
│     {"summary": "Individual caffeine sensitivity varies"}   │
│   ]                                                          │
│ }                                                            │
│                                                              │
│ ► This logging is INVISIBLE to the user                     │
│ ► Used for debugging, auditing, analysis                    │
│ ► Shows exactly what context was used when                  │
└─────────────────────────────────────────────────────────────┘
```

## Reasoning Modes Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│                       QUICK MODE                                  │
├──────────────────────────────────────────────────────────────────┤
│ Query: "What's 2+2?"                                             │
│                                                                  │
│ Internal Process:                                                │
│  1. Check if answer is trivial → YES                            │
│  2. Generate direct answer → "4"                                │
│  3. Log trace (invisible)                                        │
│                                                                  │
│ User Sees:                                                       │
│  Answer: "4"                                                     │
│  Thinking: None (hidden)                                         │
│  Confidence: 0.8                                                 │
│                                                                  │
│ Duration: ~50ms                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      THINKING MODE                                │
├──────────────────────────────────────────────────────────────────┤
│ Query: "Why does exercise help with sleep?"                     │
│                                                                  │
│ Internal Process:                                                │
│  1. Analyze query complexity                                     │
│  2. Identify sub-questions: ["exercise effects", "sleep"]       │
│  3. Check contradictions → 1 found                              │
│  4. Plan approach → "Address contradiction, then explain"       │
│  5. Generate answer with context                                │
│                                                                  │
│ User Sees:                                                       │
│  Thinking:                                                       │
│    <thinking>                                                    │
│    [analysis] Found 3 docs, 1 contradiction                     │
│    [contradiction_analysis] Multiple perspectives detected       │
│    [planning] Will explain both views, then synthesize          │
│    [answer_generation] Generated comprehensive answer           │
│    </thinking>                                                   │
│                                                                  │
│  Answer: "Exercise helps sleep in two ways... However,          │
│           timing matters because... [comprehensive answer]"      │
│  Confidence: 0.9                                                 │
│                                                                  │
│ Duration: ~500ms                                                 │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        DEEP MODE                                  │
├──────────────────────────────────────────────────────────────────┤
│ Query: "Compare sleep stages and explain memory effects"        │
│                                                                  │
│ Internal Process:                                                │
│  1. Decompose into sub-questions                                │
│     → ["sleep stages", "REM", "deep sleep", "memory"]          │
│  2. Deep contradiction analysis (3 contradictions)              │
│  3. Create multi-step reasoning plan                            │
│  4. Execute each step of plan                                   │
│  5. Synthesize comprehensive answer                             │
│  6. Verify consistency                                          │
│                                                                  │
│ User Sees:                                                       │
│  Thinking:                                                       │
│    <deep_reasoning>                                              │
│    Step 1: decomposition (45ms)                                 │
│      Identified 4 sub-questions                                 │
│                                                                  │
│    Step 2: deep_contradiction_1 (120ms)                         │
│      Analyzing REM sleep perspective differences                │
│                                                                  │
│    Step 3: deep_contradiction_2 (115ms)                         │
│      Analyzing deep sleep vs light sleep debate                 │
│                                                                  │
│    Step 4: planning (80ms)                                      │
│      Plan: Compare stages, explain mechanisms, synthesize       │
│                                                                  │
│    Step 5: execution (300ms)                                    │
│      Executed multi-step analysis                               │
│                                                                  │
│    Step 6: synthesis (200ms)                                    │
│      Comprehensive answer synthesized                           │
│    </deep_reasoning>                                             │
│                                                                  │
│  Answer: [Comprehensive multi-paragraph answer addressing       │
│           all aspects, contradictions, and synthesis]           │
│  Confidence: 0.95                                                │
│                                                                  │
│ Duration: ~860ms                                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
User Query
    │
    ├─► RAG Engine
    │    ├─► Vector Search (ChromaDB)
    │    ├─► SSE (Contradiction Detection)
    │    └─► Memory System (Learned Context)
    │
    ├─► Memory Fusion (INTERNAL HOOK)
    │    └─► Log to lineage.jsonl
    │         • fusion_id
    │         • memories used
    │         • facts retrieved
    │         • contradictions found
    │
    ├─► Reasoning Engine
    │    ├─► Auto-detect mode
    │    ├─► Execute reasoning
    │    │    ├─► QUICK: Direct answer
    │    │    ├─► THINKING: Analyze → Plan → Answer
    │    │    └─► DEEP: Decompose → Analyze → Execute → Synthesize
    │    └─► Log reasoning trace (INTERNAL)
    │
    └─► Response
         ├─► User sees:
         │    • answer
         │    • thinking (if THINKING/DEEP)
         │    • confidence
         │
         └─► Internal tracking:
              • fusion_id
              • reasoning_trace
              • retrieved_docs
              • contradictions
```

## Key Concepts

### 1. Internal Hooks = Invisible Logging
- **What**: Background tracking of what context was used
- **Where**: Logged to `lineage.jsonl`
- **Why**: Debugging, auditing, understanding what the system knows
- **User Impact**: None (completely invisible)

### 2. Reasoning Modes = Pre-Generation Thinking
- **What**: System thinks before answering (like Claude/Copilot)
- **How**: Analyzes query, plans approach, executes steps
- **Visibility**: Thinking process shown in THINKING/DEEP modes
- **User Impact**: More transparent, trustworthy answers

### 3. Memory Fusion = Context Combination
- **What**: Merging learned memories + retrieved facts
- **Tracking**: Every fusion gets unique ID and full log
- **Why**: Know exactly what information contributed to each answer
- **Example**: "Used 3 memories + 5 facts → Answer X"
