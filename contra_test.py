import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

print("CONTRADICTION DETECTION TEST")
print("=" * 60)

queries = [
    "I work at Microsoft.",
    "I work at Amazon.",  # Should detect contradiction!
]

for i, q in enumerate(queries, 1):
    print(f"\nTURN {i}: {q}")
    result = rag.query(q)
    
    gates = "PASS" if result.get("gates_passed") else "FAIL"
    contra = "YES" if result.get("contradiction_detected") else "NO"
    
    print(f"  Gates: {gates} | Contradiction: {contra}")
    print(f"  Answer: {result['answer'][:100]}...")

print("\n" + "=" * 60)
print("SUCCESS if Turn 2 detects contradiction!")
print("=" * 60)
