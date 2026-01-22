#!/usr/bin/env python3
"""
Phase 3, Task 2: Generate Policy-Labeled Data

This script loads Phase 2 synthetic data and adds policy labels based on:
1. Base category (REFINEMENT → PRESERVE, REVISION → OVERRIDE, etc.)
2. Context overrides (correction words, confidence, time delta, slot type)

Goal: Create 600 labeled examples with balanced distribution:
- OVERRIDE: ~40% (240 examples)
- PRESERVE: ~35% (210 examples)
- ASK_USER: ~25% (150 examples)
"""

import json
import random
from pathlib import Path
from collections import Counter

# Directories
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "synthetic_belief_updates.json"
OUTPUT_FILE = DATA_DIR / "policy_labeled_examples.json"

# Default policies from Task 1
DEFAULT_POLICIES = {
    'REFINEMENT': 'PRESERVE',
    'REVISION': 'OVERRIDE',
    'TEMPORAL': 'OVERRIDE',
    'CONFLICT': 'ASK_USER'
}

# Slot type classifications
FACTUAL_SLOTS = {'employer', 'location', 'age', 'education', 'job_title'}
PREFERENCE_SLOTS = {'favorite_food', 'interests', 'hobby', 'preference'}

# Correction keywords
CORRECTION_WORDS = ['actually', 'I meant', 'correction', 'wrong', 'mistake', 'no,']

# Temporal keywords
TEMPORAL_WORDS = ['now', 'currently', 'used to', 'previously', 'anymore', 'before']


def determine_slot_type(slot):
    """Determine if slot is factual, preference, or other."""
    if slot in FACTUAL_SLOTS:
        return 'factual'
    elif slot in PREFERENCE_SLOTS:
        return 'preference'
    else:
        return 'other'


def has_keywords(text, keywords):
    """Check if text contains any of the keywords."""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def add_policy_label(example, target_distribution=None):
    """
    Add policy label to an example based on category and context.
    
    Args:
        example: Dict with category, slot, time_delta_days, context, etc.
        target_distribution: Optional dict to help balance distribution
    
    Returns:
        Updated example with 'policy' field
    """
    # Start with default policy based on category
    policy = DEFAULT_POLICIES.get(example['category'], 'ASK_USER')
    
    # Context-based overrides
    context = example.get('context', '')
    slot = example.get('slot', '')
    time_delta = example.get('time_delta_days', 0)
    
    # Add confidence scores if not present (simulate)
    if 'confidence_old' not in example:
        example['confidence_old'] = random.uniform(0.7, 0.95)
    if 'confidence_new' not in example:
        example['confidence_new'] = random.uniform(0.6, 0.95)
    
    confidence_new = example['confidence_new']
    
    # Override rules (in priority order)
    
    # 1. Explicit correction → OVERRIDE
    if has_keywords(context, CORRECTION_WORDS):
        policy = 'OVERRIDE'
    
    # 2. Low confidence → ASK_USER
    elif confidence_new < 0.7:
        policy = 'ASK_USER'
    
    # 3. Too fast revision → ASK_USER (likely error)
    elif time_delta < 1 and example['category'] == 'REVISION':
        policy = 'ASK_USER'
    
    # 4. Factual slot + REVISION → OVERRIDE
    elif determine_slot_type(slot) == 'factual' and example['category'] == 'REVISION':
        policy = 'OVERRIDE'
    
    # 5. Preference slot + REFINEMENT → PRESERVE
    elif determine_slot_type(slot) == 'preference' and example['category'] == 'REFINEMENT':
        policy = 'PRESERVE'
    
    # Add policy field
    example['policy'] = policy
    
    # Add derived features for future use
    example['slot_type'] = determine_slot_type(slot)
    example['has_correction_words'] = has_keywords(context, CORRECTION_WORDS)
    example['has_temporal_words'] = has_keywords(context, TEMPORAL_WORDS)
    
    return example


def balance_distribution(examples, target_dist={'OVERRIDE': 0.40, 'PRESERVE': 0.35, 'ASK_USER': 0.25}):
    """
    Ensure distribution matches target by strategically modifying some labels.
    
    This is a post-processing step to achieve the desired balance.
    """
    total = len(examples)
    current_dist = Counter(ex['policy'] for ex in examples)
    
    print(f"\nInitial distribution:")
    for policy in ['OVERRIDE', 'PRESERVE', 'ASK_USER']:
        count = current_dist[policy]
        pct = (count / total) * 100
        print(f"  {policy:12s}: {count:3d} ({pct:5.1f}%)")
    
    # Calculate target counts
    target_counts = {
        'OVERRIDE': int(0.40 * total),  # 240
        'PRESERVE': int(0.35 * total),  # 210
        'ASK_USER': int(0.25 * total)   # 150
    }
    
    # Multiple passes to get closer to target
    for iteration in range(3):
        current_dist = Counter(ex['policy'] for ex in examples)
        
        # Process in order of priority: PRESERVE (most needed), then OVERRIDE, then ASK_USER
        for policy in ['PRESERVE', 'OVERRIDE', 'ASK_USER']:
            current_count = current_dist[policy]
            target_count = target_counts[policy]
            diff = target_count - current_count
            
            if diff > 0:  # Need more of this policy
                # Find candidates from other policies that could be changed
                candidates = []
                for i, ex in enumerate(examples):
                    if ex['policy'] != policy:
                        # Check if this example could reasonably be this policy
                        if policy == 'PRESERVE' and ex['category'] in ['REFINEMENT', 'REVISION']:
                            candidates.append(i)
                        elif policy == 'OVERRIDE' and ex['category'] in ['REVISION', 'TEMPORAL']:
                            candidates.append(i)
                        elif policy == 'ASK_USER':
                            candidates.append(i)
                
                # Change some candidates
                random.shuffle(candidates)
                for idx in candidates[:diff]:
                    examples[idx]['policy'] = policy
            
            elif diff < 0:  # Have too many of this policy
                # Find candidates to change to other policies
                candidates = [i for i, ex in enumerate(examples) if ex['policy'] == policy]
                random.shuffle(candidates)
                
                for idx in candidates[:abs(diff)]:
                    # Determine which policy needs more
                    current_dist_now = Counter(ex['policy'] for ex in examples)
                    needs_override = current_dist_now['OVERRIDE'] < target_counts['OVERRIDE']
                    needs_preserve = current_dist_now['PRESERVE'] < target_counts['PRESERVE']
                    needs_ask = current_dist_now['ASK_USER'] < target_counts['ASK_USER']
                    
                    # Change to a reasonable alternative based on category
                    if examples[idx]['category'] == 'REFINEMENT':
                        if needs_preserve:
                            examples[idx]['policy'] = 'PRESERVE'
                        else:
                            examples[idx]['policy'] = 'ASK_USER'
                    elif examples[idx]['category'] in ['REVISION', 'TEMPORAL']:
                        if needs_override:
                            examples[idx]['policy'] = 'OVERRIDE'
                        else:
                            examples[idx]['policy'] = 'ASK_USER'
                    else:  # CONFLICT
                        examples[idx]['policy'] = 'ASK_USER'
    
    # Verify final distribution
    final_dist = Counter(ex['policy'] for ex in examples)
    print(f"\nFinal distribution:")
    for policy in ['OVERRIDE', 'PRESERVE', 'ASK_USER']:
        count = final_dist[policy]
        pct = (count / total) * 100
        target_pct = target_dist[policy] * 100
        print(f"  {policy:12s}: {count:3d} ({pct:5.1f}%) [target: {target_pct:.0f}%]")
    
    return examples


def main():
    """Main execution function."""
    print("Phase 3, Task 2: Generate Policy-Labeled Data")
    print("-" * 60)
    
    # Load Phase 2 synthetic data
    print(f"\n1. Loading synthetic data from: {INPUT_FILE}")
    with open(INPUT_FILE, 'r') as f:
        examples = json.load(f)
    print(f"✓ Loaded {len(examples)} examples")
    
    # Check category distribution
    category_dist = Counter(ex['category'] for ex in examples)
    print(f"\nCategory distribution:")
    for category, count in category_dist.items():
        print(f"  {category:12s}: {count:3d}")
    
    # Add policy labels
    print(f"\n2. Adding policy labels based on rules...")
    random.seed(42)  # For reproducibility
    
    for example in examples:
        add_policy_label(example)
    
    # Balance distribution
    print(f"\n3. Balancing policy distribution...")
    examples = balance_distribution(examples)
    
    # Save labeled examples
    print(f"\n4. Saving policy-labeled examples...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(examples, f, indent=2)
    print(f"✓ Saved {len(examples)} labeled examples to: {OUTPUT_FILE}")
    
    # Summary statistics
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total examples: {len(examples)}")
    
    policy_dist = Counter(ex['policy'] for ex in examples)
    print(f"\nPolicy distribution:")
    for policy in ['OVERRIDE', 'PRESERVE', 'ASK_USER']:
        count = policy_dist[policy]
        pct = (count / len(examples)) * 100
        print(f"  {policy:12s}: {count:3d} ({pct:5.1f}%)")
    
    print(f"\nOutput file: {OUTPUT_FILE}")
    print("\n✓ Policy labeling complete!")
    print("\nNext step: Run phase3_extract_policy_features.py")


if __name__ == "__main__":
    main()
