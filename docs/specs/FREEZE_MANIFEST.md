# CRT v0.9.0 — Development Freeze Manifest

**Frozen:** February 8, 2026  
**Author:** Nick Block  
**Branch:** `main`  
**Status:** SPEC FREEZE — no feature development until specs are reviewed and accepted

---

## Freeze Declaration

Development is frozen at v0.9.0. This manifest captures the exact state of every critical file in the system. All four specification documents are canonical:

| Document | Path | Purpose |
|----------|------|---------|
| Architecture Spec | `docs/specs/ARCHITECTURE.md` | System structure, data flow, invariants |
| API Contract | `docs/specs/API_CONTRACT.md` | 94 endpoints, models, error codes |
| Innovation Pillars | `docs/specs/INNOVATION_PILLARS.md` | What CRT does that nothing else does |
| Freeze Manifest | `docs/specs/FREEZE_MANIFEST.md` | This document — file hashes, counts, state |

---

## System Metrics at Freeze

| Metric | Value |
|--------|-------|
| Package version | 0.9.0 |
| Python | ≥ 3.10 (developed on 3.13.2) |
| API endpoints | 94 application + 5 framework = 99 total |
| Route modules | 10 (auth, chat, memory, contradictions, learning, jobs, threads, scheduled_tasks, agent, misc) |
| Pydantic models | 67 shared + heartbeat models |
| Test files | 72 |
| JSON schemas | 7 |
| GroundCheck mean latency | 1.17ms |
| GroundCheck p95 latency | 2.09ms |
| Adversarial pass rate | 84/84 (100%) |
| DNNT target params | 2-20M |
| DNNT target inference | <200ms CPU |

---

## Roadmap Status at Freeze

| Phase | Description | Status |
|-------|-------------|--------|
| 0.1 | Dead code removal + DB centralization | ✅ COMPLETE |
| 0.2 | Exception hierarchy + error handling | ✅ COMPLETE |
| 0.3 | Route modularization (94 endpoints extracted) | ✅ COMPLETE |
| 0.4 | Engine package (anchors, resonance, reconstruction, degradation, collapse trails) | ✅ COMPLETE |
| 0.5 | DNNT integration points wired | ✅ COMPLETE |
| 1.1 | DNNT rename + triple-loss heads + dynamic vocab + red_penalty | ✅ COMPLETE |
| 1.2 | SentencePiece BPE backend | 🔶 IN PROGRESS |
| 1.3 | Trust-gated training + background learning + hot-reload | 🔶 IN PROGRESS |
| 1.4 | DNNT-first inference with confidence-gated LLM fallback | 🔶 IN PROGRESS |
| 2-5 | Advanced features (CogniMap, adaptive calibration, etc.) | ⬜ NOT STARTED |

---

## File Manifest

### Gateway
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `crt_api.py` | 1,250 | `6ea475ffbc085e68` |

### Routes
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `routes/__init__.py` | 6 | `1525f872ad973bf5` |
| `routes/register.py` | 28 | `e0ea7d4a8708e932` |
| `routes/models.py` | 647 | `9e2fd256191b33f2` |
| `routes/deps.py` | 94 | `e43130b39eb1f652` |
| `routes/auth.py` | 159 | `27caae84cefbd58d` |
| `routes/chat.py` | 1,701 | `f75a4bdb59d015c1` |
| `routes/memory.py` | 414 | `cbaca04a14364e12` |
| `routes/contradictions.py` | 586 | `e05481e7124a6907` |
| `routes/learning.py` | 255 | `e6477fe14f57a1db` |
| `routes/jobs.py` | 141 | `6be57f0fe15a54a8` |
| `routes/threads.py` | 387 | `733c7ff4e8a274f5` |
| `routes/scheduled_tasks.py` | 291 | `718309a6804536f3` |
| `routes/agent.py` | 186 | `adb9271392e9a7f9` |
| `routes/misc.py` | 1,145 | `0ee5682607d412b2` |

### CRT Core (personal_agent/)
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `personal_agent/crt_core.py` | 1,216 | `884b95702ce93c1d` |
| `personal_agent/crt_memory.py` | 1,527 | `6c4e6db74c24aeaa` |
| `personal_agent/crt_ledger.py` | 1,268 | `b6de715041f092e6` |
| `personal_agent/crt_rag.py` | 6,704 | `fe4c56c84655553d` |
| `personal_agent/two_tier_facts.py` | 374 | `002ddec705df89ba` |
| `personal_agent/intent_router.py` | 319 | `c6f357041e12accd` |
| `personal_agent/reasoning.py` | 1,079 | `9e9a16e2e0488057` |
| `personal_agent/reflection_system.py` | 580 | `aecc922604d82237` |
| `personal_agent/episodic_memory.py` | 1,658 | `f37d81d738027ee9` |
| `personal_agent/heartbeat_system.py` | 563 | `53ca19de9f4e083c` |
| `personal_agent/thinking_loop.py` | 430 | `55998a2ec041cff7` |
| `personal_agent/continuous_loops.py` | 1,024 | `67005a3aa67b70d5` |
| `personal_agent/training_loop.py` | 255 | `708bf5d85eace688` |
| `personal_agent/active_learning.py` | 1,066 | `36d2e7fd98e3e831` |
| `personal_agent/agent_loop.py` | 700 | `cff8bcf929357332` |
| `personal_agent/disclosure_policy.py` | 367 | `f2ad5a2d022e909c` |
| `personal_agent/ml_contradiction_detector.py` | 678 | `cb16a86e446ef14c` |
| `personal_agent/llm_drift_assessor.py` | 260 | `14adbd3529c95f6d` |

### DNNT Neural Core
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `personal_agent/dnnt/model.py` | 552 | `d50070c75e3b0249` |
| `personal_agent/dnnt/inference.py` | 552 | `b6e22ad4896c1d97` |
| `personal_agent/dnnt/trust_gate.py` | 66 | `b23c3f78a500ecfd` |
| `personal_agent/dnnt/background_learning.py` | 507 | `557251a08da4c3a3` |
| `personal_agent/dnnt/tokenizer_bpe.py` | 342 | `ae6ea742d928a6bd` |

### Engine Integration Hooks
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `personal_agent/engine/anchors.py` | 58 | `b2104ab3add2eb3f` |
| `personal_agent/engine/resonance.py` | 68 | `5b619e1d31921b86` |
| `personal_agent/engine/reconstruction.py` | 76 | `d95a3f3d2f77977f` |
| `personal_agent/engine/degradation.py` | 82 | `8d5accb0912fca6b` |
| `personal_agent/engine/collapse_trails.py` | 142 | `b0673f7effb2d56f` |

### GroundCheck
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `groundcheck/groundcheck/verifier.py` | 961 | `0bb242a1193db4b4` |
| `groundcheck/groundcheck/fact_extractor.py` | 588 | `b113d4dd893c6f07` |
| `groundcheck/groundcheck/semantic_matcher.py` | 187 | `b5a6f8d1bd35d49e` |
| `groundcheck/groundcheck/semantic_contradiction.py` | 114 | `271097ec0cc8d796` |
| `groundcheck/groundcheck/neural_extractor.py` | 163 | `d289dcdde0964eaf` |
| `groundcheck/groundcheck/tuple_verifier.py` | 387 | `2ec4ed1d3743484e` |

### SSE (Semantic String Engine)
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `sse/client.py` | 498 | `3c205d29c52451fa` |
| `sse/interaction_layer.py` | 751 | `68731b1744524349` |
| `sse/coherence.py` | 540 | `601cd7c0f8677bb9` |
| `sse/extractor.py` | 330 | `88d4aae608589e9f` |
| `sse/contradictions.py` | 225 | `0e93c66b21ebfbc0` |

### Config & Test Infrastructure
| File | Lines | SHA-256 (16) |
|------|-------|-------------|
| `conftest.py` | 55 | `567b973e6a34f7b3` |
| `pyproject.toml` | 78 | `55f11f063b4ba88d` |

---

## Total Line Count (Critical Files)

| Subsystem | Lines |
|-----------|-------|
| Gateway (`crt_api.py`) | 1,250 |
| Routes (14 files) | 5,980 |
| CRT Core (18 files) | 16,489 |
| DNNT (5 files) | 2,019 |
| Engine Hooks (5 files) | 426 |
| GroundCheck (6 files) | 2,400 |
| SSE (5 files) | 2,344 |
| **Total** | **30,908** |

---

## Acceptance Criteria for Unfreeze

Development may resume only when:

1. All four spec documents have been reviewed
2. Any corrections to specs are committed
3. The test suite passes clean (597 items as of last full run)
4. No spec-violating changes are in the working tree

---

*This manifest is the authoritative record of the codebase state at v0.9.0 freeze.*
