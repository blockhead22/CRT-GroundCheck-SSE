# LLM Integration for Multi-Agent System

**Added:** January 9, 2026  
**Purpose:** Enable agents to use LLMs (API-based or local) for enhanced capabilities

---

## Supported LLM Providers

### 1. **OpenAI (GPT-4, GPT-3.5, etc.)**
**Setup:**
```bash
pip install openai
export OPENAI_API_KEY="sk-..."
```

**Usage:**
```python
from multi_agent.llm_client import LLMClient, LLMProvider

client = LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4",
    temperature=0.3
)

code = client.generate_code("Write a Python function to sort a list")
```

---

### 2. **Anthropic (Claude)**
**Setup:**
```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Usage:**
```python
client = LLMClient(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-sonnet-20240229",
    temperature=0.3
)

analysis = client.analyze_code(code, analysis_type="boundaries")
```

---

### 3. **Ollama (Local Models)**
**Setup:**
```bash
# Install Ollama from ollama.ai
ollama pull codellama:7b
ollama pull mistral:7b
ollama serve
```

**Usage:**
```python
client = LLMClient(
    provider=LLMProvider.OLLAMA,
    model="codellama:7b",
    temperature=0.3
)

response = client.generate("Explain this contradiction...")
```

**Recommended Models:**
- `codellama:7b` - Code generation
- `mistral:7b` - General purpose
- `llama2:13b` - Higher quality (slower)
- `deepseek-coder:6.7b` - Code-focused

---

### 4. **LM Studio (Local Models with UI)**
**Setup:**
1. Download LM Studio from lmstudio.ai
2. Load a model (e.g., CodeLlama, Mistral)
3. Start local server (default port 1234)

**Usage:**
```python
client = LLMClient(
    provider=LLMProvider.LMSTUDIO,
    model="local-model",
    base_url="http://localhost:1234"
)
```

---

## Integration with Agents

### Automatic Pool Creation

```python
from multi_agent.llm_client import LLMPool
from multi_agent.orchestrator import Orchestrator

# Auto-detects available LLMs
pool = LLMPool.create_default_pool()

orchestrator = Orchestrator(llm_pool=pool)
```

**Priority order:**
1. OpenAI (if `OPENAI_API_KEY` set)
2. Anthropic (if `ANTHROPIC_API_KEY` set)
3. Ollama (if running locally)
4. Mock (fallback)

---

### Manual Configuration

```python
from multi_agent.llm_client import LLMClient, LLMProvider, LLMPool

pool = LLMPool()

# Code generation (fast, cheap)
pool.add("code", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-3.5-turbo",
    temperature=0.3
))

# Deep analysis (powerful)
pool.add("analysis", LLMClient(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-opus-20240229",
    temperature=0.2
))

# Documentation (local, free)
pool.add("docs", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="mistral:7b",
    temperature=0.4
))

orchestrator = Orchestrator(llm_pool=pool)
```

---

### Agent-Specific LLMs

```python
from multi_agent.agents import CodeAgent, BoundaryAgent, AnalysisAgent

# Give each agent its own LLM
orchestrator.register_agents({
    "CodeAgent": CodeAgent(
        llm_client=pool.get("code")
    ),
    "BoundaryAgent": BoundaryAgent(
        llm_client=pool.get("analysis")
    ),
    "AnalysisAgent": AnalysisAgent(
        workspace_path=".",
        llm_client=pool.get("analysis")
    )
})
```

---

## What Each Agent Uses LLMs For

### CodeAgent
- **Code generation**: Implement features from descriptions
- **Refactoring**: Improve existing code
- **Bug fixing**: Analyze and fix errors

**Example:**
```python
code_agent = CodeAgent(llm_client=pool.get("code"))
result = code_agent.execute(Task(
    id=1,
    agent_type="CodeAgent",
    description="Implement binary search algorithm"
))
# → Generated Python code with docstrings, type hints
```

---

### BoundaryAgent
- **Semantic analysis**: Detect subtle boundary violations
- **Pattern explanation**: Explain why code violates boundaries
- **False positive reduction**: Distinguish real violations from test code

**Example:**
```python
boundary_agent = BoundaryAgent(llm_client=pool.get("analysis"))
violations = boundary_agent._scan_for_violations("""
def recommend_and_track(user_id, recommendation):
    # This looks innocent but tracks outcomes
    save_recommendation(user_id, recommendation)
    track_user_response(user_id)  # VIOLATION
""")
# → LLM detects: "track_user_response indicates outcome measurement"
```

---

### AnalysisAgent
- **Codebase understanding**: Semantic search beyond keywords
- **Requirement extraction**: Parse complex requirements
- **Implementation planning**: Break down features into steps

**Example:**
```python
analysis_agent = AnalysisAgent(llm_client=pool.get("analysis"))
result = analysis_agent._analyze_request(
    "Build a user authentication system with OAuth2"
)
# → LLM suggests: database schema, OAuth flow, security considerations
```

---

### TestAgent
- **Test generation**: Create comprehensive test cases
- **Edge case detection**: Find scenarios to test
- **Assertion generation**: Write meaningful assertions

---

### DocsAgent
- **API documentation**: Generate from code
- **Examples**: Create usage examples
- **Tutorials**: Write step-by-step guides

---

## Cost & Performance Comparison

### API-Based (OpenAI/Anthropic)

**Pros:**
- Highest quality
- No local setup
- Fast response (GPT-3.5)

**Cons:**
- Costs money ($0.01-$0.06 per request)
- Requires internet
- Privacy concerns (code sent to API)

**Best for:**
- Production deployments
- Complex analysis
- When quality > cost

---

### Local Models (Ollama/LM Studio)

**Pros:**
- Free
- Private (code stays local)
- No internet needed
- Customizable

**Cons:**
- Slower (especially on CPU)
- Lower quality (vs GPT-4)
- Requires disk space (4-13GB per model)

**Best for:**
- Development
- Privacy-sensitive code
- High-volume usage
- Cost optimization

---

## Example: Using Ollama for SSE Development

### Setup
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull recommended models
ollama pull codellama:7b     # Code generation
ollama pull mistral:7b       # General purpose
ollama pull deepseek-coder   # Alternative code model

# Start server
ollama serve
```

### Configure Multi-Agent System
```python
from multi_agent.llm_client import LLMClient, LLMProvider, LLMPool
from multi_agent.orchestrator import Orchestrator
from multi_agent.agents import *

# Create pool with local models
pool = LLMPool()
pool.add("code", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="codellama:7b",
    temperature=0.3
))
pool.add("analysis", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="mistral:7b",
    temperature=0.2
))

# Create orchestrator
orchestrator = Orchestrator(llm_pool=pool)

# Register agents with LLMs
orchestrator.register_agents({
    "CodeAgent": CodeAgent(llm_client=pool.get("code")),
    "BoundaryAgent": BoundaryAgent(llm_client=pool.get("analysis")),
    "AnalysisAgent": AnalysisAgent(llm_client=pool.get("analysis")),
    "TestAgent": TestAgent(),
    "DocsAgent": DocsAgent()
})

# Execute
result = orchestrator.execute("Implement boundary test suite")
```

---

## Hybrid Approach (Best of Both)

```python
pool = LLMPool()

# Use OpenAI for critical tasks (code generation, boundary analysis)
pool.add("code", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4",
    temperature=0.3
))

# Use local for non-critical (docs, simple analysis)
pool.add("docs", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="mistral:7b",
    temperature=0.4
))

# Costs ~$0.02 per feature implementation
# vs ~$0.10 if all OpenAI
# vs $0 if all local (but slower/lower quality)
```

---

## Safety: LLMs + Phase 6 Boundaries

### ⚠️ Important: LLMs Don't Violate Boundaries

**Why it's safe:**
- LLMs **generate code**, they don't execute it
- BoundaryAgent **validates all output** before acceptance
- SSEValidator **detects contradictions** in generated code
- System **blocks violations** before they reach codebase

**Example:**
```python
# LLM generates code
CodeAgent (GPT-4): "
def track_user_success(user_id, outcome):
    db.save_outcome(user_id, outcome)
    update_recommendation_model(outcome)
"

# Boundary validation catches it
BoundaryAgent: "VIOLATION - update_recommendation_model = persistent learning"
SSEValidator: "VIOLATION - track_user_success = outcome measurement"

# Orchestrator blocks
→ Code rejected before reaching codebase
```

**The LLM can try to violate boundaries, but it will always be caught.**

---

## CLI Commands

### Check Available LLMs
```bash
python -c "from multi_agent.llm_client import LLMPool; pool = LLMPool.create_default_pool(); print('Available:', pool.list_clients())"
```

### Test Ollama Connection
```bash
curl http://localhost:11434/api/tags
```

### Test Code Generation
```python
from multi_agent.llm_client import LLMClient, LLMProvider

client = LLMClient(provider=LLMProvider.OLLAMA, model="codellama:7b")
code = client.generate_code("Write a function to reverse a string")
print(code)
```

---

## Troubleshooting

### "Ollama connection failed"
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start it
ollama serve
```

### "No LLMs available"
```bash
# Set API key
export OPENAI_API_KEY="sk-..."

# Or install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral:7b
```

### "LLM responses are slow"
- Use smaller model (`codellama:7b` instead of `13b`)
- Use GPU if available
- Switch to API-based (GPT-3.5 is fast)

### "LLM suggests boundary violations"
- This is **expected and safe**
- BoundaryAgent catches violations
- System learns nothing from rejected code
- No optimization loop created

---

## Files Modified

```
multi_agent/
├── llm_client.py           # NEW: LLM integration layer
├── orchestrator.py         # Updated: LLM pool support
└── agents/
    ├── code_agent.py       # Updated: LLM code generation
    ├── boundary_agent.py   # Updated: LLM semantic analysis
    └── analysis_agent.py   # Updated: LLM reasoning
```

---

## Summary

✅ **Supported**: OpenAI, Anthropic, Ollama, LM Studio  
✅ **Automatic detection**: Uses best available LLM  
✅ **Agent-specific**: Each agent can have different LLM  
✅ **Safe**: All output validated by BoundaryAgent  
✅ **Cost-optimized**: Hybrid approach (API + local)  
✅ **Privacy-safe**: Local models keep code private

**Recommended setup for SSE development:**
```python
# Use Ollama for free local development
ollama pull codellama:7b
python multi_agent_demo.py --demo 1
```

**Recommended for production:**
```python
# Use OpenAI GPT-4 for highest quality
export OPENAI_API_KEY="sk-..."
orchestrator = Orchestrator(llm_pool=LLMPool.create_default_pool())
```
