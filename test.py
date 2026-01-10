import sys
sys.path.insert(0, "D:/AI_round2"
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

rag = CRTEnhancedRAG(llm_client=get_ollama_client())

print("TEST 1: Baseline fact")
r1 = rag.query("My name is Sarah")
print(f"Gates: {'PASS' if r1['gates_passed'] else 'FAIL'}")

print("\nTEST 2: Different fact")
r2 = rag.query("I work at Microsoft")
print(f"Gates: {'PASS' if r2['gates_passed'] else 'FAIL'}")

print("\nTEST 3: Contradiction")
r3 = rag.query("I work at Amazon")
print(f"Gates: {'PASS' if r3['gates_passed'] else 'FAIL'}")
print(f"Contradiction: {'YES' if r3.get('contradiction_detected') else 'NO'}")

print("\nTEST 4: Recall")
r4 = rag.query("Where do I work?")
mems = r4.get('retrieved_memories', [])
if mems:
    print(f"Retrieved {len(mems)} memories")
    for m in mems[:3]:
        print(f"  - {m['text'][:50]}... trust={m['trust']:.2f}")
