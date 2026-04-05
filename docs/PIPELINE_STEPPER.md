# Aether Pipeline Stepper — Full 12-Step Reference

Each step in the Aether agentic loop, with source files, what it does, what data flows through, and what Claude Code does NOT have at this stage.

---

## Step 1: Input
**Source:** `frontend/src/components/chat/Composer.tsx`

User types a message. Composer handles:
- Text input with auto-grow textarea
- File/folder/image attachments (drag, paste, or picker)
- Generation mode selection (local/network/cloud_openai/cloud_claude)
- Predictive ghost text (Tab to accept)
- Spellcheck via Electron context menu

**Data out:** `{ message, generationMode, attachedPaths[], cloudModel }`

**vs Claude Code:** Similar input handling. Aether adds predictive text + model selector in composer.

---

## Step 2: Intent Classify
**Source:** `personal_agent/task_agent.py` → `classify_intent_hybrid()`

Three-tier classification:
1. **Regex** (instant, 0ms) — 26 patterns for file ops, web search, code search, desktop, reminders
2. **LLM Router** (local llama3.2, ~3-15s) — function-calling with 21 tool schemas
3. **Cloud Fallback** (OpenAI gpt-4o-mini) — when local fails

Also checks: route learning cache, pre-filter (greetings/opinions/short messages)

**Data out:** `TaskIntent { route, intent_type, slots, confidence, reason, source }`

**vs Claude Code:** Claude Code has no intent classification. Every message goes to the same API call. Aether routes differently based on what you're asking.

---

## Step 3: Routing Beliefs
**Source:** `personal_agent/routing_beliefs.py` → `should_orchestrate()`

12 structural extractors score the message:
- `state_change_verb` — "create", "build", "fix" (+0.25)
- `transformation_verb` — "rewrite", "convert", "format" (+0.30)
- `information_verb` — "what is", "explain" (-0.25)
- `system_resource` — mentions files, code, directories (+0.24)
- `compound_intent` — multiple clauses, "then", "and also" (+0.45)
- `question_form` — ends with "?" (-0.40)
- `imperative_form` — starts with verb (-0.13)
- `abstract_target` — philosophical/vague (-0.38)
- `message_complexity` — length, clause count (+0.15)

Scores aggregate into: orchestrator vs conversational vs agent_loop

**Data out:** `RoutingDecision { route, confidence, reasons[] }`

**vs Claude Code:** Does not exist. Claude Code sends everything to the same endpoint.

---

## Step 4: Route Decision
**Source:** `routes/chat.py` → agent loop gate (~line 6930)

Four possible paths:
- **Agent Loop** — LLM-driven autonomous tool loop (for task intents)
- **Orchestrator** — Claude CLI brain with full tool access (for complex multi-step)
- **Legacy Pipeline** — classify-once-execute-blind (for memory-only: broad_recall, system_info)
- **Conversational** — direct LLM generation with memory context

Guards:
- `_MEMORY_ONLY_INTENTS` bypass agent loop (broad_recall, system_info)
- `model_ok` check (can the selected provider run the loop?)
- Pure transformation detection (skip orchestrator, go direct)
- Layer 4 override (routing beliefs can force orchestrator)

**Data out:** Which path to execute

**vs Claude Code:** Claude Code always takes one path. Aether has four governed paths.

---

## Step 5: Memory Retrieval
**Source:** `personal_agent/crt_rag.py` → RAG pipeline

For every request, retrieve relevant memories:
1. Embed the query (all-MiniLM-L6-v2, 384 dimensions)
2. Cosine similarity search against memory DB (704+ memories)
3. Alias boost — canonical memories get priority (+0.1 score)
4. Trust weighting — higher trust memories rank higher
5. Topic boost — if memory matches detected topic
6. Filter — remove deprecated, low-trust, model-output sources
7. Trim to context budget (k=5 for simple, k=60 for broad)

**Data out:** `retrieved_memories[]` with scores, trust, kind, text

**vs Claude Code:** Claude Code has no persistent memory across sessions. Aether has 704+ memories with trust scores, contradiction tracking, and alias resolution.

---

## Step 6: Governance Gate (Pre-Generation)
**Source:** `routes/chat.py` → governance section (~line 3800+)

Before the LLM generates, check:
1. **Slot Classification** — is this a fact assertion? What slot? (via OpenAI or local)
2. **NLI Critic** — does the response contradict known beliefs? (pass/hedge/fail)
3. **Belief/Speech Gap Audit** — is the system about to say something it doesn't believe?
4. **Trust Threshold** — are the cited memories trustworthy enough?

Can block, hedge, or pass the generation.

**Data out:** `{ gates_passed, gate_reason, governance_tier }`

**vs Claude Code:** Does not exist. No pre-generation governance.

---

## Step 7: Brain (LLM Generation)
**Source:** `personal_agent/litellm_client.py` → `chat_with_tools()`

The LLM receives:
- **Static epistemology prefix** (6 axioms, cache-pinned)
- **Dynamic evidence** (retrieved memories, recent history)
- **Self-model** (top 3 trust-weighted self-awareness facts)
- **Tool schemas** (gated by intent — 4 tools for conversational, 16 for tasks)
- **System prompt** with personality, conversation history, context

Brain selection:
- Local: qwen3:14b via Ollama
- Cloud: Claude Sonnet via CLI, or OpenAI via API
- Fallback chain: local → Anthropic → OpenAI → cookie

**Data out:** `{ content, tool_calls[], generation_source }`

**vs Claude Code:** Similar API call, but Aether injects epistemology, self-model, and memory context. Claude Code uses a static system prompt.

---

## Step 8: Tool Call
**Source:** `personal_agent/agent_tool_loop.py` → `_execute_tool()`

If the LLM requested a tool:
1. **Tool Gate** — is this tool allowed for this intent type?
2. **Checkpoint** — does this tool need user confirmation? (Layer 3-4 tools do)
3. **Execute** — run the tool (file read, search, shell, web, memory)
4. **Action Receipt** — log what was done (who, what, when, result)
5. **Verify** — did the tool succeed? Was the result expected?
6. **Alignment Score** — how aligned is this tool call with the original request?

**Data out:** `{ tool_result, action_receipt, alignment_score, verified }`

**vs Claude Code:** Similar tool execution, but Aether adds action receipts, verification, and alignment scoring per tool call.

---

## Step 9: Loop / Drift Check
**Source:** `personal_agent/agent_tool_loop.py` + `personal_agent/agent_run_log.py`

After each tool call:
1. **Alignment Check** — is the agent drifting from the original request?
2. **Drift Flag** — if alignment drops below threshold, warn the user
3. **Repetition Guard** — if same tool called 3x, force answer
4. **Budget Check** — remaining iterations (plan doesn't consume slots)
5. **Auto-Continue** — if `complete:false`, spawn continuation (max 3)

If more work needed → back to Step 7 (Brain)
If done → proceed to Step 10

**Data out:** `{ continue, drift_detected, alignment_avg, iterations_remaining }`

**vs Claude Code:** Claude Code loops but has no drift detection, no alignment scoring, no repetition guard with forced answer.

---

## Step 10: Response Governance (Post-Generation)
**Source:** `routes/chat.py` → post-generation governance (~line 4500+)

After the final response:
1. **Trust Delta** — how did trust change this turn?
2. **Contradiction Check** — does this response contradict existing memories?
3. **Memory Write** — if a new fact was detected, store it with provenance
4. **Session State Update** — cumulative density, open contradictions, turn count
5. **Leaked Error Check** — if an error string leaked into the response, catch and fallback

**Data out:** `{ final_answer, trust_delta, new_memories[], session_state }`

**vs Claude Code:** Does not exist. No post-generation governance, no trust tracking, no memory writes.

---

## Step 11: Stream (SSE/WebSocket)
**Source:** `routes/chat.py` → SSE emission + `routes/ws.py` → WebSocket registry

Real-time events streamed to frontend:
- `token` — response text chunks
- `intent_preview` — what the system thinks you're asking
- `tool_start` / `tool_result` — tool execution progress
- `thinking` — agent reasoning (italic in pipeline panel)
- `drift` — alignment shift detected
- `session_state` — density + contradiction count
- `retrieval` — which memories were cited
- `trust_shift` — trust changes
- `followup_suggest` — suggested next questions
- `done` — final response with metadata

**Data out:** SSE event stream to browser

**vs Claude Code:** Similar streaming, but Aether streams governance events (drift, trust, contradictions) that Claude Code doesn't have.

---

## Step 12: Await
**Source:** `frontend/src/App.tsx` → stream handlers

Frontend receives and renders:
- Pipeline collapse panel (expandable trace of all steps)
- Trust delta strip (green/red trust changes)
- Memory citation badges (which memories were used)
- Governance indicators (belief tier, generation source)
- Followup suggestion chips (clickable next questions)
- Message rating bar (user feedback)

System is now idle, waiting for next input → back to Step 1.

**Data out:** Rendered UI state

**vs Claude Code:** Similar rendering, but Aether shows governance metadata (trust, drift, citations, belief tier) that Claude Code doesn't expose.

---

## Summary: What Aether Has That Claude Code Doesn't

| Capability | Claude Code | Aether |
|---|---|---|
| Intent Classification | No | 3-tier (regex/LLM/cloud) |
| Routing Beliefs | No | 12 structural extractors |
| Persistent Memory | No | 704+ memories, trust-scored |
| Pre-Generation Governance | No | Slot classify, NLI critic, gap audit |
| Drift Detection | No | Per-tool-call alignment scoring |
| Action Receipts | No | Every tool call logged with provenance |
| Post-Generation Governance | No | Trust delta, contradiction check, memory write |
| Belief/Speech Gap | No | Auditable gap between internal state and output |
| Self-Model | No | System knows its own strengths/weaknesses |
| Cascade Pressure | No | Formal model of how contradictions propagate |
| Multi-Model Brain | Single provider | Local/cloud/orchestrator with fallback chain |
| Auto-Continuation | No | Detects incomplete work, continues (max 3) |
