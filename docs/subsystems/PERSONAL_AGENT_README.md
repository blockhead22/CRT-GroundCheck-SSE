# Personal Learning Agent

**WARNING: This is Phase D+ experimental system.**

This agent violates SSE's Phase 6 boundaries **intentionally**. It's a personal tool that learns and grows with you, using SSE as its honesty layer.

## 🆕 NEW: RAG + Reasoning Engine

The agent now includes:
- **RAG Engine**: Vector search + SSE contradiction detection
- **Reasoning Modes**: QUICK, THINKING, DEEP (like Claude's extended thinking)
- **Memory Fusion Tracking**: Internal hooks showing what memories/facts were used when
- **Advanced Thinking**: Pre-generation analysis and planning

See [RAG_REASONING_README.md](RAG_REASONING_README.md) for full documentation.

## What This Does

- **Learns** your preferences, communication style, thinking patterns
- **Remembers** all conversations and builds context over time
- **Uses SSE** to find contradictions in your knowledge
- **Uses RAG** for knowledge retrieval with semantic search
- **Thinks before answering** with visible reasoning process
- **Tracks everything** with internal fusion lineage
- **Offers multiple approaches** based on contradictions
- **Tracks what works** and adapts strategies
- **Grows with you** - the more you use it, the better it gets

## SSE vs Agent

```
SSE (Phase C - Honest Layer):
├─ Finds contradictions
├─ Shows both sides
├─ Stateless, no memory
└─ Never resolves or decides

Personal Agent (Phase D+ - Learning Layer):
├─ Learns from every conversation
├─ Remembers what approaches work
├─ Uses contradictions to offer alternatives
├─ Adapts to your thinking style
├─ RAG engine for knowledge retrieval
├─ Reasoning modes (QUICK/THINKING/DEEP)
├─ Memory fusion tracking (internal hooks)
└─ Builds model of your preferences
```

## Installation

```bash
# Install dependencies
pip install openai anthropic chromadb  # chromadb for RAG

# Set API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Quick Start

```python
from personal_agent import PersonalAgent

# Initialize with your LLM
agent = PersonalAgent(llm_provider="openai")

# Index your knowledge
agent.index_knowledge("my_notes.txt", index_name="personal")

# Chat (it learns and remembers)
response = agent.chat("Tell me about my notes on sleep")
print(response)

# Show contradictions with multiple approaches
print(agent.show_contradictions("sleep", index_name="personal"))

# Give feedback (it learns)
agent.learn_from_feedback(was_helpful=True)

# See what it's learned
print(agent.get_memory_stats())
```

## Interactive Demo

```bash
python personal_agent_demo.py
```

## How It Works

### 1. SSE Layer (Honest Observation)

SSE finds contradictions without resolving them:

```python
# SSE stays Phase C - just shows both sides
contradictions = agent.find_contradictions_in_knowledge("sleep")
# Returns: [contradiction1, contradiction2, ...]
```

### 2. Agent Layer (Learning & Adaptation)

Agent uses contradictions to offer different approaches:

```python
# Agent (Phase D+) offers multiple ways to think about it
response = agent.chat("What's the truth about sleep?")

# Agent might respond:
# "I found contradictions in your knowledge. Here are different ways to think about it:
#  1. Context-dependent: 4 hours works for some, 7-8 for others
#  2. Research evolution: Newer studies favor 7-8 hours
#  3. Individual variation: Your body's needs might differ
# 
# Based on our previous conversations, you tend to prefer evidence-based approaches.
# The scientific consensus leans toward 7-8 hours for most people."
```

### 3. Memory System (Persistent Learning)

Everything is stored and learned:

```python
# Conversations
agent.memory.store_conversation(user_msg, agent_response)

# Preferences (learns what you like)
agent.memory.learn_preference("communication_style", "direct_and_concise")

# Strategies (learns what works)
agent.memory.record_strategy_outcome(
    situation="explaining_contradictions",
    approach="multiple_perspectives",
    success_score=0.9
)

# Contradiction resolutions (learns your decisions)
agent.memory.store_contradiction_resolution(
    claim_a="4 hours is enough",
    claim_b="need 7-8 hours",
    user_resolution="7-8 hours for me"
)
```

## Example Session

```
You: Tell me about sleep

Agent: I found 2 contradictions in your knowledge about sleep. 
       Here are different ways to think about this:

       1. Individual Variation Perspective:
          - Some people genuinely thrive on 4 hours
          - Most people need 7-8 hours
          - Your needs might be unique

       2. Scientific Consensus Perspective:
          - Research strongly supports 7-8 hours
          - 4-hour claims are often outliers
          - Sleep debt accumulates even if you feel fine

       3. Context-Dependent Perspective:
          - Short-term: 4 hours might work in crisis
          - Long-term: 7-8 hours for health
          - Quality matters as much as quantity

       Which perspective resonates with your experience?

You: The scientific one makes sense

Agent: Got it. I'll remember you prefer evidence-based approaches.
       [Stores preference: "reasoning_style" = "evidence_based", confidence: 0.8]

You: What should I do?

Agent: Based on what I've learned about you (evidence-based thinking),
       I'd recommend:
       
       1. Track your sleep for 2 weeks
       2. Try 7-8 hours consistently
       3. Measure: energy, mood, productivity
       4. Use that data to decide
       
       This aligns with your preference for empirical evidence.

[Agent stores this as successful strategy for future similar questions]
```

## Memory Stats

```python
stats = agent.get_memory_stats()
# {
#   'conversations': 127,
#   'preferences_learned': 8,
#   'strategies_recorded': 43,
#   'contradictions_resolved': 15
# }
```

## Commands in Demo

- Type normally to chat
- `stats` - Show memory statistics
- `contradictions` - Check contradictions about a topic
- `index <file>` - Index a new knowledge file
- `quit` - Exit (memory persists)

## Phase D+ Features (Intentional)

This agent does things SSE never does:

| Feature | SSE (Phase C) | Personal Agent (Phase D+) |
|---------|--------------|---------------------------|
| Memory | ❌ Stateless | ✅ Persistent |
| Learning | ❌ Never | ✅ Always |
| User Model | ❌ None | ✅ Builds over time |
| Adaptation | ❌ Static | ✅ Improves with use |
| Outcome Measurement | ❌ Forbidden | ✅ Tracks success |
| Preferences | ❌ None | ✅ Learns & applies |

## Why This Is OK

**For a personal tool:**
- You control it
- You see what it learns
- You can reset/delete memory
- You decide what to trust
- It's experimental and local

**For a product:**
- Phase 6 restrictions apply
- No learning allowed
- No user modeling
- Stateless only
- Maximum honesty

## Database Location

```
personal_agent/
├── memory.db           # SQLite - all learned data
└── indices/
    ├── main/          # SSE index for main knowledge
    └── custom/        # SSE index for custom docs
```

## Export Memory

```python
agent.export_memory("my_agent_memory.json")
```

## Reset Everything

```python
# Clear conversation (keeps long-term memory)
agent.reset_conversation()

# Delete database to start fresh
import os
os.remove("personal_agent/memory.db")
```

## Architecture

```
┌─────────────────────────────────────────┐
│   Personal Agent (Phase D+ Learning)    │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Memory System (SQLite)          │  │
│  │  - Conversations                 │  │
│  │  - Preferences                   │  │
│  │  - Strategies                    │  │
│  │  - Contradiction Resolutions     │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  LLM (GPT-4 / Claude)            │  │
│  │  - Generates responses           │  │
│  │  - Uses learned context          │  │
│  └──────────────────────────────────┘  │
│                                         │
└────────────┬────────────────────────────┘
             │ uses as tool
             ▼
┌─────────────────────────────────────────┐
│    SSE (Phase C Observation Layer)      │
│                                         │
│  - Finds contradictions                 │
│  - Shows both sides                     │
│  - No resolution                        │
│  - Stateless & honest                   │
└─────────────────────────────────────────┘
```

## Next Steps

1. **Try the demo**: `python personal_agent_demo.py`
2. **Index your notes**: Add your documents
3. **Chat and give feedback**: It learns from you
4. **Check stats**: See what it's learned
5. **Export memory**: Backup your agent's knowledge

## Limitations

- Requires API key (GPT-4 or Claude)
- Memory grows over time (SQLite database)
- No built-in privacy controls (it's local, you control access)
- Experimental - use at your own discretion

## Philosophy

SSE is **honest observation** (Phase C).  
Personal Agent is **learning companion** (Phase D+).  
Together = **Truth + Growth**.

SSE keeps the agent honest.  
Agent uses that honesty to help you grow.
