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

## Interactive Demo

The fastest way to see the system in action:

```bash
# Activate environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Run interactive demo
python rag-demo.py
```

### Demo Architecture
```
User Input → IntentRouter → Handler → Response

Handlers:
  • fact_statement/correction → FactStore (store with contradiction detection)
  • fact_question → FactStore (lookup) → CRT fallback
  • task_code/explain → LLM (Ollama) or templates
  • chat_greeting/emotion → Templates or LLM
  • knowledge_query → LLM
```

### Example Session
```
You: My name is Nick
[fact_statement]
🤖 Got it! I'll remember your name is Nick.

You: My favorite color is orange because of my leukemia battle.
[fact_statement]
🤖 Got it! I'll remember your favorite color is orange.

You: What is my name?
[fact_question]
🤖 Nick

You: why is my favorite color orange?
[fact_question]
🤖 Your favorite color is orange because my leukemia battle

You: Actually my name is Sarah
[fact_correction]
🤖 Updated! Your name is now Sarah (was Nick).

You: Write me some javascript to reverse a string
[task_code]
🤖 ```javascript
function reverseString(str) {
  return [...str].reverse().join('');
}
```

You: facts
==================================================
📋 CURRENT FACTS
==================================================
  user.name
    → Sarah
    Trust: [██████████] 0.98 | Source: user_corrected

  user.favorite_color
    → orange
    Trust: [█████████░] 0.95 | Source: user_stated
```

### Demo Commands
| Command | Action |
|---------|--------|
| `facts` | Show all stored facts with trust scores |
| `memory` | Show raw CRT memories |
| `history <slot>` | Show change history for a slot (e.g., `history name`) |
| `clear` | Reset all databases |
| `quit` | Exit |

### Components Used
- **FactStore** (`personal_agent/fact_store.py`): Slot-based structured memory
- **IntentRouter** (`personal_agent/intent_router.py`): Pattern-based intent classification
- **CRT** (`personal_agent/crt_rag.py`): Trust-weighted contradiction-aware memory
- **Ollama** (optional): LLM for code generation and general queries

---

## The idea
Human circumstances and preferences are not static, they evolve over time due to career changes, relocations, and shifting interests. AI systems that remember user information must account for this fluidity. However, most AI memory systems simply overwrite old information with new data, then present the latest value as fact without ever acknowledging that a change occurred. This creates confidently wrong answers or an unsettling experience where the system behaves as though the previous information never existed. Worse, it opens the door for the AI to internalize falsehoods as truth or perpetuate contradictions it never acknowledged, undermining trust and reliability.

CRT preserves the history of contradictions. When conflicts exist, the system:

Discloses the conflict explicitly
Asks for clarification when appropriate
Refuses to give a single answer when evidence is split

## System architecture
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
Tests contradiction detection across 35 challenging scenarios including negation, temporal confusion, and semantic variations.

```bash
# Full 35-turn adversarial challenge
python tools/adversarial_crt_challenge.py --turns 35

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

### Current test status (2026-01-26)

| Test | Score | Target | Status |
|------|-------|--------|--------|
| **crt_stress_test.py** | 91.7% eval, 80% detection | 90%+ | ✅ PASSING |
| **adversarial_crt_challenge.py** | 65.7% (23/35) | 80% | ⚠️ In progress |
| **False Positives** | 0 | 0 | ✅ PASSING |
| **Caveat Violations** | 0 | ≤2 | ✅ PASSING |

**Phase breakdown (35-turn adversarial):**

| Phase | Score | Status |
|-------|-------|--------|
| BASELINE | 100% | ✅ Perfect |
| TEMPORAL | 30-50% | ⚠️ Needs work |
| SEMANTIC | 80% | ✅ Good |
| IDENTITY | 100% | ✅ Perfect |
| NEGATION | 50-70% | ⚠️ Inconsistent |
| DRIFT | 50% | Manual eval |
| STRESS | 50% | Manual eval |

**Key findings:**
- System successfully detects and handles most contradictions
- Strong performance on baseline, identity, and semantic variations
- Zero false positives across all test scenarios
- Areas for improvement: direct_correction, hedged_correction, retraction_of_denial patterns

---

## Development Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Self-questioning, caveat injection, feature flags | ✅ Complete |
| **Phase 1.1** | Wire up CRTMath call sites | ✅ Complete |
| **Phase 1.2** | Context-Aware Memory (domain/temporal detection) | ✅ Complete |
| **Phase 1.3** | Advanced Testing Suite (adversarial agent, paragraph tests) | 📋 Next |
| **Phase 2** | UX Enhancements (emotion signals, humble wrapper) | 📋 Planned |
| **Phase 2.1** | **FactStore + IntentRouter** (structured memory, intent classification) | ✅ Complete |
| **Phase 3** | Vector-store-per-fact (experimental) | 📋 Planned |

### Phase 2.1 Features (Just Completed)
- **FactStore**: Slot-based structured memory (`user.name`, `user.favorite_color`, etc.)
- **IntentRouter**: Pattern-based intent classification (15 intent types)
- **Contradiction Detection**: Real fact-level contradiction handling with trust updates
- **Reason Extraction**: Stores "because" clauses as separate facts
- **LLM Integration**: Ollama for code generation and general queries
- **Template Fallbacks**: Works without LLM using template responses

### Phase 2.0 Features
- **Domain Detection**: Detects domains (career, hobbies, family) to allow multi-role facts
- **Temporal Status**: Tracks past/active/future status to handle "I used to work at..." patterns
- **Context-Aware Contradictions**: "I'm a programmer AND a photographer" no longer conflicts
- **Temporal Updates**: "I don't work at Google anymore" updates status instead of flagging contradiction

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
**Research prototype** - Updated 2026-01-27

**Current Phase:** 2.1 (FactStore + IntentRouter)

### New Files Added
| File | Purpose |
|------|---------|
| `personal_agent/fact_store.py` | Structured slot-based memory with contradiction detection |
| `personal_agent/intent_router.py` | Intent classification (15 types) with pattern matching |
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
