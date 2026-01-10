import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

queries = ["My name is Sarah.", "My name is Sarah.", "My name is Sarah.", "What's my name?"]

for i, q in enumerate(queries, 1):
    print(f"\nTURN {i}: {q}")
    result = rag.query(q)
    print(f"Gates: {'PASS' if result.get('gates_passed') else 'FAIL'} | Trust max: {result.get('trust_max', 0):.3f}")
