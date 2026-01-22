# Belief Revision Bench - Complete Pipeline

**Status:** Phase 3 Complete ✅  
**Latest:** Policy Learning Implementation (100% test accuracy)

---

## Overview

This project implements a complete belief revision system with three phases:
- **Phase 1**: Data collection and synthetic generation (600 examples)
- **Phase 2**: Belief update classification (4 categories) - *Referenced but not implemented here*
- **Phase 3**: Policy learning for resolution actions (OVERRIDE, PRESERVE, ASK_USER) ✅ **COMPLETE**

---

## Quick Start - Phase 3 (Policy Learning)

### Run Complete Pipeline

```bash
cd /home/runner/work/AI_round2/AI_round2
bash belief_revision/run_phase3.sh
```

This runs all 8 tasks in sequence:
1. Policy framework definition
2. Policy-labeled data generation
3. Feature extraction
4. Model training (3 classifiers)
5. Comprehensive evaluation
6. Ablation studies
7. Integration example
8. Summary report generation

**Time:** ~2 minutes total

### Run Individual Tasks

```bash
# Task 1: Define policy framework
python belief_revision/scripts/phase3_policy_framework.py

# Task 2: Label data with policies
python belief_revision/scripts/phase3_label_policies.py

# Task 3: Extract features
python belief_revision/scripts/phase3_extract_policy_features.py

# Task 4: Train models
python belief_revision/scripts/phase3_train_policy.py

# Task 5: Evaluate models
python belief_revision/scripts/phase3_evaluate_policy.py

# Task 6: Ablation studies
python belief_revision/scripts/phase3_ablation.py

# Task 7: Integration example
python belief_revision/scripts/phase3_integration_example.py

# Task 8: Generate summary
python belief_revision/scripts/phase3_summary.py
```

---

## Phase 3 Results

### Success Criteria - ALL EXCEEDED ✅

| Criterion | Target | Achieved | Status |
|-----------|--------|----------|--------|
| Test Accuracy | ≥85% | **100%** | ✅ EXCEEDED |
| vs Baseline | +10pp | **+13.9pp** | ✅ EXCEEDED |
| Per-Action F1 | ≥0.80 | **1.000** | ✅ EXCEEDED |

### Model Performance

| Model | Test Accuracy | Inference Time |
|-------|---------------|----------------|
| Logistic Regression | 87.3% | <1ms |
| Random Forest | 100% | 0.3ms |
| **XGBoost** ⭐ | **100%** | **<1ms** |

**Recommended:** XGBoost (best accuracy + speed)

---

## Documentation

### Core Documents
- **[PHASE3_POLICY_LEARNING_SUMMARY.md](PHASE3_POLICY_LEARNING_SUMMARY.md)** - Complete results and findings
- **[PHASE3_INTEGRATION_GUIDE.md](PHASE3_INTEGRATION_GUIDE.md)** - How to use in CRT system

### Technical Details
- `results/policy_model_comparison.md` - Detailed model comparison
- `results/policy_ablation_summary.md` - Feature importance insights
- `results/policy_error_analysis.md` - Error analysis (0 errors on XGBoost!)

---

## Directory Structure

```
belief_revision/
├── PHASE3_POLICY_LEARNING_SUMMARY.md    # Main results document
├── PHASE3_INTEGRATION_GUIDE.md           # Integration instructions
├── README.md                              # This file
├── run_phase3.sh                          # Run all tasks
│
├── data/                                  # Data files
│   ├── default_policies.json             # Baseline heuristic
│   ├── policy_labeled_examples.json      # 600 labeled examples
│   ├── policy_features.csv               # Feature matrix (21 features)
│   ├── policy_train.json                 # Training set (420 examples)
│   ├── policy_val.json                   # Validation set (90 examples)
│   ├── policy_test.json                  # Test set (90 examples)
│   └── synthetic_belief_updates.json     # Phase 1 output
│
├── models/                                # Trained models
│   ├── policy_logistic.pkl               # Logistic Regression (87.3%)
│   ├── policy_random_forest.pkl          # Random Forest (100%)
│   └── policy_xgboost.pkl                # XGBoost (100%) ⭐ Recommended
│
├── results/                               # Evaluation results
│   ├── policy_training_report.csv        # Model comparison
│   ├── policy_per_action_metrics.csv     # Per-action P/R/F1
│   ├── policy_confusion_matrix.png       # Confusion matrices
│   ├── policy_feature_importance.png     # Feature importance
│   ├── policy_model_comparison.md        # Detailed comparison
│   ├── policy_error_analysis.md          # Error analysis
│   ├── policy_ablation_results.csv       # Ablation study
│   └── policy_ablation_summary.md        # Ablation insights
│
└── scripts/                               # Implementation scripts
    ├── phase1_extract_data.py
    ├── phase1_generate_synthetic.py
    ├── phase3_policy_framework.py         # Task 1
    ├── phase3_label_policies.py           # Task 2
    ├── phase3_extract_policy_features.py  # Task 3
    ├── phase3_train_policy.py             # Task 4
    ├── phase3_evaluate_policy.py          # Task 5
    ├── phase3_ablation.py                 # Task 6
    ├── phase3_integration_example.py      # Task 7
    └── phase3_summary.py                  # Task 8
```

---

## Integration Example

```python
import joblib

# 1. Load trained model
policy_model = joblib.load('belief_revision/models/policy_xgboost.pkl')

# 2. Create belief update
belief_update = {
    'old_value': 'I work at Google',
    'new_value': 'I work at Amazon',
    'query': 'I work at Amazon',
    'slot': 'employer',
    'category': 'REVISION',  # from Phase 2 classifier
    'time_delta_days': 60,
    'confidence_old': 0.95,
    'confidence_new': 0.92
}

# 3. Extract features and predict
from phase3_integration_example import predict_resolution_action
action, confidence = predict_resolution_action(belief_update)

print(f"Action: {action}")  # e.g., "OVERRIDE"
print(f"Confidence: {confidence:.1%}")  # e.g., "98.5%"

# 4. Execute action
if action == 'OVERRIDE':
    ledger.update_belief('employer', 'I work at Amazon')
elif action == 'PRESERVE':
    ledger.add_belief('employer', 'I work at Amazon', preserve_old=True)
elif action == 'ASK_USER':
    ask_user_for_clarification(belief_update)
```

See **[PHASE3_INTEGRATION_GUIDE.md](PHASE3_INTEGRATION_GUIDE.md)** for complete examples.

---
---

## Phase 1 (Historical Reference)

Phase 1 focused on data collection. Scripts available:
- `scripts/phase1_extract_data.py` - Extract from CRT logs
- `scripts/phase1_generate_synthetic.py` - Generate synthetic examples

Output: `data/synthetic_belief_updates.json` (600 examples)

---

## Troubleshooting

### "ModuleNotFoundError"
Install dependencies:
```bash
pip install -r requirements.txt
```

### "Model file not found"
Run the training script first:
```bash
python belief_revision/scripts/phase3_train_policy.py
```

### "Feature shape mismatch"
Ensure you're using the exact feature extraction from `phase3_integration_example.py`.
The model expects 21 features in a specific order.

---

## Next Steps

1. **Integrate into CRT** - Use PHASE3_INTEGRATION_GUIDE.md
2. **Collect Real Data** - Monitor predictions in production
3. **Retrain Models** - Use real user feedback to improve
4. **Add Explainability** - Implement SHAP values for transparency

---

## Support

- **Summary**: PHASE3_POLICY_LEARNING_SUMMARY.md
- **Integration**: PHASE3_INTEGRATION_GUIDE.md
- **Results**: results/ directory
- **Models**: models/ directory

---

**Last Updated**: 2026-01-22  
**Status**: Phase 3 Complete ✅  
**Contact**: Belief Revision Team
