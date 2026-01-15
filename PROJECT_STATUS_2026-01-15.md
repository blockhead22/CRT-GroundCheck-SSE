# CRT Project Status Assessment - January 15, 2026

**Date:** January 15, 2026  
**Repository:** D:\AI_round2 (Windows) / /Users/nickblock/Documents/AI_round2 (macOS)  
**Last Thread:** Windows-based agent completed M2 debugging work  

---

## Executive Summary

The CRT (Coherent Retrieval & Truth) project is a **truthful personal AI system** that implements a "two-lane memory" architecture with explicit uncertainty handling and durable contradiction tracking. The system is currently in **late M2 phase** with core infrastructure complete and stress-testing revealing key improvement areas.

### 🎯 Current State: **M2 Implementation Complete, Hardening in Progress**

**What's Working:**
- ✅ Full-stack FastAPI + React UI architecture
- ✅ Background jobs system (SQLite queue + worker)
- ✅ M2 "contradictions become goals" end-to-end implementation
- ✅ Deterministic safety gates with regression tests
- ✅ 100-turn stress test infrastructure with detailed reporting
- ✅ Learned model tracking & comparison dashboard

**What Needs Work:**
- ⚠️ M2 followup automation showing 3/25 success rate (12%)
- ⚠️ Gate pass rate: 33% (67% failing - needs analysis)
- ⚠️ Some contradiction classification edge cases
- ⚠️ API self-check recently added but needs validation

---

## Recent Breakthrough (Jan 15, 2026)

The Windows thread agent **completed the M2 debugging mission**:

### Problem Identified
- M2 followup automation was **silently failing** (attempted > 0, succeeded = 0)
- Root cause: Broad `except Exception: pass` was swallowing HTTP errors
- API endpoint `/api/contradictions/respond` was returning 404 on wrong server instance

### Solution Delivered
1. **Added comprehensive logging** to `crt_stress_test.py`:
   - `_api_call_json()` helper captures URL, method, payload, status, response, errors
   - Every followup (/next, /asked, /respond) now logged to JSONL with full diagnostics
   - Non-2xx treated as explicit failure with captured error details

2. **Added `--m2-smoke` mode**:
   - Deterministic pass/fail test that forces a contradiction
   - Calls full /next → /asked → /respond cycle
   - Exits 0 on success, nonzero with clear error on failure

3. **Added API self-check**:
   - Probes key endpoints before running stress tests
   - Interprets 422 as "route exists" (validation error expected)
   - Interprets 404 as "wrong server / missing route"
   - Prevents wasting long runs on misconfigured servers

4. **Updated stress report generator**:
   - Header shows: `M2 followups: attempted=X succeeded=Y failed=Z`
   - Per-turn section includes "M2 HTTP steps" with status/body snippets

### Latest Evidence
**Report:** `artifacts/crt_stress_report.20260115_200540.md`
- **100 turns** completed
- **M2 followups:** attempted=25, succeeded=3, failed=22 (12% success)
- **Gates:** pass=33, fail=67 (33% pass rate)
- **Contradictions detected:** 5
- **First successful M2 cycle** confirmed in Turn 11

---

## Architecture Overview

### Core Components

#### 1. **Backend** (`crt_api.py`)
- FastAPI server (typically `:8123`)
- Endpoints:
  - `POST /api/chat/send` - main chat interface
  - `GET /api/contradictions/next` - fetch next unresolved contradiction
  - `POST /api/contradictions/asked` - mark contradiction as asked
  - `POST /api/contradictions/respond` - record user answer & resolve
  - `POST /api/thread/reset` - clear conversation thread
  - `/api/jobs/*` - background jobs management

#### 2. **Frontend** (`frontend/`)
- Vite/React/TypeScript application
- Pages:
  - Chat interface
  - Dashboard/Inspector (contradiction panel)
  - Docs viewer
  - Jobs UI (control plane)

#### 3. **Memory & Storage** (SQLite)
- `crt_memory.db` - long-term memory with trust/confidence
- `crt_ledger.db` - contradiction tracking
- `crt_jobs.db` - background job queue & artifacts
- `crt_audit.db` - audit trail (planned enhancement)

#### 4. **Stress Harness** (`crt_stress_test.py`)
- API-mode testing via `POST /api/chat/send`
- M2 followup automation (now instrumented)
- Generates JSONL logs + markdown reports
- Supports `--m2-smoke`, `--m2-followup`, `--m2-followup-verbose`

#### 5. **Report Builder** (`artifacts/build_crt_stress_report.py`)
- Parses JSONL stress run logs
- Generates markdown reports with:
  - Header metrics (turns, gates, contradictions, M2 followups)
  - Per-turn details with learned vs heuristic A/B comparison
  - M2 HTTP step diagnostics

---

## Milestone Status

### ✅ M0: Constitution + Invariants
**Status:** COMPLETE
- Constitution documented
- Core invariants enforced (no silent overwrite, provenance required)
- Questions don't become USER memories

### ✅ M1: Honesty Regression Suite
**Status:** COMPLETE
- Multi-turn stress harness operational
- Deterministic gates with regression tests
- Scenario coverage: identity drift, corrections, memory recall

### 🟡 M2: Contradictions Become Goals
**Status:** IMPLEMENTED, HARDENING IN PROGRESS
- ✅ End-to-end API implementation (`/next`, `/asked`, `/respond`)
- ✅ Frontend dashboard panel
- ✅ Stress harness M2 automation (now observable)
- ⚠️ Success rate needs improvement (currently 12%)
- ⚠️ Gate pass rate needs analysis (currently 33%)

**Acceptance Criteria Progress:**
- ✅ Contradiction count stabilizes (5 detected in 100-turn run)
- ⚠️ System asks targeted questions (working but needs tuning)
- ⚠️ No vagueness regression (needs measurement)

### 🔜 M3: Research Mode with Provenance
**Status:** NOT STARTED
- Planned: search → fetch → quote → summarize with citations
- Tool outputs as TOOL/external memories
- Evidence packets in UI

### 🔜 M4: Background Task Agent
**Status:** INFRASTRUCTURE COMPLETE, AUTONOMY NOT IMPLEMENTED
- ✅ SQLite jobs queue + worker loop
- ✅ Job events/artifacts logging
- ✅ Jobs UI page
- ⚠️ Permission tier system planned but not enforced
- ⚠️ Scheduler for opt-in periodic tasks exists but underutilized

---

## Key Metrics from Latest Run

**File:** `crt_stress_report.20260115_200540.md`

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Turns Completed | 100 | 100 | ✅ |
| Gate Pass Rate | 33% | >80% | ❌ |
| Contradictions Detected | 5 | <10 | ✅ |
| M2 Followup Success | 12% (3/25) | >80% | ❌ |
| Avg Confidence | 0.705 | >0.7 | ✅ |
| Learned/Heuristic Agreement | 100% | >90% | ✅ |

### Gate Analysis Needed
- 67% gate failure rate is concerning
- Need to identify which specific gates are failing
- Possible causes:
  - Overly strict heuristics
  - Legitimate failures (model hallucinations)
  - Test scenario design issues

### M2 Followup Analysis
- 22/25 failures (88%) need investigation
- Possible issues:
  - Schema mismatches between harness and API
  - Thread ID synchronization problems
  - Timing issues (contradiction not yet in ledger)
  - API endpoint validation errors

---

## Immediate Next Steps (Priority Order)

### 🔥 Critical (Do First)

1. **Analyze Gate Failures**
   - Run: Extract which specific gates are failing from JSONL
   - Determine: Are these true failures or false positives?
   - Action: Tune gate thresholds or fix model behavior

2. **Debug M2 Followup 88% Failure Rate**
   - Run smoke test against correct API: `python crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --thread-id m2_smoke --m2-smoke --m2-followup-verbose`
   - Review failed M2 step details in latest JSONL
   - Check schema alignment between stress harness and API endpoints
   - Verify thread_id propagation in followup calls

3. **Validate API Self-Check**
   - Start fresh API instance on `:8123`
   - Run smoke test and confirm self-check passes
   - Document expected behavior for CI/CD

### 🎯 High Priority (This Week)

4. **Run 300-Turn Baseline**
   - After fixing M2 followups, run full 300-turn stress test
   - Compare to `crt_stress_report.20260115_093355.md` baseline
   - Target: M2 success >50%, gate pass >60%

5. **Gate Threshold Tuning**
   - Based on gate analysis, adjust thresholds in `crt_core.py`
   - Current: theta_contra=0.42, theta_mem=0.37
   - Run A/B test with adjusted values

6. **Contradiction Classification Hardening**
   - Complete partially-implemented contradiction type system
   - See: `CRT_IMPLEMENTATION_STATUS.md` steps 1-5
   - Add: REFINEMENT, REVISION, TEMPORAL, CONFLICT types
   - Test: Verify only CONFLICT degrades trust

### 📊 Medium Priority (Next 2 Weeks)

7. **Multi-Run Statistical Analysis**
   - Create batch runner (N seeds, same config)
   - Aggregate metrics: mean/std for pass rates, contradictions
   - Document variance and identify flaky tests

8. **Learned Model Publishing Pipeline**
   - Implement: train → eval → publish with thresholds
   - Add: `crt_learn_publish.py` integration with control panel
   - Artifacts: promotion proposals + decisions + audit trail

9. **Background Jobs Permission System**
   - Define: Tier 0 (read-only), Tier 1 (safe writes), Tier 2 (tools)
   - Enforce: Permission checks in worker loop
   - UI: Job request approval queue

10. **Audit Answer Record**
    - Create: `crt_audit.db` with answers table
    - Write: Every API chat response with retrieval IDs
    - UI: "Why did you say that?" inspector

### 🔮 Future Work (M3+)

11. **Evidence Packets (M3)**
    - Tool chain: search → fetch → quote → summarize
    - Storage: TOOL memories with provenance
    - UI: Citation inspector

12. **Frontend Polish**
    - Mobile responsive design
    - Real-time contradiction notifications
    - Batch memory operations (bulk approve/reject)

13. **Multi-Model Support**
    - Configuration: Model selection in UI
    - Testing: Stress harness across Ollama/OpenAI/Anthropic
    - Metrics: Per-model comparison dashboard

---

## Known Issues & Technical Debt

### High Priority
- [ ] M2 followup 88% failure rate (blocking M2 completion)
- [ ] Gate pass rate 33% (blocking confidence in system)
- [ ] API self-check needs validation on clean server start

### Medium Priority
- [ ] Contradiction classification incomplete (see `CRT_IMPLEMENTATION_STATUS.md`)
- [ ] Learned model publishing not gated by thresholds
- [ ] Background job permission system not enforced
- [ ] No audit trail for API chat responses

### Low Priority
- [ ] Frontend needs mobile optimization
- [ ] No multi-model configuration UI
- [ ] Stress harness doesn't support parallel runs
- [ ] Report aggregation for batch runs not implemented

---

## Development Environment Notes

### Platform Differences
- **Windows (D:\AI_round2):** Primary development, tasks configured for Windows paths
- **macOS (/Users/nickblock/Documents/AI_round2):** Current assessment location
- **Issue:** Task definitions in `.vscode/tasks.json` use Windows paths (`D:/`)

### Running the System

#### Start API Server
```bash
# Windows
D:\AI_round2\.venv\Scripts\python.exe -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123

# macOS (adjust path)
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123
```

#### Start Frontend
```bash
cd frontend
npm run dev
# Typically runs on :5173
```

#### Run M2 Smoke Test
```bash
# Windows
py -3 crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --thread-id m2_smoke --m2-smoke --m2-followup-verbose

# macOS
python3 crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --thread-id m2_smoke --m2-smoke --m2-followup-verbose
```

#### Run 100-Turn Stress Test
```bash
python3 crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --thread-id stress_100 --reset-thread --turns 100 --sleep 0.02 --m2-followup --m2-followup-max 25 --print-every 25
```

#### Generate Report
```bash
python3 artifacts/build_crt_stress_report.py
```

---

## Critical Files Reference

### Core Engine
- `crt_core.py` - Main CRT engine with truth gates
- `crt_rag.py` - Retrieval & uncertainty handling
- `crt_ledger.py` - Contradiction tracking (needs completion)
- `crt_chat.py` - Conversation loop logic

### API & Frontend
- `crt_api.py` - FastAPI backend
- `frontend/` - React UI

### Testing & Evaluation
- `crt_stress_test.py` - Stress harness (recently enhanced)
- `artifacts/build_crt_stress_report.py` - Report generator
- `conftest.py` - Pytest configuration
- `tests/` - Regression test suite

### Documentation
- `HANDOFF_SAVE_2026-01-15.md` - Latest handoff with next steps
- `CRT_MASTER_FOCUS_ROADMAP.md` - Overall project roadmap
- `CRT_IMPLEMENTATION_STATUS.md` - Current implementation tasks
- `CRT_COMPANION_ROADMAP.md` - Milestone definitions
- `CRT_CONTROL_PANEL_ROADMAP.md` - Control plane architecture

### Configuration
- `crt_runtime_config.json` - Runtime toggles & templates
- `AI_round2.code-workspace` - VS Code workspace settings

---

## Success Criteria for M2 Completion

Before moving to M3, the following must be true:

1. **M2 Smoke Test:** 100% pass rate (currently: needs validation)
2. **M2 Followup Success:** >80% in 100-turn runs (currently: 12%)
3. **Gate Pass Rate:** >80% (currently: 33%)
4. **Contradiction Stability:** <10 in 100-turn runs (currently: 5 ✅)
5. **300-Turn Run:** Successfully completes with metrics comparable to 100-turn baseline
6. **Learned Model Publishing:** Gated by eval thresholds
7. **Audit Trail:** Every API response logged with retrieval context

---

## Recommended Immediate Action Plan

**For next 24-48 hours:**

1. ✅ **This assessment document created**
2. ⏭️ **Fix environment setup** - Adapt task paths for macOS or test on Windows
3. ⏭️ **Start API server** - Verify clean startup on `:8123`
4. ⏭️ **Run M2 smoke test** - Confirm self-check + full cycle works
5. ⏭️ **Analyze latest JSONL** - Extract gate failure patterns
6. ⏭️ **Review M2 followup failures** - Identify schema/timing issues
7. ⏭️ **Quick fixes** - Address top 1-2 blockers
8. ⏭️ **Re-run 100-turn test** - Measure improvement
9. ⏭️ **Update roadmap** - Document findings and next priorities

**Stop condition:** M2 smoke test green + followup success >50% + clear path to 80%

---

## Questions for Stakeholder/Lead

1. **Priority:** Should we focus on M2 hardening or move to M3 research mode?
2. **Gate Failures:** Are 67% failures acceptable if they're catching real issues?
3. **Platform:** Should we standardize on Windows or macOS for development?
4. **Deployment:** Any timeline for moving from local-first to hosted/product?
5. **Model Strategy:** Stick with single model or prioritize multi-model support?

---

**End of Assessment**  
*Next update: After M2 smoke test validation and gate analysis*
