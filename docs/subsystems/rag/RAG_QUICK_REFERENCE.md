# RAG + Reasoning Quick Reference

## One-Liners

```python
# Basic RAG query
from personal_agent.rag import RAGEngine
rag = RAGEngine()
result = rag.query("Your question", collection_name="main", k=5)

# RAG with reasoning
result = rag.query_with_reasoning("Your question", mode=None)  # Auto-detect mode

# Get fusion lineage
lineage = rag.get_fusion_lineage(result['fusion_id'])

# Get reasoning traces
traces = rag.get_reasoning_traces(limit=10)
```

## Common Tasks

### Initialize RAG Engine
```python
from personal_agent.rag import RAGEngine

rag = RAGEngine(
    vector_db_path="personal_agent/vector_db",
    sse_indices_path="personal_agent/indices",
    llm_client=None  # Optional: Add OpenAI/Anthropic client
)
```

### Index Documents
```python
# Single document
rag.index_document("knowledge.txt", collection_name="main")

# Multiple documents
docs = ["doc1.txt", "doc2.txt", "doc3.txt"]
for doc in docs:
    rag.index_document(doc, collection_name="knowledge_base")
```

### Query with Auto-Detection
```python
result = rag.query_with_reasoning(
    user_query="Your question here",
    collection_name="main",
    memory_context=["User preference 1", "User preference 2"],
    mode=None  # Auto-detect: QUICK, THINKING, or DEEP
)

# Access results
answer = result['answer']
thinking = result['thinking']  # None if QUICK mode
confidence = result['confidence']
mode = result['mode']
```

### Force Specific Mode
```python
from personal_agent.reasoning import ReasoningMode

# Quick mode (no visible thinking)
result = rag.query_with_reasoning(query, mode=ReasoningMode.QUICK)

# Thinking mode (analyze → reason → answer)
result = rag.query_with_reasoning(query, mode=ReasoningMode.THINKING)

# Deep mode (extended multi-step reasoning)
result = rag.query_with_reasoning(query, mode=ReasoningMode.DEEP)
```

### Get Fusion Lineage
```python
# Specific fusion
lineage = rag.get_fusion_lineage("fusion_id_here")

print(lineage['query'])
print(lineage['memories_used'])
print(lineage['facts_retrieved'])
print(lineage['contradictions_found'])

# Recent fusions
recent = rag.get_recent_fusions(limit=10)
for fusion in recent:
    print(f"{fusion['timestamp']}: {fusion['query']}")
```

### Get Reasoning Traces
```python
# Recent traces
traces = rag.get_reasoning_traces(limit=5)

for trace in traces:
    print(f"Query: {trace['query']}")
    print(f"Mode: {trace['mode']}")
    print(f"Duration: {trace['total_duration_ms']}ms")
    
    for step in trace['thinking_steps']:
        print(f"  [{step['step_type']}] {step['duration_ms']}ms")
```

## Enhanced Agent Integration

### Basic Setup
```python
from personal_agent.memory import MemorySystem
from personal_agent.rag import RAGEngine

class MyAgent:
    def __init__(self):
        self.memory = MemorySystem("agent.db")
        self.rag = RAGEngine()
    
    def chat(self, message):
        # Get learned memories
        preferences = self.memory.get_all_preferences()
        memory_context = [f"{p['preference_type']}: {p['preference_value']}" 
                         for p in preferences]
        
        # Query with reasoning
        result = self.rag.query_with_reasoning(
            user_query=message,
            memory_context=memory_context
        )
        
        # Store conversation
        self.memory.store_conversation(message, result['answer'])
        
        return result

agent = MyAgent()
result = agent.chat("Your question")
```

## Result Structure

### query() Returns
```python
{
    'retrieved_docs': [
        {'text': '...', 'source': 'file.txt', 'score': 0.92, 'id': '...'},
        ...
    ],
    'contradictions': [
        {'summary': '...', 'claims': [...]},
        ...
    ],
    'memory_context': ['learned fact 1', 'learned fact 2'],
    'fusion_id': 'abc123',
    'reasoning_required': True  # or False
}
```

### query_with_reasoning() Returns
```python
{
    'answer': 'The final answer text',
    'thinking': '<thinking>...</thinking>',  # or None if QUICK mode
    'mode': 'thinking',  # quick, thinking, or deep
    'confidence': 0.9,
    'reasoning_trace': {...},  # Internal trace
    'retrieved_docs': [...],
    'contradictions': [...],
    'fusion_id': 'abc123'
}
```

### Fusion Lineage Structure
```python
{
    'fusion_id': 'abc123',
    'timestamp': '2024-01-15T10:30:00',
    'session_id': 'sess_xyz',
    'query': 'The user question',
    'reasoning_mode': 'thinking',
    'memories_used': ['memory 1', 'memory 2'],
    'facts_retrieved': [
        {'text': '...', 'source': 'file.txt', 'score': 0.92},
        ...
    ],
    'contradictions_found': [...]
}
```

### Reasoning Trace Structure
```python
{
    'query': 'The user question',
    'mode': 'thinking',
    'thinking_steps': [
        {
            'step_type': 'analysis',
            'content': 'Analysis text',
            'duration_ms': 45.3,
            'timestamp': '2024-01-15T10:30:00.123'
        },
        ...
    ],
    'decision': 'analyzed_and_answered',
    'confidence': 0.9,
    'contradictions_found': 1,
    'total_duration_ms': 523.7
}
```

## Mode Detection Rules

| Condition | Mode |
|-----------|------|
| 3+ contradictions | DEEP |
| 1+ contradictions | THINKING |
| No docs + "search/find/research" in query | RESEARCH |
| Question words (why/how/explain) | THINKING |
| 2+ complexity markers (and/but/however) | THINKING |
| < 2 docs retrieved | THINKING |
| None of the above | QUICK |

## Thinking Process Visibility

### QUICK Mode
```
User sees:
  answer: "4"
  thinking: None
  
Internal:
  Reasoning trace logged
  Fusion event logged
```

### THINKING Mode
```
User sees:
  answer: "Comprehensive answer..."
  thinking: "<thinking>
    [analysis] ...
    [planning] ...
    [answer_generation] ...
  </thinking>"
  
Internal:
  Reasoning trace with all steps
  Fusion event with context used
```

### DEEP Mode
```
User sees:
  answer: "Multi-paragraph comprehensive answer..."
  thinking: "<deep_reasoning>
    Step 1: decomposition
      ...
    Step 2: deep_contradiction_1
      ...
    ...
  </deep_reasoning>"
  
Internal:
  Detailed reasoning trace
  Fusion event with full context
```

## File Locations

```
personal_agent/
├── rag.py                  # RAG engine
├── reasoning.py            # Reasoning engine
├── lineage.jsonl           # Fusion logs (auto-created)
├── vector_db/              # ChromaDB (auto-created)
└── indices/                # SSE indices (auto-created)
```

## Dependencies

```bash
# Required
pip install chromadb

# SSE already installed
```

## Common Patterns

### Pattern 1: Simple Q&A
```python
rag = RAGEngine()
rag.index_document("faq.txt")
result = rag.query_with_reasoning("What are your hours?")
print(result['answer'])
```

### Pattern 2: Context-Aware Chat
```python
memories = ["User prefers morning", "User is beginner"]
result = rag.query_with_reasoning(
    "When should I exercise?",
    memory_context=memories
)
```

### Pattern 3: Audit Trail
```python
result = rag.query_with_reasoning("Complex question")
fusion_id = result['fusion_id']

# Later: Check what was used
lineage = rag.get_fusion_lineage(fusion_id)
print(f"Used {len(lineage['memories_used'])} memories")
print(f"Retrieved {len(lineage['facts_retrieved'])} facts")
```

### Pattern 4: Performance Analysis
```python
traces = rag.get_reasoning_traces(limit=100)

# Average time by mode
from collections import defaultdict
times = defaultdict(list)

for t in traces:
    times[t['mode']].append(t['total_duration_ms'])

for mode, durations in times.items():
    avg = sum(durations) / len(durations)
    print(f"{mode}: {avg:.0f}ms avg")
```

## Troubleshooting

### ChromaDB not installed
```
Warning: ChromaDB not installed. Install: pip install chromadb
```
Solution: `pip install chromadb`

### No results from vector search
```python
# Check collection exists
print(rag.collections.keys())

# Check collection has docs
if 'main' in rag.collections:
    print(rag.collections['main'].count())
```

### Fusion lineage not found
```python
# Check recent fusions
recent = rag.get_recent_fusions(limit=10)
for f in recent:
    print(f"ID: {f['fusion_id']}")
```

### Reasoning always QUICK mode
```python
# Force different mode for testing
result = rag.query_with_reasoning(query, mode=ReasoningMode.THINKING)
```

## Examples

See full examples in:
- [rag_reasoning_demo.py](rag_reasoning_demo.py) - Comprehensive demos
- [enhanced_agent_demo.py](enhanced_agent_demo.py) - Integration examples
- [RAG_REASONING_README.md](RAG_REASONING_README.md) - Full documentation
