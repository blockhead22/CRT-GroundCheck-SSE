---
name: Session 2026-04-05 Full Day
description: Massive session. CogniMap compression research (memory vectors + images + code + lossless), frontend polish (confidence badge, gate dots, cost display, memory cards, epistemic graph), structural governance, cost tracking, model configuration, playdough formalism.
type: session
---

## Session Summary — April 5, 2026

### What Shipped (Frontend)
- **Confidence badge** — `◉ 0.40` next to generation source, colored green/amber/red by belief confidence
- **Gate check dots** — S N G (Slot/NLI/Gap) three colored circles showing governance results per message
- **Cost display** — `last: $0.0097 session: $0.0097` above composer for cloud messages
- **Memory cards** — animated expandable cards in message footer with trust dots, kind badges, alias badges, text previews, click to inspector
- **Epistemic graph** — SVG visualization in pipeline panel during retrieval: query pulse, memory nodes sized by trust, green similarity edges, red contradiction edges (dashed), animated sequence
- **Types updated** — `CtrMessageMeta` now includes `belief_confidence`, `gate_checks`, `cost_usd`

### What Shipped (Backend)
- **Structural governance** — confidence-gated response depth: belief<0.4 caps max_tokens to 150 + hedge prefix, 0.4-0.55 caps to 500, >0.55 full depth
- **Cost tracking** — actual token extraction from litellm responses, cookie provider estimation, price table for all models, budget warning system ($10/$25/$50/$75/$100 thresholds), per-request cost accumulation
- **Gate checks in metadata** — slot/NLI/gap results flow through done SSE event
- **Belief confidence in metadata** — computed from retrieved memory trust scores before generation
- **Model config** — gemma3:latest for governance (fast), llama3.2 for intent, Claude via cookie for generation, gemma4 too heavy for 12GB card
- **Telegram disabled** — commented out in electron/backend.js

### CogniMap Compression Research
**Memory vectors:** 6.5x compression, 91.3% recall, 3 gap-flips. Trust-weighted: high=f32, medium=f16, low=PCA96+uint8.

**Image experiments:**
- v0 per-patch JPEG: FAILED (header overhead)
- v1 wavelet non-uniform: partial (wins concept, loses to uniform on global metrics)
- Lossless v0 semantic-predicted: beats zlib 10.5%, all SHA256 verified
- Lossless v1 block-adaptive: **BEST — beats zlib 15.6%, -18.9% from PNG**
- Lossless v2 multi-stage RVQ: FAILED (residual is noise, stages add entropy)
- Lossless v3 CALIC gradient: WORSE than v1 (strategy map > fancy predictor)
- Code compression: FAILED (code is uniformly dense)
- **Dropbox sim: 5/5 files bit-identical SHA256 verified**

**Core finding: The CogniMap (strategy map / fold registry) IS the compression advantage.** Having a map that records which prediction worked best per region beats having no map with a fancier predictor.

### Playdough Formalism (via Aether)
Aether recovered original CogniMap concept from May 2025 GPT logs, formally connected playdough metaphor to Riemannian manifold with trust-weighted metric, identified why "splat" is insufficient (static vs evolving), proposed CRT belief space as deformable manifold where evidence induces local deformations propagating via BDG.

### Key Architectural Insights
- **Two product thesis**: Aether (AI assistant) + CogniMap (semantic compression). Same underlying principle: intelligent non-uniform treatment of information based on earned confidence.
- **Structural governance > advisory governance**: Confidence gate is architectural, not prompt-based. System can't be assertive when uncertain because the architecture won't let it.
- **The strategy map IS CogniMap**: Proven empirically that storing HOW each region was compressed (the fold registry) enables better compression than any single predictor applied uniformly.
- **CRT as predictor**: Future direction — the system that knows what it knows could BE the prediction engine for compression. Parked for later.

### Model/Configuration State
- `.env`: CRT_OLLAMA_MODEL=gemma3:latest, CRT_INTENT_MODEL=llama3.2, OLLAMA_BASE_URL=localhost
- Generation: Claude via cookie (claude-sonnet-4-6) for cloud_claude mode
- Governance: gemma3 locally (fast, ~1-2s per call vs gemma4's 15s)
- Telegram: disabled in electron/backend.js

### Files Modified
- `routes/chat.py` — structural governance, cost injection, gate checks, belief confidence
- `personal_agent/litellm_client.py` — token extraction, cost accumulation, _log_usage
- `personal_agent/cloud_features.py` — cookie cost estimation
- `personal_agent/cloud_usage_logger.py` — price table updated
- `personal_agent/cloud_usage_tracker.py` — check_budget()
- `frontend/src/App.tsx` — session cost state, belief_confidence, gate_checks
- `frontend/src/components/chat/MessageBubble.tsx` — confidence badge, gate dots, memory cards
- `frontend/src/components/chat/ChatThreadView.tsx` — cost display, session props
- `frontend/src/components/chat/PipelineCollapse.tsx` — epistemic graph replacing trust bars
- `frontend/src/types.ts` — CtrMessageMeta new fields
- `electron/backend.js` — telegram disabled, default model to gemma3
- `.env` — model config changes
- 9 compression experiment scripts in papers/compression_experiment/
