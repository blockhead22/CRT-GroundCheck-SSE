# LLM Setup Guide for Multi-Agent System

## Quick Start

The multi-agent system supports **4 LLM providers**:
1. **OpenAI** (GPT-4, GPT-3.5) - Best quality, paid
2. **Anthropic** (Claude) - Great quality, paid  
3. **Ollama** - Free local models, good quality
4. **LM Studio** - Free local models, GUI

**Auto-Detection**: The system automatically finds available LLMs in this priority order:
```
OpenAI → Anthropic → Ollama → Mock
```

## Option 1: OpenAI (Easiest, Paid)

### Setup
```powershell
# Install package
pip install openai

# Set API key
$env:OPENAI_API_KEY = "sk-your-api-key-here"
```

### Models
- **gpt-4**: Highest quality ($0.03/1K tokens)
- **gpt-3.5-turbo**: Fast & cheap ($0.001/1K tokens)

### Cost Estimate
- BoundaryAgent semantic analysis: ~500 tokens = $0.015 (GPT-4)
- CodeAgent code generation: ~1000 tokens = $0.03 (GPT-4)
- AnalysisAgent reasoning: ~800 tokens = $0.024 (GPT-4)

**Daily usage (10 requests):** ~$0.70 with GPT-4, ~$0.02 with GPT-3.5

## Option 2: Ollama (Free, Local)

### Setup
```powershell
# 1. Download Ollama
# Go to: https://ollama.com/download
# Install for Windows

# 2. Pull models
ollama pull codellama:7b      # Code generation (3.8GB)
ollama pull mistral:7b        # General reasoning (4.1GB)

# 3. Verify running
ollama list
```

### Recommended Models
- **codellama:7b** - Best for code generation (CodeAgent)
- **mistral:7b** - Best for analysis (AnalysisAgent, BoundaryAgent)
- **llama2:7b** - Backup option

### Performance
- **Speed**: 2-5 seconds per request (local GPU)
- **Quality**: 80-90% of GPT-3.5
- **Cost**: Free

## Option 3: Anthropic Claude (Paid)

### Setup
```powershell
# Install package
pip install anthropic

# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"
```

### Models
- **claude-3-opus**: Highest quality
- **claude-3-sonnet**: Balanced
- **claude-3-haiku**: Fast & cheap

## Option 4: LM Studio (Free, Local, GUI)

### Setup
```powershell
# 1. Download LM Studio
# Go to: https://lmstudio.ai
# Install for Windows

# 2. Download models via GUI
# Recommended: TheBloke/CodeLlama-7B-GGUF

# 3. Start local server
# In LM Studio: Click "Local Server" → Start
```

Default endpoint: `http://localhost:1234/v1`

## Usage Examples

### Example 1: Auto-Detection (Easiest)
```python
from multi_agent.orchestrator import Orchestrator

# Auto-detects available LLMs
orchestrator = Orchestrator(workspace_path=".")

# Uses best available LLM for each agent
orchestrator.execute("implement feature")
```

### Example 2: Specific Provider
```python
from multi_agent.llm_client import LLMClient, LLMProvider, LLMPool

# Create OpenAI client
pool = LLMPool()
pool.add("gpt4", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4"
))

# Pass to orchestrator
orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
```

### Example 3: Hybrid Approach (Best Value)
```python
# Use OpenAI GPT-4 for critical code generation
# Use Ollama for non-critical analysis
pool = LLMPool()

# High-quality API for code
pool.add("code", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY")
))

# Free local for analysis
pool.add("analysis", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="mistral:7b"
))

# Assign to agents
orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
orchestrator.register_agents({
    "CodeAgent": CodeAgent(llm_client=pool.get("code")),        # Uses GPT-4
    "AnalysisAgent": AnalysisAgent(llm_client=pool.get("analysis"))  # Uses Ollama
})
```

### Example 4: Agent-Specific Models
```python
pool = LLMPool()

# Code generation: Use specialized model
pool.add("codegen", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="codellama:7b"
))

# Semantic analysis: Use reasoning model
pool.add("reasoning", LLMClient(
    provider=LLMProvider.OLLAMA,
    model="mistral:7b"
))

# Assign
orchestrator.register_agents({
    "CodeAgent": CodeAgent(llm_client=pool.get("codegen")),
    "BoundaryAgent": BoundaryAgent(llm_client=pool.get("reasoning")),
    "AnalysisAgent": AnalysisAgent(llm_client=pool.get("reasoning"))
})
```

## What Each Agent Uses LLMs For

### CodeAgent
- **Purpose**: Generate implementation code
- **LLM Input**: Feature description + boundaries + context
- **LLM Output**: Complete Python code
- **Recommended Model**: codellama:7b (Ollama) or gpt-4 (OpenAI)

### BoundaryAgent  
- **Purpose**: Semantic analysis of code for boundary violations
- **LLM Input**: Code + boundary rules
- **LLM Output**: Violation analysis
- **Recommended Model**: mistral:7b (Ollama) or gpt-3.5-turbo (OpenAI)

### AnalysisAgent
- **Purpose**: Technical analysis & implementation planning
- **LLM Input**: User request + codebase context
- **LLM Output**: Implementation approach
- **Recommended Model**: mistral:7b (Ollama) or gpt-3.5-turbo (OpenAI)

### TestAgent & DocsAgent
- **Current**: Template-based (no LLM yet)
- **Future**: Could use LLMs for test generation & doc writing

## Running the Demo

### With Auto-Detection
```powershell
# No setup needed - uses mock LLMs
python multi_agent_demo.py
```

### With OpenAI
```powershell
# Set API key
$env:OPENAI_API_KEY = "sk-your-key"

# Run demo
python multi_agent_demo.py
```

### With Ollama
```powershell
# Start Ollama (separate terminal)
ollama serve

# Pull model
ollama pull codellama:7b

# Run demo
python multi_agent_demo.py
```

## Cost Comparison

| Provider | Setup | Monthly Cost (100 requests) | Quality | Speed |
|----------|-------|----------------------------|---------|-------|
| **Ollama** | 10 min | $0 | ⭐⭐⭐⭐ | 3s |
| **OpenAI GPT-3.5** | 2 min | $2 | ⭐⭐⭐⭐⭐ | 1s |
| **OpenAI GPT-4** | 2 min | $70 | ⭐⭐⭐⭐⭐ | 2s |
| **Anthropic Claude** | 2 min | $50 | ⭐⭐⭐⭐⭐ | 2s |

**Recommendation for Development**: Ollama (free, good quality)  
**Recommendation for Production**: OpenAI GPT-3.5 (best value)

## Troubleshooting

### "No LLMs available - using mock"
- **Cause**: No API keys set, Ollama not running
- **Fix**: Set `OPENAI_API_KEY` or install Ollama

### "Connection refused to localhost:11434"
- **Cause**: Ollama not running
- **Fix**: Run `ollama serve` in separate terminal

### "Invalid API key"
- **Cause**: Wrong API key format
- **Fix**: Check key starts with `sk-` for OpenAI, `sk-ant-` for Anthropic

### Slow performance with Ollama
- **Cause**: CPU-only mode (no GPU)
- **Fix**: Install CUDA/ROCm for GPU acceleration, or use smaller models (mistral:7b instead of llama2:13b)

### High costs with OpenAI
- **Cause**: Using GPT-4 for everything
- **Fix**: Use hybrid approach (GPT-4 for CodeAgent, GPT-3.5 for analysis)

## Safety Analysis

**Q: Can LLMs violate Phase 6 boundaries?**  
**A: No** - BoundaryAgent validates ALL code (LLM-generated or template) before acceptance.

**Process**:
1. CodeAgent asks LLM to generate code
2. LLM returns code (might violate boundaries)
3. BoundaryAgent scans code for violations
4. If violations found → rejected
5. If clean → accepted

**Example**:
```python
# LLM generates this (violation!)
def track_success_rate():
    return outcome_measurement.success_rate

# BoundaryAgent detects "outcome_measurement" → REJECTED
# CodeAgent falls back to safe template
```

**Guarantee**: LLM output is **untrusted** until validated by BoundaryAgent.

## Recommended Setups

### Beginner Setup
```python
# Just works - no configuration
orchestrator = Orchestrator(workspace_path=".")
orchestrator.execute("implement feature")
```

### Developer Setup (Free)
```powershell
# Install Ollama
ollama pull codellama:7b

# Auto-detected
python multi_agent_demo.py
```

### Production Setup (Best Quality)
```python
pool = LLMPool()
pool.add("code", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4"  # Best code generation
))

orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
```

### Budget Setup (Best Value)
```python
pool = LLMPool()
pool.add("default", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-3.5-turbo"  # 30x cheaper than GPT-4
))

orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
```

## Next Steps

1. **Choose provider** (Ollama recommended for development)
2. **Set up credentials** (API key or local model)
3. **Run demo** (`python multi_agent_demo.py`)
4. **Verify LLM usage** (check "Available LLMs" in output)
5. **Implement features** using orchestrator

See [LLM_INTEGRATION.md](LLM_INTEGRATION.md) for advanced usage.
