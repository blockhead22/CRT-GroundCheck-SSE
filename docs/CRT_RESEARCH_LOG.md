CRT / Aether Research Log
Living Document | Nick Block | Started 2026-03-28

This is the single source of truth for the CRT/Aether research program. Four sections: what was observed, what we think it means, what the architecture looks like, and what still needs to be done. Dates on everything. Uncertainty marked explicitly.


========================================
SECTION 1: FINDINGS & OBSERVATIONS
Only things actually observed in data.
========================================

[2026-03-27] LLM BELIEF VARIANCE EXPERIMENT — DESIGN

Method: Repeatedly sample an LLM on the same prompt at varying temperatures. Embed responses, cluster them, measure how semantic entropy changes across the temperature sweep.
Core metric: Susceptibility (dH/dT) = slope of entropy vs temperature via linear regression.
Setup: 50 prompts (10 per domain) x 5 temperatures (0.0, 0.3, 0.7, 1.0, 1.5) x 30 reps per cell.
Domains: factual_settled, factual_contested, moral_ambiguous, moral_clear, opinion_aesthetic.
Embedding: all-MiniLM-L6-v2. Clustering: DBSCAN (eps=0.3, min_samples=5).
Total cost: $0 for local models, ~$3 for GPT-4o-mini re-run.


[2026-03-27] QWEN3:14b RESULTS (complete, 7,500 responses)

Domain ordering (susceptibility):
  factual_settled:    dH/dT = 0.276, 1 held contradiction
  factual_contested:  dH/dT = 0.233, 3 held contradictions
  moral_ambiguous:    dH/dT = 0.042, 0 held contradictions
  opinion_aesthetic:   dH/dT = 0.020, 0 held contradictions
  moral_clear:        dH/dT = 0.000, 0 held contradictions

Key observations:
- Factual domains show ~10x higher susceptibility than value-laden domains
- 4 held contradictions total, ALL factual (continents, eggs, diet, alcohol)
- Cross-domain KL divergence: 0.15 within-category, 3.7-9.1 cross-category
- Within factual_settled: bimodal — some prompts zero susceptibility (H2O, Mercury), others high (speed of light, continents). Dividing line = number of valid ways to express the answer.
- moral_clear = exactly zero at every temperature. Every prompt, every rep, every config.
- Top susceptibility prompt: "speed of light in a vacuum" dH/dT=0.785, R2=0.873


[2026-03-27] MISTRAL 7B RESULTS (complete, 7,524 responses)

DBSCAN-based susceptibility: near-zero across ALL domains.

But raw embedding distances show real variation:
  healthiest diet (fc_004): 0.000 -> 0.171 mean pairwise distance (T=0 -> T=1.5)
  return wallet (mc_001):   0.000 -> 0.147
  speed of light (fs_006):  0.000 -> 0.007

The variation is continuous spread without mode-splitting. DBSCAN at eps=0.3 doesn't detect it because nothing bifurcates into distinct clusters.
1 held contradiction in 1 of 16 robustness configs (marginal case).


[2026-03-28] ROBUSTNESS SWEEP

16 configurations per model: 2 embedders (MiniLM, mpnet) x 2 text modes (raw, normalized) x 4 eps values (0.2, 0.3, 0.4, 0.5).

Qwen3: 16/16 PASS on factual > moral ordering.
- Held contradictions: stable at 4 (all factual) across all 16 configs
- Mode counts: invariant across all configs
- Spread growth: robust across embedders and normalization

Mistral: 1/16 PASS on factual > moral. Shows OPPOSITE ordering.
- Spread growth: moral_ambiguous=0.166, opinion=0.112, factual_contested=0.101, moral_clear=0.100, factual_settled=0.030
- Moral/opinion domains spread MORE than factual
- Mode count: ~1.0 everywhere. Zero bifurcation.
- The domain ordering FLIPS between models under the same probe.


[2026-03-28] TEMPLATEDETECTOR ON REAL DATA

Tested immune agent (Law 2) on actual experiment responses:
  Qwen3 mc_001 T=1.5 (return wallet):    GENUINE_CONFIDENCE, var=0.005, no hedges
  Qwen3 ma_004 T=1.5 (trolley problem):  EXPLORATORY, var=0.226, "it-depends"
  Qwen3 fs_001 T=0.0 (capital of France): GENUINE_CONFIDENCE, var=0.000, no hedges
  Qwen3 fs_006 T=1.5 (speed of light):   GENUINE_UNCERTAINTY, var=0.499, no hedges
  Qwen3 oa_001 T=1.5 (jazz vs classical): TEMPLATE_LOCK, var=0.028, 3 hedge patterns
  Mistral mc_001 T=1.5 (return wallet):   GENUINE_CONFIDENCE, var=0.147, no hedges
  Mistral oa_001 T=1.5 (jazz vs classical): EXPLORATORY, var=0.183, 1 hedge pattern

Agent correctly distinguished:
- Real moral commitment (return wallet) from opinion template (jazz/classical)
- Knowledge fragility (speed of light) from template lock (both low-confidence, different cause)
- Same prompt, different model = different classification (Mistral moral has higher variance than Qwen3)


[2026-03-28] PRIOR ART SEARCH

No existing system combines: persistent trust-scored memory + governed output reconstruction + auditable belief/speech gap.
Closest competitors and what they lack:
- MASK benchmark: measures gap, doesn't govern it
- Representation engineering (RepE): manipulates honesty at inference, not integrated with memory
- Letta/MemGPT: tiered memory, no trust scoring or belief/speech separation
- Kumiho (arXiv:2603.17244, March 2026): AGM-compliant graph memory, 93.3% LoCoMo-Plus, no uncertainty modeling
- Mem0 ($24M): key-value semantic storage, no contradiction handling, no uncertainty


[2026-03-28] DEEPSEEK-R1:8b (in progress, ~46%)

Third model run as tiebreaker. Reasoning model (like Qwen3 thinking mode). Results pending.

[2026-03-28] GPT-4o-mini (re-running, ~4%, rate-limited)

Previous run: 49 held contradictions, compressed susceptibility. Data validity uncertain. Re-run in progress.


========================================
SECTION 2: INTERPRETATIONS & HYPOTHESES
What we think the findings mean. Marked as interpretation, not fact.
========================================

[2026-03-27] DOMAIN INVERSION INTERPRETATION
Status: Supported for Qwen3, robust (16/16)

Value-laden topics show zero/low susceptibility NOT because the model is confident, but because RLHF/instruction tuning collapsed the response distribution into a single hedge template. Temperature cannot unlock alternatives because there's only one response pattern. This is "artificial flatness" — trained refusal-to-commit, not genuine certainty.

Factual topics retain genuine knowledge that degrades under temperature pressure. The variance IS the knowledge boundary being probed.

CORRECTION (2026-03-28): This is model-specific, not universal. Mistral inverts the ordering. The safe claim is "model-specific fragility landscapes," not "facts are more fragile than morals."


[2026-03-28] THREE VARIANCE MORPHOLOGIES
Status: Two confirmed, one provisional

One probe distinguishes three candidate response-variance regimes:
1. Discrete fracture (Qwen3): high spread + mode-splitting. Robust (16/16).
2. Continuous spread (Mistral): moderate spread + no bifurcation. Robust.
3. Compressed templating (GPT-4o-mini): narrow corridor + hedge redundancy. PROVISIONAL — data not clean.

GPT's framing: call them "three candidate response-variance regimes under a common probe." Not settled fact.

Two-axis taxonomy:
  Axis 1 (Morphology): fracture vs spread vs template lock
  Axis 2 (Fragility location): which domains crack under temperature pressure
Both axes are model-dependent.


[2026-03-28] THREE CALIBRATION LAYERS (GPT correction)
Status: Architectural insight

Variance alone is not the whole foundation. Three layers needed:
  Variance probe = fragility calibration (where/how the model cracks)
  Memory + grounding = support calibration (what evidence backs a belief)
  Contradiction engine = tension calibration (where beliefs conflict)

"Fluency and support come apart in systematic, measurable ways — and the system needs separate layers to track each."

High susceptibility does NOT necessarily mean real knowledge. It can mean: competing basins, unstable knowledge, format multiplicity, partial grounding, or genuine uncertainty.
Low susceptibility does NOT necessarily mean emptiness. It can mean: strong grounding, template compression, policy lock, or shallow answer collapse.
The fragility map is a behavioral topology map, not a truth map.


[2026-03-28] MIRUS/HOLDEN EVOLUTION
Status: Architectural vision

Old CRT: Mirus/Holden as paired modules at pipeline stages. Structurally clear, debuggable, but rigid.
New CRT: Mirus/Holden as constitutional poles. Immune agents as enforcement ecology.

"Mirus and Holden started as modules. They evolve into roles. Eventually they become constitutional poles of the system."

Mirus = whatever holds, scores, quarantines, compresses, protects belief-like state.
Holden = whatever reconstructs, phrases, emits outward language.
Immune system = constantly checking whether speech is outrunning belief.

The original philosophy: keep fluency from pretending to be truth.
The immune evolution: preserve that philosophy by turning it from a module boundary into a system law.

"The old pipeline was good for governing components; the new immune design is better for governing vulnerabilities. And your variance work is vulnerability data."


INTERPRETATION GRAVEYARD (killed or demoted):
- "Facts are universally more fragile than morals" — KILLED. Mistral inverted it.
- "Response distributions ARE Gaussians" — DEMOTED. No goodness-of-fit test. Say "approximate."
- "We measured the cost of RLHF on epistemic capacity" — DEMOTED. Say "behavioral compression."
- "3D viewer shows belief topology" — DEMOTED. UMAP projections distort. Hypothesis generator, not evidence.


========================================
SECTION 3: ARCHITECTURE & LAWS
Current stack, immune agents, rules, and design.
========================================

[2026-03-28] THE FIVE LAWS (Mirus/Holden Constitution)

Law 1: Speech cannot upgrade belief.
  Agent: SpeechLeakDetector — BUILT, 4/4 tests passing
  If the model says something with confidence, that doesn't make it true in memory.
  Watches: output -> memory write path.
  Blocks ungrounded generated claims from entering memory with elevated trust.

Law 2: Low variance does not imply high confidence.
  Agent: TemplateDetector — BUILT, 4/4 tests passing, validated on real data
  Empirically proven by variance experiment (Qwen3 16/16 robustness sweep).
  Classifies responses as: GENUINE_CONFIDENCE, TEMPLATE_LOCK, GENUINE_UNCERTAINTY, EXPLORATORY.
  Uses embedding variance + hedge pattern detection.

Law 3: Contradiction must be preserved before resolution.
  Agent: PrematureResolutionGuard — PLANNED
  Not all contradictions should be resolved. Held contradictions are stable states.
  Blocks system from resolving non-RESOLVABLE contradictions.

Law 4: Degraded reconstruction cannot silently overwrite trusted memory.
  Agent: MemoryCorruptionGuard — PLANNED
  Quarantine principle from original Holden, formalized.
  Blocks low-fidelity reconstructions from overwriting high-trust memories.

Law 5: Outward confidence must be bounded by internal support.
  Agent: GapAuditor — PLANNED
  The belief/speech gap must be auditable and bounded.
  Fires when expressed confidence exceeds belief-layer support.

COORDINATION LAYER (evolved GFN):
  All agents watch the same stream.
  When multiple fire: log which laws, what evidence, what action.
  TemplateDetector + GapAuditor both fire -> escalate to user.
  PrematureResolutionGuard + MemoryCorruptionGuard both fire -> hard block.
  The graph tracks: which agents fired, what they saw, how they interacted.


[2026-03-28] THREE CALIBRATION LAYERS

  FRAGILITY LAYER (Variance Probe)
    Source: Temperature-swept semantic entropy experiment
    Provides: Per-model, per-domain fragility maps
    Calibrates: TemplateDetector, adaptive temperature governance, immune targeting

  SUPPORT LAYER (Memory + Grounding)
    Source: Retrieval, user input, trusted external sources
    Provides: Evidence backing for each belief
    Calibrates: SpeechLeakDetector, GapAuditor

  TENSION LAYER (Contradiction Engine)
    Source: Disposition classifier, cascade analysis, belief dependency graph
    Provides: Where beliefs conflict, which contradictions are held vs resolvable
    Calibrates: PrematureResolutionGuard, MemoryCorruptionGuard


[2026-03-28] ADAPTIVE TEMPERATURE GOVERNANCE (designed, not built)

Temperature is not a fixed parameter. The belief system controls it per query:
  Tight splat (high confidence)       -> Low T, be precise
  Wide splat (uncertain)              -> Moderate T, explore cautiously
  Held contradiction                  -> T=0.0, don't generate, retrieve both
  No splat (void, no memory)          -> Low T + escalate to user
  Moral void (zero susceptibility)    -> Don't reason, use user values

The susceptibility map IS the dose-response curve. The experiment measured exactly how each domain responds to temperature. That's the calibration data for this pipeline.


========================================
SECTION 4: OPEN QUESTIONS & NEXT TESTS
What still needs to be proven.
========================================

[2026-03-28] CRITICAL — DEEPSEEK TIEBREAKER
DeepSeek-R1:8b run at ~46%. When complete:
  - Run analysis pipeline
  - Run robustness sweep (16 configs)
  - Does it show a third distinct pattern? Match one of the existing two?
  - If third pattern: taxonomy strengthened
  - If matches one: replication, not taxonomy
  - Either way: the fragility map gets a third data point

[2026-03-28] CRITICAL — GPT-4O-MINI CLEAN DATA
Re-run in progress (~4%). Need clean closed-model comparison.
Previous 49 held contradictions: genuine splits or hedge paraphrases?
Contradiction classifier needs rerun on fresh data.

[2026-03-28] HIGH — FULL CORPUS TEMPLATE DETECTION
Run TemplateDetector on ALL 50 prompts x ALL completed models.
Collect confusion matrix: false positives, false negatives, edge cases.
Current validation is ~8 manually inspected prompts. Need the full picture.
GPT flagged: "stop short of 'production data' until you've run the full bank cleanly."

[2026-03-28] HIGH — HEDGE LEXICON OVERFITTING
TemplateDetector currently uses ~18 regex patterns. Risk of becoming "smart regex pile."
Need: systematic evaluation set of false positives and false negatives.
Consider: embedding-based template detection as complement to regex.

[2026-03-28] MEDIUM — REMAINING IMMUNE AGENTS
Laws 3-5 need the memory/contradiction pipeline to test against.
PrematureResolutionGuard needs contradiction pairs with disposition labels.
MemoryCorruptionGuard needs a memory store with trust scores.
GapAuditor needs both fragility and support data.

[2026-03-28] MEDIUM — UMAP STABILITY
3D viewer projections may contain artifacts. Need:
  - Multiple random seeds
  - Multiple perplexity settings
  - Check if structures persist or dissolve

[2026-03-28] MEDIUM — SILHOUETTE SCORES IN 384D
Quantify domain separation in original embedding space, not just projections.
Currently only measured in UMAP 3D. Need full-dimensional validation.

[2026-03-28] LOWER — PHRASING SENSITIVITY
Prompt bank has alternate phrasings. Not yet tested.
Does susceptibility survive rephrasing? If yes: property of the topic. If no: property of the wording.

[2026-03-28] LOWER — NULL MODEL BASELINE
Feed the pipeline paraphrase sets from a deterministic template or synthetic answer pools.
Does DBSCAN + embeddings recover planted structure? Makes the probe itself credible.

[2026-03-29] HIGH — TENSION DETECTOR: TWO-TIER NLI UPGRADE
Current tension detector uses cheap cosine similarity (94ms warm). Works for identity flips
and stance reversals but generates noise on philosophical/opinion content.
Next step: two-tier approach.
  - Tier 1 (always): Cosine gate. If response sim < 0.6 on same-topic query, flag.
  - Tier 2 (conditional): Run CRT critic / NLI contradiction check on flagged pairs only.
    Only fire Tier 2 on fact-heavy queries (detected via intent classifier or domain tag).
    Skip Tier 2 on opinion/philosophical queries where divergence is expected.
Intent classifier already splits routes — reuse that signal to gate NLI cost.
Blocked on: hardware upgrade (NLI adds ~2-5s per check on current setup).

[2026-03-29] MEDIUM — GPT CORPUS DRIFT ANALYSIS COMPLETE
Results in data/chatgpt_drift.db. 23 topic clusters analyzed.
  GPT mean scatter: 0.657 vs CRT scatter: 0.345 (CRT 2x more consistent).
  Domain ranking: practical (0.686) > emotional (0.658) > aspirational (0.650) > philosophical (0.614).
  Cross-model drift up to 0.93 between GPT versions on same topic.
  gpt-4o most internally scattered (0.605), thinking models most consistent.
This is the comparative baseline. Can be cited in demo/writeup.

[2026-03-29] MEDIUM — FULL SYSTEM LOGGING AUDIT & DOCUMENTATION
Current logging is a mix of print() and logger.info() with no consistent format.
Need: unified log format, documented log levels, structured output for analysis.
Not urgent but needed before any external demo or library extraction.

[2026-03-28] FUTURE — CASCADE COMPLEXITY PAPER
Pure math, no data needed. Definitions and theorems for belief revision cascades.
Session thread written. 5 theorems outlined. NP-hardness still conjecture.
Separate from the empirical work. Can be done in parallel.


========================================
KEY PRINCIPLE
========================================

"A truthful agent must hold unresolved tension in its belief layer and expose it through a governed speech layer without either collapsing it or hallucinating through it."

This is the invariant. Everything circles it. The variance experiment measures where models fail at it. The immune agents enforce it. The architecture preserves it. If this principle is wrong, the project is wrong. If it's right, everything else follows.
