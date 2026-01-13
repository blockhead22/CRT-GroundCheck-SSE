# CRT System Architecture (Dashboard-Embedded)

This document is the **authoritative architecture reference** for the CRT (Cognitive‑Reflective Transformer) system in this repo.

## 1) What CRT is (in one paragraph)

CRT is a **memory-first personal assistant** that prioritizes **coherence over time**. It stores user-provided information as memories with **trust** and **confidence**, retrieves them with a trust-weighted scorer, detects contradictions (and records them rather than overwriting), and uses **reconstruction gates** to decide whether an output can be promoted to a stable **BELIEF** or should remain a cautious **SPEECH** fallback.

---

## 2) System goals & invariants (expected behavior)

### Hard invariants
- **No silent overwrite:** conflicting user facts are preserved as separate memories; a ledger entry records the conflict.
- **Honest provenance:** UI/provenance should not claim "used stored memories" unless the gates for reconstruction passed.
- **Uncertainty is scoped:** unresolved contradictions should only block/soften answers when they are **relevant to the user’s current question**.
- **Deterministic safe paths:** for certain personal slots (e.g., name, favorite_color), the system prefers deterministic extraction/answers grounded in stored text over hallucination.

### Soft goals
- **Coherence > single-shot accuracy** when personal facts are involved.
- **Recoverability:** the user can inspect what was stored, how it was retrieved, and what contradictions exist.

---

## 3) Core components

### 3.1 Memory Store (SQLite)
- **Purpose:** durable storage of memories, their embeddings, trust/confidence, source, and metadata.
- **Key behaviors:**
  - retrieval returns top‑k memories using similarity + recency + trust weighting.
  - trust can evolve via logged updates.

### 3.2 Contradiction Ledger (SQLite)
- **Purpose:** persistent record of conflicts between memories (old vs new) plus drift metrics and summaries.
- **Key behaviors:**
  - contradictions are *tracked*, not merged.
  - contradictions can be queried for open/unresolved status.

### 3.3 Retrieval + Prompt Assembly
- **Purpose:** find the most relevant memories, then assemble a context that is safe and helpful.
- **Key behaviors:**
  - filters out derived helper outputs from being re-ingested as “facts” (prevents recursive quoting/prompt pollution).
  - can build **resolved memory docs** that prefer high-signal `FACT:` lines.

### 3.4 Reconstruction Gates (BELIEF vs SPEECH)
- **Purpose:** determine whether a response is aligned with user intent and memory evidence.
- **Expected behavior:**
  - **BELIEF:** gates pass; response is grounded and stable.
  - **SPEECH:** gates fail; response is a best-effort conversational fallback.

### 3.5 Slot extraction (deterministic)
- **Purpose:** extract durable user-profile fields from text (e.g., `name`, `favorite_color`).
- **Expected behavior:**
  - when a slot is available, answering should be deterministic and should not contradict stored text.
  - spelling variants are handled where applicable (e.g., color/colour).

### 3.6 Reasoning engine (+ streaming preview)
- **Purpose:** generate answers in modes (quick/thinking/deep), optionally streaming a draft.
- **Important UI contract:**
  - the **final CRT answer** (post retrieval + gates + contradiction checks) is authoritative.
  - any streaming output is a **draft preview** and may differ.

---

## 4) End-to-end request lifecycle

1. **User input** arrives (Chat UI or test harness).
2. **Retrieve** candidate memories (trust-weighted).
3. **Detect contradictions** relevant to retrieved evidence and/or inferred slots.
4. **Attempt deterministic slot answer** when appropriate.
5. **Generate candidate response** (LLM) with memory context.
6. **Apply gates** to decide BELIEF vs SPEECH.
7. **Write outputs**: store memory updates (as appropriate), record contradictions, attach metadata.
8. **UI renders**: answer + badges + optional metadata.

---

## 5) Where to look in the code

- CRT core pipeline: `personal_agent/crt_rag.py`
- Memory store: `personal_agent/crt_memory.py`
- Contradiction ledger: `personal_agent/crt_ledger.py`
- Slot extraction: `personal_agent/fact_slots.py`
- Reasoning/streaming: `personal_agent/reasoning.py`
- Chat UI: `crt_chat_gui.py`
- Dashboard UI: `crt_dashboard.py`

---

## 6) Operational notes

### Databases
- Default DBs:
  - `personal_agent/crt_memory.db`
  - `personal_agent/crt_ledger.db`

### Common failure modes
- Ollama not running / model missing → the system can’t generate LLM responses.
- Port conflicts for Streamlit → launch on a different port.

---

## 7) Glossary
- **Memory:** stored user/system text with trust/confidence and metadata.
- **Trust:** slowly changing belief strength.
- **Confidence:** local certainty at creation time.
- **BELIEF:** gated, memory-aligned output.
- **SPEECH:** ungated fallback output.
- **Contradiction:** recorded conflict between two memories.
- **Slot:** deterministic profile field (name, favorite_color, etc.).
