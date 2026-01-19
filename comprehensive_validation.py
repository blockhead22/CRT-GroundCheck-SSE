"""
Comprehensive validation of gradient gates v2 with progressive difficulty.

Test structure:
1. Store facts in memory (setup phase)
2. Ask questions about those facts (retrieval phase)
3. Progressively increase difficulty
4. Measure performance at each difficulty level
"""

import requests
import time
import json
import re
import uuid
from typing import Dict, List, Tuple

API_BASE = "http://localhost:8123"
# Use unique thread ID per run to avoid contamination
THREAD_ID = f"validation_{uuid.uuid4().hex[:8]}"

# Test progression: easy → medium → hard
TEST_PHASES = {
    "phase1_basic_facts": {
        "setup": [
            "My name is Alex Chen",
            "I work at TechCorp",
            "I live in San Francisco",
            "My favorite color is blue",
            "I have two siblings"
        ],
        "queries": [
            ("What is my name?", "factual", "easy"),
            ("Where do I work?", "factual", "easy"),
            ("What city do I live in?", "factual", "easy"),
            ("What is my favorite color?", "factual", "easy"),
            ("How many siblings do I have?", "factual", "easy")
        ]
    },
    "phase2_conversational": {
        "setup": [],  # Uses facts from phase1
        "queries": [
            ("Hi, how are you?", "conversational", "easy"),
            ("Can you help me?", "conversational", "easy"),
            ("Thanks for the information!", "conversational", "easy"),
            ("Tell me about yourself", "conversational", "medium")
        ]
    },
    "phase3_synthesis": {
        "setup": [
            "I enjoy programming in Python",
            "I like machine learning",
            "I'm interested in AI safety"
        ],
        "queries": [
            ("What do you know about my interests?", "synthesis", "medium"),
            ("What technologies am I into?", "synthesis", "medium"),
            ("Can you summarize what you know about me?", "synthesis", "hard")
        ]
    },
    "phase4_question_words": {
        "setup": [
            "I graduated in 2020",
            "My project is called CRT",
            "I speak three languages"
        ],
        "queries": [
            ("When did I graduate?", "question_word", "easy"),
            ("What is my project called?", "question_word", "easy"),
            ("How many languages do I speak?", "question_word", "medium"),
            ("Why am I working on this project?", "question_word", "hard"),
            ("How does CRT work?", "question_word", "hard")
        ]
    },
    "phase5_contradictions": {
        "setup": [
            "I'm thinking about changing jobs",
            "I just got promoted at TechCorp"  # Contradicts changing jobs
        ],
        "queries": [
            ("Am I happy at TechCorp?", "contradiction", "hard"),
            ("What's going on with my job?", "contradiction", "hard")
        ]
    }
}

def reset_thread():
    """Reset test thread to clean slate."""
    try:
        response = requests.post(
            f"{API_BASE}/api/thread/reset",
            json={"thread_id": THREAD_ID},
            timeout=10
        )
        print(f"Thread reset: {response.status_code == 200}")
        return response.status_code == 200
    except Exception as e:
        print(f"Reset failed: {e}")
        return False

def store_fact(fact: str) -> bool:
    """Store a fact in memory."""
    try:
        response = requests.post(
            f"{API_BASE}/api/chat/send",
            json={
                "thread_id": THREAD_ID,
                "message": fact
            },
            timeout=30
        )
        if response.status_code == 200:
            print(f"  ✓ Stored: {fact}")
            return True
        else:
            print(f"  ✗ Failed to store: {fact} ({response.status_code})")
            return False
    except Exception as e:
        print(f"  ✗ Exception storing fact: {e}")
        return False

def test_query(query: str, expected_type: str, difficulty: str) -> Dict:
    """Test a query and return detailed results."""
    try:
        response = requests.post(
            f"{API_BASE}/api/chat/send",
            json={
                "thread_id": THREAD_ID,
                "message": query
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            gates_passed = data.get("gates_passed", False)
            gate_reason = data.get("gate_reason", "")
            metadata = data.get("metadata", {})
            
            # Check if answer is meaningful (not a rejection)
            # Look for explicit rejection patterns, not just presence of phrases
            rejection_patterns = [
                r"^(sorry|unfortunately),?\s+(i\s+)?don't\s+(have|know)",
                r"^i\s+don't\s+(have|know)\s+(that|any|the)",
                r"(not|don't)\s+have\s+(that\s+)?information",
                r"can't\s+(help|assist)\s+with",
            ]
            
            # Answer is a rejection if it STARTS with or is PRIMARILY a rejection
            is_rejection = any(re.search(pattern, answer.lower(), re.IGNORECASE) for pattern in rejection_patterns)
            
            # If gates passed and it's not an explicit rejection, it's meaningful
            is_meaningful = gates_passed and not is_rejection
            
            passed = gates_passed and is_meaningful
            
            return {
                "query": query,
                "expected_type": expected_type,
                "difficulty": difficulty,
                "passed": passed,
                "gates_passed": gates_passed,
                "is_meaningful": is_meaningful,
                "answer": answer,
                "gate_reason": gate_reason,
                "answer_length": len(answer)
            }
        else:
            return {
                "query": query,
                "expected_type": expected_type,
                "difficulty": difficulty,
                "passed": False,
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "query": query,
            "expected_type": expected_type,
            "difficulty": difficulty,
            "passed": False,
            "error": str(e)
        }

def run_phase(phase_name: str, phase_data: Dict) -> Dict:
    """Run a complete test phase."""
    print(f"\n{'='*80}")
    print(f"PHASE: {phase_name}")
    print(f"{'='*80}")
    
    # Setup: store facts
    if phase_data["setup"]:
        print(f"\nSetup: Storing {len(phase_data['setup'])} facts...")
        for fact in phase_data["setup"]:
            store_fact(fact)
            time.sleep(0.3)
    
    # Test: run queries
    print(f"\nTesting: {len(phase_data['queries'])} queries...")
    results = []
    for query, qtype, difficulty in phase_data["queries"]:
        print(f"\n  Query: {query}")
        result = test_query(query, qtype, difficulty)
        results.append(result)
        
        if result.get("passed"):
            print(f"    ✓ PASS (gates:{result['gates_passed']}, meaningful:{result['is_meaningful']})")
            print(f"    Answer: {result['answer'][:100]}...")
        else:
            print(f"    ✗ FAIL")
            if 'error' in result:
                print(f"    Error: {result['error']}")
            else:
                print(f"    Gates:{result.get('gates_passed')}, Meaningful:{result.get('is_meaningful')}")
                if not result.get('is_meaningful'):
                    print(f"    Answer: {result.get('answer', '')[:150]}")
        
        time.sleep(0.5)
    
    # Phase summary
    passed_count = sum(1 for r in results if r.get("passed"))
    total = len(results)
    pass_rate = 100 * passed_count / total if total > 0 else 0
    
    print(f"\nPhase Results: {passed_count}/{total} ({pass_rate:.1f}% pass rate)")
    
    return {
        "phase_name": phase_name,
        "results": results,
        "passed": passed_count,
        "total": total,
        "pass_rate": pass_rate
    }

def main():
    print("="*80)
    print("COMPREHENSIVE VALIDATION: Gradient Gates V2")
    print("="*80)
    print(f"\nAPI: {API_BASE}")
    print(f"Thread ID: {THREAD_ID}")
    
    # Reset thread
    print("\nResetting test thread...")
    if not reset_thread():
        print("Warning: Thread reset failed, continuing anyway...")
    
    # Run all phases
    phase_results = []
    for phase_name, phase_data in TEST_PHASES.items():
        phase_result = run_phase(phase_name, phase_data)
        phase_results.append(phase_result)
        time.sleep(1)
    
    # Overall summary
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    
    total_passed = sum(p["passed"] for p in phase_results)
    total_queries = sum(p["total"] for p in phase_results)
    overall_pass_rate = 100 * total_passed / total_queries if total_queries > 0 else 0
    
    print(f"\nTotal: {total_passed}/{total_queries} ({overall_pass_rate:.1f}% pass rate)")
    
    print(f"\nBreakdown by phase:")
    for p in phase_results:
        print(f"  {p['phase_name']}: {p['passed']}/{p['total']} ({p['pass_rate']:.1f}%)")
    
    # Breakdown by difficulty
    all_results = []
    for p in phase_results:
        all_results.extend(p["results"])
    
    by_difficulty = {}
    for r in all_results:
        diff = r.get("difficulty", "unknown")
        if diff not in by_difficulty:
            by_difficulty[diff] = {"passed": 0, "total": 0}
        by_difficulty[diff]["total"] += 1
        if r.get("passed"):
            by_difficulty[diff]["passed"] += 1
    
    print(f"\nBreakdown by difficulty:")
    for diff in ["easy", "medium", "hard"]:
        if diff in by_difficulty:
            d = by_difficulty[diff]
            rate = 100 * d["passed"] / d["total"] if d["total"] > 0 else 0
            print(f"  {diff.capitalize()}: {d['passed']}/{d['total']} ({rate:.1f}%)")
    
    # Assessment
    print(f"\nASSESSMENT:")
    if overall_pass_rate >= 80:
        print(f"  [EXCELLENT] System exceeds 80% target ({overall_pass_rate:.1f}%)")
    elif overall_pass_rate >= 70:
        print(f"  [GOOD] System meets 70% target ({overall_pass_rate:.1f}%)")
    elif overall_pass_rate >= 60:
        print(f"  [ACCEPTABLE] System functional but needs tuning ({overall_pass_rate:.1f}%)")
    else:
        print(f"  [NEEDS WORK] System below 60% ({overall_pass_rate:.1f}%)")
    
    # Save results
    results_file = "comprehensive_validation_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "overall_pass_rate": overall_pass_rate,
            "total_passed": total_passed,
            "total_queries": total_queries,
            "phase_results": phase_results,
            "by_difficulty": by_difficulty
        }, f, indent=2)
    print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    main()
