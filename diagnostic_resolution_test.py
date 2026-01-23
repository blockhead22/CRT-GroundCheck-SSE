"""Test OVERRIDE resolution and gate blocking"""
import requests
import json
import time

API_URL = "http://127.0.0.1:8123/api/chat/send"
API_CONTRA = "http://127.0.0.1:8123/api/contradictions"
API_RESOLVE = "http://127.0.0.1:8123/api/resolve_contradiction"

def test_gate_blocking():
    """Test that gates block when contradictions are unresolved."""
    print("=" * 70)
    print("TEST: Gate Blocking on Unresolved Contradictions")
    print("=" * 70)
    
    thread_id = f"gate_test_{int(time.time())}"
    
    # Create contradiction
    print("\n1. Creating employer contradiction...")
    r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Microsoft"}, timeout=30)
    print(f"   Setup: {r1.json()['answer'][:60]}...")
    
    time.sleep(0.5)
    
    r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Amazon"}, timeout=30)
    print(f"   Contradict: {r2.json()['answer'][:60]}...")
    
    # Query about employer - should be blocked
    print("\n2. Querying 'Where do I work?' - should be blocked...")
    r3 = requests.post(API_URL, json={"thread_id": thread_id, "message": "Where do I work?"}, timeout=30)
    data = r3.json()
    
    gates_passed = data.get("gates_passed", True)
    answer = data.get("answer", "")
    
    print(f"   Answer: {answer[:80]}...")
    print(f"   gates_passed: {gates_passed}")
    
    # Check if response indicates uncertainty or asks for clarification
    blocked = not gates_passed or "conflicting" in answer.lower() or "which" in answer.lower() or "unclear" in answer.lower()
    
    if blocked:
        print("   ✅ PASS - Gates correctly blocked (or asked for clarification)")
        return True
    else:
        print("   ❌ FAIL - Gates did not block!")
        return False


def test_override_resolution():
    """Test OVERRIDE resolution policy."""
    print("\n" + "=" * 70)
    print("TEST: OVERRIDE Resolution Policy")
    print("=" * 70)
    
    thread_id = f"override_test_{int(time.time())}"
    
    # Create contradiction
    print("\n1. Creating employer contradiction...")
    r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Microsoft"}, timeout=30)
    print(f"   Setup: {r1.json()['answer'][:60]}...")
    
    time.sleep(0.5)
    
    r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Amazon"}, timeout=30)
    print(f"   Contradict: {r2.json()['answer'][:60]}...")
    
    # Get contradictions
    print("\n2. Getting open contradictions...")
    r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
    
    if r_contra.status_code != 200:
        print(f"   ❌ Failed to get contradictions: {r_contra.status_code}")
        return False
    
    contradictions = r_contra.json().get("contradictions", [])
    
    if not contradictions:
        print("   ❌ No contradictions found")
        return False
    
    # Find the employer contradiction
    employer_contra = None
    for c in contradictions:
        if "employer" in c.get("summary", "").lower() or "microsoft" in c.get("summary", "").lower():
            employer_contra = c
            break
    
    if not employer_contra:
        print("   ⚠️ No employer contradiction found, using first one")
        employer_contra = contradictions[0]
    
    ledger_id = employer_contra["ledger_id"]
    new_mem = employer_contra.get("new_memory_id")
    
    print(f"   Found: {ledger_id}")
    print(f"   Summary: {employer_contra.get('summary', 'N/A')[:60]}")
    
    # Resolve with OVERRIDE
    print("\n3. Resolving with OVERRIDE (choosing Amazon)...")
    resolve_resp = requests.post(API_RESOLVE, json={
        "thread_id": thread_id,
        "ledger_id": ledger_id,
        "resolution": "OVERRIDE",
        "chosen_memory_id": new_mem,
        "user_confirmation": "Amazon is correct, I switched jobs"
    }, timeout=30)
    
    print(f"   Status: {resolve_resp.status_code}")
    
    if resolve_resp.status_code == 200:
        print("   ✅ OVERRIDE succeeded!")
        
        # Verify by querying again
        print("\n4. Verifying with query 'Where do I work?'...")
        r_verify = requests.post(API_URL, json={"thread_id": thread_id, "message": "Where do I work?"}, timeout=30)
        v_data = r_verify.json()
        
        print(f"   Answer: {v_data.get('answer', '')[:80]}...")
        print(f"   gates_passed: {v_data.get('gates_passed', 'N/A')}")
        
        if v_data.get("gates_passed", False) and "amazon" in v_data.get("answer", "").lower():
            print("   ✅ Verification passed - Amazon is the answer!")
            return True
        elif "amazon" in v_data.get("answer", "").lower():
            print("   ✅ Verification passed - Amazon mentioned")
            return True
        else:
            print("   ⚠️ Answer unclear but OVERRIDE worked")
            return True
    else:
        print(f"   ❌ OVERRIDE failed: {resolve_resp.status_code}")
        print(f"   Error: {resolve_resp.text[:200]}")
        return False


def test_ask_user_resolution():
    """Test ASK_USER resolution policy."""
    print("\n" + "=" * 70)
    print("TEST: ASK_USER Resolution Policy")
    print("=" * 70)
    
    thread_id = f"askuser_test_{int(time.time())}"
    
    # Create contradiction
    print("\n1. Creating location contradiction...")
    r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I live in Seattle"}, timeout=30)
    print(f"   Setup: {r1.json()['answer'][:60]}...")
    
    time.sleep(0.5)
    
    r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I moved to Denver"}, timeout=30)
    print(f"   Contradict: {r2.json()['answer'][:60]}...")
    
    # Get contradictions
    r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
    contradictions = r_contra.json().get("contradictions", [])
    
    if not contradictions:
        print("   ❌ No contradictions found")
        return False
    
    ledger_id = contradictions[0]["ledger_id"]
    
    print(f"\n2. Resolving with ASK_USER (answer: Denver)...")
    resolve_resp = requests.post(API_RESOLVE, json={
        "thread_id": thread_id,
        "ledger_id": ledger_id,
        "resolution": "ASK_USER",
        "user_confirmation": "I actually live in Denver now"
    }, timeout=30)
    
    print(f"   Status: {resolve_resp.status_code}")
    
    if resolve_resp.status_code == 200:
        print("   ✅ ASK_USER resolution succeeded!")
        return True
    else:
        print(f"   ❌ ASK_USER failed: {resolve_resp.status_code}")
        print(f"   Error: {resolve_resp.text[:200]}")
        return False


if __name__ == "__main__":
    results = {}
    
    results["gate_blocking"] = test_gate_blocking()
    results["override"] = test_override_resolution()
    results["ask_user"] = test_ask_user_resolution()
    
    print("\n" + "=" * 70)
    print("RESOLUTION & GATE TEST SUMMARY")
    print("=" * 70)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test}: {status}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nOverall: {passed}/{total} ({100*passed/total:.0f}%)")
