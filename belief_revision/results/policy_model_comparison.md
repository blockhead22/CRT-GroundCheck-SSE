# Policy Model Comparison

## Overall Performance

| Model | Accuracy | Precision | Recall | F1 | Inference Time (ms) |
|-------|----------|-----------|--------|----|--------------------|
| Baseline Heuristic   | 0.861 | 0.896 | 0.870 | 0.867 | 0.00 |
| Logistic Regression  | 0.873 | 0.889 | 0.881 | 0.881 | 0.00 |
| Random Forest        | 1.000 | 1.000 | 1.000 | 1.000 | 0.29 |
| XGBoost              | 1.000 | 1.000 | 1.000 | 1.000 | 0.02 |

## Key Findings

- **Best Model**: Random Forest
- **Best Accuracy**: 100.0%
- **Baseline Accuracy**: 86.1%
- **Improvement over Baseline**: +13.9%

## Success Criteria

- ✅ Accuracy ≥ 85%: ACHIEVED
- ✅ Outperform baseline by ≥10pp: ACHIEVED