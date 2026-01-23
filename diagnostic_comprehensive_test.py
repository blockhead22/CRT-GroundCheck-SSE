"""Comprehensive Final Test - All Systems"""
import requests
import json
import time
import sqlite3
import glob
from pathlib import Path

API_URL = "http://127.0.0.1:8123/api/chat/send"
API_CONTRA = "http://127.0.0.1:8123/api/contradictions"
API_RESOLVE = "http://127.0.0.1:8123/api/resolve_contradiction"

def wait_and_test():
    """Wait for server and run all tests."""
    # Check server is up
    for i in range(5):
        try:
            r = requests.get("http://127.0.0.1:8123/health", timeout=5)
            if r.status_code == 200:
                break
        except:
            time.sleep(1)
    
    timestamp = int(time.time())
    results = {
        "detection": {},
        "gate_blocking": {},
        "resolution": {}
    }
    
    print("=" * 70)
    print("COMPREHENSIVE FINAL TEST - ALL SYSTEMS")
    print("=" * 70)
    
    # =============================================
    # TEST 1: DETECTION (5 slot types)
    # =============================================
    print("\n\n" + "="*70)
    print("PART 1: CONTRADICTION DETECTION (5 slots)")
    print("="*70)
    
    detection_tests = [
        ("employer", "I work at Microsoft", "I work at Amazon"),
        ("location", "I live in Seattle", "I live in Denver"),
        ("name", "My name is Nick", "My name is Ben"),
        ("age", "I am 25 years old", "I am 30 years old"),
        ("preference", "I prefer working remotely", "I prefer the office"),
    ]
    
    for slot, stmt1, stmt2 in detection_tests:
        thread_id = f"detect_{slot}_{timestamp}"
        
        r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": stmt1}, timeout=30)
        time.sleep(0.3)
        r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": stmt2}, timeout=30)
        
        data = r2.json()
        detected = data.get("contradiction_detected") or data.get("metadata", {}).get("contradiction_detected", False)
        
        results["detection"][slot] = detected
        status = "✅" if detected else "❌"
        print(f"  {slot}: {status}")
    
    detection_passed = sum(1 for v in results["detection"].values() if v)
    print(f"\n  Detection Rate: {detection_passed}/5 ({100*detection_passed/5:.0f}%)")
    
    # =============================================
    # TEST 2: GATE BLOCKING (4 queries)
    # =============================================
    print("\n\n" + "="*70)
    print("PART 2: GATE BLOCKING (4 test cases)")
    print("="*70)
    
    gate_tests = [
        ("employer_gate", "I work at Microsoft", "I work at Amazon", "Where do I work?"),
        ("location_gate", "I live in Seattle", "I live in Denver", "Where do I live?"),
        ("age_gate", "I am 25 years old", "I am 30 years old", "How old am I?"),
        ("name_gate", "My name is Nick", "My name is Ben", "What is my name?"),
    ]
    
    for test_name, stmt1, stmt2, query in gate_tests:
        thread_id = f"gate_{test_name}_{timestamp}"
        
        requests.post(API_URL, json={"thread_id": thread_id, "message": stmt1}, timeout=30)
        time.sleep(0.3)
        requests.post(API_URL, json={"thread_id": thread_id, "message": stmt2}, timeout=30)
        time.sleep(0.3)
        
        r_query = requests.post(API_URL, json={"thread_id": thread_id, "message": query}, timeout=30)
        data = r_query.json()
        
        gates_passed = data.get("gates_passed", True)
        answer = data.get("answer", "").lower()
        
        # Gate is blocked if gates_passed=False OR answer mentions conflict
        blocked = not gates_passed or "conflicting" in answer or "which" in answer
        
        results["gate_blocking"][test_name] = blocked
        status = "✅" if blocked else "❌"
        print(f"  {test_name}: {status} (gates_passed={gates_passed})")
    
    gate_passed = sum(1 for v in results["gate_blocking"].values() if v)
    print(f"\n  Gate Blocking Rate: {gate_passed}/4 ({100*gate_passed/4:.0f}%)")
    
    # =============================================
    # TEST 3: RESOLUTION POLICIES (3 types)
    # =============================================
    print("\n\n" + "="*70)
    print("PART 3: RESOLUTION POLICIES (3 types)")
    print("="*70)
    
    # Test OVERRIDE
    thread_id = f"resolve_override_{timestamp}"
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Microsoft"}, timeout=30)
    time.sleep(0.3)
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Amazon"}, timeout=30)
    
    r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
    contradictions = r_contra.json().get("contradictions", [])
    
    if contradictions:
        ledger_id = contradictions[0]["ledger_id"]
        new_mem = contradictions[0].get("new_memory_id")
        
        r_resolve = requests.post(API_RESOLVE, json={
            "thread_id": thread_id,
            "ledger_id": ledger_id,
            "resolution": "OVERRIDE",
            "chosen_memory_id": new_mem,
            "user_confirmation": "Amazon is correct"
        }, timeout=30)
        
        results["resolution"]["OVERRIDE"] = r_resolve.status_code == 200
    else:
        results["resolution"]["OVERRIDE"] = False
    
    status = "✅" if results["resolution"]["OVERRIDE"] else "❌"
    print(f"  OVERRIDE: {status}")
    
    # Test PRESERVE
    thread_id = f"resolve_preserve_{timestamp}"
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I like Python programming"}, timeout=30)
    time.sleep(0.3)
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I also like JavaScript"}, timeout=30)
    
    r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
    contradictions = r_contra.json().get("contradictions", [])
    
    if contradictions:
        ledger_id = contradictions[0]["ledger_id"]
        r_resolve = requests.post(API_RESOLVE, json={
            "thread_id": thread_id,
            "ledger_id": ledger_id,
            "resolution": "PRESERVE",
            "user_confirmation": "Both are true"
        }, timeout=30)
        results["resolution"]["PRESERVE"] = r_resolve.status_code == 200
    else:
        # No contradiction is fine for this case (programming languages are additive)
        results["resolution"]["PRESERVE"] = True
    
    status = "✅" if results["resolution"]["PRESERVE"] else "❌"
    print(f"  PRESERVE: {status}")
    
    # Test ASK_USER
    thread_id = f"resolve_askuser_{timestamp}"
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I live in Seattle"}, timeout=30)
    time.sleep(0.3)
    requests.post(API_URL, json={"thread_id": thread_id, "message": "I live in Denver"}, timeout=30)
    
    r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
    contradictions = r_contra.json().get("contradictions", [])
    
    if contradictions:
        ledger_id = contradictions[0]["ledger_id"]
        r_resolve = requests.post(API_RESOLVE, json={
            "thread_id": thread_id,
            "ledger_id": ledger_id,
            "resolution": "ASK_USER",
            "user_confirmation": "Denver is correct now"
        }, timeout=30)
        results["resolution"]["ASK_USER"] = r_resolve.status_code == 200
    else:
        results["resolution"]["ASK_USER"] = False
    
    status = "✅" if results["resolution"]["ASK_USER"] else "❌"
    print(f"  ASK_USER: {status}")
    
    resolution_passed = sum(1 for v in results["resolution"].values() if v)
    print(f"\n  Resolution Rate: {resolution_passed}/3 ({100*resolution_passed/3:.0f}%)")
    
    # =============================================
    # SUMMARY
    # =============================================
    print("\n\n" + "="*70)
    print("COMPREHENSIVE TEST SUMMARY")
    print("="*70)
    
    total_detection = 5
    total_gate = 4
    total_resolution = 3
    
    det_pass = sum(1 for v in results["detection"].values() if v)
    gate_pass = sum(1 for v in results["gate_blocking"].values() if v)
    res_pass = sum(1 for v in results["resolution"].values() if v)
    
    overall = det_pass + gate_pass + res_pass
    total = total_detection + total_gate + total_resolution
    
    print(f"\n  Detection:   {det_pass}/{total_detection} ({100*det_pass/total_detection:.0f}%)")
    print(f"  Gate Block:  {gate_pass}/{total_gate} ({100*gate_pass/total_gate:.0f}%)")
    print(f"  Resolution:  {res_pass}/{total_resolution} ({100*res_pass/total_resolution:.0f}%)")
    print(f"\n  OVERALL:     {overall}/{total} ({100*overall/total:.0f}%)")
    
    if overall == total:
        print("\n  🎉 ALL TESTS PASSED!")
    elif overall >= total * 0.8:
        print("\n  ✅ SYSTEM READY (>80%)")
    else:
        print("\n  ⚠️ NEEDS WORK")
    
    return results


if __name__ == "__main__":
    results = wait_and_test()
    
    # Save results
    with open("COMPREHENSIVE_TEST_RESULTS.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n\nResults saved to COMPREHENSIVE_TEST_RESULTS.json")
