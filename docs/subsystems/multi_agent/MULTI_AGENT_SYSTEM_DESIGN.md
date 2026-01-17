# Multi-Agent Orchestration System
## Designed for SSE Development + General-Purpose Use

**Date:** January 9, 2026  
**Purpose:** Build a multi-agent system to accelerate SSE development while enforcing Phase 6 boundaries  
**Key Innovation:** Use SSE's contradiction detection to validate agent outputs against architectural constraints

---

## Core Architecture

```
User Request
    ↓
Orchestrator (main_agent.py)
    ├─ Task Decomposition Engine
    ├─ Agent Registry & Routing
    ├─ SSE Validation Layer ← USES SSE CONTRADICTION DETECTION
    └─ Result Synthesis
         ↓
Specialized Agents (parallel execution where possible)
    ├─ CodeAgent (writes implementation)
    ├─ TestAgent (writes tests, runs validation)
    ├─ BoundaryAgent (checks Phase 6 compliance)
    ├─ DocsAgent (updates documentation)
    └─ AnalysisAgent (semantic search, code review)
         ↓
Validation Pipeline (SSE-powered)
    ├─ Contradiction Detection (agent outputs vs Phase 6)
    ├─ Consistency Checking (code vs docs vs tests)
    └─ Boundary Violation Detection
         ↓
Final Output (synthesized, validated)
```

---

## Agent Types & Responsibilities

### 1. **Orchestrator** (`orchestrator.py`)
**Role:** Main coordinator, task decomposition, result synthesis

**Capabilities:**
- Parse complex user requests into subtasks
- Route subtasks to appropriate agents
- Run agents in parallel when independent
- Synthesize results into coherent output
- Validate using SSE contradiction detection

**Tools:**
- Task decomposition (LLM-powered)
- Agent registry
- SSE validation client
- Result merger

**Example:**
```
User: "Implement Week 1 boundary tests"

Orchestrator breaks down:
Task 1 → CodeAgent: "Write test_outcome_measurement_forbidden.py"
Task 2 → BoundaryAgent: "Define what counts as outcome measurement"
Task 3 → DocsAgent: "Update test documentation"
Task 4 → SSE: "Check if new tests contradict Phase 6 charter"

Runs 1-3 in parallel → validates with SSE → synthesizes result
```

---

### 2. **CodeAgent** (`agents/code_agent.py`)
**Role:** Writes production code, implements features

**Capabilities:**
- Read existing codebase for context
- Generate new modules/functions
- Refactor existing code
- Follow coding standards
- Never add forbidden patterns (validated by BoundaryAgent)

**Tools:**
- `read_file`, `create_file`, `replace_string_in_file`
- `grep_search`, `semantic_search`
- `get_errors` (check for syntax errors)

**Constraints:**
- All code must pass BoundaryAgent review before commit
- Cannot write outcome measurement, persistent state, confidence scoring

**Example Task:**
```
"Implement SSEClient safe wrapper (9 methods only)"

1. Read existing sse/ module structure
2. Identify Phase A-C methods to expose
3. Write client.py with only permitted methods
4. Add type stubs blocking forbidden operations
5. Return code to orchestrator for validation
```

---

### 3. **TestAgent** (`agents/test_agent.py`)
**Role:** Writes tests, runs validation, analyzes failures

**Capabilities:**
- Write pytest tests
- Run test suite
- Analyze failures
- Generate boundary violation tests
- Ensure 100% coverage of forbidden patterns

**Tools:**
- `create_file`, `replace_string_in_file`
- `run_in_terminal` (pytest execution)
- `get_errors`, `test_failure`
- `semantic_search` (find related tests)

**Constraints:**
- Tests must actually test boundaries (not just pass trivially)
- Must cover positive cases (allowed operations) and negative cases (forbidden)

**Example Task:**
```
"Write test for outcome measurement detection"

1. Create test_phase_6_boundaries.py
2. Write TestOutcomeMeasurementForbidden class
3. Test: no outcome_data tables exist
4. Test: no measure_recommendation_success() methods
5. Test: no user_followed_advice tracking
6. Run tests to ensure they fail if boundaries violated
```

---

### 4. **BoundaryAgent** (`agents/boundary_agent.py`)
**Role:** Phase 6 enforcement, detect architectural violations

**Capabilities:**
- Review code for forbidden patterns
- Check for measurement, learning, optimization
- Validate against Phase 6 contract
- Generate violation reports
- **Use SSE to detect contradictions between code and charter**

**Tools:**
- `grep_search` (find suspicious patterns)
- `semantic_search` (find optimization-like code)
- `read_file` (code review)
- **SSE API** (contradiction detection)

**Forbidden Patterns to Detect:**
```python
# Outcome measurement
"measure_success", "track_outcome", "user_followed", 
"recommendation_accepted", "outcome_data", "success_rate"

# Persistent learning
"update_model", "learn_from", "improve_confidence",
"historical_accuracy", "track_performance"

# Confidence scoring
"confidence_score", "certainty_level", "reliability_rating"

# Truth filtering
"filter_by_truth", "select_best", "rank_by_accuracy"

# Explanation ranking
"best_explanation", "rank_hypotheses", "score_reasoning"
```

**SSE Integration:**
```python
# Check code against Phase 6 charter
contradictions = sse.detect_contradictions([
    new_code_claims,
    phase_6_charter_claims
])

if contradictions:
    return f"BOUNDARY VIOLATION: {contradictions}"
```

---

### 5. **DocsAgent** (`agents/docs_agent.py`)
**Role:** Generate and update documentation

**Capabilities:**
- Update README, docs, quick references
- Generate API documentation
- Write implementation summaries
- Keep docs in sync with code

**Tools:**
- `read_file`, `create_file`, `replace_string_in_file`
- `grep_search` (find related docs)
- `semantic_search` (understand context)

**Constraints:**
- Documentation must match actual implementation
- Must not claim capabilities beyond Phase A-C
- Must accurately represent boundaries

---

### 6. **AnalysisAgent** (`agents/analysis_agent.py`)
**Role:** Deep code analysis, semantic search, research

**Capabilities:**
- Semantic search across codebase
- Find related implementations
- Analyze dependencies
- Research best practices
- Find contradictions in existing code

**Tools:**
- `semantic_search`, `grep_search`
- `file_search`, `list_dir`
- `read_file` (bulk reading)
- **SSE API** (detect contradictions in docs/code)

**Use Cases:**
- "Find all places we track user data"
- "Search for any learning/optimization patterns"
- "Analyze if implementation matches charter"

---

## SSE Integration Layer

### **ValidationEngine** (`sse_validation.py`)
Uses SSE's contradiction detection to validate agent outputs

**How It Works:**
```python
from sse.sse import SSE

class AgentValidator:
    def __init__(self):
        self.sse = SSE()
        self.phase_6_charter = load_charter()
    
    def validate_code_against_charter(self, code: str, claims: list[str]) -> list:
        """
        Detect contradictions between new code and Phase 6 charter
        """
        # Extract claims from code (docstrings, comments, function names)
        code_claims = self.extract_code_claims(code)
        
        # Combine with Phase 6 charter claims
        all_claims = code_claims + self.phase_6_charter
        
        # Run SSE contradiction detection
        contradictions = self.sse.detect_contradictions(all_claims)
        
        return contradictions
    
    def validate_agent_outputs(self, outputs: dict) -> dict:
        """
        Check if different agent outputs contradict each other
        """
        # CodeAgent says: "This function tracks user preferences"
        # BoundaryAgent says: "No persistent state allowed"
        # SSE detects: CONTRADICTION
        
        all_claims = []
        for agent, output in outputs.items():
            claims = self.extract_claims(output)
            all_claims.extend([(agent, claim) for claim in claims])
        
        contradictions = self.sse.detect_contradictions([c[1] for c in all_claims])
        
        # Annotate which agents contradict
        violations = []
        for c in contradictions:
            violations.append({
                "agent_a": all_claims[c.claim_a][0],
                "agent_b": all_claims[c.claim_b][0],
                "contradiction": c
            })
        
        return violations
```

**Validation Checks:**
1. **Code vs Charter:** New code doesn't contradict Phase 6
2. **Agent vs Agent:** CodeAgent output doesn't contradict BoundaryAgent analysis
3. **Code vs Docs:** Implementation matches documentation
4. **Tests vs Code:** Tests actually validate what code claims to do

---

## Orchestrator Implementation

### **TaskDecomposer** (`task_decomposer.py`)
Breaks complex requests into agent-specific subtasks

```python
class TaskDecomposer:
    def decompose(self, user_request: str) -> list[Task]:
        """
        Parse user request into subtasks with dependencies
        """
        # Example: "Implement boundary test suite"
        
        tasks = [
            Task(
                id=1,
                agent="BoundaryAgent",
                description="Define forbidden patterns for outcome measurement",
                dependencies=[]
            ),
            Task(
                id=2,
                agent="CodeAgent",
                description="Implement test_outcome_measurement_forbidden.py",
                dependencies=[1]  # needs boundary definitions first
            ),
            Task(
                id=3,
                agent="TestAgent",
                description="Run boundary tests and validate they catch violations",
                dependencies=[2]
            ),
            Task(
                id=4,
                agent="DocsAgent",
                description="Document boundary test suite",
                dependencies=[2]
            ),
            Task(
                id=5,
                agent="AnalysisAgent",
                description="Search codebase for any existing boundary violations",
                dependencies=[1]
            )
        ]
        
        return tasks
```

### **AgentRouter** (`agent_router.py`)
Routes tasks to appropriate agents, handles parallel execution

```python
class AgentRouter:
    def __init__(self):
        self.agents = {
            "CodeAgent": CodeAgent(),
            "TestAgent": TestAgent(),
            "BoundaryAgent": BoundaryAgent(),
            "DocsAgent": DocsAgent(),
            "AnalysisAgent": AnalysisAgent()
        }
    
    def execute_tasks(self, tasks: list[Task]) -> dict:
        """
        Execute tasks respecting dependencies, parallelize when possible
        """
        results = {}
        
        while tasks:
            # Find tasks with satisfied dependencies
            ready_tasks = [t for t in tasks if self.dependencies_met(t, results)]
            
            # Execute in parallel if independent
            parallel_results = self.execute_parallel(ready_tasks)
            
            results.update(parallel_results)
            tasks = [t for t in tasks if t.id not in results]
        
        return results
    
    def execute_parallel(self, tasks: list[Task]) -> dict:
        """Run independent tasks simultaneously"""
        # Group by agent type (same agent can't run parallel)
        grouped = self.group_by_agent(tasks)
        
        results = {}
        for agent_type, agent_tasks in grouped.items():
            agent = self.agents[agent_type]
            for task in agent_tasks:
                results[task.id] = agent.execute(task)
        
        return results
```

### **ResultSynthesizer** (`result_synthesizer.py`)
Combines agent outputs into coherent final result

```python
class ResultSynthesizer:
    def __init__(self):
        self.validator = AgentValidator()
    
    def synthesize(self, results: dict, tasks: list[Task]) -> str:
        """
        Combine agent outputs, check for contradictions, format final output
        """
        # 1. Validate no contradictions between agents
        violations = self.validator.validate_agent_outputs(results)
        
        if violations:
            return self.handle_violations(violations, results)
        
        # 2. Combine outputs in logical order
        synthesis = self.merge_outputs(results, tasks)
        
        # 3. Validate against Phase 6 charter
        charter_violations = self.validator.validate_code_against_charter(synthesis)
        
        if charter_violations:
            return self.handle_charter_violations(charter_violations)
        
        # 4. Format for user
        return self.format_output(synthesis)
```

---

## Phase 6 Enforcement in Multi-Agent Context

### **Key Insight:** Multi-agent systems can accidentally create optimization loops

**Dangerous Pattern:**
```
User: "Make SSE better"

CodeAgent: Adds feature to track which contradictions users click on
TestAgent: Tests feature works (tracking persists)
DocsAgent: Documents new "user engagement analytics"
BoundaryAgent: ❌ FAILS TO CATCH IT (each piece looks innocent)

Result: Outcome measurement snuck in through distributed implementation
```

**Safe Pattern (with SSE validation):**
```
User: "Make SSE better"

CodeAgent: Proposes tracking which contradictions users click on
TestAgent: Writes tests for tracking
DocsAgent: Drafts documentation

↓ BEFORE SYNTHESIS ↓

SSEValidator:
  - Extracts claim from CodeAgent: "tracks user clicks"
  - Extracts claim from Phase 6: "no outcome measurement"
  - Detects contradiction: "tracking user behavior = measuring outcomes"
  - BLOCKS implementation

BoundaryAgent (alerted):
  - Reviews proposed feature
  - Confirms: "Click tracking = outcome measurement"
  - Suggests alternative: "Show all contradictions equally, no tracking"

Orchestrator:
  - Rejects CodeAgent output
  - Returns to user with boundary explanation
```

---

## Example Workflows

### **Workflow 1: Implement Week 1 Boundary Tests**

```
User Request: "Implement Week 1 boundary test suite from roadmap"

Orchestrator Decomposes:
  Task 1 (BoundaryAgent): Define all forbidden patterns
  Task 2 (CodeAgent): Write tests/test_phase_6_boundaries.py
  Task 3 (TestAgent): Run tests, ensure they fail on violations
  Task 4 (DocsAgent): Update test documentation
  Task 5 (AnalysisAgent): Search for existing violations

Execution (parallel where possible):
  [BoundaryAgent] → forbidden_patterns.json (5 categories)
  [CodeAgent + AnalysisAgent] → parallel (use patterns from Task 1)
  [TestAgent] → runs after CodeAgent
  [DocsAgent] → runs after CodeAgent

Validation:
  SSEValidator checks:
    ✓ Tests actually test boundaries (not trivial passes)
    ✓ Documentation matches implementation
    ✓ No contradictions between agents
    ✓ All aligns with Phase 6 charter

Output:
  - tests/test_phase_6_boundaries.py (800 lines, 20 tests)
  - docs/boundary_tests.md (updated)
  - analysis_report.md (no existing violations found)
  - All tests passing
```

---

### **Workflow 2: Review PR for Boundary Violations**

```
User Request: "Review PR #42 for Phase 6 compliance"

Orchestrator Decomposes:
  Task 1 (AnalysisAgent): Get PR diff, extract changes
  Task 2 (BoundaryAgent): Scan for forbidden patterns
  Task 3 (SSEValidator): Check changes vs Phase 6 charter
  Task 4 (TestAgent): Run boundary tests on new code
  Task 5 (DocsAgent): Check if docs updated consistently

Execution:
  [AnalysisAgent] → Reads PR diff
  [BoundaryAgent + SSEValidator + TestAgent] → parallel analysis
  [DocsAgent] → checks doc updates

Validation:
  BoundaryAgent: grep for "track_outcome", "measure_success" → FOUND
  SSEValidator: Contradiction detected:
    - PR claims: "Add feature to track recommendation success"
    - Phase 6: "No outcome measurement"
    - Result: VIOLATION DETECTED
  
  TestAgent: Run test_outcome_measurement_forbidden → FAILS
  DocsAgent: No doc update (suspicious for new feature)

Output:
  🛑 PR #42 REJECTED - Phase 6 Boundary Violation
  
  Violations found:
  1. Line 42: `track_recommendation_success()` - outcome measurement
  2. Line 78: `user_followed_advice` table - persistent state
  3. No documentation (indicates stealth feature)
  
  SSE Contradiction Detection:
  - PR adds "recommendation success tracking"
  - Phase 6 forbids "measuring if recommendations worked"
  
  Recommendation: Remove tracking. Show recommendations without measurement.
```

---

### **Workflow 3: Generate Feature Based on Roadmap**

```
User Request: "Implement multi-frame explanation engine (Phase B)"

Orchestrator Decomposes:
  Task 1 (AnalysisAgent): Read COMPLETE_IMPLEMENTATION_ROADMAP.md pseudocode
  Task 2 (BoundaryAgent): Verify multi-frame doesn't rank/select
  Task 3 (CodeAgent): Implement MultiFrameExplainer class
  Task 4 (TestAgent): Write tests for 5 independent framings
  Task 5 (DocsAgent): Document multi-frame system

Execution:
  [AnalysisAgent] → Extracts pseudocode from roadmap
  [BoundaryAgent] → Defines constraints: "no ranking, all frames equal"
  [CodeAgent] → Implements (uses BoundaryAgent constraints)
  [TestAgent + DocsAgent] → parallel

Validation:
  BoundaryAgent checks CodeAgent output:
    ✓ 5 framings generated
    ✓ No confidence scores
    ✓ No "best explanation" selection
    ✓ All presented equally
  
  SSEValidator:
    ✓ Code doesn't contradict Phase 6
    ✓ Docs match implementation
    ✓ Tests validate boundary compliance

Output:
  - sse/multi_frame_explainer.py (Phase B compliant)
  - tests/test_multi_frame.py (validates equal treatment)
  - docs/multi_frame_usage.md
  - Example: 5 framings for same contradiction, no ranking
```

---

## Features for General-Purpose Use (Beyond SSE)

### **Plugin Architecture**
```python
class AgentPlugin:
    """Base class for custom agents"""
    def execute(self, task: Task) -> Result:
        raise NotImplementedError

# Custom agents for future projects
class WebScraperAgent(AgentPlugin):
    """Scrapes web data"""
    pass

class DataAnalysisAgent(AgentPlugin):
    """Analyzes datasets"""
    pass

class DeploymentAgent(AgentPlugin):
    """Handles deployment tasks"""
    pass
```

### **Workspace Memory**
Persistent context across sessions (but stateless per request)

```python
class WorkspaceMemory:
    """Remembers project context, not outcomes"""
    def __init__(self, workspace_path: str):
        self.context = {
            "project_type": "SSE",
            "phase": "Phase 6 implementation",
            "boundaries": load_phase_6_charter(),
            "recent_files": [],
            "active_tasks": []
        }
    
    def get_context(self) -> dict:
        """Provide context to agents"""
        return self.context
    
    def update_context(self, key: str, value: any):
        """Update workspace state (not learning from outcomes)"""
        self.context[key] = value
```

### **Conflict Resolution**
When agents disagree, use SSE to detect contradictions

```python
class ConflictResolver:
    def resolve(self, agent_outputs: dict) -> Resolution:
        """
        When agents contradict, don't pick a winner.
        Show contradictions to user, let them decide.
        """
        contradictions = sse.detect_contradictions(agent_outputs)
        
        return Resolution(
            contradictions=contradictions,
            options=[output for output in agent_outputs.values()],
            decision="user"  # user chooses, system doesn't optimize
        )
```

---

## Implementation Priorities

### **Phase 1: Core Infrastructure (Week 1)**
- Orchestrator with task decomposition
- Agent base classes
- Basic routing
- Simple result synthesis

### **Phase 2: SSE Integration (Week 1-2)**
- AgentValidator using SSE
- Contradiction detection pipeline
- Boundary violation detection

### **Phase 3: Specialized Agents (Week 2-3)**
- CodeAgent
- TestAgent
- BoundaryAgent
- DocsAgent
- AnalysisAgent

### **Phase 4: Advanced Features (Week 3-4)**
- Parallel execution
- Conflict resolution
- Plugin architecture
- Workspace memory

### **Phase 5: SSE-Specific Workflows (Week 4)**
- Boundary test generation
- PR review automation
- Roadmap implementation
- Quarterly audit helpers

---

## Success Criteria

### **For SSE Development:**
✅ Can implement roadmap features automatically with Phase 6 compliance  
✅ Catches boundary violations before they reach codebase  
✅ Speeds up development by 3-5x  
✅ Maintains 100% test coverage  
✅ No false positives (doesn't block valid Phase A-C work)

### **For General Use:**
✅ Plugin architecture allows custom agents  
✅ Works for non-SSE projects  
✅ Parallel execution reduces time by 50%+  
✅ Contradiction detection prevents inconsistent implementations  
✅ Reusable across future projects

---

## Key Innovation: SSE as Meta-Validator

**The system uses SSE to validate itself:**
- SSE detects contradictions in agent outputs
- SSE validates code against charter
- SSE ensures documentation matches implementation
- SSE prevents distributed boundary violations

**This is Phase A SSE usage** (observation only):
- System observes agent outputs
- System detects contradictions
- System shows contradictions to user
- User decides how to resolve
- **System doesn't learn which resolution "worked"**

**Not optimization:** The multi-agent system doesn't get better at avoiding contradictions over time. It just detects them every time, fresh.

---

## The Meta-Irony

We're building a multi-agent system to help build SSE.  
SSE's job is to prevent systems from becoming agents.  
The multi-agent system uses SSE to prevent itself from becoming too agentic.

**It's boundaries all the way down.**

This is good design.
