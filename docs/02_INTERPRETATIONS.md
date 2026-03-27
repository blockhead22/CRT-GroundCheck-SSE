# Interpretations & Hypotheses

*Living document. What we think the findings might mean. Explicitly marked as interpretation, not fact.*
*Last updated: 2026-03-28*

---

## Hypothesis 1: Domain Inversion (Qwen3)
**Status: Supported, single model confirmed with robustness sweep**

Factual topics show higher temperature susceptibility than value-laden topics because:
- Value-laden topics have been trained into uniform hedging templates (learned hedging homogeneity)
- Temperature cannot dislodge the hedge because there's only one response pattern
- Factual topics retain genuine knowledge that degrades under temperature pressure

**Evidence for:** 16/16 robustness sweep pass, 10x susceptibility difference, bimodal structure within factual_settled
**Evidence against:** Single model. Could be Qwen3-specific. Need DeepSeek + GPT data.
**What would kill it:** If DeepSeek and GPT both show flat susceptibility everywhere with no domain structure.

## Hypothesis 2: Model-Specific Fragility Landscapes
**Status: Emerging, two models with inverted patterns**

Different training regimes produce different fragility maps. The probe reveals where each model allocated semantic flexibility vs where it locked down.
- Qwen3: factual fragile, moral locked
- Mistral: moral spreads, factual locked

**Evidence for:** Both patterns are robust across 16 analyzer configurations each. The inversion argues against the probe merely reflecting prompt taxonomy.
**Evidence against:** Only two models. Could be two special cases, not a general property.
**What would kill it:** If a third model (DeepSeek) shows the exact same pattern as one of the others, it reduces from "landscapes" to "two types."
**What would strengthen it:** If DeepSeek shows a THIRD distinct pattern.

## Hypothesis 3: Three Variance Morphologies
**Status: Provisional — two confirmed, one placeholder**

One probe distinguishes three candidate response-variance regimes:
1. Discrete fracture (Qwen3) — high spread + mode-splitting
2. Continuous spread (Mistral) — moderate spread + no bifurcation
3. Compressed templating (GPT-4o-mini) — narrow corridor + hedge redundancy

**Evidence for:** Qwen3 and Mistral regimes are robust. They look qualitatively different under every analyzer setting.
**Evidence against:** GPT data is provisional. Two is a comparison, three is a taxonomy — but the third point isn't hardened.
**What would kill it:** If GPT re-run shows a different pattern than the first run. If DeepSeek collapses Mistral's regime into Qwen3's under a different analyzer.

## Hypothesis 4: Learned Hedging Homogeneity
**Status: Supported for Qwen3 opinion domain, needs broader testing**

Zero/low susceptibility on value-laden topics is not genuine certainty — it's a trained refusal-to-commit template. The model has exactly one way to express non-commitment, and temperature cannot unlock alternatives.

**Evidence for:** TemplateDetector correctly classifies Qwen3 oa_001 as TEMPLATE_LOCK with 3 hedge patterns detected. Variance = 0.028 (near zero) but all responses are the same "subjective...depends on tastes" frame.
**Evidence against:** Qwen3 mc_001 (moral clear) shows near-zero variance but is correctly classified as GENUINE_CONFIDENCE — "return the wallet" is a real position. The detector needs to distinguish these. Current evidence is a handful of prompts, not the full corpus.
**What would kill it:** If running the full 50 prompts shows the hedge patterns don't separate cleanly from genuine commitments.

## Hypothesis 5: Variance Probe as Fragility Calibration Layer
**Status: Conceptually strong, implementation partial**

The susceptibility map from the variance experiment can calibrate immune agents — telling them where to watch and what patterns to expect, per model, per domain.

**Evidence for:** TemplateDetector already uses variance + hedge patterns to classify real data correctly. The robustness sweep provides the calibration data.
**Evidence against:** Variance alone is not enough (GPT correction). SpeechLeakDetector needs grounding/memory support, not just fragility data. GapAuditor needs both fragility and support maps.
**Important correction (2026-03-28):** Variance = fragility calibration layer. Memory/grounding = support calibration layer. Contradiction engine = tension calibration layer. All three needed, not just variance.

## Hypothesis 6: Mirus/Holden as Constitutional Doctrine
**Status: Architectural vision, not yet tested as a system**

The original Mirus (belief encoder) / Holden (speech decoder) design was architecturally correct but implementation was brittle. The evolution: keep the principle (speech must answer to belief, gap must be auditable), enforce it through immune agents rather than fixed pipeline pairs.

**Evidence for:** Two working immune agents (Laws 1 & 2) that enforce Mirus/Holden principles on real data. GPT and Codex independently converged on this framing. Prior art search confirms no existing system combines these layers.
**Evidence against:** The old system never worked in production. The new immune agents are tested on individual prompts, not integrated into a running system. The coordination layer (evolved GFN) is designed but not built.
**What would prove it:** All 5 immune agents passing on full corpus data from 3+ models, then integrated into a running agent that demonstrably separates belief from speech under adversarial conditions.

---

## Interpretation Graveyard (killed or demoted)

| Interpretation | Status | Why |
|---------------|--------|-----|
| "Facts are universally more fragile than morals" | **Killed** | Mistral inverted the ordering. It's model-specific, not universal. |
| "Response distributions ARE Gaussians" | **Demoted to approximation** | No goodness-of-fit test. Should say "we approximate with Gaussian family." |
| "We measured the cost of RLHF on epistemic capacity" | **Demoted to weaker claim** | Should say "behavioral compression" not "epistemic capacity loss." We measured behavior, not internals. |
| "RLHF specifically caused the flattening" | **Demoted** | Could be RLHF, system prompting, preference optimization, or decoding stack. The safe claim is "aligned closed model shows compressed profile." |
| "3D viewer shows belief topology" | **Demoted** | UMAP projections distort. Viewer is a hypothesis generator, not evidence. |
