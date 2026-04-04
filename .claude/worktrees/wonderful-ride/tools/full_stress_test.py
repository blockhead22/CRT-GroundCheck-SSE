#!/usr/bin/env python3
"""
FULL CRT STRESS TEST SUITE
Run this after merging the PR and restarting the API server.

Tests:
1. Basic Memory Storage/Retrieval
2. Contradiction Detection
3. Gates Blocking
4. NL Resolution (6 patterns)
5. API Resolution (OVERRIDE/PRESERVE)
6. Database Integrity
7. Rapid Fire Detection
"""

import requests
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_URL = "http://127.0.0.1:8123"
RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "tests": {},
    "summary": {}
}

def chat(thread_id, message, timeout=120):
    """Send a chat message and return the response."""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat/send",
            json={"thread_id": thread_id, "message": message},
            timeout=timeout
        )
        return resp.json()
    except Exception as e:
        return {"answer": f"ERROR: {e}", "gates_passed": None, "metadata": {}}

def get_contradictions(thread_id):
    """Get contradictions for a thread."""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/contradictions",
            params={"thread_id": thread_id},
            timeout=10
        )
        return resp.json().get("contradictions", [])
    except:
        return []

def resolve_via_api(thread_id, ledger_id, resolution, chosen_memory_id=None):
    """Resolve contradiction via API."""
    try:
        body = {
            "thread_id": thread_id,
            "ledger_id": ledger_id,
            "resolution": resolution,
            "user_confirmation": "test"
        }
        if chosen_memory_id:
            body["chosen_memory_id"] = chosen_memory_id
        resp = requests.post(
            f"{BASE_URL}/api/resolve_contradiction",
            json=body,
            timeout=30
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def health_check():
    """Check if API is running."""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except:
        return False

# ============================================================
# TEST 1: Basic Memory Storage/Retrieval
# ============================================================
def test_basic_memory():
    print("\n" + "="*60)
    print("TEST 1: Basic Memory Storage/Retrieval")
    print("="*60)
    
    thread = f"test_basic_{int(time.time())}"
    
    # Store
    print("  → Storing: My name is TestUser")
    r1 = chat(thread, "My name is TestUser")
    print(f"    Response: {r1.get('answer', '')[:80]}...")
    
    time.sleep(0.5)
    
    # Retrieve
    print("  → Querying: What is my name?")
    r2 = chat(thread, "What is my name?")
    answer = r2.get("answer", "")
    print(f"    Response: {answer[:80]}...")
    
    passed = "testuser" in answer.lower()
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    RESULTS["tests"]["basic_memory"] = {
        "passed": passed,
        "details": {"answer_contains_name": passed}
    }
    return passed

# ============================================================
# TEST 2: Contradiction Detection
# ============================================================
def test_contradiction_detection():
    print("\n" + "="*60)
    print("TEST 2: Contradiction Detection")
    print("="*60)
    
    thread = f"test_detection_{int(time.time())}"
    
    # First fact
    print("  → Storing: I work at Microsoft")
    chat(thread, "I work at Microsoft")
    time.sleep(0.5)
    
    # Contradicting fact
    print("  → Contradicting: I work at Google")
    r = chat(thread, "I work at Google")
    detected = r.get("metadata", {}).get("contradiction_detected", False)
    print(f"    Contradiction detected: {detected}")
    
    # Check ledger
    contras = get_contradictions(thread)
    print(f"    Contradictions in ledger: {len(contras)}")
    
    passed = detected or len(contras) > 0
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    RESULTS["tests"]["contradiction_detection"] = {
        "passed": passed,
        "details": {
            "metadata_detected": detected,
            "ledger_count": len(contras)
        }
    }
    return passed

# ============================================================
# TEST 3: Gates Blocking
# ============================================================
def test_gates_blocking():
    print("\n" + "="*60)
    print("TEST 3: Gates Blocking")
    print("="*60)
    
    thread = f"test_gates_{int(time.time())}"
    
    # Create contradiction
    print("  → Creating contradiction: Microsoft vs Google")
    chat(thread, "I work at Microsoft")
    time.sleep(0.5)
    chat(thread, "I work at Google")
    time.sleep(0.5)
    
    # Query - should block
    print("  → Querying: Where do I work?")
    r = chat(thread, "Where do I work?")
    gates_passed = r.get("gates_passed", True)
    answer = r.get("answer", "")
    print(f"    Gates passed: {gates_passed}")
    print(f"    Answer: {answer[:100]}...")
    
    # Gates should NOT pass when contradiction exists
    passed = gates_passed == False
    
    # Alternative pass condition: answer mentions conflict
    if not passed:
        conflict_mentioned = any(word in answer.lower() for word in ["conflict", "contradicting", "unclear", "both", "microsoft", "google"])
        if conflict_mentioned and "microsoft" in answer.lower() and "google" in answer.lower():
            print("    (Alternative: Answer mentions both conflicting values)")
            passed = True
    
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    RESULTS["tests"]["gates_blocking"] = {
        "passed": passed,
        "details": {
            "gates_passed": gates_passed,
            "expected": False
        }
    }
    return passed, thread  # Return thread for NL resolution test

# ============================================================
# TEST 4: NL Resolution (6 patterns)
# ============================================================
def test_nl_resolution():
    print("\n" + "="*60)
    print("TEST 4: NL Resolution (6 patterns)")
    print("="*60)
    
    patterns = [
        {
            "name": "X is correct",
            "setup": ["I work at Microsoft"],
            "contradiction": "I work at Google",
            "resolution": "Google is correct, I switched jobs",
            "expected": "google"
        },
        {
            "name": "Actually...",
            "setup": ["I live in Seattle"],
            "contradiction": "I live in Austin",
            "resolution": "Actually, I moved to Austin last month",
            "expected": "austin"
        },
        {
            "name": "I meant...",
            "setup": ["I am 25 years old"],
            "contradiction": "I am 30 years old",
            "resolution": "I meant 30, I mistyped before",
            "expected": "30"
        },
        {
            "name": "changed to...",
            "setup": ["I prefer coffee"],
            "contradiction": "I prefer tea",
            "resolution": "I've changed to tea recently",
            "expected": "tea"
        },
        {
            "name": "explicit confirm",
            "setup": ["I am single"],
            "contradiction": "I am married",
            "resolution": "Yes, I got married, that's correct now",
            "expected": "married"
        },
        {
            "name": "keep OLD value",
            "setup": ["My favorite color is blue"],
            "contradiction": "My favorite color is red",
            "resolution": "No wait, blue was right, ignore the red",
            "expected": "blue"
        }
    ]
    
    results = {}
    timestamp = int(time.time())
    
    for i, p in enumerate(patterns):
        print(f"\n  [{i+1}/6] Pattern: '{p['name']}'")
        thread = f"nl_test_{i}_{timestamp}"
        
        # Setup
        for fact in p["setup"]:
            chat(thread, fact)
            time.sleep(0.3)
        
        # Contradict
        chat(thread, p["contradiction"])
        time.sleep(0.3)
        
        # Count before
        contras_before = len([c for c in get_contradictions(thread) if c.get("status") == "open"])
        
        # Resolve
        print(f"       Resolution: \"{p['resolution']}\"")
        chat(thread, p["resolution"])
        time.sleep(0.5)
        
        # Count after
        contras_after = len([c for c in get_contradictions(thread) if c.get("status") == "open"])
        resolved = contras_after < contras_before
        
        # Verify answer
        r = chat(thread, "Tell me about this")
        answer = r.get("answer", "").lower()
        correct = p["expected"].lower() in answer
        
        passed = resolved and correct
        results[p["name"]] = passed
        
        print(f"       Resolved: {resolved} ({contras_before}→{contras_after})")
        print(f"       Answer correct: {correct}")
        print(f"       {'✅' if passed else '❌'}")
    
    total_passed = sum(results.values())
    print(f"\n  NL Resolution: {total_passed}/6 ({100*total_passed/6:.0f}%)")
    
    overall_passed = total_passed >= 4  # 67% threshold
    print(f"\n  {'✅ PASSED' if overall_passed else '❌ FAILED'} (need 4/6)")
    
    RESULTS["tests"]["nl_resolution"] = {
        "passed": overall_passed,
        "details": results,
        "score": f"{total_passed}/6"
    }
    return overall_passed

# ============================================================
# TEST 5: API Resolution (OVERRIDE/PRESERVE)
# ============================================================
def test_api_resolution():
    print("\n" + "="*60)
    print("TEST 5: API Resolution (OVERRIDE/PRESERVE)")
    print("="*60)
    
    results = {}
    
    # Test OVERRIDE
    print("\n  [OVERRIDE]")
    thread = f"api_override_{int(time.time())}"
    
    chat(thread, "I work at Apple")
    time.sleep(0.3)
    chat(thread, "I work at Meta")
    time.sleep(0.5)
    
    contras = get_contradictions(thread)
    if contras:
        c = contras[0]
        print(f"    Resolving ledger_id: {c.get('ledger_id', 'N/A')[:20]}...")
        r = resolve_via_api(
            thread,
            c.get("ledger_id"),
            "OVERRIDE",
            c.get("new_memory_id")
        )
        override_ok = r.get("status") == "resolved" or "resolved" in str(r).lower()
        print(f"    Result: {'✅' if override_ok else '❌'}")
        results["OVERRIDE"] = override_ok
    else:
        print("    ❌ No contradiction created")
        results["OVERRIDE"] = False
    
    # Test PRESERVE
    print("\n  [PRESERVE]")
    thread = f"api_preserve_{int(time.time())}"
    
    chat(thread, "I live in Denver")
    time.sleep(0.3)
    chat(thread, "I live in Miami")
    time.sleep(0.5)
    
    contras = get_contradictions(thread)
    if contras:
        c = contras[0]
        print(f"    Resolving ledger_id: {c.get('ledger_id', 'N/A')[:20]}...")
        r = resolve_via_api(
            thread,
            c.get("ledger_id"),
            "PRESERVE"
        )
        preserve_ok = r.get("status") == "resolved" or "resolved" in str(r).lower()
        print(f"    Result: {'✅' if preserve_ok else '❌'}")
        results["PRESERVE"] = preserve_ok
    else:
        print("    ❌ No contradiction created")
        results["PRESERVE"] = False
    
    passed = all(results.values())
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    RESULTS["tests"]["api_resolution"] = {
        "passed": passed,
        "details": results
    }
    return passed

# ============================================================
# TEST 6: Rapid Fire Detection
# ============================================================
def test_rapid_fire():
    print("\n" + "="*60)
    print("TEST 6: Rapid Fire Detection (5 pairs)")
    print("="*60)
    
    pairs = [
        ("I'm 25 years old", "I'm 30 years old"),
        ("I live in Seattle", "I live in New York"),
        ("I love coffee", "I hate coffee"),
        ("I am single", "I am married"),
        ("I'm left-handed", "I'm right-handed"),
    ]
    
    detected = 0
    timestamp = int(time.time())
    
    for i, (fact1, fact2) in enumerate(pairs):
        thread = f"rapid_{i}_{timestamp}"
        
        chat(thread, fact1)
        time.sleep(0.3)
        r = chat(thread, fact2)
        
        is_detected = r.get("metadata", {}).get("contradiction_detected", False)
        if not is_detected:
            # Check ledger as backup
            contras = get_contradictions(thread)
            is_detected = len(contras) > 0
        
        status = "✅" if is_detected else "❌"
        print(f"  {status} \"{fact1}\" vs \"{fact2}\"")
        
        if is_detected:
            detected += 1
    
    rate = detected / len(pairs)
    passed = rate >= 0.75  # 75% threshold
    
    print(f"\n  Detection rate: {detected}/{len(pairs)} ({100*rate:.0f}%)")
    print(f"  {'✅ PASSED' if passed else '❌ FAILED'} (need 75%+)")
    
    RESULTS["tests"]["rapid_fire"] = {
        "passed": passed,
        "details": {
            "detected": detected,
            "total": len(pairs),
            "rate": rate
        }
    }
    return passed

# ============================================================
# TEST 7: Database Integrity
# ============================================================
def test_database_integrity():
    print("\n" + "="*60)
    print("TEST 7: Database Integrity")
    print("="*60)
    
    pa_dir = Path("personal_agent")
    if not pa_dir.exists():
        pa_dir = Path("D:/AI_round2/personal_agent")
    
    issues = []
    
    # Find DBs
    memory_dbs = list(pa_dir.glob("crt_memory*.db"))
    ledger_dbs = list(pa_dir.glob("crt_ledger*.db"))
    
    print(f"  Memory DBs: {len(memory_dbs)}")
    print(f"  Ledger DBs: {len(ledger_dbs)}")
    
    if ledger_dbs:
        latest = sorted(ledger_dbs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        print(f"  Checking: {latest.name}")
        
        try:
            conn = sqlite3.connect(str(latest))
            cur = conn.cursor()
            
            # Check tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            print(f"  Tables: {tables}")
            
            if "contradictions" not in tables:
                issues.append("Missing contradictions table")
            
            # Check for orphaned records
            if "contradictions" in tables:
                cur.execute("SELECT COUNT(*) FROM contradictions WHERE status IS NULL")
                null_status = cur.fetchone()[0]
                if null_status > 0:
                    issues.append(f"{null_status} records with NULL status")
            
            conn.close()
        except Exception as e:
            issues.append(f"DB error: {e}")
    else:
        print("  ⚠️ No ledger DBs found (may be OK if fresh install)")
    
    passed = len(issues) == 0
    
    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("  ✅ No integrity issues found")
    
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    RESULTS["tests"]["database_integrity"] = {
        "passed": passed,
        "details": {"issues": issues}
    }
    return passed

# ============================================================
# MAIN
# ============================================================
def main():
    print("="*60)
    print("CRT FULL STRESS TEST SUITE")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Health check
    print("\nHealth check...", end=" ")
    if not health_check():
        print("❌ API not responding!")
        print("Start the server with: python -m uvicorn crt_api:app --host 127.0.0.1 --port 8123")
        return False
    print("✅ API is running")
    
    # Run all tests
    test_results = []
    
    test_results.append(("Basic Memory", test_basic_memory()))
    test_results.append(("Contradiction Detection", test_contradiction_detection()))
    
    gates_result = test_gates_blocking()
    if isinstance(gates_result, tuple):
        test_results.append(("Gates Blocking", gates_result[0]))
    else:
        test_results.append(("Gates Blocking", gates_result))
    
    test_results.append(("NL Resolution", test_nl_resolution()))
    test_results.append(("API Resolution", test_api_resolution()))
    test_results.append(("Rapid Fire Detection", test_rapid_fire()))
    test_results.append(("Database Integrity", test_database_integrity()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed_count = 0
    for name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if passed:
            passed_count += 1
    
    total = len(test_results)
    rate = passed_count / total
    
    print(f"\nTotal: {passed_count}/{total} ({100*rate:.0f}%)")
    
    RESULTS["summary"] = {
        "passed": passed_count,
        "total": total,
        "rate": rate,
        "verdict": "PASS" if rate >= 0.8 else "PARTIAL" if rate >= 0.5 else "FAIL"
    }
    
    if rate >= 0.8:
        print("\n🎉 SYSTEM READY - All core functionality working!")
    elif rate >= 0.5:
        print("\n⚠️ PARTIAL SUCCESS - Some features need work")
    else:
        print("\n❌ NEEDS WORK - Core functionality broken")
    
    # Save results
    with open("full_stress_test_results.json", "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)
    
    print(f"\nResults saved to: full_stress_test_results.json")
    
    return rate >= 0.8


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
