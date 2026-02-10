# Round 2 Adversarial Hardening — Implementation Plan

## Current State

- **Round 5 result**: 15/19 (79%), 9/9 direct contradictions detected (100%), 0 false positives
- **4 remaining failures**: T35 (gaslighting), T39–T41 (blindside)
- **Target**: 18/19 (95%) or better

## Implementation Order (dependency-ordered)

### Step 1: T2 — Gaslighting Edge Case (T35)

**~20 lines, 2 files**

**Root Cause**: `extract_fact_slots` in `personal_agent/fact_slots.py` ~line 587 matches `"you think my name is Alex"` as a name declaration because the regex `\bmy\s+(?:real|actual|true|full)?\s*name is\s+` greedily matches without checking for negation context. Additionally, `_detect_gaslighting_attempt()` in `personal_agent/crt_rag.py` ~line 489–533 has patterns that are too narrow.

**Fix**:

1. **`personal_agent/fact_slots.py`** ~line 587: Add a negation-context guard before the `\bmy\s+name is\s+` pattern — skip extraction if preceded by `"you think"`, `"why do you think"`, `"you said"`, `"you believe"`, etc.

2. **`personal_agent/crt_rag.py`** `_detect_gaslighting_attempt()` ~line 489–533: Add new patterns:
   - `r"i don't know why you think"`
   - `r"(?:my|it)\s*(?:'s|has)\s+always been"`
   - `r"why do you think (?:my|i)"`

**Verification**: Send `"I don't know why you think my name is Alex"` — should NOT extract `name=Alex`, should flag gaslighting.

---

### Step 2: T1 — Blindside Detection (T39–T41)

**~50–70 lines new code**

**Root Cause**: No identity-wipe detection exists. `_is_user_name_declaration()` at crt_rag.py ~line 1121–1131 has no context awareness. Blindside attacks like `"Everything I told you was a lie"` or `"Forget everything — my real name is Zara"` pass through unchallenged.

**Fix**:

1. **Add `_detect_blindside_attack()`** near line 534 in `personal_agent/crt_rag.py` (after `_detect_gaslighting_attempt()`):
   - Pattern-based detection for:
     - `"everything was a lie"` / `"everything I told you was a lie"`
     - `"forget everything"` / `"disregard everything"`
     - `"none of that was true"` / `"none of that was real"`
     - Multi-fact replacement in a single message (≥3 contradicting facts)
   - Returns `True` if blindside detected, along with a reason string

2. **Wire into `query()`** between gaslighting check (~line 3060) and assertion block (~line 3170):
   - If blindside detected → set `contradiction_detected = True`, add hedge response, lower confidence

**Verification**: Send `"Actually everything I told you was a lie. My real name is Zara, I'm 40, and I live in Berlin"` — should flag as blindside, not accept any of the new facts blindly.

---

### Step 3: T4 — OllamaClient API Mismatch

**~8 lines, 4 files**

**Root Cause**: `generate()` in `personal_agent/ollama_client.py` ~line 67 has signature `def generate(self, prompt, system=None, max_tokens=500, temperature=0.7, stream=False)` — NO `model` parameter. But 6+ call sites pass `model=` keyword, and 2 SSE files pass `model` as a positional arg (mapping to `prompt`).

**Fix**:

1. **`personal_agent/agent_reasoning.py`** lines 185, 218, 263, 297, 333: Remove `model=self.model` from each `generate()` call
2. **`personal_agent/agent_loop.py`** line 623: Remove `model="mistral:latest"` from `generate()` call
3. **`sse/extractor.py`** line 235: Fix positional arg order (model passed as prompt)
4. **`sse/contradictions.py`** line 80: Fix positional arg order (model passed as prompt)

**Verification**: Exercise any agent reasoning path; confirm no `TypeError: generate() got an unexpected keyword argument 'model'`.

---

### Step 4: T5 — Shared-Memory Reset Path

**~5–10 lines**

**Root Cause**: `_thread_db_paths_map()` in `routes/threads.py` ~line 115 always returns per-thread paths even when `CRT_SHARED_MEMORY=true`. Thread reset deletes per-thread files that don't exist, leaving the shared DB untouched.

**Fix**:

1. **`routes/threads.py`** `_thread_db_paths_map()` ~line 115: When `CRT_SHARED_MEMORY=true`, return the shared DB path(s) instead of per-thread paths. The reset logic should then clear only the thread's data from the shared DB (using `clear_thread_data(thread_id)` from F1) rather than deleting files.

**Verification**: With `CRT_SHARED_MEMORY=true`, reset a thread → confirm its memories are cleared from the shared DB without affecting other threads.

---

### Step 5: T3 — Stale Memory / False Contradiction Regression

**~10–20 lines**

**Root Cause**: `_load_all_memories()` in `personal_agent/crt_memory.py` ~line 1152 has no `WHERE thread_id = ?` clause. With `CRT_SHARED_MEMORY=true`, all ~200 stale memories from prior test runs are loaded, causing false contradictions on baseline facts from new threads.

**Fix**:

1. **`personal_agent/crt_rag.py`** `_check_all_fact_contradictions_ml()` ~line 2043: Add `thread_id` filtering when loading memories for contradiction checking — only compare against facts from the current thread.

2. Alternatively, add the `WHERE thread_id = ?` clause to `_load_all_memories()` when a `thread_id` is provided.

**Verification**: Start a fresh thread, assert `"My name is Alex"` — should NOT trigger contradiction from a stale memory of a different thread saying `"My name is Jordan"`.

---

## Post-Implementation

1. Kill any running server, restart clean: `$env:PORT="8123"; $env:CRT_HOST="127.0.0.1"; $env:CRT_CORS_ORIGINS="*"; $env:CRT_SHARED_MEMORY="true"; $env:CRT_ENABLE_LLM="true"; $env:CRT_OLLAMA_MODEL="deepseek-r1:latest"; D:\AI_round2\.venv\Scripts\python.exe crt_api.py`
2. Run full 50-turn adversarial test: `D:\AI_round2\.venv\Scripts\python.exe tools/agent_adversarial_driver.py --url http://127.0.0.1:8123 --mode auto --turns 50`
3. Parse results JSON for pass rate
4. Update README badges if 95%+ achieved
