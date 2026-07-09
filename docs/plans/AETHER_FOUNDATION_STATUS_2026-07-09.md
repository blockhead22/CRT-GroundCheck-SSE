# Foundation status (pre–Phase 2)

**Date:** 2026-07-09  
**Stamp:** `20260709_085023`

## 1. Snapshot

| Item | Location |
|---|---|
| Live substrate + workbench | `D:\AI_round2\_snapshots\pre_rag_20260709_085023\aether_home\` |
| Files | `substrate.json`, `workbench.db` (passages.json not present yet on live) |
| Git tag (aether-core) | `pre-rag-foundation-20260709_085023` @ `820ef0a8bed30de1f77b62d509beba11d36a5937` (tag marks commit; **uncommitted work still in tree**) |

**Note:** Working tree had many uncommitted changes at snapshot time. Tag points at last commit; full code state = commit + local mods. For a fuller code freeze later: commit or zip `aether-core` if needed.

---

## 2. Live environment (confirmed)

| Setting | Value |
|---|---|
| `AETHER_HOME` | unset → default |
| Default aether dir | `C:\Users\block\.aether` |
| `AETHER_DEMO_PERSONAL_HARDCODE` | unset → **default off** (`demo_hardcode_enabled=False`) |
| `AETHER_PASSAGES_PATH` | unset → `~\.aether\passages.json` when dual-write runs |
| substrate.json | present |
| workbench.db | present |
| passages.json (live) | **not yet** (created on first dual-write after workbench restart with new code) |

**Product root:** `D:\AI_round2\aether-core`  
**Live dogfood only:** `C:\Users\block\.aether`  
**Labs/fixtures:** `aether-core\.eval-runs\`, `aether-core\labs\` — do not auto-merge into live.

**Recommended (optional explicit env for clarity):**

```powershell
$env:AETHER_DEMO_PERSONAL_HARDCODE = "0"
# leave AETHER_HOME unset unless you intentionally point elsewhere
```

---

## 3. LLC trigger (decision)

**Trigger (pick whichever comes first):**

1. **Applying for a grant or program that requires a legal entity**, or  
2. **Opening a business bank account / taking money under the Aether name**, or  
3. **Date: 2026-09-01** — revisit LLC formation even if 1–2 haven’t fired (calendar check-in, not a panic deadline).

**Purpose line for entity (when formed):**  
Local personal AI memory — inspectable, answers from stored state, fitted to the user.

**Not a trigger:** “Code feels done” or “north star feels good.”

---

## 4. Parking lot (tangents — do not build this week)

| Idea | Why parked |
|---|---|
| Full `AI_round2` archive folder reorg / bring product up one level | After Milestone A (RAG path real) |
| Pure compression / splat labs as product path | Engines only; serve retrieve→answer |
| Cancer clinical / NCI product framing | Separate pivot; not current scope |
| Growing phrase-route catalogs (hello/how-you-work specials) | Violates north star |
| Bulk GPT dump into live `~/.aether` without confirm | Lab/fixture only |
| Mem0-clone feature race | Adopt retrieve patterns; keep held-tension edge |
| Grant one-pager / pitch deck | After Milestone A dogfood |
| Multi-user SaaS | Milestone D or later |

**Add new tangents here; do not implement until weekly north-star test is green on retrieve path.**

---

## Weekly north-star test

Store → new session → ask → grounded answer, no invent.  
Probes listed in `AETHER_NORTH_STAR_FREEZE_2026-07-09.md`.

---

## Next

Phase 2: `retrieve(query) → EvidencePack` over passages.
