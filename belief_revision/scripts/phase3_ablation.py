#!/usr/bin/env python3
"""
Phase 3, Task 6: Ablation Studies

This script performs ablation studies to identify which features are critical
for policy prediction. Tests various feature combinations and measures
performance degradation.
"""

import json
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.metrics import accuracy_score
import xgboost as xgb

# Directories
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

# Input files
FEATURES_CSV = DATA_DIR / "policy_features.csv"
TRAIN_JSON = DATA_DIR / "policy_train.json"
TEST_JSON = DATA_DIR / "policy_test.json"

# Output files
ABLATION_RESULTS_CSV = RESULTS_DIR / "policy_ablation_results.csv"
ABLATION_SUMMARY_MD = RESULTS_DIR / "policy_ablation_summary.md"

# Policy encoding
POLICY_ENCODING = {'OVERRIDE': 0, 'PRESERVE': 1, 'ASK_USER': 2}


def load_data():
    """Load and prepare training and test data."""
    print("\n1. Loading data...")
    
    # Load feature matrix
    df = pd.read_csv(FEATURES_CSV)
    df = df.drop_duplicates(subset=['id'], keep='first')
    
    # Load splits
    with open(TRAIN_JSON, 'r') as f:
        train_data = json.load(f)
    with open(TEST_JSON, 'r') as f:
        test_data = json.load(f)
    
    # Get IDs
    train_ids = set(ex['id'] for ex in train_data)
    test_ids = set(ex['id'] for ex in test_data)
    
    # Split dataframe
    df_train = df[df['id'].isin(train_ids)]
    df_test = df[df['id'].isin(test_ids)]
    
    # Get all feature columns (excluding metadata)
    exclude_cols = ['policy', 'id', 'slot']
    all_features = [col for col in df.columns if col not in exclude_cols]
    
    # Prepare full dataset
    X_train_full = df_train[all_features].values
    X_test_full = df_test[all_features].values
    y_train = df_train['policy'].map(POLICY_ENCODING).values
    y_test = df_test['policy'].map(POLICY_ENCODING).values
    
    print(f"✓ Train: {len(X_train_full)} examples")
    print(f"✓ Test: {len(X_test_full)} examples")
    print(f"✓ Total features: {len(all_features)}")
    
    return df_train, df_test, all_features, X_train_full, X_test_full, y_train, y_test


def train_and_evaluate(X_train, y_train, X_test, y_test, feature_set_name):
    """
    Train XGBoost model and evaluate.
    
    Args:
        X_train, y_train: Training data
        X_test, y_test: Test data
        feature_set_name: Name of feature configuration
    
    Returns:
        tuple: (accuracy, feature_set_name, num_features)
    """
    model = xgb.XGBClassifier(
        objective='multi:softmax',
        num_class=3,
        max_depth=5,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    return accuracy, feature_set_name, X_train.shape[1]


def run_ablation_studies(df_train, df_test, all_features, y_train, y_test):
    """
    Run ablation studies with different feature combinations.
    
    Returns:
        pd.DataFrame: Results of ablation studies
    """
    print("\n2. Running ablation studies...")
    
    results = []
    
    # Helper to get feature indices
    def get_feature_cols(feature_names):
        return [i for i, f in enumerate(all_features) if f in feature_names]
    
    # Helper to exclude features
    def get_all_except(exclude_patterns):
        return [f for f in all_features if not any(p in f for p in exclude_patterns)]
    
    # Get full model baseline
    X_train_full = df_train[all_features].values
    X_test_full = df_test[all_features].values
    
    baseline_acc, _, _ = train_and_evaluate(
        X_train_full, y_train, X_test_full, y_test, "All Features (Baseline)"
    )
    
    print(f"  ✓ Baseline (all features): {baseline_acc:.3f}")
    results.append({
        'Feature_Set': 'All Features (Baseline)',
        'Accuracy': baseline_acc,
        'Delta_from_Full': 0.0,
        'Features_Used': len(all_features)
    })
    
    # === Ablation 1: No category features ===
    print("  • Ablation 1: Removing category features...")
    features_no_category = get_all_except(['category_'])
    if features_no_category:
        X_train = df_train[features_no_category].values
        X_test = df_test[features_no_category].values
        acc, _, n_features = train_and_evaluate(
            X_train, y_train, X_test, y_test, "No Category"
        )
        print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
        results.append({
            'Feature_Set': 'No Category',
            'Accuracy': acc,
            'Delta_from_Full': acc - baseline_acc,
            'Features_Used': n_features
        })
    
    # === Ablation 2: No confidence features ===
    print("  • Ablation 2: Removing confidence features...")
    features_no_confidence = [f for f in all_features 
                              if 'confidence' not in f and 'trust' not in f and 'drift' not in f]
    if features_no_confidence:
        X_train = df_train[features_no_confidence].values
        X_test = df_test[features_no_confidence].values
        acc, _, n_features = train_and_evaluate(
            X_train, y_train, X_test, y_test, "No Confidence"
        )
        print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
        results.append({
            'Feature_Set': 'No Confidence',
            'Accuracy': acc,
            'Delta_from_Full': acc - baseline_acc,
            'Features_Used': n_features
        })
    
    # === Ablation 3: No linguistic features ===
    print("  • Ablation 3: Removing linguistic features...")
    features_no_linguistic = [f for f in all_features 
                              if 'has_correction' not in f and 'has_temporal' not in f 
                              and 'user_signal' not in f]
    if features_no_linguistic:
        X_train = df_train[features_no_linguistic].values
        X_test = df_test[features_no_linguistic].values
        acc, _, n_features = train_and_evaluate(
            X_train, y_train, X_test, y_test, "No Linguistic"
        )
        print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
        results.append({
            'Feature_Set': 'No Linguistic',
            'Accuracy': acc,
            'Delta_from_Full': acc - baseline_acc,
            'Features_Used': n_features
        })
    
    # === Ablation 4: No slot type features ===
    print("  • Ablation 4: Removing slot type features...")
    features_no_slot = [f for f in all_features 
                        if 'slot_type' not in f and 'is_factual' not in f and 'is_preference' not in f]
    if features_no_slot:
        X_train = df_train[features_no_slot].values
        X_test = df_test[features_no_slot].values
        acc, _, n_features = train_and_evaluate(
            X_train, y_train, X_test, y_test, "No Slot Type"
        )
        print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
        results.append({
            'Feature_Set': 'No Slot Type',
            'Accuracy': acc,
            'Delta_from_Full': acc - baseline_acc,
            'Features_Used': n_features
        })
    
    # === Ablation 5: Minimal features (category + confidence) ===
    print("  • Ablation 5: Minimal features (category + confidence only)...")
    minimal_features = [f for f in all_features 
                       if 'category_' in f or 'confidence' in f]
    if minimal_features:
        X_train = df_train[minimal_features].values
        X_test = df_test[minimal_features].values
        acc, _, n_features = train_and_evaluate(
            X_train, y_train, X_test, y_test, "Minimal (Category + Confidence)"
        )
        print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
        results.append({
            'Feature_Set': 'Minimal (Category + Confidence)',
            'Accuracy': acc,
            'Delta_from_Full': acc - baseline_acc,
            'Features_Used': n_features
        })
    
    # === Ablation 6: Top 5 most important features (from RF) ===
    print("  • Ablation 6: Top 5 most important features...")
    # Load RF model to get feature importance
    rf_model = joblib.load(MODELS_DIR / "policy_random_forest.pkl")
    feature_importance = pd.DataFrame({
        'feature': all_features,
        'importance': rf_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    top_5_features = feature_importance.head(5)['feature'].tolist()
    X_train = df_train[top_5_features].values
    X_test = df_test[top_5_features].values
    acc, _, n_features = train_and_evaluate(
        X_train, y_train, X_test, y_test, "Top 5 Important"
    )
    print(f"    Features: {', '.join(top_5_features)}")
    print(f"    Accuracy: {acc:.3f} (Δ: {acc - baseline_acc:+.3f})")
    results.append({
        'Feature_Set': 'Top 5 Important',
        'Accuracy': acc,
        'Delta_from_Full': acc - baseline_acc,
        'Features_Used': n_features
    })
    
    return pd.DataFrame(results), feature_importance


def save_results(results_df, feature_importance):
    """Save ablation results to CSV and summary to Markdown."""
    print("\n3. Saving results...")
    
    # Save CSV
    results_df.to_csv(ABLATION_RESULTS_CSV, index=False)
    print(f"✓ Ablation results: {ABLATION_RESULTS_CSV}")
    
    # Generate summary
    lines = [
        "# Policy Ablation Study Summary\n",
        "## Overview\n",
        "This ablation study identifies which features are critical for policy prediction.\n",
        "We systematically remove feature groups and measure performance degradation.\n",
        "\n## Results\n",
        "| Feature Set | Accuracy | Δ from Full | # Features |",
        "|-------------|----------|-------------|------------|"
    ]
    
    for _, row in results_df.iterrows():
        lines.append(
            f"| {row['Feature_Set']:30s} | {row['Accuracy']:.3f} | "
            f"{row['Delta_from_Full']:+.3f} | {row['Features_Used']} |"
        )
    
    lines.extend([
        "\n## Key Findings\n"
    ])
    
    # Identify critical feature groups
    critical_threshold = -0.05  # 5% drop is significant
    critical_ablations = results_df[results_df['Delta_from_Full'] < critical_threshold]
    
    if len(critical_ablations) > 0:
        lines.append("### Critical Feature Groups (removal causes >5% accuracy drop):\n")
        for _, row in critical_ablations.iterrows():
            lines.append(f"- **{row['Feature_Set']}**: {row['Delta_from_Full']:.1%} drop\n")
    else:
        lines.append("- No single feature group is critical (all drops < 5%)\n")
    
    # Identify non-critical features
    non_critical = results_df[results_df['Delta_from_Full'] >= -0.01]
    if len(non_critical) > 1:  # Exclude baseline
        lines.append("\n### Non-Critical Feature Groups (can be removed with <1% impact):\n")
        for _, row in non_critical.iterrows():
            if row['Feature_Set'] != 'All Features (Baseline)':
                lines.append(f"- **{row['Feature_Set']}**: {row['Delta_from_Full']:.1%} impact\n")
    
    # Simplification opportunity
    minimal_result = results_df[results_df['Feature_Set'] == 'Top 5 Important']
    if len(minimal_result) > 0:
        minimal_acc = minimal_result.iloc[0]['Accuracy']
        minimal_delta = minimal_result.iloc[0]['Delta_from_Full']
        lines.extend([
            "\n## Simplification Opportunity\n",
            f"Using only the **top 5 most important features** achieves {minimal_acc:.1%} accuracy ",
            f"({minimal_delta:+.1%} vs full model), reducing feature count by ",
            f"{100 * (1 - 5/results_df.iloc[0]['Features_Used']):.0f}%.\n"
        ])
    
    # Top features
    lines.extend([
        "\n## Top 10 Most Important Features\n"
    ])
    
    for i, row in feature_importance.head(10).iterrows():
        lines.append(f"{i+1}. **{row['feature']}**: {row['importance']:.4f}\n")
    
    lines.extend([
        "\n## Recommendations\n",
        "- **For production**: Use full feature set to maximize accuracy\n",
        "- **For interpretation**: Focus on top 5-10 features\n",
        "- **For efficiency**: Minimal model (category + confidence) may suffice if speed is critical\n"
    ])
    
    # Write summary
    with open(ABLATION_SUMMARY_MD, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))
    
    print(f"✓ Ablation summary: {ABLATION_SUMMARY_MD}")


def main():
    """Main execution function."""
    print("Phase 3, Task 6: Ablation Studies")
    print("-" * 60)
    
    # Load data
    df_train, df_test, all_features, X_train_full, X_test_full, y_train, y_test = load_data()
    
    # Run ablation studies
    results_df, feature_importance = run_ablation_studies(
        df_train, df_test, all_features, y_train, y_test
    )
    
    # Save results
    save_results(results_df, feature_importance)
    
    # Print summary
    print("\n" + "="*60)
    print("ABLATION STUDY SUMMARY")
    print("="*60)
    
    print("\nPerformance Impact:")
    for _, row in results_df.iterrows():
        print(f"  {row['Feature_Set']:30s}: {row['Accuracy']:.3f} ({row['Delta_from_Full']:+.3f})")
    
    print("\n✓ Ablation studies complete!")
    print("\nNext step: Run phase3_integration_example.py")


if __name__ == "__main__":
    main()
