#!/usr/bin/env python3
"""
Phase 2, Task 2: Baseline Model Training

Trains baseline models (Logistic Regression, Random Forest, XGBoost)
with stratified k-fold cross-validation.

Week 3, Days 3-4
"""

import json
import numpy as np
import pandas as pd
import pickle
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
import xgboost as xgb

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

INPUT_FEATURES = DATA_DIR / "features.csv"
TRAIN_DATA = DATA_DIR / "train.json"
VAL_DATA = DATA_DIR / "val.json"
TEST_DATA = DATA_DIR / "test.json"

# Output paths
MODEL_LR = MODELS_DIR / "logistic_regression.pkl"
MODEL_RF = MODELS_DIR / "random_forest.pkl"
MODEL_XGB = MODELS_DIR / "xgboost.pkl"
COMPARISON_CSV = RESULTS_DIR / "baseline_comparison.csv"
COMPARISON_PNG = RESULTS_DIR / "baseline_comparison.png"

# Random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Create directories
MODELS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Category mapping
CATEGORY_MAP = {
    'REFINEMENT': 0,
    'REVISION': 1,
    'TEMPORAL': 2,
    'CONFLICT': 3
}
CATEGORY_NAMES = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']

def load_and_prepare_data():
    """Load features and prepare training data."""
    print("Loading features from CSV...")
    df = pd.read_csv(INPUT_FEATURES)
    
    # Select numeric features only (exclude id, category, slot, text columns)
    feature_columns = [
        'query_to_old_similarity', 'cross_memory_similarity',
        'time_delta_days', 'recency_score', 'update_frequency',
        'query_word_count', 'old_word_count', 'new_word_count', 'word_count_delta',
        'negation_in_new', 'negation_in_old', 'negation_delta',
        'temporal_in_new', 'temporal_in_old', 'correction_markers',
        'memory_confidence', 'trust_score', 'drift_score'
    ]
    
    X = df[feature_columns].values
    y = df['category'].map(CATEGORY_MAP).values
    
    print(f"✓ Loaded {len(X)} examples with {X.shape[1]} features")
    print(f"  Features: {len(feature_columns)}")
    print(f"  Categories: {len(CATEGORY_MAP)}")
    
    return X, y, feature_columns, df

def load_split_data(split_file, df_full):
    """Load specific split and extract features."""
    with open(split_file, 'r') as f:
        split_data = json.load(f)
    
    # Get IDs from split
    split_ids = [item['id'] for item in split_data]
    
    # Filter full dataframe
    split_df = df_full[df_full['id'].isin(split_ids)]
    
    # Feature columns
    feature_columns = [
        'query_to_old_similarity', 'cross_memory_similarity',
        'time_delta_days', 'recency_score', 'update_frequency',
        'query_word_count', 'old_word_count', 'new_word_count', 'word_count_delta',
        'negation_in_new', 'negation_in_old', 'negation_delta',
        'temporal_in_new', 'temporal_in_old', 'correction_markers',
        'memory_confidence', 'trust_score', 'drift_score'
    ]
    
    X = split_df[feature_columns].values
    y = split_df['category'].map(CATEGORY_MAP).values
    
    return X, y

def train_logistic_regression(X_train, y_train):
    """Train Logistic Regression model (simple baseline, target: 60-70%)."""
    print("\n" + "=" * 60)
    print("Training Logistic Regression")
    print("=" * 60)
    
    model = LogisticRegression(
        max_iter=1000,
        random_state=RANDOM_SEED
    )
    
    # Stratified K-Fold cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    
    cv_results = cross_validate(
        model, X_train, y_train, cv=skf,
        scoring=['accuracy', 'precision_macro', 'recall_macro', 'f1_macro'],
        return_train_score=True
    )
    
    print(f"\n5-Fold Cross-Validation Results:")
    print(f"  Accuracy:  {cv_results['test_accuracy'].mean():.4f} ± {cv_results['test_accuracy'].std():.4f}")
    print(f"  Precision: {cv_results['test_precision_macro'].mean():.4f} ± {cv_results['test_precision_macro'].std():.4f}")
    print(f"  Recall:    {cv_results['test_recall_macro'].mean():.4f} ± {cv_results['test_recall_macro'].std():.4f}")
    print(f"  F1:        {cv_results['test_f1_macro'].mean():.4f} ± {cv_results['test_f1_macro'].std():.4f}")
    
    # Train on full training set
    model.fit(X_train, y_train)
    
    # Save model
    with open(MODEL_LR, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✓ Model saved to {MODEL_LR}")
    
    return model, cv_results

def train_random_forest(X_train, y_train, feature_names):
    """Train Random Forest model (feature importance, target: 70-75%)."""
    print("\n" + "=" * 60)
    print("Training Random Forest")
    print("=" * 60)
    
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=RANDOM_SEED,
        n_jobs=-1
    )
    
    # Stratified K-Fold cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    
    cv_results = cross_validate(
        model, X_train, y_train, cv=skf,
        scoring=['accuracy', 'precision_macro', 'recall_macro', 'f1_macro'],
        return_train_score=True
    )
    
    print(f"\n5-Fold Cross-Validation Results:")
    print(f"  Accuracy:  {cv_results['test_accuracy'].mean():.4f} ± {cv_results['test_accuracy'].std():.4f}")
    print(f"  Precision: {cv_results['test_precision_macro'].mean():.4f} ± {cv_results['test_precision_macro'].std():.4f}")
    print(f"  Recall:    {cv_results['test_recall_macro'].mean():.4f} ± {cv_results['test_recall_macro'].std():.4f}")
    print(f"  F1:        {cv_results['test_f1_macro'].mean():.4f} ± {cv_results['test_f1_macro'].std():.4f}")
    
    # Train on full training set
    model.fit(X_train, y_train)
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Most Important Features:")
    for i, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']}: {row['importance']:.4f}")
    
    # Save model
    with open(MODEL_RF, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✓ Model saved to {MODEL_RF}")
    
    return model, cv_results, feature_importance

def train_xgboost(X_train, y_train):
    """Train XGBoost model (best tabular model, target: 75-80%)."""
    print("\n" + "=" * 60)
    print("Training XGBoost")
    print("=" * 60)
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=RANDOM_SEED,
        eval_metric='mlogloss',
        tree_method='hist'
    )
    
    # Stratified K-Fold cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    
    cv_results = cross_validate(
        model, X_train, y_train, cv=skf,
        scoring=['accuracy', 'precision_macro', 'recall_macro', 'f1_macro'],
        return_train_score=True
    )
    
    print(f"\n5-Fold Cross-Validation Results:")
    print(f"  Accuracy:  {cv_results['test_accuracy'].mean():.4f} ± {cv_results['test_accuracy'].std():.4f}")
    print(f"  Precision: {cv_results['test_precision_macro'].mean():.4f} ± {cv_results['test_precision_macro'].std():.4f}")
    print(f"  Recall:    {cv_results['test_recall_macro'].mean():.4f} ± {cv_results['test_recall_macro'].std():.4f}")
    print(f"  F1:        {cv_results['test_f1_macro'].mean():.4f} ± {cv_results['test_f1_macro'].std():.4f}")
    
    # Train on full training set
    model.fit(X_train, y_train)
    
    # Save model
    with open(MODEL_XGB, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✓ Model saved to {MODEL_XGB}")
    
    return model, cv_results

def evaluate_on_test(models, X_test, y_test):
    """Evaluate all models on test set."""
    print("\n" + "=" * 60)
    print("Evaluating on Test Set")
    print("=" * 60)
    
    results = []
    
    for model_name, model in models.items():
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, average='macro', zero_division=0
        )
        
        print(f"\n{model_name}:")
        print(f"  Accuracy:  {accuracy:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1:        {f1:.4f}")
        
        # Per-category metrics
        precision_per_cat, recall_per_cat, f1_per_cat, support_per_cat = precision_recall_fscore_support(
            y_test, y_pred, labels=[0, 1, 2, 3], zero_division=0
        )
        
        print("  Per-category F1:")
        for i, cat_name in enumerate(CATEGORY_NAMES):
            print(f"    {cat_name}: {f1_per_cat[i]:.4f}")
        
        results.append({
            'Model': model_name,
            'Accuracy': accuracy,
            'Precision': precision,
            'Recall': recall,
            'F1': f1,
            'REFINEMENT_F1': f1_per_cat[0],
            'REVISION_F1': f1_per_cat[1],
            'TEMPORAL_F1': f1_per_cat[2],
            'CONFLICT_F1': f1_per_cat[3]
        })
    
    return pd.DataFrame(results)

def create_comparison_visualization(results_df):
    """Create comparison visualization of models."""
    print("\n" + "=" * 60)
    print("Creating Comparison Visualization")
    print("=" * 60)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Overall metrics
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1']
    x = np.arange(len(results_df))
    width = 0.2
    
    for i, metric in enumerate(metrics):
        axes[0].bar(x + i*width, results_df[metric], width, label=metric)
    
    axes[0].set_xlabel('Model')
    axes[0].set_ylabel('Score')
    axes[0].set_title('Baseline Model Comparison - Overall Metrics')
    axes[0].set_xticks(x + width * 1.5)
    axes[0].set_xticklabels(results_df['Model'])
    axes[0].legend()
    axes[0].grid(axis='y', alpha=0.3)
    axes[0].set_ylim([0, 1])
    
    # Per-category F1
    categories = ['REFINEMENT_F1', 'REVISION_F1', 'TEMPORAL_F1', 'CONFLICT_F1']
    category_labels = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']
    
    for i, model_row in results_df.iterrows():
        values = [model_row[cat] for cat in categories]
        axes[1].plot(category_labels, values, marker='o', label=model_row['Model'])
    
    axes[1].set_xlabel('Category')
    axes[1].set_ylabel('F1 Score')
    axes[1].set_title('Baseline Model Comparison - Per-Category F1')
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    axes[1].set_ylim([0, 1])
    
    plt.tight_layout()
    plt.savefig(COMPARISON_PNG, dpi=150, bbox_inches='tight')
    print(f"✓ Visualization saved to {COMPARISON_PNG}")
    plt.close()

def main():
    """Main baseline training pipeline."""
    print("=" * 60)
    print("PHASE 2, TASK 2: BASELINE MODEL TRAINING")
    print("=" * 60)
    print()
    
    # Load data
    X_full, y_full, feature_names, df_full = load_and_prepare_data()
    
    # Load train/test splits
    print("\nLoading train/val/test splits...")
    X_train, y_train = load_split_data(TRAIN_DATA, df_full)
    X_val, y_val = load_split_data(VAL_DATA, df_full)
    X_test, y_test = load_split_data(TEST_DATA, df_full)
    
    print(f"  Train: {len(X_train)} examples")
    print(f"  Val:   {len(X_val)} examples")
    print(f"  Test:  {len(X_test)} examples")
    
    # Train models
    lr_model, lr_cv = train_logistic_regression(X_train, y_train)
    rf_model, rf_cv, rf_importance = train_random_forest(X_train, y_train, feature_names)
    xgb_model, xgb_cv = train_xgboost(X_train, y_train)
    
    # Evaluate on test set
    models = {
        'Logistic Regression': lr_model,
        'Random Forest': rf_model,
        'XGBoost': xgb_model
    }
    
    results_df = evaluate_on_test(models, X_test, y_test)
    
    # Save results
    results_df.to_csv(COMPARISON_CSV, index=False)
    print(f"\n✓ Results saved to {COMPARISON_CSV}")
    
    # Create visualization
    create_comparison_visualization(results_df)
    
    print("\n" + "=" * 60)
    print("BASELINE MODEL TRAINING COMPLETE!")
    print("=" * 60)
    print(f"\nOutputs:")
    print(f"  Models:")
    print(f"    - {MODEL_LR}")
    print(f"    - {MODEL_RF}")
    print(f"    - {MODEL_XGB}")
    print(f"  Results:")
    print(f"    - {COMPARISON_CSV}")
    print(f"    - {COMPARISON_PNG}")
    print("\nNext: Run phase2_finetune_bert.py to train BERT classifier\n")

if __name__ == "__main__":
    main()
