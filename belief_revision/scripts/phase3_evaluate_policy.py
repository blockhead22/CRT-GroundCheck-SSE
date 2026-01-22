#!/usr/bin/env python3
"""
Phase 3, Task 5: Comprehensive Evaluation

This script provides comprehensive evaluation of all trained policy models:
1. Per-action metrics (precision, recall, F1)
2. Confusion matrix visualization
3. Baseline heuristic comparison
4. Model comparison table
5. Feature importance analysis
6. Error analysis
"""

import json
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, classification_report
)
import time

# Directories
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

# Input files
FEATURES_CSV = DATA_DIR / "policy_features.csv"
TEST_JSON = DATA_DIR / "policy_test.json"
DEFAULT_POLICIES_JSON = DATA_DIR / "default_policies.json"

# Model files
MODEL_LR = MODELS_DIR / "policy_logistic.pkl"
MODEL_RF = MODELS_DIR / "policy_random_forest.pkl"
MODEL_XGB = MODELS_DIR / "policy_xgboost.pkl"

# Output files
PER_ACTION_METRICS = RESULTS_DIR / "policy_per_action_metrics.csv"
CONFUSION_MATRIX_PNG = RESULTS_DIR / "policy_confusion_matrix.png"
MODEL_COMPARISON_MD = RESULTS_DIR / "policy_model_comparison.md"
FEATURE_IMPORTANCE_PNG = RESULTS_DIR / "policy_feature_importance.png"
ERROR_ANALYSIS_MD = RESULTS_DIR / "policy_error_analysis.md"

# Policy encoding
POLICY_ENCODING = {'OVERRIDE': 0, 'PRESERVE': 1, 'ASK_USER': 2}
POLICY_DECODING = {0: 'OVERRIDE', 1: 'PRESERVE', 2: 'ASK_USER'}


def load_test_data():
    """Load test data and prepare features/labels."""
    print("\n1. Loading test data...")
    
    # Load feature matrix
    df = pd.read_csv(FEATURES_CSV)
    
    # Load test split
    with open(TEST_JSON, 'r') as f:
        test_data = json.load(f)
    
    test_ids = set(ex['id'] for ex in test_data)
    df_test = df[df['id'].isin(test_ids)]
    
    # Remove duplicates (keep first occurrence)
    df_test = df_test.drop_duplicates(subset=['id'], keep='first')
    
    # Separate features from labels
    exclude_cols = ['policy', 'id', 'slot']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    X_test = df_test[feature_cols].values
    y_test = df_test['policy'].map(POLICY_ENCODING).values
    
    print(f"✓ Loaded {len(X_test)} test examples with {X_test.shape[1]} features")
    
    return X_test, y_test, feature_cols, test_data


def load_models():
    """Load all trained models."""
    print("\n2. Loading trained models...")
    
    lr_model = joblib.load(MODEL_LR)
    print(f"✓ Logistic Regression")
    
    rf_model = joblib.load(MODEL_RF)
    print(f"✓ Random Forest")
    
    xgb_model = joblib.load(MODEL_XGB)
    print(f"✓ XGBoost")
    
    return lr_model, rf_model, xgb_model


def evaluate_baseline(test_data, y_test):
    """
    Evaluate baseline heuristic that uses category-based rules.
    
    Args:
        test_data: List of test examples
        y_test: True labels (already deduplicated)
    
    Returns:
        dict: Baseline predictions and metrics
    """
    print("\n3. Evaluating baseline heuristic...")
    
    # Load default policies
    with open(DEFAULT_POLICIES_JSON, 'r') as f:
        default_policies = json.load(f)
    
    # Create ID->policy mapping from test_data
    id_to_example = {}
    for example in test_data:
        id_to_example[example['id']] = example
    
    # Generate predictions matching deduplicated test set
    baseline_preds = []
    
    # Load test CSV to get deduplicated IDs in same order
    df = pd.read_csv(FEATURES_CSV)
    test_ids = set(ex['id'] for ex in test_data)
    df_test = df[df['id'].isin(test_ids)]
    df_test = df_test.drop_duplicates(subset=['id'], keep='first')
    
    for idx, row in df_test.iterrows():
        example = id_to_example.get(row['id'])
        if example:
            category = example['category']
            predicted_policy = default_policies.get(category, 'ASK_USER')
            baseline_preds.append(POLICY_ENCODING[predicted_policy])
    
    baseline_preds = np.array(baseline_preds)
    
    accuracy = accuracy_score(y_test, baseline_preds)
    
    print(f"✓ Baseline Heuristic Accuracy: {accuracy:.3f}")
    
    return {
        'predictions': baseline_preds,
        'accuracy': accuracy,
        'name': 'Baseline Heuristic'
    }


def generate_per_action_metrics(models_dict, y_test):
    """
    Generate per-action metrics for all models.
    
    Args:
        models_dict: Dict of model predictions
        y_test: True labels
    
    Returns:
        pd.DataFrame: Per-action metrics
    """
    print("\n4. Generating per-action metrics...")
    
    results = []
    
    for model_name, model_info in models_dict.items():
        y_pred = model_info['predictions']
        
        # Calculate metrics for each class
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, labels=[0, 1, 2], average=None
        )
        
        for i, policy_name in enumerate(['OVERRIDE', 'PRESERVE', 'ASK_USER']):
            results.append({
                'Model': model_name,
                'Action': policy_name,
                'Precision': precision[i],
                'Recall': recall[i],
                'F1': f1[i],
                'Support': support[i]
            })
    
    df = pd.DataFrame(results)
    df.to_csv(PER_ACTION_METRICS, index=False)
    
    print(f"✓ Saved per-action metrics: {PER_ACTION_METRICS}")
    
    return df


def plot_confusion_matrices(models_dict, y_test):
    """
    Plot confusion matrices for all models.
    
    Args:
        models_dict: Dict of model predictions
        y_test: True labels
    """
    print("\n5. Generating confusion matrices...")
    
    n_models = len(models_dict)
    fig, axes = plt.subplots(1, n_models, figsize=(6*n_models, 5))
    
    if n_models == 1:
        axes = [axes]
    
    for idx, (model_name, model_info) in enumerate(models_dict.items()):
        y_pred = model_info['predictions']
        
        cm = confusion_matrix(y_test, y_pred)
        
        # Plot
        sns.heatmap(
            cm, 
            annot=True, 
            fmt='d', 
            cmap='Blues',
            xticklabels=['OVERRIDE', 'PRESERVE', 'ASK_USER'],
            yticklabels=['OVERRIDE', 'PRESERVE', 'ASK_USER'],
            ax=axes[idx]
        )
        
        axes[idx].set_title(f'{model_name}\n(Accuracy: {model_info["accuracy"]:.3f})')
        axes[idx].set_ylabel('True Label')
        axes[idx].set_xlabel('Predicted Label')
    
    plt.tight_layout()
    plt.savefig(CONFUSION_MATRIX_PNG, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✓ Saved confusion matrix: {CONFUSION_MATRIX_PNG}")


def generate_model_comparison(models_dict, baseline):
    """
    Generate model comparison table in Markdown.
    
    Args:
        models_dict: Dict of model predictions and metrics
        baseline: Baseline model info
    """
    print("\n6. Generating model comparison table...")
    
    # Add baseline to comparison
    all_models = {'Baseline Heuristic': baseline, **models_dict}
    
    # Create comparison table
    lines = [
        "# Policy Model Comparison\n",
        "## Overall Performance\n",
        "| Model | Accuracy | Precision | Recall | F1 | Inference Time (ms) |",
        "|-------|----------|-----------|--------|----|--------------------|"
    ]
    
    for model_name, model_info in all_models.items():
        accuracy = model_info['accuracy']
        
        # Calculate macro-averaged metrics
        y_pred = model_info['predictions']
        y_test = model_info.get('y_test')
        
        if y_test is not None:
            precision, recall, f1, _ = precision_recall_fscore_support(
                y_test, y_pred, average='macro'
            )
            inference_time = model_info.get('inference_time_ms', 0)
            
            lines.append(
                f"| {model_name:20s} | {accuracy:.3f} | {precision:.3f} | {recall:.3f} | {f1:.3f} | {inference_time:.2f} |"
            )
    
    lines.extend([
        "\n## Key Findings\n",
        f"- **Best Model**: {max(models_dict.items(), key=lambda x: x[1]['accuracy'])[0]}",
        f"- **Best Accuracy**: {max(m['accuracy'] for m in models_dict.values()):.1%}",
        f"- **Baseline Accuracy**: {baseline['accuracy']:.1%}",
        f"- **Improvement over Baseline**: +{(max(m['accuracy'] for m in models_dict.values()) - baseline['accuracy']):.1%}",
        "\n## Success Criteria\n",
        "- ✅ Accuracy ≥ 85%: ACHIEVED" if max(m['accuracy'] for m in models_dict.values()) >= 0.85 else "- ❌ Accuracy ≥ 85%: NOT ACHIEVED",
        "- ✅ Outperform baseline by ≥10pp: ACHIEVED" if (max(m['accuracy'] for m in models_dict.values()) - baseline['accuracy']) >= 0.10 else "- ❌ Outperform baseline by ≥10pp: NOT ACHIEVED"
    ])
    
    # Write to file
    with open(MODEL_COMPARISON_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✓ Saved model comparison: {MODEL_COMPARISON_MD}")


def plot_feature_importance(rf_model, feature_cols):
    """
    Plot feature importance from Random Forest.
    
    Args:
        rf_model: Trained Random Forest model
        feature_cols: List of feature names
    """
    print("\n7. Generating feature importance analysis...")
    
    # Get feature importance
    importances = rf_model.feature_importances_
    
    # Create dataframe
    feature_importance_df = pd.DataFrame({
        'Feature': feature_cols,
        'Importance': importances
    }).sort_values('Importance', ascending=False)
    
    # Plot top 15 features
    top_n = min(15, len(feature_importance_df))
    plt.figure(figsize=(10, 6))
    
    top_features = feature_importance_df.head(top_n)
    plt.barh(range(top_n), top_features['Importance'].values)
    plt.yticks(range(top_n), top_features['Feature'].values)
    plt.xlabel('Importance')
    plt.title('Top 15 Most Important Features for Policy Prediction')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    
    plt.savefig(FEATURE_IMPORTANCE_PNG, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✓ Saved feature importance: {FEATURE_IMPORTANCE_PNG}")
    
    return feature_importance_df


def error_analysis(xgb_model, X_test, y_test, test_data, feature_cols):
    """
    Perform error analysis on misclassified examples.
    
    Args:
        xgb_model: XGBoost model
        X_test: Test features
        y_test: True labels
        test_data: Original test examples
        feature_cols: Feature names
    """
    print("\n8. Performing error analysis...")
    
    # Get predictions
    y_pred = xgb_model.predict(X_test)
    
    # Find misclassified examples
    errors = []
    for i, (true, pred) in enumerate(zip(y_test, y_pred)):
        if true != pred:
            errors.append({
                'index': i,
                'example': test_data[i],
                'true_label': POLICY_DECODING[true],
                'predicted_label': POLICY_DECODING[pred]
            })
    
    # Create error analysis report
    lines = [
        "# Policy Model Error Analysis\n",
        f"## Summary\n",
        f"- Total test examples: {len(y_test)}",
        f"- Correctly classified: {len(y_test) - len(errors)}",
        f"- Misclassified: {len(errors)}",
        f"- Error rate: {len(errors)/len(y_test):.1%}\n",
        "## Misclassified Examples\n"
    ]
    
    # Show up to 10 misclassified examples
    for i, error in enumerate(errors[:10], 1):
        ex = error['example']
        lines.extend([
            f"### Example {i}\n",
            f"**ID**: {ex.get('id', 'N/A')}",
            f"**Category**: {ex.get('category', 'N/A')}",
            f"**Slot**: {ex.get('slot', 'N/A')}",
            f"**Old Value**: {ex.get('old_value', 'N/A')}",
            f"**New Value**: {ex.get('new_value', 'N/A')}",
            f"**True Policy**: {error['true_label']}",
            f"**Predicted Policy**: {error['predicted_label']}",
            f"**Time Delta**: {ex.get('time_delta_days', 'N/A')} days",
            f"**Confidence**: old={ex.get('confidence_old', 0):.2f}, new={ex.get('confidence_new', 0):.2f}\n",
            "**Possible Reason**: ",
        ])
        
        # Try to explain the error
        if error['true_label'] == 'PRESERVE' and error['predicted_label'] == 'ASK_USER':
            lines.append("Model may be overly cautious due to low confidence or ambiguous context.\n")
        elif error['true_label'] == 'OVERRIDE' and error['predicted_label'] == 'PRESERVE':
            lines.append("Model may have interpreted change as refinement rather than replacement.\n")
        elif error['true_label'] == 'ASK_USER' and error['predicted_label'] == 'OVERRIDE':
            lines.append("Model may be too confident despite contradictory signals.\n")
        else:
            lines.append("Ambiguous case requiring more context.\n")
    
    # Common error patterns
    lines.extend([
        "\n## Common Error Patterns\n"
    ])
    
    # Analyze confusion patterns
    error_pairs = [(e['true_label'], e['predicted_label']) for e in errors]
    from collections import Counter
    error_counts = Counter(error_pairs)
    
    if error_counts:
        lines.append("Most common confusions:\n")
        for (true, pred), count in error_counts.most_common(5):
            lines.append(f"- {true} → {pred}: {count} times\n")
    else:
        lines.append("- No misclassifications found!\n")
    
    # Write to file
    with open(ERROR_ANALYSIS_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✓ Saved error analysis: {ERROR_ANALYSIS_MD}")


def main():
    """Main execution function."""
    print("Phase 3, Task 5: Comprehensive Evaluation")
    print("-" * 60)
    
    # Load test data
    X_test, y_test, feature_cols, test_data = load_test_data()
    
    # Load models
    lr_model, rf_model, xgb_model = load_models()
    
    # Evaluate baseline
    baseline = evaluate_baseline(test_data, y_test)
    baseline['y_test'] = y_test
    
    # Get predictions from all models and measure inference time
    print("\nGetting model predictions...")
    
    models_dict = {}
    
    for model_name, model in [
        ('Logistic Regression', lr_model),
        ('Random Forest', rf_model),
        ('XGBoost', xgb_model)
    ]:
        start_time = time.time()
        predictions = model.predict(X_test)
        inference_time = (time.time() - start_time) * 1000 / len(X_test)  # ms per example
        
        accuracy = accuracy_score(y_test, predictions)
        
        models_dict[model_name] = {
            'model': model,
            'predictions': predictions,
            'accuracy': accuracy,
            'inference_time_ms': inference_time,
            'y_test': y_test
        }
        
        print(f"✓ {model_name}: {accuracy:.3f} accuracy, {inference_time:.2f} ms/example")
    
    # Generate per-action metrics
    per_action_df = generate_per_action_metrics(models_dict, y_test)
    
    # Plot confusion matrices
    plot_confusion_matrices(models_dict, y_test)
    
    # Generate model comparison
    generate_model_comparison(models_dict, baseline)
    
    # Feature importance
    feature_importance_df = plot_feature_importance(rf_model, feature_cols)
    
    # Error analysis
    error_analysis(xgb_model, X_test, y_test, test_data, feature_cols)
    
    # Final summary
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    
    print("\nModel Performance:")
    for model_name, model_info in models_dict.items():
        print(f"  {model_name:20s}: {model_info['accuracy']:.1%}")
    
    print(f"\nBaseline Heuristic: {baseline['accuracy']:.1%}")
    
    best_model = max(models_dict.items(), key=lambda x: x[1]['accuracy'])
    improvement = best_model[1]['accuracy'] - baseline['accuracy']
    print(f"\nBest Model: {best_model[0]}")
    print(f"Improvement over Baseline: +{improvement:.1%}")
    
    # Check success criteria
    print("\n" + "="*60)
    print("SUCCESS CRITERIA")
    print("="*60)
    
    best_acc = best_model[1]['accuracy']
    if best_acc >= 0.85:
        print(f"✓ Accuracy ≥ 85%: ACHIEVED ({best_acc:.1%})")
    else:
        print(f"✗ Accuracy ≥ 85%: NOT ACHIEVED ({best_acc:.1%})")
    
    if improvement >= 0.10:
        print(f"✓ Outperform baseline by ≥10pp: ACHIEVED (+{improvement:.1%})")
    else:
        print(f"✗ Outperform baseline by ≥10pp: NOT ACHIEVED (+{improvement:.1%})")
    
    # Check per-action F1 scores
    xgb_metrics = per_action_df[per_action_df['Model'] == 'XGBoost']
    min_f1 = xgb_metrics['F1'].min()
    if min_f1 >= 0.80:
        print(f"✓ All per-action F1 ≥ 0.80: ACHIEVED (min: {min_f1:.3f})")
    else:
        print(f"✗ All per-action F1 ≥ 0.80: NOT ACHIEVED (min: {min_f1:.3f})")
    
    print("\n✓ Comprehensive evaluation complete!")
    print("\nNext step: Run phase3_ablation.py")


if __name__ == "__main__":
    main()
