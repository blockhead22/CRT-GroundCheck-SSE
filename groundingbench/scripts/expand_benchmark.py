"""Script to expand GroundingBench to 500 examples."""

import json
import random
from pathlib import Path
from typing import List, Dict

# Templates for generating new examples
TEMPLATES = {
    "factual_grounding": [
        {
            "query": "What is my {slot}?",
            "memory_template": "User's {slot} is {value}",
            "output_grounded": "Your {slot} is {value}",
            "output_hallucinated": "Your {slot} is {wrong_value}",
        }
    ],
    "paraphrasing": [
        {
            "query": "Where do I work?",
            "memory_variants": [
                "User works at {company}",
                "User is employed by {company}",
                "User has a job at {company}",
                "{company} employee",
            ],
            "output_variants": [
                "You work at {company}",
                "You're employed by {company}",
                "Your employer is {company}",
            ]
        }
    ],
    "contradictions": [
        {
            "query": "Where do I work?",
            "memories": [
                {"text": "User works at {company_a}", "trust": 0.9, "timestamp": "2025-01-01"},
                {"text": "User works at {company_b}", "trust": 0.85, "timestamp": "2025-06-01"},
            ],
            "output_with_disclosure": "You work at {company_b} (changed from {company_a})",
            "output_without_disclosure": "You work at {company_b}",
        }
    ]
}

# Sample values for template filling
SAMPLE_VALUES = {
    "company": ["Microsoft", "Google", "Amazon", "Apple", "Meta", "Netflix", "Spotify", "Tesla", "OpenAI", "Anthropic"],
    "location": ["Seattle", "San Francisco", "New York", "Austin", "Boston", "Denver", "Portland", "Chicago"],
    "name": ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"],
    "occupation": ["Software Engineer", "Product Manager", "Data Scientist", "Designer", "DevOps Engineer"],
    "school": ["MIT", "Stanford", "Berkeley", "CMU", "Harvard", "Yale", "Princeton"],
    "programming_language": ["Python", "JavaScript", "Go", "Rust", "Java", "C++", "TypeScript"],
    "hobby": ["reading", "hiking", "gaming", "cooking", "photography", "music"],
}

def generate_factual_grounding_examples(count: int) -> List[Dict]:
    """Generate factual grounding examples."""
    examples = []
    slots = ["employer", "location", "name", "occupation", "school"]
    
    for i in range(count):
        slot = random.choice(slots)
        value = random.choice(SAMPLE_VALUES.get(slot.replace("employer", "company"), ["value"]))
        wrong_value = random.choice([v for v in SAMPLE_VALUES.get(slot.replace("employer", "company"), ["wrong"]) if v != value])
        
        example = {
            "id": f"factual_{i}",
            "query": f"What is my {slot}?",
            "memories": [
                {"id": "m1", "text": f"User's {slot} is {value}", "trust": 0.9}
            ],
            "output_grounded": f"Your {slot} is {value}",
            "output_hallucinated": f"Your {slot} is {wrong_value}",
            "expected_grounded": True,
            "expected_hallucinated": False,
        }
        examples.append(example)
    
    return examples

def generate_paraphrasing_examples(count: int) -> List[Dict]:
    """Generate paraphrasing examples."""
    examples = []
    
    paraphrases = {
        "employer": [
            ("works at", "work for"),
            ("job at", "are employed by"),
            ("employee of", "work at"),
        ],
        "location": [
            ("lives in", "reside in"),
            ("based in", "are located in"),
            ("from", "are originally from"),
        ],
    }
    
    for i in range(count):
        slot = random.choice(list(paraphrases.keys()))
        phrase_a, phrase_b = random.choice(paraphrases[slot])
        value = random.choice(SAMPLE_VALUES.get(slot.replace("employer", "company"), ["Seattle"]))
        
        # Ensure proper grammar - add "are" or "do" as needed
        output_phrase = phrase_b
        if not any(helper in output_phrase for helper in ["are", "do", "work"]):
            # For phrases without helping verbs, add appropriate one
            if "reside" in output_phrase or "located" in output_phrase:
                output_phrase = output_phrase
            elif output_phrase.startswith("work"):
                output_phrase = output_phrase  # "work for" is correct
            else:
                output_phrase = f"are {output_phrase}"
        
        example = {
            "id": f"paraphrase_{i}",
            "query": f"Where do I work?" if slot == "employer" else "Where do I live?",
            "memories": [
                {"id": "m1", "text": f"User {phrase_a} {value}", "trust": 0.9}
            ],
            "output": f"You {output_phrase} {value}",
            "expected_grounded": True,
        }
        examples.append(example)
    
    return examples

def generate_contradiction_examples(count: int) -> List[Dict]:
    """Generate contradiction examples."""
    examples = []
    
    for i in range(count):
        company_a = random.choice(SAMPLE_VALUES["company"])
        company_b = random.choice([c for c in SAMPLE_VALUES["company"] if c != company_a])
        
        # Randomly assign which company is more recent
        if random.random() > 0.5:
            company_a, company_b = company_b, company_a
        
        example = {
            "id": f"contradiction_{i}",
            "query": "Where do I work?",
            "memories": [
                {"id": "m1", "text": f"User works at {company_a}", "trust": 0.9, "timestamp": 1640995200},
                {"id": "m2", "text": f"User works at {company_b}", "trust": 0.85, "timestamp": 1656633600},
            ],
            "output_with_disclosure": f"You work at {company_b} (changed from {company_a})",
            "output_without_disclosure": f"You work at {company_b}",
            "expected_requires_disclosure": True,
        }
        examples.append(example)
    
    return examples

def main():
    """Generate expanded benchmark dataset."""
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    
    print("Generating expanded benchmark examples...")
    
    # Generate examples
    categories = {
        "factual_grounding": generate_factual_grounding_examples(100),
        "paraphrasing": generate_paraphrasing_examples(100),
        "contradictions": generate_contradiction_examples(100),
    }
    
    # Write to files
    for category, examples in categories.items():
        output_file = output_dir / f"{category}_expanded.jsonl"
        with open(output_file, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")
        
        print(f"✓ Generated {len(examples)} examples for {category}")
        print(f"  Saved to {output_file}")
    
    print(f"\nTotal examples generated: {sum(len(ex) for ex in categories.values())}")

if __name__ == "__main__":
    main()
