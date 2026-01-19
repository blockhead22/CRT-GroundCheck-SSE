"""Show detailed failure information from latest validation."""
import json

with open('comprehensive_validation_results.json') as f:
    data = json.load(f)

failures = []
for phase in data['phase_results']:
    for result in phase['results']:
        if not result['passed']:
            failures.append({
                'phase': phase['phase_name'],
                'query': result['query'],
                'gates': result['gates_passed'],
                'meaningful': result['is_meaningful'],
                'answer': result['answer'][:200]
            })

print("=" * 80)
print(f"REMAINING FAILURES: {len(failures)}/19")
print("=" * 80)
print()

for i, f in enumerate(failures, 1):
    print(f"{i}. {f['query']}")
    print(f"   Phase: {f['phase']}")
    print(f"   Gates: {f['gates']}, Meaningful: {f['meaningful']}")
    print(f"   Answer: {f['answer']}...")
    print()

print("=" * 80)
print(f"Pass rate: {data['total_passed']}/{data['total_queries']} = {data['overall_pass_rate']:.1f}%")
