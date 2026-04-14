---
name: Session 2026-04-13 Mac Test + Modularization
description: Mac Electron test log assessment + crt_rag.py Phase 4 modularization completed
type: session
---

## Mac Electron Test (M2, local-only, llama3.2)

**Setup**: Electron app on Mac, repo at `/Volumes/ex_video/ai/CRT-GroundCheck-SSE`, Python 3.13, Ollama with 6 models, cloud disabled (`cloud_to_local → local_only`).

**Startup**: Clean. Embedding model loaded (384d), NLI model loaded, 24 shared memories, BDG 21 nodes. SSH key added for remote access.

**Missing packages on Mac**: `ripser` (belief classifier init failed), `curl_cffi` (CookieProvider unavailable). Non-blocking — belief classifier degrades gracefully, cloud falls back to OpenAI key.

**Deprecation warnings**: `duckduckgo_search` renamed to `ddgs`, FastAPI `on_event` → lifespan handlers, `datetime.utcnow()` → `datetime.now(UTC)`. Non-blocking.

**Behavioral issues observed across 6 test queries:**

### 1. Web search tool failures (Q: "What is the basic algorithm that makes an llm work?")
- Agent loop burns 4 iterations: `web_search` fails 3x, `gpt_log_search` fails 1x
- All marked `[VERIFY] unexpected_failure`
- Coherence guard fires at iter 4, forces answer
- Root cause: web_search tool likely failing silently (DuckDuckGo rename?)
- Model falls back to knowledge-based answer — adequate but not great

### 2. Orchestrator over-planning (Q: "Can you describe how you work?")
- Routes correctly to orchestrator (broad_recall, layer4)
- 5 iterations: introspect(all), think, plan, system_info(REJECTED — not in tool gate), gpt_log_context(error)
- 80% surprise rate on tool verification
- Answer is shallow: "I am a decision-making API" — misses the CRT/memory architecture
- 21.3s total brain time for a mediocre answer

### 3. Iteration budget exhaustion (Q: "What components make you remember?")
- Good retrieval (top hits: embedding description, GroundCheck, local Ollama)
- Model wastes iterations: plan → introspect(all) → introspect(execution_beliefs) → think → introspect(components_memory) → think → FORCE_RESPOND
- Ran out at iter 5/5 after adaptive depth limited it
- Answer admits "I ran out of iteration budget" — bad UX

### 4. Name ingestion failure + fidelity mirror (Q: "My name is Nick")
- Intent routed as broad_recall instead of personal_fact/name_declaration
- Memory recall for "Nick" returns 0 relevant hits (shared DB has no user facts yet)
- Model plans twice, then JSON parse fails on iteration 2/5
- Fidelity mirror FAILS (composite=0.029) — correct enforcement, raw JSON leaked to user
- **Bug**: `_is_user_name_declaration` didn't trigger — intent router classified as broad_recall

### 5. Coherence guard repeat (Q: "How do you work?")
- Classified as self_referential (regex, 0.95 confidence)
- Agent loop calls `memory_recall("how I work")` 3x identically
- Coherence guard forces answer at iter 4
- **This is the known coherence guard bug** — model loops on same tool call

### 6. Correct enforcement (Q: "What is my biggest weakness?")
- Conversational route, legacy pipeline path
- No memories about user weakness → 0 retrieval results
- BDG shape mismatch error: `shapes (384,) and (8,) not aligned` — non-blocking but logged
- Fidelity mirror correctly FAILS (composite=0.184), hedges response
- **Fidelity enforcement working as designed**

### Resource leak
- Massive sqlite3 ResourceWarning spam throughout — unclosed database connections in numpy arrayprint
- Not causing failures but filling logs. Connections created in retrieval scoring but not closed.

### Assessment Summary
| Area | Status |
|------|--------|
| Startup/init | ✅ Clean, all subsystems load |
| Embedding + NLI | ✅ Working |
| Retrieval | ✅ Working, scores reasonable |
| Orchestrator routing | ⚠️ Over-plans, wastes iterations |
| Agent loop coherence | ❌ Known bug — repeats identical tool calls |
| Name ingestion | ❌ Intent misroute (broad_recall vs name_declaration) |
| Web search | ❌ Tool failures (ddgs rename?) |
| Fidelity mirror | ✅ Correctly catching ungrounded responses |
| Memory leak | ⚠️ sqlite3 connections not closed |
| Overall UX | ⚠️ Functional but rough — loops, JSON leaks, shallow answers |

**Key Mac-specific issues**: `ripser` and `curl_cffi` not installed. Everything else is codebase-level, not platform-specific.

## Modularization Status (Phase 4 — crt_rag split)

`personal_agent/crt_rag.py` (10,075 lines) → `personal_agent/crt_rag/` package (12 files, 11,521 lines):

| Module | Lines | Scope |
|--------|-------|-------|
| `_engine.py` | 4,062 | Class + __init__/query()/dispatchers |
| `_contradiction.py` | 2,417 | Detection + resolution |
| `_answer_gen.py` | 1,217 | Slot answers, variation |
| `_citation.py` | 760 | Memory citation, inventory |
| `_fact_extraction.py` | 755 | Fact extraction, slot inference |
| `_memory_ops.py` | 729 | Ingestion, profile, retrieval |
| `_web_search.py` | 495 | Web search, copilot |
| `_classification.py` | 483 | Query classification |
| `_security.py` | 347 | Gaslighting/denial detection |
| `_sanitization.py` | 165 | Memory sanitization |
| `_tracing.py` | 67 | Trace/debug |
| `__init__.py` | 24 | Package exports |

All AST-verified. Backup at `crt_rag_old.py`. Needs production test on Windows (Mac test was pre-split code).

**Prior phases complete**: trust/, contradiction/, belief/, memory_subsystem/ subpackages + routes/chat/ package split.

## Top 10 Math Labs — ALL PASS (10/10)

File: `docs/labs/top10_math_labs.py` — runs in <1 second, pure numpy.

| Lab | Name | Key Result |
|-----|------|------------|
| 1 | Learnable gain/decay | vol_d dampens gain, amplifies decay. Name earns trust faster than mood. |
| 2 | Beta distribution trust | Same trust (0.7) but 4.9x variance difference. New memory 5x more affected by contradiction. |
| 3 | Unified gate equation | Single equation collapses 3 separate gates. Drift raises threshold, depth attenuates. |
| 4 | Typed-edge damping | SUPERSEDES propagates 70% stronger than flat. SUPPORTS 40% weaker. |
| 5 | Continuous disposition | 4D simplex correctly drifts: both_reinforced→held, clarified→resolve, shift→evolve, idle→dormant. |
| 6 | Contraction mapping | avg α=0.885 < 1. Distance reduced 93.8% in 20 steps. Banach condition satisfied. |
| 7 | Marble stability | No firewalls: marble GROWS (+46%). With firewalls: marble SHRINKS. 1 firewall sufficient. |
| 8 | Cascade size bound | 15% firewalls reduce cascade 31%. 30% reduce to 45% of baseline. Monotonic. |
| 9 | Salience gate convergence | Loss halved in 1 epoch. 99.7% reduction in 50 epochs. Monotonically decreasing. |
| 10 | CRT attention | Trust gating: high-trust avg attn 0.197 vs low-trust 0.017 (12x). Entropy lower (more focused). |

## CRT Math Upgrades — ALL 5 SHIPPED

All 5 top-ROI math upgrades from Grok review implemented in production code with `[CRT_MATH]` console logging throughout. All backward-compatible (defaults match old behavior).

| # | Upgrade | Files | What It Does |
|---|---------|-------|-------------|
| 1 | Learnable Gain/Decay | `crt_core.py`, `trust/decay.py`, `volatility_context.py` | Trust evolution scales by domain volatility. Names gain trust fast, opinions slow. |
| 2 | Beta Distribution Trust | `crt_core.py`, `crt_memory.py` | Replace scalar trust with Beta(α,β). Variance = uncertainty. Conjugate Bayesian updates. Schema: `trust_alpha`, `trust_beta` columns. |
| 3 | Unified Gate Equation | `crt_core.py`, `crt_rag/_engine.py` | `gate(v) = I(R > θ+λ*drift) * exp(-γ*depth)`. Collapses 3 gates. Added as supplementary signal at 3 call sites. |
| 4 | Typed-Edge Damping | `memory_subsystem/graph.py`, `crt_rag/_contradiction.py` | SUPERSEDES=0.85, CONTRADICTS=0.60, SUPPORTS=0.30 instead of flat CASCADE_TRUST_FACTOR. |
| 5 | Continuous Disposition | `disposition_classifier.py`, `crt_ledger.py` | 4D simplex [resolve,hold,evolve,dormant] replaces discrete enum. Schema: 4 float columns. |

**New additions to crt_core.py**: `BetaTrust` dataclass, `CRTMath.unified_gate()`, `CRTConfig.vol_beta/vol_gamma/gate_*` params. **New in volatility_context.py**: `get_domain_volatility()` with `_DOMAIN_VOLATILITY_DEFAULTS` dict. **New in disposition_classifier.py**: `DispositionSimplex` dataclass with `update()` method + `_attach_simplex()` wrapper.

**Verification**: 10/10 math labs pass. All smoke tests pass. Full `[CRT_MATH]` logging confirmed.

## Wednesday plan: TPU governance proof
- Prove governance > standard RAG on TPU (v4 or v6e)
- Use labs as validation suite
- Benchmark: naked 3B vs 3B+CRT on FEVER or equivalent

## Next session priorities
- Production test modularized crt_rag on Windows (user will run app)
- Production test math upgrades (grep `[CRT_MATH]` in console)
- Fix coherence guard bug (agent loop identical tool calls)
- Fix name declaration intent misroute
- TPU benchmark setup
