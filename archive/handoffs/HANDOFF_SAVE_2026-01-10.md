# CRT Thread Handoff Save (2026-01-10)

This file is a **portable handoff snapshot** so another agent (or you on another machine) can pick up exactly where this thread left off.

## 0) Current state (what is “done”)

- Stress harness is extended to **50 turns** with a **Phase 11 PRESSURE / ADVERSARIAL** section.
- Evaluator is stricter and supports less-brittle checks: `must_contain_any` / `must_not_contain_any`.
- Prompt-injection / “instruction” hardening is in place:
  - Control/injection prompts are classified as `instruction` and **not stored** as durable USER facts.
  - Slot-based “answer from canonical resolved USER facts” fast-path applies to **questions and instructions**.
  - Summary-style instructions can be answered via a **fact-grounded one-line summary** fast-path.
- Slot extraction expanded to support missing recall targets (`first_language`, `team_size`).
- Learned suggestion layer exists (optional, suggestion-only) with offline training + reflection workflow.

### Latest confirmed run (end-to-end)

- Command used:
  - `D:/AI_round2/.venv/Scripts/python.exe crt_stress_test.py --turns 50 --sleep 0.02 --config crt_runtime_config.json`
- Result:
  - **Total turns:** 50
  - **Eval failures:** 0 (56/56 checks passed)
  - **Memory failures:** 0
  - **Artifact JSONL:** `artifacts/crt_stress_run.20260110_090237.jsonl`
  - **Per-run DBs:**
    - `artifacts/crt_stress_memory.20260110_090237.db`
    - `artifacts/crt_stress_ledger.20260110_090237.db`

## 1) Primary entry points (what to run)

### Stress test harness (main)

- File: `crt_stress_test.py`
- Purpose: Runs multi-turn CRT stress tests, emits per-turn metrics + eval checks, writes artifacts.
- Key flags:
  - `--turns` (default 30; we run 50 for “pressure”)
  - `--sleep` seconds between turns
  - `--config` path to `crt_runtime_config.json` (enables learned suggestion logging/A-B etc)
  - `--artifacts-dir`, `--memory-db`, `--ledger-db`

### Evaluator

- File: `crt_response_eval.py`
- Function: `evaluate_turn(user_prompt, result, expectations)`
- Supports expectations:
  - `expect_contradiction`, `expect_uncertainty`, etc.
  - `must_contain`, `must_not_contain`
  - `must_contain_any`, `must_not_contain_any`

### CRT core pipeline

- File: `personal_agent/crt_rag.py`
- Class: `CRTEnhancedRAG`
- Key behavior added/relied upon in this thread:
  1) **Store USER memory only for assertions**
     - `_classify_user_input()` returns one of: `question`, `instruction`, `assertion`, `other`.
     - Only `assertion` is stored as `MemorySource.USER`.
  2) **Slot-aware retrieval augmentation**
     - `_infer_slots_from_query()` infers relevant slots.
     - `_augment_retrieval_with_slot_memories()` injects best per-slot USER memories.
  3) **Slot fast-path answering**
     - `_answer_from_fact_slots()` answers from canonical resolved USER facts.
     - Applies to both `question` and `instruction`.
  4) **Fact-grounded summary fast-path**
     - `_one_line_summary_from_facts()` builds `k=v; k=v; ...` from resolved USER facts.
     - Triggered for summary-like instruction prompts.
  5) **Claim/slot-based contradiction detection**
     - Contradictions are detected by comparing extracted slots (not raw embedding drift alone).

### Fact slot extraction

- File: `personal_agent/fact_slots.py`
- Function: `extract_fact_slots(text)`
- Adds/uses slots including:
  - `name`, `employer`, `title`, `location`
  - `programming_years`, `first_language`
  - `team_size`, `remote_preference`
  - `masters_school`, `undergrad_school`

### Learned suggestions (optional)

- File: `personal_agent/learned_suggestions.py`
- Class: `LearnedSuggestionEngine`
- Notes:
  - **Suggestion-only**: never overwrites memories or resolves contradictions.
  - Loads optional model from env var `CRT_LEARNED_MODEL_PATH`.

### Training the learned suggestion model

- File: `crt_learn_train.py`
- Trains an sklearn pipeline (DictVectorizer → scaler → MLPClassifier), saved via joblib.
- Usage example:
  - `D:/AI_round2/.venv/Scripts/python.exe crt_learn_train.py --memory-db artifacts/crt_stress_memory.<runid>.db --ledger-db artifacts/crt_stress_ledger.<runid>.db --out artifacts/learned_suggestions.joblib`

### “Reflection” retraining runner

- File: `crt_reflect.py`
- Purpose: scheduled/batch job that scans `artifacts/` for runs and trains `artifacts/learned_suggestions.latest.joblib`.
- This **does not** mutate CRT memories or auto-resolve contradictions.

### Report builder for JSONL artifacts

- File: `artifacts/build_crt_stress_report.py`
- Purpose: reads latest `artifacts/crt_stress_run.*.jsonl` and writes a markdown report `artifacts/crt_stress_report.<runid>.md`.

## 2) Runtime config + environment variables

### Runtime config file

- File: `crt_runtime_config.json`
- Currently used values:
  - `learned_suggestions.enabled`: true
  - `learned_suggestions.emit_metadata`: true
  - `learned_suggestions.emit_ab`: true
  - `learned_suggestions.print_in_stress_test`: true
  - `learned_suggestions.write_jsonl`: true
  - `learned_suggestions.jsonl_include_full_answer`: true
  - `reflection.*`: controls `crt_reflect.py` training scan/output

### Config resolution order

- Implemented in `personal_agent/runtime_config.py`:
  1) explicit path passed to `load_runtime_config(path)`
  2) `CRT_RUNTIME_CONFIG_PATH`
  3) repo-root `./crt_runtime_config.json` (if present)
  4) defaults

### Learned model path

- Env var: `CRT_LEARNED_MODEL_PATH`
- Latest model artifact exists at:
  - `artifacts/learned_suggestions.latest.joblib`

## 3) What changed conceptually (thread narrative)

### Stress test length evolution

- Standardized stress harness default (30 turns), then extended to 40 and ultimately 50.
- Added a dedicated adversarial “pressure” block to try to break:
  - correction handling (snap-back regression)
  - prompt injection resistance
  - “forget everything” style attempts
  - compression/summary stability

### Why the injection hardening was added

Pressure runs revealed a key failure mode:
- Under injected prompts, the model would sometimes mention/accept old employer text (e.g., “Microsoft”) even after explicit correction to “Amazon”.

Hardening applied:
- Classify prompt-control text as `instruction` and do **not** store it as USER fact.
- Extend slot-fast-path to instruction prompts so “Where do I work?” stays grounded.
- Add a fact-grounded summary fast-path for summary-style instructions.

### Evaluator strictness tuning

- The pressure test initially banned the token `microsoft` entirely for Turn 41.
- That caused a false failure when the model *mentioned* it while refusing.
- Updated Turn 41 expectation to instead ban phrases that indicate acceptance (e.g., “you work at microsoft”).
- After that: full 50-turn run achieved **0 eval failures**.

## 4) Repo/test runner notes

### Pytest configuration

- File: `pytest.ini`
- Current behavior:
  - `python_files = test_*.py`
  - This avoids collecting many runnable `*_test.py` scripts.

### Known remaining issue (pytest may still fail)

- There are several `test_*.py` scripts at repo root (not just in `tests/`) that are not pytest-style unit tests.
- Example: `test_crt_conversation.py` defines functions named `test_*` taking a `rag` parameter but does not provide a pytest fixture, so pytest will error unless excluded.

Suggested fix options (choose one):
1) Add `testpaths = tests` to `pytest.ini` (limits discovery to `tests/` folder).
2) Rename root-level scripts to not match `test_*.py`.
3) Convert those scripts into real pytest tests with proper fixtures.

## 5) Quick start on another machine

1) Ensure Python venv + deps:
   - `python -m venv .venv`
   - `.venv/Scripts/pip install -r requirements.txt`

2) Ensure Ollama is installed and the model is available:
   - Default model in stress test: `llama3.2:latest`

3) (Optional) point at learned model:
   - `set CRT_LEARNED_MODEL_PATH=artifacts/learned_suggestions.latest.joblib`

4) Run the 50-turn pressure test:
   - `D:/AI_round2/.venv/Scripts/python.exe crt_stress_test.py --turns 50 --sleep 0.02 --config crt_runtime_config.json`

5) Build a markdown report from the latest JSONL:
   - `D:/AI_round2/.venv/Scripts/python.exe artifacts/build_crt_stress_report.py`

## 6) Recommended next work (if continuing)

- Tighten/measure “policy” pressure behavior:
  - Add eval expectations for Turn 49 (currently it’s informational and the model can respond inconsistently about how it would behave).
- Make pytest green by formalizing test discovery scope (`testpaths=tests`) or cleaning up root-level `test_*.py` scripts.
- If moving toward production:
  - add privacy controls for stored personal facts, retention controls, encryption-at-rest options, and explicit threat model for prompt injection.

---

Handoff authoring note: This snapshot reflects the state after the successful run producing `artifacts/crt_stress_run.20260110_090237.jsonl` with 0 eval failures.

---

## 7) Handoff assessment (verified on macOS, 2026-01-10)

This section was added by an automated review pass to confirm what’s true in the current repo checkout and to flag drift.

### ✅ What I verified

- **Repo has only a stray `.DS_Store` change** (`git status` shows `.DS_Store` modified).
- **Pytest is green after minor hygiene fixes**:
  - `271 passed, 2 skipped` (warnings only).
  - The skips are for script-style files that were being (incorrectly) collected as pytest tests.

### ⚠️ Mismatches / drift vs this handoff

- `pytest.ini` referenced above **does not exist** in this repo checkout. Test behavior is currently controlled by pytest defaults.
- `crt_stress_test.py` currently contains a guardrail:
  - `if metrics['total_turns'] >= 30: return None`
  - That means the script **won’t actually run 50 turns** unless that guardrail has been updated elsewhere (or this file was different on the machine that produced the Windows run noted above).

### 🧪 Why pytest was failing initially (and what was done)

`pytest` initially failed during collection because some root-level, script-style files matched `test_*.py` and executed on import.

Fix applied (minimal, low-risk):
- `test_fresh_provenance.py`: now **skips during pytest collection** and remains runnable as a script.
  - Optional env override: `SSE_FRESH_INDEX_PATH`.
- `test_crt_conversation.py`: now **skips during pytest collection**; it’s an Ollama-dependent integration script and not a unit test.

### 🧯 Environment risk noted

- Disk was tight during the first full pytest run (`/` at ~97% used, ~441MiB free). A transient "No space left on device" was observed once, then the test passed on rerun.

### Recommended next steps (highest ROI)

1) **Decide how you want 50-turn pressure runs to work in this repo**:
   - Either remove/parameterize the `>= 30` hard stop in `crt_stress_test.py`, or run a separate harness that truly supports `--turns 50`.
2) Add a real pytest config (optional), e.g. `pytest.ini` or `pyproject.toml`, to codify test discovery and avoid root script collection surprises.
3) Consider ignoring `.DS_Store` repo-wide (and removing from git) to keep diffs clean.
