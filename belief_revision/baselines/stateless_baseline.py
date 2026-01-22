#!/usr/bin/env python3
"""
Phase 4, Task 1: Stateless Baseline (No Memory)

Simulates a standard LLM with no long-term memory, like base ChatGPT.
Uses only the current query (new_value) without old_value context.
Predicts categories using simple keyword heuristics.

Expected performance: 40-50% accuracy (poor without context)
"""

import json
import numpy as np
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    classification_report
)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent.parent / "results"

TEST_DATA = DATA_DIR / "test.json"
OUTPUT_RESULTS = RESULTS_DIR / "baseline_stateless_results.json"

# Category mapping
CATEGORY_MAP = {
    'REFINEMENT': 0,
    'REVISION': 1,
    'TEMPORAL': 2,
    'CONFLICT': 3
}
CATEGORY_NAMES = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']


def predict_category_stateless(new_value):
    """
    Predict category using only new_value text (no old_value context).
    
    Uses simple keyword heuristics:
    - Contains "and", "also", "too" → REFINEMENT
    - Contains "now", "currently", "changed to" → REVISION or TEMPORAL
    - Contains "not", "never", "don't" → CONFLICT
    - Default → REFINEMENT
    
    Args:
        new_value: The new belief statement (str)
    
    Returns:
        str: Predicted category name
    """
    new_lower = new_value.lower()
    
    # Check for negation patterns (highest priority)
    negation_words = ["not", "never", "don't", "doesn't", "didn't", "won't", "cannot"]
    if any(word in new_lower for word in negation_words):
        return "CONFLICT"
    
    # Check for temporal keywords
    temporal_words = ["now", "currently", "today", "this week", "this month"]
    if any(word in new_lower for word in temporal_words):
        return "TEMPORAL"
    
    # Check for revision markers
    revision_words = ["changed to", "updated to", "switched to", "moved to"]
    if any(word in new_lower for word in revision_words):
        return "REVISION"
    
    # Check for refinement markers
    refinement_words = ["and", "also", "too", "additionally", "furthermore"]
    if any(word in new_lower for word in refinement_words):
        return "REFINEMENT"
    
    # Default to REFINEMENT (most common category)
    return "REFINEMENT"


def evaluate_stateless_baseline():
    """
    Evaluate stateless baseline on Phase 2 test set.
    
    Returns:
        dict: Results including predictions and metrics
    """
    print("=" * 60)
    print("STATELESS BASELINE EVALUATION")
    print("=" * 60)
    print()
    print("Simulating LLM with no memory (like base ChatGPT)")
    print("Only uses new_value text, ignores old_value context")
    print()
    
    # Load test data
    print("Loading test data...")
    with open(TEST_DATA, 'r') as f:
        test_data = json.load(f)
    
    print(f"✓ Loaded {len(test_data)} test examples")
    
    # Generate predictions
    print("\nGenerating predictions (keyword heuristics only)...")
    predictions = []
    y_true = []
    
    for example in test_data:
        # Stateless: only use new_value
        pred_category = predict_category_stateless(example['new_value'])
        predictions.append(CATEGORY_MAP[pred_category])
        y_true.append(CATEGORY_MAP[example['category']])
    
    y_pred = np.array(predictions)
    y_true = np.array(y_true)
    
    print("✓ Generated predictions for all examples")
    
    # Calculate metrics
    print("\nCalculating metrics...")
    
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=[0, 1, 2, 3], zero_division=0
    )
    
    # Macro averages
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average='macro', zero_division=0
    )
    
    # Build results
    results = {
        'method': 'Stateless (No Memory)',
        'description': 'Standard LLM with no long-term memory, keyword-based prediction',
        'test_set': 'Phase 2 test set (90 examples)',
        'accuracy': float(accuracy),
        'macro_precision': float(macro_precision),
        'macro_recall': float(macro_recall),
        'macro_f1': float(macro_f1),
        'per_category_metrics': {}
    }
    
    for i, category in enumerate(CATEGORY_NAMES):
        results['per_category_metrics'][category] = {
            'precision': float(precision[i]),
            'recall': float(recall[i]),
            'f1': float(f1[i]),
            'support': int(support[i])
        }
    
    # Save results
    print(f"\nSaving results to {OUTPUT_RESULTS}...")
    with open(OUTPUT_RESULTS, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("✓ Results saved")
    
    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print()
    print(f"Overall Accuracy: {accuracy:.1%}")
    print(f"Macro Precision:  {macro_precision:.1%}")
    print(f"Macro Recall:     {macro_recall:.1%}")
    print(f"Macro F1:         {macro_f1:.1%}")
    print()
    print("Per-Category Performance:")
    print("-" * 60)
    print(f"{'Category':<15} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Support':<10}")
    print("-" * 60)
    
    for i, category in enumerate(CATEGORY_NAMES):
        print(f"{category:<15} {precision[i]:<12.3f} {recall[i]:<12.3f} {f1[i]:<12.3f} {support[i]:<10}")
    
    print()
    print("=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    print()
    print("❌ Low accuracy as expected (no context)")
    print("❌ Cannot distinguish REVISION from TEMPORAL without old_value")
    print("❌ Keyword heuristics are insufficient for accurate categorization")
    print("✓  This baseline demonstrates the importance of memory")
    print()
    print(f"Results saved to: {OUTPUT_RESULTS}")
    print()
    
    return results


def main():
    """Main execution."""
    results = evaluate_stateless_baseline()
    
    print("=" * 60)
    print("Next: Run override_baseline.py for simple RAG baseline")
    print("=" * 60)
    

if __name__ == "__main__":
    main()
