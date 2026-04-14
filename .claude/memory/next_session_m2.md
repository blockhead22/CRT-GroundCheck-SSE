---
name: next_session_m2
description: Carry-forward task list for M2 Mac dev session (2026-04-09). Fidelity mirror fix, doc cleanup, repo setup.
type: project
---

## M2 Mac Session TODO

**Why:** Windows machine GPU-locked on Phi-3 fine-tune (~13h). Dev work moves to M2.

### Setup (do first)
- Clone AI_round2 and projectboard repos
- Recreate `.env` with API keys
- Download chatgpt_export from Google Drive → `data/chatgpt_export/`
- Optionally copy `personal_agent/crt_memory_shared.db` (886 memories) for Aether memory continuity

### Priority Work
1. **Fidelity mirror Fix C** — retrieval-response coherence pre-check (~20 lines in `personal_agent/fidelity_mirror.py`). Before scoring, check if retrieved memories are topically relevant to the response. If max cosine sim < 0.25, retrieval missed — score neutral instead of penalizing. Root cause: conversational queries surface irrelevant memories, then grounding check fails against them.

2. **Doc cleanup** — main repo architecture docs for self-onboarding. Projectboard README (currently Vite boilerplate, already replaced but could expand).

3. **Push Phi-3 adapter** — after training finishes on Windows, copy `models/phi3-crt-adapter-v2/` to new machine. Training was at loss 1.34, accuracy 68.4%, epoch 0.5 when session ended.

### Completed (2026-04-11)
- Gravity system built and wired into Aether (3 production hooks, singleton, kill switch)
- Salience gate solves coherence decay (3 epochs vs 26)
- GravityBeliefStore loads from production DBs (1000 memories, 19 rooms)
- Coherence decay diagnosed and fixed in scaffold
- MemPalace comparison done (CRT wins on all axes)

### Next from gravity session
- Wire gravity into CRT heartbeat as structural topology feed
- Add exploit template for 3B model (curl JSON formatting)
- Head-to-head comparison: gravity vs flat exploration tree
- Photography/music/finance room splitting in production (rooms flagged UNSTABLE)

### Backlog (from prior sessions)
- Breathing loop implementation (flagged as missing gate)
- Bug #5 BDG cascade demotion
- search_code tool blind spot (can't find files that grep finds trivially)
- 9 bugs total, 3 at P0 (see session_2026_04_08_overnight.md for full list)
