# Infrastructure Bugfixes — Extracted from Adversarial Hardening

> **Context:** These are Steps 3–5 from the original adversarial hardening plan. They do NOT affect adversarial scores — they fix runtime bugs for production stability. Do these AFTER the hardening plan achieves 95%+.

---

## Bug 1: OllamaClient API Mismatch

**~8 lines, 4 files**

**Root Cause**: `generate()` in `personal_agent/ollama_client.py` ~line 67 has signature `def generate(self, prompt, system=None, max_tokens=500, temperature=0.7, stream=False)` — NO `model` parameter. But 6+ call sites pass `model=` keyword, and 2 SSE files pass `model` as a positional arg (mapping to `prompt`).

**Fix**:

1. **`personal_agent/agent_reasoning.py`** lines 185, 218, 263, 297, 333: Remove `model=self.model` from each `generate()` call
2. **`personal_agent/agent_loop.py`** line 623: Remove `model="mistral:latest"` from `generate()` call
3. **`sse/extractor.py`** line 235: Fix positional arg order (model passed as prompt)
4. **`sse/contradictions.py`** line 80: Fix positional arg order (model passed as prompt)

**Verification**: Exercise any agent reasoning path; confirm no `TypeError: generate() got an unexpected keyword argument 'model'`.

---

## Bug 2: Shared-Memory Reset Path

**~5–10 lines**

**Root Cause**: `_thread_db_paths_map()` in `routes/threads.py` ~line 115 always returns per-thread paths even when `CRT_SHARED_MEMORY=true`. Thread reset deletes per-thread files that don't exist, leaving the shared DB untouched.

**Fix**:

1. **`routes/threads.py`** `_thread_db_paths_map()` ~line 115: When `CRT_SHARED_MEMORY=true`, return the shared DB path(s) instead of per-thread paths. The reset logic should then clear only the thread's data from the shared DB (using `clear_thread_data(thread_id)` from F1) rather than deleting files.

**Verification**: With `CRT_SHARED_MEMORY=true`, reset a thread → confirm its memories are cleared from the shared DB without affecting other threads.

---

## Bug 3: Stale Memory / False Contradiction Regression

**~10–20 lines**

**Root Cause**: `_load_all_memories()` in `personal_agent/crt_memory.py` ~line 1152 has no `WHERE thread_id = ?` clause. With `CRT_SHARED_MEMORY=true`, all ~200 stale memories from prior test runs are loaded, causing false contradictions on baseline facts from new threads.

**Fix**:

1. **`personal_agent/crt_rag.py`** `_check_all_fact_contradictions_ml()` ~line 2043: Add `thread_id` filtering when loading memories for contradiction checking — only compare against facts from the current thread.

2. Alternatively, add the `WHERE thread_id = ?` clause to `_load_all_memories()` when a `thread_id` is provided.

**Verification**: Start a fresh thread, assert `"My name is Alex"` — should NOT trigger contradiction from a stale memory of a different thread saying `"My name is Jordan"`.
