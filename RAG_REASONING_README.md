# RAG + Reasoning Engine

**Advanced retrieval system with internal observability and thinking modes**

Like Claude Sonnet's extended thinking or GitHub Copilot's pre-generation analysis.

## Overview

This system combines:

1. **RAG (Retrieval-Augmented Generation)**
   - Vector search with ChromaDB
   - SSE contradiction detection
   - Memory context integration

2. **Memory Fusion Tracking** (Internal Hooks)
   - Invisible background logging
   - Tracks what memories + facts were combined when
   - Lineage for debugging/auditing

3. **Advanced Reasoning Modes**
   - **QUICK**: Direct answer, no visible thinking
   - **THINKING**: Analyze → Reason → Answer (like Claude's thinking)
   - **DEEP**: Extended reasoning with sub-tasks
   - **RESEARCH**: Multi-step information gathering

## Quick Start

```python
from personal_agent.rag import RAGEngine
from personal_agent.reasoning import ReasoningMode

# Create RAG engine
rag = RAGEngine()

# Index documents
rag.index_document("my_knowledge.txt", collection_name="main")

# Query with auto-detected reasoning
result = rag.query_with_reasoning(
    user_query="Why does exercise help with sleep?",
    memory_context=["User exercises at 6 AM", "User prefers 8 hours sleep"],
    mode=None  # Auto-detect: QUICK, THINKING, or DEEP
)

print(result['answer'])
print(result['thinking'])  # See the reasoning process
print(result['fusion_id'])  # Internal tracking ID
```

## Architecture

### 1. RAG Layer

**What it does:**
- Semantic search over your documents (ChromaDB)
- Contradiction detection (SSE)
- Memory context integration

**Example:**
```python
result = rag.query(
    user_query="What helps with sleep?",
    collection_name="health_docs",
    k=5,  # Retrieve top 5 docs
    memory_context=["User is sensitive to caffeine"]
)

# Returns:
# {
#   'retrieved_docs': [...],      # Vector search results
#   'contradictions': [...],      # SSE found contradictions
#   'memory_context': [...],      # Your learned context
#   'fusion_id': '...',           # Internal tracking
#   'reasoning_required': True    # Detected complexity
# }
```

### 2. Memory Fusion Tracking (Internal Hooks)

**What it does:**
- **Invisibly** logs what information was used where
- Background tracking for debugging/auditing
- "At timestamp X, we combined memory Y with fact Z"

**Logged to:** `personal_agent/lineage.jsonl`

**Format:**
```json
{
  "fusion_id": "abc123",
  "timestamp": "2024-01-15T10:30:00",
  "session_id": "xyz789",
  "query": "What time should I stop drinking coffee?",
  "reasoning_mode": "thinking",
  "memories_used": [
    "User prefers waking up at 6 AM",
    "User is sensitive to caffeine"
  ],
  "facts_retrieved": [
    {"text": "Caffeine has a half-life of 5-6 hours...", "source": "sleep.txt"}
  ],
  "contradictions_found": []
}
```

**Accessing lineage:**
```python
# Get specific fusion event
lineage = rag.get_fusion_lineage("abc123")

# Get recent fusions
recent = rag.get_recent_fusions(limit=10)
```

### 3. Reasoning Engine

**What it does:**
- Analyzes query complexity
- Decides thinking mode
- Plans approach before answering
- Tracks reasoning steps internally

**Modes:**

#### QUICK Mode
- **When**: Simple questions, no contradictions
- **Process**: Direct answer (internal thinking hidden)
- **Example**: "What's 2+2?"

```python
result = rag.query_with_reasoning(
    user_query="What's the capital of France?",
    mode=ReasoningMode.QUICK
)
# Returns answer immediately, no visible thinking
```

#### THINKING Mode
- **When**: Complex questions, contradictions present
- **Process**: Analyze → Identify sub-questions → Reason → Answer
- **Example**: "Why does exercise help with sleep?"

```python
result = rag.query_with_reasoning(
    user_query="How does caffeine affect sleep quality?",
    mode=ReasoningMode.THINKING
)

# result['thinking'] shows:
# <thinking>
# [analysis] Query: 'How does caffeine affect sleep quality?' | Found 5 docs, 1 contradictions
# [contradiction_analysis] Detected 1 contradictions requiring reconciliation
# [planning] Plan: Present all perspectives from contradictions, explain context for each
# [answer_generation] Generated final answer
# </thinking>
```

#### DEEP Mode
- **When**: Multiple contradictions, very complex queries
- **Process**: Decompose → Analyze deeply → Plan → Execute → Synthesize
- **Example**: "Compare REM vs deep sleep and explain how each affects memory consolidation"

```python
result = rag.query_with_reasoning(
    user_query="Compare sleep stages and their cognitive effects",
    mode=ReasoningMode.DEEP
)

# result['thinking'] shows detailed multi-step reasoning:
# <deep_reasoning>
# Step 1: decomposition
# Identified 2 sub-questions: ['sleep stages', 'cognitive effects']
# (Duration: 45ms)
#
# Step 2: deep_contradiction_1
# Contradiction analysis: Multiple valid perspectives detected
# (Duration: 120ms)
# ...
# </deep_reasoning>
```

## Complete Workflow Example

```python
from personal_agent.rag import RAGEngine

# Initialize
rag = RAGEngine()

# Index your knowledge
rag.index_document("health_knowledge.txt", collection_name="health")

# User asks question
user_query = "I wake up at 3 AM and can't fall back asleep. Why?"

# Add learned memory context
memories = [
    "User goes to bed around 11 PM",
    "User drinks coffee until 5 PM",
    "User has high stress job"
]

# Query with reasoning
result = rag.query_with_reasoning(
    user_query=user_query,
    collection_name="health",
    memory_context=memories,
    mode=None  # Auto-detect
)

# 1. See the answer
print("Answer:", result['answer'])

# 2. See the thinking process (if THINKING or DEEP mode)
if result['thinking']:
    print("Thinking:", result['thinking'])

# 3. Check what was retrieved
print(f"Retrieved {len(result['retrieved_docs'])} documents")

# 4. Check contradictions
if result['contradictions']:
    print(f"Found {len(result['contradictions'])} contradictions")

# 5. View internal fusion tracking
lineage = rag.get_fusion_lineage(result['fusion_id'])
print(f"Used {len(lineage['memories_used'])} memories")
print(f"Retrieved {len(lineage['facts_retrieved'])} facts")

# 6. View reasoning trace (internal)
traces = rag.get_reasoning_traces(limit=1)
for step in traces[0]['thinking_steps']:
    print(f"[{step['step_type']}] {step['duration_ms']}ms")
```

## Auto Mode Detection

The system automatically detects which reasoning mode to use:

```python
result = rag.query_with_reasoning(
    user_query="...",
    mode=None  # Auto-detect
)
```

**Triggers for each mode:**

| Mode | Triggers |
|------|----------|
| **QUICK** | Simple question, no contradictions, clear answer available |
| **THINKING** | Question words (why/how/explain), contradictions present |
| **DEEP** | Multiple contradictions (3+), very complex multi-part question |
| **RESEARCH** | No docs found, query contains "search/find/research/latest" |

## Internal Observability

### Fusion Lineage

Every query logs what information was combined:

```python
# Automatic logging (invisible to user)
fusion_id = rag.query_with_reasoning(...)['fusion_id']

# Later: Inspect what happened
lineage = rag.get_fusion_lineage(fusion_id)
print(f"Query: {lineage['query']}")
print(f"Memories used: {lineage['memories_used']}")
print(f"Facts retrieved: {lineage['facts_retrieved']}")
print(f"Contradictions: {lineage['contradictions_found']}")
```

### Reasoning Traces

Every reasoning session is internally tracked:

```python
traces = rag.get_reasoning_traces(limit=5)

for trace in traces:
    print(f"Query: {trace['query']}")
    print(f"Mode: {trace['mode']}")
    print(f"Steps: {len(trace['thinking_steps'])}")
    print(f"Duration: {trace['total_duration_ms']}ms")
    
    for step in trace['thinking_steps']:
        print(f"  [{step['step_type']}] {step['content']}")
        print(f"  Time: {step['duration_ms']}ms")
```

## Integration with Personal Agent

The RAG + Reasoning system integrates with the personal learning agent:

```python
from personal_agent import PersonalAgent

agent = PersonalAgent(
    name="MyAgent",
    rag_enabled=True  # Enable RAG + reasoning
)

# Agent now uses RAG for knowledge retrieval
# And reasoning engine for complex questions
response = agent.chat("Why do I wake up at 3 AM?")

# Internally:
# 1. Retrieves learned memories about user
# 2. Searches knowledge base (RAG)
# 3. Detects contradictions (SSE)
# 4. Reasons about the answer (THINKING mode)
# 5. Logs fusion event (lineage tracking)
# 6. Returns answer with thinking visible (if complex)
```

## Advanced Features

### Custom Reasoning Mode

```python
from personal_agent.reasoning import ReasoningMode

# Force deep reasoning even for simple questions
result = rag.query_with_reasoning(
    user_query="What's 2+2?",
    mode=ReasoningMode.DEEP
)
# Will decompose, plan, execute, synthesize (overkill but demonstrates)
```

### Batch Lineage Analysis

```python
# Get all fusions from last 24 hours
recent_fusions = rag.get_recent_fusions(limit=100)

# Analyze what's being used
memory_usage = {}
for fusion in recent_fusions:
    for mem in fusion['memories_used']:
        memory_usage[mem] = memory_usage.get(mem, 0) + 1

# See which memories are used most
print("Most used memories:")
for mem, count in sorted(memory_usage.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {count}x: {mem}")
```

### Reasoning Performance Analysis

```python
# Get reasoning traces
traces = rag.get_reasoning_traces(limit=50)

# Analyze performance by mode
from collections import defaultdict
stats = defaultdict(list)

for trace in traces:
    stats[trace['mode']].append(trace['total_duration_ms'])

# Average time per mode
for mode, times in stats.items():
    avg_time = sum(times) / len(times)
    print(f"{mode}: {avg_time:.0f}ms average")
```

## Files Created

- `personal_agent/rag.py` - RAG engine + memory lineage
- `personal_agent/reasoning.py` - Reasoning engine with thinking modes
- `personal_agent/lineage.jsonl` - Fusion event log (auto-created)
- `rag_reasoning_demo.py` - Comprehensive demos

## Dependencies

```bash
pip install chromadb  # Vector database
# SSE already installed
```

## Demo

Run the comprehensive demo:

```bash
python rag_reasoning_demo.py
```

Demos include:
1. Basic RAG (vector search + SSE)
2. Reasoning modes (QUICK, THINKING, DEEP)
3. Memory fusion tracking (internal hooks)
4. Reasoning traces (observability)
5. Auto mode detection
6. Complete workflow

## Summary

This system gives you:

1. **RAG**: Semantic search + contradiction detection
2. **Internal Hooks**: Invisible tracking of what info was used when
3. **Reasoning Modes**: Like Claude's thinking - visible reasoning process
4. **Observability**: Full lineage and trace logging for debugging

**Key insight:** The system thinks before answering (like Claude/Copilot), and tracks what it used internally (for auditing/debugging).
