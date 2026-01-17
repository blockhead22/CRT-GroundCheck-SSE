# CRT (working name)

**A truthful personal AI system with explicit uncertainty handling and contradiction tracking.**

CRT implements a "two-lane memory" architecture that separates grounded beliefs from conversational speech, enabling an AI assistant that knows what it knows, admits what it doesn't, and asks for clarification when faced with contradictions.

## 🎯 Core Features

- **Two-Lane Memory**: BELIEF (grounded facts) vs SPEECH (conversational responses)
- **Contradiction Tracking**: Durable ledger detects and resolves conflicting information
- **Safety Gates**: Prevents hallucinated claims with validation checks
- **Background Learning (M2)**: Contradictions automatically become learning goals
- **Trust-Weighted Reasoning**: Not just RAG - retrieval weighted by confidence scores
- **Evidence Packets**: Every claim links to source evidence with provenance

## 🚀 Quick Start

### Installation

```bash
# Clone and setup
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
pip install -e .
```

### Run the System

**Option 1: Full Stack (Recommended)**
```bash
# Terminal 1: Start API server
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123

# Terminal 2: Start frontend
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

**Option 2: CLI Chat**
```bash
python personal_agent_cli.py
```

**Option 3: Streamlit GUI**
```bash
streamlit run crt_chat_gui.py
```

## 📖 Documentation

**Essential Reading:**
- [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md) - Complete usage guide
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - System architecture and design philosophy
- [CRT_QUICK_REFERENCE.md](CRT_QUICK_REFERENCE.md) - API reference and examples

**Frontend:**
- [frontend/README.md](frontend/README.md) - React/TypeScript web interface

**Advanced:**
- [CRT_BACKGROUND_LEARNING.md](CRT_BACKGROUND_LEARNING.md) - M2 learning system
- [CRT_COMPANION_CONSTITUTION.md](CRT_COMPANION_CONSTITUTION.md) - AI safety principles

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend UI   │  React + TypeScript (localhost:5173)
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────┐
│   FastAPI       │  crt_api.py (localhost:8123)
│   Server        │
└────────┬────────┘
         │
    ┌────┴────┐
    │ CRT Core│
    └────┬────┘
         │
    ┌────┴─────────────┬──────────────┬─────────────┐
    │                  │              │             │
┌───▼────┐      ┌─────▼──────┐  ┌───▼──────┐  ┌──▼─────┐
│Memory  │      │Contradiction│  │ Research │  │  Jobs  │
│ System │      │   Ledger    │  │  Engine  │  │ Worker │
└────────┘      └─────────────┘  └──────────┘  └────────┘
   (SQLite)          (SQLite)       (Hybrid)    (Background)
```

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
