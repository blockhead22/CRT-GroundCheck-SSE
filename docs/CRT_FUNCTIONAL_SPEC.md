# CRT Functional Specification (Rigorous)

This document defines **expected behavior** for each major user-facing function of CRT.

Conventions used below:
- **Inputs**: what the UI/user provides
- **Outputs**: what the user sees or what the system returns
- **Side effects**: DB writes, artifacts, state changes
- **Failure modes**: common problems and what should happen
- **Acceptance checks**: quick manual checks to validate behavior

---

## 0) Unified app entrypoint

### Feature: Unified Streamlit app (Chat + Dashboard)

- **Where:** `crt_app.py` (with Streamlit multipage wrappers in `pages/`)
- **Inputs:** user selects a page in Streamlit sidebar (Chat or Dashboard)
- **Outputs:** renders the selected page inside a single Streamlit server
- **Side effects:** none (aside from whatever the selected page does)
- **Failure modes:**
  - Port already in use → Streamlit should display an error; user should choose a new port.
- **Acceptance checks:**
  - `streamlit run crt_app.py` shows **Chat** and **Dashboard** in sidebar.

---

## 1) Chat UI (Streamlit)

### Feature: Message send / response display

- **Where:** `crt_chat_gui.py`
- **Inputs:** user types a message; optional “⭐ Important” checkbox
- **Outputs:**
  - A final assistant message (authoritative)
  - Badges:
    - **BELIEF** if gates pass
    - **SPEECH** otherwise
    - **CONTRADICTION** if conflict detected
  - Optional metadata expander
- **Side effects:**
  - May write memories to Memory DB
  - May write contradiction entries to Ledger DB
- **Failure modes:**
  - LLM unavailable (Ollama not running / model missing) → UI should show a clear initialization error and setup instructions.
  - DB path invalid/unwritable → initialization should fail fast with a clear error.
- **Acceptance checks:**
  - Send a normal message; see a CRT response and a SPEECH/BELIEF badge.

### Feature: DB path configuration

- **Where:** Chat sidebar “🗄️ Storage”
- **Inputs:** Memory DB path; Ledger DB path
- **Outputs:** CRT system restarts with new DBs
- **Side effects:**
  - May create new sqlite files/directories
  - Clears cached CRT resource; reinitializes system
- **Failure modes:**
  - Non-writable directory → error shown on initialization
- **Acceptance checks:**
  - Change DB paths; verify the system reinitializes and uses new empty DBs.

### Feature: Streaming draft preview (best-effort)

- **Where:** Chat sidebar toggle “Stream draft preview”
- **Inputs:** toggle on/off; “Use memory context in draft” toggle
- **Outputs:**
  - Live-updating draft message while CRT computes final answer
  - Final answer replaces the draft
- **Side effects:** none (preview does not write to DB)
- **Expected behavior:**
  - Draft is explicitly non-authoritative.
  - If enabled, draft should be grounded by retrieved memory context when possible.
- **Failure modes:**
  - Underlying LLM client doesn’t support streaming → draft falls back to a single non-stream response.
- **Acceptance checks:**
  - Enable streaming; ask a question using known memory; draft should usually reflect memory.

---

## 2) CRT core pipeline (query lifecycle)

### Feature: Trust-weighted retrieval

- **Where:** `personal_agent/crt_rag.py` (`retrieve`)
- **Inputs:** query text; top-k; min_trust
- **Outputs:** ordered list of memories with scores
- **Side effects:** none (retrieval itself)
- **Expected behavior:**
  - Derived helper outputs are filtered out (prevents recursive prompt pollution).
- **Failure modes:**
  - Empty DB → returns empty list
- **Acceptance checks:**
  - With demo data, retrieval returns relevant memories for a query.

### Feature: Contradiction detection + ledger recording

- **Where:** `personal_agent/crt_rag.py`, `personal_agent/crt_ledger.py`
- **Inputs:** new user text + retrieved/prior memory context
- **Outputs:**
  - `contradiction_detected` flag in result
  - optional contradiction metadata for UI
- **Side effects:**
  - Writes contradiction entries to ledger DB when conflicts are detected
- **Expected behavior:**
  - Conflicts are preserved; old memories are not deleted/overwritten.
  - Unrelated open contradictions should not stall unrelated chat.
- **Failure modes:**
  - Ledger DB locked/unavailable → contradiction recording fails; system should continue with best-effort answer and surface an error in logs/metadata if available.

### Feature: Reconstruction gates (BELIEF vs SPEECH)

- **Where:** `personal_agent/crt_rag.py`
- **Inputs:** candidate answer + memory context
- **Outputs:**
  - `gates_passed` boolean
  - `response_type`: belief/speech
  - `confidence`, alignment diagnostics
- **Side effects:** may influence what gets stored/promoted
- **Expected behavior:**
  - Provenance claims about memory usage should align with `gates_passed`.

### Feature: Deterministic slot extraction + slot Q&A

- **Where:** `personal_agent/fact_slots.py`, `personal_agent/crt_rag.py`
- **Inputs:** user statements/questions
- **Outputs:** extracted slot values; deterministic slot answers where applicable
- **Supported slots (current):** at least `name`, `favorite_color` (and others depending on repo state)
- **Expected behavior:**
  - Slot answers should prefer stored text; avoid hallucination.
  - Name variants (e.g., prefix vs full name) should not create noisy contradictions.
- **Acceptance checks:**
  - Store: “My favorite color is orange.”
  - Ask: “Do you recall my favorite color?” → answer “orange”.

---

## 3) Dashboard (Streamlit)

### Global behavior

- **Where:** `crt_dashboard.py`
- **Inputs:** page selection in sidebar
- **Outputs:** charts/tables/controls for the selected page
- **Side effects:** some pages can write artifacts / apply changes
- **Failure modes:**
  - Missing DB → dashboard should initialize a new one or fail with a clear error.

### Page: 🏥 System Health

- **Inputs:** none (read-only)
- **Outputs:** summary metrics (memory counts, contradiction stats, etc.)
- **Side effects:** none

### Page: 📈 Trust Evolution

- **Inputs:** optional filters (memory id)
- **Outputs:** trust-history plots/tables
- **Side effects:** none

### Page: ⚠️ Contradictions

- **Inputs:** filters/sort
- **Outputs:** list of contradictions with details (drift, summary)
- **Side effects:** none (view-only)

### Page: 💭 Belief vs Speech

- **Inputs:** none/filters
- **Outputs:** gate pass rates / ratios / charts
- **Side effects:** none

### Page: 🔍 Memory Explorer

- **Inputs:** search query, filters, sorting
- **Outputs:** memory table + details
- **Side effects:** none (unless there are edit tools enabled elsewhere)

### Page: ✅ Promotion Approvals

- **Purpose:** governance workflow for applying promotion decisions.
- **Inputs:**
  - Proposals/decisions paths
  - dry-run vs real apply
  - sandbox DB creation
- **Outputs:**
  - preview of changes
  - apply results + audit artifacts
- **Side effects:**
  - writes sandbox DB files
  - may apply changes to target memory DB
  - writes decision/apply-result artifacts
- **Expected behavior:**
  - Dry-run should not mutate target DB.
  - Real apply should be explicitly gated/confirmed.

### Page: 🧠 Learned Model

- **Purpose:** manage suggestion-only learned model lifecycle.
- **Inputs:** thresholds, artifact directories, eval-set selection
- **Outputs:** model timelines, eval metrics, publish status
- **Side effects:**
  - trains models, writes joblib artifacts
  - writes `.meta.json` and `.eval.json` sidecars
  - may update `learned_suggestions.latest.joblib` on pass

### Page: 📚 Docs / FAQ / Architecture

- **Purpose:** render this spec + architecture + FAQ + repo reference docs.
- **Inputs:** which doc to open
- **Outputs:** in-app documentation
- **Side effects:** none

---

## 4) Demo / Data population

### Feature: Populate demo data

- **Where:** `populate_crt_demo_data.py`
- **Inputs:** (script options may vary)
- **Outputs:** demo memories/contradictions in DB
- **Side effects:** writes to DB
- **Acceptance checks:**
  - Run once; dashboard shows non-empty metrics.

---

## 5) Stress + evaluation harness

### Feature: Adaptive stress test runner

- **Where:** `crt_adaptive_stress_test.py`
- **Inputs:** turns/runs/seed/challenge pack
- **Outputs:** artifact directory with run logs/results
- **Side effects:** writes test DBs + artifacts
- **Expected behavior:**
  - deterministic packs (like `ux`) should be repeatable with the same seed.

---

## 6) Configuration surface (current)

- `CRT_DB_DIR` (chat UI convenience for DB location, if set)
- Streamlit server options: `--server.port`, `--server.address`
- Ollama must be running for LLM-backed features

---

## 7) Validation checklist (manual)

1. Launch unified app.
2. In Chat, store and recall a slot fact (favorite color).
3. Create a deliberate name conflict; verify uncertainty is scoped.
4. In Dashboard, verify all pages load without exceptions.
5. In Promotion Approvals, run a dry-run in sandbox and verify no real DB mutation.
6. In Learned Model, run a dry-run publish pipeline and verify artifacts are written.
