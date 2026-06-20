# Mirus/Holden Governance-Dose Results

Run: 2026-06-19  
Result artifact: `results/governance_dose_1781852832.json`

```text
532ecd7b992a370e921d3387a3998092dba221b6ce3f45ecb86a85db9397ca49  results/governance_dose_1781852832.json
007be64a33760867f056d14d9902bdb636eb5f730fea516eb4db81cc1d75ec6a  governance_dose_eval.py
c300211d64ab4383b78860fb87c340ae5a5c926524b93ac68f926f617a4a515c  GOVERNANCE_DOSE_CONTRACT_20260619.md
```

## Profile Selection

Profiles were selected from the 19 calibration cases only. Ties favored lower
governance exposure.

| Model | Selected dose | Calibration contract | Validation at profile | Validation at fixed Dose 4 |
|---|---:|---:|---:|---:|
| Qwen 2.5 7B | 1 | 17/19 | 6/6 | 6/6 |
| Phi-3 3.8B | 1 | 18/19 | 6/6 | 6/6 |
| Llama 3.2 | 5 | 16/19 | 6/6 | 5/6 |
| Mistral | 1 | 17/19 | 6/6 | 4/6 |

Aggregate validation:

```text
Profile-selected semantic: 24/24
Profile-selected contract: 24/24
Fixed Dose 4 semantic:      22/24
Fixed Dose 4 contract:      21/24
Profile severe failures:    0
Distinct selected doses:    2
Models improved vs Dose 4:  2
Models matched or improved: 4
```

All frozen validation criteria passed.

## Dose Curves

Calibration full-contract passes by dose:

| Model | D0 | D1 | D2 | D3 | D4 | D5 |
|---|---:|---:|---:|---:|---:|---:|
| Qwen | 13 | **17** | **17** | 12 | 11 | 12 |
| Phi-3 | 13 | **18** | 17 | 13 | 13 | 13 |
| Llama 3.2 | 14 | 13 | 15 | 14 | 14 | **16** |
| Mistral | 15 | **17** | **17** | 11 | 11 | 10 |

The response is non-monotonic:

- Qwen, Phi-3, and Mistral degraded as irrelevant governed state accumulated.
- Mistral showed the strongest over-governance effect.
- Llama benefited from maximal explicit warnings and selected Dose 5.
- One fixed scaffold exposure was not optimal for all model families.

## Validation Failures at Fixed Dose 4

Llama:

```text
No, due to POLICY shell.destructive_without_confirmation = forbidden.
```

The answer was behaviorally correct but leaked internal protocol syntax. Its
learned Dose 5 profile removed the leak.

Mistral:

```text
The current name is Marcus ... Previously, it was Daniel.
You are currently working on Juniper, but previously ... Meridian.
```

Its learned Dose 1 profile removed both history leaks.

## Supported Conclusion

This run supports:

> Governance exposure has a model-dependent, non-monotonic optimum. A
> calibration-derived Holden profile can select different doses for
> interchangeable models and generalize better than a fixed full scaffold.

This is the first direct empirical bridge from the original Mirus/Holden
concept to the current CRT runtime architecture:

```text
Mirus  -> maintain complete governed state
Holden -> calibrate how much of that state the active model should see
```

## Limits

- Validation cases were excluded from profile selection, but they were not
  globally virgin: they had been used in earlier interface experiments.
- The profile is one scalar default dose per model. A mature system may require
  profiles by question contract and consequence level.
- The calibration set remains small and hand-authored.
- Dose 1 and Dose 2 tied for Qwen and Mistral; the frozen lower-dose tie-break
  selected Dose 1.
- The auxiliary protocol-label detector is broader than the frozen format judge
  and flags natural uses of words such as “current.” Its counts are diagnostic,
  not retroactive score changes.

The next decisive test is a newly authored, untouched case pack that is created
after profiles are frozen and includes genuine missing-evidence conditions.

