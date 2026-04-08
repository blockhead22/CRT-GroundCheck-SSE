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

### 5. Cloud governance demotion uses flat 0.4x multiplier
**Severity:** Low (partially mitigated)
**Discovered:** 2026-04-08
**Symptom:** The cloud governance demotion in `routes/chat.py` applies `trust * 0.4` to all conflicting memories. No damping, no depth bounds, no BDG cascade consultation.
**Root cause:** The demotion was written before the BDG cascade system existed. The text search was rewritten to use `memory_facts` (incident fix), but the flat multiplier remains.
**Fix estimate:** Wire demotion through BDG cascade. Medium effort.
**Mitigated by:** Text search → memory_facts rewrite prevents cascade destruction (81-memory incident). Flat multiplier only hits structured slot matches now.
