#!/usr/bin/env python3
"""
Phase 1, Step 3: Generate Synthetic Belief Updates

This script generates synthetic belief update examples using templates.
This is the FREE version - no API calls required.

For higher quality, you can optionally use GPT-4 (see commented code).
"""

import json
import random
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "data"

# Templates for each category
TEMPLATES = {
    'REFINEMENT': [
        {
            'old_value': 'I like {item1}',
            'new_value': 'I like {item1} and {item2}',
            'slots': ['skill', 'preference', 'hobby'],
            'items': [
                ['Python', 'JavaScript'],
                ['coffee', 'tea'],
                ['reading', 'writing'],
                ['running', 'swimming'],
                ['movies', 'series']
            ]
        },
        {
            'old_value': 'I work with {tool1}',
            'new_value': 'I work with {tool1}, {tool2}, and {tool3}',
            'slots': ['skill', 'tool'],
            'items': [
                ['Python', 'Docker', 'Kubernetes'],
                ['React', 'Vue', 'Angular'],
                ['PostgreSQL', 'Redis', 'MongoDB']
            ]
        }
    ],
    
    'REVISION': [
        {
            'old_value': 'I work at {company1}',
            'new_value': 'I work at {company2}',
            'slots': ['employer'],
            'items': [
                ['Microsoft', 'Amazon'],
                ['Google', 'Meta'],
                ['Apple', 'Tesla'],
                ['Netflix', 'Spotify'],
                ['Uber', 'Lyft']
            ]
        },
        {
            'old_value': 'I live in {city1}',
            'new_value': 'I live in {city2}',
            'slots': ['location'],
            'items': [
                ['Seattle', 'San Francisco'],
                ['New York', 'Austin'],
                ['London', 'Berlin'],
                ['Tokyo', 'Seoul']
            ]
        },
        {
            'old_value': 'My role is {role1}',
            'new_value': 'My role is {role2}',
            'slots': ['job_title'],
            'items': [
                ['Software Engineer', 'Senior Software Engineer'],
                ['Data Analyst', 'Data Scientist'],
                ['Product Manager', 'Director of Product']
            ]
        }
    ],
    
    'TEMPORAL': [
        {
            'old_value': "I'm {age1} years old",
            'new_value': "I'm {age2} years old",
            'slots': ['age'],
            'items': [
                ['25', '26'],
                ['30', '31'],
                ['28', '29']
            ]
        },
        {
            'old_value': 'Currently working on {project1}',
            'new_value': 'Currently working on {project2}',
            'slots': ['current_project'],
            'items': [
                ['API redesign', 'database migration'],
                ['frontend redesign', 'backend optimization'],
                ['user research', 'feature development']
            ]
        }
    ],
    
    'CONFLICT': [
        {
            'old_value': 'I prefer {option1}',
            'new_value': "I don't like {option1}",
            'slots': ['preference'],
            'items': [
                ['working remotely', 'working remotely'],
                ['morning meetings', 'morning meetings'],
                ['pair programming', 'pair programming']
            ]
        },
        {
            'old_value': 'I use {tool}',
            'new_value': "I've never used {tool}",
            'slots': ['skill'],
            'items': [
                ['Docker', 'Docker'],
                ['Kubernetes', 'Kubernetes'],
                ['TypeScript', 'TypeScript']
            ]
        }
    ]
}

def generate_from_template(category, template, num_examples=10):
    """Generate examples from a template."""
    examples = []
    
    for _ in range(num_examples):
        item_set = random.choice(template['items'])
        slot = random.choice(template['slots'])
        
        # Fill in template
        old_value = template['old_value']
        new_value = template['new_value']
        
        for i, item in enumerate(item_set):
            old_value = old_value.replace(f'{{item{i+1}}}', item)
            old_value = old_value.replace(f'{{tool{i+1}}}', item)
            old_value = old_value.replace(f'{{company{i+1}}}', item)
            old_value = old_value.replace(f'{{city{i+1}}}', item)
            old_value = old_value.replace(f'{{role{i+1}}}', item)
            old_value = old_value.replace(f'{{age{i+1}}}', item)
            old_value = old_value.replace(f'{{project{i+1}}}', item)
            old_value = old_value.replace(f'{{option{i+1}}}', item)
            old_value = old_value.replace(f'{{tool}}', item)
            
            new_value = new_value.replace(f'{{item{i+1}}}', item)
            new_value = new_value.replace(f'{{tool{i+1}}}', item)
            new_value = new_value.replace(f'{{company{i+1}}}', item)
            new_value = new_value.replace(f'{{city{i+1}}}', item)
            new_value = new_value.replace(f'{{role{i+1}}}', item)
            new_value = new_value.replace(f'{{age{i+1}}}', item)
            new_value = new_value.replace(f'{{project{i+1}}}', item)
            new_value = new_value.replace(f'{{option{i+1}}}', item)
            new_value = new_value.replace(f'{{tool}}', item)
        
        # Generate time delta (days between updates)
        if category == 'TEMPORAL':
            time_delta_days = random.randint(300, 400)  # About a year
        elif category == 'REVISION':
            time_delta_days = random.randint(30, 180)  # 1-6 months
        elif category == 'REFINEMENT':
            time_delta_days = random.randint(1, 30)  # Days to weeks
        else:  # CONFLICT
            time_delta_days = random.randint(7, 60)  # 1 week to 2 months
        
        example = {
            'id': f'synthetic_{category.lower()}_{len(examples)+1:03d}',
            'category': category,
            'slot': slot,
            'old_value': old_value,
            'new_value': new_value,
            'time_delta_days': time_delta_days,
            'context': f'User mentioned this after {time_delta_days} days',
            'recommended_action': {
                'REFINEMENT': 'PRESERVE',
                'REVISION': 'OVERRIDE',
                'TEMPORAL': 'OVERRIDE',
                'CONFLICT': 'ASK_USER'
            }[category],
            'source': 'template_generated'
        }
        
        examples.append(example)
    
    return examples

def generate_synthetic_dataset(target_total=600):
    """Generate synthetic dataset with balanced categories."""
    print("=" * 60)
    print("GENERATING SYNTHETIC BELIEF UPDATES")
    print("=" * 60)
    
    all_examples = []
    
    # Generate examples for each category (150 per category = 600 total)
    per_category = target_total // 4
    
    for category, templates in TEMPLATES.items():
        print(f"\nGenerating {category} examples...")
        category_examples = []
        
        # Distribute across templates
        per_template = per_category // len(templates)
        
        for template in templates:
            examples = generate_from_template(category, template, per_template)
            category_examples.extend(examples)
        
        print(f"  ✓ Generated {len(category_examples)} examples")
        all_examples.extend(category_examples)
    
    # Shuffle
    random.shuffle(all_examples)
    
    print(f"\n{'='*60}")
    print(f"Total synthetic examples generated: {len(all_examples)}")
    print(f"{'='*60}")
    
    # Save
    output_file = OUTPUT_DIR / "synthetic_belief_updates.json"
    with open(output_file, 'w') as f:
        json.dump(all_examples, f, indent=2)
    
    print(f"\n✓ Saved to: {output_file}")
    
    # Show distribution
    print("\nCategory distribution:")
    for category in ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']:
        count = sum(1 for ex in all_examples if ex['category'] == category)
        print(f"  - {category}: {count}")
    
    # Show examples
    print("\nExample synthetic updates:")
    for i, example in enumerate(all_examples[:3]):
        print(f"\n{i+1}. Category: {example['category']}")
        print(f"   Old: {example['old_value']}")
        print(f"   New: {example['new_value']}")
        print(f"   Action: {example['recommended_action']}")
    
    return all_examples

def main():
    """Generate synthetic dataset."""
    print("\n🤖" * 30)
    print("PHASE 1: SYNTHETIC DATA GENERATION")
    print("🤖" * 30 + "\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    examples = generate_synthetic_dataset(target_total=600)
    
    print("\n✅" * 30)
    print("SYNTHETIC DATA GENERATION COMPLETE!")
    print("✅" * 30 + "\n")
    
    print(f"Generated {len(examples)} synthetic examples")
    print("Next: Combine with real data for MTurk annotation\n")

if __name__ == "__main__":
    main()
