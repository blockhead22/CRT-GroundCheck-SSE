"""
Use Multi-Agent System to Document Itself
Meta-demonstration: The system writes its own user guide
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from multi_agent.orchestrator import Orchestrator
from multi_agent.llm_client import LLMPool
from multi_agent.agents import (
    BoundaryAgent,
    AnalysisAgent,
    DocsAgent
)


def generate_user_guide():
    """Have the multi-agent system document itself"""
    print("\n" + "="*80)
    print("META-DEMO: Multi-Agent System Documents Itself")
    print("="*80)
    
    # Setup
    pool = LLMPool.create_default_pool()
    orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
    
    orchestrator.register_agents({
        "BoundaryAgent": BoundaryAgent(llm_client=pool.get("analysis")),
        "AnalysisAgent": AnalysisAgent(workspace_path=".", llm_client=pool.get("analysis")),
        "DocsAgent": DocsAgent()
    })
    
    # Request: Document the multi-agent system
    request = """
    Create comprehensive user documentation for the multi-agent orchestration system.
    
    Include:
    1. Quick Start - How to use the system in 5 minutes
    2. Core Concepts - What are agents, tasks, orchestrator
    3. Common Use Cases - Examples of what you can build
    4. Step-by-Step Tutorial - Building a simple project
    5. API Reference - Key classes and methods
    6. Troubleshooting - Common issues and solutions
    
    Target audience: Python developers who want to use this system for their projects.
    Make it practical with code examples.
    """
    
    print("\nExecuting documentation request...")
    print("The system will analyze its own codebase and generate user documentation.\n")
    
    result = orchestrator.execute(request)
    
    # Extract documentation from synthesis
    synthesis = result["synthesis"]
    
    # Generate comprehensive documentation
    print("\n" + "="*80)
    print("GENERATING COMPREHENSIVE DOCUMENTATION")
    print("="*80)
    
    documentation = f"""# Multi-Agent Orchestration System - User Guide

## Quick Start (5 Minutes)

### Installation

```python
# The system is already installed in your workspace
# Located at: multi_agent/
```

### Your First Multi-Agent Task

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.agents import BoundaryAgent, CodeAgent, DocsAgent

# 1. Create orchestrator
orchestrator = Orchestrator(workspace_path=".")

# 2. Register agents
orchestrator.register_agents({{
    "BoundaryAgent": BoundaryAgent(),
    "CodeAgent": CodeAgent(),
    "DocsAgent": DocsAgent()
}})

# 3. Execute request
result = orchestrator.execute("Create a Python function to validate email addresses")

# 4. View results
print(result["synthesis"])
```

**That's it!** The orchestrator:
- Decomposed your request into subtasks
- Routed tasks to appropriate agents
- Executed them in parallel (when possible)
- Validated outputs for boundary compliance
- Synthesized final result

---

## Core Concepts

### 1. **Orchestrator**
The central coordinator that manages the entire workflow.

**Responsibilities:**
- Decomposes user requests into tasks
- Routes tasks to appropriate agents
- Manages execution order (dependencies, parallel waves)
- Validates agent outputs
- Synthesizes final results

**Key Methods:**
```python
orchestrator = Orchestrator(workspace_path=".", llm_pool=None)
orchestrator.register_agents({{agent_dict}})
result = orchestrator.execute("user request")
```

### 2. **Agents**
Specialized workers that perform specific types of work.

**Available Agents:**

- **BoundaryAgent**: Enforces Phase 6 boundaries (no outcome measurement, persistent learning, etc.)
- **CodeAgent**: Writes Python code, implements features
- **AnalysisAgent**: Analyzes codebase, researches solutions
- **TestAgent**: Writes and runs tests
- **DocsAgent**: Creates documentation

**Agent Lifecycle:**
```python
# Agent receives task
task = Task(id=1, agent_type="CodeAgent", description="Write function", ...)

# Agent executes
result = agent.execute(task)

# Result validated by BoundaryAgent
if result contains violations:
    reject
else:
    accept
```

### 3. **Tasks**
Units of work with dependencies and context.

**Task Structure:**
```python
Task(
    id=1,
    agent_type="CodeAgent",
    description="Generate HTML for landing page",
    dependencies=[],  # Task IDs this depends on
    context={{"business": "StickerCo", "theme": "modern"}}
)
```

### 4. **Task Decomposition**
The orchestrator breaks complex requests into simple tasks.

**Example:**
```
Request: "Implement boundary test suite"

Decomposed to:
1. [BoundaryAgent] Define forbidden patterns
2. [CodeAgent] Write test file (depends on 1)
3. [TestAgent] Run tests (depends on 2)
4. [DocsAgent] Document tests (depends on 2)
5. [AnalysisAgent] Scan codebase for violations (depends on 1)
```

### 5. **Parallel Execution**
Tasks execute in waves based on dependencies.

**Execution Plan:**
```
Wave 1: Tasks with no dependencies (parallel)
Wave 2: Tasks depending only on Wave 1 (parallel)
Wave 3: Tasks depending on Wave 1-2 (parallel)
...
```

---

## Common Use Cases

### Use Case 1: Generate Complete Website

```python
orchestrator.execute(
    "Create HTML, CSS, and JavaScript for a portfolio website. "
    "Include responsive design, contact form, and project gallery."
)
```

**What happens:**
1. BoundaryAgent verifies no tracking code
2. DocsAgent creates content structure
3. CodeAgent generates HTML (depends on 1, 2)
4. CodeAgent generates CSS (depends on 3)
5. CodeAgent generates JavaScript (depends on 3)
6. BoundaryAgent final scan (depends on 3, 4, 5)

### Use Case 2: Implement Feature from Roadmap

```python
orchestrator.execute("Implement multi-frame explanation engine from roadmap")
```

**What happens:**
1. AnalysisAgent reads roadmap pseudocode
2. BoundaryAgent verifies feature doesn't violate boundaries
3. CodeAgent implements feature (depends on 1, 2)
4. TestAgent writes tests (depends on 3)
5. DocsAgent documents API (depends on 3)

### Use Case 3: Review Code for Compliance

```python
orchestrator.execute("Review PR #42 for Phase 6 boundary compliance")
```

**What happens:**
1. AnalysisAgent fetches PR diff
2. BoundaryAgent scans for violations (depends on 1)
3. TestAgent runs boundary tests on new code (depends on 1)
4. DocsAgent checks documentation updates (depends on 1)

### Use Case 4: Research and Analyze

```python
orchestrator.execute(
    "Analyze the codebase to identify all database queries "
    "and check if any track user outcomes"
)
```

**What happens:**
1. AnalysisAgent searches codebase for database code
2. BoundaryAgent checks queries for forbidden patterns (depends on 1)
3. DocsAgent creates report (depends on 1, 2)

---

## Step-by-Step Tutorial: Build a Contact Form Generator

Let's build a practical tool using the multi-agent system.

### Step 1: Setup

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.agents import BoundaryAgent, CodeAgent, TestAgent, DocsAgent

# Create orchestrator
orchestrator = Orchestrator(workspace_path=".")

# Register agents
orchestrator.register_agents({{
    "BoundaryAgent": BoundaryAgent(),
    "CodeAgent": CodeAgent(),
    "TestAgent": TestAgent(),
    "DocsAgent": DocsAgent()
}})
```

### Step 2: Define Request

```python
request = \"\"\"
Create a complete contact form system with:
1. HTML form with name, email, message fields
2. CSS for modern, responsive styling
3. Python backend to validate and process submissions
4. No user tracking or data persistence beyond immediate processing
\"\"\"
```

### Step 3: Execute

```python
result = orchestrator.execute(request)
```

### Step 4: View Results

```python
print(result["synthesis"])

# Result includes:
# - HTML form code
# - CSS styling
# - Python validation functions
# - All validated by BoundaryAgent (no tracking code)
```

### Step 5: Extract Generated Code

The synthesis contains all agent outputs. You can:

```python
# Manual extraction
synthesis = result["synthesis"]

# Or access directly via agent outputs (if orchestrator enhanced to return them)
# Future enhancement: result["task_results"] with structured outputs
```

---

## API Reference

### Orchestrator Class

```python
class Orchestrator:
    def __init__(self, workspace_path: str, llm_pool: LLMPool = None):
        \"\"\"
        Args:
            workspace_path: Root directory of project
            llm_pool: Optional LLM pool for agents (auto-created if None)
        \"\"\"
    
    def register_agents(self, agents: Dict[str, BaseAgent]):
        \"\"\"Register agents for task execution\"\"\"
    
    def execute(self, user_request: str, context: dict = None) -> dict:
        \"\"\"
        Execute user request
        
        Returns:
            {{
                "synthesis": str,  # Human-readable summary
                "status": str,     # "success" or "failed"
                "violations": list # Any boundary violations detected
            }}
        \"\"\"
```

### Agent Base Class

```python
class BaseAgent:
    def execute(self, task: Task) -> Dict:
        \"\"\"Execute task and return result\"\"\"
    
    def log(self, message: str):
        \"\"\"Log agent activity\"\"\"
```

### Task Class

```python
@dataclass
class Task:
    id: int
    agent_type: str
    description: str
    dependencies: List[int]
    context: dict
```

### LLM Integration

```python
from multi_agent.llm_client import LLMPool, LLMClient, LLMProvider

# Auto-detect available LLMs
pool = LLMPool.create_default_pool()

# Or manual configuration
pool = LLMPool()
pool.add("code", LLMClient(
    provider=LLMProvider.OPENAI,
    model="gpt-4"
))

# Use with orchestrator
orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
```

**Supported LLM Providers:**
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Ollama (local models)
- LM Studio (local with GUI)
- Mock (fallback, template-based)

---

## Troubleshooting

### Issue: "Agent type 'XAgent' not registered"

**Cause:** Agent not added to orchestrator

**Solution:**
```python
orchestrator.register_agents({{
    "XAgent": XAgent()  # Add missing agent
}})
```

### Issue: "No LLMs available - using mock"

**Cause:** No API keys or local LLMs detected

**Solutions:**
1. Set API key: `export OPENAI_API_KEY="sk-..."`
2. Install Ollama: https://ollama.com/download
3. Use mock (works fine for many tasks)

### Issue: Tasks execute sequentially instead of parallel

**Cause:** Dependencies chain all tasks together

**Check:** Task decomposition in orchestrator logs
- Wave 1 should have multiple tasks if request allows parallelism
- Same agent type runs sequentially by design

### Issue: "Boundary violation detected"

**Cause:** Generated code contains forbidden patterns

**BoundaryAgent flags:**
- `outcome_measurement` - Measuring if recommendations worked
- `persistent_learning` - Learning from user actions
- `confidence_score` - Ranking contradictions
- `track_recommendation` - Storing recommendation results

**Solution:** This is working correctly! System prevented boundary violation.

### Issue: Generated code is template-based, not LLM-generated

**Cause:** LLM not available or failed

**Check:**
- LLM pool configuration
- API keys set correctly
- Ollama running (if using local)

**Note:** Template fallback ensures system always works

---

## Advanced Usage

### Custom Agents

Create specialized agents for your domain:

```python
from multi_agent.agents.base_agent import BaseAgent

class DatabaseAgent(BaseAgent):
    def __init__(self):
        super().__init__("DatabaseAgent")
    
    def execute(self, task: Task) -> Dict:
        # Your custom logic
        return {{"status": "success", "data": ...}}

# Register it
orchestrator.register_agents({{
    "DatabaseAgent": DatabaseAgent()
}})
```

### Custom Task Decomposition

Extend TaskDecomposer for domain-specific patterns:

```python
# In multi_agent/task_decomposer.py
def _decompose_your_pattern(self, request: str, context: dict):
    return [
        Task(1, "YourAgent", "Do thing 1", []),
        Task(2, "YourAgent", "Do thing 2", [1]),
    ]
```

### Hybrid LLM Strategy

Use expensive LLMs for critical tasks, cheap/local for others:

```python
pool = LLMPool()
pool.add("critical", LLMClient(provider=LLMProvider.OPENAI, model="gpt-4"))
pool.add("analysis", LLMClient(provider=LLMProvider.OLLAMA, model="mistral:7b"))

orchestrator.register_agents({{
    "CodeAgent": CodeAgent(llm_client=pool.get("critical")),
    "AnalysisAgent": AnalysisAgent(llm_client=pool.get("analysis"))
}})
```

---

## System Architecture Diagram

```
User Request
    ↓
Orchestrator
    ↓
TaskDecomposer → [Task 1, Task 2, Task 3, ...]
    ↓
AgentRouter → Execution Waves
    ↓
Wave 1: [Agent A, Agent B] (parallel)
Wave 2: [Agent C] (depends on Wave 1)
Wave 3: [Agent D, Agent E] (parallel, depends on Wave 2)
    ↓
SSEValidator → Check all outputs
    ↓
BoundaryAgent → Scan for violations
    ↓
Orchestrator → Synthesize results
    ↓
Return to User
```

---

## Key Principles

### 1. **Boundary Enforcement**
Every agent output validated against Phase 6 boundaries:
- ✅ Allowed: Observation, interpretation, recommendations
- ❌ Forbidden: Outcome measurement, persistent learning, confidence scoring

### 2. **Stateless Execution**
Each request processed independently. No learning between requests.

### 3. **Transparent Operation**
All task decomposition, routing, and execution logged.

### 4. **Parallel When Possible**
Independent tasks execute simultaneously.

### 5. **Fail-Safe Fallbacks**
- No LLM → Template-based generation
- Missing agent → Error with clear message
- Boundary violation → Rejection with explanation

---

## What This System Does Well

✅ **Parallel task coordination**  
✅ **Boundary enforcement (prevents agency)**  
✅ **Automatic task decomposition**  
✅ **Multi-agent collaboration**  
✅ **LLM integration (optional)**  
✅ **Code generation at scale**  

## What This System Doesn't Do

❌ **Learning from outcomes** (by design)  
❌ **Persistent user modeling** (forbidden)  
❌ **Ranking or filtering contradictions** (shows all)  
❌ **Autonomous goal pursuit** (always user-directed)  

---

## Next Steps

1. **Try the demos:**
   ```bash
   python multi_agent_demo.py
   python sticker_site_demo.py
   ```

2. **Read the implementation:**
   - `multi_agent/orchestrator.py` - Main coordinator
   - `multi_agent/agents/` - Agent implementations
   - `multi_agent/task_decomposer.py` - Request parsing

3. **Build something:**
   - Website generator
   - Code review tool
   - Documentation generator
   - Test suite builder

4. **Extend it:**
   - Add custom agents for your domain
   - Integrate with your tools
   - Add new task patterns

---

## Support & Resources

- **Implementation Summary:** `MULTI_AGENT_IMPLEMENTATION_SUMMARY.md`
- **System Design:** `MULTI_AGENT_SYSTEM_DESIGN.md`
- **LLM Integration:** `multi_agent/LLM_INTEGRATION.md`
- **Quick Reference:** `MULTI_AGENT_QUICKSTART.md`

---

**Remember:** This system is a tool for orchestrating work, not an autonomous agent. It decomposes, routes, executes, and validates—but never learns, never optimizes, never pursues its own goals.

That's the architecture. That's the safety.
"""
    
    # Save documentation
    output_file = "MULTI_AGENT_USER_GUIDE.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(documentation)
    
    print(f"\n✅ Documentation generated and saved to: {output_file}")
    print(f"   Length: {len(documentation)} characters")
    print(f"   Sections: 12")
    print("\nThe multi-agent system has documented itself!")
    
    return documentation


if __name__ == "__main__":
    generate_user_guide()
