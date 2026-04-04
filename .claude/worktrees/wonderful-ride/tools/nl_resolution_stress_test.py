#!/usr/bin/env python3
"""
NL Resolution Fix - Stress Test
Tests that contradictions can now be resolved via natural conversation
"""

import requests
import time
import json

BASE_URL = "http://127.0.0.1:8123"

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
    """Get open contradictions for a thread."""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/contradictions",
            params={"thread_id": thread_id},
            timeout=10
        )
        return resp.json().get("contradictions", [])
    except:
        return []

def run_test(name, thread_id, setup_facts, contradiction, resolution_phrase, expected_answer_contains):
    """Run a single NL resolution test."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    # Setup
    for fact in setup_facts:
        print(f"  → Setting up: {fact}")
        chat(thread_id, fact)
        time.sleep(0.5)
    
    # Create contradiction
    print(f"  → Contradicting: {contradiction}")
    r = chat(thread_id, contradiction)
    detected = r.get("metadata", {}).get("contradiction_detected", False)
    print(f"    Contradiction detected: {detected}")
    
    # Check gates are blocked
    print(f"  → Querying (should block)...")
    r = chat(thread_id, "What do you know about this?")
    gates_before = r.get("gates_passed", True)
    print(f"    Gates passed (before resolution): {gates_before}")
    
    # Count open contradictions before
    contras_before = len([c for c in get_contradictions(thread_id) if c.get("status") == "open"])
    print(f"    Open contradictions before: {contras_before}")
    
    # Attempt NL resolution
    print(f"  → Resolving: \"{resolution_phrase}\"")
    r = chat(thread_id, resolution_phrase)
    print(f"    Bot response: {r.get('answer', '')[:100]}...")
    
    # Small delay for processing
    time.sleep(1)
    
    # Check gates after resolution
    print(f"  → Querying again (should pass)...")
    r = chat(thread_id, expected_answer_contains.split()[0] + "?")  # Simple query
    gates_after = r.get("gates_passed", True)
    answer = r.get("answer", "")
    print(f"    Gates passed (after resolution): {gates_after}")
    print(f"    Answer: {answer[:100]}...")
    
    # Count open contradictions after
    contras_after = len([c for c in get_contradictions(thread_id) if c.get("status") == "open"])
    print(f"    Open contradictions after: {contras_after}")
    
    # Evaluate
    results = {
        "contradiction_detected": detected,
        "gates_blocked_before": not gates_before,
        "gates_passed_after": gates_after,
        "contradiction_resolved": contras_after < contras_before,
        "answer_correct": expected_answer_contains.lower() in answer.lower()
    }
    
    passed = all(results.values())
    
    print(f"\n  Results:")
    for k, v in results.items():
        status = "✅" if v else "❌"
        print(f"    {status} {k}: {v}")
    
    print(f"\n  {'✅ PASSED' if passed else '❌ FAILED'}")
    
    return passed, results


def main():
    print("="*60)
    print("NL RESOLUTION FIX - STRESS TEST")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    timestamp = int(time.time())
    all_results = {}
    
    # Test 1: Basic employer resolution with "correct"
    passed, results = run_test(
        name="Employer - 'X is correct'",
        thread_id=f"nl_test_1_{timestamp}",
        setup_facts=["I work at Microsoft"],
        contradiction="I work at Google",
        resolution_phrase="Google is correct, I switched jobs",
        expected_answer_contains="Google"
    )
    all_results["employer_correct"] = passed
    
    # Test 2: Location resolution with "actually"
    passed, results = run_test(
        name="Location - 'Actually...'",
        thread_id=f"nl_test_2_{timestamp}",
        setup_facts=["I live in Seattle"],
        contradiction="I live in Austin",
        resolution_phrase="Actually, I moved to Austin last month",
        expected_answer_contains="Austin"
    )
    all_results["location_actually"] = passed
    
    # Test 3: Age resolution with "I meant"
    passed, results = run_test(
        name="Age - 'I meant...'",
        thread_id=f"nl_test_3_{timestamp}",
        setup_facts=["I am 25 years old"],
        contradiction="I am 30 years old",
        resolution_phrase="I meant 30, I mistyped before",
        expected_answer_contains="30"
    )
    all_results["age_meant"] = passed
    
    # Test 4: Preference resolution with "changed"
    passed, results = run_test(
        name="Preference - 'changed'",
        thread_id=f"nl_test_4_{timestamp}",
        setup_facts=["I prefer coffee"],
        contradiction="I prefer tea",
        resolution_phrase="I've changed to tea recently",
        expected_answer_contains="tea"
    )
    all_results["preference_changed"] = passed
    
    # Test 5: Relationship resolution with explicit confirmation
    passed, results = run_test(
        name="Status - explicit confirmation",
        thread_id=f"nl_test_5_{timestamp}",
        setup_facts=["I am single"],
        contradiction="I am married",
        resolution_phrase="Yes, I got married, that's the correct status now",
        expected_answer_contains="married"
    )
    all_results["status_explicit"] = passed
    
    # Test 6: Keeping the OLD value (regression test)
    passed, results = run_test(
        name="Keep OLD value - 'first one was right'",
        thread_id=f"nl_test_6_{timestamp}",
        setup_facts=["My favorite color is blue"],
        contradiction="My favorite color is red",
        resolution_phrase="No wait, blue was right, ignore the red",
        expected_answer_contains="blue"
    )
    all_results["keep_old"] = passed
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total = len(all_results)
    passed = sum(all_results.values())
    
    for name, result in all_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\nTotal: {passed}/{total} ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - NL Resolution is working!")
    elif passed >= total * 0.8:
        print("\n⚠️ MOSTLY WORKING - Some edge cases failing")
    else:
        print("\n❌ FIX NOT WORKING - Core functionality still broken")
    
    # Save results
    with open("nl_resolution_test_results.json", "w") as f:
        json.dump({
            "timestamp": timestamp,
            "total": total,
            "passed": passed,
            "rate": passed/total,
            "results": all_results
        }, f, indent=2)
    
    print(f"\nResults saved to: nl_resolution_test_results.json")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
