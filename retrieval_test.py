import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

# Turn 1
print("Turn 1: Storing Microsoft")
rag.query("I work at Microsoft")

# Manual check
print("\nChecking what would be retrieved for 'I work at Amazon':")
retrieved = rag.retrieve("I work at Amazon", k=5)
print(f"Total memories retrieved: {len(retrieved)}")
for mem, score in retrieved:
    print(f"  - {mem.text[:50]}... (source={mem.source}, score={score:.3f})")
