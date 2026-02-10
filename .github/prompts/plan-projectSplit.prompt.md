# Project Split Plan — CRT Monolith → Packages

> **Purpose:** Map exactly which files go where when the 58K-line monolith becomes separate, installable packages.

---

## Target Architecture

```
crt-memory          (pip install crt-memory)        — Core library, zero-config
groundcheck         (pip install groundcheck)        — Standalone verifier
crt-mcp-server      (pip install crt-mcp-server)     — MCP tool server
crt-server          (not published)                  — Full FastAPI monolith (personal agent)
```

### Dependency Graph

```
crt-server (full monolith, private)
    ├── crt-memory
    ├── groundcheck
    ├── fastapi, uvicorn, ollama, xgboost, ...
    └── crt-mcp-server (optional)

crt-mcp-server
    ├── crt-memory
    └── mcp SDK

crt-memory (core library)
    ├── numpy
    ├── sentence-transformers
    ├── scikit-learn
    └── groundcheck (optional)

groundcheck (standalone)
    └── (no dependencies beyond stdlib)
```

---

## Package 1: `crt-memory` (Core Library)

**What ships:** The trust-weighted memory system with contradiction detection. No server, no LLM required.

### Files INCLUDED in `crt-memory`

| File | Purpose | Notes |
|------|---------|-------|
| `personal_agent/crt.py` | **NEW** — `CRT()` wrapper facade | Created in Phase 1 |
| `personal_agent/crt_types.py` | **NEW** — `StoreResult`, `AskResult`, `VerifyResult` | Created in Phase 1 |
| `personal_agent/crt_core.py` | CRT math equations, trust scoring (~1000 lines) | Core, no changes needed |
| `personal_agent/crt_memory.py` | SQLite memory storage (~1528 lines) | Add `:memory:` default path |
| `personal_agent/crt_ledger.py` | Contradiction ledger (~500 lines) | Core, no changes needed |
| `personal_agent/fact_slots.py` | Regex fact extraction (~900 lines) | Core, no changes needed |
| `personal_agent/domain_detector.py` | Domain detection (~300 lines) | Core, no changes needed |
| `personal_agent/embeddings.py` | Embedding utilities | Core, lazy-load model |
| `personal_agent/crt_semantic_anchor.py` | Semantic anchoring | Core |
| `personal_agent/ml_contradiction_detector.py` | XGBoost detector | Behind `_XGB_AVAILABLE` guard |
| `personal_agent/db_utils.py` | Database utilities | Core |
| `personal_agent/exceptions.py` | Custom exceptions | Core |
| `personal_agent/__init__.py` | Package exports | Add `CRT` to exports |
| `personal_agent/integrations/` | **NEW** — LangChain/LlamaIndex plugins | Created in Phase 4 |

### Files EXCLUDED from `crt-memory` (stay in monolith only)

| File | Why Excluded |
|------|-------------|
| `personal_agent/crt_rag.py` (7001 lines) | Requires LLM, FastAPI context, too heavy |
| `personal_agent/agent_loop.py` | Server-only orchestration |
| `personal_agent/agent_reasoning.py` | LLM reasoning, server-only |
| `personal_agent/ollama_client.py` | LLM client, optional |
| `personal_agent/core.py` | PersonalAgent class, server-only |
| `personal_agent/memory.py` | Old MemorySystem (pre-CRT) |
| `personal_agent/rag.py` | Old RAGEngine (pre-CRT) |
| `personal_agent/reasoning.py` | Old ReasoningEngine |
| `personal_agent/researcher.py` | Research agent, server-only |
| `personal_agent/research_engine.py` | Research engine, server-only |
| `personal_agent/code_executor.py` | Code execution, server-only |
| `personal_agent/code_worker.py` | Code worker, server-only |
| `personal_agent/artifact_store.py` | Artifact storage, server-only |
| `personal_agent/background_jobs.py` | Background jobs, server-only |
| `personal_agent/continuous_loops.py` | Server loops |
| `personal_agent/heartbeat_*.py` | Heartbeat system, server-only |
| `personal_agent/idle_scheduler.py` | Scheduler, server-only |
| `personal_agent/intent_router.py` | Intent routing, server-only |
| `personal_agent/jobs_*.py` | Job system, server-only |
| `personal_agent/greeting_system.py` | Greeting, server-only |
| `personal_agent/onboarding.py` | Onboarding flow, server-only |
| `personal_agent/policy.py` | Disclosure policy, server-only |
| `personal_agent/runtime_config.py` | Runtime config, server-only |
| `personal_agent/llm_extractor.py` | LLM-based extraction (library uses regex) |
| `personal_agent/llm_drift_assessor.py` | LLM drift, server-only |
| `personal_agent/profile_llm_methods.py` | LLM profile methods |
| `personal_agent/training_loop.py` | DNNT training |
| `personal_agent/thinking_loop.py` | Thinking loop |
| `personal_agent/tasking_loop.py` | Tasking loop |
| `personal_agent/dnnt/` | Entire DNNT micro-transformer directory |
| `personal_agent/engine/` | Engine subdirectory |
| `personal_agent/reasoning_learner/` | Learning subsystem |
| `personal_agent/fact_tuples.py` | Open-world fact tuples (LLM-dependent) |
| `personal_agent/two_tier_facts.py` | Two-tier system (LLM-dependent) |
| `personal_agent/contradiction_lifecycle.py` | Lifecycle tracking (server feature) |
| `personal_agent/user_profile.py` | User profiles (server feature) |
| `personal_agent/canonical_view.py` | Canonical view (server feature) |
| `personal_agent/disclosure_policy.py` | Disclosure policy (server feature) |
| `personal_agent/active_learning.py` | Active learning (server feature) |
| `personal_agent/learned_suggestions.py` | Suggestions (server feature) |
| `personal_agent/episodic_memory.py` | Episodic memory (server feature) |
| `personal_agent/promotion_apply.py` | Promotions (server feature) |
| `personal_agent/schema_validation.py` | Schema validation (server feature) |
| `personal_agent/scheduled_tasks.py` | Scheduled tasks (server feature) |
| `personal_agent/proactive_triggers.py` | Proactive triggers (server feature) |
| `personal_agent/reflection_system.py` | Reflection (server feature) |
| `personal_agent/resolution_patterns.py` | Resolution patterns (server feature) |
| `personal_agent/contradiction_trace_logger.py` | Trace logging (server feature) |
| `personal_agent/evidence_packet.py` | Evidence packets (server feature) |
| `personal_agent/fact_store.py` | Fact store (server feature) |

### `crt-memory` pyproject.toml

```toml
[project]
name = "crt-memory"
version = "1.0.0"
description = "Contradiction-preserving memory for AI agents. No silent overwrites."
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "numpy>=1.24.0",
    "sentence-transformers>=2.2.0",
    "scikit-learn>=1.3.0",
]

[project.optional-dependencies]
ml = ["xgboost>=1.7.0"]
groundcheck = ["groundcheck>=0.1.0"]
server = ["fastapi>=0.100.0", "uvicorn[standard]>=0.22.0", "requests>=2.31.0"]
llm = ["openai>=1.0.0", "anthropic>=0.18.0"]
langchain = ["langchain>=0.1.0"]
full = ["crt-memory[ml,groundcheck,server,llm,langchain]"]
dev = ["pytest>=7.0.0", "pytest-asyncio>=0.21.0", "ruff>=0.1.0"]
```

---

## Package 2: `groundcheck` (Standalone Verifier)

**What ships:** The grounding verifier. Already 90% decoupled at `groundcheck/`.

### Files INCLUDED

| File | Purpose |
|------|---------|
| `groundcheck/groundcheck/__init__.py` | Package exports |
| `groundcheck/groundcheck/verifier.py` | `GroundCheck.verify()` — 962 lines |
| `groundcheck/groundcheck/types.py` | `Memory`, `VerificationReport`, `ExtractedFact` |
| `groundcheck/groundcheck/fact_extractor.py` | `extract_fact_slots()` |
| `groundcheck/groundcheck/utils.py` | Utilities |
| `groundcheck/groundcheck/tuple_verifier.py` | Tuple verification |
| `groundcheck/groundcheck/neural_extractor.py` | Optional neural extraction |
| `groundcheck/groundcheck/semantic_matcher.py` | Optional semantic matching |
| `groundcheck/groundcheck/semantic_contradiction.py` | Optional contradiction detection |
| `groundcheck/pyproject.toml` | Already exists, v0.1.0 |
| `groundcheck/README.md` | Already exists |
| `groundcheck/tests/` | Already exists |

### Status: Already Split

GroundCheck is already a separate package with its own `pyproject.toml`, `setup.py`, tests, and `__init__.py`. Neural features are already behind `ImportError` guards.

**Remaining work:**
1. Bump version to `1.0.0` to match `crt-memory`
2. Update README with standalone usage examples
3. Ensure `pip install groundcheck` works independently (verify no imports from `personal_agent`)
4. Publish to PyPI

---

## Package 3: `crt-mcp-server` (MCP Tool Server)

**What ships:** Three MCP tools for any compatible agent.

### Files (all NEW)

| File | Purpose |
|------|---------|
| `mcp_server/crt_mcp.py` | MCP server with 3 tools |
| `mcp_server/pyproject.toml` | Package config |
| `mcp_server/README.md` | Setup instructions for Claude Desktop, Copilot |
| `mcp_server/tests/test_mcp_tools.py` | Tool tests |

### MCP Tools

| Tool | Input | Output |
|------|-------|--------|
| `crt_store_fact` | `{text: str}` | `{facts_stored: [], contradictions: []}` |
| `crt_check_memory` | `{query: str}` | `{facts: [], contradiction: bool, confidence: float}` |
| `crt_verify_output` | `{claim: str}` | `{grounded: bool, conflicts: []}` |

### Dependencies

```toml
[project]
dependencies = ["crt-memory>=1.0.0", "mcp>=1.0.0"]
```

---

## Package 4: `crt-server` (Full Monolith — NOT Published)

**What stays:** Everything. The monolith continues to work for the personal agent use case.

### No Changes Required

- `crt_api.py` — FastAPI entry point
- `routes/` — All API routes
- `sse/` — All SSE modules
- `personal_agent/` — Full directory (superset of what `crt-memory` ships)
- `frontend/` — Web UI
- `tools/` — Test drivers, analysis scripts
- `tests/` — Full test suite
- `data/`, `docs/`, `schemas/` — Supporting files

### Installation

```powershell
pip install -e ".[full]"  # Installs everything including server deps
```

---

## Migration Strategy

### Phase A: Wrapper First (No File Moves)

1. Create `personal_agent/crt.py` and `personal_agent/crt_types.py`
2. Add import guards to files that need them
3. Slim `pyproject.toml` dependencies
4. Verify: `pip install -e .` works, `from crt_memory import CRT` works, server still works

**Key insight:** We DON'T physically move files. The `crt-memory` package ships from the same `personal_agent/` directory — we just control what's importable via `__init__.py` and what's installable via `pyproject.toml`.

### Phase B: Publish (After Phase A validated)

1. `pip install build && python -m build` to create wheel
2. `pip install twine && twine upload dist/*` to publish
3. Verify: `pip install crt-memory` from PyPI works on a clean venv

### Phase C: Physical Split (Optional, Later)

If we ever want truly separate repos:
1. `crt-memory/` repo — only the files from Package 1
2. `groundcheck/` repo — already almost there
3. `crt-mcp-server/` repo — just the MCP server
4. `crt-server/` repo — the full monolith, depends on the other three

**This is NOT needed for v1.0.** Monorepo with multiple `pyproject.toml` files works fine. LangChain, FastAPI, and many major projects use this pattern.

---

## Implementation Order

```
Week 1:  Phase 1 (CRT wrapper) + Phase 2 (README + demos)
         ├── Create crt.py, crt_types.py
         ├── Wire exports
         ├── Write tests
         ├── Rewrite README
         └── Create example scripts

Week 2:  Phase 3 (slim deps + import guards)
         ├── Restructure pyproject.toml
         ├── Add try/except guards
         ├── Test: pip install with no extras
         └── Test: pip install with [server] extras

Week 3:  Phase 4 (integrations) + Phase 5 start (MCP)
         ├── LangChain CRTMemory
         ├── MCP server skeleton
         └── MCP tool implementations

Week 4:  Phase 5 finish + publish
         ├── MCP testing
         ├── PyPI publish crt-memory
         ├── PyPI publish groundcheck
         ├── PyPI publish crt-mcp-server
         └── Announcement / demo video
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| `sentence-transformers` is 500MB+ | Scares off quick install | Document `CRT(embedding_model=None)` for TF-IDF fallback |
| `crt_memory.py` imports server-only code | Import crash | Audit all imports in included files, add guards |
| Breaking existing tests | Blocks monolith development | Run full test suite after every change |
| PyPI name `crt-memory` taken | Can't publish | Already registered in `pyproject.toml` |
| LangChain API changes frequently | Integration breaks | Pin to `langchain>=0.1.0,<0.3.0`, test monthly |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| `pip install crt-memory` time (no extras) | < 60 seconds |
| Lines of code to first contradiction | ≤ 6 |
| Import time (`from crt_memory import CRT`) | < 2 seconds |
| First `tell()` call (includes model load) | < 10 seconds |
| Subsequent `tell()` calls | < 50ms |
| `verify()` call | < 2ms |
| GitHub stars (3 months) | > 100 |
| PyPI downloads (3 months) | > 1,000 |
