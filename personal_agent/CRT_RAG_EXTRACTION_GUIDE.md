# crt_rag.py Extraction Guide

## Current State
- **10,171 lines**, **107 methods** in one file
- Does 10 different jobs that should be separate modules

## The Plan
Extract one module at a time. After each extraction, `crt_rag.py` still works exactly the same - it just imports from the new file instead of having the code inline. No behavior changes. Just organization.

## Extraction Order (easiest to hardest)

### 1. `trust_evolution.py` (EASY - start here)
**4 methods, ~200 lines**
- Lines 1367-1519: `compute_grounding_score()` - compute grounding score for answer based on memory overlap
- Lines 2208-2244: `should_express_uncertainty()` - determine if system should express uncertainty
- Lines 9192-9229: `enforce_web_answer_policy()` - enforce citations/disclaimers
- Plus the trust gain/decay math currently inline

**Why first:** Pure math, minimal dependencies. Takes memory scores in, returns numbers out. Almost no coupling to the rest of the file.

---

### 2. `slot_extraction.py` (EASY)
**9 methods, ~400 lines**
- Lines 454-485: `extract_facts_cached()` - LRU-cached fact extraction
- Lines 486-529: `extract_facts()` - two-tier extraction (hard slots + open tuples)
- Lines 985-1007: `extract_facts_with_context()` - facts with temporal/domain metadata
- Lines 1694-1699: `canonicalize_slot_name()` - strip "user." prefix
- Lines 1700-1771: `record_profile_replacement()` - record structured fact updates
- Lines 2441-2512: `extract_factual_value()` - parse FACT: slots from memory text
- Lines 7458-7610: `infer_question_slots()` - infer which slots a question asks about
- Lines 9056-9091: `extract_search_query()` - strip prefixes from search queries
- Lines 8379-8535: `classify_assertion_vs_question()` - avoid storing questions as facts

**Why second:** Self-contained text processing. Takes text in, returns structured data out.

---

### 3. `contradiction_detection.py` (MEDIUM)
**21 methods, ~2500 lines - the biggest extraction**
- Lines 560-607: `detect_denial()` - denial statement detection
- Lines 608-676: `check_denial_retraction()` - retraction of prior denial
- Lines 677-723: `build_gaslighting_citation()` - citation for denied claims
- Lines 754-833: `detect_gaslighting()` - gaslighting attempt detection
- Lines 834-890: `detect_identity_wipe()` - mass retraction attacks
- Lines 1520-1556: `classify_contradiction_severity()` - blocking/note/none
- Lines 1644-1668: `has_open_contradictions()` - check for unresolved conflicts
- Lines 2312-2440: `infer_next_steps()` - actionable steps from hard conflicts
- Lines 2513-2585: `build_caveat()` + `build_specific_caveat()` - caveat text
- Lines 2586-2618: `already_has_caveat()` - check for existing caveat language
- Lines 2619-2711: `auto_resolve_contradiction()` - pick highest trust claim
- Lines 2712-2911: `check_blocking_contradictions()` - should block response?
- Lines 3063-3544: `check_contradictions_ml()` - ML-based detection
- Lines 3545-3677: `semantic_contradiction_check()` - opinion-level contradictions
- Lines 3678-3735: `track_implicit_confirmations()` - repeated facts from open contradictions
- Lines 3736-3839: `resolve_on_clarification()` - resolve when user clarifies
- Lines 3840-4338: `detect_natural_language_resolution()` - NL resolution statements
- Lines 8898-8955: `detect_implicit_sentiment_contradiction()` - sentiment conflicts
- Lines 10163-10167: `get_unresolved_contradictions()`
- Lines 530-559: `are_semantically_equivalent()` - value equivalence check
- Lines 1578-1599: `is_name_declaration()` - detect name declarations

**Why third:** Many methods but they mostly talk to each other, not to the rest of the file. The interface to `crt_rag.py` is clean: "here's a new fact, does it contradict anything?"

---

### 4. `query_resonance.py` (MEDIUM)
**13 methods, ~800 lines**
- Lines 926-984: `needs_disambiguation()` - multi-domain context check
- Lines 1325-1331: `mentions_user_name()` - name in query check
- Lines 1332-1366: `classify_query_type_heuristic()` - explanatory vs conversational
- Lines 1600-1643: `detect_third_person_reference()` - third-person user questions
- Lines 7611-7642: `is_self_question()` - "who are you?" detection
- Lines 8189-8197: variation config helpers
- Lines 8956-9055: Copilot/GroundCheck context detection
- Lines 9246-9255: binary capability question check
- Lines 9349-9411: memory recall/citation/alias/dump detection
- Lines 9819-9865: open contradiction listing detection
- Lines 8888-8941: synthesis/summary detection

**Why fourth:** Query classification is pure input analysis. Takes a query string, returns a classification. No side effects.

---

### 5. `retrieval.py` (MEDIUM)
**12 methods, ~800 lines**
- Lines 170-220: `rerank_fisher()` - Fisher precision/uncertainty reranking
- Lines 1008-1221: `retrieve_memories()` - the main trust-weighted retrieval
- Lines 1222-1247: `filter_slot_claims()` - filter disallowed slot claims
- Lines 1248-1278: `get_latest_slot_value()` - latest value for a slot
- Lines 1279-1324: `extract_user_name()` - best-effort name from memories
- Lines 1669-1692: `load_user_memories()` - scoped memory loading
- Lines 2026-2061: `search_effective_facts()` - keyword search
- Lines 7315-7457: `build_resolved_documents()` - fact/fallback separation
- Lines 7701-7848: `augment_with_slot_memories()` - slot-specific retrieval
- Lines 8961-9045: `read_groundcheck_context()` - GroundCheck MCP DB
- Lines 9092-9107: `fetch_url()` - direct URL content
- Lines 9108-9138: `web_search()` - DuckDuckGo search

**Why fifth:** Retrieval has more dependencies (needs the embedding model, the DB, trust scores) but the interface is clean: query in, ranked memories out.

---

### 6. `prompt_assembly.py` (HARD - do last)
**26 methods, ~2500 lines**
This is everything that builds text for the LLM: uncertainty responses, identity answers, web citations, caveat injection, memory inventory, synthesis responses, etc.

**Why last:** These methods are the glue between retrieval, contradiction detection, and the LLM. They depend on everything else. Extract everything else first, then what's left in `crt_rag.py` is essentially prompt assembly + the main orchestration method.

---

### 7. What stays in `crt_rag.py`
After all extractions:
- The `CRTEnhancedRAG` class definition and `__init__`
- The main `query()` method (lines 4339-7155) - the orchestrator that calls everything else
- The `query_with_intent_router()` method
- System health/status methods
- Tracing/diagnostics

This should be ~3000-4000 lines - still big but now it's just orchestration, not implementation.

---

## How to Extract (step by step for each module)

1. Create the new file (e.g., `personal_agent/trust_evolution.py`)
2. Copy the functions/methods into it
3. Add necessary imports at the top of the new file
4. In `crt_rag.py`, replace the method bodies with imports:
   ```python
   from personal_agent.trust_evolution import compute_grounding_score
   ```
   Or if they're methods on the class, delegate:
   ```python
   def compute_grounding_score(self, ...):
       return trust_evolution.compute_grounding_score(self.memory, ...)
   ```
5. Run tests: `python -m pytest tests/`
6. Manual smoke test: start the app, ask a few questions, check nothing broke
7. Commit. Move to next module.

## Don't Do
- Don't rewrite logic while extracting. Just move it.
- Don't rename functions. Just move them.
- Don't optimize. Just move.
- Don't do two extractions in one commit.
