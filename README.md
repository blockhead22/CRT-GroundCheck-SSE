# CRT + GroundCheck + SSE: Honest AI Memory

> **Quick Status:** See [STATUS.md](STATUS.md) for current metrics and next actions.  
> **AI Agents:** See [.github/prompts/_project-context.prompt.md](.github/prompts/_project-context.prompt.md) for context.

## What it is
This repository integrates three systems for transparent AI memory that tracks contradictions:
- **CRT**: A memory layer that preserves contradictions instead of overwriting them
- **GroundCheck**: A verification system that makes AI responses disclose conflicts instead of hiding them
- **SSE (Semantic String Engine)**: Powers fact retrieval and semantic matching
- **FactStore**: Structured slot-based memory with real contradiction detection
- **IntentRouter**: Classifies user intent to route inputs appropriately

This is a **research prototype** for memory governance and output verification in AI assistants.

---

## Interactive Demo (rag-demo.py)

The fastest way to see the system in action:

```bash
# Activate environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Run interactive demo
python rag-demo.py
```

### Requirements
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`
- Optional: [Ollama](https://ollama.ai/) with llama3.2 for LLM features

### Demo Architecture
```
IntentRouter -> classifies user input (fact, question, task, chat)
     |
     v
FactStore   -> structured facts (user.name, user.favorite_color)
CRT         -> trust-weighted memory + contradiction tracking
LLM         -> code generation, explanations (requires Ollama)
Templates   -> fallback responses when no LLM
```

### Example Session
```
You: My name is Nick
Bot: Got it. I'll remember your name is Nick.

You: What is my name?
Bot: Your name is Nick.

You: My favorite color is blue because it reminds me of the ocean
Bot: Got it. I'll remember your favorite color is blue.

You: facts
  user.name
    Value: Nick
    Trust: [##########] 1.00 | Source: user
  user.favorite_color
    Value: blue
    Trust: [##########] 1.00 | Source: user
```

### Demo Commands
| Command   | Description                              |
|-----------|------------------------------------------|
| `facts`   | Show all stored facts                    |
| `memory`  | Show CRT memory entries                  |
| `history` | Show conversation history                |
| `clear`   | Clear databases (with confirmation)      |
| `dump`    | Export facts to JSON, then clear all     |
| `verbose` | Toggle verbose step logging              |
| `quit`    | Exit the demo                            |

---

## System architecture

### How Modern LLMs vs CRT Handle Contradiction

**CRT Hybrid Architecture:**
1. **Fast path (regex)** - Instant extraction of obvious patterns (no LLM cost)
2. **Semantic path (LLM)** - Uses the LLM itself to extract complex claims
3. **Memory layer** - Persists facts with timestamps, sources, and trust scores
4. **Contradiction ledger** - Audit trail of all detected conflicts
5. **Gaslighting detection** - Cites original claim when user denies saying something

This is NOT rigid regex gates - the LLM does the heavy semantic lifting. Patterns are just a speed optimization for common cases.

### Architecture Diagram

1. **CRT memory layer**: Stores user facts with timestamps and tracks contradictions via a ledger
2. **ML contradiction detection**: Uses XGBoost models to classify belief changes (refinement vs. revision vs. temporal vs. conflict)
3. **Trust scoring**: Updates as new claims arrive; newer or confirmed facts gain trust, but older facts stay in memory
4. **SSE retrieval**: Returns relevant memories using semantic search, including conflicting ones
5. **GroundCheck verification**: Inspects responses to make sure contradictions are disclosed
6. **React frontend**: Provides an interactive UI with real time contradiction tracking, memory visualization, and educational onboarding

## Intended use
- **Long running personal assistants** where user facts change over time
- **Auditable domains** (health, legal, enterprise knowledge) where transparency matters more than hiding conflicts
- **Research and evaluation** for contradiction handling and truthful memory behavior

## Core benefits
- **Reduces silent memory overwrites** that lead to confident false answers
- **Improves transparency** by surfacing conflicts instead of hiding them
- **Creates auditability** with a ledger of conflicting claims and how they were resolved

---

## Frontend UI

The repository includes a **production ready React frontend** that demonstrates CRT capabilities through an interactive web interface.

### Features
- **60 second onboarding tutorial**: Interactive walkthrough showing how contradictions are detected and disclosed
- **Live contradiction ledger**: Real time panel displaying all detected contradictions with trust scores and audit trail
- **Memory lane visualization**: Two lane architecture showing stable facts vs. candidate facts
- **Side by side comparison**: Visual demonstration of regular AI (hides conflicts) vs. CRT (discloses conflicts)
- **Integration code examples**: Copy and paste ready snippets for Python, JavaScript, and cURL
- **Example scenarios**: Preloaded demos showing job changes, location moves, and preference updates

### Quick start (Frontend)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Then open `http://localhost:5173` in your browser.

**Backend requirement**: The frontend connects to the CRT API. Start the backend server first:
```bash
# From repository root
python crt_api.py
```

The API runs on `http://127.0.0.1:8123` by default.

### Frontend architecture
- **React 18.3** with TypeScript for type safety
- **Tailwind CSS** for responsive, utility based styling
- **Framer Motion** for smooth animations and transitions
- **Vite** for fast builds and hot module replacement

For detailed frontend documentation, see `frontend/README.md` and `frontend/IMPLEMENTATION_SUMMARY.md`.

---

## Quick Start

### Installation
```bash
# Clone the repository
git clone https://github.com/blockhead22/AI_round2.git
cd AI_round2

# Install dependencies
pip install -r requirements.txt

# Install the project packages
pip install -e .
pip install -e groundcheck/
```

## How to Run the Backend (API Server)

Start the backend API server (FastAPI):
```bash
# From repository root
uvicorn crt_api:app --host 0.0.0.0 --port 8123 --reload
```
Or, for production:
```bash
python crt_api.py
```
The API runs on `http://127.0.0.1:8123` by default.

If you want LLM features, make sure [Ollama](https://ollama.ai/) is installed and running:
```bash
ollama serve
# (Optional) ollama pull llama3.2
```

---

## How to Start the Frontend

The frontend is a React app in the `frontend/` directory.

```bash
cd frontend
npm install
npm run dev
```
Then open [http://localhost:5173](http://localhost:5173) in your browser.

---

## How to Run the Stress Tests

### Adversarial Challenge (no Ollama required)
```bash
python tools/adversarial_crt_challenge.py --turns 35
```

### CRT Stress Test (requires Ollama running)
```bash
ollama serve
python tools/crt_stress_test.py --turns 30 --print-every 5
```

### Run all tests (pytest)
```bash
pytest
```

---
### Basic usage (Programmatic)
```python
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_store import FactStore

# Option 1: FactStore for structured facts
store = FactStore(db_path="my_facts.db")
store.process_input("My name is Nick")
store.process_input("My favorite color is blue")
print(store.answer("What is my name?"))  # → "Nick"

# Option 2: CRT for complex memory with contradictions
rag = CRTEnhancedRAG()
rag.query("I work at Microsoft", thread_id="demo")
rag.query("I work at Amazon", thread_id="demo")
result = rag.query("Where do I work?", thread_id="demo")
print(result["answer"])  # Discloses both with conflict notice
```

### Intent Router usage
```python
from personal_agent.intent_router import IntentRouter, Intent

router = IntentRouter()
result = router.classify("Write me some Python code")
print(result.intent)      # Intent.TASK_CODE
print(result.extracted)   # {'language': 'python'}
print(result.confidence)  # 0.9
```

---

## Testing

### Run adversarial challenge (comprehensive stress test)
Tests contradiction detection across 45 challenging scenarios including negation, temporal confusion, gaslighting detection, and semantic variations.

```bash
# Full 45-turn adversarial challenge
python tools/adversarial_crt_challenge.py --turns 45

# Expected: Overall score ≥80%, with NEGATION and TEMPORAL phases ≥70%
```

### Run basic stress test
```bash
# Quick stress test (30 turns)
python tools/crt_stress_test.py --turns 30 --print-every 1
```

### Run pytest suite
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_contradiction_stress.py -v
pytest tests/test_adversarial_prompts.py -v
```

### Expected passing criteria
- Adversarial challenge overall score: **≥80%**
- NEGATION phase: **≥70%**
- TEMPORAL phase: **≥70%**
- All pytest tests: **PASS**
- No TypeErrors on integer value contradictions

### Current test status (2026-01-28)

| Test | Score | Target | Status |
|------|-------|--------|--------|
| **crt_stress_test.py** | 92.9% eval pass, 82.9% gate pass | 90%+ | ✅ PASSING |
| **adversarial_crt_challenge.py** | 87.5% (17.5/20 first phases) | 80% | ✅ PASSING |
| **False Positives** | 0 | 0 | ✅ PASSING |
| **Missed Detections** | 2 | ≤2 | ✅ PASSING |
| **Name Extraction Edge Cases** | 100% | 100% | ✅ PASSING |

**Latest stress test metrics (35 turns):**

| Metric | Value | Status |
|--------|-------|--------|
| Total Turns | 35 | - |
| Gates Passed | 29 (82.9%) | ✅ Good |
| Contradictions Detected | 6 | ✅ All key ones |
| Avg Confidence | 0.809 | ✅ Good |
| Avg Trust Score | 0.753 | ✅ Good |
| Eval Pass Rate | 92.9% (26/28) | ✅ Strong |
| Memory Failures | 0 | ✅ Perfect |

**Phase breakdown (adversarial test - first 20 turns):**

| Phase | Score | Status |
|-------|-------|--------|
| BASELINE | 100% (5/5) | ✅ Perfect |
| TEMPORAL | 70% (3.5/5) | ✅ Good |
| SEMANTIC | 80% (4/5) | ✅ Improved |
| IDENTITY | 100% (5/5) | ✅ Perfect |

**Key improvements (2026-01-28):**
- ✅ Fixed fact extraction for conjunction edge cases ("My name is Nick but you said Sarah" → extracts "Nick")
- ✅ Gaslighting detection with memory citation
- ✅ Hybrid LLM/regex claim extraction
- ✅ Zero false positives on synonyms/paraphrases
- ✅ Denial contradiction tracking
- ✅ LLM self-contradiction tracking (4 detected in test run)

**Key findings:**
- 6 contradictions correctly detected across employer, experience, education, preference, and name changes
- Strong performance on baseline, identity, and negation phases
- Edge case testing: Name extraction correctly handles conjunctions (e.g., "Nick but you" → "Nick")
- Reintroduction invariant: 18 flagged (audited), 0 unflagged violations
- 2 minor eval failures: contradiction detection timing, uncertainty expectation

---

## Roadmap (updated 2026-01-30)

### Next (committed)
1) **Phase 2.4 - Test Harness (required)**
   - Adversarial agent + paragraph tests
   - Gold labels for contradiction types
   - Regression dashboard + drift tracking
2) **Phase 2.5 - Model-based Contradiction Detection**
   - Classifier drop-in vs heuristic baseline
   - Feature flag + A/B comparison
3) **Phase 2.6 - Neural Retrieval + Reranking**
   - Embedding retrieval + reranker
   - Recall/precision evaluation vs baseline

### Later
4) **Phase 3 - UX Enhancements**
5) **Phase 4 - Vector-store-per-fact (experimental)**

### Completed Phases
| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Self-questioning, caveat injection, feature flags | Complete |
| **Phase 1.1** | Wire up CRTMath call sites | Complete |
| **Phase 1.2** | Context-Aware Memory (domain/temporal detection) | Complete |
| **Phase 2.1** | FactStore + IntentRouter (structured memory, intent classification) | Complete |
| **Phase 2.2** | **LLM Claim Tracker** (LLM self-contradiction + LLM<->User contradiction detection) | Complete |
| **Phase 2.3** | **Episodic Memory** (session summaries, preferences, patterns, concept linking) | Complete |


### Phase 2.3 Features (Completed)
- **Session Summaries**: Narrative summaries of conversations with topics, entities, facts learned
- **Preference Learning**: Extracts explicit preferences and infers from interaction patterns
- **Pattern Detection**: Identifies recurring topics, communication styles, behavioral patterns
- **Concept Linking**: Connects entities (people, projects, orgs) across sessions with alias resolution
- **Consumer-grade optimization**: SQLite WAL mode, fast regex, incremental updates, auto-cleanup

### Phase 2.2 Features (Completed)
- **LLM Claim Extraction**: Parse factual claims from LLM responses into slot/value pairs
- **LLM Fact Storage**: Store LLM claims with `source="llm"` in FactStore
- **LLM→LLM Contradiction Detection**: Flag when LLM says X then later says Y
- **LLM→USER Contradiction Detection**: Flag when LLM claims contradict user-stated facts
- **Disclosure Injection**: Add "I previously said..." or "You told me X but..." to responses

#### Full Contradiction Matrix (Phase 2.2)
| Source A | Source B | Detection | Status |
|----------|----------|-----------|--------|
| User | User | FactStore + CRT | ✅ Complete |
| LLM | LLM | LLM Claim Tracker | ✅ Complete |
| LLM | User | LLM Claim Tracker | ✅ Complete |
| User | LLM | LLM Claim Tracker | ✅ Complete |

### Phase 2.1 Features (Completed)
- **FactStore**: Slot-based structured memory (`user.name`, `user.favorite_color`, etc.)
- **IntentRouter**: Pattern-based intent classification (15 intent types)
- **Contradiction Detection**: Real fact-level contradiction handling with trust updates
- **Reason Extraction**: Stores "because" clauses as separate facts
- **LLM Integration**: Ollama for code generation and general queries
- **Template Fallbacks**: Works without LLM using template responses

### Phase 2.0 Features
- **Domain Detection**: Detects domains 
- **Temporal Status**: Tracks past/active/future status to handle "I used to work at..." patterns
- **Context-Aware Contradictions**: "I'm a programmer AND a photographer" no longer conflicts
- **Temporal Updates**: "I don't work at Google anymore" updates status instead of flagging contradiction

---

## Episodic Memory System

The repository includes an **Episodic Memory System** for higher-order learning about user preferences, interaction patterns, and connected concepts. This goes beyond basic fact storage to build a personalized understanding of the user over time.

### Key Capabilities

| Feature | Description | Performance |
|---------|-------------|-------------|
| **Session Summaries** | Narrative summaries of conversation sessions with topics, entities, and learned facts | Lightweight heuristic or LLM-powered |
| **Preference Learning** | Extracts explicit preferences ("I prefer short answers") and infers from patterns | Fast regex + frequency analysis |
| **Pattern Detection** | Identifies recurring topics, communication styles, and behavioral patterns | Incremental updates only |
| **Concept Linking** | Connects related entities across sessions (people, projects, organizations) | Alias-based resolution |

### Design Philosophy: Consumer Hardware First
- **SQLite with WAL mode**: Fast concurrent access, no server dependencies
- **Lightweight pattern matching**: Regex-based, no heavy NLP/ML
- **Incremental updates**: No full re-indexing on each interaction
- **Auto-cleanup triggers**: Limits data growth (~1000 interactions retained)
- **Lazy processing**: Store everything immediately, analyze later

### Architecture

```
User Message → CRT Memory (facts) → Response
                    ↓
            Episodic Memory Manager
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
Preference      Pattern         Concept
Extractor       Detector        Linker
    ↓               ↓               ↓
┌───────────────────────────────────────┐
│           SQLite Database             │
│  (summaries, preferences, patterns,   │
│   concepts, interaction_log)          │
└───────────────────────────────────────┘
```

### Usage Examples

#### Automatic Learning (via Chat Endpoints)
The system automatically processes each interaction through `/api/chat/send` or `/api/chat/stream`:
- Extracts explicit preferences ("I like concise answers")
- Infers style from response patterns
- Links mentioned entities to knowledge graph
- Logs interaction for pattern analysis

#### API Endpoints

```bash
# Get full user context (preferences, patterns, summaries, concepts)
curl http://127.0.0.1:8123/api/episodic/context

# Get learned preferences
curl "http://127.0.0.1:8123/api/episodic/preferences?category=style"

# Get detected patterns
curl "http://127.0.0.1:8123/api/episodic/patterns?min_confidence=0.5"

# Get linked concepts/entities
curl "http://127.0.0.1:8123/api/episodic/concepts?concept_type=person"

# Get session summaries
curl "http://127.0.0.1:8123/api/episodic/summaries?limit=5"

# Finalize session (creates summary + runs analysis)
curl -X POST http://127.0.0.1:8123/api/episodic/finalize-session
```

#### Programmatic Access

```python
from personal_agent.episodic_memory import get_episodic_manager

# Get the singleton manager
mgr = get_episodic_manager()

# Get user context for prompt building
context = mgr.get_user_context()
print(context["preferences"])  # {'style': {'verbosity': 'concise', 'emoji': True}}
print(context["patterns"])     # [{'type': 'topic_frequency', 'description': '...'}]

# Build context for LLM prompt
prompt_context = mgr.build_context_prompt()
# → "User Preferences: Prefers concise responses. Uses emoji..."
```

### What Gets Stored

**Preferences** (explicit and inferred):
- Communication style: verbosity, formality, detail level
- Response format: emoji usage, code style, technical depth
- Domain preferences: favorite languages, tools, topics

**Patterns** (detected from behavior):
- Topic frequency: What subjects the user asks about most
- Time patterns: When they're most active
- Style evolution: How preferences change over time

**Concepts** (knowledge graph):
- People mentioned: colleagues, family, friends
- Projects discussed: work projects, side projects
- Organizations: employers, schools, communities
- Topics: recurring interests and domains

**Session Summaries**:
- Narrative overview of conversation
- Key topics and entities mentioned
- Facts learned during session
- Unresolved questions for follow-up

### Storage Location
By default, episodic data is stored in:
```
personal_agent/data/episodic_memory.db
```

---

## API Server

Start the FastAPI server for remote access:

```bash
uvicorn crt_api:app --host 0.0.0.0 --port 8123
```

Query via API:
```bash
curl -X POST http://127.0.0.1:8123/api/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Where do I work?", "thread_id": "demo"}'
```

Run stress test against API:
```bash
python tools/crt_stress_test.py \
  --use-api \
  --api-base-url http://127.0.0.1:8123 \
  --reset-thread \
  --print-every 1
```

---

## Troubleshooting

### ML dependencies (xgboost)
The system uses XGBoost models for ML based contradiction detection. If xgboost is not installed:

**Symptom**: Warnings about "xgboost not installed" or "Falling back to heuristic contradiction detection"

**Fix**:
```bash
pip install xgboost>=1.7.0
```

The system will automatically fall back to heuristic based detection if xgboost is unavailable, but ML models provide better accuracy (especially for NEGATION and TEMPORAL cases).

### Missing groundcheck module
**Symptom**: `ModuleNotFoundError: No module named 'groundcheck'`

**Fix**:
```bash
cd groundcheck
pip install -e .
```

### Sentence transformers / torch issues
**Symptom**: Large download or space issues with PyTorch/transformers

**Note**: These are optional for full functionality. The core CRT system works with fallback modes if these are unavailable.

**Fix** (if needed):
```bash
pip install sentence-transformers
```

### TypeError on integer values
**Symptom**: `AttributeError: 'int' object has no attribute 'lower'`

**Status**: **FIXED** in latest version. The `ml_contradiction_detector.py` now converts all values to strings before string operations.

---

## Project status
**Research prototype** - Updated 2026-01-30

**Current Phase:** 2.4 (Test Harness)

### New Files Added
| File | Purpose |
|------|---------|
| `personal_agent/fact_store.py` | Structured slot-based memory with contradiction detection |
| `personal_agent/intent_router.py` | Intent classification (15 types) with pattern matching |
| `personal_agent/episodic_memory.py` | Higher-order memory: preferences, patterns, concept linking |
| `rag-demo.py` | Interactive CLI demonstrating all components |

This system works well for:
- Researchers exploring contradiction aware AI memory
- Developers building transparent personal assistants
- Teams needing auditable memory systems

Not recommended for production use without additional hardening, monitoring, and domain specific tuning.

For detailed project status and metrics, see [STATUS.md](STATUS.md).

---


## License
MIT License - see [LICENSE](LICENSE) for details
