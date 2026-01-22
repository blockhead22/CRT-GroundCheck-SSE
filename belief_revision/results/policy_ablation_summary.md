# Policy Ablation Study Summary
## Overview
This ablation study identifies which features are critical for policy prediction.
We systematically remove feature groups and measure performance degradation.

## Results
| Feature Set | Accuracy | Δ from Full | # Features ||-------------|----------|-------------|------------|| All Features (Baseline)        | 1.000 | +0.000 | 21 || No Category                    | 1.000 | +0.000 | 15 || No Confidence                  | 0.924 | -0.076 | 16 || No Linguistic                  | 1.000 | +0.000 | 18 || No Slot Type                   | 1.000 | +0.000 | 16 || Minimal (Category + Confidence) | 0.987 | -0.013 | 9 || Top 5 Important                | 0.924 | -0.076 | 5 |
## Key Findings
### Critical Feature Groups (removal causes >5% accuracy drop):
- **No Confidence**: -7.6% drop
- **Top 5 Important**: -7.6% drop

### Non-Critical Feature Groups (can be removed with <1% impact):
- **No Category**: 0.0% impact
- **No Linguistic**: 0.0% impact
- **No Slot Type**: 0.0% impact

## Simplification Opportunity
Using only the **top 5 most important features** achieves 92.4% accuracy (-7.6% vs full model), reducing feature count by 76%.

## Top 10 Most Important Features
12. **category_CONFLICT**: 0.2037
1. **time_delta_days**: 0.1738
13. **category_REFINEMENT**: 0.1333
15. **category_TEMPORAL**: 0.0873
2. **semantic_similarity**: 0.0859
4. **confidence_new**: 0.0442
8. **is_factual_slot**: 0.0375
6. **drift_score**: 0.0359
3. **confidence_old**: 0.0354
16. **slot_type_factual**: 0.0319

## Recommendations
- **For production**: Use full feature set to maximize accuracy
- **For interpretation**: Focus on top 5-10 features
- **For efficiency**: Minimal model (category + confidence) may suffice if speed is critical
