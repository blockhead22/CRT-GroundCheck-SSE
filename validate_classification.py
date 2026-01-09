#!/usr/bin/env python3
"""Quick validation test for contradiction classification system."""

import sys
sys.path.insert(0, 'd:/AI_round2')

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
from personal_agent.crt_ledger import ContradictionType

print("="*70)
print(" CONTRADICTION CLASSIFICATION VALIDATION ".center(70, "="))
print("="*70)

ollama = get_ollama_client("llama3.2:latest")
rag = CRTEnhancedRAG(llm_client=ollama)

print("\nTest 1: Baseline fact")
r1 = rag.query("I work at Microsoft as a senior developer.")
print(f"Response: {r1['answer'][:100]}...")
print(f"Gates: {'✓' if r1['gates_passed'] else '✗'}, Contradiction: {r1['contradiction_detected']}")

print("\nTest 2: Refinement (Seattle → Bellevue)")
r2 = rag.query("I live in Seattle.")
print(f"Gates: {'✓' if r2['gates_passed'] else '✗'}")

r3 = rag.query("I live in Bellevue, which is in the Seattle area.")
print(f"Response: {r3['answer'][:100]}...")
print(f"Gates: {'✓' if r3['gates_passed'] else '✗'}, Contradiction: {r3['contradiction_detected']}")
if r3['contradiction_entry']:
    print(f"  Type: {r3['contradiction_entry']['contradiction_type']}")
    print(f"  Expected: {ContradictionType.REFINEMENT}")

print("\nTest 3: Temporal progression (Senior → Principal)")
r4 = rag.query("Actually, I was promoted to Principal Engineer.")
print(f"Response: {r4['answer'][:100]}...")
print(f"Gates: {'✓' if r4['gates_passed'] else '✗'}, Contradiction: {r4['contradiction_detected']}")
if r4['contradiction_entry']:
    print(f"  Type: {r4['contradiction_entry']['contradiction_type']}")
    print(f"  Expected: {ContradictionType.TEMPORAL} or {ContradictionType.REVISION}")

print("\nTest 4: Conflict (Microsoft vs Amazon)")
r5 = rag.query("I work at Amazon, not Microsoft.")
print(f"Response: {r5['answer'][:100]}...")
print(f"Gates: {'✓' if r5['gates_passed'] else '✗'}, Contradiction: {r5['contradiction_detected']}")
if r5['contradiction_entry']:
    print(f"  Type: {r5['contradiction_entry']['contradiction_type']}")
    print(f"  Expected: {ContradictionType.CONFLICT}")

print("\nTest 5: Recall with unresolved contradictions (should express uncertainty)")
r6 = rag.query("Where do I work?")
print(f"Response: {r6['answer'][:200]}...")
print(f"Response type: {r6['response_type']}")
print(f"Expected: 'uncertainty' (due to Microsoft vs Amazon conflict)")

print("\n" + "="*70)
print(" TEST COMPLETE ".center(70, "="))
print("="*70)
print("\nKey Validations:")
print("1. Refinement (Seattle→Bellevue) should NOT trigger full contradiction")
print("2. Temporal (Senior→Principal) should be logged but not degrade trust heavily")
print("3. Conflict (Microsoft vs Amazon) should trigger contradiction detection")
print("4. System should express uncertainty when recalling conflicting facts")
