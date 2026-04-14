---
name: Session 2026-04-05 Compression & CogniMap
description: CogniMap v0 experiment, trust-weighted non-uniform compression, playdough formalism, INR discussion, video encoding concept, structural governance shipped.
type: session
---

## Session Summary — April 5, 2026

### CogniMap v0 Experiment — RESULTS
Trust-weighted non-uniform compression on 711 production memories:

| Method | Recall@5 | Size | Ratio |
|---|---|---|---|
| Full precision (baseline) | 1.000 | 1066 KB | 1.0x |
| Uniform PCA-192 | 0.913 | 533 KB | 2.0x |
| Uniform PCA-96 | 0.900 | 267 KB | 4.0x |
| **CogniMap (trust-weighted)** | **0.913** | **163 KB** | **6.5x** |

Key findings:
- 6.5x compression with 91.3% recall — matches PCA-192 quality at 3x better compression
- 3 gap-flips detected (not zero, needs investigation)
- Zero total failures (no query below 0.6 recall)
- PCA-96 captures 84.5% of variance
- CogniMap registry itself is 87.5 KB (fold map metadata)
- 628/711 memories are low trust (<0.4) — 87% compress aggressively without quality loss

Script: `papers/compression_experiment/cognimap_v0.py`

### CogniMap Theory — Formalized from GPT Log Recovery
Aether recovered the original CogniMap concept from May-June 2025 GPT logs:
- CogniMap = cognitive scaffold that records HOW meaning was compressed (fold geometry)
- Not a visualization — a decompression key
- Original vision: CRT as general-purpose semantic compression engine
- Key insight: traditional compression throws away the map; CogniMap keeps it

### Playdough Formalism
Aether defended and critiqued the playdough metaphor formally:
- **Defense**: Maps to Riemannian manifold with trust-weighted metric, deformation under evidence pressure, cascade propagation, hysteresis (path-dependent shape retention), adaptive stiffness (Fisher information)
- **Critique**: CRT is discrete not continuous, memories are independent not physically coupled, sharp gate boundaries, 384-dim not 3D, contradictions are relational signals not dents
- **Correct formalism**: "CRT belief space is a Riemannian manifold with a trust-weighted metric, where evidence induces local deformations that propagate via the BDG, and the metric (certainty) governs resistance to deformation"

### Frequency Band Compression Concept
Beliefs decomposed into frequency bands:
- Low frequency = core identity (name, values). Rarely changes. Extreme compression.
- Mid frequency = working context (current project, preferences). Changes between sessions.
- High frequency = ephemeral (this turn's context). Changes every frame.
- Compaction = low-pass filtering (discard high frequency noise, keep structural bass notes)

### Video Encoding / Streaming Concept
H.265 temporal compression maps to CRT epistemic dynamics:
- Keyframe = full session state snapshot
- P-frame = per-turn trust deltas (only what changed)
- Motion vectors = cascade propagation
- GOP structure = session boundaries
- Codec's bitrate allocation = trust-weighted compression (high-trust regions get more bits)
- NOT Memvid (QR codes in video) — using codec primitives directly on belief state

### Lazy Decompression / Predictive Priming Concept
- Codebase sits compressed, decompresses predicted hot paths on demand
- Like CPU branch prediction but at semantic/module level
- For CRT: compress memory corpus, decompress only retrieved memories at query time
- Speed gain from less data through pipeline, not faster computation
- Crossover point: small corpus (711) = marginal gain, large corpus (100K+) = significant

### Structural Governance Shipped
Confidence-gated response depth:
- belief < 0.4: max_tokens=150, hedge prefix injected
- belief 0.4-0.55: max_tokens=500
- belief > 0.55: full depth (4096)
- Computed from retrieved memory trust scores BEFORE generation
- Applied to cloud generation path (max_tokens cap) and local path (post-generation truncation)
- Console: `[STRUCTURAL_GATE] Confidence gate ACTIVE: belief=0.32 < 0.4`

### Frontend Polish Shipped
- Confidence badge: `◉ 0.85` next to generation source (green/amber/red by confidence)
- Gate check dots: S N G (Slot/NLI/Gap) — three colored circles showing governance results
- Cost badge: `last: $0.0097 session: $0.0097` above composer
- Types added to CtrMessageMeta: belief_confidence, gate_checks, cost_usd

### Cost Tracking Shipped
- Cookie provider cost estimation (input chars//4, output words*1.3)
- Actual token extraction from litellm responses
- Price table updated (Sonnet/Opus/GPT-4o/GPT-4o-mini)
- Budget warning system ($10/$25/$50/$75/$100 thresholds)
- Frontend session cost display

### Model Configuration
- CRT_OLLAMA_MODEL=gemma3:latest (for governance, NLI, slot classify — fast on 12GB)
- CRT_INTENT_MODEL=llama3.2 (for intent classification)
- Cloud generation via Claude cookie (claude-sonnet-4-6)
- gemma4 too large for governance calls (15s per call, 7 calls = 105s overhead)

### Next Steps
1. Benchmark lazy decompression overhead (decompression time vs full-load time)
2. Test CogniMap on file compression (images, code, documents)
3. Investigate 3 gap-flips — adaptive stiffness (promote wobbling memories)
4. Explore GGUF as CogniMap container format
5. Video encoding prototype for belief state temporal evolution
6. Frontend polish weeks 2-4 (memory animation, drift visualization, WS migration)
