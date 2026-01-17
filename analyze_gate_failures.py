"""
Analyze gate rejection patterns with ML classifier
"""
import json

with open('comprehensive_validation_results.json') as f:
    results = json.load(f)

print("="*80)
print("GATE REJECTION ANALYSIS")
print("="*80)

failures = []
for phase_result in results['phase_results']:
    phase_name = phase_result['phase_name']
    for query in phase_result['results']:
        if not query['passed']:
            failures.append({
                'phase': phase_name,
                'query': query['query'],
                'gates_passed': query['gates_passed'],
                'meaningful': query['is_meaningful'],
                'response_type': query.get('response_type', 'unknown'),
                'answer': query.get('answer', '')[:80],
            })

print(f"\nTotal failures: {len(failures)}/19")
print("\nFailed queries breakdown:\n")

gate_failures = [f for f in failures if not f['gates_passed']]
meaningful_failures = [f for f in failures if f['gates_passed'] and not f['meaningful']]

print(f"Gate rejections: {len(gate_failures)}")
print(f"Meaningful answer failures: {len(meaningful_failures)}")

if gate_failures:
    print("\n" + "="*80)
    print("GATE REJECTIONS (need threshold tuning)")
    print("="*80)
    for f in gate_failures:
        print(f"\n{f['query']}")
        print(f"  Type: {f['response_type']}")
        print(f"  Answer: {f['answer']}")
        print(f"  Phase: {f['phase']}")

if meaningful_failures:
    print("\n" + "="*80)
    print("MEANINGFUL ANSWER FAILURES (content quality)")
    print("="*80)
    for f in meaningful_failures:
        print(f"\n{f['query']}")
        print(f"  Type: {f['response_type']}")
        print(f"  Phase: {f['phase']}")

# Aggregate by response type
from collections import defaultdict
by_type = defaultdict(list)
for f in gate_failures:
    by_type[f['response_type']].append(f)

print("\n" + "="*80)
print("GATE FAILURES BY RESPONSE TYPE")
print("="*80)
for rtype, fails in by_type.items():
    if fails:
        print(f"\n{rtype.upper()}: {len(fails)} failures")
        for fail in fails:
            print(f"  - {fail['query']}")

