# Future Work

This is a living backlog of ideas worth exploring once core correctness + demo stability are solid.

## FAISS / ANN Retrieval (Optional)

**Why:** If per-thread memory grows large (thousands+ items), approximate nearest-neighbor (ANN) indexing can improve retrieval latency and sometimes practical recall for top-k memory candidates.

**What to copy from crt-mvp:**
- Persist the index alongside data.
- Write a small metadata file (count + hash) and validate it before loading the index.
- If metadata mismatches, rebuild the index.

**Notes:**
- This does *not* solve gate logic or contradiction-resolution issues directly; it mainly accelerates and stabilizes retrieval.
- Consider feature-flagging (FAISS optional) with a safe fallback path.

**Reference pattern:** `crt-mvp/core/anchor_store.py` uses `{ anchor_count, anchors_sha1 }` in a `.meta.json` file to prevent stale-index usage.
