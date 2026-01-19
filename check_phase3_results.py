import json

with open('comprehensive_validation_results.json') as f:
    data = json.load(f)

# Find phase3
phase3 = next((p for p in data['phase_results'] if p['phase_name'] == 'phase3_synthesis'), None)

if phase3:
    print('Phase3 Synthesis Results:')
    print('=' * 80)
    for q in phase3['results']:
        status = 'PASS' if q['passed'] else 'FAIL'
        print(f"  {q['query']}")
        print(f"    {status} (gates:{q['gates_passed']}, meaningful:{q['is_meaningful']})")
        print(f"    Answer: {q['answer'][:150]}...")
        print()
    
    passed = sum(1 for q in phase3['results'] if q['passed'])
    total = len(phase3['results'])
    print(f"Total: {passed}/{total} ({100*passed/total:.1f}%)")
else:
    print("Phase3 not found")

print()
print(f"Overall: {data['total_passed']}/{data['total_queries']} ({data['overall_pass_rate']:.1f}%)")
