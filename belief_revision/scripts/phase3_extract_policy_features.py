#!/usr/bin/env python3
"""
Phase 3, Task 3: Policy Feature Extraction

This script extracts features from policy-labeled data for model training.
It creates both Phase 2 features (category, time_delta, etc.) and new 
policy-specific features (confidence_delta, slot_type, linguistic signals).

Outputs:
- policy_features.csv: Feature matrix
- policy_train.json, policy_val.json, policy_test.json: Train/val/test splits (70/15/15)
"""

import json
import random
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from collections import Counter

# Directories
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "policy_labeled_examples.json"

# Outputs
OUTPUT_CSV = DATA_DIR / "policy_features.csv"
OUTPUT_TRAIN = DATA_DIR / "policy_train.json"
OUTPUT_VAL = DATA_DIR / "policy_val.json"
OUTPUT_TEST = DATA_DIR / "policy_test.json"

# Constants
CORRECTION_WORDS = ['actually', 'I meant', 'correction', 'wrong', 'mistake', 'no,']
TEMPORAL_WORDS = ['now', 'currently', 'used to', 'previously', 'anymore', 'before']


def calculate_semantic_similarity(old_value, new_value):
    """
    Simplified semantic similarity based on word overlap.
    In production, you'd use sentence-transformers.
    """
    old_words = set(old_value.lower().split())
    new_words = set(new_value.lower().split())
    
    if not old_words or not new_words:
        return 0.0
    
    intersection = old_words & new_words
    union = old_words | new_words
    
    return len(intersection) / len(union) if union else 0.0


def extract_features(example):
    """
    Extract all features for policy prediction.
    
    Returns:
        dict: Feature dictionary
    """
    features = {}
    
    # ===== Phase 2 Features (reuse) =====
    
    # Category (one-hot encoded later)
    features['category'] = example['category']
    
    # Time delta
    features['time_delta_days'] = example.get('time_delta_days', 0)
    
    # Semantic similarity
    features['semantic_similarity'] = calculate_semantic_similarity(
        example['old_value'], 
        example['new_value']
    )
    
    # Confidence scores
    features['confidence_old'] = example.get('confidence_old', 0.85)
    features['confidence_new'] = example.get('confidence_new', 0.85)
    
    # Trust and drift scores (simulated for now)
    features['trust_score'] = random.uniform(0.7, 1.0)
    features['drift_score'] = abs(features['confidence_new'] - features['confidence_old'])
    
    # ===== NEW Policy-Specific Features =====
    
    # Confidence delta
    features['confidence_delta'] = features['confidence_new'] - features['confidence_old']
    
    # Slot type
    features['slot'] = example.get('slot', 'unknown')
    features['slot_type'] = example.get('slot_type', 'other')
    
    # Boolean slot flags
    features['is_factual_slot'] = 1 if features['slot_type'] == 'factual' else 0
    features['is_preference_slot'] = 1 if features['slot_type'] == 'preference' else 0
    
    # Linguistic features
    features['has_correction_words'] = 1 if example.get('has_correction_words', False) else 0
    features['has_temporal_words'] = 1 if example.get('has_temporal_words', False) else 0
    
    # User signal strength
    features['user_signal_strength'] = 'explicit' if features['has_correction_words'] else 'implicit'
    
    # Time category
    time_delta = features['time_delta_days']
    if time_delta < 1:
        features['time_category'] = 'immediate'
    elif time_delta <= 7:
        features['time_category'] = 'recent'
    else:
        features['time_category'] = 'old'
    
    # Target label
    features['policy'] = example['policy']
    
    # Keep ID for tracking
    features['id'] = example.get('id', 'unknown')
    
    return features


def create_feature_dataframe(examples):
    """
    Create feature matrix as pandas DataFrame.
    
    Args:
        examples: List of examples with features extracted
    
    Returns:
        pd.DataFrame: Feature matrix
    """
    # Extract features for all examples
    feature_list = [extract_features(ex) for ex in examples]
    
    # Convert to DataFrame
    df = pd.DataFrame(feature_list)
    
    # One-hot encode categorical features
    categorical_cols = ['category', 'slot_type', 'user_signal_strength', 'time_category']
    df_encoded = pd.get_dummies(df, columns=categorical_cols, prefix=categorical_cols)
    
    return df_encoded


def split_data(examples, train_size=0.7, val_size=0.15, test_size=0.15, random_state=42):
    """
    Split data into train/val/test sets with stratification.
    
    Args:
        examples: List of examples
        train_size, val_size, test_size: Split ratios
        random_state: Random seed for reproducibility
    
    Returns:
        tuple: (train_examples, val_examples, test_examples)
    """
    # Get labels for stratification
    labels = [ex['policy'] for ex in examples]
    
    # First split: train vs (val + test)
    train_examples, temp_examples = train_test_split(
        examples,
        test_size=(val_size + test_size),
        stratify=labels,
        random_state=random_state
    )
    
    # Second split: val vs test
    temp_labels = [ex['policy'] for ex in temp_examples]
    val_examples, test_examples = train_test_split(
        temp_examples,
        test_size=(test_size / (val_size + test_size)),
        stratify=temp_labels,
        random_state=random_state
    )
    
    return train_examples, val_examples, test_examples


def print_split_summary(train, val, test):
    """Print summary statistics for each split."""
    print("\n" + "="*60)
    print("SPLIT SUMMARY")
    print("="*60)
    
    for split_name, split_data in [('Train', train), ('Val', val), ('Test', test)]:
        policy_dist = Counter(ex['policy'] for ex in split_data)
        print(f"\n{split_name} set ({len(split_data)} examples):")
        for policy in ['OVERRIDE', 'PRESERVE', 'ASK_USER']:
            count = policy_dist[policy]
            pct = (count / len(split_data)) * 100 if split_data else 0
            print(f"  {policy:12s}: {count:3d} ({pct:5.1f}%)")


def main():
    """Main execution function."""
    print("Phase 3, Task 3: Policy Feature Extraction")
    print("-" * 60)
    
    # Load policy-labeled data
    print(f"\n1. Loading policy-labeled data from: {INPUT_FILE}")
    with open(INPUT_FILE, 'r') as f:
        examples = json.load(f)
    print(f"✓ Loaded {len(examples)} examples")
    
    # Set random seed
    random.seed(42)
    
    # Extract features
    print(f"\n2. Extracting features...")
    print("   • Phase 2 features: category, time_delta, semantic_similarity, confidence, etc.")
    print("   • New features: confidence_delta, slot_type, linguistic signals, etc.")
    
    df = create_feature_dataframe(examples)
    print(f"✓ Extracted {len(df.columns)} features")
    
    # Display sample features
    print(f"\nFeature columns ({len(df.columns)} total):")
    for i, col in enumerate(df.columns):
        if i < 15:
            print(f"  • {col}")
    if len(df.columns) > 15:
        print(f"  ... and {len(df.columns) - 15} more")
    
    # Save feature matrix
    print(f"\n3. Saving feature matrix to CSV...")
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✓ Saved to: {OUTPUT_CSV}")
    
    # Split data
    print(f"\n4. Splitting data (70% train, 15% val, 15% test)...")
    train_examples, val_examples, test_examples = split_data(examples)
    
    print_split_summary(train_examples, val_examples, test_examples)
    
    # Save splits
    print(f"\n5. Saving train/val/test splits...")
    
    with open(OUTPUT_TRAIN, 'w') as f:
        json.dump(train_examples, f, indent=2)
    print(f"✓ Train set saved: {OUTPUT_TRAIN} ({len(train_examples)} examples)")
    
    with open(OUTPUT_VAL, 'w') as f:
        json.dump(val_examples, f, indent=2)
    print(f"✓ Val set saved: {OUTPUT_VAL} ({len(val_examples)} examples)")
    
    with open(OUTPUT_TEST, 'w') as f:
        json.dump(test_examples, f, indent=2)
    print(f"✓ Test set saved: {OUTPUT_TEST} ({len(test_examples)} examples)")
    
    # Final summary
    print("\n" + "="*60)
    print("FEATURE EXTRACTION COMPLETE")
    print("="*60)
    print(f"Total examples: {len(examples)}")
    print(f"Total features: {len(df.columns)}")
    print(f"\nTrain: {len(train_examples)} examples")
    print(f"Val:   {len(val_examples)} examples")
    print(f"Test:  {len(test_examples)} examples")
    
    print("\nOutputs:")
    print(f"  • {OUTPUT_CSV}")
    print(f"  • {OUTPUT_TRAIN}")
    print(f"  • {OUTPUT_VAL}")
    print(f"  • {OUTPUT_TEST}")
    
    print("\n✓ Feature extraction complete!")
    print("\nNext step: Run phase3_train_policy.py")


if __name__ == "__main__":
    main()
