"""Check GroundCheck against benchmark's requires_contradiction_disclosure labels."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "groundcheck"))
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()
data_file = Path(__file__).parent / "data" / "contradictions.jsonl"

print("=== CHECKING REQUIRES_CONTRADICTION_DISCLOSURE LABELS ===\n")

correct_count = 0
total_count = 0

with open(data_file) as f:
    for i, line in enumerate(f, 1):
        example = json.loads(line)
        memories = [
            Memory(
                id=m["id"], 
                text=m["text"], 
                trust=m.get("trust", 1.0),
                timestamp=m.get("timestamp")
            )
            for m in example["retrieved_context"]
        ]
        result = verifier.verify(example["generated_output"], memories)
        
        expected_disclosure = example["label"].get("requires_contradiction_disclosure", False)
        
        # Evaluation logic from evaluate_all.py
        if expected_disclosure:
            # Should detect disclosure requirement
            correct = result.requires_disclosure
        else:
            # Should pass (no disclosure needed)
            correct = result.passed
        
        status = "✅" if correct else "❌"
        if correct:
            correct_count += 1
        total_count += 1
        
        print(f"{status} {example['id']}")
        print(f"   Expected disclosure: {expected_disclosure}")
        print(f"   Our requires_disclosure: {result.requires_disclosure}")
        print(f"   Our passed: {result.passed}")
        if expected_disclosure != result.requires_disclosure:
            print(f"   ** MISMATCH: Expected disclosure={expected_disclosure}, got {result.requires_disclosure}")
        if not expected_disclosure and not result.passed:
            print(f"   ** MISMATCH: Should pass but passed={result.passed}")
        print()

print(f"{'='*70}")
print(f"SCORE: {correct_count}/{total_count} ({correct_count/total_count*100:.0f}%)")
print(f"{'='*70}")
