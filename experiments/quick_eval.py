"""Quick GroundCheck evaluation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "groundcheck"))
from groundcheck import GroundCheck, Memory

# Load data
examples = [json.loads(line) for line in open('../groundingbench/data/combined.jsonl')]
print(f'Loaded {len(examples)} examples\n')

# Evaluate
verifier = GroundCheck()
correct = 0
by_cat = {}

for ex in examples:
    cat = ex['category']
    mems = [
        Memory(id=m['id'], text=m['text'], trust=m.get('trust', 1.0), timestamp=m.get('timestamp')) 
        for m in ex['retrieved_context']
    ]
    res = verifier.verify(ex['generated_output'], mems)
    exp_disc = ex['label'].get('requires_contradiction_disclosure', False)
    
    if exp_disc:
        ok = res.requires_disclosure
    else:
        ok = res.passed == ex['label']['grounded']
    
    if ok:
        correct += 1
    if cat not in by_cat:
        by_cat[cat] = {'c': 0, 't': 0}
    if ok:
        by_cat[cat]['c'] += 1
    by_cat[cat]['t'] += 1

print(f'GroundCheck Results:')
print(f'  Overall: {correct/len(examples)*100:.1f}% ({correct}/{len(examples)})')
for cat, stats in by_cat.items():
    acc = stats["c"]/stats["t"]*100
    print(f'    {cat}: {acc:.1f}% ({stats["c"]}/{stats["t"]})')
