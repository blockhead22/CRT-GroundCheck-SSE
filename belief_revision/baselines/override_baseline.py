#!/usr/bin/env python3
"""
Phase 4, Task 2: Simple Override Baseline (Last Write Wins)

Simulates a RAG system with simple memory that always overwrites on conflict.
Has access to both old_value and new_value (unlike stateless).
Uses TF-IDF similarity for category prediction.
Always predicts OVERRIDE policy (last write wins strategy).

Expected performance: 60-70% category accuracy, 55% policy accuracy
"""

import json
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support
)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent.parent / "results"

TEST_DATA = DATA_DIR / "test.json"
POLICY_TEST_DATA = DATA_DIR / "policy_test.json"
OUTPUT_RESULTS = RESULTS_DIR / "baseline_override_results.json"

# Category mapping
CATEGORY_MAP = {
    'REFINEMENT': 0,
    'REVISION': 1,
    'TEMPORAL': 2,
    'CONFLICT': 3
}
CATEGORY_NAMES = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']

# Policy mapping
POLICY_MAP = {'OVERRIDE': 0, 'PRESERVE': 1, 'ASK_USER': 2}
POLICY_NAMES = ['OVERRIDE', 'PRESERVE', 'ASK_USER']


def compute_similarity(text1, text2):
    """
    Compute TF-IDF cosine similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
    
    Returns:
        float: Cosine similarity score [0, 1]
    """
    if not text1 or not text2:
        return 0.0
    
    vectorizer = TfidfVectorizer()
    try:
        tfidf = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return similarity
    except:
        return 0.0


def predict_category_override(old_value, new_value):
    """
    Predict category using TF-IDF similarity between old and new values.
    
    Rules:
    - If similarity > 0.8 → REFINEMENT (very similar, likely adding detail)
    - If similarity 0.3-0.8 → REVISION (moderately different)
    - If similarity < 0.3 → CONFLICT (very different)
    - If new_value contains temporal keywords → TEMPORAL (override REVISION)
    
    Args:
        old_value: Previous belief statement
        new_value: New belief statement
    
    Returns:
        str: Predicted category name
    """
    similarity = compute_similarity(old_value, new_value)
    new_lower = new_value.lower()
    
    # Check for temporal keywords (highest priority)
    temporal_words = ["now", "currently", "today", "this week", "this month", 
                      "working on", "current"]
    has_temporal = any(word in new_lower for word in temporal_words)
    
    if has_temporal and similarity < 0.8:
        return "TEMPORAL"
    
    # Similarity-based classification
    if similarity > 0.8:
        return "REFINEMENT"
    elif similarity >= 0.3:
        return "REVISION"
    else:
        return "CONFLICT"


def predict_policy_override(old_value, new_value, category):
    """
    Predict policy using "last write wins" strategy.
    
    This baseline ALWAYS predicts OVERRIDE - representing
    production RAG systems that overwrite on any update.
    
    Args:
        old_value: Previous belief statement
        new_value: New belief statement
        category: Predicted category
    
    Returns:
        str: Always 'OVERRIDE'
    """
    # Simple override baseline - always overwrite
    return "OVERRIDE"


def evaluate_override_baseline():
    """
    Evaluate override baseline on both Phase 2 and Phase 3 test sets.
    
    Returns:
        dict: Results including predictions and metrics
    """
    print("=" * 60)
    print("OVERRIDE BASELINE EVALUATION")
    print("=" * 60)
    print()
    print("Simulating simple RAG with 'last write wins' strategy")
    print("Uses TF-IDF similarity for categorization")
    print("Always predicts OVERRIDE policy")
    print()
    
    # ===== Evaluate on Phase 2 test set (categories) =====
    print("Loading Phase 2 test data (categories)...")
    with open(TEST_DATA, 'r') as f:
        test_data = json.load(f)
    
    print(f"✓ Loaded {len(test_data)} test examples")
    
    print("\nGenerating category predictions (TF-IDF similarity)...")
    cat_predictions = []
    cat_true = []
    
    for example in test_data:
        pred_category = predict_category_override(
            example['old_value'],
            example['new_value']
        )
        cat_predictions.append(CATEGORY_MAP[pred_category])
        cat_true.append(CATEGORY_MAP[example['category']])
    
    cat_pred = np.array(cat_predictions)
    cat_true = np.array(cat_true)
    
    print("✓ Generated category predictions")
    
    # Calculate category metrics
    print("\nCalculating category metrics...")
    cat_accuracy = accuracy_score(cat_true, cat_pred)
    cat_precision, cat_recall, cat_f1, cat_support = precision_recall_fscore_support(
        cat_true, cat_pred, labels=[0, 1, 2, 3], zero_division=0
    )
    cat_macro_p, cat_macro_r, cat_macro_f1, _ = precision_recall_fscore_support(
        cat_true, cat_pred, average='macro', zero_division=0
    )
    
    # ===== Evaluate on Phase 3 test set (policies) =====
    print("\nLoading Phase 3 test data (policies)...")
    with open(POLICY_TEST_DATA, 'r') as f:
        policy_test_data = json.load(f)
    
    print(f"✓ Loaded {len(policy_test_data)} test examples")
    
    print("\nGenerating policy predictions (always OVERRIDE)...")
    policy_predictions = []
    policy_true = []
    
    for example in policy_test_data:
        pred_category = predict_category_override(
            example['old_value'],
            example['new_value']
        )
        pred_policy = predict_policy_override(
            example['old_value'],
            example['new_value'],
            pred_category
        )
        policy_predictions.append(POLICY_MAP[pred_policy])
        policy_true.append(POLICY_MAP[example['policy']])
    
    policy_pred = np.array(policy_predictions)
    policy_true = np.array(policy_true)
    
    print("✓ Generated policy predictions")
    
    # Calculate policy metrics
    print("\nCalculating policy metrics...")
    policy_accuracy = accuracy_score(policy_true, policy_pred)
    policy_precision, policy_recall, policy_f1, policy_support = precision_recall_fscore_support(
        policy_true, policy_pred, labels=[0, 1, 2], zero_division=0
    )
    policy_macro_p, policy_macro_r, policy_macro_f1, _ = precision_recall_fscore_support(
        policy_true, policy_pred, average='macro', zero_division=0
    )
    
    # Build results
    results = {
        'method': 'Override (Simple RAG)',
        'description': 'Simple RAG with last-write-wins, TF-IDF similarity',
        'category_evaluation': {
            'test_set': 'Phase 2 test set (90 examples)',
            'accuracy': float(cat_accuracy),
            'macro_precision': float(cat_macro_p),
            'macro_recall': float(cat_macro_r),
            'macro_f1': float(cat_macro_f1),
            'per_category_metrics': {}
        },
        'policy_evaluation': {
            'test_set': 'Phase 3 test set (90 examples)',
            'accuracy': float(policy_accuracy),
            'macro_precision': float(policy_macro_p),
            'macro_recall': float(policy_macro_r),
            'macro_f1': float(policy_macro_f1),
            'per_policy_metrics': {}
        }
    }
    
    for i, category in enumerate(CATEGORY_NAMES):
        results['category_evaluation']['per_category_metrics'][category] = {
            'precision': float(cat_precision[i]),
            'recall': float(cat_recall[i]),
            'f1': float(cat_f1[i]),
            'support': int(cat_support[i])
        }
    
    for i, policy in enumerate(POLICY_NAMES):
        results['policy_evaluation']['per_policy_metrics'][policy] = {
            'precision': float(policy_precision[i]),
            'recall': float(policy_recall[i]),
            'f1': float(policy_f1[i]),
            'support': int(policy_support[i])
        }
    
    # Save results
    print(f"\nSaving results to {OUTPUT_RESULTS}...")
    with open(OUTPUT_RESULTS, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("✓ Results saved")
    
    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY - CATEGORY PREDICTION")
    print("=" * 60)
    print()
    print(f"Overall Accuracy: {cat_accuracy:.1%}")
    print(f"Macro Precision:  {cat_macro_p:.1%}")
    print(f"Macro Recall:     {cat_macro_r:.1%}")
    print(f"Macro F1:         {cat_macro_f1:.1%}")
    print()
    print("Per-Category Performance:")
    print("-" * 60)
    print(f"{'Category':<15} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Support':<10}")
    print("-" * 60)
    
    for i, category in enumerate(CATEGORY_NAMES):
        print(f"{category:<15} {cat_precision[i]:<12.3f} {cat_recall[i]:<12.3f} {cat_f1[i]:<12.3f} {cat_support[i]:<10}")
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY - POLICY PREDICTION")
    print("=" * 60)
    print()
    print(f"Overall Accuracy: {policy_accuracy:.1%}")
    print(f"Macro Precision:  {policy_macro_p:.1%}")
    print(f"Macro Recall:     {policy_macro_r:.1%}")
    print(f"Macro F1:         {policy_macro_f1:.1%}")
    print()
    print("Per-Policy Performance:")
    print("-" * 60)
    print(f"{'Policy':<15} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Support':<10}")
    print("-" * 60)
    
    for i, policy in enumerate(POLICY_NAMES):
        print(f"{policy:<15} {policy_precision[i]:<12.3f} {policy_recall[i]:<12.3f} {policy_f1[i]:<12.3f} {policy_support[i]:<10}")
    
    print()
    print("=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    print()
    print("✓  Better than stateless (has context from old_value)")
    print("❌ TF-IDF similarity is insufficient for accurate categorization")
    print("❌ Always OVERRIDE loses historical context")
    print("❌ Cannot handle contradictions properly (should ASK_USER)")
    print("✓  Represents most production RAG systems today")
    print()
    print(f"Results saved to: {OUTPUT_RESULTS}")
    print()
    
    return results


def main():
    """Main execution."""
    results = evaluate_override_baseline()
    
    print("=" * 60)
    print("Next: Run nli_baseline.py for NLI-based baseline")
    print("=" * 60)
    

if __name__ == "__main__":
    main()
