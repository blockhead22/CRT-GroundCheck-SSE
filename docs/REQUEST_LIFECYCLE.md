# How a Request Flows Through CRT

This document traces a user message from arrival to response delivery, referencing the actual code paths in `routes/chat.py`.

## Overview

```
User sends message
    |
    v
1. Authentication & Session Setup
2. Request Classification
3. Delegation Check (OpenClaw handoff)
4. Special-Case Routing (self-referential, meta-awareness, reminders)
5. Memory Retrieval
6. Prompt Assembly
7. LLM Generation
8. Mid-Stream Verification (streaming path)
9. Gate Check & Trust Updates
10. Response Delivery
11. Background Bookkeeping
```

## Step-by-Step

### 1. Authentication & Session Setup

Entry point: `chat_send()` at `routes/chat.py:1907`

- Resolve authenticated `user_id` from the `Authorization` header
- Propagate `user_id` into the memory system's context variable (`_request_user_id`) so all memory writes during this request are tagged
- Get or create the `CRTEnhancedRAG` engine for the thread via `get_engine(thread_id)`
- Load runtime config
- Initialize `ResponseControlState` for pipeline tracing
- Update session activity, generate greeting if the user has been away
- Increment turn counter

### 2. Request Classification

The system classifies the incoming message:

- **follow_up** — matches patterns like "tell me more", "continue", "about that"
- **meta_provenance** — asking about where an answer came from
- **architecture_explanation** — asking how CRT/Aether works
- **contradiction_inventory** — asking about stored contradictions
- **direct** — everything else

This classification affects which code path handles the response.

### 3. Delegation Check

Before CRT processes the message itself, it checks whether to delegate to OpenClaw (an external agent gateway) for tool-heavy or research tasks. Keywords like "research", "investigate", "look up" trigger this check.

If delegated: the message is forwarded to OpenClaw with CRT context injected, and the response is returned directly.

### 4. Special-Case Routing

Several message types bypass the normal generation pipeline:

- **Self-referential questions** ("how do you work?", "what are you?") — handled by `_answer_self_referential()` at line 1214, which injects the 7-slot self-model and system knowledge into the LLM prompt
- **Meta-awareness prompts** ("what do you know about me?") — uses `build_meta_awareness_snapshot()` to produce a structured summary
- **Reminder requests** ("remind me in 30 minutes") — extracts the reminder via `extract_reminder_from_message()` and schedules it
- **Expand/continue** — retrieves the previous response from session state and asks the LLM to elaborate

### 5. Memory Retrieval

For direct queries, the engine retrieves relevant memories:

```python
# In CRTMemorySystem.retrieve_memories() at crt_memory.py:1508
# Scoring: R_i = similarity * recency * belief_weight * tier_weight
# where:
#   similarity = cosine similarity (with query expansion for slot patterns)
#   recency = exp(-age / 604800)  # 7-day lambda
#   belief_weight = 0.7 * trust + 0.3 * confidence
#   tier_weight = {0: 0.85, 1: 0.95, 2: 1.0}  # compression tier penalty
```

The retrieval is user-scoped (memories are filtered by `user_id`) and excludes deprecated memories, resolved contradiction losers, and memories below the trust threshold.

### 6. Prompt Assembly

The engine assembles a full prompt containing:

- System identity instructions (who Aether is, how to behave)
- Retrieved memories formatted as numbered facts with trust scores
- Self-model top facts (from the reflection loop)
- Conversation history (recent turns)
- Style profile (verbosity, tone, hedging level)
- The user's message

If the request is routed to a cloud provider, the prompt is scrubbed: trust metadata is redacted, PII slots on the deny list are removed, and the prompt is truncated to `max_context_chars`.

### 7. LLM Generation

The `HybridLLMClient` routes generation to the appropriate provider:

- **local:** (default) — Ollama with the configured model (e.g., `qwen2.5-coder:14b`)
- **cloud:** — OpenAI-compatible API (gpt-4o-mini, etc.)
- **anthropic:** — Claude via Anthropic API

Model selection can use role-based routing: `role:answer` looks up `model_roles["answer"]` which might resolve to `anthropic:claude-sonnet-4-6`.

### 8. Mid-Stream Verification (Streaming Path)

For the SSE streaming endpoint (`POST /api/chat/stream`), the `StreamVerifier` runs checkpoints every ~150 tokens:

**Check 1: Think Tag Leak** — Regex scan for `<think>` tags that leaked into visible output. Action: strip them.

**Check 2: Fact Contradiction** — String matching against retrieved memories. If the response contradicts a stored fact, the stream is stopped.

**Check 3: Repetition Detection** — Sentence dedup to catch generation loops. Action: stop on excessive repetition.

Each checkpoint emits an SSE event (`stream_checkpoint`) so the frontend can display pipeline trace information.

Reference: `personal_agent/stream_verifier.py`

### 9. Gate Check & Trust Updates

After generation completes:

- **Contradiction caveat detection** — regex scan for phrases like "most recent", "conflicting", "however" that indicate the LLM is hedging about contradictory data
- **Self-correction check** — if the answer says "I don't know" but retrieved memories contain relevant data, emit a correction
- **Trust updates** — memories that were cited in the answer get trust reinforcement; memories that were contradicted get trust reduction
- **Belief/speech tracking** — the response is logged with whether it represents a belief (high-confidence, backed by trusted memory) or speech (tentative, lower confidence)
- **Fact extraction** — new facts mentioned by the user are extracted and stored as memories

### 10. Response Delivery

The response object includes:

- `answer` — the generated text
- `response_type` — "memory", "uncertainty", "greeting", "meta_awareness", etc.
- `gates_passed` — boolean indicating whether verification passed
- `gate_reason` — explanation if gates failed
- `metadata` — pipeline trace, timings, stream verification summary, interaction ID
- `xray` — optional debug data (retrieved memories, scores)

### 11. Background Bookkeeping

After the response is sent, background tasks run:

- Episodic memory recording (conversation turns → episodic store)
- Active learning coordinator updates (what the system learned from this interaction)
- Collapse trail logging (audit trail for how the response was constructed)
- GroundCheck bridge sync (if enabled, syncs facts to the verification database)

These run in a separate thread to avoid blocking the response.

## The Streaming Path vs Sync Path

- `POST /api/chat/send` — synchronous, returns complete JSON response
- `POST /api/chat/stream` — SSE stream with phases: `thinking`, `answer`, `done`

Both paths share the same core logic (memory retrieval, prompt assembly, generation) but the streaming path adds:
- Token-by-token delivery
- Mid-stream verification checkpoints
- Phase events for frontend pipeline visualization
- Think tag stripping in real-time
