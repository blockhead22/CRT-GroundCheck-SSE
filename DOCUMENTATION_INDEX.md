# CRT Documentation Index

**Last Updated**: 2026-01-20  
**Purpose**: Navigate all CRT documentation  
**Start**: [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Read this first to understand why CRT exists

---

## 🎯 For New Users

**Getting Started** (read in order):

1. **[CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md)** ⭐ **START HERE**
   - Why CRT exists
   - What problems it solves
   - Core principles and design philosophy
   - What CRT is and is NOT

2. **[README.md](README.md)**
   - Quick overview
   - Installation instructions
   - Basic features

3. **[QUICKSTART.md](QUICKSTART.md)**
   - Get running in 5 minutes
   - Three different interfaces (Web UI, CLI, API)
   - Demo script to test functionality

4. **[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)**
   - Current beta limitations
   - Workarounds for known issues
   - What's working vs what's experimental

---

## 📚 For Understanding the System

**Architecture & Design**:

- **[CRT_WHITEPAPER.md](CRT_WHITEPAPER.md)**
  - Technical architecture
  - Memory governance principles
  - Trust-weighted retrieval math
  - Contradiction ledger design
  - Evaluation philosophy

- **[CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md)**
  - Complete usage guide
  - Query types and system behavior
  - Memory management
  - Contradiction handling workflows

- **[CRT_QUICK_REFERENCE.md](CRT_QUICK_REFERENCE.md)**
  - API endpoint reference
  - Response schemas
  - Configuration options
  - Code examples

---

## 🔧 For Developers

**Contributing & Development**:

- **[BETA_RELEASE_CHECKLIST.md](BETA_RELEASE_CHECKLIST.md)**
  - Structured go/no-go analysis
  - Evidence-based status
  - Blocker tracking

- **[BETA_LAUNCH_WORKFLOW.md](BETA_LAUNCH_WORKFLOW.md)**
  - Day-by-day launch plan
  - Testing procedures
  - Deployment steps

- **[DEBUG_PRINT_REMOVAL_GUIDE.md](DEBUG_PRINT_REMOVAL_GUIDE.md)**
  - Converting debug prints to logging
  - Line-by-line instructions
  - Verification steps

**Configuration**:

- **[.env.example](.env.example)**
  - Environment variable template
  - Database paths
  - API keys and settings
  - Gate threshold configuration

**Testing**:

- **Stress Test Reports**: `artifacts/adaptive_stress_report.*.md`
  - 80-turn adversarial conversation tests
  - Contradiction detection metrics
  - Gate performance analysis

---

## 🏗️ For System Administrators

**Deployment**:

- **[README.md](README.md)** - Installation section
- **[.env.example](.env.example)** - Configuration template
- **[LICENSE](LICENSE)** - MIT license terms

**Monitoring**:

- Check `artifacts/` for stress test results
- API health: `http://127.0.0.1:8123/api/dashboard/overview`
- Contradiction tracking: `http://127.0.0.1:8123/api/contradictions`

---

## 📖 By Topic

### Contradictions
- [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Why contradictions matter
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Ledger design (§5-6)
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Current contradiction handling issues

### Memory & Retrieval
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Trust-weighted retrieval (§4)
- [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Memory as evidence principle
- [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md) - Memory management

### Gates & Validation
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Gate design (§3)
- [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Why gates exist
- [.env.example](.env.example) - Gate threshold configuration

### Uncertainty Handling
- [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Uncertainty as first-class output
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Uncertainty design (§5)
- [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md) - Interpreting uncertainty responses

### Trust & Confidence
- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Trust evolution (§6)
- [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Trust principles
- [CRT_QUICK_REFERENCE.md](CRT_QUICK_REFERENCE.md) - Trust score API

---

## 🚀 By Use Case

### "I want to understand the philosophy"
1. [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md)
2. [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Abstract + §1-2

### "I want to try it out"
1. [QUICKSTART.md](QUICKSTART.md)
2. [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
3. [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md)

### "I want to deploy it"
1. [README.md](README.md) - Installation
2. [.env.example](.env.example) - Configuration
3. [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - What to expect

### "I want to contribute"
1. [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Understand the vision
2. [BETA_RELEASE_CHECKLIST.md](BETA_RELEASE_CHECKLIST.md) - Current status
3. [DEBUG_PRINT_REMOVAL_GUIDE.md](DEBUG_PRINT_REMOVAL_GUIDE.md) - Example contribution

### "I want to integrate it"
1. [CRT_QUICK_REFERENCE.md](CRT_QUICK_REFERENCE.md) - API reference
2. [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Architecture
3. [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md) - Usage patterns

### "I want to understand the current state"
1. [BETA_RELEASE_SUMMARY.md](BETA_RELEASE_SUMMARY.md) - What works right now
2. [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - What doesn't
3. Latest stress test: `artifacts/adaptive_stress_report.*.md`

---

## 📂 File Organization

```
d:\AI_round2\
│
├── 📘 PHILOSOPHY & VISION
│   ├── CRT_PHILOSOPHY.md           ⭐ START HERE - Why CRT exists
│   └── CRT_WHITEPAPER.md           Technical philosophy
│
├── 🚀 GETTING STARTED
│   ├── README.md                   Overview + installation
│   ├── QUICKSTART.md               5-minute setup
│   ├── KNOWN_LIMITATIONS.md        Current beta status
│   └── .env.example                Configuration template
│
├── 📖 USER DOCUMENTATION
│   ├── CRT_HOW_TO_USE.md          Complete usage guide
│   └── CRT_QUICK_REFERENCE.md     API reference
│
├── 🔧 DEVELOPER DOCUMENTATION
│   ├── BETA_RELEASE_CHECKLIST.md  Go/no-go analysis
│   ├── BETA_RELEASE_SUMMARY.md    Current state summary
│   ├── BETA_LAUNCH_WORKFLOW.md    Launch procedures
│   └── DEBUG_PRINT_REMOVAL_GUIDE.md Code improvement guide
│
├── 📊 EVIDENCE & TESTING
│   └── artifacts/
│       ├── adaptive_stress_report.*.md   Test results
│       └── adaptive_stress_run.*.jsonl   Full test logs
│
├── 🏗️ IMPLEMENTATION
│   ├── crt_api.py                 REST API server
│   ├── personal_agent_cli.py      CLI interface
│   ├── crt_chat_gui.py           Streamlit GUI
│   └── personal_agent/            Core library
│       ├── crt_rag.py            Main engine
│       ├── crt_memory.py         Memory system
│       ├── crt_ledger.py         Contradiction tracking
│       └── ...
│
└── 📝 LEGAL & LICENSE
    └── LICENSE                    MIT license
```

---

## 🎯 Reading Paths

### Path 1: "Just Let Me Use It" (15 minutes)
1. [QUICKSTART.md](QUICKSTART.md) - Follow installation steps
2. Run demo script
3. [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Know what to expect

### Path 2: "I Want to Understand It" (1 hour)
1. [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Why it exists (20 min)
2. [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - How it works (30 min)
3. [QUICKSTART.md](QUICKSTART.md) - Try it (10 min)

### Path 3: "I'm Evaluating for Production" (2 hours)
1. [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Alignment check (20 min)
2. [BETA_RELEASE_SUMMARY.md](BETA_RELEASE_SUMMARY.md) - Current capabilities (15 min)
3. [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Risk assessment (15 min)
4. [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Architecture deep dive (40 min)
5. [QUICKSTART.md](QUICKSTART.md) + Testing - Hands-on validation (30 min)

### Path 4: "I Want to Contribute" (3 hours)
1. [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) - Understand the vision (20 min)
2. [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Technical foundation (40 min)
3. [BETA_RELEASE_CHECKLIST.md](BETA_RELEASE_CHECKLIST.md) - Current status (20 min)
4. [QUICKSTART.md](QUICKSTART.md) - Set up dev environment (15 min)
5. Code review: `personal_agent/crt_rag.py` - Core implementation (60 min)
6. [DEBUG_PRINT_REMOVAL_GUIDE.md](DEBUG_PRINT_REMOVAL_GUIDE.md) - Example task (15 min)

---

## 🔗 External Resources

- **Frontend**: `frontend/README.md` - React web interface documentation
- **Testing**: `tests/` - Pytest test suite
- **Tools**: `tools/` - Stress testing, training scripts
- **Archived**: `archive/` - Historical documentation

---

## ⭐ Most Important Documents

If you only read three things:

1. **[CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md)** - Understand why CRT exists
2. **[QUICKSTART.md](QUICKSTART.md)** - Get it running
3. **[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)** - Know what to expect

Everything else builds on these three.

---

**Questions?** Check the relevant document above or review the stress test artifacts in `artifacts/` for evidence of current system behavior.

**Contributing?** Start with [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md) to understand the vision, then review [BETA_RELEASE_CHECKLIST.md](BETA_RELEASE_CHECKLIST.md) for current priorities.

**Deploying?** Follow [QUICKSTART.md](QUICKSTART.md), configure via [.env.example](.env.example), and review [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for production readiness.
