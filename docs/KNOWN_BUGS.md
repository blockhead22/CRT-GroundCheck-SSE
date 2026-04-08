# Known Bugs

Active bugs tracked for future sessions. Not blocking production use unless noted.

## Pipeline

### 1. Orchestrator JSON code fence parsing
**Severity:** Medium (cosmetic, affects user experience)
**Discovered:** 2026-04-08
**Symptom:** Raw JSON renders in the chat instead of the extracted message when the brain wraps its response in markdown code fences (```json ... ```). The `[PARSE] Failed to extract JSON` log line fires.
**Root cause:** The orchestrator response parser doesn't strip markdown code fences before `json.loads()`.
**Fix estimate:** ~5 lines in the orchestrator brain response parser.
**Workaround:** None. User sees raw JSON. The message content is correct inside the JSON.

### 2. T5/T9 pipeline hangs on specific probes
**Severity:** Medium (blocks lab runs, not normal usage)
**Discovered:** 2026-04-08
**Symptom:** Specific lab probes (T5: contextual color declaration, T9: third-party fact) consistently hang beyond 300s timeout regardless of network state. Other probes of similar length complete in 30-45s.
**Root cause:** Undiagnosed. Not network — confirmed by testing with stable connection. May be a pipeline interaction with specific content patterns or Ollama model loading.
**Fix estimate:** Unknown. Needs profiling of what the pipeline does differently for these messages.

### 3. Excessive Ollama calls per message
**Severity:** Low (performance, not correctness)
**Discovered:** 2026-04-08
**Symptom:** Every message triggers ~30+ local Ollama calls (gemma3) for background classification, intent routing, and various pipeline stages — even for simple greetings or questions that contain no facts.
**Root cause:** Architectural — the pipeline runs all stages unconditionally. No early-exit for messages that don't need fact extraction or contradiction checking.
**Fix estimate:** Proportional governance redesign. Not a quick fix.

## Memory / Contradiction

### 4. Slot exclusivity classification too broad
**Severity:** Low (correctness risk)
**Discovered:** 2026-04-08
**Symptom:** `favorite_drink` was classified as EXCLUSIVE in seed lists, but users naturally have multiple favorite drinks. Slot type classification needs context-aware handling (exclusive for `name`/`age`, additive for preferences that coexist).
**Root cause:** Static seed lists in `slot_discovery.py` don't distinguish between truly exclusive slots (name, age) and preference slots that can hold multiple values.
**Fix estimate:** Expand slot type system to support "primary + secondary" pattern. Medium effort.

### 6. Agent loop does not surface memories or contradictions
**Severity:** High (correctness — affects user experience on key intents)
**Discovered:** 2026-04-08
**Symptom:** When the agent loop path handles a message (instead of the legacy pipeline), no memories are cited in the response, no contradiction detection runs, and no pipeline steps are visible. The response generates without grounding in stored beliefs. This was visible in the "Clean memory audit feeling... wanna explain more" exchange — the legacy path showed `5 memories cited` but the agent loop path showed none for similar queries.
**Root cause:** The agent loop (`routes/chat.py` agent loop gate) uses its own tool-based flow (introspect, memory_recall, gpt_log_search) which only fires when the orchestrator explicitly decides to call those tools. If it doesn't call `memory_recall`, no memories are surfaced. The legacy pipeline always runs retrieval. The agent loop makes retrieval optional based on the brain's judgment.
**What needs investigation:**
- Which intents route through agent loop vs legacy? (Check `AGENT_LOOP_GATE` in logs)
- Does the agent loop ever create contradiction ledger entries? (Likely no — contradiction detection lives in `crt_rag.py` which only the legacy path calls)
- Intents that 100% SHOULD surface memories but may not: `conversational` (when layer4 orchestrator fires), `broad_recall`, any intent where the user references prior context
- The `[AGENT_LOOP_GATE] >>> LEGACY PATH (agent loop was skipped or failed)` vs `[ORCHESTRATOR] >>> ENTERING agent loop path` log lines show the split
**Fix estimate:** Medium-high. Either (a) make the agent loop always call memory_recall as a first step, or (b) inject retrieved memories into the agent loop's context automatically, or (c) run contradiction detection as a post-step after the agent loop completes.

### 5. Cloud governance demotion uses flat 0.4x multiplier
**Severity:** Low (partially mitigated)
**Discovered:** 2026-04-08
**Symptom:** The cloud governance demotion in `routes/chat.py` applies `trust * 0.4` to all conflicting memories. No damping, no depth bounds, no BDG cascade consultation.
**Root cause:** The demotion was written before the BDG cascade system existed. The text search was rewritten to use `memory_facts` (incident fix), but the flat multiplier remains.
**Fix estimate:** Wire demotion through BDG cascade. Medium effort.
**Mitigated by:** Text search → memory_facts rewrite prevents cascade destruction (81-memory incident). Flat multiplier only hits structured slot matches now.
