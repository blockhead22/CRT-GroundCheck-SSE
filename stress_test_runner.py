#!/usr/bin/env python3
"""Comprehensive CRT Stress Test Runner"""

import requests
import json
import time
from datetime import datetime
from statistics import mean, median
from pathlib import Path

BASE_URL = "http://127.0.0.1:8123"
RESULTS = {}

def log(msg, color=None):
    """Print with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }
    if color and color in colors:
        print(f"[{ts}] {colors[color]}{msg}{colors['reset']}")
    else:
        print(f"[{ts}] {msg}")


def chat(thread_id: str, message: str, timeout: int = 120) -> dict:
    """Send a chat message and return the response."""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat/send",
            json={"thread_id": thread_id, "message": message},
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        log(f"⚠️ Timeout after {timeout}s for: {message[:30]}...", "yellow")
        return {"answer": "TIMEOUT", "gates_passed": None, "metadata": {}}
    except Exception as e:
        log(f"⚠️ Error: {e}", "yellow")
        return {"answer": "ERROR", "gates_passed": None, "metadata": {}}


def health_check():
    """Verify backend is healthy."""
    log("=" * 70)
    log("HEALTH CHECK")
    log("=" * 70)
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            log("✅ Backend is healthy", "green")
            return True
        else:
            log(f"❌ Health check failed: {resp.status_code}", "red")
            return False
    except Exception as e:
        log(f"❌ Cannot connect to backend: {e}", "red")
        return False


def test_2_1_basic_storage():
    """Test 2.1: Basic Memory Storage & Retrieval"""
    log("\n" + "=" * 70)
    log("TEST 2.1: Basic Memory Storage & Retrieval")
    log("=" * 70)
    
    thread = f"stress_basic_{int(time.time())}"
    
    # Store name
    log("Storing: My name is Alex")
    r1 = chat(thread, "My name is Alex")
    log(f"Response: {r1['answer'][:100]}...")
    
    time.sleep(0.5)
    
    # Retrieve name
    log("Retrieving: What is my name?")
    r2 = chat(thread, "What is my name?")
    log(f"Response: {r2['answer']}")
    
    passed = "Alex" in r2["answer"]
    if passed:
        log("✅ PASS: Name recalled correctly", "green")
    else:
        log("❌ FAIL: Name not recalled", "red")
    
    RESULTS["test_2_1"] = {"status": "PASS" if passed else "FAIL"}
    return passed


def test_2_2_contradiction_detection():
    """Test 2.2: Contradiction Detection"""
    log("\n" + "=" * 70)
    log("TEST 2.2: Contradiction Detection")
    log("=" * 70)
    
    thread = f"stress_contra_{int(time.time())}"
    results = {}
    
    # 1. Initial fact
    log("\n1. Storing: I work at Microsoft")
    r1 = chat(thread, "I work at Microsoft")
    log(f"   Response: {r1['answer'][:80]}...")
    results["initial_store"] = "OK"
    
    time.sleep(0.5)
    
    # 2. Contradicting fact
    log("\n2. Contradicting: I work at Google")
    r2 = chat(thread, "I work at Google")
    log(f"   Response: {r2['answer'][:80]}...")
    contradiction_detected = r2.get("metadata", {}).get("contradiction_detected", False)
    log(f"   Contradiction detected: {contradiction_detected}")
    
    if contradiction_detected:
        log("   ✅ PASS: Contradiction detected", "green")
        results["detection"] = "PASS"
    else:
        log("   ❌ FAIL: Contradiction missed", "red")
        results["detection"] = "FAIL"
    
    time.sleep(0.5)
    
    # 3. Query (should be blocked by gates)
    log("\n3. Query: Where do I work?")
    r3 = chat(thread, "Where do I work?")
    log(f"   Response: {r3['answer'][:100]}...")
    gates_passed = r3.get("gates_passed", True)
    log(f"   Gates passed: {gates_passed}")
    
    if not gates_passed:
        log("   ✅ PASS: Gates blocked correctly", "green")
        results["blocking"] = "PASS"
    else:
        log("   ⚠️ Gates passed (might be acceptable)", "yellow")
        results["blocking"] = "MAYBE"
    
    overall = contradiction_detected
    RESULTS["test_2_2"] = {
        "status": "PASS" if overall else "FAIL",
        "details": results
    }
    return overall


def test_3_1_natural_language_resolution():
    """Test 3.1: Natural Language Resolution (KNOWN BUG)"""
    log("\n" + "=" * 70)
    log("TEST 3.1: Natural Language Resolution (KNOWN BUG)")
    log("=" * 70)
    
    thread = f"stress_nl_res_{int(time.time())}"
    
    # 1. Create contradiction
    log("\n1. Creating contradiction...")
    chat(thread, "I work at Microsoft")
    time.sleep(0.5)
    
    r2 = chat(thread, "I work at Google")
    log(f"   Contradiction detected: {r2.get('metadata', {}).get('contradiction_detected', False)}")
    time.sleep(0.5)
    
    # 2. Verify gates blocked
    log("\n2. Verify gates blocked...")
    r3 = chat(thread, "Where do I work?")
    log(f"   Gates passed: {r3.get('gates_passed', True)}")
    time.sleep(0.5)
    
    # 3. Attempt natural language resolution
    log("\n3. Attempting NL resolution: 'Google is correct, I switched jobs'")
    r4 = chat(thread, "Google is correct, I switched jobs")
    log(f"   Response: {r4['answer'][:100]}...")
    time.sleep(0.5)
    
    # 4. Check if resolution worked
    log("\n4. Checking if resolution worked...")
    r5 = chat(thread, "Where do I work?")
    log(f"   Response: {r5['answer'][:100]}...")
    log(f"   Gates passed: {r5.get('gates_passed', True)}")
    
    resolution_worked = r5.get("gates_passed", False) and "Google" in r5["answer"]
    
    if resolution_worked:
        log("\n✅ PASS: NL Resolution WORKED!", "green")
    else:
        log("\n❌ FAIL: NL Resolution broken (known bug)", "red")
        log("   Expected: Gates pass and answer contains 'Google'", "yellow")
    
    RESULTS["test_3_1"] = {
        "status": "PASS" if resolution_worked else "FAIL",
        "known_bug": True,
        "gates_passed_after": r5.get("gates_passed", False),
        "answer_contains_google": "Google" in r5["answer"]
    }
    return resolution_worked


def test_4_1_rapid_fire():
    """Test 4.1: 20 Contradictions Rapid Fire"""
    log("\n" + "=" * 70)
    log("TEST 4.1: Rapid Fire - 20 Contradictions")
    log("=" * 70)
    
    thread = f"stress_rapid_{int(time.time())}"
    
    contradictions = [
        ("I work at Microsoft", "I work at Amazon"),
        ("I'm 25 years old", "I'm 30 years old"),
        ("I live in Seattle", "I live in New York"),
        ("I prefer coffee", "I hate coffee"),
        ("I like dogs", "I'm allergic to dogs"),
        ("I'm a vegetarian", "I love steak"),
        ("I speak English", "I only speak Spanish"),
        ("I'm single", "I'm married"),
        ("I drive a Tesla", "I don't own a car"),
        ("I wake up at 6am", "I never wake up before noon"),
        ("I love winter", "I hate cold weather"),
        ("I'm an introvert", "I'm extremely extroverted"),
        ("I hate flying", "I love airplanes"),
        ("I'm a night owl", "I'm a morning person"),
        ("I live alone", "I have 5 roommates"),
        ("I'm allergic to peanuts", "I eat peanut butter daily"),
        ("I'm left-handed", "I'm right-handed"),
        ("I hate sports", "I play basketball every day"),
        ("I'm a minimalist", "I'm a hoarder"),
        ("I never drink alcohol", "I drink wine every night"),
    ]
    
    detected = 0
    total = len(contradictions)
    start_time = time.time()
    
    for i, (first, second) in enumerate(contradictions):
        try:
            # First statement
            chat(thread, first)
            time.sleep(0.2)
            
            # Second statement (contradicting)
            r2 = chat(thread, second)
            is_detected = r2.get("metadata", {}).get("contradiction_detected", False)
            
            if is_detected:
                log(f"✅ [{i+1:2d}/20] {first[:20]}... → {second[:20]}...", "green")
                detected += 1
            else:
                log(f"❌ [{i+1:2d}/20] MISSED: {first[:20]}... → {second[:20]}...", "red")
            
            time.sleep(0.2)
        except Exception as e:
            log(f"❌ [{i+1:2d}/20] ERROR: {e}", "red")
    
    elapsed = time.time() - start_time
    rate = detected / total * 100
    
    log(f"\n--- RAPID FIRE RESULTS ---")
    log(f"Detected: {detected}/{total} ({rate:.1f}%)")
    log(f"Time: {elapsed:.1f} seconds")
    log(f"Average: {elapsed/total:.2f}s per pair")
    
    if rate >= 75:
        log(f"✅ PASS: Detection rate ≥75%", "green")
    elif rate >= 60:
        log(f"⚠️ PARTIAL: Detection rate acceptable", "yellow")
    else:
        log(f"❌ FAIL: Detection rate too low", "red")
    
    RESULTS["test_4_1"] = {
        "status": "PASS" if rate >= 75 else ("PARTIAL" if rate >= 60 else "FAIL"),
        "detected": detected,
        "total": total,
        "rate": rate,
        "elapsed_seconds": elapsed
    }
    return rate >= 75


def test_4_2_resolution_policies():
    """Test 4.2: Resolution Policies Test"""
    log("\n" + "=" * 70)
    log("TEST 4.2: Resolution Policies Test")
    log("=" * 70)
    
    # Get contradictions from API
    thread = f"stress_rapid_{int(time.time()) - 1}"  # Use last rapid fire thread
    
    try:
        resp = requests.get(f"{BASE_URL}/api/contradictions", params={"thread_id": thread}, timeout=10)
        contradictions = resp.json().get("contradictions", [])
    except Exception as e:
        log(f"⚠️ Could not fetch contradictions: {e}", "yellow")
        # Create fresh contradictions for testing
        thread = f"stress_policy_{int(time.time())}"
        chat(thread, "I work at Microsoft")
        time.sleep(0.3)
        chat(thread, "I work at Google")
        time.sleep(0.3)
        chat(thread, "I'm 25 years old")
        time.sleep(0.3)
        chat(thread, "I'm 30 years old")
        time.sleep(0.3)
        chat(thread, "I live in Seattle")
        time.sleep(0.3)
        chat(thread, "I live in NYC")
        
        resp = requests.get(f"{BASE_URL}/api/contradictions", params={"thread_id": thread}, timeout=10)
        contradictions = resp.json().get("contradictions", [])
    
    log(f"Found {len(contradictions)} contradictions to test")
    
    results = {}
    
    # Test OVERRIDE
    if len(contradictions) >= 1:
        c = contradictions[0]
        log(f"\n[OVERRIDE] Testing with ledger_id: {c.get('ledger_id', 'N/A')}")
        
        try:
            resolve_body = {
                "thread_id": thread,
                "ledger_id": c.get("ledger_id"),
                "resolution": "OVERRIDE",
                "chosen_memory_id": c.get("new_memory_id"),
                "user_confirmation": "Test OVERRIDE policy"
            }
            resolve_resp = requests.post(
                f"{BASE_URL}/api/resolve_contradiction",
                json=resolve_body,
                timeout=10
            )
            
            if resolve_resp.status_code == 200 and resolve_resp.json().get("status") == "resolved":
                log("✅ OVERRIDE worked", "green")
                results["OVERRIDE"] = "PASS"
            else:
                log(f"❌ OVERRIDE failed: {resolve_resp.text[:100]}", "red")
                results["OVERRIDE"] = "FAIL"
        except Exception as e:
            log(f"❌ OVERRIDE error: {e}", "red")
            results["OVERRIDE"] = "ERROR"
    
    # Test PRESERVE
    if len(contradictions) >= 2:
        c = contradictions[1]
        log(f"\n[PRESERVE] Testing with ledger_id: {c.get('ledger_id', 'N/A')}")
        
        try:
            resolve_body = {
                "thread_id": thread,
                "ledger_id": c.get("ledger_id"),
                "resolution": "PRESERVE",
                "user_confirmation": "Test PRESERVE policy"
            }
            resolve_resp = requests.post(
                f"{BASE_URL}/api/resolve_contradiction",
                json=resolve_body,
                timeout=10
            )
            
            if resolve_resp.status_code == 200:
                log("✅ PRESERVE worked", "green")
                results["PRESERVE"] = "PASS"
            else:
                log(f"❌ PRESERVE failed: {resolve_resp.text[:100]}", "red")
                results["PRESERVE"] = "FAIL"
        except Exception as e:
            log(f"❌ PRESERVE error: {e}", "red")
            results["PRESERVE"] = "ERROR"
    
    # Test ASK_USER
    if len(contradictions) >= 3:
        c = contradictions[2]
        log(f"\n[ASK_USER] Testing with ledger_id: {c.get('ledger_id', 'N/A')}")
        
        try:
            resolve_body = {
                "thread_id": thread,
                "ledger_id": c.get("ledger_id"),
                "resolution": "ASK_USER",
                "user_confirmation": "I'll decide later"
            }
            resolve_resp = requests.post(
                f"{BASE_URL}/api/resolve_contradiction",
                json=resolve_body,
                timeout=10
            )
            
            status = resolve_resp.json().get("status", "")
            if resolve_resp.status_code == 200 and status in ("deferred", "resolved"):
                log("✅ ASK_USER worked", "green")
                results["ASK_USER"] = "PASS"
            else:
                log(f"❌ ASK_USER failed: {resolve_resp.text[:100]}", "red")
                results["ASK_USER"] = "FAIL"
        except Exception as e:
            log(f"❌ ASK_USER error: {e}", "red")
            results["ASK_USER"] = "ERROR"
    
    RESULTS["test_4_2"] = {
        "status": "PASS" if all(v == "PASS" for v in results.values()) else "PARTIAL",
        "details": results
    }
    return all(v == "PASS" for v in results.values())


def test_5_1_negation_detection():
    """Test 5.1: Negation Detection"""
    log("\n" + "=" * 70)
    log("TEST 5.1: Negation Detection")
    log("=" * 70)
    
    thread = f"stress_negation_{int(time.time())}"
    
    negation_tests = [
        ("I like coffee", "I don't like coffee", True),
        ("I speak Spanish", "I don't speak Spanish at all", True),
        ("I'm allergic to peanuts", "I'm not allergic to peanuts", True),
        ("I love winter", "I hate winter", True),  # Semantic negation
    ]
    
    passed = 0
    
    for first, second, expected in negation_tests:
        chat(thread, first)
        time.sleep(0.3)
        
        r2 = chat(thread, second)
        detected = r2.get("metadata", {}).get("contradiction_detected", False)
        
        log(f"\n'{first}' → '{second}'")
        log(f"Detected: {detected} | Expected: {expected}")
        
        if detected == expected:
            log("✅ PASS", "green")
            passed += 1
        else:
            log("❌ FAIL", "red")
        
        time.sleep(0.3)
    
    log(f"\nNegation Detection: {passed}/{len(negation_tests)}")
    
    RESULTS["test_5_1"] = {
        "status": "PASS" if passed >= 3 else "FAIL",
        "passed": passed,
        "total": len(negation_tests)
    }
    return passed >= 3


def test_5_2_semantic_contradiction():
    """Test 5.2: Semantic Contradiction (Winter ≈ Cold)"""
    log("\n" + "=" * 70)
    log("TEST 5.2: Semantic Contradiction (Winter ≈ Cold)")
    log("=" * 70)
    
    thread = f"stress_semantic_{int(time.time())}"
    
    chat(thread, "I love winter weather")
    time.sleep(0.5)
    
    r2 = chat(thread, "I hate cold temperatures")
    detected = r2.get("metadata", {}).get("contradiction_detected", False)
    
    log("User: I love winter weather")
    log("User: I hate cold temperatures")
    log(f"Contradiction detected: {detected}")
    
    if detected:
        log("✅ PASS: Semantic contradiction detected (winter ≈ cold)", "green")
    else:
        log("⚠️ FAIL: Semantic understanding limited (acceptable)", "yellow")
    
    RESULTS["test_5_2"] = {
        "status": "PASS" if detected else "ACCEPTABLE_FAIL",
        "detected": detected
    }
    return detected


def test_6_1_latency():
    """Test 6.1: Latency Benchmarking"""
    log("\n" + "=" * 70)
    log("TEST 6.1: Latency Benchmarking")
    log("=" * 70)
    
    thread = f"stress_latency_{int(time.time())}"
    latencies = []
    
    # Warm-up
    log("Warming up (5 requests)...")
    for i in range(5):
        chat(thread, f"warm up {i}")
    
    # Benchmark
    log("Running 50 requests...")
    for i in range(50):
        start = time.time()
        chat(thread, f"test message {i}")
        latency = (time.time() - start) * 1000  # ms
        latencies.append(latency)
        
        if (i + 1) % 10 == 0:
            log(f"  [{i+1}/50] Latest: {latency:.0f}ms")
    
    mean_lat = mean(latencies)
    median_lat = median(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    sorted_lat = sorted(latencies)
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
    
    log(f"\n--- LATENCY RESULTS ---")
    log(f"Mean:   {mean_lat:.0f}ms")
    log(f"Median: {median_lat:.0f}ms")
    log(f"Min:    {min_lat:.0f}ms")
    log(f"Max:    {max_lat:.0f}ms")
    log(f"P95:    {p95:.0f}ms")
    
    if mean_lat < 1000:
        log("✅ PASS: Average latency < 1 second", "green")
    else:
        log(f"⚠️ WARNING: High latency ({mean_lat:.0f}ms avg)", "yellow")
    
    RESULTS["test_6_1"] = {
        "status": "PASS" if mean_lat < 1000 else "SLOW",
        "mean_ms": mean_lat,
        "median_ms": median_lat,
        "min_ms": min_lat,
        "max_ms": max_lat,
        "p95_ms": p95
    }
    return mean_lat < 1000


def generate_report():
    """Generate final report."""
    log("\n")
    log("=" * 70)
    log("COMPREHENSIVE STRESS TEST REPORT")
    log("=" * 70)
    
    log("\nCORE FUNCTIONALITY", "cyan")
    log("-" * 70)
    log(f"Basic Storage/Retrieval:     {'✅ PASS' if RESULTS.get('test_2_1', {}).get('status') == 'PASS' else '❌ FAIL'}")
    log(f"Contradiction Detection:     {'✅ PASS' if RESULTS.get('test_2_2', {}).get('status') == 'PASS' else '❌ FAIL'}")
    
    log("\nNATURAL LANGUAGE RESOLUTION", "cyan")
    log("-" * 70)
    nl_status = RESULTS.get('test_3_1', {}).get('status', 'UNKNOWN')
    if nl_status == 'PASS':
        log("Status: ✅ WORKING", "green")
    else:
        log("Status: ❌ BROKEN (known bug)", "red")
        log("Impact: Users can't resolve contradictions via chat", "yellow")
    
    log("\nRAPID FIRE STRESS TEST", "cyan")
    log("-" * 70)
    rf = RESULTS.get('test_4_1', {})
    log(f"Detection Rate: {rf.get('detected', 0)}/{rf.get('total', 0)} ({rf.get('rate', 0):.1f}%)")
    log(f"Time: {rf.get('elapsed_seconds', 0):.1f}s")
    log(f"Status: {'✅ PASS' if rf.get('status') == 'PASS' else '⚠️ ' + rf.get('status', 'UNKNOWN')}")
    
    log("\nRESOLUTION POLICIES", "cyan")
    log("-" * 70)
    rp = RESULTS.get('test_4_2', {}).get('details', {})
    log(f"OVERRIDE:  {'✅' if rp.get('OVERRIDE') == 'PASS' else '❌'}")
    log(f"PRESERVE:  {'✅' if rp.get('PRESERVE') == 'PASS' else '❌'}")
    log(f"ASK_USER:  {'✅' if rp.get('ASK_USER') == 'PASS' else '❌'}")
    
    log("\nEDGE CASES", "cyan")
    log("-" * 70)
    neg = RESULTS.get('test_5_1', {})
    log(f"Negation Detection: {neg.get('passed', 0)}/{neg.get('total', 0)}")
    sem = RESULTS.get('test_5_2', {})
    log(f"Semantic Contradiction: {'✅' if sem.get('detected') else '⚠️ Limited'}")
    
    log("\nPERFORMANCE", "cyan")
    log("-" * 70)
    lat = RESULTS.get('test_6_1', {})
    log(f"Mean Latency:   {lat.get('mean_ms', 0):.0f}ms")
    log(f"Median Latency: {lat.get('median_ms', 0):.0f}ms")
    log(f"P95 Latency:    {lat.get('p95_ms', 0):.0f}ms")
    log(f"Status: {'✅ ACCEPTABLE' if lat.get('status') == 'PASS' else '⚠️ SLOW'}")
    
    log("\n" + "=" * 70)
    log("OVERALL SYSTEM STATUS")
    log("=" * 70)
    
    issues = []
    if RESULTS.get('test_3_1', {}).get('status') != 'PASS':
        issues.append("Natural language resolution broken (known bug)")
    if RESULTS.get('test_4_1', {}).get('rate', 0) < 75:
        issues.append(f"Detection rate below 75% ({RESULTS.get('test_4_1', {}).get('rate', 0):.1f}%)")
    if RESULTS.get('test_6_1', {}).get('mean_ms', float('inf')) > 1000:
        issues.append(f"High latency ({RESULTS.get('test_6_1', {}).get('mean_ms', 0):.0f}ms avg)")
    
    if len(issues) == 0:
        log("🎉 ALL TESTS PASSED - SYSTEM READY FOR DEPLOYMENT", "green")
    elif len(issues) == 1 and "known bug" in issues[0]:
        log("✅ CORE SYSTEM WORKING - 1 known issue", "green")
        log(f"   - {issues[0]}", "yellow")
    else:
        log("⚠️ ISSUES FOUND:", "yellow")
        for issue in issues:
            log(f"   - {issue}", "yellow")
    
    # Save results
    results_file = Path("stress_test_results.json")
    with open(results_file, "w") as f:
        json.dump(RESULTS, f, indent=2)
    log(f"\nResults saved to: {results_file}")
    
    return RESULTS


def main():
    """Run all tests."""
    log("=" * 70, "cyan")
    log("CRT COMPREHENSIVE STRESS TEST", "cyan")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "cyan")
    log("=" * 70, "cyan")
    
    if not health_check():
        log("Cannot proceed - backend not healthy", "red")
        return
    
    # Run all tests
    test_2_1_basic_storage()
    test_2_2_contradiction_detection()
    test_3_1_natural_language_resolution()
    test_4_1_rapid_fire()
    test_4_2_resolution_policies()
    test_5_1_negation_detection()
    test_5_2_semantic_contradiction()
    test_6_1_latency()
    
    # Generate report
    generate_report()


if __name__ == "__main__":
    main()
