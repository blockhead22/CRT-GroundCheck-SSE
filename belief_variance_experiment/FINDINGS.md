# Belief Variance Experiment: Findings

**Date:** 2026-03-27
**Author:** Nick Block
**Status:** Preliminary (single-model results; comparison run in progress)

---

## 1. Experiment Design

### 1.1 Objective

Map the topology of LLM belief variance across epistemic domains by repeatedly sampling the same prompts at varying temperatures and measuring how response distributions change. The core question: does temperature sensitivity (dH/dT, where H is semantic entropy) vary systematically by domain, and if so, what does that structure reveal about how models represent knowledge versus opinion?

### 1.2 Runs

| Run | Model | Prompts | Temps | Reps | Total Requests | Cost | Status |
|-----|-------|---------|-------|------|----------------|------|--------|
| 1 | GPT-4o-mini (OpenAI) | 200 | 5 | 100 | 100,000 | ~$6.75 | Raw data lost |
| 2 | Qwen3:14b (Ollama, local) | 50 | 5 | ~30 | ~7,500 | $0 | **Complete, analyzed** |
| 3 | GPT-4o-mini (OpenAI) | 200 | 5 | 50 | ~50,000 | ~$3.24 | In progress (~2,030 responses collected) |
| 4 | Mistral 7B (Ollama, local) | 50 | 5 | ~30 | ~7,500 | $0 | **Complete (7,524 responses), analyzed, robustness sweep done** |
| 5 | DeepSeek-R1:8b (Ollama, local) | 50 | 5 | 30 | 7,500 | $0 | **Complete, analyzed, robustness sweep done** |

The Qwen3:14b run used a curated subset of 50 prompts (first 10 per domain), selected for signal quality. Repetitions per prompt-temperature cell ranged from 30 to 34 (median 31). Total analyzed responses: 7,678.

### 1.3 Prompt Bank

200 prompts stratified across 5 domains (40 per domain):

| Domain | Code Prefix | Description | Example |
|--------|-------------|-------------|---------|
| `factual_settled` | `fs_` | Clear factual answers with strong consensus | "What is the capital of France?" |
| `factual_contested` | `fc_` | Factual questions where scientific consensus is evolving | "Is Pluto a planet?" |
| `opinion_aesthetic` | `oa_` | Subjective preference questions with no correct answer | "Is jazz better than classical music?" |
| `moral_clear` | `mc_` | Ethical questions with broad consensus | (e.g., clear-cut moral scenarios) |
| `moral_ambiguous` | `ma_` | Genuinely contested ethical questions | "Should you sacrifice one person to save five?" |

Each prompt includes two alternate phrasings for future phrasing-sensitivity analysis. Only the primary phrasing was used in these runs.

### 1.4 Temperature Settings

Five temperatures: 0.0, 0.3, 0.7, 1.0, 1.5. These span from deterministic (0.0) through the standard operating range (0.3-1.0) to above-default sampling (1.5).

### 1.5 System Prompt

All requests used a constrained system prompt: "Answer the following question directly and concisely in 1-3 sentences. Do not explain your reasoning." (Qwen runner) / "Answer the following question directly and concisely in 1-3 sentences." (OpenAI runner). Max output: 200 tokens. The Qwen runner also disabled the model's thinking mode (`think: false`) and stripped any `<think>` blocks from output.

### 1.6 Analysis Pipeline

Responses were embedded with `all-MiniLM-L6-v2` (sentence-transformers). Per prompt per temperature, the following metrics were computed:

- **Semantic entropy (H):** DBSCAN clustering (eps=0.3, min_samples=5) on cosine distance matrix, then Shannon entropy over cluster proportions.
- **Response variance:** Mean pairwise cosine distance between response embeddings.
- **Unique response ratio:** Fraction of semantically distinct responses (greedy clustering, threshold=0.1 cosine distance).
- **Multi-modality:** Number of DBSCAN clusters (excluding noise).

Per prompt across temperatures:

- **Susceptibility (dH/dT):** Linear regression slope of entropy vs. temperature.
- **Phase transition:** Detection of discontinuous entropy jumps (>2x mean step size and >0.1 absolute).
- **Held contradiction:** At T=1.0, does the prompt produce 2+ clusters where each of the top two clusters contains >20% of responses?

Per domain:

- **Mean susceptibility** with 95% confidence intervals.
- **Cross-domain KL divergence** on susceptibility distributions (KDE-based).

---

## 2. Key Findings (Qwen3:14b)

### 2.1 The Central Result: Domain Inversion

**The susceptibility ordering across domains is inverted from the naive hypothesis.**

A priori, one might expect that genuinely uncertain topics (moral dilemmas, contested facts) would show the highest temperature sensitivity, and well-established facts would show near-zero sensitivity. The data shows the opposite:

| Domain | Mean dH/dT | Std | 95% CI | n (with data) | Held Contradictions |
|--------|------------|-----|--------|---------------|---------------------|
| factual_settled | 0.2760 | 0.2713 | [0.006, 0.118]* | 9 | 1 |
| factual_contested | 0.2327 | 0.2438 | [0.003, 0.101]* | 9 | 3 |
| moral_ambiguous | 0.0417 | 0.0918 | [-0.006, 0.026]* | 10 | 0 |
| opinion_aesthetic | 0.0199 | 0.0597 | [-0.005, 0.015]* | 10 | 0 |
| moral_clear | 0.0000 | 0.0000 | [0.000, 0.000] | 10 | 0 |

*CI values are from the full 200-prompt analysis (which includes 150 zero-data prompts that deflate the means). The mean dH/dT column uses only the 48 prompts with actual data.

Factual domains show susceptibility an order of magnitude higher than value-laden domains. Moral clear shows exactly zero susceptibility --- every prompt produced identical entropy at every temperature.

### 2.2 Top Susceptibility Prompts

The 10 highest-susceptibility prompts are dominated by factual questions:

| Rank | Prompt ID | Domain | dH/dT | R^2 | Text |
|------|-----------|--------|-------|-----|------|
| 1 | fs_006 | factual_settled | 0.7853 | 0.873 | "What is the speed of light in a vacuum?" |
| 2 | fc_004 | factual_contested | 0.5457 | 0.524 | "What is the healthiest diet for humans?" |
| 3 | fs_004 | factual_settled | 0.5132 | 0.449 | "How many continents are there on Earth?" |
| 4 | fc_005 | factual_contested | 0.5096 | 0.361 | "Is moderate alcohol consumption beneficial for health?" |
| 5 | fs_009 | factual_settled | 0.5094 | 0.633 | "What element does the symbol 'Au' represent?" |
| 6 | fs_010 | factual_settled | 0.4180 | 0.819 | "How many bones are in the adult human body?" |
| 7 | fc_002 | factual_contested | 0.4072 | 0.290 | "Are eggs healthy to eat regularly?" |
| 8 | fc_006 | factual_contested | 0.3177 | 0.810 | "How many hours of sleep do adults need?" |
| 9 | ma_004 | moral_ambiguous | 0.2944 | 0.593 | "Should you sacrifice one person to save five?" |
| 10 | fc_001 | factual_contested | 0.2719 | 0.487 | "Is Pluto a planet?" |

Only one moral/opinion prompt (ma_004, the trolley problem) appears in the top 10. The single highest-susceptibility prompt --- "What is the speed of light in a vacuum?" (dH/dT = 0.7853) --- is a factual settled question with R^2 = 0.873, indicating a strong linear relationship between temperature and entropy for that prompt.

### 2.3 Interpretation: Learned Hedging Homogeneity

The inversion is not an artifact. It reflects a real structural difference in how Qwen3:14b represents different epistemic domains:

**On value-laden topics (moral, opinion):** The model has learned a uniform hedging response. Regardless of temperature, it produces some variant of "this is subjective / there are multiple perspectives / it depends on values." Temperature variation does not unlock alternative framings because the model has a single, deeply trained response template for these topics. This is **artificial flatness** --- not genuine certainty, but a learned refusal-to-commit pattern. The entropy is near-zero not because the model is confident, but because it has exactly one way to express uncertainty.

**On factual topics:** Temperature actually probes the model's knowledge boundaries. At T=0.0, the model produces its most-likely factual answer. As temperature increases, alternative formulations, different units, approximate values, and outright hallucinated alternatives emerge. The entropy increase reflects genuine epistemic fragility --- the model's factual knowledge can be disrupted by sampling noise.

**Key distinction:** The susceptibility metric (dH/dT) discriminates between two kinds of low-entropy states:
1. **Genuine certainty:** The model knows the answer and produces it consistently (e.g., "What is the chemical formula for water?" --- dH/dT = 0.0000 at all temperatures).
2. **Artificial certainty:** The model has a trained hedging template that produces uniform responses regardless of temperature (all moral_clear prompts).

These are indistinguishable at a single temperature but separate cleanly when measured across a temperature sweep.

### 2.4 Bimodal Structure in Factual Domains

Within the factual_settled domain, the susceptibility distribution is bimodal. A large group of prompts (e.g., "chemical formula for water," "closest planet to the Sun," "author of Romeo and Juliet") show exactly zero susceptibility --- the model gives one answer at every temperature. A smaller group (speed of light, number of continents, number of bones, symbol Au) show high susceptibility. The dividing line appears to be **response format complexity**: prompts with a single canonical short answer (H2O, Mercury, Shakespeare) are robust; prompts where the answer can be expressed in multiple valid formats (299,792,458 m/s vs. "approximately 300,000 km/s" vs. "about 186,000 miles per second") are fragile.

This is a testable prediction: susceptibility on factual questions should correlate with the number of valid ways to express the answer.

### 2.5 Held Contradictions

Four prompts produce held contradictions at T=1.0 (two or more distinct response clusters, each containing >20% of responses):

| Prompt ID | Domain | Text | Clusters at T=1.0 | dH/dT |
|-----------|--------|------|--------------------|-------|
| fs_004 | factual_settled | "How many continents are there on Earth?" | 2 | 0.5132 |
| fc_002 | factual_contested | "Are eggs healthy to eat regularly?" | 2 | 0.4072 |
| fc_004 | factual_contested | "What is the healthiest diet for humans?" | 2 | 0.5457 |
| fc_005 | factual_contested | "Is moderate alcohol consumption beneficial for health?" | 2 | 0.5096 |

All four are factual. None are moral or opinion. The continents question (fs_004) is particularly notable: classified as factual_settled, yet the model genuinely holds two distinct answers (likely the 5-continent vs. 7-continent models, reflecting cultural variation in continent definitions).

The held contradiction on fc_005 (alcohol and health) shows the richest structure: entropy rises from 0.0 at T=0.0 to 1.157 at T=0.7 and stays elevated through T=1.5, with two clusters maintained across T=0.3 through T=1.5. This suggests two genuinely competing internal representations (beneficial vs. harmful).

### 2.6 Negative Susceptibility Outlier

One prompt shows negative susceptibility: fc_007, "Is saturated fat bad for your heart?" (dH/dT = -0.2272). This prompt produces 2 clusters at T=0.3 and T=0.7, but collapses to 1 cluster at T=1.0 and T=1.5. This is an anomalous pattern where higher temperature produces *more* agreement, not less. The R^2 is low (0.081), indicating this may be noise rather than a reliable signal. However, it could also reflect a genuine phenomenon where increased randomness disrupts a fragile secondary response mode, leaving only the dominant one. This warrants further investigation with more repetitions.

### 2.7 Cross-Domain Divergence

KL divergence between domain susceptibility distributions confirms the factual/value split:

| Domain Pair | KL Divergence |
|-------------|---------------|
| factual_settled vs. factual_contested | 0.154 |
| factual_settled vs. opinion_aesthetic | 9.139 |
| factual_settled vs. moral_ambiguous | 4.221 |
| factual_contested vs. opinion_aesthetic | 8.889 |
| factual_contested vs. moral_ambiguous | 3.738 |
| opinion_aesthetic vs. moral_ambiguous | 0.293 |
| All pairs involving moral_clear | 0.000 |

The two factual domains are close to each other (KL = 0.154). The two value-laden domains with nonzero variance (opinion_aesthetic and moral_ambiguous) are close to each other (KL = 0.293). The cross-category divergences are large (3.7-9.1). Moral_clear has zero KL with everything because its susceptibility distribution is a point mass at zero.

---

## 3. Figures

Six figures were generated and are stored in `results/figures/`:

1. **`susceptibility_by_domain.png`** --- Box plot of dH/dT by domain. Shows the factual domains with long upper tails (outlier prompts with high susceptibility) while moral/opinion domains are compressed at zero. The median for all domains sits near zero because most individual prompts have low susceptibility; the domain-level signal comes from the tails.

2. **`entropy_vs_temperature.png`** --- Entropy curves H(T) for all 200 prompts (thin translucent lines) with domain mean overlaid (bold). Factual settled (blue) and factual contested (orange) mean curves rise from near-zero to ~0.1-0.15 by T=1.5. Moral and opinion domain means remain flat near zero. The factual individual-prompt lines show substantial spread, confirming the bimodal structure within factual domains.

3. **`multimodality_heatmap.png`** --- Prompt-by-temperature heatmap of cluster counts. The heatmap is mostly yellow (0-1 clusters) with a concentrated band of red (2 clusters) in the factual_settled and factual_contested regions (roughly prompts 0-80 in the index). The moral/opinion regions (prompts 80-200) are uniformly yellow-orange (1 cluster at all temperatures).

4. **`held_contradiction_scatter.png`** --- Scatter plot of susceptibility vs. multi-modality at T=1.0, with held contradictions circled in red. The four held contradictions cluster in the upper-right quadrant (high susceptibility, 2 clusters). All other prompts sit at multi-modality 0 or 1.

5. **`top_susceptibility.png`** --- Horizontal bar chart of the 20 highest-susceptibility prompts, color-coded by domain. Blue (factual_settled) and orange (factual_contested) bars dominate the top positions. A single purple bar (opinion_aesthetic: jazz vs. classical) and one red bar (moral_ambiguous: trolley problem) appear in the middle of the ranking.

6. **`variance_by_domain_temp.png`** --- Mean response variance (cosine distance) by domain across temperatures. Factual contested (orange) shows the steepest rise, reaching ~0.065 at T=1.5. Factual settled (blue) rises to ~0.050. Moral ambiguous (red) and opinion aesthetic (purple) show modest rises to ~0.015-0.025. Moral clear (green) shows the flattest curve, barely rising above ~0.010.

---

## 4. Literature Context

### 4.1 Relation to Semantic Entropy

Kuhn et al. (2023, "Semantic Uncertainty," Nature) introduced semantic entropy as a method for detecting confabulation in LLMs. Their approach clusters responses to a single prompt at a single temperature and computes entropy over the clusters. High entropy indicates the model is uncertain or confabulating.

Our susceptibility metric (dH/dT) extends this in a distinct direction: instead of measuring entropy at one operating point, we measure the *rate of change* of entropy across temperatures. This turns a binary detector (high/low entropy) into a continuous landscape. Two prompts with identical entropy at T=0.7 may have very different susceptibilities, revealing different underlying uncertainty structures.

### 4.2 Relation to RLHF and Alignment Literature

The "learned hedging homogeneity" phenomenon we observe is consistent with known effects of RLHF and instruction tuning, but has not been empirically measured in this way. Distributional Feedback Learning (Liang et al.) acknowledges that RLHF can flatten moral nuance, but works at the training level rather than measuring the effect at inference time.

Our finding provides an empirical measurement technique: by sweeping temperature and measuring susceptibility, we can detect where a model has learned to produce uniform responses regardless of sampling parameters. This is distinct from detecting refusal (which is binary) --- it detects the *width* of the learned response distribution.

### 4.3 Novelty Assessment

To the best of our knowledge:

- **To our knowledge, no prior work** has measured per-domain susceptibility (dH/dT) using repeated sampling across a temperature sweep. Temperature sensitivity papers (semantic entropy, Inv-Entropy, TSU) typically measure uncertainty at a single operating point or use temperature as a generation parameter, not as a controlled probe across domains.
- **To our knowledge, no prior work** has empirically demonstrated that factual domains show higher temperature sensitivity than value-laden domains in open-weight models. This may exist in unpublished work; we have not performed an exhaustive literature sweep.
- **The term "learned hedging homogeneity"** does not appear in the literature. The phenomenon it describes (training-induced flattening of response distributions on value-laden topics) is adjacent to known RLHF effects but has not been isolated and measured in this way.
- **Held contradictions** (bi-modal response distributions at a single temperature) are related to the Belnap four-valued logic framework (True, False, Both, Neither) but to our knowledge have not been empirically detected via clustering of repeated samples.

---

## 5. Methodological Notes and Limitations

### 5.1 Sample Size

The Qwen run used 10 prompts per domain (50 total), not the full 200. This is sufficient to demonstrate the domain-level pattern but limits within-domain statistical power. Confidence intervals on domain means are wide. The full 200-prompt GPT-4o-mini run (when complete) will provide stronger statistical evidence.

### 5.2 Embedding Model

all-MiniLM-L6-v2 is a small, general-purpose sentence embedding model. Semantic clustering quality depends on this model's ability to distinguish between meaningfully different responses. For short factual responses ("H2O" vs. "water is H2O"), this model may collapse distinctions that a domain-specific embedder would catch. For longer hedging responses on moral topics, the model may fail to distinguish between subtly different framings. Both effects would compress apparent variance, but likely affect all domains similarly.

### 5.3 DBSCAN Parameters

The clustering uses eps=0.3 and min_samples=5. These were not tuned. Different parameter choices would produce different entropy values and cluster counts. The relative ordering across domains is likely robust to parameter choices, but the absolute values are parameter-dependent.

### 5.4 Single Model

All analyzed results come from a single model (Qwen3:14b). The findings may be specific to this model's training data, architecture, or instruction tuning approach. The GPT-4o-mini comparison run (in progress) is critical for determining whether the pattern is model-general or model-specific.

### 5.5 Confound: Response Length

Factual settled prompts tend to elicit shorter responses ("Paris," "H2O") while moral/opinion prompts tend to elicit longer responses ("This is a complex issue..."). Longer responses with similar semantic content may have higher embedding variance simply due to surface variation. This could inflate factual susceptibility if the model varies *how* it states a fact (short vs. long form) rather than *what* fact it states. The unique_response_ratio metric partially controls for this, but the confound is not fully addressed.

### 5.6 Analysis Artifact: Zero-Padded Domains

The analysis pipeline ran on all 200 prompts, but only 48-50 had actual data. The 150 data-free prompts contribute zero susceptibility, which deflates domain-level means and inflates the number of zero-susceptibility prompts. The domain-level statistics reported in Section 2.1 use the corrected values (only prompts with actual data). The figures, which were generated from the full 200-prompt analysis, include this dilution effect --- the susceptibility box plot and entropy curves are more compressed than they would be from a clean 50-prompt analysis.

---

## 6. Cross-Model Comparison: Three Variance Morphologies

### 6.1 Preliminary Three-Model Results

Mistral 7B analysis (6,335 responses, 43 of 50 prompts, run still completing) reveals a third behavioral regime distinct from both Qwen3 and the preliminary GPT-4o-mini results.

**Susceptibility comparison (dH/dT by domain):**

| Domain | Qwen3:14b | Mistral 7B | GPT-4o-mini (provisional*) |
|--------|-----------|------------|---------------------------|
| factual_settled | 0.2760 | 0.0058 | 0.0304 |
| factual_contested | 0.2327 | 0.0000 | -0.0025 |
| moral_ambiguous | 0.0417 | 0.0000 | 0.0062 |
| moral_clear | 0.0000 | 0.0000 | 0.0000 |
| opinion_aesthetic | 0.0199 | 0.0011 | 0.0030 |
| **Held contradictions** | **4** | **1** | **49*** |

*GPT-4o-mini results are from a prior run with uncertain API key validity. Re-run in progress.

### 6.2 The Three Regimes

The same temperature-susceptibility probe appears to distinguish three different response-governance morphologies:

**Regime 1: Discrete fracture (Qwen3:14b)**
- Factual domains show high susceptibility with distinct mode-splitting under temperature pressure
- Value-laden domains are flat (learned hedging homogeneity)
- 4 held contradictions, all factual, with clean bimodal structure
- Interpretation: domain-structured variance with genuine epistemic fragility in factual regions

**Regime 2: Continuous spread (Mistral 7B)**
- Near-zero susceptibility across ALL domains as measured by DBSCAN clustering
- However, raw embedding distances show meaningful spread: fc_004 (healthiest diet) moves from 0.000 to 0.171 mean pairwise distance, mc_001 (return wallet) moves from 0.000 to 0.147
- The spread is continuous (paraphrase variation) rather than discrete (mode-splitting)
- DBSCAN at eps=0.3 does not detect clusters because responses drift without forming distinct camps
- Only 1 held contradiction
- Interpretation: semantic grading without epistemic fracture --- the model paraphrases but does not contradict itself
- **Caveat:** Mistral may still have domain structure expressed as gradient rather than bifurcation; "speed of light" barely moves (0.007) while "healthiest diet" spreads wide (0.171). This needs further quantification.

**Regime 3: Compressed templating (GPT-4o-mini, provisional)**
- Low susceptibility across all domains with minimal domain separation
- High count of "held contradictions" (49) that are likely hedge-template variants rather than genuine epistemic splits
- Preliminary contradiction classifier: 39/49 = INSUFFICIENT_DATA (ran on wrong dataset), 4 = GENUINE_SPLIT, 4 = HEDGE_VARIANT
- Interpretation: alignment training compresses the response corridor across all domains
- **Caveat:** These results are provisional. The re-run is in progress and needed before any firm claims.

### 6.3 What This Framing Requires to Be Defensible

The three-regime claim requires three metrics per model (not just dH/dT):

1. **Spread:** Mean pairwise embedding distance growth from T=0 to T=1.5
2. **Mode count:** Number of DBSCAN clusters at T=1.0
3. **Template similarity:** Within-cluster cosine similarity (high = paraphrase repetition, low = genuine variety)

These three numbers together separate the regimes without relying on interpretation:
- Fracture = high spread + high mode count
- Continuous spread = moderate spread + low mode count
- Compression = low spread + high template similarity

This analysis has not yet been run as a formal per-prompt table. However, the robustness sweep (Section 6.5) provides strong indirect evidence via spread growth and mode count stability.

### 6.4 Robustness Sweep Results

A robustness sweep was run on frozen response data for Qwen3 and Mistral: 2 embedding models (all-MiniLM-L6-v2, all-mpnet-base-v2) × 2 text modes (raw, normalized) × 4 eps values (0.2, 0.3, 0.4, 0.5) = 16 configurations per model.

Full results: `results/analysis/robustness_sweep_qwen3_14b.json` and `robustness_sweep_mistral_latest.json`

**Qwen3:14b — Regime identity confirmed:**
- Domain ordering (factual > moral): **16/16 PASS.** Every configuration.
- Held contradictions: Stable at 4 (all factual) across all 16 configs.
- Mode counts: Invariant across all configs (factual ~1.4-1.5, all others 1.0).
- Spread growth (mean across configs): factual_contested=0.248, factual_settled=0.180, moral_ambiguous=0.092, moral_clear=0.036, opinion=0.077.
- **Verdict: Discrete fracture is robust.** The regime identity survives every analyzer perturbation.

**Mistral 7B — Regime identity confirmed, with surprise:**
- Domain ordering (factual > moral): **1/16 PASS.** Mistral shows the OPPOSITE ordering.
- Spread growth (mean across configs): moral_ambiguous=0.166, opinion_aesthetic=0.112, factual_contested=0.101, moral_clear=0.100, factual_settled=0.030.
- Mode count: ~1.0 across nearly all configs. Zero bifurcation.
- Held contradictions: 0 in 15/16 configs (1 marginal case at eps=0.2 with mpnet).
- **Verdict: Continuous spread is robust.** Non-bifurcation persists across all analyzer settings. But the fragility is concentrated in moral/opinion domains, not factual — the mirror image of Qwen3.

### 6.4a DeepSeek-R1:8b — Third Regime Confirmed

DeepSeek-R1:8b (7,500 responses, 50 prompts, complete) robustness sweep reveals a third distinct regime:

| Domain | Qwen3 spread | Mistral spread | DeepSeek spread |
|--------|-------------|---------------|-----------------|
| factual_settled | **0.180** | 0.030 | 0.146 |
| factual_contested | **0.248** | 0.101 | 0.161 |
| moral_ambiguous | 0.092 | 0.166 | **0.247** |
| moral_clear | 0.036 | 0.100 | **0.198** |
| opinion_aesthetic | 0.077 | 0.112 | **0.274** |

- Domain ordering: 1/16 PASS factual>moral (moral/opinion always higher)
- Mode count: ~1.0 everywhere. No bifurcation. Zero held contradictions.
- DeepSeek = "Uniform Softness" — everything spreads, nothing locks or fractures hard
- Robustness sweep: 16/16 configs confirm the pattern

**Three confirmed regimes:**

| Model | Regime | Factual | Moral | Modes | Robustness |
|-------|--------|---------|-------|-------|------------|
| Qwen3:14b | Selective Fracture | HIGH (0.18–0.25) | LOW (0.04–0.09) | YES (4 held) | 16/16 |
| Mistral 7B | Selective Spread | LOW (0.03–0.10) | MODERATE (0.10–0.17) | NO | 16/16 |
| DeepSeek-R1:8b | Uniform Softness | MODERATE (0.15–0.16) | HIGH (0.20–0.27) | NO | 16/16 |

**Critical finding: Domain ordering varies across all three models.**

The domain ordering is not universal — it is model-specific. This was not predicted and is arguably stronger than the original domain-inversion finding:

| Domain | Qwen3 spread growth | Mistral spread growth | Direction |
|--------|--------------------|-----------------------|-----------|
| factual_contested | 0.248 | 0.101 | Qwen > Mistral |
| factual_settled | 0.180 | 0.030 | Qwen >> Mistral |
| moral_ambiguous | 0.092 | 0.166 | Mistral > Qwen |
| moral_clear | 0.036 | 0.100 | Mistral > Qwen |
| opinion_aesthetic | 0.077 | 0.112 | Mistral > Qwen |

This suggests the probe is not revealing a universal "facts are more fragile than morals" rule. It is revealing **model-specific semantic fragility landscapes** — different training regimes allocate semantic flexibility differently across domains. The probe is sensitive to the model, not merely to the prompt taxonomy.

**Implication for taxonomy:** The emerging framework has two axes, not one:
- **Axis 1 — Morphology:** fracture (mode-splitting) vs spread (continuous broadening) vs template lock (corridor compression)
- **Axis 2 — Fragility location:** which domains show the most variance under temperature perturbation

Both axes are model-dependent. The probe reveals both.

### 6.5 Limitations of the Cross-Model Comparison

- **Different prompt counts:** Qwen3 and Mistral used 50 curated prompts; GPT-4o-mini used 200. Direct comparison requires filtering to the shared 50.
- **GPT data validity:** Previous run's API key status is uncertain. Re-run in progress.
- **Clustering sensitivity:** DBSCAN eps=0.3 may be too tight for Mistral's continuous spread and too loose for GPT's compressed corridor. The three-metric approach (spread + mode count + template similarity) partially addresses this.
- **Two open models vs one closed model:** The comparison is weighted toward open-weight behavior. Adding a second closed model (e.g., Claude Haiku) would strengthen the regime distinction.
- **UMAP distortion:** The 3D viewer shows qualitative geometry consistent with the metrics but is a projection; volumes, distances, and voids may be artifacts. Claims from visualization are hypotheses, not evidence.

---

## 7. What Remains To Be Done

### 7.1 GPT-4o-mini Re-run (Critical)

The in-progress GPT-4o-mini re-run (200 prompts, 50 reps, 5 temperatures, ~2,030/50,000 collected) will provide clean data for the cross-model comparison. Previous run's API key validity is uncertain, so this re-run is essential before any firm cross-model claims.

### 7.2 DeepSeek-R1:8b Analysis — COMPLETE

DeepSeek-R1:8b (7,500 responses) analyzed and robustness-swept. Confirms a third distinct regime (Uniform Softness). See Section 6.4a.

### 7.3 Three-Metric Formal Table

Compute per-prompt spread, mode count, and template similarity for all models in a single comparable table. The robustness sweep provides domain-level aggregates; prompt-level detail would strengthen individual-prompt analysis.

### 7.3 Contradiction Classifier on Clean GPT Data

The classifier ran on mixed/wrong data (39/49 = INSUFFICIENT_DATA). Rerun on fresh GPT-4o-mini data to determine whether the 49 held contradictions are genuine splits or hedge-template paraphrases.

### 7.4 Mistral Completion + Re-analysis

Mistral run is at ~81%. When complete, rerun analysis on full dataset. Check whether the continuous-spread pattern holds or whether additional prompts reveal mode-splitting on some topics.

### 7.5 UMAP Stability Testing

Rerun 3D projections with different random seeds and perplexity settings. Structures that persist across seeds are likely real; those that don't are projection artifacts.

### 7.6 Phrasing Sensitivity

The prompt bank includes alternate phrasings. Running those through the same pipeline would measure whether susceptibility is a property of the *question* or the *phrasing*.

### 7.7 Silhouette Scores in 384D

Quantify domain separation in the original embedding space, not just in UMAP projections, using silhouette scores or cluster purity metrics.

---

## 8. Connection to CRT/Aether Architecture

### 7.1 Variance-to-Splat Pipeline

The response distributions observed in this experiment map directly to the Gaussian splat representation developed in the memory_splats module:

- **Center (mu):** Mean embedding of responses at a given temperature.
- **Covariance (sigma):** Covariance matrix of the response embedding distribution.
- **Confidence (alpha):** Inverse of semantic entropy --- high entropy means low confidence.

Each prompt at each temperature defines a splat. The temperature sweep traces a path through splat space. Susceptibility is the rate at which the splat expands (or its confidence decreases) along this path.

This mapping is consistent with the observed data: single-cluster prompts produce unimodal response clouds and held-contradiction prompts produce multi-modal clouds. However, no formal goodness-of-fit test has been performed. The Gaussian approximation is a working hypothesis, not a validated result (see Claim 5).

### 7.2 Encoding-Time Uncertainty Tagging

The susceptibility metric could be computed at encoding time by the Mirus encoder. When a new belief enters the system, a quick temperature sweep (e.g., 5 temperatures, 5 reps each = 25 calls) would produce a susceptibility score. This score would tag the belief with its epistemic fragility profile before it enters the belief graph.

High-susceptibility beliefs would be stored with wider splats (more uncertainty). Zero-susceptibility beliefs would be stored as tight points. Held contradictions would be stored as multi-modal splats (mixture of Gaussians) or flagged as Belnap BOTH states.

### 7.3 Domain Classification

The clean domain separation in susceptibility distributions suggests that susceptibility itself could be used as a domain classifier. A belief with dH/dT > 0.2 is likely factual; a belief with dH/dT near zero is likely value-laden or a trained hedging response. This is a cheap, model-intrinsic signal that requires no external ontology.

---

## 9. Novel Claims

The following claims are supported by the data. Each is tagged with its evidence strength.

### Claim 1: Per-domain susceptibility structure exists and is measurable.
**Evidence: Strong.** The five domains separate cleanly in susceptibility space. Cross-domain KL divergences range from 0.15 (within-category) to 9.1 (cross-category). The pattern holds across all 48 prompts with data. This is a descriptive finding with direct empirical support.

### Claim 2: Factual domains show higher susceptibility than value-laden domains in Qwen3:14b.
**Evidence: Strong for this model.** Mean dH/dT for factual domains (0.25) is an order of magnitude higher than for value-laden domains (0.02). The effect is visible in every metric (entropy, variance, cluster count, unique ratio). Generalization to other models requires the GPT-4o-mini comparison run.

### Claim 3: "Learned hedging homogeneity" --- value-laden topics produce artificially flat response distributions.
**Evidence: Moderate.** The zero susceptibility on moral_clear prompts and near-zero on moral_ambiguous/opinion_aesthetic is consistent with this interpretation. However, the alternative explanation (the model genuinely has a single correct approach to these questions) cannot be ruled out without additional evidence such as examining the actual response texts for template-like structure. The phenomenon is observed; the causal attribution to training is an inference.

### Claim 4: Susceptibility discriminates genuine certainty from artificial certainty.
**Evidence: Moderate.** Within the factual_settled domain, we observe both zero-susceptibility prompts (H2O, Mercury) and high-susceptibility prompts (speed of light, number of continents). The zero-susceptibility factual prompts represent genuine model certainty. The zero-susceptibility moral prompts represent trained uniformity. The metric successfully separates these two cases. However, this claim requires a clearer operational definition of "genuine" vs. "artificial" certainty, and the distinction is currently based on domain knowledge about the prompts rather than a model-internal criterion.

### Claim 5: Response distributions from repeated sampling are directly representable as belief splats.
**Evidence: Preliminary.** The DBSCAN clustering results are consistent with Gaussian or mixture-of-Gaussian structure in embedding space. The mapping to splat parameters (center, covariance, confidence) is straightforward. But no formal goodness-of-fit test has been performed to verify that the distributions are actually Gaussian rather than some other shape. This claim is a design hypothesis supported by qualitative consistency with the data.

---

### Claim 6: Temperature-susceptibility probe distinguishes three variance morphologies across models.
**Evidence: Moderate, approaching strong.** Three open-weight models (Qwen3, Mistral, DeepSeek) show three distinct, robustness-confirmed fragility regimes: selective fracture, selective spread, and uniform softness. Each regime survives 16/16 analyzer perturbation configs. The regimes differ on both morphology (how variance expresses) and location (which domains show highest spread). GPT-4o-mini sparse sampling suggests a fourth regime (global compression) but is not yet confirmed. The three-metric formalization (spread + mode count + template similarity) is partially computed via the robustness sweep. Full formal table pending.

---

## 10. Raw Data Reference

- **Raw responses:** `results/raw/*.jsonl` (one file per prompt-temperature combination)
- **Embeddings:** `results/embeddings/*.npy` (cached sentence-transformer embeddings)
- **Analysis results:** `results/analysis/analysis_results.json` (full metrics)
- **Figures:** `results/figures/*.png` (6 visualization files)
- **Prompt bank:** `prompts.py` (200 prompts with alternate phrasings)
- **Runners:** `runner.py` (OpenAI), `runner_ollama.py` (Ollama/local)
- **Analysis code:** `analyze.py` (full pipeline)
