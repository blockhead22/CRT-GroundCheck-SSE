# 🚀 RAG + Reasoning System - START HERE

**New Addition to AI_round2 Project**

## What This Is

A complete **Retrieval-Augmented Generation (RAG) system** with:
- Advanced reasoning modes (QUICK, THINKING, DEEP)
- Internal memory fusion tracking
- SSE contradiction detection
- Vector search with ChromaDB

**Think:** Claude's extended thinking + RAG + internal observability hooks

## 30-Second Quick Start

```bash
# Install
pip install chromadb

# Run demo
python rag_reasoning_demo.py
```

## 2-Minute Quick Start

```python
from personal_agent.rag import RAGEngine

# Initialize
rag = RAGEngine()

# Index knowledge
rag.index_document("your_knowledge.txt")

# Query with auto-reasoning
result = rag.query_with_reasoning(
    user_query="Your question here",
    mode=None  # Auto-detect: QUICK, THINKING, or DEEP
)

# See answer + thinking
print(result['answer'])
if result['thinking']:
    print(result['thinking'])

# Check what was used (internal tracking)
lineage = rag.get_fusion_lineage(result['fusion_id'])
print(f"Used {len(lineage['memories_used'])} memories")
print(f"Retrieved {len(lineage['facts_retrieved'])} facts")
```

## Documentation Map

### 🎯 Just Getting Started?
**Read:** [RAG_SUMMARY.md](RAG_SUMMARY.md) - Complete overview in 5 minutes

### 📋 Need Quick Lookup?
**Read:** [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md) - One-liners and patterns

### 📚 Want Full Documentation?
**Read:** [RAG_REASONING_README.md](RAG_REASONING_README.md) - Everything in detail

### 🏗️ Understand Architecture?
**Read:** [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md) - Visual diagrams

### 🔍 See All Docs?
**Read:** [RAG_INDEX.md](RAG_INDEX.md) - Complete documentation index

## What You Get

### 1. RAG Engine
```
Vector Search (ChromaDB)
    +
SSE Contradiction Detection
    +
Memory Context
    =
Comprehensive Retrieval
```

### 2. Reasoning Modes
```
QUICK Mode:
  Simple question → Direct answer
  (Internal thinking hidden)

THINKING Mode:
  Complex question → Analyze → Reason → Answer
  (Thinking process visible)

DEEP Mode:
  Very complex → Decompose → Analyze → Plan → Execute → Synthesize
  (Extended reasoning visible)
```

### 3. Internal Hooks
```
Every query logs (invisibly):
  - What memories were used
  - What facts were retrieved
  - What contradictions were found
  - What reasoning mode was used

Logged to: personal_agent/lineage.jsonl
```

## Key Files

### Run These
- `rag_reasoning_demo.py` - 6 standalone demos
- `enhanced_agent_demo.py` - Full integration examples

### Read These
- `RAG_SUMMARY.md` - Start here for overview
- `RAG_QUICK_REFERENCE.md` - Quick lookup
- `RAG_REASONING_README.md` - Full docs
- `RAG_ARCHITECTURE.md` - Visual diagrams

### Code
- `personal_agent/rag.py` - RAG engine (~450 lines)
- `personal_agent/reasoning.py` - Reasoning engine (~400 lines)

## Features

### ✅ Vector Search
Semantic search over documents with ChromaDB

### ✅ SSE Integration
Contradiction detection on retrieved docs

### ✅ Memory Fusion
Combines learned memories + retrieved facts

### ✅ Reasoning Modes
QUICK, THINKING, DEEP (like Claude's thinking)

### ✅ Internal Tracking
Invisible hooks logging what was used when

### ✅ Observability
Complete lineage and reasoning traces

## Example Output

### User Query
```
"Why do I wake up at 3 AM?"
```

### System Response
```
Mode: THINKING

Thinking:
<thinking>
[analysis] Found 5 docs about sleep cycles, 1 contradiction about causes
[contradiction_analysis] Multiple perspectives on midnight waking
[planning] Will explain common causes, then address user's specific context
[answer_generation] Generated comprehensive answer
</thinking>

Answer:
Waking at 3 AM typically happens due to sleep cycle transitions...
[comprehensive answer addressing multiple perspectives]

Confidence: 0.9
```

### Internal Tracking
```json
{
  "fusion_id": "abc123",
  "query": "Why do I wake up at 3 AM?",
  "memories_used": [
    "User goes to bed at 11 PM",
    "User drinks coffee until 5 PM"
  ],
  "facts_retrieved": [
    {"text": "Sleep cycles are 90 minutes...", "source": "sleep.txt"}
  ],
  "contradictions_found": [
    {"summary": "Multiple causes for midnight waking"}
  ],
  "reasoning_mode": "thinking"
}
```

## How It Fits Together

```
SSE Project (Phase C)
├── Honest observation layer
├── Contradiction detection
└── No learning, stateless

    +

Personal Agent (Phase D+)
├── Learning layer
├── Memory system
├── Preference tracking
└── Strategy adaptation

    +

RAG + Reasoning (NEW)
├── Vector search
├── Memory fusion tracking
├── Advanced reasoning modes
└── Internal observability

    =

Complete System
```

## Quick Commands

```bash
# Install dependencies
pip install chromadb

# Run RAG demos (6 demos)
python rag_reasoning_demo.py

# Run integration demos (5 scenarios)
python enhanced_agent_demo.py

# Test imports
python -c "from personal_agent.rag import RAGEngine; print('✅ OK')"
```

## Learning Path

### 5 Minutes
1. Read this file
2. Run: `python rag_reasoning_demo.py` (Demo 1)

### 15 Minutes
1. Read: [RAG_SUMMARY.md](RAG_SUMMARY.md)
2. Run: All demos in `rag_reasoning_demo.py`

### 30 Minutes
1. Read: [RAG_REASONING_README.md](RAG_REASONING_README.md)
2. Read: [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md)
3. Run: `enhanced_agent_demo.py`

### 1 Hour
1. Read all documentation
2. Study source code
3. Build your own integration

## Next Steps

1. **Install ChromaDB**: `pip install chromadb`
2. **Run demos**: `python rag_reasoning_demo.py`
3. **Read overview**: [RAG_SUMMARY.md](RAG_SUMMARY.md)
4. **Try examples**: From [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)
5. **Build something**: Use [enhanced_agent_demo.py](enhanced_agent_demo.py) as template

## Questions?

- **What is RAG?** [RAG_REASONING_README.md § RAG Layer](RAG_REASONING_README.md)
- **What are reasoning modes?** [RAG_REASONING_README.md § Reasoning Engine](RAG_REASONING_README.md)
- **What are internal hooks?** [RAG_REASONING_README.md § Memory Fusion Tracking](RAG_REASONING_README.md)
- **How do I use this?** [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)
- **See all docs?** [RAG_INDEX.md](RAG_INDEX.md)

## Summary

**You now have:**

✅ RAG engine (vector search + SSE + memory)  
✅ Reasoning modes (QUICK/THINKING/DEEP like Claude)  
✅ Internal tracking (fusion lineage + reasoning traces)  
✅ Complete observability (debug/audit everything)  
✅ Full documentation (guides, refs, examples)  
✅ Working demos (11 scenarios total)  

**Bottom line:** A sophisticated RAG system that thinks before answering and tracks everything internally.

---

**Ready?** → [RAG_SUMMARY.md](RAG_SUMMARY.md)
