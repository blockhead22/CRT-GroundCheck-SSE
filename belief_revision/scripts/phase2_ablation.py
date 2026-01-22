#!/usr/bin/env python3
"""
Phase 2: Ablation Studies

Trains XGBoost models with different feature sets to understand
feature importance and contribution to model performance.

Evaluates impact of removing different feature groups.
"""

import json
import numpy as np
import pandas as pd
import pickle
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

INPUT_FEATURES = DATA_DIR / "features.csv"
TRAIN_DATA = DATA_DIR / "train.json"
TEST_DATA = DATA_DIR / "test.json"

# Output paths
ABLATION_RESULTS = RESULTS_DIR / "ablation_results.csv"
FEATURE_IMPORTANCE_PNG = RESULTS_DIR / "feature_importance.png"
ABLATION_SUMMARY = RESULTS_DIR / "ablation_summary.md"

# Random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Create directories
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Category mapping
CATEGORY_MAP = {
    'REFINEMENT': 0,
    'REVISION': 1,
    'TEMPORAL': 2,
    'CONFLICT': 3
}
CATEGORY_NAMES = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']

# Define feature groups
ALL_FEATURES = [
    'query_to_old_similarity', 'cross_memory_similarity',
    'time_delta_days', 'recency_score', 'update_frequency',
    'query_word_count', 'old_word_count', 'new_word_count', 'word_count_delta',
    'negation_in_new', 'negation_in_old', 'negation_delta',
    'temporal_in_new', 'temporal_in_old', 'correction_markers',
    'memory_confidence', 'trust_score', 'drift_score'
]

SEMANTIC_FEATURES = ['query_to_old_similarity', 'cross_memory_similarity']
TEMPORAL_FEATURES = ['time_delta_days', 'recency_score', 'update_frequency']
LINGUISTIC_FEATURES = [
    'query_word_count', 'old_word_count', 'new_word_count', 'word_count_delta',
    'negation_in_new', 'negation_in_old', 'negation_delta'
]
TOP_5_FEATURES = ['time_delta_days', 'recency_score', 'drift_score', 'word_count_delta', 'trust_score']

def load_data():
    """Load features and prepare train/test data."""
    print("Loading features and splits...")
    
    # Load features
    df = pd.read_csv(INPUT_FEATURES)
    
    # Load train/test splits
    with open(TRAIN_DATA, 'r') as f:
        train_data = json.load(f)
    with open(TEST_DATA, 'r') as f:
        test_data = json.load(f)
    
    # Get train/test IDs
    train_ids = [item['id'] for item in train_data]
    test_ids = [item['id'] for item in test_data]
    
    # Split data
    train_df = df[df['id'].isin(train_ids)]
    test_df = df[df['id'].isin(test_ids)]
    
    print(f"✓ Loaded {len(train_df)} training examples, {len(test_df)} test examples")
    print(f"  Total features available: {len(ALL_FEATURES)}")
    
    return train_df, test_df

def train_and_evaluate_xgboost(X_train, y_train, X_test, y_test, feature_set_name):
    """Train XGBoost model and evaluate on test set."""
    print(f"\n  Training XGBoost with {feature_set_name}...")
    print(f"    Features: {X_train.shape[1]}")
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=RANDOM_SEED,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train, verbose=False)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"    Accuracy: {accuracy:.4f}")
    
    return accuracy, model

def run_ablation_studies(train_df, test_df):
    """Run ablation studies with different feature sets."""
    print("\n" + "="*60)
    print("ABLATION STUDIES")
    print("="*60)
    
    results = []
    
    # Define feature sets
    feature_sets = {
        'All Features': ALL_FEATURES,
        'No Semantic': [f for f in ALL_FEATURES if f not in SEMANTIC_FEATURES],
        'No Temporal': [f for f in ALL_FEATURES if f not in TEMPORAL_FEATURES],
        'No Linguistic': [f for f in ALL_FEATURES if f not in LINGUISTIC_FEATURES],
        'Top 5 Only': TOP_5_FEATURES
    }
    
    baseline_accuracy = None
    
    for feature_set_name, features in feature_sets.items():
        # Prepare data
        X_train = train_df[features].values
        y_train = train_df['category'].map(CATEGORY_MAP).values
        X_test = test_df[features].values
        y_test = test_df['category'].map(CATEGORY_MAP).values
        
        # Train and evaluate
        accuracy, model = train_and_evaluate_xgboost(
            X_train, y_train, X_test, y_test, feature_set_name
        )
        
        # Calculate delta from baseline
        if feature_set_name == 'All Features':
            baseline_accuracy = accuracy
            delta = 0.0
        else:
            delta = accuracy - baseline_accuracy
        
        results.append({
            'Feature_Set': feature_set_name,
            'Accuracy': accuracy,
            'Delta_from_Full': delta,
            'Features_Used': len(features)
        })
    
    return pd.DataFrame(results), baseline_accuracy

def compute_feature_importance(train_df, test_df):
    """Compute feature importance using Random Forest."""
    print("\n" + "="*60)
    print("FEATURE IMPORTANCE ANALYSIS")
    print("="*60)
    
    X_train = train_df[ALL_FEATURES].values
    y_train = train_df['category'].map(CATEGORY_MAP).values
    
    print("\nTraining Random Forest for feature importance...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=RANDOM_SEED,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    
    # Get feature importances
    importances = rf.feature_importances_
    feature_importance_df = pd.DataFrame({
        'feature': ALL_FEATURES,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    print(f"✓ Feature importance computed")
    print(f"\nTop 5 most important features:")
    for idx, row in feature_importance_df.head(5).iterrows():
        print(f"  {row['feature']}: {row['importance']:.4f}")
    
    return feature_importance_df

def plot_feature_importance(feature_importance_df):
    """Create feature importance visualization."""
    print("\nCreating feature importance visualization...")
    
    # Take top 15 features
    top_features = feature_importance_df.head(15)
    
    plt.figure(figsize=(10, 8))
    plt.barh(range(len(top_features)), top_features['importance'].values)
    plt.yticks(range(len(top_features)), top_features['feature'].values)
    plt.xlabel('Importance', fontsize=12)
    plt.ylabel('Feature', fontsize=12)
    plt.title('Top 15 Feature Importances (Random Forest)', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(FEATURE_IMPORTANCE_PNG, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✓ Saved to {FEATURE_IMPORTANCE_PNG}")

def generate_summary(results_df, baseline_accuracy, feature_importance_df):
    """Generate ablation summary markdown."""
    print("\nGenerating ablation summary...")
    
    summary = f"""# Ablation Study Results

## Overview

This report presents the results of ablation studies conducted to understand
the contribution of different feature groups to the belief revision classifier.

## Methodology

- **Model**: XGBoost (100 estimators, max_depth=5)
- **Baseline**: All {len(ALL_FEATURES)} features
- **Baseline Accuracy**: {baseline_accuracy:.4f} ({baseline_accuracy*100:.2f}%)
- **Random Seed**: {RANDOM_SEED}

## Results Summary

### Performance by Feature Set

| Feature Set | Accuracy | Delta from Full | Features Used |
|------------|----------|-----------------|---------------|
"""
    
    for _, row in results_df.iterrows():
        summary += f"| {row['Feature_Set']} | {row['Accuracy']:.4f} | "
        if row['Delta_from_Full'] >= 0:
            summary += f"+{row['Delta_from_Full']:.4f}"
        else:
            summary += f"{row['Delta_from_Full']:.4f}"
        summary += f" | {row['Features_Used']} |\n"
    
    summary += f"""
## Key Findings

"""
    
    # Analyze results
    no_semantic = results_df[results_df['Feature_Set'] == 'No Semantic'].iloc[0]
    no_temporal = results_df[results_df['Feature_Set'] == 'No Temporal'].iloc[0]
    no_linguistic = results_df[results_df['Feature_Set'] == 'No Linguistic'].iloc[0]
    top5 = results_df[results_df['Feature_Set'] == 'Top 5 Only'].iloc[0]
    
    # Find most impactful ablation
    worst_ablation = results_df[results_df['Feature_Set'] != 'All Features'].nsmallest(1, 'Accuracy').iloc[0]
    
    summary += f"""1. **Most Critical Feature Group**: {worst_ablation['Feature_Set']}
   - Removing this group caused the largest accuracy drop: {abs(worst_ablation['Delta_from_Full']):.4f}
   - Demonstrates the importance of these features for classification

2. **Semantic Features Impact**:
   - Accuracy without semantic features: {no_semantic['Accuracy']:.4f}
   - Delta: {no_semantic['Delta_from_Full']:.4f}
   - Semantic similarity features (query-to-old, cross-memory) {'are critical' if abs(no_semantic['Delta_from_Full']) > 0.05 else 'have moderate impact'}

3. **Temporal Features Impact**:
   - Accuracy without temporal features: {no_temporal['Accuracy']:.4f}
   - Delta: {no_temporal['Delta_from_Full']:.4f}
   - Time-based features (time_delta, recency, update_frequency) {'are critical' if abs(no_temporal['Delta_from_Full']) > 0.05 else 'have moderate impact'}

4. **Linguistic Features Impact**:
   - Accuracy without linguistic features: {no_linguistic['Accuracy']:.4f}
   - Delta: {no_linguistic['Delta_from_Full']:.4f}
   - Word count and negation features {'are critical' if abs(no_linguistic['Delta_from_Full']) > 0.05 else 'have moderate impact'}

5. **Top 5 Features Performance**:
   - Accuracy with only 5 features: {top5['Accuracy']:.4f}
   - Delta from full set: {top5['Delta_from_Full']:.4f}
   - Using {top5['Features_Used']} features achieves {top5['Accuracy']/baseline_accuracy*100:.1f}% of full performance
   - Features: {', '.join(TOP_5_FEATURES)}

## Feature Importance Rankings

Top 10 features by Random Forest importance:

"""
    
    for idx, row in feature_importance_df.head(10).iterrows():
        summary += f"{idx+1}. **{row['feature']}**: {row['importance']:.4f}\n"
    
    summary += f"""
## Recommendations

"""
    
    if top5['Accuracy'] > baseline_accuracy * 0.95:
        summary += f"""1. **Feature Selection**: The top 5 features achieve {top5['Accuracy']/baseline_accuracy*100:.1f}% of full performance.
   Consider using a reduced feature set for faster inference.

"""
    
    if abs(no_temporal['Delta_from_Full']) > 0.05:
        summary += """2. **Temporal Features Critical**: Time-based features are essential for accurate classification.
   Ensure these are always computed accurately.

"""
    
    if abs(no_semantic['Delta_from_Full']) > 0.05:
        summary += """3. **Semantic Features Critical**: Similarity-based features are essential for distinguishing categories.
   Consider upgrading the embedding model for better semantic understanding.

"""
    
    summary += f"""
## Visualization

Feature importance visualization saved to: `{FEATURE_IMPORTANCE_PNG.name}`

---
*Generated by phase2_ablation.py*
"""
    
    with open(ABLATION_SUMMARY, 'w') as f:
        f.write(summary)
    
    print(f"✓ Saved to {ABLATION_SUMMARY}")

def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("PHASE 2: ABLATION STUDIES")
    print("="*60)
    
    # Load data
    train_df, test_df = load_data()
    
    # Run ablation studies
    results_df, baseline_accuracy = run_ablation_studies(train_df, test_df)
    
    # Save results
    results_df.to_csv(ABLATION_RESULTS, index=False)
    print(f"\n✓ Results saved to {ABLATION_RESULTS}")
    
    # Compute feature importance
    feature_importance_df = compute_feature_importance(train_df, test_df)
    
    # Create visualization
    plot_feature_importance(feature_importance_df)
    
    # Generate summary
    generate_summary(results_df, baseline_accuracy, feature_importance_df)
    
    print("\n" + "="*60)
    print("ABLATION STUDY COMPLETE")
    print("="*60)
    print(f"\nOutputs:")
    print(f"  1. {ABLATION_RESULTS}")
    print(f"  2. {FEATURE_IMPORTANCE_PNG}")
    print(f"  3. {ABLATION_SUMMARY}")
    print()

if __name__ == "__main__":
    main()
