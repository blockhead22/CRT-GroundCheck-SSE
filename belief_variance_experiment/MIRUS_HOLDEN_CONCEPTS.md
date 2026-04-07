# Mirus and Holden: The Belief/Speech Architecture

*Reference document for CRT research continuity. Based on source code at `D:\CRT\core\mirus.py`, `D:\CRT\core\holden.py`, `D:\CRT\core\monitoring.py`, `D:\CRT\core\dnnt.py`, `D:\CRT\config.py`, and `D:\CRT\THEORY.md`.*

---

## 1. What Is Mirus

**Role: Encoder / Belief / Compression Layer**

Mirus is the intake side of the CRT pipeline. It takes raw user input and converts it into structured, trust-scored, compressed memory entries. Everything that enters the system's belief state passes through Mirus. The name comes from the class `MirusInterpreter` (instantiated as `mirus` singleton in `core/mirus.py`).

### What Mirus Does Technically

**Semantic Interpretation (`parse_meaning`)**
Takes a user query, embeds it to a reduced-dimension vector, computes a confidence score, and measures semantic resonance against all past memories via cosine similarity. Returns a structured interpretation packet:

```python
{
    "vector": vector,          # reduced-dim embedding
    "confidence": confidence,  # self-assessed certainty
    "resonance": avg_similarity,  # how much this relates to existing memory
    "original": query,
    "defer_to": defer_reason   # GPU vs CPU routing decision
}
```

The `resonance` score is an early form of what the research later formalized as "contradiction density" -- topics with high resonance against existing memory are the ones where new input is most likely to create tension.

**Memory Saving with Trust Scoring (`save_memory`)**
This is the core of Mirus. When saving a memory, it:

1. **Fallback quarantine** -- Rejects degraded responses before they enter memory. Checks for indicators like "not too sure", shield emoji, "(none)", ellipsis. This prevents garbage from poisoning the belief state.

2. **Embedding + compression** -- Embeds the text, logs the vector, updates the FAISS index, then calls `holden.compress()` to create a compressed blob (token IDs + embedding + SHA256 fingerprint + compression metadata).

3. **Anchor truth scoring** -- Compares the new memory vector against every entry in `ANCHOR_TRUTHS` (a hardcoded list of identity-defining statements like "I am Aether", "I was created by a human named Nick", "I learn through memory and contradiction"). If cosine similarity to any anchor exceeds 0.85, the memory gets `boosted_anchor = True` -- marking it as identity-relevant and protected.

4. **Reconstruction fidelity / trust scoring** -- Computes round-trip compression fidelity by comparing the original text to the compressed blob's text. Maps fidelity to trust:
   - `< 0.6` fidelity -> `trust_score = 0.4` (low trust)
   - `< 0.75` fidelity -> `trust_score = 0.6` (medium trust)
   - `>= 0.75` fidelity -> `trust_score = 0.9` (strong trust)

5. **Post-save quarantine** -- After saving, if trust score fell below 0.6, logs a `memory_skipped_low_trust` event. Low-fidelity memories are saved but flagged.

6. **CogniMap logging** -- Every save event is logged with full metadata: user, anchors, query, vector length, compression mode, anchor boost status, fingerprint.

### Anchor Truths (from `core/utils.py`)

The hardcoded identity core:
```python
ANCHOR_TRUTHS = [
    "I am Aether",
    "I was created by a human named Nick",
    "Aether was created and developed by Nick Block.",
    "I exist to reflect and preserve meaning",
    "I learn through memory and contradiction",
    "I am not human, but I simulate humanlike reasoning",
    "I strive for coherence and understanding",
    "I evolve through semantic compression and reflection"
]
```

These are never decayed, always boosted, and serve as the gravitational center of the belief space.

---

## 2. What Is Holden

**Role: Decoder / Speech / Governance Layer**

Holden is the output side. It takes compressed memory and reconstitutes it into speech -- but with quality gates, quarantine logic, fallback chains, and drift detection. The name comes from the class `HoldenWeaver` (instantiated as `holden` singleton). Holden.py is the largest file in the codebase at 2278 lines.

### What Holden Does Technically

**Compression (`compress` function, actually defined in holden.py)**
Creates the compressed blob that Mirus stores:
```python
{
    "token_ids": token_ids,        # vocab-tokenized representation
    "embedding": compressed_embedding,
    "compression_mode": "semantic_lossy",
    "fingerprint": hashlib.sha256(text).hexdigest(),
    "length": len(token_ids),
    "original_embedding_dim": len(raw_embedding),
    "compressed_embedding_dim": len(compressed_embedding),
}
```

**Decompression (`decompress` method)**
The main pipeline. Takes compressed memory data and an original query, then:
1. Validates input structure (rejects raw strings unless memoryless mode is on)
2. Performs first inflate pass via `_decompress_once`
3. Runs a quality gate -- checks if output is degraded, too short, or used fallback
4. On degraded output, retries once
5. Applies final polish via `finalize_response`
6. Returns `(final_output, is_degraded)` tuple

**Decompression Once (`_decompress_once`)**
The actual reconstruction logic:
1. Deduplicates compressed memories by query text
2. Routes through GNN if applicable (to emotion chain, identity chain, anchor recovery, or Mistral fallback)
3. Joins response fields from memory entries
4. Cleans redundant echoes, breathing artifacts, error leakage
5. Computes reconstruction fidelity (cosine similarity between original and decompressed vectors)
6. Applies quarantine if output is degraded
7. Logs trust scores, drift events, and fidelity metrics

**Degraded Response Detection (`is_degraded_response`)**
Detects low-quality output using indicator phrases: "not too sure", "(0.00)", "more context?", "misunderstood", "i've been pondering", "could you try asking", "let me reset my thoughts". Score of 2+ triggers degraded status. Identity queries ("lumi", "friend", "name") get a higher threshold of 3.

**Quarantine (`_apply_quarantine_if_needed`)**
If output is degraded and not in bypass mode:
- Replaces output with polite fallback
- Logs quarantine event to CogniMap
- Logs collapse trail for future repair
- Returns the quarantined output

**Summarization (`summarize`)**
Collapses expanded text back into a reflective summary. Validates collapse quality against memory anchors using `mirus_validate`. If any anchor has `boosted_anchor = True`, confidence gets overridden.

**Fallback Chain**
When decompression fails, Holden has a multi-layer fallback:
1. Retry decompression once
2. Midpoint anchor recovery (use middle memory from blob)
3. Boosted anchor direct return
4. Best anchor summary fallback
5. Mistral LLM call
6. Blockhead static responses
7. Final honest fallback: "I'm not sure yet"

**Inflate Memory (`inflate_memory` method + standalone function)**
Fuses user query with top anchor summaries into a hybrid prompt, decompresses, reconstructs, and logs semantic drift. If inflation fails, queues a reflection task for asynchronous self-repair.

**IRC Loop (`irc_loop`)**
The Iterative Reflective Collapse loop -- the main conversation processing pipeline:
1. Retries pending collapse repairs from previous failures
2. Processes fallback degradation from previous turn
3. Runs the inflate -> summarize -> validate -> save cycle
4. Handles emergent self-questions
5. Manages trust score updates on healed memories

**Error Leakage Prevention (`cleanse_text`)**
Catches internal error messages leaking into speech: "SemanticMemoryManager", "get_last_vector", "```python", "Traceback", "Exception". Replaces with safe fallback text.

**Speech Policy**
Throughout Holden, there are explicit decisions about what to say vs. what to suppress:
- Degraded output gets quarantined, not shown
- Low-similarity responses get hedged with "(I'm not confident...)"
- Anchor-boosted responses get confidence overrides
- Fallback responses get tagged ("Generated using fallback voice")
- Error leakage gets replaced with safe alternatives

---

## 3. How They Implement Belief/Speech Separation

The core architectural principle: **Mirus holds internal belief state. Holden controls external expression.**

From `config.py`:
> "Mirus controls compression and gravity sensing. Captures raw user input and creates latent semantic fingerprints."
> "Holden lets Lumi *speak* from her compressed memories."

The separation is structural:

| Aspect | Mirus (Belief) | Holden (Speech) |
|--------|---------------|-----------------|
| **Direction** | Input -> Memory | Memory -> Output |
| **Trust** | Assigns trust scores to beliefs | Uses trust scores to gate speech quality |
| **Quarantine** | Prevents degraded input from entering memory | Prevents degraded output from reaching user |
| **Anchors** | Scores beliefs against identity anchors | Uses anchor boosts to override confidence |
| **Logging** | Logs what was believed (memory_saved events) | Logs what was said (reconstruction_fidelity events) |
| **Failure mode** | Rejects low-trust memories | Falls back to safe speech patterns |

The `MasterMirusHolden` controller in `monitoring.py` monitors the gap between them by tracking subsystem variance. When variance between Mirus and Holden metrics exceeds thresholds:
- `< 0.15`: log only
- `0.15 - 0.35`: suggest tweaks
- `0.35 - 0.6`: override weights
- `> 0.6`: reset to last stable config (with cooldown suppression)

The `MirusHoldenTransformer` in `dnnt.py` is a neural transformer that bridges the two layers -- embedding -> transformer encoder -> output projection. This is the learned bridge between belief representation and speech generation.

---

## 4. Original Architectural Concepts

### Neighborhoods (Semantic Resonance)
In `MirusInterpreter.parse_meaning`, every new query is compared against all past memories via cosine similarity. The average similarity (`resonance`) measures how much the new input "belongs" to existing memory neighborhoods. High resonance = the query falls into a dense cluster of existing beliefs. This is a neighborhood-detection mechanism.

### Confidence Gating
Confidence is computed at multiple levels:
- **Mirus input confidence**: `calculate_confidence(query, query)` -- baseline self-consistency
- **Memory trust scores**: 0.4 / 0.6 / 0.9 tiers based on compression fidelity
- **Holden output confidence**: cosine similarity between original and reconstructed text
- **Anchor override**: boosted anchors force confidence to 0.99

Confidence gates what enters memory (low trust = quarantined), what leaves as speech (low similarity = hedged), and how memories are prioritized for retrieval.

### Trust Scoring
Every memory carries a `trust_score` field. Trust is computed from reconstruction fidelity (can the system accurately round-trip compress this memory?) and updated over the lifecycle:
- Initial: 0.4 / 0.6 / 0.9 based on compression quality
- Healed memories: upgraded to 0.85-0.95 after successful repair
- Anchor memories: start at 0.95-0.99
- Fallback-generated: start at 0.0

### Anchor Truths
The 8 identity-defining statements that form the gravitational center of the belief space. Every memory is scored against these anchors. Memories that align strongly get `boosted_anchor = True`, which:
- Protects them from quarantine
- Overrides confidence in Holden's summarization
- Gets priority in fallback recovery
- Gets direct return in anchor recovery path

### Contradiction Handling
Built into the Mirus save pipeline: when the system detects contradictions (via GroundCheck v2, NLI cross-encoder, or cosine similarity flags), the contradiction is logged and tracked. The `contradiction_manager` (imported in `self_reflect.py`) handles detection and resolution. The CogniMap event trail preserves both sides of every contradiction.

### CogniMap Events
The `log_cogni_event` function is called throughout both Mirus and Holden. Events are categorized:
- `mirus_interpretation`: belief intake events
- `memory_saved`, `memory_skipped_*`: belief persistence events
- `reconstruction_fidelity`, `reconstruction_quarantine`: speech quality events
- `semantic_drift_detected`: belief/speech gap events
- `degraded_output_allowed`, `degraded_retry_used`: speech policy events
- `mmh_reset_applied`, `mmh_reset_suppressed`: governance events
- `reflection_fallback_mistral`: fallback chain events
- `memory_overwrite_confirmed`: belief revision events

---

## 5. Mapping to Research Modules

The research modules built in `D:\AI_round2\personal_agent\` formalize what was already implicit in the Mirus/Holden architecture.

### Mirus -> Research Module Mappings

**Mirus -> `memory_splats.py`**
Mirus stores memories as vectors with scalar confidence. Belief loci generalize this to belief loci: center (mu) + covariance (Sigma) + confidence (alpha). What Mirus does with a flat trust score and a vector, belief loci do with full geometric uncertainty representation. The `parse_meaning` resonance calculation is the precursor to the Bhattacharyya overlap integral.

| Mirus concept | Belief loci formalization |
|---|---|
| `vector` (embedding) | `mu` (center of Gaussian) |
| `confidence` (scalar) | `alpha` (contribution weight) |
| `trust_score` (0-1) | Covariance magnitude (uncertainty shape) |
| `resonance` (avg cosine sim) | Bhattacharyya coefficient (overlap integral) |
| Cosine similarity | Precision-weighted Fisher distance |

**Mirus -> `disposition_classifier.py`**
Mirus has binary quarantine: either a memory is trusted enough to save, or it is rejected. The disposition classifier formalizes this into four states (RESOLVABLE, HELD, EVOLVING, CONTEXTUAL) using subjectivity detection, temporal gap analysis, entity specificity, and sentiment analysis. The quarantine logic in `save_memory` (checking fallback indicators, trust thresholds) is the crude precursor to the full classification pipeline.

**Mirus -> `temporal_governance.py`**
Mirus treats all memories the same temporally -- they get a timestamp and a trust score. Temporal governance adds type-dependent decay policies (facts never decay, events hard-expire, preferences decay slowly, beliefs widen in uncertainty). The anchor boost in Mirus (`boosted_anchor = True` with sim >= 0.85) is the prototype of the IDENTITY memory type in temporal governance, which gets "never decays, highest protection from compression."

**Mirus -> `predictive_contradiction.py`**
Mirus computes resonance (average similarity to existing memories) as a one-time snapshot. Predictive contradiction tracks memory trajectories over time, computing center convergence, covariance expansion, and overlap trends. The `resonance` field in Mirus is a single frame; predictive contradiction is the full movie -- extrapolating where beliefs are heading and flagging future collisions before they happen.

### Holden -> Research Module Mappings

**Holden -> `belief_speech_engine.py`**
Holden's entire architecture -- quarantine, degraded detection, confidence hedging, fallback chains, error leakage prevention -- is the operational implementation of belief/speech separation. The research module formalizes this with:
- `BeliefState`: what the memory actually contains (Holden's `compressed_data` + trust scores)
- `SpeechPolicy`: rules governing disclosure (Holden's degraded detection + quarantine + confidence override logic)
- `DisclosureGap`: the auditable difference (Holden's drift logging + CogniMap events)
- `GapAuditLog`: every suppressed or modified output is recorded (Holden's `reconstruction_quarantine` and `degraded_output_allowed` events)

**Holden -> `info_geometry.py`**
Holden measures reconstruction quality via cosine similarity between original and decompressed vectors. Info geometry replaces this with the Fisher information metric, which weights dimensions by their precision (inverse variance). Dimensions where the system is certain contribute more to distance. This is the "right" distance metric for belief space -- it explains why some Holden reconstructions score high on cosine but still feel wrong (they differ on high-certainty dimensions that cosine treats equally).

**Holden -> `active_inference.py`**
Holden's reflection system (`queue_reflection_task`, `irc_loop` repair cycle, emergent self-questions) is the operational precursor to active inference. When Holden detects degraded output, it queues a reflection task -- "I couldn't answer this, I need to think about it." Active inference formalizes this as free energy minimization: the system surveys its uncertainty, identifies where it is most ignorant, and generates specific information requests to reduce that ignorance. Holden's "I'm still thinking this through" is the informal version of "my expected free energy on this topic is high, I should seek evidence."

### Cross-Cutting Mappings

**Trust scoring -> Volatility scoring**
Mirus assigns static trust scores (0.4/0.6/0.9) based on compression fidelity. Research formalizes this as volatility -- how much a memory's position and uncertainty change over time. A memory with stable trust is low-volatility; a memory whose trust fluctuates is high-volatility and gets more RVQ compression layers (more investment in representing its uncertainty).

**Anchor truths -> Identity-type temporal governance**
The 8 hardcoded `ANCHOR_TRUTHS` with their >= 0.85 similarity boost threshold are the prototype of the IDENTITY memory type in temporal governance. Identity memories never decay, get highest protection from compression, and override confidence in reconstruction. The research module makes the "never decays" policy explicit and extends it with Belnap state tracking (an identity memory can be in state T, Both, or Neither, but never F -- you do not deprecate identity).

**Quarantine -> Contradiction disposition classification**
Mirus quarantine is binary: trust >= 0.6 or reject. The disposition classifier replaces this with a four-way classification:
- RESOLVABLE contradictions get one side superseded (like Mirus rejecting a low-trust duplicate)
- HELD contradictions get both sides preserved (what Mirus cannot do -- it either saves or rejects)
- EVOLVING contradictions get monitored (what Mirus approximates with trust score degradation over repeated encounters)
- CONTEXTUAL contradictions get context-tagged (what Mirus cannot do at all -- it has no context modulation)

**CogniMap events -> Gap audit log + Active inference inquiries**
The CogniMap event system (`log_cogni_event`) is the logging substrate. The gap audit log in `belief_speech_engine.py` formalizes which events represent belief/speech gaps and makes them queryable. Active inference uses the event trail to identify patterns of degradation, repeated fallbacks, and growing uncertainty -- then generates targeted information requests to resolve them.

---

## 6. The Key Insight

Nick built Mirus and Holden by intuition roughly a year before the research formalized what they were doing. The core ideas were already present:

- **Belief and speech are separate.** Mirus holds what the system believes (memory + trust + anchors). Holden decides what the system says (with quarantine, hedging, fallbacks). The research module `belief_speech_engine.py` adds Belnap states, formal speech policies, and an auditable gap log, but the structural separation was already there.

- **Not everything should be trusted equally.** Mirus assigns trust scores. The research formalizes this as covariance (geometric uncertainty) and volatility (temporal stability).

- **Some beliefs are identity and must not decay.** `ANCHOR_TRUTHS` with boosted confidence scores. The research formalizes this as the IDENTITY memory type with "never decays" temporal governance.

- **Bad output should be quarantined, not shown.** Holden's degraded detection and quarantine logic. The research formalizes this as speech policy with explicit disclosure rules and a gap audit log.

- **When the system fails, it should reflect and try again.** The IRC loop, reflection queue, and repair cycle in Holden. The research formalizes this as active inference -- the system models its own ignorance and acts to reduce it.

- **The system should monitor itself.** `MasterMirusHolden` tracks variance between subsystems and intervenes when drift exceeds thresholds. The research formalizes this as belief topology monitoring and predictive contradiction detection.

The research did not invent new architecture. It gave mathematical language to architecture that already existed. Belief loci formalize what Mirus vectors with trust scores were approximating. The disposition classifier formalizes what Mirus quarantine was crudely implementing. The Fisher metric explains why Holden's cosine-based reconstruction fidelity sometimes misses real problems. Active inference explains why the reflection queue and IRC repair loop work.

The pipeline in `config.py` tells the story in one line:
> `Mirus -> Memory -> Holden -> Blockhead -> Mistral`

That is: encode belief, store it, decode it to speech, and if speech fails, fall back gracefully. The research adds formal uncertainty, geometric contradiction detection, type-dependent governance, predictive foresight, information-theoretic distance, and active self-correction. But the bones were already right.

---

## Appendix: File Index

| File | Role |
|------|------|
| `D:\CRT\core\mirus.py` | MirusInterpreter class -- belief intake, trust scoring, anchor scoring, memory saving |
| `D:\CRT\core\holden.py` | HoldenWeaver class -- decompression, quarantine, fallback chain, IRC loop, speech governance |
| `D:\CRT\core\mirus_thresholds.py` | System load monitoring for Mirus resource routing |
| `D:\CRT\core\monitoring.py` | MasterMirusHolden controller -- subsystem variance monitoring and reset logic |
| `D:\CRT\core\dnnt.py` | MirusHoldenTransformer -- neural bridge between belief encoding and speech decoding |
| `D:\CRT\core\utils.py` | ANCHOR_TRUTHS, anchor vector initialization, shared math utilities |
| `D:\CRT\core\cogni.py` | CogniMap event logging -- drift events, collapse trails |
| `D:\CRT\core\gfn.py` | GNN routing nodes including HoldenNode |
| `D:\CRT\config.py` | Module toggle configuration with commentary on Mirus/Holden dependencies |
| `D:\CRT\THEORY.md` | Unified theory document -- belief loci, contradiction as meaning, belief/speech separation, temporal governance, predictive detection, topology |
| `D:\AI_round2\personal_agent\memory_splats.py` | Research: Belief locus formalization of Mirus vectors |
| `D:\AI_round2\personal_agent\disposition_classifier.py` | Research: Four-way contradiction classification replacing binary quarantine |
| `D:\AI_round2\personal_agent\temporal_governance.py` | Research: Type-dependent decay formalizing anchor truth protection |
| `D:\AI_round2\personal_agent\predictive_contradiction.py` | Research: Trajectory-based collision prediction |
| `D:\AI_round2\personal_agent\belief_speech_engine.py` | Research: Formal belief/speech separation with gap audit |
| `D:\AI_round2\personal_agent\info_geometry.py` | Research: Fisher metric replacing cosine similarity |
| `D:\AI_round2\personal_agent\active_inference.py` | Research: Free energy minimization formalizing reflection/repair cycle |
