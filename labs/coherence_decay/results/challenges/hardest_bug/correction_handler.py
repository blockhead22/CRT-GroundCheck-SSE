"""Correction Handler — processes user corrections.

When the user corrects Aether, the correction is saved as a new memory.
This is correct behavior in isolation.

The problem: if the SAME correction keeps happening because of a routing
bug, we get duplicate memories piling up. The handler doesn't detect
that repeated corrections to the same topic indicate a systemic issue.
"""
import json
import time
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def handle_correction(corrected_text, user_id="default"):
    """Save a user correction as a new memory."""
    if not MEMORY_DB.exists():
        memories = []
    else:
        with open(MEMORY_DB) as f:
            memories = json.load(f)

    memory = {
        "id": len(memories) + 1,
        "text": corrected_text,
        "trust": 0.15,
        "source": "user_correction",
        "user_id": user_id,
        "created": time.time(),
    }
    memories.append(memory)

    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)

    return memory

def get_correction_count(topic_keywords, user_id="default"):
    """Count how many times a similar correction has been made.

    This function EXISTS but is NEVER CALLED by the pipeline.
    If it were called, it could detect the feedback loop.
    """
    if not MEMORY_DB.exists():
        return 0

    with open(MEMORY_DB) as f:
        memories = json.load(f)

    count = 0
    for mem in memories:
        if mem.get("source") == "user_correction":
            if any(kw in mem["text"].lower() for kw in topic_keywords):
                count += 1
    return count
