# Repo Consolidation Plan: CRT-GroundCheck-SSE Monorepo

> Generated: 2026-02-16

## 1. Current State

| Repo | Location | Purpose | Status |
|------|----------|---------|--------|
| CRT-GroundCheck-SSE | `d:\AI_round2` | Main harness: FastAPI + React + CRT + VILT | Active |
| GroundCheck | `d:\groundcheck` | PyPI package: verifier, fact extraction, MCP | Active |
| CogniForge | `d:\CogniForge` | Model training framework | Separate |
| `f:\Ai Move later\CRT\core` | Stale path | **Does not exist** — remove from workspace | Dead |

## 2. Dependency Map

```
AI_round2 (crt-memory)
  └── pip install groundcheck>=0.4.0
      Used in: vilt_*.py, crt_mcp_server.py
      Direction: ONE-WAY (AI_round2 → groundcheck, never reverse)
```

## 3. Recommended: Vendor into Monorepo (Option A)

**Why:** Nick is sole developer of both. GC is tightly integrated. Single repo = atomic changes, no version skew.

GC stays publishable to PyPI from a `packages/` subdirectory.

### Target Structure

```
CRT-GroundCheck-SSE/
├── pyproject.toml              (root — crt-memory)
├── crt_api.py                  (FastAPI entrypoint)
├── personal_agent/             (CRT core — unchanged)
├── sse/                        (Semantic String Engine)
├── routes/                     (API routes)
├── frontend/                   (React/Vite)
├── scripts/                    (VILT benchmarks)
├── packages/
│   └── groundcheck/            ◀ MOVED from d:\groundcheck
│       ├── pyproject.toml      (PyPI: groundcheck)
│       ├── groundcheck/        (source)
│       ├── groundcheck_mcp/    (MCP server)
│       └── tests/              (GC tests)
├── tests/
│   ├── crt/                    ◀ existing CRT tests
│   ├── sse/                    ◀ existing SSE tests
│   └── conftest.py
├── docs/
├── .github/workflows/          (merged CI)
└── ...
```

## 4. Execution Steps

### Phase 1: Prep
1. Remove stale workspace entries (`f:\Ai Move later`)
2. Tag both repos: `git tag pre-consolidation`
3. Clean artifacts/ (150+ .db files → gitignore)

### Phase 2: Move
4. `git subtree add` groundcheck into `packages/groundcheck/`
5. Update `requirements.txt`: `groundcheck>=0.4.0` → `-e packages/groundcheck`
6. Move GC CI workflows, update path filters

### Phase 3: Tests
7. Reorganize tests into `tests/crt/`, `tests/sse/`, `tests/groundcheck/`
8. Update pytest.ini testpaths

### Phase 4: Cleanup
9. Archive `d:\groundcheck` (README redirect)
10. Consolidate .gitignore files
11. Update .code-workspace to single folder

## 5. Risks

| Risk | Mitigation |
|------|-----------|
| PyPI publish breaks | Test `python -m build` from packages/groundcheck before merge |
| Import paths break | No changes needed — `groundcheck` namespace unchanged |
| Git history loss | Use `git subtree add` to preserve history |

## 6. Post-Merge Checklist
- [ ] `pip install -e .` and `pip install -e packages/groundcheck` work
- [ ] All imports resolve (`groundcheck`, `personal_agent`, `sse`)
- [ ] `pytest` passes everywhere
- [ ] `python -m build` in packages/groundcheck produces valid wheel
- [ ] Frontend `npm run dev` works
- [ ] `python crt_api.py` starts
- [ ] MCP server works
