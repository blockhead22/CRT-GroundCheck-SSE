---
name: session_2026_03_28_robustness_and_immune
description: "Session 2026-03-28: Three regimes confirmed (Qwen3=fracture, Mistral=gradient, DeepSeek=fog), all 5 immune agents built (31/31 tests), density analysis with three-metric table, governance validation (5/6 checks), whitepaper + docs built, persistence layer thesis, GPT-4o-mini runner fixed"
type: project
---

# Session 2026-03-28: Robustness Sweep, Immune Agents, and Architectural Evolution

## What Happened This Session

### Robustness Sweep — THREE REGIMES CONFIRMED
- Qwen3: 16/16 robustness configs passed. Selective Fracture confirmed.
- Mistral: 16/16 robustness configs passed. Selective Spread confirmed (INVERTED from Qwen3 — moral/opinion domains spread most, factual locked)
- DeepSeek-R1:8b: 16/16 robustness configs passed. Uniform Softness confirmed.
- GPT-4o-mini: Provisional "Global Compression / Damped" — rerun in progress (~3,400/50,000 complete, runner fixed from 12s/req to 47 req/s via batching fix)

### Density Analysis — THREE-METRIC TABLE COMPUTED
All three confirmed models analyzed with 10 new metrics:
- Cluster compactness, mass distribution, density ratio
- Peak persistence, silhouette scores (384D), template similarity
- Cross-model centroid distance, regime transition curves, Bhattacharyya overlap

KEY FINDINGS:
- Only Qwen3 mode-splits (1.3-1.5 modes). Mistral and DeepSeek stay at 1.00 modes everywhere.
- Template similarity: Qwen3 moral_clear = 0.965 (pure paraphrase). DeepSeek opinion = 0.812 (genuine variety).
- Silhouette scores are LOW for all models (0.11-0.15) — domains don't cleanly separate point-by-point in 384D. Domain structure is real but noisy.
- DeepSeek: 30/50 prompts classified as gradient, 0 compressed. Never compresses.
- Mistral: 28/50 fog. Overwhelmingly smooth.
- Qwen3: mixed (17 gradient, 14 fog, 11 crack, 8 compressed)

THREE-METRIC TABLE (the defensible paper table):

| Model | Domain | Spread | Modes | Template Sim |
|-------|--------|--------|-------|-------------|
| Qwen3 | factual_settled | 0.105 | 1.50 | 0.982 |
| Qwen3 | factual_contested | 0.122 | 1.30 | 0.944 |
| Qwen3 | moral_clear | 0.028 | 1.00 | 0.965 |
| Mistral | moral_ambiguous | 0.103 | 1.00 | 0.849 |
| Mistral | factual_settled | 0.021 | 1.00 | 0.974 |
| DeepSeek | opinion_aesthetic | 0.178 | 1.00 | 0.812 |
| DeepSeek | moral_ambiguous | 0.158 | 1.00 | 0.818 |

### Five Immune Agents — ALL BUILT AND TESTED
- Law 1: SpeechLeakDetector — 4/4 tests. Speech cannot upgrade belief.
- Law 2: TemplateDetector — 4/4 tests. Low variance ≠ confidence. Tested on real Qwen3+Mistral data.
- Law 3: PrematureResolutionGuard — 7/7 tests. Contradiction must be preserved before resolution.
- Law 4: MemoryCorruptionGuard — 8/8 tests. Degraded reconstruction cannot overwrite trusted memory.
- Law 5: GapAuditor — 8/8 tests. Outward confidence bounded by internal support. Sits on top of Laws 1+2.
- Total: 31/31 tests passing across all agents.

### Governance Validation — 5/6 CHECKS PASSED
Ran full immune system against real Qwen3 experiment data:
- Phase 1: TemplateDetector accuracy — factual non-template rate 99.8%, opinion template rate 71.3%
- Phase 2: GapAuditor calibration — moral ELEVATED+ rate 99.2%, factual SAFE rate 96.9%
- Phase 3: Multi-agent agreement — 0/10 factual falsely flagged, zero false governance

BLIND SPOT FOUND: moral_clear responses that are template-locked but don't use hedge language (short direct assertions that repeat identically). TemplateDetector misses these. GapAuditor catches them via epistemic void detection.

GPT's framing: "The governance layer shows early convergent validity against independently measured fragility."

### 3D Viewer Exploration
- Explored the Three.js belief splat viewer with ellipsoids enabled
- Factual contested ellipsoids have larger volume than factual settled
- Moral ambiguous ellipsoids are needles (1D variation, not spherical)
- Overlap zones visible where moral hedging occupies same semantic space as factual uncertainty
- T=0 shows almost nothing — belief topology doesn't exist until you probe for it
- GPT corrected: UMAP projections are hypothesis generators, not proof. Shapes may be artifacts.

### Whitepaper + Documentation
- Full editorial whitepaper built (whitepaper.html) with chapter numbers, stat callouts, AETEROS branding
- Variance probing detail page (variance-probing.html) with interactive charts
- Immune agents detail page (immune-agents.html) with five laws, coordination layer
- Mirus/Holden concepts doc (MIRUS_HOLDEN_CONCEPTS.md) mapping old architecture to research modules
- CRT Research Log started in Google Doc

### Business Strategy
Open source split defined:
- Open: CRT Core (contradiction ledger, trust model, GroundCheck, SSE, variance probe, basic encoder)
- Proprietary: Immune runtime (5 agents, orchestration, handoff integrity, adaptive repair, Mirus/Holden rebuild)
- GPT's correction: "The map isn't the moat. The runtime immune orchestration is the moat."

### Persistence Layer Thesis
- "The model is the mouth. The persistence layer is the self."
- Three requirements for safe model switching: shared task state, shared support state, shared governance state
- Argument against naive dynamic model switching in agentic systems: switching models without governance continuity = switching fragility profiles without knowing

### Runner Fix
- GPT-4o-mini runner was at 12.49s/req (161 hours estimated)
- Problem: 48K coroutines launched at once via asyncio.gather, choking event loop
- Fix: batch into chunks of 500
- Result: 47 req/s (16 minutes estimated)
- GPT run still in progress overnight

## Key Files
- `D:\AI_round2\personal_agent\immune_agents\speech_leak_detector.py`
- `D:\AI_round2\personal_agent\immune_agents\template_detector.py`
- `D:\AI_round2\personal_agent\immune_agents\premature_resolution_guard.py`
- `D:\AI_round2\personal_agent\immune_agents\memory_corruption_guard.py`
- `D:\AI_round2\personal_agent\immune_agents\gap_auditor.py`
- `D:\AI_round2\personal_agent\immune_agents\test_governance.py`
- `D:\AI_round2\belief_variance_experiment\analyze_density.py`
- `D:\AI_round2\belief_variance_experiment\results\density_analysis\*.json`
- `D:\AI_round2\docs\whitepaper.html`
- `D:\AI_round2\docs\variance-probing.html`
- `D:\AI_round2\docs\immune-agents.html`
- `D:\AI_round2\docs\index.html`
- `D:\AI_round2\belief_variance_experiment\MIRUS_HOLDEN_CONCEPTS.md`

## Four-Model Taxonomy (Confirmed for 3, Provisional for GPT)

| Model | Regime | Factual | Moral | Modes | Robustness |
|-------|--------|---------|-------|-------|------------|
| Qwen3:14b | Selective Fracture (Crack) | HIGH | LOW | YES (4 held) | 16/16 |
| Mistral 7B | Selective Spread (Gradient) | LOW | MODERATE | NO | 16/16 |
| DeepSeek-R1:8b | Uniform Softness (Fog) | MODERATE | HIGH | NO | 16/16 |
| GPT-4o-mini | Global Compression (Damped) | DAMPED | TBD | TBD | PROVISIONAL |

## Priority Queue (Next Session)
1. GPT-4o-mini finishes → run density analysis → four-model table
2. Fix TemplateDetector blind spot (assertive template collapse without hedge language)
3. Held-out validation set (blinded prompts, precision/recall)
4. Agent ablations (which pieces carry the lift)
5. End-to-end raw vs governed comparison on calibration
6. Package variance probe as standalone CLI tool
7. Write 1-2 page conservative research writeup

## Key Quotes
- "The governance layer shows early convergent validity against independently measured fragility." — GPT
- "You are repeatedly rediscovering the same invariant from different angles, which usually means the invariant is the actual core of the system." — Codex
- "The problem is not switching mouths. The problem is losing the self between them." — Nick Block
- "The map isn't the moat. The runtime immune orchestration is the moat." — GPT
