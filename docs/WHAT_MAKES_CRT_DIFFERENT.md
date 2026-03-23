# What Makes CRT/Aether Different

CRT (Cognitive Reflective Transformer) is a trust-weighted memory and verification system for AI assistants. This document explains what distinguishes it from existing approaches and why those differences matter.

## Core Differentiators

### 1. Trust-Weighted Memory (Not Just RAG Similarity)

**Standard RAG:** Retrieves documents by vector similarity alone. A memory from 6 months ago with 99% similarity ranks the same as one from yesterday.

**CRT:** Retrieval score = `similarity * recency * belief_weight * tier_weight`

Every memory has a trust score that evolves independently from its content. Trust increases when the user reinforces information, decreases through time decay, and drops sharply when contradicted. This means:

- A fact the user has confirmed three times ranks higher than one mentioned once
- A corrected fact (old value) naturally falls out of retrieval even though its vector is still a good match
- Stale memories fade unless reinforced, preventing zombie facts from dominating

### 2. Belief/Speech Separation (Provisional Output, Not Truth)

**Standard systems:** LLM output is treated as the answer. If it's stored at all, it's stored with the same authority as user input.

**CRT:** Every memory has an `authority` level (provisional/confirmed/locked) and a `source_kind` (principal/tool_receipt/model_output/social/external/system). LLM-generated content is automatically `provisional` and `model_output` — it cannot promote itself to `confirmed` without a user action.

This prevents a common failure mode: the system generates a speculative answer, stores it, retrieves it next time, and treats it as fact. In CRT, the system knows the difference between what the user said and what it inferred.

### 3. Mid-Stream Verification (Supervise While Speaking)

**Standard systems:** Verify the complete response after generation, then either accept or reject the whole thing.

**CRT:** `StreamVerifier` runs checkpoints every ~150 tokens during streaming. It checks for think-tag leaks, fact contradictions against retrieved memories, and repetition loops. If a contradiction is detected mid-stream, generation is stopped immediately — the user sees the honest partial answer rather than a complete but wrong one.

This is fundamentally different from post-hoc guardrails. The verification happens while tokens are being delivered, not after.

### 4. Earned Contradiction Resolution (Preserve Both Sides)

**Standard systems:** When new information conflicts with old, the old is overwritten silently. Or a "last write wins" policy is applied.

**CRT:** Contradictions are logged in a ledger with status tracking (OPEN/REFLECTING/RESOLVED). Both memories are preserved. Resolution requires evidence: user clarification, correction language, or significant trust differential. Until resolution, contested memories have their trust capped at 10% of normal, so the system naturally hedges rather than asserting.

### 5. Self-Reflection With Behavioral Trajectories

**Standard systems:** No self-model, or a static prompt describing the assistant's personality.

**CRT:** A 7-slot self-model that is populated entirely from evidence:
- Gate failures (what the system tried to say but was blocked)
- Negative feedback (what the user corrected)
- Trust deltas (how memory trust has been moving)
- Open contradictions (unresolved conflicts)

The self-model is updated via an LLM self-assessment in the heartbeat loop. Personality checkpoints are stored with diffs, creating a timeline of how the system's self-understanding has evolved. This is earned structure, not configured identity.

### 6. Adaptive Semantic Compression

**Standard systems:** All vectors are stored at full dimensionality forever, or old data is simply deleted.

**CRT:** Three-tier compression (10D/64D/384D) driven by a volatility formula. Stable, low-trust memories fold down to save space; volatile or high-trust memories stay at full fidelity. CogniSeed reconstruction guides enable approximate recovery. This means the system can scale to large memory stores without losing access to its history.

### 7. Auditable Synthesis (Citations With Trust Scores)

**Standard systems:** Answers appear with no provenance. "The AI said it" is the only attribution.

**CRT:** Every response carries metadata showing which memories were retrieved, their trust scores, their similarity to the query, and their source. The response is tagged as "belief" or "speech" based on the trust of the supporting evidence. Pipeline trace data shows every stage the request passed through.

## Comparison With Existing Systems

### vs. Guardrails AI / NeMo Guardrails

These are post-generation filtering layers. They check the completed output against rules and either pass or block. CRT does this too (gate checks), but also operates *during* generation (stream verification) and *before* generation (trust-weighted memory selection). The verification is embedded in the pipeline, not bolted on.

### vs. MemGPT / Letta

MemGPT implements hierarchical memory (core/archival/recall) with an LLM managing memory operations. CRT's approach differs in:
- **Trust scores** — MemGPT doesn't weight memories by trustworthiness
- **Contradiction handling** — MemGPT overwrites; CRT preserves and tracks
- **Compression** — CRT uses mathematical compression tiers; MemGPT relies on LLM summarization
- **Self-model** — CRT has a formal self-reflection system; MemGPT has system prompts

### vs. Standard RAG Agents (LangChain, LlamaIndex)

Standard RAG retrieves chunks by similarity and stuffs them into the prompt. CRT adds:
- Trust and recency weighting to retrieval scoring
- Source provenance and authority tracking
- Contradiction detection between retrieved facts
- Compression tiers with tier-aware retrieval penalties
- User-scoped memory isolation

### vs. Constitutional AI / RLHF Alignment

These approaches shape the model's weights or outputs through training. CRT operates at the application layer — it wraps any LLM (local or cloud) with a trust and verification membrane. The LLM is treated as a generation engine; the control logic is external and inspectable.

## What's Working vs. What's Planned

### Working Now
- Trust-weighted memory storage and retrieval
- Belief/speech separation with authority tracking
- Mid-stream verification (think leak, fact contradiction, repetition)
- 7-slot self-model with heartbeat-driven reflection
- Three-tier adaptive compression
- Three-tier cloud routing (local/OpenAI/Anthropic)
- Contradiction ledger with status tracking
- User-scoped memory isolation
- Pipeline tracing and audit metadata

### In Progress
- Full synthesis engine (evidence-based answer assembly with citation chains)
- Sub-agent interface (delegating complex tasks to specialized agents)
- Long-horizon evaluation harness (measuring system behavior over weeks/months)

### Planned
- Correction surface UI (letting users directly edit their memory store)
- Earned personality evolution (self-model changes that persist across reboots)
- Multi-user trust isolation (trust scores that are per-user, not global)
