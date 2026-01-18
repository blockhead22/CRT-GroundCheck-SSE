"""Analyze the 10.5% of queries that still fail."""
import json

with open('comprehensive_validation_results.json') as f:
    data = json.load(f)

failures = []
for phase in data['phase_results']:
    for result in phase['results']:
        if not result['passed']:
            failures.append({
                'query': result['query'],
                'phase': phase['phase_name'],
                'difficulty': result['difficulty'],
                'gates': result['gates_passed'],
                'meaningful': result['is_meaningful']
            })

print("=" * 70)
print("🔍 ANALYZING THE 10.5% FAILURES")
print("=" * 70)

print(f"\nTotal failures: {len(failures)}/19 queries\n")

for i, f in enumerate(failures, 1):
    print(f"{i}. {f['query']}")
    print(f"   Phase: {f['phase']}")
    print(f"   Issue: {'Gates blocked' if not f['gates'] else 'Not meaningful'}")
    print()

print("=" * 70)
print("🎯 FAILURE PATTERNS")
print("=" * 70)

print("\n1. 'What do you know about my interests?' - SYNTHESIS FAILURE")
print("   Problem: Can't synthesize multiple facts into answer")
print("   Fix: Improve multi-fact aggregation in RAG")

print("\n2. 'How does CRT work?' - DOC-GROUNDED QUERY")
print("   Problem: System doc query, not personal memory")
print("   Fix: Better detection of meta/system queries")

print("\n🚀 NEXT IMPROVEMENTS:")
print("   Option A: Fix memory synthesis (biggest impact)")
print("   Option B: Improve meta-query handling")  
print("   Option C: Lower thresholds for edge cases")

print("\n" + "=" * 70)
