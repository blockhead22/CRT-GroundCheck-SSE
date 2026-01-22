from groundcheck import GroundCheck, Memory
import time

verifier = GroundCheck()

test_cases = [
    {
        "name": "Programming languages (Oxford comma)",
        "memory": "User knows Python and JavaScript",
        "claim": "You use Python, JavaScript, Ruby, and Go",
        "expected_hallucinations": ["Ruby", "Go"]
    },
    {
        "name": "Multiple separators mixed",
        "memory": "User likes hiking and swimming",
        "claim": "You enjoy hiking, swimming, running; skiing/snowboarding and surfing",
        "expected_hallucinations": ["running", "skiing", "snowboarding", "surfing"]
    },
    {
        "name": "Slash-separated with spaces",
        "memory": "User location: Seattle",
        "claim": "You're in Seattle / Portland / San Francisco",
        "expected_hallucinations": ["Portland", "San Francisco"]
    },
]

print("🔥 COMPOUND VALUE STRESS TEST\n")
passed = 0

for i, test in enumerate(test_cases, 1):
    print(f"Test {i}: {test['name']}")
    memories = [Memory(id=f'm{i}', text=test['memory'], timestamp=1704067200)]
    
    start = time.time()
    result = verifier.verify(test['claim'], memories)
    latency = (time.time() - start) * 1000
    
    detected = set(result.hallucinations)
    expected = set(test['expected_hallucinations'])
    
    if detected == expected:
        print(f"  ✅ PASS ({latency:.2f}ms)")
        passed += 1
    else:
        print(f"  ❌ FAIL - Expected: {expected}, Got: {detected}")
    print()

print(f"Results: {passed}/{len(test_cases)} passed\n")
