#!/usr/bin/env python3
"""
CRT Conversation Testing Script

Tests the fixes:
1. Memory retrieval with real embeddings
2. Trust evolution through confirmations
3. Coherence/alignment scores
4. System self-description
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
import time


def print_result(query: str, result: dict, test_num: int):
    """Print formatted test result."""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: {query}")
    print('='*80)
    
    print(f"\n📝 Answer: {result['answer'][:200]}...")
    
    print(f"\n📊 CRT Metrics:")
    print(f"   Response Type: {result['response_type'].upper()}")
    print(f"   Gates Passed: {'✅' if result['gates_passed'] else '❌'}")
    if not result['gates_passed']:
        print(f"   Gate Reason: {result['gate_reason']}")
    print(f"   Confidence: {result['confidence']:.2f}")
    print(f"   Mode: {result['mode']}")
    
    if result['retrieved_memories']:
        print(f"\n🧠 Retrieved {len(result['retrieved_memories'])} memories:")
        for i, mem in enumerate(result['retrieved_memories'][:3], 1):
            print(f"   {i}. [{mem['source']}] Trust: {mem['trust']:.2f}")
            print(f"      Text: {mem['text'][:60]}...")


def test_memory_retrieval(rag):
    """Test 1: Memory storage and retrieval."""
    print("\n" + " TEST 1: Memory Storage & Retrieval ".center(80, "="))
    
    # Store some facts
    result1 = rag.query("My name is Nick and I like orange")
    print_result("Store: Name + Color", result1, 1.1)
    
    time.sleep(0.5)
    
    # Retrieve
    result2 = rag.query("What's my name and favorite color?")
    print_result("Retrieve: Name + Color", result2, 1.2)
    
    # Check if it retrieved correctly
    success = "nick" in result2['answer'].lower() and "orange" in result2['answer'].lower()
    print(f"\n✅ PASS" if success else f"\n❌ FAIL")
    return success


def test_trust_evolution(rag):
    """Test 2: Trust evolution through confirmation."""
    print("\n" + " TEST 2: Trust Evolution ".center(80, "="))
    
    # Initial fact
    result1 = rag.query("I'm a software engineer")
    print_result("Store: Job", result1, 2.1)
    
    time.sleep(0.5)
    
    # Confirm it
    result2 = rag.query("Yes, I work in software development")
    print_result("Confirm: Job", result2, 2.2)
    
    time.sleep(0.5)
    
    # Confirm again
    result3 = rag.query("I've been coding for 10 years")
    print_result("Reinforce: Coding experience", result3, 2.3)
    
    # Check trust scores
    if result3['retrieved_memories']:
        trust_scores = [m['trust'] for m in result3['retrieved_memories']]
        max_trust = max(trust_scores)
        print(f"\n📊 Max Trust: {max_trust:.3f}")
        success = max_trust > 0.5  # Should have increased from base
        print(f"✅ PASS - Trust evolved" if success else f"❌ FAIL - Trust stuck at {max_trust:.3f}")
        return success
    
    return False


def test_contradiction_detection(rag):
    """Test 3: Contradiction detection."""
    print("\n" + " TEST 3: Contradiction Detection ".center(80, "="))
    
    # Store first claim
    result1 = rag.query("I live in New York")
    print_result("Store: Location 1", result1, 3.1)
    
    time.sleep(0.5)
    
    # Contradict it
    result2 = rag.query("Actually, I live in California")
    print_result("Store: Location 2 (contradiction?)", result2, 3.2)
    
    success = result2.get('contradiction_detected', False)
    print(f"\n✅ PASS - Contradiction detected" if success else f"❌ FAIL - No contradiction detected")
    return success


def test_self_description(rag):
    """Test 4: CRT self-description."""
    print("\n" + " TEST 4: CRT Self-Description ".center(80, "="))
    
    result = rag.query("Explain how you work - your architecture and principles")
    print_result("System self-description", result, 4)
    
    # Check if it mentions CRT concepts
    answer_lower = result['answer'].lower()
    keywords = ['trust', 'belief', 'contradiction', 'memory', 'coherence']
    found = sum(1 for k in keywords if k in answer_lower)
    
    print(f"\n📊 CRT Keywords Found: {found}/{len(keywords)}")
    success = found >= 3  # Should mention at least 3 CRT concepts
    print(f"✅ PASS - Describes CRT architecture" if success else f"❌ FAIL - Generic AI description")
    return success


def test_coherence_gates(rag):
    """Test 5: Reconstruction gates."""
    print("\n" + " TEST 5: Coherence Gates ".center(80, "="))
    
    # Store context
    rag.query("I love Python programming")
    rag.query("I use Django for web development")
    time.sleep(0.5)
    
    # Related query (should pass gates)
    result1 = rag.query("What programming language do I prefer?")
    print_result("Related query", result1, 5.1)
    
    time.sleep(0.5)
    
    # Unrelated query (might fail gates)
    result2 = rag.query("What's the weather like on Mars?")
    print_result("Unrelated query", result2, 5.2)
    
    print(f"\n📊 Gate Results:")
    print(f"   Related query gates: {'✅ PASSED' if result1['gates_passed'] else '❌ FAILED'}")
    print(f"   Unrelated query gates: {'✅ PASSED' if result2['gates_passed'] else '❌ FAILED'}")
    
    # Success if related passes and unrelated fails
    success = result1['gates_passed'] and not result2['gates_passed']
    print(f"\n✅ PASS - Gates working correctly" if success else f"❌ FAIL - Gate logic issues")
    return success


def main():
    """Run comprehensive CRT tests."""
    print("\n" + " CRT COMPREHENSIVE TESTING ".center(80, "="))
    print("Testing fixes: embeddings, trust evolution, gates, system prompts\n")
    
    # Initialize CRT
    print("🔄 Initializing CRT with Ollama...")
    try:
        ollama = get_ollama_client("llama3.2:latest")
        rag = CRTEnhancedRAG(llm_client=ollama)
        print("✅ CRT initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    # Run tests
    results = {
        "Memory Retrieval": test_memory_retrieval(rag),
        "Trust Evolution": test_trust_evolution(rag),
        "Contradiction Detection": test_contradiction_detection(rag),
        "Self-Description": test_self_description(rag),
        "Coherence Gates": test_coherence_gates(rag),
    }
    
    # Summary
    print("\n" + " TEST SUMMARY ".center(80, "="))
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}  {test_name}")
    
    print(f"\n{'='*80}")
    print(f"Result: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print('='*80)
    
    if passed == total:
        print("\n🎉 All tests passed! CRT is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review output above for details.")


if __name__ == "__main__":
    main()

