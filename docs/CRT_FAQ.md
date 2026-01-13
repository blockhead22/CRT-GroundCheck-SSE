# CRT FAQ (Dashboard-Embedded)

This FAQ is intended to be shown inside the Streamlit dashboard. It focuses on **expected behavior** and **how to interpret what you’re seeing**.

---

## What do the badges mean in Chat?

- **BELIEF**: the response passed reconstruction gates (intent + memory alignment). It is meant to be stable and grounded.
- **SPEECH**: the response did not pass gates. It is a best-effort conversational response and may be less reliable.
- **CONTRADICTION**: the system detected (and recorded) conflicting information relevant to the interaction.

---

## Why does CRT sometimes say it’s uncertain?

CRT becomes explicitly uncertain when there are **unresolved contradictions relevant to what you asked** (especially for personal-profile slots like name).

Expected behavior:
- If you ask about a conflicted slot (“What’s my name?”) and there’s a hard conflict, CRT should ask for clarification or acknowledge the conflict.
- If you say unrelated smalltalk (“Hello again!”), unrelated contradictions should not block a normal response.

---

## Why can streaming show something wrong and then the final answer changes?

The streaming output is a **draft preview**. The full CRT response requires retrieval, contradiction checks, and gates.

Expected behavior:
- The final answer may differ from the draft.
- The UI should make it clear the draft is non-authoritative.
- (Recommended) the draft preview should be grounded with retrieved memories when possible.

---

## Why does CRT retrieve a memory but still say “I don’t know”?

Common causes:
- The memory was retrieved but **did not survive gating** for the final response.
- The system did not recognize the question as asking for a **supported slot**.

Expected behavior:
- For supported slots (e.g., `favorite_color`), if memory contains a clear fact, CRT should answer deterministically from stored text.
- Provenance/footer text should not claim memory grounding if gates failed.

---

## What is “trust” and how does it change?

- **Trust** is a slow-changing belief strength (0..1).
- **Confidence** is the local certainty at creation time.

Expected behavior:
- High-trust memories should be preferred in retrieval.
- Contradictions do not delete old memories; they can cause trust to adjust over time.

---

## What does “Promotion Approvals” do?

It supports a governance workflow for applying proposed memory promotions:
- load proposal artifacts
- review decisions (approve/reject)
- run dry-run against a sandbox DB
- apply to the real DB (gated)

Expected behavior:
- You can inspect what will change before applying.
- Apply writes an audit artifact (apply result JSON).

---

## What is the “Learned Model” section?

It tracks the suggestion-only learned model lifecycle:
- Train → Eval → Publish (gated)
- Uses sidecar metadata and eval artifacts

Expected behavior:
- Publishing only happens when thresholds pass.
- The “latest” model pointer updates only after successful gated publish.

---

## Where are the databases stored?

Defaults:
- Memory DB: `personal_agent/crt_memory.db`
- Ledger DB: `personal_agent/crt_ledger.db`

Chat UI can be configured to point at other DB paths (useful for demos / per-user sessions).

---

## Troubleshooting

### Ollama errors
- Start server: `ollama serve`
- Pull model: `ollama pull llama3.2`

### Streamlit port already in use
- Run on a different port: `streamlit run crt_app.py --server.port 8505`

