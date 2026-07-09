# Aether North Star Freeze

**Date:** 2026-07-09  
**Status:** Frozen for product work (until deliberately revised)  
**Related:** `AETHER_MEMORY_RAG_DEFAULT_PATH_2026-07-09.md`

This is the map so we don’t get lost. Technical phases (passages, RAG, etc.) **serve this**, not the reverse.

---

## Problem (one sentence)

Personal AI either **forgets** what matters, **invents** what was never stored, or **flattens** multi-truth into a single tidy story — often while the user can’t inspect or control what the system believes.

---

## Outcome (what “works” means)

A **local** assistant that:

1. **Answers from what was stored** (clear text / claims retrieved — not route theater).  
2. **Holds multi-truth** when both sides are real (two favorites, preference + concern, etc.).  
3. **Does not invent** personal lore (health, meaning, identity) without memory.  
4. **Is inspectable** — user can see stored passages/slots; governance steps in at edges, not as monologue.  
5. **Grows with the user** — fitted to *them*, not the average public model curve.

---

## Moral north star

> **Not AI for everyone. AI that remembers *you*, on *your* machine, that you can open and check.**

Local, trustworthy, personal continuity — not “big AI bad” as a slogan; **agency and inspectability** as practice. Pricing, data centers, and cloud lock-in make this more valuable over time, not less.

---

## Technical north star (how we get there)

> **If it wasn’t stored and retrieved, it doesn’t get to speak.**

- Compression, vectors, governance, open claims = **engines**.  
- Default chat path = **retrieve → answer from pack**.  
- Tools/governance = write, confirm, conflict, quarantine — not 40 phrase classes.

---

## Out of scope (do not chase this sprint / until Milestone A)

- New phrase / semantic **routes** for hello, how-you-work, etc.  
- Nick / orange / leukemia **demo hardcode** as product behavior  
- Cancer clinical product / NCI-style health product (unless a deliberate later pivot)  
- Full monorepo archaeology / archive folder toss (parked; do after path is real)  
- VC-scale productization / multi-user SaaS  
- Pure governance essays without retrieval  
- Reinventing Mem0-class vector layers from scratch (adopt patterns; keep held-tension edge)

---

## Weekly test (progress = this, not more MDs)

**North-star probe (minimum):**

1. Store something clear (“My favorite drink is coffee.” / multi if ready).  
2. **New session / thread.**  
3. Ask for it.  
4. Answer must come from **stored** memory (eventually: retrieved passage).  
5. No invent, no governance cockpit monologue.

**Full regression set** (when answering path is live):

1. Hello?  
2. How do you work?  
3. What is my favorite drink?  
4. How many favorite drinks?  
5. What do I think about my favorite drinks?  
6. Why does my favorite color matter? (only if a reason is stored)  
7. I’m tired today  
8. What do you know about me?

---

## Live vs lab (isolation)

| | Role |
|---|---|
| **Live** | `~/.aether` — real dogfood only; no bulk archive merge without confirm |
| **Lab / fixture** | `.eval-runs/`, `labs/`, archive seed substrates/passages — **never auto-merge** into live |
| **Product root** | `D:\AI_round2\aether-core` (and plans under `docs/plans`) |
| **Archive later** | Optional `_archive/` for old trees — **not** blocking; after Milestone A |

---

## Business mode (not free-reign exploration)

| Exploration | Structure |
|---|---|
| Interesting idea → dive | Idea parks unless it serves **weekly test** |
| Labs = progress | **Probe pass/fail** = progress |
| Someday LLC | **Trigger:** grant form, bank, IP, or chosen date |
| Someday grants | **After** Milestone A (memory answers without theater) |

**Operating rhythm**

1. One goal per week (from RAG plan phases).  
2. Parking lot for tangents.  
3. Friday: run north-star test; note pass/fail.  
4. Kill new phrase routes by default.

---

## Milestone map (LLC / funding — when it’s time)

| Milestone | Meaning | When |
|---|---|---|
| **A — Path real** | Default chat answers from retrieved memory on probes | End of RAG plan Phases 0–5 |
| **B — LLC** | Legal vessel | See **LLC trigger** below |
| **C — Grants** | One-pager + demo, honest scope | After A + showable store→recall |
| **D — Broader commercial** | Non-you users | Later |

**Do not pitch C while still living on route theater.**

### LLC trigger (frozen 2026-07-09)

Form / file LLC when **first of**:

1. Applying for a grant/program that needs a legal entity, or  
2. Banking / taking money under the Aether name, or  
3. **Calendar revisit: 2026-09-01** (decision check-in, not “must form that day”).

Purpose line: *Local personal AI memory — inspectable, answers from stored state, fitted to the user.*

Full detail: end of `AETHER_MEMORY_RAG_DEFAULT_PATH_2026-07-09.md` + `AETHER_FOUNDATION_STATUS_2026-07-09.md`.

---

## What already landed (does not replace freeze)

- Phase 1 **passage store** + dual-write (`aether/memory/passages.py`) — foundation for retrieve  
- Multi-facet open claims lab  
- Demo hardcode default **off**  
- GPT archive fixture (isolated)  

These support the north star; they are not the north star themselves.

---

## Revision rule

This freeze changes only when Nick explicitly revises it — not when a cool lab appears.

**Sign-off:** Working product direction for Aether as of 2026-07-09.
