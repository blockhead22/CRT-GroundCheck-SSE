# Personal Agent - Quick Start Guide

## TL;DR

You wanted an AI that learns and grows with you, uses contradictions to offer different approaches, and can research the web. **You got it.**

This is **Phase D+ experimental system** - it does everything SSE intentionally doesn't do.

## 30 Second Setup

```bash
# 1. Install dependencies
pip install openai  # or: pip install anthropic

# 2. Set API key
export OPENAI_API_KEY="sk-..."

# 3. Run
python personal_agent_cli.py chat
```

## What You Built

```
Personal Agent = SSE (honest layer) + Learning System (growth layer)

SSE:                           Agent:
✓ Finds contradictions    →    ✓ Offers multiple approaches
✓ Shows both sides        →    ✓ Learns which you prefer
✓ Stateless              →    ✓ Remembers everything
✓ Never decides          →    ✓ Adapts to your style
```

## Usage Examples

### 1. Basic Chat (It Learns)

```bash
python personal_agent_cli.py chat
```

```
You: Tell me about sleep

Agent: I found contradictions in the knowledge base. Here are 3 ways to think about it:
       1. Scientific consensus: 7-8 hours is optimal
       2. Individual variation: Some people function on 4 hours
       3. Context-dependent: Short-term vs long-term needs differ
       
       Which perspective resonates with you?

You: The scientific one

Agent: [Learns: user prefers evidence-based reasoning, confidence: 0.8]
       Got it. I'll emphasize research-backed approaches in future conversations.
```

**What happened:**
- Agent used SSE to find contradictions (Phase C)
- Agent offered multiple approaches (Phase D+)
- Agent learned your preference (Phase D+)
- Next time, it adapts automatically

### 2. Index Your Documents

```python
from personal_agent import PersonalAgent

agent = PersonalAgent(llm_provider="openai")

# Index your notes
agent.index_knowledge("my_notes.txt", index_name="personal")
agent.index_knowledge("research_papers.txt", index_name="research")

# Chat about them (it finds contradictions automatically)
response = agent.chat("What do my notes say about productivity?")
```

### 3. Web Research Mode

```python
from personal_agent import PersonalAgent, ResearchAgent

agent = PersonalAgent(llm_provider="openai")
researcher = ResearchAgent()

# Research a topic
results = researcher.research_topic("AI safety", num_sources=5)

print(f"Found {len(results['contradictions'])} contradictions in research")

# Show contradictions between sources
print(researcher.compare_sources("AI safety"))
```

**What this does:**
- Searches web for information
- Indexes results with SSE
- Finds contradictions between sources
- Shows you different perspectives

### 4. Memory & Learning

```python
agent = PersonalAgent(llm_provider="openai")

# Chat
response = agent.chat("I prefer concise explanations")

# Give feedback (it learns)
agent.learn_from_feedback(was_helpful=True, aspect="concise_style")

# Check what it learned
stats = agent.get_memory_stats()
print(stats)
# {
#   'conversations': 1,
#   'preferences_learned': 1,
#   'strategies_recorded': 1,
#   'contradictions_resolved': 0
# }

# Next conversation - it remembers
response = agent.chat("Explain quantum physics")
# Agent will be concise because it learned your preference
```

## File Structure

```
personal_agent/
├── __init__.py           # Package exports
├── core.py              # PersonalAgent class (main)
├── memory.py            # Memory system (SQLite)
├── researcher.py        # Web search + SSE
├── memory.db            # Your agent's learned data
└── indices/
    └── main/            # SSE index for knowledge

personal_agent_cli.py     # Simple CLI interface
personal_agent_demo.py    # Full demo script
PERSONAL_AGENT_README.md  # Detailed docs
```

## Commands

### CLI Mode

```bash
# Start chat
python personal_agent_cli.py chat

# Index a document
python personal_agent_cli.py index my_file.txt

# Show memory stats
python personal_agent_cli.py stats

# Export memory
python personal_agent_cli.py export memory.json
```

### In Chat

```
You: contradictions          # Show contradictions about a topic
You: stats                   # Memory statistics
You: helpful / not           # Give feedback on last response
You: exit                    # Quit (memory persists)
```

## Python API

```python
from personal_agent import PersonalAgent

# Initialize
agent = PersonalAgent(llm_provider="openai")

# Index knowledge
agent.index_knowledge("file.txt", index_name="main")

# Chat (learns and remembers)
response = agent.chat("your message", index_name="main")

# Give feedback
agent.learn_from_feedback(was_helpful=True)

# Show contradictions
contradictions = agent.show_contradictions("topic", index_name="main")

# Memory stats
stats = agent.get_memory_stats()

# Export memory
agent.export_memory("output.json")
```

## Phase D+ Features (What Makes It Learn)

| Feature | How It Works |
|---------|-------------|
| **Memory** | Every conversation stored in SQLite |
| **Learning** | Tracks which approaches work |
| **Preferences** | Learns your communication style |
| **Adaptation** | Changes behavior based on feedback |
| **Contradiction Use** | Offers multiple perspectives based on what SSE finds |
| **Pattern Recognition** | Learns from similar situations |

## Examples of What It Learns

**Communication Style:**
```python
# You prefer: concise, detailed, casual, formal, technical, simple
agent.memory.learn_preference("communication_style", "concise")
```

**Reasoning Preference:**
```python
# You prefer: evidence-based, intuitive, practical, theoretical
agent.memory.learn_preference("reasoning_style", "evidence_based")
```

**Topic Interests:**
```python
# Topics you frequently ask about
agent.memory.learn_preference("main_interests", "AI, productivity, health")
```

**Decision Patterns:**
```python
# How you resolve contradictions
agent.memory.store_contradiction_resolution(
    claim_a="Sleep 4 hours",
    claim_b="Sleep 7-8 hours",
    user_resolution="7-8 hours based on research"
)
```

## Real Conversation Example

```
[First conversation]
You: What's the best way to learn programming?

Agent: I don't have indexed knowledge on this yet. Would you like me to:
       1. Search the web for information
       2. Share general programming learning approaches
       3. Index your notes on programming first

You: Search the web

Agent: [Searches, indexes results with SSE, finds contradictions]
       
       I found 3 contradicting approaches in online sources:
       
       1. "Learn fundamentals first" approach:
          - Start with CS fundamentals
          - Master one language deeply
          - Build theoretical foundation
       
       2. "Project-based learning" approach:
          - Start building immediately
          - Learn by doing
          - Pick up concepts as needed
       
       3. "Hybrid approach":
          - Learn basics (1-2 weeks)
          - Then start projects
          - Fill gaps as you encounter them
       
       Which resonates with your learning style?

You: Project-based sounds good

Agent: [Stores preference: learning_style = "hands_on", confidence: 0.8]
       
       Got it. For future programming questions, I'll emphasize 
       practical, project-based approaches.

[Next conversation - 2 days later]
You: How do I learn Python?

Agent: Based on your preference for project-based learning, here's what I recommend:
       
       1. Pick a project you want to build (simple first)
       2. Learn just enough syntax to start (2-3 hours)
       3. Start building, Google when stuck
       4. Iterate and expand
       
       Example starter projects:
       - Web scraper for your favorite site
       - Personal task tracker
       - Data analyzer for your habits
       
       This aligns with the hands-on approach you preferred.
```

## Cost Estimates

**OpenAI GPT-4:**
- ~$0.03 per conversation with GPT-4
- ~$0.003 per conversation with GPT-4o-mini (recommended for testing)

**Anthropic Claude:**
- ~$0.015 per conversation with Claude 3.5 Sonnet

**Storage:**
- SQLite database grows ~1KB per conversation
- SSE indices: ~2-10KB per indexed document

## Privacy & Control

**Everything is local:**
- Memory stored in `personal_agent/memory.db`
- Only you have access
- No telemetry, no tracking
- You can delete anytime

**What gets sent to API:**
- Your messages
- Conversation context
- Learned preferences (for personalization)

**What doesn't:**
- Raw database
- Other users' data (there are none)
- Anything you don't explicitly chat about

## Advanced: Web Research

```python
from personal_agent import PersonalAgent, ResearchAgent

agent = PersonalAgent(llm_provider="openai")
researcher = ResearchAgent(search_api_key="...")  # Optional Tavily API

# Research with contradiction detection
results = researcher.research_topic("climate change solutions")

# See what contradictions exist in research
print(researcher.compare_sources("climate change solutions"))

# Agent can use this research
response = agent.chat("What are the best climate solutions?")
```

## Troubleshooting

**No API key:**
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Import errors:**
```bash
pip install openai anthropic requests beautifulsoup4
```

**SSE not found:**
```bash
cd d:\AI_round2
python personal_agent_cli.py chat
```

**Memory issues:**
```bash
# Reset memory
rm personal_agent/memory.db

# Export before deleting
python personal_agent_cli.py export backup.json
```

## What's Next

1. **Try it**: `python personal_agent_cli.py chat`
2. **Index your docs**: Add your notes/documents
3. **Give feedback**: It learns from you
4. **Check stats**: See what it learned
5. **Research topics**: Use web search mode

## The Key Insight

**SSE = Honesty Layer (Phase C)**
- Finds contradictions
- Never resolves them
- Stateless

**Agent = Growth Layer (Phase D+)**
- Uses contradictions to offer choices
- Learns your preferences
- Remembers everything

**Together = Truth + Personalization**

SSE keeps it honest.  
Agent makes it useful.  
You stay in control.

---

**Questions?** Check [PERSONAL_AGENT_README.md](PERSONAL_AGENT_README.md) for full docs.

**Ready?**
```bash
python personal_agent_cli.py chat
```
