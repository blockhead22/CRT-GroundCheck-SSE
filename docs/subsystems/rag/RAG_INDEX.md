# RAG + Reasoning System - Documentation Index

## Overview

Complete RAG (Retrieval-Augmented Generation) system with advanced reasoning modes and internal memory tracking.

**Key Features:**
- Vector search + SSE contradiction detection
- Reasoning modes: QUICK, THINKING, DEEP (like Claude's extended thinking)
- Internal fusion tracking (invisible hooks logging what was used when)
- Complete observability for debugging/auditing

## Quick Links

### Getting Started
- **[RAG_SUMMARY.md](RAG_SUMMARY.md)** - Start here! Complete overview and quick start
- **[RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)** - One-liners and common patterns
- **[RAG_REASONING_README.md](RAG_REASONING_README.md)** - Full documentation

### Understanding the System
- **[RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md)** - Visual diagrams and flow charts
- **[PERSONAL_AGENT_README.md](PERSONAL_AGENT_README.md)** - Integration with personal agent

### Examples & Demos
- **[rag_reasoning_demo.py](rag_reasoning_demo.py)** - 6 comprehensive demos
- **[enhanced_agent_demo.py](enhanced_agent_demo.py)** - Full integration examples

### Source Code
- **[personal_agent/rag.py](personal_agent/rag.py)** - RAG engine + memory lineage
- **[personal_agent/reasoning.py](personal_agent/reasoning.py)** - Reasoning engine with thinking modes

## Documentation Structure

```
📚 Documentation
├── 🚀 Quick Start
│   ├── RAG_SUMMARY.md              # Start here
│   └── RAG_QUICK_REFERENCE.md      # Fast lookup
│
├── 📖 Complete Guides
│   ├── RAG_REASONING_README.md     # Full documentation
│   └── RAG_ARCHITECTURE.md         # System design
│
├── 🔗 Integration
│   └── PERSONAL_AGENT_README.md    # Agent integration
│
└── 💻 Examples
    ├── rag_reasoning_demo.py       # Standalone demos
    └── enhanced_agent_demo.py      # Integration demos
```

## Quick Start (30 seconds)

```python
from personal_agent.rag import RAGEngine

# 1. Initialize
rag = RAGEngine()

# 2. Index knowledge
rag.index_document("knowledge.txt")

# 3. Query with reasoning
result = rag.query_with_reasoning(
    user_query="Your question here",
    mode=None  # Auto-detect: QUICK, THINKING, or DEEP
)

# 4. Get answer
print(result['answer'])
print(result['thinking'])  # See reasoning process
```

## Main Concepts

### 1. RAG (Retrieval-Augmented Generation)
Combines vector search, SSE contradiction detection, and memory context.

**Read:** [RAG_REASONING_README.md § RAG Layer](RAG_REASONING_README.md#1-rag-layer)

### 2. Memory Fusion Tracking (Internal Hooks)
Invisible background logging of what memories + facts were combined when.

**Read:** [RAG_REASONING_README.md § Memory Fusion Tracking](RAG_REASONING_README.md#2-memory-fusion-tracking-internal-hooks)

### 3. Reasoning Modes
Pre-generation thinking like Claude Sonnet or GitHub Copilot.

**Modes:**
- **QUICK**: Direct answer, no visible thinking
- **THINKING**: Analyze → Reason → Answer
- **DEEP**: Extended multi-step reasoning

**Read:** [RAG_REASONING_README.md § Reasoning Engine](RAG_REASONING_README.md#3-reasoning-engine)

### 4. Observability
Complete traces and lineage for debugging/auditing.

**Read:** [RAG_REASONING_README.md § Internal Observability](RAG_REASONING_README.md#internal-observability)

## Usage Examples

### Basic RAG Query
```python
result = rag.query(
    user_query="What helps with sleep?",
    collection_name="health",
    k=5
)
# Returns: retrieved_docs, contradictions, fusion_id, reasoning_required
```

### Query with Reasoning
```python
result = rag.query_with_reasoning(
    user_query="Why does exercise help with sleep?",
    memory_context=["User exercises at 6 AM"],
    mode=None  # Auto-detect
)
# Returns: answer, thinking, mode, confidence, fusion_id, reasoning_trace
```

### Access Fusion Lineage
```python
lineage = rag.get_fusion_lineage(result['fusion_id'])
print(lineage['memories_used'])     # What memories were used
print(lineage['facts_retrieved'])   # What facts were retrieved
print(lineage['reasoning_mode'])    # Which mode was used
```

### Access Reasoning Traces
```python
traces = rag.get_reasoning_traces(limit=5)
for trace in traces:
    print(trace['query'])
    print(trace['mode'])
    for step in trace['thinking_steps']:
        print(f"  [{step['step_type']}] {step['duration_ms']}ms")
```

## Features by Document

### [RAG_SUMMARY.md](RAG_SUMMARY.md)
- ✅ Complete overview
- ✅ Quick start guide
- ✅ Integration examples
- ✅ Technical notes
- ✅ Next steps

### [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)
- ✅ One-liner commands
- ✅ Common patterns
- ✅ Result structures
- ✅ Mode detection rules
- ✅ Troubleshooting

### [RAG_REASONING_README.md](RAG_REASONING_README.md)
- ✅ Full documentation
- ✅ Architecture details
- ✅ Complete workflow
- ✅ Auto mode detection
- ✅ Advanced features

### [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md)
- ✅ System flow diagrams
- ✅ Memory fusion tracking
- ✅ Reasoning modes comparison
- ✅ Data flow charts
- ✅ Key concepts

### [rag_reasoning_demo.py](rag_reasoning_demo.py)
- ✅ Demo 1: Basic RAG
- ✅ Demo 2: Reasoning modes
- ✅ Demo 3: Memory fusion tracking
- ✅ Demo 4: Reasoning traces
- ✅ Demo 5: Auto mode detection
- ✅ Demo 6: Complete workflow

### [enhanced_agent_demo.py](enhanced_agent_demo.py)
- ✅ Scenario 1: Learning over time
- ✅ Scenario 2: Deep reasoning
- ✅ Scenario 3: Fusion tracking
- ✅ Scenario 4: Reasoning modes
- ✅ Scenario 5: Full integration

## Key Files

### Source Code
| File | Purpose | Lines |
|------|---------|-------|
| [personal_agent/rag.py](personal_agent/rag.py) | RAG engine + memory lineage | ~450 |
| [personal_agent/reasoning.py](personal_agent/reasoning.py) | Reasoning engine with modes | ~400 |

### Documentation
| File | Purpose | Pages |
|------|---------|-------|
| [RAG_SUMMARY.md](RAG_SUMMARY.md) | Complete overview | ~250 lines |
| [RAG_REASONING_README.md](RAG_REASONING_README.md) | Full guide | ~500 lines |
| [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md) | Fast lookup | ~350 lines |
| [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md) | Visual diagrams | ~400 lines |

### Demos
| File | Purpose | Scenarios |
|------|---------|-----------|
| [rag_reasoning_demo.py](rag_reasoning_demo.py) | Standalone demos | 6 |
| [enhanced_agent_demo.py](enhanced_agent_demo.py) | Integration demos | 5 |

## Learning Path

### Beginner (15 minutes)
1. Read: [RAG_SUMMARY.md](RAG_SUMMARY.md) § What Was Built
2. Read: [RAG_SUMMARY.md](RAG_SUMMARY.md) § How It Works
3. Run: `python rag_reasoning_demo.py` (Demo 1 & 2)

### Intermediate (30 minutes)
1. Read: [RAG_REASONING_README.md](RAG_REASONING_README.md) § Architecture
2. Read: [RAG_ARCHITECTURE.md](RAG_ARCHITECTURE.md) § System Flow
3. Run: `python rag_reasoning_demo.py` (All demos)
4. Try: Code examples from [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)

### Advanced (1 hour)
1. Read: Full [RAG_REASONING_README.md](RAG_REASONING_README.md)
2. Study: [personal_agent/rag.py](personal_agent/rag.py) source code
3. Study: [personal_agent/reasoning.py](personal_agent/reasoning.py) source code
4. Run: `python enhanced_agent_demo.py` (All scenarios)
5. Build: Your own integration

## Common Questions

### How is this different from regular RAG?
**Regular RAG:** Vector search → Retrieve docs → Generate answer

**This system:**
- Vector search + SSE contradiction detection
- Internal fusion tracking (what was used when)
- Advanced reasoning modes (visible thinking)
- Complete observability (lineage + traces)

### What are "internal hooks"?
Background logging that's invisible to the user. Tracks what memories and facts were combined for each answer. Used for debugging/auditing.

**Example:** "At 2024-01-15 10:30, we combined memory X with fact Y to answer query Z"

### What does "reasoning like Claude" mean?
Pre-generation thinking and planning. The system:
1. Analyzes the query
2. Plans the approach
3. Executes reasoning steps
4. Generates answer

In THINKING/DEEP modes, this process is visible to the user.

### When should I use each mode?
- **QUICK**: Simple factual questions, no contradictions
- **THINKING**: Complex questions, contradictions present, "why/how" questions
- **DEEP**: Multiple contradictions, very complex multi-part questions

Or let the system auto-detect with `mode=None`.

### How do I debug what the system knows?
```python
# Check fusion lineage
lineage = rag.get_fusion_lineage(fusion_id)
print(lineage['memories_used'])
print(lineage['facts_retrieved'])

# Check reasoning traces
traces = rag.get_reasoning_traces(limit=10)
for trace in traces:
    print(trace['thinking_steps'])
```

## Dependencies

```bash
pip install chromadb  # Vector database
```

SSE is already installed and integrated.

## Next Steps

1. **Install**: `pip install chromadb`
2. **Run demos**: `python rag_reasoning_demo.py`
3. **Read docs**: Start with [RAG_SUMMARY.md](RAG_SUMMARY.md)
4. **Try examples**: From [RAG_QUICK_REFERENCE.md](RAG_QUICK_REFERENCE.md)
5. **Build integration**: See [enhanced_agent_demo.py](enhanced_agent_demo.py)

## Support & Feedback

- **Issues**: Check [RAG_QUICK_REFERENCE.md § Troubleshooting](RAG_QUICK_REFERENCE.md#troubleshooting)
- **Examples**: All demos in `rag_reasoning_demo.py` and `enhanced_agent_demo.py`
- **Source**: Read the code in `personal_agent/rag.py` and `personal_agent/reasoning.py`

## Summary

This system gives you:

✅ **RAG**: Vector search + SSE contradiction detection  
✅ **Internal Hooks**: Invisible tracking of what info was used  
✅ **Reasoning Modes**: Like Claude's thinking - visible reasoning  
✅ **Observability**: Full lineage and trace logging  

**Bottom line:** A sophisticated RAG system that thinks before answering and tracks everything internally.
