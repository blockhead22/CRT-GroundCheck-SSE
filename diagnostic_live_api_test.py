"""Comprehensive live API contradiction test"""
import requests
import json
import time

API_URL = "http://127.0.0.1:8123/api/chat/send"
API_CONTRA = "http://127.0.0.1:8123/api/contradictions"
API_RESOLVE = "http://127.0.0.1:8123/api/resolve_contradiction"

def test_contradiction_case(thread_id, statement1, statement2, expected_slot, should_detect=True):
    """Test a single contradiction case."""
    print(f"\n{'='*70}")
    print(f"Testing: {statement1} → {statement2}")
    print(f"Expected slot: {expected_slot}, Should detect: {should_detect}")
    print("="*70)
    
    # First statement
    r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": statement1}, timeout=30)
    if r1.status_code != 200:
        print(f"❌ Step 1 failed: {r1.status_code}")
        return False
    print(f"✓ Step 1: {r1.json()['answer'][:60]}...")
    
    time.sleep(0.5)
    
    # Second (contradicting) statement
    r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": statement2}, timeout=30)
    if r2.status_code != 200:
        print(f"❌ Step 2 failed: {r2.status_code}")
        return False
    
    data = r2.json()
    detected = data.get("contradiction_detected") or data.get("metadata", {}).get("contradiction_detected", False)
    
    print(f"✓ Step 2: {data['answer'][:60]}...")
    print(f"  Contradiction detected: {detected}")
    print(f"  Category: {data.get('category', 'N/A')}")
    
    if should_detect and detected:
        print(f"✅ PASS - Contradiction correctly detected")
        return True
    elif not should_detect and not detected:
        print(f"✅ PASS - Correctly did not detect (not a contradiction)")
        return True
    elif should_detect and not detected:
        print(f"❌ FAIL - Contradiction MISSED!")
        return False
    else:
        print(f"❌ FAIL - False positive")
        return False


def run_all_tests():
    """Run all contradiction test cases."""
    timestamp = int(time.time())
    results = {}
    
    # Test Case 1: Employer (should work - slot exists)
    results["employer"] = test_contradiction_case(
        f"test_employer_{timestamp}",
        "I work at Microsoft",
        "I work at Amazon",
        "employer",
        should_detect=True
    )
    
    # Test Case 2: Location (should work - slot exists)  
    results["location"] = test_contradiction_case(
        f"test_location_{timestamp}",
        "I live in Seattle",
        "I moved to Denver",
        "location",
        should_detect=True
    )
    
    # Test Case 3: Name (should work - slot exists)
    results["name"] = test_contradiction_case(
        f"test_name_{timestamp}",
        "My name is Nick",
        "My name is Ben",
        "name",
        should_detect=True
    )
    
    # Test Case 4: Age (will fail - slot doesn't exist)
    results["age"] = test_contradiction_case(
        f"test_age_{timestamp}",
        "I am 25 years old",
        "I am 30 years old",
        "age",
        should_detect=True
    )
    
    # Test Case 5: Remote preference (should work - slot exists)
    results["preference"] = test_contradiction_case(
        f"test_pref_{timestamp}",
        "I prefer working remotely",
        "I prefer the office",
        "remote_preference",
        should_detect=True
    )
    
    # Summary
    print("\n" + "="*70)
    print("LIVE API TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for case, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {case}: {status}")
    
    print(f"\nOverall: {passed}/{total} ({100*passed/total:.0f}%)")
    
    if results.get("employer") and results.get("location") and results.get("name"):
        print("\n✅ ML-based detection IS WORKING for slots that have extraction")
    
    if not results.get("age"):
        print("\n⚠️  AGE DETECTION FAILED because:")
        print("   - No 'age' slot in fact_slots.py")
        print("   - ML detector never called (no facts extracted)")
        print("   - FIX: Add age extraction pattern to fact_slots.py")
    
    return results


if __name__ == "__main__":
    run_all_tests()
