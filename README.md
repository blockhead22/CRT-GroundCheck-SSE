# CRT v0.9-beta - Contradiction-Preserving Memory

**Memory governance for conversational AI that never lies about uncertainty.**

CRT implements reintroduction invariant enforcement: contradicted memories MUST be flagged in data and disclosed in language. When the system uses conflicting information, you see it—always.

---

## 🎯 What Makes CRT Different

### The Invariant
**If a memory has an open contradiction, the system MUST NOT present it as unqualified truth.**

- **Data Layer:** Every contradicted memory carries `reintroduced_claim: true` flag
- **Language Layer:** Answers using contradicted claims include inline caveats
- **Zero Tolerance:** Unflagged contradictions = 0, Uncaveated assertions = 0

### Core Principles
- **Contradictions Are Information** - Never silently overwrite conflicting facts
- **Explicit Disclosure** - "Amazon (most recent update)" when Microsoft/Amazon conflict exists
- **Evidence-First** - Every claim traceable to source memory with trust scores
- **X-Ray Transparency** - See which memories built each answer, which are contradicted
- **Two-Lane Memory** - BELIEF (high-trust facts) vs SPEECH (conversational fallback)

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- **Python 3.10+**
- **Ollama** (for natural language responses)
  ```bash
  # Install: https://ollama.com/download
  ollama pull llama3.2:latest
  ollama serve
  ```
- **Node.js 18+** (for web UI, optional)

### Installation

```bash
# 1. Clone and setup Python
cd d:\AI_round2
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

# 2. Start API server
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123
# Wait for: "Uvicorn running on http://127.0.0.1:8123"
```

### Quick Demo (2 Minutes)

```powershell
# Create contradiction
$thread = "quick_demo"
$api = "http://127.0.0.1:8123/api/chat/send"

$b1 = @{thread_id=$thread; message="I work at Microsoft."} | ConvertTo-Json
Invoke-RestMethod -Uri $api -Method POST -Body $b1 -ContentType "application/json"

$b2 = @{thread_id=$thread; message="Actually, I work at Amazon, not Microsoft."} | ConvertTo-Json
Invoke-RestMethod -Uri $api -Method POST -Body $b2 -ContentType "application/json"

# Recall contradicted fact
$b3 = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r = Invoke-RestMethod -Uri $api -Method POST -Body $b3 -ContentType "application/json"

Write-Host "Answer: $($r.answer)"
# Expected: "Amazon (most recent update)"
Write-Host "Contradicted claims: $($r.metadata.reintroduced_claims_count)"
# Expected: 2
```

**✅ Success:** Answer includes caveat, count = 2, both memories flagged

---

## 📖 Documentation

### Start Here
- **[BETA_STARTER_KIT.md](BETA_STARTER_KIT.md)** - Beta tester guide with 5-minute demo
- **[QUICKSTART.md](QUICKSTART.md)** - Detailed installation + setup
- **[DEMO_5_TURN.md](DEMO_5_TURN.md)** - Quick contradiction demonstration

### Technical Specs
- **[CRT_REINTRODUCTION_INVARIANT.md](CRT_REINTRODUCTION_INVARIANT.md)** - Complete invariant specification
- **[BETA_RELEASE_NOTES.md](BETA_RELEASE_NOTES.md)** - v0.9-beta changelog
- **[CRT_WHITEPAPER.md](CRT_WHITEPAPER.md)** - Architecture deep dive

### Validation
- **[BETA_READINESS_SUMMARY.md](BETA_READINESS_SUMMARY.md)** - Smoke test results
- **[BETA_VERIFICATION_CHECKLIST.md](BETA_VERIFICATION_CHECKLIST.md)** - 10-minute validation script
- **Proof Artifact:** `artifacts/crt_stress_run.20260121_162816.jsonl` (0 violations)

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend UI   │  React + TypeScript
│                 │  Visual indicators for contradicted claims
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────────────────────────┐
│   FastAPI Server (crt_api.py)      │
│                                     │
│   ┌──────────────────────────┐     │
│   │ Reintroduction Enforcer  │     │  ← v0.9-beta
│   │ (API serialization)      │     │
│   └──────────────────────────┘     │
└────────┬────────────────────────────┘
         │
    ┌────▼─────────────────┐
    │ CRT Core (crt_rag.py)│
    │ - Truth coherence    │
    │ - Inline caveats     │
    └────┬─────────────────┘
         │
    ┌────┴─────────┬──────────────┬─────────────┐
    │              │              │             │
┌───▼────┐   ┌────▼─────────┐  ┌─▼──────┐  ┌──▼─────┐
│Memory  │   │Contradiction │  │Research│  │  Jobs  │
│System  │   │   Ledger     │  │ Engine │  │ Worker │
└────────┘   └──────────────┘  └────────┘  └────────┘
  (SQLite)      (SQLite)         (Hybrid)   (Background)
```

### Data Flow: Contradiction Handling

```
1. User: "I work at Microsoft"
   → Memory stored, trust=0.7

2. User: "Actually, I work at Amazon"
   → Contradiction detected
   → Ledger entry: Microsoft vs Amazon (status=open)
   → Both memories preserved

3. User: "Where do I work?"
   → Query retrieves both memories
   → API calls ledger.has_open_contradiction(memory_id)
   → Sets reintroduced_claim=true on both
   → Truth coherence adds caveat: "(most recent update)"
   → Response: "Amazon (most recent update)"
   → metadata.reintroduced_claims_count = 2
```

---

## 📂 Project Structure

```
/crt_api.py                    # FastAPI server (version 0.9-beta)
/personal_agent/
  ├── crt_rag.py               # Core retrieval + truth coherence
  ├── crt_memory.py            # Memory storage & retrieval
  ├── crt_ledger.py            # Contradiction tracking
  └── research_engine.py       # External knowledge integration
/frontend/                     # React web interface
  └── src/components/chat/
      └── MessageBubble.tsx    # Visual contradiction indicators
/tools/
  └── crt_stress_test.py       # Automated validation (15-30 turns)
/tests/                        # Pytest test suite
/artifacts/                    # Stress test reports & proof artifacts
/docs/                         # Additional documentation

Key Files:
- CRT_REINTRODUCTION_INVARIANT.md   # Invariant specification
- BETA_STARTER_KIT.md               # Tester onboarding guide
- DEMO_5_TURN.md                    # Quick demonstration script
```

---

## 🧪 Testing & Validation

### Smoke Test (2 minutes)
```bash
# See BETA_VERIFICATION_CHECKLIST.md for copy-paste script
# Tests: Memory → Contradiction → Recall → Flags
```

### Stress Test (15 turns)
```bash
python tools/crt_stress_test.py \
  --use-api \
  --api-base-url http://127.0.0.1:8123 \
  --thread-id test_run \
  --reset-thread \
  --turns 15 \
  --sleep 0.05

# Expected output:
# REINTRODUCTION INVARIANT (v0.9-beta):
#   Flagged (audited): N
#   Unflagged (violations): 0
#   Asserted without caveat (violations): 0
#   ✅ INVARIANT MAINTAINED
```

### Unit Tests
```bash
pytest tests/ -v
```

---

## 📊 Current Status

**Version:** v0.9-beta  
**Released:** January 21, 2026  
**Status:** Controlled beta (5 testers)

### ✅ What's Working
- **Reintroduction invariant enforcement** (0 violations in stress tests)
- API-layer flag enforcement (`reintroduced_claim` field on all memories)
- Truth coherence disclosure (inline caveats in answers)
- X-Ray transparency (memory provenance + contradiction flags)
- Visual UI indicators (badges for contradicted claims)
- Two-lane memory (BELIEF/SPEECH separation)
- Contradiction detection & tracking

### ⚠️ Known Limitations
1. **Caveat detection:** Keyword-based ("most recent", "latest", etc.)
   - Can be gamed with careful phrasing
   - Acceptable for beta, upgrade to semantic later

2. **Ollama dependency:** Requires local LLM for natural answers
   - Graceful degradation: Returns error messages without Ollama
   - Memory/flags still work, just no natural language

3. **UI hover preview:** Planned but not yet implemented
   - Feature: Show alternative answer if different memory was used
   - Design approved, implementation post-beta

### 🗺️ Roadmap
- **Post-beta improvements:**
  - Semantic caveat detection (upgrade from keywords)
  - No-LLM demo mode (testing without Ollama)
  - UI hover preview (context fork visualization)
  - Wider beta (10-20 testers)

- **Future milestones:**
  - M3: Evidence packets (web research with citations)
  - M4: Permissions (tiered background task safety)
  - M5: Learning polish (user-facing controls)

---

## 🤝 Beta Testing

**Current phase:** Controlled beta with 5 initial testers

### How to Participate
1. Read [BETA_STARTER_KIT.md](BETA_STARTER_KIT.md)
2. Follow [QUICKSTART.md](QUICKSTART.md) for setup
3. Run [BETA_VERIFICATION_CHECKLIST.md](BETA_VERIFICATION_CHECKLIST.md) (10 minutes)
4. Report results using bug template

### Success Criteria
```
✅ Contradiction detection works
✅ Reintroduced_claim flags appear in data
✅ Answer includes caveat when using contradicted claims
✅ X-Ray mode shows flagged memories
✅ Count accuracy: metadata == xray == actual
```

---

## 📄 License

[Add your license here]

---

**Built with:** Python 3.10+, FastAPI, React, SQLite, Ollama, sentence-transformers  
**Philosophy:** Uncertainty-honest AI that preserves contradictions instead of hiding them

## 📂 Project Structure

```
/crt_api.py              # FastAPI server (production entry point)
/personal_agent/         # Core library modules
  ├── crt_rag.py         # Main CRT retrieval logic
  ├── crt_memory.py      # Memory storage & retrieval
  ├── crt_ledger.py      # Contradiction tracking
  ├── research_engine.py # External knowledge integration
  └── jobs_worker.py     # Background task processor
/frontend/               # React web interface
/tests/                  # Pytest test suite
/docs/                   # Additional documentation
/artifacts/              # Stress test reports & analysis
```


## 🧪 Testing

```bash
# Run test suite
pytest

# Run specific test
pytest tests/test_crt_conversation.py -v

# Stress test (100 turns)
python crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --turns 100
```

## 📊 Current Status

**Version:** 0.85 (M2 Complete)  
**Last Updated:** January 16, 2026

### What's Working ✅
- Two-lane memory (BELIEF/SPEECH separation)
- Contradiction detection & resolution (M2: 12-33% auto-success)
- FastAPI backend + React frontend
- Background jobs system
- Safety gates (preventing hallucinations)
- Multi-turn conversation with memory

### Known Issues ⚠️
- Gate pass rate at 33% (needs tuning - many false positives)
- M2 followup automation at 12% (working but needs improvement)
- Some contradiction classification edge cases

### Roadmap 🗺️
- **M2 Hardening:** Improve gate logic, boost M2 success to 70%+
- **M3 - Evidence Packets:** Web research with citations
- **M4 - Permissions:** Tiered background task safety
- **M5 - Multi-modal:** Image/document understanding

## 🤝 Contributing

This is a research prototype. Core modules are in [personal_agent/](personal_agent/). Tests use pytest. See archived docs in [archive/](archive/) for development history.

## 📄 License

[Add your license here]

---

**Built with:** Python 3.10+, FastAPI, React, SQLite, sentence-transformers
- **M5 - Learning Polish**: User-facing controls for suggestions, export/import

### 📚 Documentation

**Start Here:**
- `CRT_HOW_TO_USE.md` - Quick start guide
- `CRT_MASTER_FOCUS_ROADMAP.md` - Full roadmap + architecture
- `CRT_COMPANION_ROADMAP.md` - Milestone definitions (M0-M5)

**Technical Deep Dives:**
- `CRT_INTEGRATION.md` - Core math framework
- `CRT_QUICK_REFERENCE.md` - API reference
- `CRT_ARTIFACT_SCHEMAS.md` - Data schemas
- `CRT_BACKGROUND_LEARNING.md` - Subconscious worker design
- `BROWSER_BRIDGE_README.md` - Research mode setup

**Architecture Principles:**
- **No hallucination**: If uncertain, express uncertainty or ask
- **Explicit contradictions**: Never auto-resolve conflicts
- **Traceable claims**: Every fact grounded in memory text or citations

## Optional: Local LLM (Ollama)

To enable NLI-based contradiction detection with a local LLM:

1. Install [Ollama](https://ollama.ai)
2. Pull a model (e.g., `ollama pull mistral`)
3. Start Ollama server (default: `http://localhost:11434`)
4. Use flag: `sse compress --input notes.txt --out ./index --use-ollama`

## Testing

```bash
pytest -v
```

All 11 tests pass, covering:
- Chunk offset integrity
- Chunk overlap behavior
- Claim extraction and deduplication
- Ambiguity detection
- Contradiction detection
- Clustering
- Schema validation

## No Remote APIs

By design, SSE-v0 does not depend on remote services. The optional Ollama integration is entirely local.

---

## Phase 6: Interface & Coherence Layer (ICL)

**Status:** Specification Complete (Implementation Pending)

Phase 6 is a **boundary-locking phase**. It defines how external systems can interact with SSE without corrupting it.

### What Phase 6 Delivers

**D1: Interface Contract** ([SSE_INTERFACE_CONTRACT.md](SSE_INTERFACE_CONTRACT.md))
- Formal specification of permitted operations (retrieval, search, filtering, navigation)
- Explicitly forbidden operations (synthesis, truth picking, ambiguity softening, suppression)
- Binding contract; violations raise `SSEBoundaryViolation`

**D2: Read-Only Interaction Layer** (implementation pending)
- Stateless navigator for natural language queries
- Preserves contradictions and ambiguity in all operations
- Enables conversation without decision-making

**D3: Coherence Tracking** ([SSE_COHERENCE_TRACKING.md](SSE_COHERENCE_TRACKING.md))
- Metadata about disagreement: persistence, source alignment, claim recurrence, ambiguity evolution
- Enables users to understand contradiction patterns without resolving them

**D4: Platform Integration Guide** ([SSE_PLATFORM_INTEGRATION.md](SSE_PLATFORM_INTEGRATION.md))
- How to integrate SSE into RAG systems, personal AIs, multi-agent systems, fact-checking pipelines
- Anti-patterns to avoid
- Examples of correct integration

**D5: Test Suite** (implementation pending)
- Verifies query parsing, contradiction preservation, boundary violations
- Ensures Interface Contract is enforced at code review time

### Why Phase 6 Matters

Most systems erode because they add features before locking integrity boundaries.

Phase 6 locks the boundaries **before** building on top. This ensures:
- Contradictions are never hidden
- Synthesis is never performed by SSE
- Ambiguity is never softened
- Provenance is always maintained

### Navigation

- **[PHASE_6_NAVIGATION.md](PHASE_6_NAVIGATION.md)** — Quick links and reading order
- **[PHASE_6_INFLECTION_POINT.md](PHASE_6_INFLECTION_POINT.md)** — Why this phase matters philosophically
- **[PHASE_6_PLAN.md](PHASE_6_PLAN.md)** — Complete Phase 6 strategy
- **[PHASE_6_SUMMARY.md](PHASE_6_SUMMARY.md)** — Deliverables checklist
