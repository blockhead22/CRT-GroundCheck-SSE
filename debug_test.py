import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

result = rag.query("My name is Sarah.")
print("Result keys:", result.keys())
print("\nFirst result full:")
for k, v in result.items():
    if k != "answer":
        print(f"  {k}: {v}")
