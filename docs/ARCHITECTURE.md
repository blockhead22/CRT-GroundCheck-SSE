# System Architecture

CRT/Aether is a trust-weighted AI assistant built around seven interconnected subsystems. All control logic runs locally; only generation can optionally route to cloud providers.

## The Seven Subsystems

### 1. Memory

Stores everything the system learns as trust-scored, vector-embedded memory items. Each memory carries a confidence score (fixed at creation), a trust score (evolves over time), a source tag, and an SSE (Significance-Stratified Encoding) mode.

**Key files:**
- `personal_agent/crt_memory.py` — `CRTMemorySystem` class: store, retrieve, trust update, dedup
- `personal_agent/crt_core.py` — `CRTMath`, `CRTConfig`, `SSEMode`, `MemorySource` definitions
- `personal_agent/crt_rag.py` — `CRTEnhancedRAG` orchestrator wrapping memory + ledger + LLM

**Calls:** Compression (tier transitions), Verification (contradiction check on store), Governance (trust thresholds)

### 2. Verification (GroundCheck / CRT-as-Critic)

Post-generation verification that catches contradictions, hallucinations, and think-tag leaks before the response reaches the user. Operates at two levels: pre-delivery gate checks and mid-stream checkpoint verification.

**Key files:**
- `personal_agent/stream_verifier.py` — `StreamVerifier`: mid-stream checkpoint checks (think leak, fact contradiction, repetition)
- `personal_agent/cloud_features.py` — `CloudFeatureService`: cloud-backed NLI contradiction detection, slot classification, reflection validation
- `packages/groundcheck/` — Vendored verification library for sub-2ms fact checking

**Calls:** Memory (retrieves stored facts for comparison), Cloud Routing (escalates to cloud NLI when local confidence is low)

### 3. Reflection (Heartbeat / Self-Model)

A periodic self-awareness loop that runs on a configurable interval (default 30 minutes). Each heartbeat cycle gathers evidence from recent interactions (gate failures, negative feedback, trust deltas, open contradictions), calls an LLM to produce a self-assessment, and updates the 7-slot self-model.

**Key files:**
- `personal_agent/heartbeat_system.py` — `HeartbeatScheduler`: daemon thread that triggers per-thread heartbeats
- `personal_agent/self_model.py` — `SelfModel`: 7-slot persistent self-knowledge (stored as CRT memories with `kind='self_model'`)
- `personal_agent/reflection_system.py` — `run_reflection_pass`: standalone reflection trigger

**Calls:** Memory (reads/writes self-model slots as CRT memories), Verification (validates reflection updates via cloud), Compression (heartbeat triggers compression pass after trust decay)

### 4. Compression (V(t) / Tiers)

Adaptive semantic compression that moves memories between three fidelity tiers based on volatility. Stable, low-trust memories fold down to 10D vectors; volatile or high-trust memories stay at full 384D.

**Key files:**
- `personal_agent/memory_compression.py` — `fold_vector`, `unfold_vector`, `compute_volatility`, `run_compression_pass`, `CogniSeed`

**Calls:** Memory (reads/writes compression state on memory rows), Reflection (compression runs after trust decay in the heartbeat cycle)

### 5. Routing (Cloud Escalation)

Three-tier generation routing: local Ollama (Tier 0), OpenAI-compatible API (Tier 1), Anthropic Claude (Tier 2). The control layer always stays local; only raw generation is routed.

**Key files:**
- `personal_agent/hybrid_llm_client.py` — `HybridLLMClient`: provider routing with `local:`, `cloud:`, `anthropic:`, `role:` prefix resolution
- `personal_agent/ollama_client.py` — Local Ollama client
- `personal_agent/model_router.py` — `ModelRouter`: decides which model handles a given request
- `personal_agent/cloud_features.py` — Cloud-specific features (slot classification, NLI, reflection validation)

**Calls:** Governance (rate limits, daily budgets), Verification (cloud policy scrubs PII before sending prompts upstream)

### 6. Synthesis (Planned)

Evidence-based answer assembly with auditable citation chains. Currently partially implemented through the evidence packet system.

**Key files:**
- `personal_agent/evidence_packet.py` — `Citation`, `EvidencePacket` data structures
- `personal_agent/research_engine.py` — `ResearchEngine` for multi-step research tasks

**Status:** The data structures exist and citations are attached to responses, but full synthesis (where the system assembles answers from multiple evidence sources with weighted trust) is not yet complete.

### 7. Governance (Cycle Limits / Trust Thresholds)

Enforcement of safety boundaries: daily call limits per cloud feature, rate limiting for Anthropic API, tool execution policies, and trust thresholds for memory authority transitions.

**Key files:**
- `personal_agent/runtime_config.py` — All configurable limits and policies (see `_DEFAULT_CONFIG`)
- `personal_agent/rate_limiter.py` — `PersonalRateLimiter` for Anthropic API
- `personal_agent/cloud_features.py` — Daily limit tracking per cloud feature
- `personal_agent/policy.py` — Memory write policy validation

**Calls:** Routing (enforces rate limits), Memory (trust thresholds for authority promotion), Reflection (limits reflection validation calls)

## How They Connect

```
User Message
    |
    v
[Routing] -- selects model (local/cloud/anthropic)
    |
    v
[Memory] -- retrieval (similarity + recency + trust + tier weight)
    |
    v
[LLM Generation] -- prompt assembled with memory context
    |
    v
[Verification] -- mid-stream checkpoints + post-generation gates
    |
    v
[Governance] -- trust updates, cycle counting, rate limiting
    |
    v
Response delivered to user
    |
    v
[Reflection] -- heartbeat loop (async, periodic)
    |     |
    v     v
[Compression]  [Self-Model update]
```

## App Startup

The application boots in `crt_api.py` via a `create_app()` factory function. Key initialization:

1. **Runtime config** loaded from `crt_runtime_config.json` (or defaults)
2. **LLM client** initialized lazily on first use (`HybridLLMClient`)
3. **Model router** configured with default model from `CRT_OLLAMA_MODEL` env var
4. **Per-thread engines** created on demand via `get_engine(thread_id)` — each gets its own `CRTEnhancedRAG` instance with isolated or shared memory databases
5. **Background loops** started: heartbeat scheduler, continuous loops, DNNT retraining, jobs worker
6. **Routes registered** from `routes/` package: chat, memory, auth, models, threads, misc, copilot, learning

The `doc_map` at line 1076 of `crt_api.py` defines which markdown files are served through the `/api/docs` endpoint.
