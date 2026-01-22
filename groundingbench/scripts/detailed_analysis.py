"""Detailed analysis of groundcheck performance on GroundingBench."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "groundcheck"))
from groundcheck import GroundCheck, Memory

def analyze_category(category: str):
    """Analyze groundcheck performance on a specific category."""
    data_file = Path(__file__).parent.parent / "data" / f"{category}.jsonl"
    examples = [json.loads(line) for line in open(data_file)]
    
    verifier = GroundCheck()
    
    print(f"\n{'=' * 70}")
    print(f"Category: {category}")
    print(f"{'=' * 70}")
    
    mismatches = []
    
    for example in examples:
        memories = [
            Memory(id=ctx["id"], text=ctx["text"], trust=ctx.get("trust", 1.0))
            for ctx in example["retrieved_context"]
        ]
        
        result = verifier.verify(example["generated_output"], memories)
        expected = example["label"]["grounded"]
        
        if expected != result.passed:
            mismatches.append({
                "id": example["id"],
                "query": example["query"],
                "output": example["generated_output"],
                "expected": expected,
                "predicted": result.passed,
                "hallucinations_found": result.hallucinations,
                "hallucinations_labeled": example["label"]["hallucinations"],
                "confidence": result.confidence
            })
    
    if mismatches:
        print(f"Found {len(mismatches)} mismatches:")
        for m in mismatches:
            print(f"\n  ID: {m['id']}")
            print(f"  Query: {m['query']}")
            print(f"  Output: {m['output']}")
            print(f"  Expected: {'✅ Grounded' if m['expected'] else '❌ Not grounded'}")
            print(f"  Predicted: {'✅ Grounded' if m['predicted'] else '❌ Not grounded'}")
            print(f"  Labeled hallucinations: {m['hallucinations_labeled']}")
            print(f"  Found hallucinations: {m['hallucinations_found']}")
            print(f"  Confidence: {m['confidence']:.2f}")
    else:
        print("✅ All examples match expected labels!")

if __name__ == "__main__":
    categories = ["factual_grounding", "contradictions", "partial_grounding", 
                  "paraphrasing", "multi_hop"]
    
    for cat in categories:
        analyze_category(cat)
