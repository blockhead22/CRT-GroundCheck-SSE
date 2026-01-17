#!/usr/bin/env python3
"""Comprehensive validation of gradient gates with diverse query types."""
import requests
import time
import json
from collections import defaultdict

API_BASE = "http://127.0.0.1:8123"
THREAD_ID = "validation_test"

# Comprehensive test suite
test_categories = {
    "factual_personal": [
        ("What is my name?", True),
        ("What company do I work for?", True),
        ("Where do I live?", True),
        ("What is my job title?", True),
        ("How many years of programming experience do I have?", True),
    ],
    "factual_unknown": [
        ("What's my favorite color?", True),  # Should gracefully say "don't know"
        ("What car do I drive?", True),
        ("Where did I go to college?", True),
    ],
    "conversational": [
        ("Hello", True),
        ("Thanks", True),
        ("That's helpful", True),
        ("Good morning", True),
    ],
    "questions_with_keywords": [
        # These historically failed due to question word bias
        ("What do you know about me?", True),
        ("How can you help me?", True),
        ("Why should I trust your memory?", True),
        ("When did we start talking?", True),
    ],
    "synthesis_required": [
        ("Tell me about yourself", True),
        ("Summarize what you know", True),
        ("Give me a brief overview", True),
    ],
}

def reset_and_seed():
    """Reset thread and seed with test data."""
    requests.post(f"{API_BASE}/api/thread/reset", json={"thread_id": THREAD_ID, "target": "all"})
    
    # Seed memories
    memories = [
        "My name is Alex Chen",
        "I work at TechCorp",
        "I live in Seattle",
        "I am a senior engineer",
        "I have 8 years of programming experience",
    ]
    
    for mem in memories:
        requests.post(f"{API_BASE}/api/chat/send", json={"thread_id": THREAD_ID, "message": mem})
        time.sleep(0.05)

def run_test_category(category_name, tests):
    """Run all tests in a category."""
    results = []
    
    for query, should_pass in tests:
        try:
            resp = requests.post(f"{API_BASE}/api/chat/send", 
                               json={"thread_id": THREAD_ID, "message": query})
            data = resp.json()
            
            gates_passed = data.get("gates_passed", False)
            gate_reason = data.get("gate_reason", "unknown")
            response_type = data.get("response_type", "unknown")
            
            # Determine success
            test_passed = (gates_passed == should_pass)
            
            results.append({
                "query": query,
                "expected_pass": should_pass,
                "actual_pass": gates_passed,
                "test_passed": test_passed,
                "gate_reason": gate_reason,
                "response_type": response_type,
            })
            
            time.sleep(0.1)
            
        except Exception as e:
            results.append({
                "query": query,
                "expected_pass": should_pass,
                "test_passed": False,
                "error": str(e),
            })
    
    return results

def print_results(all_results):
    """Print formatted results."""
    print("\n" + "="*80)
    print("GRADIENT GATES VALIDATION RESULTS")
    print("="*80 + "\n")
    
    total_tests = 0
    total_passed = 0
    category_stats = {}
    
    for category, results in all_results.items():
        category_passed = sum(1 for r in results if r.get("test_passed", False))
        category_total = len(results)
        category_rate = (category_passed / category_total * 100) if category_total else 0
        
        category_stats[category] = {
            "passed": category_passed,
            "total": category_total,
            "rate": category_rate,
        }
        
        total_tests += category_total
        total_passed += category_passed
        
        print(f"{category.upper().replace('_', ' ')}")
        print("-" * 80)
        
        for r in results:
            status = "[PASS]" if r.get("test_passed") else "[FAIL]"
            query = r["query"][:50]
            
            if "error" in r:
                print(f"  {status} {query} - ERROR: {r['error']}")
            else:
                gates = "pass" if r.get("actual_pass") else "fail"
                reason = r.get("gate_reason", "")
                print(f"  {status} {query}")
                print(f"         Gates: {gates} | Reason: {reason}")
        
        print(f"\n  Category Pass Rate: {category_rate:.1f}% ({category_passed}/{category_total})\n")
    
    # Overall statistics
    overall_rate = (total_passed / total_tests * 100) if total_tests else 0
    
    print("="*80)
    print("OVERALL STATISTICS")
    print("="*80)
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    print(f"Pass Rate: {overall_rate:.1f}%")
    
    # Benchmark comparison
    print(f"\nBenchmark Comparison:")
    print(f"  Bootstrap baseline: 33.0% (binary gates)")
    print(f"  Current system: {overall_rate:.1f}% (gradient gates)")
    print(f"  Improvement: +{overall_rate - 33.0:.1f} percentage points")
    
    if overall_rate >= 80:
        print("\n[SUCCESS] Excellent performance! System ready for production.")
    elif overall_rate >= 70:
        print("\n[GOOD] Good performance. Minor tuning recommended.")
    elif overall_rate >= 50:
        print("\n[MODERATE] Moderate performance. Further optimization needed.")
    else:
        print("\n[POOR] Significant issues. Review gate logic.")
    
    return overall_rate

def check_learning_stats():
    """Check active learning statistics."""
    try:
        stats = requests.get(f"{API_BASE}/api/learning/stats").json()
        print("\n" + "="*80)
        print("ACTIVE LEARNING STATUS")
        print("="*80)
        print(f"\nTotal Events Logged: {stats['total_events']}")
        print(f"Total Corrections: {stats['total_corrections']}")
        print(f"Model Loaded: {stats['model_loaded']}")
        print(f"Pending Training: {stats['pending_training']}")
        print("\n[OK] Active learning infrastructure operational")
    except Exception as e:
        print(f"\n[ERROR] Active learning check failed: {e}")

if __name__ == "__main__":
    print("Resetting thread and seeding memories...")
    reset_and_seed()
    time.sleep(0.5)
    
    print("Running comprehensive validation tests...\n")
    
    all_results = {}
    for category, tests in test_categories.items():
        print(f"Testing {category}...")
        all_results[category] = run_test_category(category, tests)
        time.sleep(0.2)
    
    overall_rate = print_results(all_results)
    check_learning_stats()
    
    print("\n" + "="*80)
    print(f"Validation complete. Overall: {overall_rate:.1f}%")
    print("="*80)
