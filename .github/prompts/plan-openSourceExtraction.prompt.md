# Open-Source Library Extraction — Implementation Plan

> **Goal:** Extract the CRT monolith into a pip-installable library that wins developers in 10 seconds.
> **Prerequisites:** Adversarial hardening at 95%+ (Steps 1–2 from `plan-adversarialRound2Hardening.prompt.md`)
> **Estimated effort:** 4 weeks, 5 phases

---

## The Problem

The CRT system is 58K lines, requires a FastAPI server, Ollama, and SQLite config to do anything. Nobody will try it. The fix: `pip install crt-memory` → 6 lines of Python → contradiction caught. No server, no LLM, no config.

---

## Phase 1: The 10-Second Demo (Week 1)

### 1.1 Create `CRT()` Wrapper Class

**New file: `personal_agent/crt.py`** (~120 lines)

A thin facade over `CRTMemorySystem`, `CRTEnhancedRAG`, and `GroundCheck` that works with zero config:

```python
from crt_memory import CRT

crt = CRT()  # In-memory SQLite, no server, no LLM
crt.tell("My name is Alice and I work at Google")
crt.tell("I've been at Google for 3 years")

result = crt.ask("What do you know about me?")
print(result.facts)      # [name=Alice, employer=Google, tenure=3 years]

crt.tell("Actually I work at Microsoft")
result = crt.ask("Where do I work?")
print(result.contradiction)  # True
print(result.history)        # [Google (trust=0.4), Microsoft (trust=0.8)]
```

**Implementation details:**

- `CRT.__init__(self, db=":memory:", embedding_model="all-MiniLM-L6-v2")`:
  - Creates `CRTMemorySystem` with in-memory SQLite
  - Creates `CRTMath` with default config
  - Lazy-loads `sentence-transformers` on first `tell()` call
  - NO FastAPI, NO Ollama, NO thread management
- `CRT.tell(self, text: str) -> StoreResult`:
  - Calls `fact_slots.extract_fact_slots(text)` for extraction
  - Calls `CRTMemorySystem.store_memory()` with extracted facts
  - Runs contradiction detection against existing memories
  - Returns `StoreResult(facts_stored=[], contradictions_found=[], trust_scores={})`
- `CRT.ask(self, query: str) -> AskResult`:
  - Calls `CRTMemorySystem.retrieve_memories(query)`
  - Runs GroundCheck verification if memories exist
  - Returns `AskResult(facts=[], contradiction=bool, history=[], confidence=float)`
- `CRT.verify(self, claim: str) -> VerifyResult`:
  - Runs `GroundCheck.verify(claim, all_memories)`
  - Returns `VerifyResult(grounded=bool, supporting=[], conflicting=[])`
- `CRT.contradictions` property:
  - Returns all entries from `ContradictionLedger`

**Key constraint:** ZERO LLM calls. All detection uses regex (fact_slots) + cosine similarity + CRTMath. LLM is optional enhancement, never required.

**Source files to reference:**
- `personal_agent/crt_memory.py` — `store_memory()` at line 361, `retrieve_memories()` at line 569
- `personal_agent/crt_core.py` — `CRTMath`, trust scoring
- `personal_agent/fact_slots.py` — `extract_fact_slots()` for regex extraction
- `personal_agent/crt_ledger.py` — `ContradictionLedger`
- `groundcheck/groundcheck/verifier.py` — `GroundCheck.verify()` at line 501

### 1.2 Create Return Types

**New file: `personal_agent/crt_types.py`** (~50 lines)

```python
@dataclass
class StoreResult:
    facts_stored: list[dict]
    contradictions_found: list[dict]
    trust_scores: dict[str, float]

@dataclass
class AskResult:
    facts: list[dict]
    contradiction: bool
    history: list[dict]
    confidence: float

@dataclass
class VerifyResult:
    grounded: bool
    supporting: list[str]
    conflicting: list[str]
```

### 1.3 Wire Exports

**Edit `personal_agent/__init__.py`:** Add `CRT`, `StoreResult`, `AskResult`, `VerifyResult` to imports and `__all__`.

### 1.4 Validate Zero-Config Operation

**New test: `tests/test_crt_wrapper.py`** (~80 lines)

```python
def test_ten_second_demo():
    """The entire 10-second pitch must work with no config."""
    crt = CRT()
    crt.tell("My name is Alice")
    crt.tell("My name is Bob")
    result = crt.ask("What is my name?")
    assert result.contradiction is True
    assert len(result.history) == 2
```

Tests must pass with ONLY `pip install crt-memory` — no server, no env vars, no Ollama.

---

## Phase 2: README Rewrite & Demo Scripts (Week 1–2)

### 2.1 Rewrite README.md

The current README is implementation-focused. New structure:

```
# CRT Memory — Contradiction-Preserving Memory for AI Agents

[Badges: PyPI version, Python 3.10+, MIT, tests passing]

## Install
pip install crt-memory

## 10-Second Demo
[The 6-line code block from Phase 1.1]

## What It Does
- Stores facts with trust scores (not just embeddings)
- Detects contradictions without an LLM (regex + cosine + CRT math)
- Preserves both versions (never silently overwrites)
- Sub-2ms verification (2,634x faster than SelfCheckGPT)
- Works in-memory or with SQLite persistence

## Side-by-Side: CRT vs Plain Vector Store
[Link to examples/side_by_side.py]

## Use With LangChain
[5-line integration example]

## Benchmark
[Table: CRT vs SelfCheckGPT vs NLI on speed, accuracy, false positives]

## Advanced Usage
[Server mode, custom embeddings, trust thresholds]

## How It Works
[Brief CRT math explanation — R_i = s_i · ρ_i · (α·trust + (1-α)·confidence)]
```

### 2.2 Create `examples/side_by_side.py`

**New file: `examples/side_by_side.py`** (~60 lines)

Shows the same 10 facts fed to (a) raw ChromaDB and (b) CRT Memory, then queries with a contradiction. ChromaDB returns the latest silently; CRT catches it.

```python
"""Side-by-side: CRT Memory vs plain vector store on contradiction handling."""
from crt_memory import CRT

crt = CRT()
facts = [
    "My name is Jordan",
    "I work at Tesla",
    "I've been there 5 years",
    "I have a PhD in Physics",
    "I live in Austin",
    # Now contradict
    "Actually my name is Alex",
    "I work at SpaceX, not Tesla",
    "I've only been there 2 years",
]

for fact in facts:
    result = crt.tell(fact)
    if result.contradictions_found:
        print(f"⚠ Contradiction: {result.contradictions_found}")

final = crt.ask("Tell me about myself")
print(f"\nFacts: {len(final.facts)}")
print(f"Contradictions detected: {final.contradiction}")
print(f"Full history preserved: {len(final.history)} entries")
```

### 2.3 Create `examples/benchmark_memory.py`

**New file: `examples/benchmark_memory.py`** (~100 lines)

Runs the adversarial memory benchmark:
- 19 contradiction scenarios (same as `agent_adversarial_driver.py` scenarios)
- Reports: detection rate, false positive rate, mean verification time
- Outputs a markdown table suitable for README embedding

Reference: `tools/agent_adversarial_driver.py` for scenario definitions, `groundcheck/stress_test_performance.py` for timing patterns.

---

## Phase 3: Slim Dependencies & Package Config (Week 2)

### 3.1 Split `pyproject.toml` Dependencies

Current `pyproject.toml` requires `fastapi`, `uvicorn`, `beautifulsoup4` — none needed for the library.

**New dependency tiers:**

```toml
[project]
dependencies = [
    "numpy>=1.24.0",
    "sentence-transformers>=2.2.0",
    "scikit-learn>=1.3.0",
]

[project.optional-dependencies]
ml = ["xgboost>=1.7.0"]
server = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.22.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
]
groundcheck = ["groundcheck>=0.1.0"]
llm = ["openai>=1.0.0", "anthropic>=0.18.0"]
full = [
    "crt-memory[ml,server,groundcheck,llm]",
    "torch>=2.0.0",
    "transformers>=4.30.0",
]
dev = ["pytest>=7.0.0", "pytest-asyncio>=0.21.0", "ruff>=0.1.0"]
```

**Key:** `pip install crt-memory` installs ONLY numpy + sentence-transformers + scikit-learn. Everything else is opt-in.

### 3.2 Add Graceful Import Guards

Files that import `fastapi`, `xgboost`, `requests`, etc. need try/except guards so the library doesn't crash when server dependencies are missing.

**Files to guard:**
- `personal_agent/crt_rag.py` — uses `xgboost` for ML contradiction detection (fallback: skip ML, use rule-based only)
- `personal_agent/ollama_client.py` — uses `requests` (only needed in LLM mode)
- `personal_agent/ml_contradiction_detector.py` — uses `xgboost` (fallback: rule-based)

Pattern:
```python
try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False
```

### 3.3 Update Package Metadata

- Bump version to `1.0.0` (this is the public release)
- Update `[project.urls]` — confirm GitHub repo is public
- Add `[project.scripts]` entry if we want a CLI: `crt = "personal_agent.crt:main"`
- Ensure `[tool.setuptools.packages.find]` includes only what ships

---

## Phase 4: LangChain Integration (Week 3)

### 4.1 Create `CRTMemory` for LangChain

**New file: `personal_agent/integrations/langchain_memory.py`** (~80 lines)

Drop-in replacement for `ConversationBufferMemory`:

```python
from langchain.memory import BaseMemory
from crt_memory import CRT

class CRTMemory(BaseMemory):
    """LangChain memory backend that detects contradictions."""
    
    memory_key: str = "history"
    crt: CRT = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.crt = CRT()
    
    @property
    def memory_variables(self) -> list[str]:
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: dict) -> dict:
        query = inputs.get("input", "")
        result = self.crt.ask(query)
        return {self.memory_key: self._format(result)}
    
    def save_context(self, inputs: dict, outputs: dict) -> None:
        self.crt.tell(inputs.get("input", ""))
    
    def clear(self) -> None:
        self.crt = CRT()
```

**Usage:**
```python
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
from crt_memory.integrations import CRTMemory

chain = ConversationChain(llm=OpenAI(), memory=CRTMemory())
chain.predict(input="My name is Alice")
chain.predict(input="Actually my name is Bob")
# Memory now tracks the contradiction
```

### 4.2 Create LlamaIndex Integration (Stretch)

**New file: `personal_agent/integrations/llamaindex_store.py`** (~60 lines)

Similar pattern — implements the `BaseChatStore` interface from LlamaIndex.

---

## Phase 5: MCP Server (Week 3–4)

### 5.1 Create MCP Tool Server

**New file: `mcp_server/crt_mcp.py`** (~150 lines)

Three tools that any MCP-compatible agent (Claude, Copilot, etc.) can call:

```python
# Tool 1: crt_store_fact
# Input: {"text": "My name is Alice and I work at Google"}
# Output: {"facts_stored": [...], "contradictions": [...]}

# Tool 2: crt_check_memory  
# Input: {"query": "Where does the user work?"}
# Output: {"facts": [...], "contradiction": false, "confidence": 0.92}

# Tool 3: crt_verify_output
# Input: {"claim": "The user works at Amazon", "context": [...]}
# Output: {"grounded": false, "conflicts": ["User stated Google (trust=0.85)"]}
```

**Implementation:** Use the `mcp` Python SDK (`pip install mcp`). Each tool wraps the `CRT()` class from Phase 1.

### 5.2 MCP Package Config

**New file: `mcp_server/pyproject.toml`**

```toml
[project]
name = "crt-mcp-server"
version = "1.0.0"
dependencies = ["crt-memory>=1.0.0", "mcp>=1.0.0"]

[project.scripts]
crt-mcp = "crt_mcp:main"
```

### 5.3 Test MCP Tools

**New file: `mcp_server/tests/test_mcp_tools.py`** (~60 lines)

Test each tool independently — store facts, query, verify. No server needed (MCP tools can be tested as plain function calls).

---

## Validation Criteria

### Phase 1 Gate (must pass before Phase 2):
- [ ] `pip install -e .` works with no server dependencies
- [ ] `CRT()` creates an in-memory instance with no config
- [ ] `tell()` + `ask()` round-trip detects a name contradiction
- [ ] `verify()` catches an ungrounded claim
- [ ] All existing tests still pass (`pytest tests/ -v`)

### Phase 2 Gate:
- [ ] README has working code block that copy-pastes to success
- [ ] `examples/side_by_side.py` runs standalone
- [ ] `examples/benchmark_memory.py` produces a markdown table

### Phase 3 Gate:
- [ ] `pip install crt-memory` (no extras) installs ≤3 dependencies
- [ ] `from crt_memory import CRT` works without fastapi/xgboost/requests
- [ ] `pip install crt-memory[server]` still runs the full FastAPI app

### Phase 4 Gate:
- [ ] LangChain `CRTMemory` passes as drop-in for `ConversationBufferMemory`
- [ ] Example notebook runs end-to-end

### Phase 5 Gate:
- [ ] MCP server starts and registers 3 tools
- [ ] Claude Desktop can call `crt_store_fact` and `crt_check_memory`
- [ ] Tool responses are JSON-parseable

---

## Files Created/Modified Summary

| Action | File | Phase |
|--------|------|-------|
| CREATE | `personal_agent/crt.py` | 1 |
| CREATE | `personal_agent/crt_types.py` | 1 |
| MODIFY | `personal_agent/__init__.py` | 1 |
| CREATE | `tests/test_crt_wrapper.py` | 1 |
| REWRITE | `README.md` | 2 |
| CREATE | `examples/side_by_side.py` | 2 |
| CREATE | `examples/benchmark_memory.py` | 2 |
| MODIFY | `pyproject.toml` | 3 |
| MODIFY | `personal_agent/crt_rag.py` (import guards) | 3 |
| MODIFY | `personal_agent/ml_contradiction_detector.py` (import guards) | 3 |
| CREATE | `personal_agent/integrations/__init__.py` | 4 |
| CREATE | `personal_agent/integrations/langchain_memory.py` | 4 |
| CREATE | `mcp_server/crt_mcp.py` | 5 |
| CREATE | `mcp_server/pyproject.toml` | 5 |
| CREATE | `mcp_server/tests/test_mcp_tools.py` | 5 |

---

## What NOT To Do

1. **Do NOT refactor crt_rag.py** — it's 7K lines and works. Wrap it, don't rewrite it.
2. **Do NOT add new dependencies** — the whole point is fewer dependencies.
3. **Do NOT break the server** — `pip install crt-memory[server]` must still run `crt_api.py`.
4. **Do NOT optimize prematurely** — ship the wrapper first, optimize later.
5. **Do NOT touch adversarial/stress test infrastructure** — it's working and tested.
