# Findings & Observations

*Living document. Only things actually observed in data. No interpretation.*
*Last updated: 2026-03-28*

---

## Experiment: LLM Belief Variance (Temperature-Swept Semantic Entropy)

### Design
- 50 prompts (10 per domain) x 5 temperatures (0.0, 0.3, 0.7, 1.0, 1.5) x 30 reps
- Domains: factual_settled, factual_contested, moral_ambiguous, moral_clear, opinion_aesthetic
- Embedded with all-MiniLM-L6-v2, clustered with DBSCAN, entropy computed per cell
- Susceptibility = dH/dT (linear regression of entropy vs temperature)

### Model 1: Qwen3:14b (complete, 7,500 responses)
**Date: 2026-03-27**

| Domain | Mean dH/dT | Held Contradictions |
|--------|------------|---------------------|
| factual_settled | 0.276 | 1 |
| factual_contested | 0.233 | 3 |
| moral_ambiguous | 0.042 | 0 |
| opinion_aesthetic | 0.020 | 0 |
| moral_clear | 0.000 | 0 |

- Factual domains show ~10x higher susceptibility than value-laden domains
- 4 held contradictions, all factual (continents, eggs, diet, alcohol)
- Cross-domain KL divergence: 0.15 within-category, 3.7-9.1 cross-category
- Within factual_settled: bimodal — some prompts zero susceptibility (H2O, Mercury), others high (speed of light, continents)
- Bimodal dividing line appears to be response format complexity (single canonical answer vs multiple valid expressions)

### Model 2: Mistral 7B (complete, 7,524 responses)
**Date: 2026-03-27/28**

| Domain | Mean dH/dT | Held Contradictions |
|--------|------------|---------------------|
| factual_settled | 0.006 | 0 |
| factual_contested | 0.000 | 0 |
| moral_ambiguous | 0.000 | 0 |
| moral_clear | 0.000 | 0 |
| opinion_aesthetic | 0.001 | 0 |

- Near-zero susceptibility across ALL domains (DBSCAN-based)
- BUT raw embedding distances tell a different story:
  - healthiest diet (fc_004): 0.000 → 0.171 mean pairwise distance T=0→T=1.5
  - return wallet (mc_001): 0.000 → 0.147
  - speed of light (fs_006): 0.000 → 0.007
- Variation is continuous spread without mode-splitting — DBSCAN at eps=0.3 doesn't find clusters because nothing bifurcates
- 1 held contradiction in 1/16 robustness configs (marginal, eps=0.2 with mpnet)

### Model 3: DeepSeek-R1:8b (in progress, ~46% as of 2026-03-28)
**Date: 2026-03-28**
- Results pending

### Model 4: GPT-4o-mini (re-running, ~4%, rate-limited at 8.84s/req)
**Date: 2026-03-28**
- Previous run showed 49 held contradictions across all domains, compressed susceptibility everywhere
- Previous run data validity uncertain (API key issue)
- Re-run in progress

### Robustness Sweep
**Date: 2026-03-28**

16 configurations per model: 2 embedders (MiniLM, mpnet) x 2 text modes (raw, normalized) x 4 eps values (0.2, 0.3, 0.4, 0.5)

**Qwen3: 16/16 PASS on factual > moral domain ordering**
- Held contradictions stable at 4 (all factual) across all 16 configs
- Mode counts invariant
- Spread growth robust across all configs

**Mistral: 1/16 PASS on factual > moral — INVERTED ordering**
- Moral/opinion domains spread MORE than factual
- Spread growth (mean across configs): moral_ambiguous=0.166, opinion=0.112, factual_contested=0.101, moral_clear=0.100, factual_settled=0.030
- Mode count ~1.0 across all configs — zero bifurcation
- The domain ordering FLIPS between models under the same probe

### TemplateDetector Results on Real Data
**Date: 2026-03-28**

| Prompt | Model | Classification | Variance | Hedges Found |
|--------|-------|---------------|----------|--------------|
| mc_001 moral_clear T=1.5 | Qwen3 | GENUINE_CONFIDENCE | 0.005 | none |
| ma_004 trolley T=1.5 | Qwen3 | EXPLORATORY | 0.226 | it-depends |
| fs_001 factual T=0.0 | Qwen3 | GENUINE_CONFIDENCE | 0.000 | none |
| fs_006 speed_light T=1.5 | Qwen3 | GENUINE_UNCERTAINTY | 0.499 | none |
| oa_001 opinion T=1.5 | Qwen3 | TEMPLATE_LOCK | 0.028 | subjectivity, individual-preference, equal-validity |
| mc_001 moral T=1.5 | Mistral | GENUINE_CONFIDENCE | 0.147 | none |
| oa_001 opinion T=1.5 | Mistral | EXPLORATORY | 0.183 | individual-preference |
| fs_001 factual T=0.0 | Mistral | GENUINE_CONFIDENCE | 0.000 | none |

### Prior Art Search
**Date: 2026-03-28**

No existing system combines persistent trust-scored memory encoding + governed output reconstruction + auditable belief/speech gap. Closest:
- MASK benchmark — measures belief/speech gap, doesn't govern it
- Representation engineering (RepE) — manipulates honesty at inference, not integrated with memory
- Letta/MemGPT — tiered memory, no trust scoring or belief/speech separation
- Kumiho (arXiv:2603.17244) — AGM-compliant graph memory, 93.3% on LoCoMo-Plus, no uncertainty modeling or held contradictions

---

## Raw Data Locations

| Dataset | Path | Status |
|---------|------|--------|
| Qwen3 raw | results/raw/qwen3_14b/ | Complete |
| Mistral raw | results/raw/mistral_latest/ | Complete |
| DeepSeek raw | results/raw/deepseek-r1_8b/ | In progress |
| GPT-4o-mini raw | results/raw/ | Re-running |
| Qwen3 robustness | results/analysis/robustness_sweep_qwen3_14b.json | Complete |
| Mistral robustness | results/analysis/robustness_sweep_mistral_latest.json | Complete |
| Figures | results/figures/ | Qwen3 only |
