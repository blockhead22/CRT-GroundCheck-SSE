"""Example: Evaluate groundcheck against GroundingBench dataset."""
import json
import sys
from pathlib import Path

# Add parent directories to path to import groundcheck
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "groundcheck"))

try:
    from groundcheck import GroundCheck, Memory
except ImportError:
    print("Warning: groundcheck not found. Install with: pip install -e groundcheck/")
    print("This example shows how to use groundcheck with GroundingBench.\n")

def load_dataset(category: str = None):
    """Load GroundingBench dataset."""
    data_dir = Path(__file__).parent.parent / "data"
    
    if category:
        file_path = data_dir / f"{category}.jsonl"
    else:
        file_path = data_dir / "combined.jsonl"
    
    examples = []
    with open(file_path) as f:
        for line in f:
            examples.append(json.loads(line))
    
    return examples

def evaluate_groundcheck(examples, verbose=False):
    """Evaluate groundcheck on dataset examples."""
    verifier = GroundCheck()
    
    correct = 0
    total = 0
    
    for example in examples:
        # Convert retrieved_context to Memory objects
        memories = [
            Memory(
                id=ctx["id"],
                text=ctx["text"],
                trust=ctx.get("trust", 1.0)
            )
            for ctx in example["retrieved_context"]
        ]
        
        # Verify with groundcheck
        result = verifier.verify(example["generated_output"], memories)
        
        # Compare to ground truth label
        expected = example["label"]["grounded"]
        predicted = result.passed
        
        if expected == predicted:
            correct += 1
        elif verbose:
            print(f"❌ Mismatch on {example['id']}:")
            print(f"   Expected: {expected}, Got: {predicted}")
            print(f"   Query: {example['query']}")
            print(f"   Output: {example['generated_output']}")
            print()
        
        total += 1
    
    accuracy = correct / total if total > 0 else 0
    return accuracy, correct, total

def main():
    """Run evaluation."""
    print("=" * 60)
    print("GroundingBench Evaluation with GroundCheck")
    print("=" * 60)
    
    # Load dataset
    examples = load_dataset()
    print(f"\nLoaded {len(examples)} examples")
    
    # Evaluate by category
    categories = ["factual_grounding", "contradictions", "partial_grounding", 
                  "paraphrasing", "multi_hop"]
    
    print("\nResults by category:")
    print("-" * 60)
    
    for category in categories:
        cat_examples = load_dataset(category)
        accuracy, correct, total = evaluate_groundcheck(cat_examples)
        print(f"{category:20s}: {correct:3d}/{total:3d} ({accuracy*100:5.1f}%)")
    
    # Overall evaluation
    print("-" * 60)
    accuracy, correct, total = evaluate_groundcheck(examples)
    print(f"{'Overall':20s}: {correct:3d}/{total:3d} ({accuracy*100:5.1f}%)")
    print("=" * 60)
    
    # Show some examples
    print("\nExample benchmark items:")
    for i, example in enumerate(examples[:3]):
        print(f"\n{i+1}. {example['id']} ({example['category']})")
        print(f"   Query: {example['query']}")
        print(f"   Generated: {example['generated_output']}")
        print(f"   Label: {'✅ Grounded' if example['label']['grounded'] else '❌ Not grounded'}")
        if example['label'].get('hallucinations'):
            print(f"   Hallucinations: {example['label']['hallucinations']}")

if __name__ == "__main__":
    main()
