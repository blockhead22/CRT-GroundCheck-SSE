import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

print("TRUST EVOLUTION TEST")
print("=" * 60)

queries = ["My name is Sarah.", "My name is Sarah.", "My name is Sarah.", "What's my name?"]

for i, q in enumerate(queries, 1):
    print(f"\nTURN {i}: {q}")
    result = rag.query(q)
    
    gates = "PASS" if result.get("gates_passed") else "FAIL"
    mem_align = result.get("memory_alignment", 0)
    
    memories = result.get("retrieved_memories", [])
    if memories:
        trusts = [m["trust"] for m in memories]
        max_trust = max(trusts)
        avg_trust = sum(trusts) / len(trusts)
        print(f"  Gates: {gates} | Mem_align: {mem_align:.3f}")
        print(f"  Trust: max={max_trust:.3f}, avg={avg_trust:.3f}, count={len(memories)}")
    else:
        print(f"  Gates: {gates} | No memories")

print("\n" + "=" * 60)
print("SUCCESS if trust increases: 0.70 -> 0.75 -> 0.80 -> 0.85")
print("=" * 60)
