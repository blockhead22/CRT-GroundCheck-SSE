# CRT + GroundCheck: Honest AI Memory (Prototype)

## What it is
CRT + GroundCheck is a **contradiction‑preserving memory layer** for AI assistants. It keeps conflicting user facts instead of overwriting them, and it verifies that responses **disclose conflicts** rather than presenting one side as definitive truth.

This repository is a **research prototype** focused on memory governance and output verification, not a fully productized application.

## The idea
People change jobs, move cities, and revise preferences. Most AI memory systems silently overwrite old facts and then answer confidently with the latest value—creating the risk of **confident wrong answers** or “gaslighting.”

CRT keeps the history of contradictions and forces transparency. If a conflict exists, the system should either:
1) disclose the conflict,
2) ask for clarification, or
3) refuse to assert a single answer.

## How it works (high level)
1. **Memory layer (CRT)** stores user facts and tracks contradictions instead of overwriting them. A contradiction ledger records conflicting claims.
2. **Trust scoring** updates as new claims arrive; newer or confirmed facts can gain trust, but older facts are retained.
3. **Retrieval** returns relevant memories, including conflicting ones.
4. **GroundCheck verification** inspects the generated response and enforces disclosure when contradictions are present.

## Intended use
- **Long‑term personal assistants** where user facts change over time.
- **Auditable domains** (health, legal, enterprise knowledge) where transparency matters more than hiding conflicts.
- **Research and evaluation** for contradiction handling and truthful memory behavior.

## Why it matters (grounded impact)
- **Reduces silent memory overwrites** that lead to confident false answers.
- **Improves transparency** by surfacing conflicts instead of hiding them.
- **Creates auditability** through a ledger of conflicting claims and their resolution history.

## Run the stress test
The built‑in stress harness exercises contradictions and recall behaviors.

```bash
python tools/crt_stress_test.py --turns 30 --print-every 1
```

API mode (if the server is running):

```bash
uvicorn crt_api:app --host 127.0.0.1 --port 8123
python tools/crt_stress_test.py --use-api --api-base-url http://127.0.0.1:8123 --reset-thread --print-every 1
```

## Integrate into an existing project
You can embed the CRT memory layer into your app by instantiating the engine and routing user inputs through it.

```python
from personal_agent.crt_rag import CRTEnhancedRAG

rag = CRTEnhancedRAG()

# Store user facts (contradictions are preserved)
rag.process_user_input("I work at Microsoft", thread_id="demo")
rag.process_user_input("I work at Amazon", thread_id="demo")

# Query with conflict disclosure
result = rag.query("Where do I work?", thread_id="demo")
print(result["answer"])
```

### API integration
The FastAPI server exposes endpoints for queries, contradiction inspection, and evaluation workflows.

```bash
uvicorn crt_api:app --host 0.0.0.0 --port 8123
```

Send a query:

```bash
curl -X POST http://127.0.0.1:8123/api/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Where do I work?", "thread_id": "demo"}'
```

---

**Status:** Research prototype. Designed for transparency and contradiction handling rather than maximum raw grounding accuracy.
