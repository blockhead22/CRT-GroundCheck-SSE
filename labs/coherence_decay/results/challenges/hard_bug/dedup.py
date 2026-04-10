"""Memory Deduplication — merges similar memories."""

def cosine_similarity(a, b):
    """Simplified: word overlap ratio as similarity proxy."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    total = len(words_a | words_b)
    return overlap / total

def deduplicate_memories(memories, threshold=0.85):
    """Find and merge similar memories.

    When two memories are similar enough (cosine > threshold),
    merge them into one to prevent bloat.
    """
    if len(memories) < 2:
        return memories

    merged = []
    skip = set()

    for i, mem_a in enumerate(memories):
        if i in skip:
            continue

        for j, mem_b in enumerate(memories):
            if j <= i or j in skip:
                continue

            sim = cosine_similarity(mem_a["text"], mem_b["text"])
            if sim >= threshold:
                # Merge: keep the text of the higher-trust one,
                # but AVERAGE the trust scores
                if mem_a["trust"] >= mem_b["trust"]:
                    merged_mem = {**mem_a}
                else:
                    merged_mem = {**mem_b}

                # BUG: averaging drags down trust when one memory
                # is a new low-trust correction (0.15) and the other
                # is an established high-trust fact (0.9)
                # Result: 0.9 + 0.15 / 2 = 0.525 — trust destroyed
                merged_mem["trust"] = (mem_a["trust"] + mem_b["trust"]) / 2

                merged.append(merged_mem)
                skip.add(i)
                skip.add(j)
                break

        if i not in skip:
            merged.append(mem_a)

    return merged
