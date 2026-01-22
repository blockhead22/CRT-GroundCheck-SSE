# Policy Ablation Study Summary
## Overview
This ablation study identifies which features are critical for policy prediction.
We systematically remove feature groups and measure performance degradation.

## Results
| Feature Set | Accuracy | Δ from Full | # Features ||-------------|----------|-------------|------------|| All Features (Baseline)        | 1.000 | +0.000 | 21 || No Category                    | 0.987 | -0.013 | 15 || No Confidence                  | 0.962 | -0.038 | 16 || No Linguistic                  | 1.000 | +0.000 | 18 || No Slot Type                   | 1.000 | +0.000 | 16 || Minimal (Category + Confidence) | 1.000 | +0.000 | 9 || Top 5 Important                | 0.975 | -0.025 | 5 |
## Key Findings
- No single feature group is critical (all drops < 5%)

### Non-Critical Feature Groups (can be removed with <1% impact):
- **No Linguistic**: 0.0% impact
- **No Slot Type**: 0.0% impact
- **Minimal (Category + Confidence)**: 0.0% impact

## Simplification Opportunity
Using only the **top 5 most important features** achieves 97.5% accuracy (-2.5% vs full model), reducing feature count by 76%.

## Top 10 Most Important Features
12. **category_CONFLICT**: 0.1924
1. **time_delta_days**: 0.1745
13. **category_REFINEMENT**: 0.1466
2. **semantic_similarity**: 0.1062
15. **category_TEMPORAL**: 0.0997
8. **is_factual_slot**: 0.0424
16. **slot_type_factual**: 0.0393
3. **confidence_old**: 0.0317
7. **confidence_delta**: 0.0291
6. **drift_score**: 0.0269

## Recommendations
- **For production**: Use full feature set to maximize accuracy
- **For interpretation**: Focus on top 5-10 features
- **For efficiency**: Minimal model (category + confidence) may suffice if speed is critical
