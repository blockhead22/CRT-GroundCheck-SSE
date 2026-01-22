#!/usr/bin/env python3
"""
Phase 2, Task 1: Feature Extraction Script

Extracts features from synthetic belief updates for classifier training.
Outputs features.csv and train/val/test splits.

Week 3, Days 1-2
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "synthetic_belief_updates.json"
OUTPUT_FEATURES = DATA_DIR / "features.csv"
OUTPUT_TRAIN = DATA_DIR / "train.json"
OUTPUT_VAL = DATA_DIR / "val.json"
OUTPUT_TEST = DATA_DIR / "test.json"

# Random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Initialize TF-IDF vectorizer for semantic similarity
print("Initializing TF-IDF vectorizer for semantic features...")
vectorizer = TfidfVectorizer(max_features=100)
print("✓ Vectorizer initialized\n")

def compute_semantic_similarity(text1, text2):
    """Compute cosine similarity between two texts using TF-IDF vectors."""
    try:
        vectors = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return float(similarity)
    except:
        # Return neutral similarity if vectorization fails
        return 0.5

def extract_temporal_features(example):
    """Extract temporal-related features."""
    time_delta_days = example.get('time_delta_days', 0)
    
    # Recency score (exponential decay)
    recency_score = np.exp(-time_delta_days / 365.0)
    
    # Update frequency indicator (proxy based on time delta)
    if time_delta_days < 7:
        update_frequency = 3  # High frequency
    elif time_delta_days < 30:
        update_frequency = 2  # Medium frequency
    else:
        update_frequency = 1  # Low frequency
    
    return {
        'time_delta_days': time_delta_days,
        'recency_score': recency_score,
        'update_frequency': update_frequency
    }

def extract_linguistic_patterns(old_value, new_value):
    """Extract linguistic pattern features."""
    # Combine for query simulation
    query = new_value  # New value acts as the query
    
    # Word count
    query_word_count = len(query.split())
    old_word_count = len(old_value.split())
    new_word_count = len(new_value.split())
    
    # Negation detection
    negation_words = ['not', 'never', 'no longer', "n't", 'don\'t', 'didn\'t', 'won\'t', 'can\'t']
    negation_in_new = int(any(neg in new_value.lower() for neg in negation_words))
    negation_in_old = int(any(neg in old_value.lower() for neg in negation_words))
    
    # Temporal keywords
    temporal_keywords = ['now', 'previously', 'used to', 'currently', 'was', 'were', 'am', 'is', 'are']
    temporal_in_new = int(any(kw in new_value.lower() for kw in temporal_keywords))
    temporal_in_old = int(any(kw in old_value.lower() for kw in temporal_keywords))
    
    # Correction markers
    correction_markers = ['actually', 'i meant', 'correction', 'sorry', 'mistake', 'wrong']
    correction_in_new = int(any(marker in new_value.lower() for marker in correction_markers))
    
    return {
        'query_word_count': query_word_count,
        'old_word_count': old_word_count,
        'new_word_count': new_word_count,
        'word_count_delta': new_word_count - old_word_count,
        'negation_in_new': negation_in_new,
        'negation_in_old': negation_in_old,
        'negation_delta': negation_in_new - negation_in_old,
        'temporal_in_new': temporal_in_new,
        'temporal_in_old': temporal_in_old,
        'correction_markers': correction_in_new
    }

def extract_confidence_features(example):
    """Extract confidence and trust-related features (simulated for synthetic data)."""
    # For synthetic data, we simulate these based on category
    category = example['category']
    
    # Simulate confidence scores based on category patterns
    if category == 'REFINEMENT':
        confidence = np.random.uniform(0.8, 0.95)
        trust_score = np.random.uniform(0.85, 0.98)
        drift_score = np.random.uniform(0.05, 0.20)
    elif category == 'REVISION':
        confidence = np.random.uniform(0.7, 0.85)
        trust_score = np.random.uniform(0.75, 0.90)
        drift_score = np.random.uniform(0.40, 0.70)
    elif category == 'TEMPORAL':
        confidence = np.random.uniform(0.75, 0.90)
        trust_score = np.random.uniform(0.80, 0.95)
        drift_score = np.random.uniform(0.30, 0.50)
    else:  # CONFLICT
        confidence = np.random.uniform(0.50, 0.70)
        trust_score = np.random.uniform(0.55, 0.75)
        drift_score = np.random.uniform(0.70, 0.95)
    
    return {
        'memory_confidence': confidence,
        'trust_score': trust_score,
        'drift_score': drift_score
    }

def extract_features_from_example(example):
    """Extract all features from a single example."""
    old_value = example['old_value']
    new_value = example['new_value']
    
    # Semantic similarity features
    query_to_old_similarity = compute_semantic_similarity(new_value, old_value)
    cross_memory_similarity = compute_semantic_similarity(old_value, new_value)
    
    # Temporal features
    temporal_features = extract_temporal_features(example)
    
    # Linguistic patterns
    linguistic_features = extract_linguistic_patterns(old_value, new_value)
    
    # Confidence features
    confidence_features = extract_confidence_features(example)
    
    # Combine all features
    features = {
        'id': example['id'],
        'category': example['category'],
        'query_to_old_similarity': query_to_old_similarity,
        'cross_memory_similarity': cross_memory_similarity,
        **temporal_features,
        **linguistic_features,
        **confidence_features,
        'slot': example['slot'],
        'old_value': old_value,
        'new_value': new_value
    }
    
    return features

def create_train_val_test_splits(data, train_size=0.7, val_size=0.15, test_size=0.15):
    """Create stratified train/val/test splits."""
    # First split: train vs (val + test)
    train_data, temp_data = train_test_split(
        data, 
        train_size=train_size, 
        stratify=[d['category'] for d in data],
        random_state=RANDOM_SEED
    )
    
    # Second split: val vs test
    val_ratio = val_size / (val_size + test_size)
    val_data, test_data = train_test_split(
        temp_data,
        train_size=val_ratio,
        stratify=[d['category'] for d in temp_data],
        random_state=RANDOM_SEED
    )
    
    return train_data, val_data, test_data

def main():
    """Main feature extraction pipeline."""
    print("=" * 60)
    print("PHASE 2, TASK 1: FEATURE EXTRACTION")
    print("=" * 60)
    print()
    
    # Load synthetic belief updates
    print(f"Loading data from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r') as f:
        examples = json.load(f)
    print(f"✓ Loaded {len(examples)} examples")
    
    # Category distribution
    categories = {}
    for ex in examples:
        cat = ex['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategory distribution:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    # Extract features
    print("\nExtracting features...")
    features_list = []
    for i, example in enumerate(examples):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(examples)} examples...")
        
        features = extract_features_from_example(example)
        features_list.append(features)
    
    print(f"✓ Extracted features from {len(features_list)} examples")
    
    # Convert to DataFrame
    df = pd.DataFrame(features_list)
    
    # Save features.csv
    print(f"\nSaving features to {OUTPUT_FEATURES}...")
    df.to_csv(OUTPUT_FEATURES, index=False)
    print(f"✓ Saved {len(df)} rows, {len(df.columns)} columns")
    
    # Create train/val/test splits
    print("\nCreating train/val/test splits (70/15/15)...")
    train_data, val_data, test_data = create_train_val_test_splits(examples)
    
    print(f"  Train: {len(train_data)} examples")
    print(f"  Val:   {len(val_data)} examples")
    print(f"  Test:  {len(test_data)} examples")
    
    # Save splits
    with open(OUTPUT_TRAIN, 'w') as f:
        json.dump(train_data, f, indent=2)
    print(f"✓ Saved train split to {OUTPUT_TRAIN}")
    
    with open(OUTPUT_VAL, 'w') as f:
        json.dump(val_data, f, indent=2)
    print(f"✓ Saved val split to {OUTPUT_VAL}")
    
    with open(OUTPUT_TEST, 'w') as f:
        json.dump(test_data, f, indent=2)
    print(f"✓ Saved test split to {OUTPUT_TEST}")
    
    # Verify splits are stratified
    print("\nSplit category distributions:")
    for split_name, split_data in [('Train', train_data), ('Val', val_data), ('Test', test_data)]:
        split_cats = {}
        for ex in split_data:
            cat = ex['category']
            split_cats[cat] = split_cats.get(cat, 0) + 1
        
        print(f"\n  {split_name}:")
        for cat in sorted(categories.keys()):
            count = split_cats.get(cat, 0)
            percentage = (count / len(split_data)) * 100
            print(f"    {cat}: {count} ({percentage:.1f}%)")
    
    print("\n" + "=" * 60)
    print("FEATURE EXTRACTION COMPLETE!")
    print("=" * 60)
    print(f"\nOutputs:")
    print(f"  - {OUTPUT_FEATURES}")
    print(f"  - {OUTPUT_TRAIN}")
    print(f"  - {OUTPUT_VAL}")
    print(f"  - {OUTPUT_TEST}")
    print("\nNext: Run phase2_train_baseline.py to train baseline models\n")

if __name__ == "__main__":
    main()
