#!/usr/bin/env python3
"""Quick targeted stress test"""

import requests
import time
import json

BASE_URL = "http://127.0.0.1:8123"

def chat(thread_id, message, timeout=120):
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat/send", 
            json={"thread_id": thread_id, "message": message}, 
            timeout=timeout
        )
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"   ⚠️ TIMEOUT after {timeout}s")
        return {"answer": "TIMEOUT", "gates_passed": None, "metadata": {}}
    except Exception as e:
        print(f"   ⚠️ ERROR: {e}")
        return {"answer": f"ERROR: {e}", "gates_passed": None, "metadata": {}}

def shorten(text, maxlen=80):
    if len(text) > maxlen:
        return text[:maxlen] + "..."
    return text

def run_tests():
    results = {}
    
    # =====================================================
    # TEST 2.2: Contradiction Detection
    # =====================================================
    print("=" * 60)
    print("TEST 2.2: Contradiction Detection")
    print("=" * 60)
    
    thread = f"contra_test_{int(time.time())}"
    
    print("\n1. Storing: I work at Microsoft")
    r1 = chat(thread, "I work at Microsoft")
    print(f"   Response: {shorten(r1['answer'])}")
    time.sleep(0.5)
    
    print("\n2. Contradicting: I work at Google")
    r2 = chat(thread, "I work at Google")
    print(f"   Response: {shorten(r2['answer'])}")
    detected = r2.get("metadata", {}).get("contradiction_detected", False)
    print(f"   Contradiction detected: {detected}")
    if detected:
        print("   ✅ PASS: Contradiction detected")
        results["contradiction_detection"] = "PASS"
    else:
        print("   ❌ FAIL: Contradiction missed")
        results["contradiction_detection"] = "FAIL"
    time.sleep(0.5)
    
    print("\n3. Query: Where do I work?")
    r3 = chat(thread, "Where do I work?")
    print(f"   Response: {shorten(r3['answer'], 100)}")
    gates = r3.get("gates_passed", True)
    print(f"   Gates passed: {gates}")
    if not gates:
        print("   ✅ PASS: Gates blocked")
        results["gates_blocking"] = "PASS"
    else:
        print("   ⚠️ Gates passed")
        results["gates_blocking"] = "MAYBE"
    
    # =====================================================
    # TEST 3.1: Natural Language Resolution
    # =====================================================
    print("\n" + "=" * 60)
    print("TEST 3.1: Natural Language Resolution (KNOWN BUG)")
    print("=" * 60)
    
    print("\n4. Attempting resolution: 'Google is correct, I switched jobs'")
    r4 = chat(thread, "Google is correct, I switched jobs")
    print(f"   Response: {shorten(r4['answer'], 100)}")
    time.sleep(0.5)
    
    print("\n5. Re-query: Where do I work?")
    r5 = chat(thread, "Where do I work?")
    print(f"   Response: {shorten(r5['answer'], 100)}")
    gates_after = r5.get("gates_passed", False)
    print(f"   Gates passed after resolution: {gates_after}")
    
    resolution_worked = gates_after and "Google" in r5["answer"]
    if resolution_worked:
        print("   ✅ PASS: NL Resolution worked!")
        results["nl_resolution"] = "PASS"
    else:
        print("   ❌ FAIL: NL Resolution broken (known bug)")
        results["nl_resolution"] = "FAIL (known bug)"
    
    # =====================================================
    # TEST 4.1: Quick Rapid Fire (5 contradictions)
    # =====================================================
    print("\n" + "=" * 60)
    print("TEST 4.1: Quick Rapid Fire (5 contradictions)")
    print("=" * 60)
    
    rapid_thread = f"rapid_{int(time.time())}"
    quick_contradictions = [
        ("I'm 25 years old", "I'm 30 years old"),
        ("I live in Seattle", "I live in New York"),
        ("I prefer coffee", "I hate coffee"),
        ("I'm single", "I'm married"),
        ("I'm left-handed", "I'm right-handed"),
    ]
    
    detected_count = 0
    for i, (first, second) in enumerate(quick_contradictions):
        print(f"\n{i+1}. '{first}' → '{second}'")
        chat(rapid_thread, first)
        time.sleep(0.3)
        r = chat(rapid_thread, second)
        is_detected = r.get("metadata", {}).get("contradiction_detected", False)
        if is_detected:
            print("   ✅ Detected")
            detected_count += 1
        else:
            print("   ❌ Missed")
        time.sleep(0.3)
    
    rate = detected_count / len(quick_contradictions) * 100
    print(f"\nRapid Fire: {detected_count}/{len(quick_contradictions)} ({rate:.0f}%)")
    results["rapid_fire"] = f"{detected_count}/{len(quick_contradictions)} ({rate:.0f}%)"
    
    # =====================================================
    # TEST 6.1: Quick Latency (10 requests)
    # =====================================================
    print("\n" + "=" * 60)
    print("TEST 6.1: Quick Latency (10 requests)")
    print("=" * 60)
    
    lat_thread = f"latency_{int(time.time())}"
    latencies = []
    
    for i in range(10):
        start = time.time()
        chat(lat_thread, f"test message {i}")
        lat = (time.time() - start) * 1000
        latencies.append(lat)
        print(f"   Request {i+1}: {lat:.0f}ms")
    
    avg_lat = sum(latencies) / len(latencies)
    print(f"\nAverage latency: {avg_lat:.0f}ms")
    results["avg_latency_ms"] = avg_lat
    
    # =====================================================
    # FINAL SUMMARY
    # =====================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    
    # Save results
    with open("quick_stress_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to: quick_stress_results.json")

if __name__ == "__main__":
    # Quick health check
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            print("✅ Backend healthy")
            run_tests()
        else:
            print(f"❌ Backend unhealthy: {r.status_code}")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
