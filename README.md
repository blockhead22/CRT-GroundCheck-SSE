# CRT + GroundCheck: Contradiction-Preserving AI Memory

## What This Is

Long-term AI assistants accumulate contradictory facts as user information updates (job changes, location moves, preference shifts). **CRT + GroundCheck** preserves these contradictions in a queryable ledger, detects when AI outputs reference conflicting information, and enforces explicit disclosure—preventing silent overwrites and false confidence. This is the first production-ready system that treats contradictions as data to preserve rather than errors to hide.

## How It Works

**CRT (Contradiction Resolution & Trust)** — Memory governance layer
- Preserves contradictions in queryable ledger instead of overwriting
- Two-lane architecture: stable facts (BELIEF) vs. conversational output (SPEECH)
- Trust scores evolve as facts age or get confirmed
- Policy engine defines how contradictions should be handled

**GroundCheck** — Output verification layer  
- Detects when generated text uses contradicted facts
- Verifies output acknowledges contradictions appropriately
- Enforces disclosure or generates corrections
- Deterministic (regex-based), zero LLM calls, <10ms

**Core Invariant:** If retrieved memory contains mutually exclusive values, the system must either disclose both values, ask for clarification, or NOT present one value as definitive truth.

## Current Performance

**Test Results (Latest):**
- **207 tests total** with **99.5% pass rate** (206/207 passing)
- Core functionality: 100% operational
- Contradiction detection: 90% accuracy on test examples
- Zero-violation invariant: Proven in 1000+ turn stress tests
- Verification speed: <10ms per check
- Zero API costs (deterministic logic)

**GroundingBench Benchmark:**
- 76% overall accuracy on 500-example benchmark
- 90% accuracy on contradiction detection category
- Trade-off: Speed + contradiction handling vs raw accuracy (SelfCheckGPT: 82%)
- Multi-hop reasoning: 100% accuracy

## Known Limitations

**Fact extraction:**
- Regex-based, limited to 20+ predefined slots (employer, location, name, etc.)
- Cannot extract domain-specific or arbitrary fact types
- Misses complex linguistic patterns

**Accuracy:**
- 76% overall grounding (vs 82% for SelfCheckGPT)
- 40% accuracy on partial grounding detection (improvement area)
- Known failures: substring matching, complex paraphrases

**Scope:**
- Text-only (no multi-modal contradiction detection)
- Trust thresholds chosen empirically, not learned
- English-only patterns
- SQLite storage (tested to 10,000+ memories, not designed for >100K users)

**Maturity:**
- Production-ready for beta deployment
- Single-user threads (no multi-user support per thread)
- See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for detailed list

## Where This Could Help

**Personal AI assistants:**
- Prevent gaslighting when facts change
- Build trust through transparency
- Show history, not just current state

**Healthcare:**
- Track diagnosis evolution (initial positive → retest negative)
- Audit trail for contradictory test results
- Disclosure compliance (HIPAA)

**Legal:**
- Flag contradictory witness statements
- Track testimony evolution
- Discovery compliance

**Enterprise knowledge:**
- Detect conflicting documentation
- Version tracking for policies
- Reduce errors from stale information

**Customer service:**
- Acknowledge account history changes
- Transparent updates ("shipping address changed from...")
- Build customer trust

## Architecture

```
User Input → CRT Memory Layer → Retrieval → LLM Generation → 
GroundCheck Verification → Corrected Output (if needed) → User
                ↓                                              ↓
         Ledger Update ←────────────────────────────────────────
```

**CRT components:**
- Two-lane memory (stable + candidate)
- Contradiction ledger (tracks conflicts)
- Trust evolution (facts age, confirmations boost)
- Policy engine (MANDATORY_DISCLOSURE, PREFER_NEWER, ASK_USER, MERGE)

**GroundCheck components:**
- Fact extractor (regex patterns)
- Contradiction detector (groups facts by slot, finds conflicts)
- Disclosure verifier (checks for acknowledgment patterns)
- Correction generator (suggests proper disclosure)

## Technical Differentiators

**vs. SelfCheckGPT:**
- They: Check output consistency via LLM sampling
- We: Check retrieved memory for contradictions
- Trade-off: We're faster + cheaper, they're more accurate on basic grounding

**vs. Chain-of-Verification:**
- They: LLM generates verification questions
- We: Deterministic pattern matching + contradiction ledger
- Trade-off: We're deterministic + explainable, they handle arbitrary claims

**vs. ChatGPT Memory / Claude Projects:**
- They: Overwrite or randomly pick between conflicts
- We: Preserve contradictions + enforce disclosure
- Unique: Explicit contradiction tracking + policy enforcement

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Ollama** (for natural language responses)
  ```bash
  # Install: https://ollama.com/download
  ollama pull llama3.2:latest
  ollama serve
  ```

### Installation

```bash
# 1. Clone repository
git clone https://github.com/blockhead22/AI_round2.git
cd AI_round2

# 2. Setup Python environment
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt

# 3. Start API server
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123
# Wait for: "Uvicorn running on http://127.0.0.1:8123"
```

### Quick Demo (2 Minutes)

**PowerShell (Windows):**
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

**bash/curl (Linux/macOS/WSL):**
```bash
# Create contradiction
THREAD="quick_demo"
API="http://127.0.0.1:8123/api/chat/send"

curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"I work at Microsoft.\"}"

curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Actually, I work at Amazon, not Microsoft.\"}"

# Recall contradicted fact (pipe to jq for pretty JSON)
curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Where do I work?\"}" | jq '.answer, .metadata.reintroduced_claims_count'

# Expected: "Amazon (most recent update)" and 2
```

**✅ Success:** Answer includes caveat, count = 2, both memories flagged

---

## 📖 Documentation

**→ [START_HERE.md](START_HERE.md)** - Best starting point for new users  
**→ [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - Complete navigation guide

### Essential Reading
- **[QUICKSTART.md](QUICKSTART.md)** - Installation and setup (5 minutes)
- **[PURPOSE.md](PURPOSE.md)** - Why this project exists (honest impact assessment)
- **[CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md)** - System design principles and philosophy
- **[ELEVATOR_PITCH.md](ELEVATOR_PITCH.md)** - 30-second technical summary

### Test Reports & Validation
- **[COMPREHENSIVE_SYSTEM_TEST_REPORT.md](COMPREHENSIVE_SYSTEM_TEST_REPORT.md)** - Latest test results (207 tests, 99.5% pass rate)
- **[SYSTEM_TEST_EXECUTIVE_SUMMARY.md](SYSTEM_TEST_EXECUTIVE_SUMMARY.md)** - Executive summary of test results
- **[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)** - Current limitations and workarounds

### Technical Details
- **[CRT_WHITEPAPER.md](CRT_WHITEPAPER.md)** - Architecture deep dive
- **[CRT_REINTRODUCTION_INVARIANT.md](CRT_REINTRODUCTION_INVARIANT.md)** - Invariant specification
- **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** - Development roadmap

### For Beta Testers
- **[BETA_STARTER_KIT.md](BETA_STARTER_KIT.md)** - Beta tester onboarding guide
- **[DEMO_5_TURN.md](DEMO_5_TURN.md)** - Quick contradiction demonstration

---

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
│   │ Reintroduction Enforcer  │     │
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
/crt_api.py                    # FastAPI server
/personal_agent/
  ├── crt_rag.py               # Core retrieval + truth coherence
  ├── crt_memory.py            # Memory storage & retrieval
  ├── crt_ledger.py            # Contradiction tracking
  ├── crt_core.py              # Core CRT logic
  └── research_engine.py       # External knowledge integration
/groundcheck/                  # GroundCheck verification library
/groundingbench/               # 500-example benchmark dataset
/frontend/                     # React web interface
/tools/                        # Testing and validation tools
/tests/                        # Comprehensive test suite (207 tests)
/docs/                         # Additional documentation

Key Documentation:
- COMPREHENSIVE_SYSTEM_TEST_REPORT.md  # Latest test results
- SYSTEM_TEST_EXECUTIVE_SUMMARY.md     # Test summary & metrics
- CRT_PHILOSOPHY.md                    # System design principles
- QUICKSTART.md                        # Detailed setup guide
- KNOWN_LIMITATIONS.md                 # Current limitations & workarounds
```

## 🧪 Testing & Validation

### Smoke Test (2 minutes)
```bash
# See BETA_VERIFICATION_CHECKLIST.md for copy-paste script
# Tests: Memory → Contradiction → Recall → Flags
```

### Stress Test
```bash
# Run comprehensive stress test
python full_stress_test.py

# Or quick validation
python quick_validation_test.py

# Expected: All tests pass, zero invariant violations
```

### Unit Tests
```bash
pytest tests/ -v
```

---

## 📊 System Status

**Test Results:** 99.5% pass rate (207 tests)  
**Updated:** January 24, 2026  
**Status:** Production-ready for beta deployment

### ✅ What's Working
- **Zero-violation invariant** (proven in 1000+ turn stress tests)
- **Core functionality:** 100% operational (memory, ledger, trust, gates)
- **Contradiction detection:** 90% accuracy in diagnostic tests
- **API stability:** No crashes in extensive testing
- **Two-lane memory:** BELIEF/SPEECH separation working
- **Multi-interface support:** API, CLI, and web UI all functional
- **Thread isolation:** No cross-contamination between conversations

### ⚠️ Active Limitations
1. **Partial grounding detection:** 40% accuracy (improvement target: 80%+)
   - Affects complex "partially true" statement detection
   - Core contradiction detection unaffected (90% accuracy)

2. **Natural language resolution:** User saying "X is correct" doesn't auto-resolve
   - Workaround: Use direct API endpoint for resolution
   - UX issue, not system failure

3. **Production scale:** Tested to 10,000+ memories
   - SQLite-based (not designed for >100K users)
   - Migration path to PostgreSQL documented

### 🗺️ Roadmap
- **Current:** Beta deployment and testing
- **Near-term:** Academic publication, enterprise pilots
- **Mid-term:** Production hardening, scalability improvements  
- **Long-term:** Industry standard for AI memory governance

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for complete list and [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for detailed plans.

---

---

## Does This Matter? (Honest Answer)

**The honest answer: It depends on your use case.**

**What we know:**
- Contradiction detection works well (90% accuracy in tests, vs 30% for naive baselines)
- System is fast and deterministic (<10ms verification)
- Architecture is sound (99.5% test pass rate)
- Zero-violation invariant proven in extensive testing

**What we don't know:**
- Will users prefer disclosure to confident errors?
- Are contradictions common enough in real usage to justify the overhead?
- Will regulations eventually require this type of transparency?
- How will this scale to millions of users?

**We're publishing because:**
- The problem is real (AI memory systems do accumulate contradictions)
- The approach is novel (first explicit contradiction-preserving system)
- Others can evaluate if it helps their use case
- Research should be reproducible and extensible

**If you're working on:**
- Long-term AI memory → This might help
- Regulated AI (healthcare, legal) → This might help
- Personal assistants → This might help
- One-shot QA → This probably doesn't help
- Stateless chatbots → This doesn't help

**Try it. Evaluate it. Extend it if useful. Ignore it if not.**

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

---

**Built with:** Python 3.10+, FastAPI, React, SQLite, Ollama, sentence-transformers  
**Philosophy:** Evidence-first AI that preserves contradictions instead of hiding them  
**Status:** Production-ready for beta deployment (99.5% test pass rate)

---

**Questions?** See [QUICKSTART.md](QUICKSTART.md) or [BETA_STARTER_KIT.md](BETA_STARTER_KIT.md)
