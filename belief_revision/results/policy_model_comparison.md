# Policy Model Comparison

## Overall Performance

| Model | Accuracy | Precision | Recall | F1 | Inference Time (ms) |
|-------|----------|-----------|--------|----|--------------------|
| Baseline Heuristic   | 0.861 | 0.911 | 0.865 | 0.868 | 0.00 |
| Logistic Regression  | 0.873 | 0.891 | 0.879 | 0.883 | 0.00 |
| Random Forest        | 0.987 | 0.989 | 0.988 | 0.988 | 0.37 |
| XGBoost              | 1.000 | 1.000 | 1.000 | 1.000 | 0.01 |

## Key Findings

- **Best Model**: XGBoost
- **Best Accuracy**: 100.0%
- **Baseline Accuracy**: 86.1%
- **Improvement over Baseline**: +13.9%

## Success Criteria

- ✅ Accuracy ≥ 85%: ACHIEVED
- ✅ Outperform baseline by ≥10pp: ACHIEVED