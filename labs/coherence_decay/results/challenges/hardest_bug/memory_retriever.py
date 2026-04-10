"""Memory Retriever — finds relevant memories for a query."""
import json
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def retrieve_relevant_memories(query, user_id="default", top_k=5):
    """Retrieve memories relevant to the query.

    Uses simple keyword matching (simplified from embedding similarity).
    """
    if not MEMORY_DB.exists():
        return []

    with open(MEMORY_DB) as f:
        memories = json.load(f)

    query_words = set(query.lower().split())
    scored = []

    for mem in memories:
        mem_words = set(mem["text"].lower().split())
        overlap = len(query_words & mem_words)
        if overlap > 0:
            scored.append((overlap, mem))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored[:top_k]]
