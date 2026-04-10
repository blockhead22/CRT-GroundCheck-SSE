"""Memory Store — persists memories with trust scores."""
import json
import time
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def load_memories():
    if MEMORY_DB.exists():
        with open(MEMORY_DB) as f:
            return json.load(f)
    return []

def save_memory(text, trust=0.15, source="user"):
    """Save a new memory. New memories start at trust=0.15 (unverified)."""
    memories = load_memories()
    memory = {
        "id": len(memories) + 1,
        "text": text,
        "trust": trust,
        "source": source,
        "created": time.time(),
        "last_accessed": time.time(),
    }
    memories.append(memory)

    # Run dedup after every save
    from dedup import deduplicate_memories
    memories = deduplicate_memories(memories)

    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)
    return memory

def get_memory(text):
    """Find a memory by text similarity (simplified: exact match)."""
    memories = load_memories()
    for m in memories:
        if text.lower() in m["text"].lower() or m["text"].lower() in text.lower():
            return m
    return None

def update_trust(memory_id, new_trust):
    """Update a memory's trust score."""
    memories = load_memories()
    for m in memories:
        if m["id"] == memory_id:
            m["trust"] = new_trust
            m["last_accessed"] = time.time()
    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)
