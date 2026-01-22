#!/usr/bin/env python3
"""
Phase 3, Task 4: Train Policy Classifier

This script trains three classifiers to predict resolution actions:
1. Logistic Regression (baseline, interpretable)
2. Random Forest (feature importance)
3. XGBoost (best performance, recommended)

Target: 85%+ test accuracy
"""

import json
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb

# Directories
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

# Input files
FEATURES_CSV = DATA_DIR / "policy_features.csv"
TRAIN_JSON = DATA_DIR / "policy_train.json"
VAL_JSON = DATA_DIR / "policy_val.json"
TEST_JSON = DATA_DIR / "policy_test.json"

# Output files
MODEL_LR = MODELS_DIR / "policy_logistic.pkl"
MODEL_RF = MODELS_DIR / "policy_random_forest.pkl"
MODEL_XGB = MODELS_DIR / "policy_xgboost.pkl"
TRAINING_REPORT = RESULTS_DIR / "policy_training_report.csv"

# Policy label encoding
POLICY_ENCODING = {'OVERRIDE': 0, 'PRESERVE': 1, 'ASK_USER': 2}
POLICY_DECODING = {0: 'OVERRIDE', 1: 'PRESERVE', 2: 'ASK_USER'}


def load_and_prepare_data():
    """
    Load feature data and prepare for training.
    
    Returns:
        tuple: (X_train, y_train, X_val, y_val, X_test, y_test, feature_names)
    """
    print("\n1. Loading feature data...")
    
    # Load full feature matrix
    df = pd.read_csv(FEATURES_CSV)
    
    # Remove duplicates (keep first occurrence)
    df = df.drop_duplicates(subset=['id'], keep='first')
    
    # Load splits to get IDs
    with open(TRAIN_JSON, 'r') as f:
        train_data = json.load(f)
    with open(VAL_JSON, 'r') as f:
        val_data = json.load(f)
    with open(TEST_JSON, 'r') as f:
        test_data = json.load(f)
    
    # Get IDs for each split
    train_ids = set(ex['id'] for ex in train_data)
    val_ids = set(ex['id'] for ex in val_data)
    test_ids = set(ex['id'] for ex in test_data)
    
    # Split dataframe
    df_train = df[df['id'].isin(train_ids)]
    df_val = df[df['id'].isin(val_ids)]
    df_test = df[df['id'].isin(test_ids)]
    
    # Separate features from labels
    exclude_cols = ['policy', 'id', 'slot']  # Non-feature columns
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    X_train = df_train[feature_cols].values
    X_val = df_val[feature_cols].values
    X_test = df_test[feature_cols].values
    
    # Encode labels
    y_train = df_train['policy'].map(POLICY_ENCODING).values
    y_val = df_val['policy'].map(POLICY_ENCODING).values
    y_test = df_test['policy'].map(POLICY_ENCODING).values
    
    print(f"✓ Train: {X_train.shape[0]} examples, {X_train.shape[1]} features")
    print(f"✓ Val:   {X_val.shape[0]} examples")
    print(f"✓ Test:  {X_test.shape[0]} examples")
    
    return X_train, y_train, X_val, y_val, X_test, y_test, feature_cols


def train_logistic_regression(X_train, y_train, X_val, y_val, X_test, y_test):
    """
    Train Logistic Regression classifier.
    
    Returns:
        tuple: (model, train_acc, val_acc, test_acc, cv_mean, cv_std)
    """
    print("\n2. Training Logistic Regression...")
    
    model = LogisticRegression(
        max_iter=1000,
        random_state=42
    )
    
    # Train
    model.fit(X_train, y_train)
    
    # Evaluate
    train_acc = accuracy_score(y_train, model.predict(X_train))
    val_acc = accuracy_score(y_val, model.predict(X_val))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy')
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()
    
    print(f"✓ Train Accuracy: {train_acc:.3f}")
    print(f"✓ Val Accuracy:   {val_acc:.3f}")
    print(f"✓ Test Accuracy:  {test_acc:.3f}")
    print(f"✓ CV Mean ± Std:  {cv_mean:.3f} ± {cv_std:.3f}")
    
    return model, train_acc, val_acc, test_acc, cv_mean, cv_std


def train_random_forest(X_train, y_train, X_val, y_val, X_test, y_test):
    """
    Train Random Forest classifier.
    
    Returns:
        tuple: (model, train_acc, val_acc, test_acc, cv_mean, cv_std)
    """
    print("\n3. Training Random Forest...")
    
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    
    # Train
    model.fit(X_train, y_train)
    
    # Evaluate
    train_acc = accuracy_score(y_train, model.predict(X_train))
    val_acc = accuracy_score(y_val, model.predict(X_val))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy')
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()
    
    print(f"✓ Train Accuracy: {train_acc:.3f}")
    print(f"✓ Val Accuracy:   {val_acc:.3f}")
    print(f"✓ Test Accuracy:  {test_acc:.3f}")
    print(f"✓ CV Mean ± Std:  {cv_mean:.3f} ± {cv_std:.3f}")
    
    return model, train_acc, val_acc, test_acc, cv_mean, cv_std


def train_xgboost(X_train, y_train, X_val, y_val, X_test, y_test):
    """
    Train XGBoost classifier.
    
    Returns:
        tuple: (model, train_acc, val_acc, test_acc, cv_mean, cv_std)
    """
    print("\n4. Training XGBoost...")
    
    model = xgb.XGBClassifier(
        objective='multi:softmax',
        num_class=3,
        max_depth=5,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42,
        eval_metric='mlogloss'
    )
    
    # Train
    model.fit(X_train, y_train)
    
    # Evaluate
    train_acc = accuracy_score(y_train, model.predict(X_train))
    val_acc = accuracy_score(y_val, model.predict(X_val))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy')
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()
    
    print(f"✓ Train Accuracy: {train_acc:.3f}")
    print(f"✓ Val Accuracy:   {val_acc:.3f}")
    print(f"✓ Test Accuracy:  {test_acc:.3f}")
    print(f"✓ CV Mean ± Std:  {cv_mean:.3f} ± {cv_std:.3f}")
    
    return model, train_acc, val_acc, test_acc, cv_mean, cv_std


def save_models(lr_model, rf_model, xgb_model):
    """Save trained models to disk."""
    print("\n5. Saving trained models...")
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(lr_model, MODEL_LR)
    print(f"✓ Logistic Regression: {MODEL_LR}")
    
    joblib.dump(rf_model, MODEL_RF)
    print(f"✓ Random Forest: {MODEL_RF}")
    
    joblib.dump(xgb_model, MODEL_XGB)
    print(f"✓ XGBoost: {MODEL_XGB}")


def save_training_report(results):
    """
    Save training report as CSV.
    
    Args:
        results: Dict with model results
    """
    print("\n6. Saving training report...")
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame([
        {
            'Model': 'Logistic Regression',
            'Train_Acc': results['lr']['train_acc'],
            'Val_Acc': results['lr']['val_acc'],
            'Test_Acc': results['lr']['test_acc'],
            'Cross_Val_Mean': results['lr']['cv_mean'],
            'Cross_Val_Std': results['lr']['cv_std']
        },
        {
            'Model': 'Random Forest',
            'Train_Acc': results['rf']['train_acc'],
            'Val_Acc': results['rf']['val_acc'],
            'Test_Acc': results['rf']['test_acc'],
            'Cross_Val_Mean': results['rf']['cv_mean'],
            'Cross_Val_Std': results['rf']['cv_std']
        },
        {
            'Model': 'XGBoost',
            'Train_Acc': results['xgb']['train_acc'],
            'Val_Acc': results['xgb']['val_acc'],
            'Test_Acc': results['xgb']['test_acc'],
            'Cross_Val_Mean': results['xgb']['cv_mean'],
            'Cross_Val_Std': results['xgb']['cv_std']
        }
    ])
    
    df.to_csv(TRAINING_REPORT, index=False)
    print(f"✓ Training report: {TRAINING_REPORT}")


def print_summary(results):
    """Print training summary."""
    print("\n" + "="*70)
    print("TRAINING SUMMARY")
    print("="*70)
    
    print("\n{:20s} {:>10s} {:>10s} {:>10s} {:>15s}".format(
        "Model", "Train", "Val", "Test", "CV (Mean±Std)"
    ))
    print("-" * 70)
    
    for model_name, key in [
        ('Logistic Regression', 'lr'),
        ('Random Forest', 'rf'),
        ('XGBoost', 'xgb')
    ]:
        r = results[key]
        print("{:20s} {:>10.3f} {:>10.3f} {:>10.3f} {:>15s}".format(
            model_name,
            r['train_acc'],
            r['val_acc'],
            r['test_acc'],
            f"{r['cv_mean']:.3f}±{r['cv_std']:.3f}"
        ))
    
    # Check if target achieved
    print("\n" + "="*70)
    best_model = max(results.items(), key=lambda x: x[1]['test_acc'])
    best_name = best_model[0].upper()
    best_acc = best_model[1]['test_acc']
    
    print(f"Best Model: {best_name} with {best_acc:.1%} test accuracy")
    
    if best_acc >= 0.85:
        print("✓ TARGET ACHIEVED: ≥85% test accuracy")
    else:
        print(f"⚠ Target not met: {best_acc:.1%} < 85%")
        print("  Consider: More features, hyperparameter tuning, or more data")


def main():
    """Main execution function."""
    print("Phase 3, Task 4: Train Policy Classifier")
    print("-" * 60)
    
    # Load data
    X_train, y_train, X_val, y_val, X_test, y_test, feature_cols = load_and_prepare_data()
    
    # Train models
    lr_model, lr_train, lr_val, lr_test, lr_cv_mean, lr_cv_std = train_logistic_regression(
        X_train, y_train, X_val, y_val, X_test, y_test
    )
    
    rf_model, rf_train, rf_val, rf_test, rf_cv_mean, rf_cv_std = train_random_forest(
        X_train, y_train, X_val, y_val, X_test, y_test
    )
    
    xgb_model, xgb_train, xgb_val, xgb_test, xgb_cv_mean, xgb_cv_std = train_xgboost(
        X_train, y_train, X_val, y_val, X_test, y_test
    )
    
    # Save models
    save_models(lr_model, rf_model, xgb_model)
    
    # Collect results
    results = {
        'lr': {
            'train_acc': lr_train, 'val_acc': lr_val, 'test_acc': lr_test,
            'cv_mean': lr_cv_mean, 'cv_std': lr_cv_std
        },
        'rf': {
            'train_acc': rf_train, 'val_acc': rf_val, 'test_acc': rf_test,
            'cv_mean': rf_cv_mean, 'cv_std': rf_cv_std
        },
        'xgb': {
            'train_acc': xgb_train, 'val_acc': xgb_val, 'test_acc': xgb_test,
            'cv_mean': xgb_cv_mean, 'cv_std': xgb_cv_std
        }
    }
    
    # Save report
    save_training_report(results)
    
    # Print summary
    print_summary(results)
    
    print("\n✓ Policy classifier training complete!")
    print("\nNext step: Run phase3_evaluate_policy.py")


if __name__ == "__main__":
    main()
