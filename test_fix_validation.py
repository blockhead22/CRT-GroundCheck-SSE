#!/usr/bin/env python3
"""
Quick validation of the 3 fixes:
1. Memory alignment threshold lowered (0.45 -> 0.38)
2. Contradiction status detection fixed
3. Testing gate pass rate improvement
"""
import requests
import time

def test_fixes():
    thread_id = f"fix_validation_{int(time.time())}"
    base_url = "http://127.0.0.1:8123"
    
    tests = [
        {
            "name": "Turn 4 Repro - Should NOT trigger contradiction handler",
            "message": "I work full-time on CRT development, focusing on memory architecture and contradiction detection.",
            "expected_gate_reason": "gates_passed",  # NOT "contradiction_status"
            "expected_gates": True
        },
        {
            "name": "Detailed explanation - Should pass gates with new threshold",
            "message": "Explain how CRT's memory system works in detail.",
            "expect_long": True,
            "min_gate_confidence": 0.6  # Should pass with lower threshold
        },
        {
            "name": "Legitimate contradiction query - Should trigger handler",
            "message": "Do you have any open contradictions?",
            "expected_gate_reason": "contradiction_status",
            "expected_gates": False
        },
        {
            "name": "Memory recall with detail",
            "message": "What have I told you about CRT so far?",
            "expect_long": True,
            "expected_gates": True  # Should pass with new threshold
        }
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    # Seed with foundation
    requests.post(f"{base_url}/api/chat/send", 
                 json={"thread_id": thread_id, "message": "I'm Nick Block, and I created CRT in 2025."})
    time.sleep(0.3)
    
    for i, test in enumerate(tests, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {test['name']}")
        print(f"{'='*80}")
        print(f">>> {test['message']}")
        
        r = requests.post(f"{base_url}/api/chat/send",
                         json={"thread_id": thread_id, "message": test['message']})
        data = r.json()
        
        answer = data['answer']
        gates = data.get('gates_passed', False)
        gate_reason = data.get('gate_reason', 'unknown')
        conf = data['metadata'].get('confidence', 0)
        
        print(f"\n<<< {answer[:200]}{'...' if len(answer) > 200 else ''}")
        print(f"\n[Gates: {gates} | Reason: {gate_reason} | Conf: {conf:.2f} | Length: {len(answer)}]")
        
        # Validate expectations
        passed = True
        issues = []
        
        if 'expected_gate_reason' in test and gate_reason != test['expected_gate_reason']:
            passed = False
            issues.append(f"Gate reason mismatch: expected {test['expected_gate_reason']}, got {gate_reason}")
        
        if 'expected_gates' in test and gates != test['expected_gates']:
            passed = False
            issues.append(f"Gates mismatch: expected {test['expected_gates']}, got {gates}")
        
        if test.get('expect_long') and len(answer) < 200:
            passed = False
            issues.append(f"Expected long response, got {len(answer)} chars")
        
        if test.get('min_gate_confidence') and conf < test['min_gate_confidence']:
            passed = False
            issues.append(f"Confidence too low: {conf:.2f} < {test['min_gate_confidence']}")
        
        if passed:
            print("✅ PASS")
            results['passed'] += 1
        else:
            print("❌ FAIL:")
            for issue in issues:
                print(f"   - {issue}")
            results['failed'] += 1
        
        results['details'].append({
            "test": test['name'],
            "passed": passed,
            "issues": issues
        })
        
        time.sleep(0.3)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Passed: {results['passed']}/{len(tests)}")
    print(f"Failed: {results['failed']}/{len(tests)}")
    
    if results['failed'] == 0:
        print("\n✅ All fixes validated successfully!")
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed - review above")
    
    return results

if __name__ == "__main__":
    print("🧪 Validating 3 Fixes")
    print("1. Memory alignment threshold: 0.45 -> 0.38")
    print("2. Contradiction status detection: require interrogative context")
    print("3. Gate pass rate improvement")
    
    test_fixes()
