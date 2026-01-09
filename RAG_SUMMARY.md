# RAG + Reasoning System - Implementation Complete

## What Was Built

A complete **Retrieval-Augmented Generation (RAG) system with advanced reasoning modes** and internal memory tracking.

### Components Created

1. **RAG Engine** ([personal_agent/rag.py](personal_agent/rag.py))
   - Vector search with ChromaDB
   - SSE contradiction detection
   - Memory context integration
   - Internal fusion tracking (invisible hooks)

2. **Reasoning Engine** ([personal_agent/reasoning.py](personal_agent/reasoning.py))
   - QUICK mode: Direct answers
   - THINKING mode: Analyze → Reason → Answer (like Claude)
   - DEEP mode: Extended multi-step reasoning
   - RESEARCH mode: Multi-step information gathering

3. **Memory Lineage Tracker** ([personal_agent/rag.py](personal_agent/rag.py))
   - Invisible background logging
   - Tracks what memories + facts combined when
   - JSONL-based fusion event log

4. **Demo & Documentation**
   - [rag_reasoning_demo.py](rag_reasoning_demo.py) - Comprehensive demos
   - [RAG_REASONING_README.md](RAG_REASONING_README.md) - Full documentation
   - [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md) - Visual diagrams

## How It Works

### 1. User Asks Question

```python
from personal_agent.rag import RAGEngine

rag = RAGEngine()

result = rag.query_with_reasoning(
    user_query="Why do I wake up at 3 AM?",
    memory_context=["User goes to bed at 11 PM", "User drinks coffee until 5 PM"],
    mode=None  # Auto-detect
)
```

### 2. System Processes (Invisible)

```
┌─ RAG Layer ─────────────────────────────────────┐
│ • Vector search finds relevant docs             │
│ • SSE checks for contradictions                 │
│ • Memory system adds learned context            │
└─────────────────────────────────────────────────┘
                    ▼
┌─ Internal Hooks (INVISIBLE) ────────────────────┐
│ • Log fusion event to lineage.jsonl             │
│ • Track: query, memories used, facts retrieved  │
│ • Generate fusion_id for tracing                │
└─────────────────────────────────────────────────┘
                    ▼
┌─ Reasoning Engine ──────────────────────────────┐
│ • Auto-detect mode (QUICK/THINKING/DEEP)        │
│ • Execute thinking process                      │
│ • Generate answer                               │
│ • Log reasoning trace (internal)                │
└─────────────────────────────────────────────────┘
```

### 3. User Gets Response

```python
{
    'answer': "You wake at 3 AM because...",
    'thinking': "<thinking>...[analysis]...</thinking>",  # Visible if THINKING/DEEP
    'mode': 'thinking',
    'confidence': 0.9,
    
    # Internal (for debugging)
    'fusion_id': 'abc123',
    'reasoning_trace': {...},
    'retrieved_docs': [...],
    'contradictions': [...]
}
```

## Key Features

### Internal Hooks (Memory Tracking)

**What it does:**
- Invisibly logs what information was used where
- Background tracking for debugging/auditing
- "At timestamp X, we combined memory Y with fact Z"

**Logged to:** `personal_agent/lineage.jsonl`

**Example entry:**
```json
{
  "fusion_id": "abc123",
  "timestamp": "2024-01-15T10:30:00",
  "query": "What time should I stop drinking coffee?",
  "memories_used": ["User prefers waking at 6 AM", "User is caffeine-sensitive"],
  "facts_retrieved": [{"text": "Caffeine half-life is 5-6 hours...", "source": "sleep.txt"}],
  "contradictions_found": [],
  "reasoning_mode": "thinking"
}
```

**Accessing:**
```python
# Get specific fusion
lineage = rag.get_fusion_lineage("abc123")

# Get recent fusions
recent = rag.get_recent_fusions(limit=10)
```

### Advanced Reasoning (Like Claude's Thinking)

**QUICK Mode:**
- Direct answer, no visible thinking
- Internal trace still logged

**THINKING Mode:**
```
<thinking>
[analysis] Query: 'Why does exercise help sleep?' | Found 5 docs, 1 contradiction
[contradiction_analysis] Detected 1 contradiction requiring reconciliation
[planning] Plan: Present all perspectives, explain context for each
[answer_generation] Generated final answer
</thinking>
```

**DEEP Mode:**
```
<deep_reasoning>
Step 1: decomposition (45ms)
  Identified 3 sub-questions: ['exercise', 'sleep quality', 'timing']

Step 2: deep_contradiction_1 (120ms)
  Multiple valid perspectives on optimal exercise timing

Step 3: planning (80ms)
  Plan: Address each sub-question, reconcile contradictions, synthesize

Step 4: execution (300ms)
  Executed multi-step reasoning process

Step 5: synthesis (200ms)
  Comprehensive answer synthesized
</deep_reasoning>
```

## Quick Start

### Install Dependencies

```bash
pip install chromadb
```

### Basic Usage

```python
from personal_agent.rag import RAGEngine

# Initialize
rag = RAGEngine()

# Index documents
rag.index_document("knowledge.txt", collection_name="main")

# Query with auto-detected reasoning
result = rag.query_with_reasoning(
    user_query="Your question here",
    memory_context=["Learned fact 1", "Learned fact 2"],
    mode=None  # Auto-detect: QUICK, THINKING, or DEEP
)

# Get answer
print(result['answer'])

# See thinking process (if THINKING/DEEP mode)
if result['thinking']:
    print(result['thinking'])

# Check internal tracking
lineage = rag.get_fusion_lineage(result['fusion_id'])
print(f"Used {len(lineage['memories_used'])} memories")
print(f"Retrieved {len(lineage['facts_retrieved'])} facts")
```

### Run Demos

```bash
python rag_reasoning_demo.py
```

6 comprehensive demos:
1. Basic RAG (vector search + SSE)
2. Reasoning modes (QUICK, THINKING, DEEP)
3. Memory fusion tracking (internal hooks)
4. Reasoning traces (observability)
5. Auto mode detection
6. Complete workflow

## Integration with Personal Agent

The RAG + Reasoning system is designed to integrate with the personal learning agent:

```python
from personal_agent import PersonalAgent

agent = PersonalAgent(
    name="MyAgent",
    rag_enabled=True  # Enable RAG + reasoning
)

# Agent uses RAG for knowledge retrieval
# Reasoning engine for complex questions
# Memory fusion tracking for observability
response = agent.chat("Why do I wake up at 3 AM?")
```

## File Structure

```
personal_agent/
├── rag.py                  # RAG engine + memory lineage
├── reasoning.py            # Reasoning engine with thinking modes
├── lineage.jsonl           # Fusion event log (auto-created)
├── vector_db/              # ChromaDB storage (auto-created)
└── indices/                # SSE indices (auto-created)

rag_reasoning_demo.py       # Comprehensive demos
RAG_REASONING_README.md     # Full documentation
RAG_ARCHITECTURE.md         # Visual diagrams
RAG_SUMMARY.md             # This file
```

## What Makes This Special

### 1. Internal Observability
- Every query is fully tracked (invisibly)
- Know exactly what context was used when
- Debugging/auditing built-in from the start

### 2. Thinking Like Claude/Copilot
- Pre-generation analysis and planning
- Visible reasoning process for complex questions
- Multiple modes for different complexity levels

### 3. Memory Fusion Tracking
- Background hooks log what was combined
- Full lineage: memories + facts → answer
- JSONL format for easy analysis

### 4. Auto Mode Detection
- System decides: QUICK, THINKING, or DEEP
- Based on: contradictions, complexity, doc count
- Manual override available

## Example Workflow

```python
# 1. User asks complex question
query = "I wake up at 3 AM and can't fall back asleep. Why?"

# 2. Add learned context
memories = [
    "User goes to bed at 11 PM",
    "User drinks coffee until 5 PM",
    "User has high stress job"
]

# 3. Query with reasoning
result = rag.query_with_reasoning(
    user_query=query,
    memory_context=memories,
    mode=None  # Auto-detect
)

# 4. Get comprehensive response
print("Answer:", result['answer'])
print("Mode:", result['mode'])  # → "thinking"

if result['thinking']:
    print("Thinking:")
    print(result['thinking'])

# 5. Inspect what happened internally
lineage = rag.get_fusion_lineage(result['fusion_id'])
print(f"\nInternal Tracking:")
print(f"  Memories used: {len(lineage['memories_used'])}")
print(f"  Facts retrieved: {len(lineage['facts_retrieved'])}")
print(f"  Contradictions: {len(lineage['contradictions_found'])}")

# 6. Analyze reasoning process
traces = rag.get_reasoning_traces(limit=1)
for step in traces[0]['thinking_steps']:
    print(f"  [{step['step_type']}] {step['duration_ms']:.0f}ms")
```

## Next Steps

### Immediate
1. Install ChromaDB: `pip install chromadb`
2. Run demo: `python rag_reasoning_demo.py`
3. Test with your own documents

### Integration
1. Connect to personal agent
2. Add LLM client (OpenAI/Anthropic) for actual answer generation
3. Build web UI for visualization

### Advanced
1. Add more reasoning modes (RESEARCH, VERIFICATION)
2. Implement memory policy system (save/forget rules)
3. Create fusion lineage analytics dashboard
4. Add reasoning performance optimization

## Technical Notes

### ChromaDB (Optional)
- Vector database for semantic search
- If not installed, RAG works without vector search
- Install: `pip install chromadb`

### SSE Integration
- Already integrated with SSE for contradiction detection
- Uses existing SSE indices
- No additional setup required

### Reasoning Engine
- Works without LLM (demo mode)
- Add LLM client for actual answer generation
- Supports OpenAI, Anthropic, etc.

## Summary

You now have:

✅ **RAG Engine** - Vector search + SSE + memory context  
✅ **Internal Hooks** - Invisible fusion tracking for debugging  
✅ **Reasoning Modes** - QUICK, THINKING, DEEP (like Claude)  
✅ **Memory Lineage** - Full audit trail of what was used when  
✅ **Auto Detection** - Smart mode selection based on complexity  
✅ **Observability** - Complete traces and logs for analysis  

**Bottom line:** A sophisticated RAG system that thinks before answering and tracks everything internally for debugging/auditing.
