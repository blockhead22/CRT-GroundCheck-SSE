from groundcheck import GroundCheck, Memory
import time

verifier = GroundCheck()

test_cases = [
    ("works at Google", "employed by Google"),
    ("works at Google", "job at Google"),
    ("software engineer", "SWE"),
    ("lives in Seattle", "resides in Seattle"),
    ("likes coffee", "enjoys coffee"),
    ("allergic to peanuts", "peanut allergy"),
    ("knows Python", "familiar with Python"),
]

print("🏃 SEMANTIC PARAPHRASING STRESS TEST\n")
passed = 0
total_time = 0

for i, (memory_text, claim_text) in enumerate(test_cases, 1):
    print(f"Test {i}/7: '{memory_text}' ≈ '{claim_text}'")
    memories = [Memory(id=f'm{i}', text=f"User {memory_text}", timestamp=1704067200)]
    
    start = time.time()
    result = verifier.verify(f"User {claim_text}", memories)
    latency = (time.time() - start) * 1000
    total_time += latency
    
    if result.passed and len(result.hallucinations) == 0:
        print(f"  ✅ PASS ({latency:.2f}ms)")
        passed += 1
    else:
        print(f"  ❌ FAIL - Treated as hallucination")
    print()

print(f"Results: {passed}/{len(test_cases)} passed")
print(f"Average latency: {total_time/len(test_cases):.2f}ms\n")
