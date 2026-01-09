import sys
sys.path.insert(0, "d:\\AI_round2"

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

print("Initializing...")
ollama = get_ollama_client("llama3.2:latest")
rag = CRTEnhancedRAG(llm_client=ollama)

# TURN 1
print("\n" + "="*60)
print("TURN 1")
print("="*60)
print("ME: Hello! Can you explain how your trust-weighted memory works?")
r = rag.query("Hello! Can you explain how your trust-weighted memory works?")
print(f"CRT: {r['answer'][:300]}")
print(f"[Gates: {r['gates_passed']}, Conf: {r['confidence']:.2f}]")
