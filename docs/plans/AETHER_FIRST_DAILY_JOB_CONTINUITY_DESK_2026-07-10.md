# Aether First Daily Job — Continuity Desk

**Date:** 2026-07-10  
**Focus:** Daily usefulness only (not secure context packets)  
**Constraint:** Keep thesis — model = voice, memory = self, governance = evidence / review / correction / trace  

---

### Short answer first

**Yes — Aether is currently too much infrastructure and not enough job.**  
You open it to *test the thesis*, not to *finish work*. That is why the same meta prompts keep winning: they are the only affordances the product advertises.

**First daily job: Continuity Desk**

```text
Where were we? What changed? What’s next (with evidence)?
```

Not a full project manager. Not security. Not “explain Aether.”  
A **local continuity surface** over *your* repo + *your* substrate + *your* recent traces.

---

### 1. Most useful first daily job

**Continuity Desk** for Nick’s Aether work (then expand to other projects).

Three moves only:

1. **Where did we leave off?**
2. **What changed since last time?** (code + memory + traces)
3. **What should I do next?** (3 candidates, evidence-backed, reviewable)

That is a reason to open Workbench tomorrow morning without inventing a quiz.

---

### 2. Why that, and why not the others first

| Direction | Verdict |
|-----------|---------|
| **1 Continuity desk** | **First.** Matches memory=self + voice + trace. Uses what you already have. Daily loop is natural. |
| **2 Project workbench** | Strong #2, but too broad if it starts as “inspect any repo.” Fold *into* continuity for *this* repo first. |
| **3 Memory review** | Real differentiator, but empty if there’s no daily work flowing *into* memory. Secondary panel of the desk, not the front door. |
| **4 Daily briefing** | Continuity desk *is* the briefing, but event-driven (“since last open / last N hours”), not calendar theater. |
| **5 Testing copilot** | Valuable for *you as builder*, not as the product’s user job. Keep as internal harness. |
| **6 Handoff generator** | Excellent week-2 feature of continuity (“package for Grok”), not day-1. (Packets can wait.) |
| **7 Reflection/support** | Keep review-only; don’t make it the product spine. |
| **8 Repo watcher** | Support layer for “what changed,” not a standalone daemon product yet. |

**Why not memory-review-first?** You only get shallow memory because you only do shallow chat. Continuity *creates* moments worth remembering.

**Why not testing-copilot-first?** That optimizes the lab, not “open Aether to live.”

---

### 3. Smallest MVP

One Workbench mode / home card: **Continuity**.

On open (or button **“Where were we?”**):

```text
Last session summary (from traces / last turns)
Open loops (explicit user “todo/next” language + unfinished probes)
What changed (git status + recent commits on aether-core + optional substrate deltas)
Suggested next 3 moves (short, ordered, each with evidence links)
Memory that still matters for those moves (confirmed slots only)
```

No multi-project portfolio. No background agents. No API key required.

---

### 4. Exact Workbench commands / prompts

Fixed actions (buttons + slash commands), not free-form discovery:

| Command | Job |
|---------|-----|
| `/where` or **Where were we?** | Continuity brief |
| `/changed` or **What changed?** | Repo + memory + last N turns delta |
| `/next` or **What next?** | 3 ranked next moves with evidence |
| `/remember this` | Explicit store path (already partially there) |
| `/review` | Show review-only candidates for the brief |
| `/done <thing>` | Mark open loop closed (local, not ML magic) |

Free chat still works (voice), but **home is Continuity**, not blank chat that invites “what are you?”

---

### 5. Data it needs

**Local only, narrow:**

- `D:\AI_round2\aether-core` git: status, recent commits, dirty files (names + short diffs optional)
- Workbench turns/traces for this conversation history (SQLite)
- Confirmed substrate slots (profile + project-relevant)
- Passages already in memory-as-RAG for *project* docs if indexed
- Explicit open-loop markers you type (`next:`, `todo:`, `/done`)

---

### 6. What it should NOT access yet

- Full disk / all of AI_round2 blindly
- GPT archive bulk by default
- Network/APIs for “research the world”
- Email/calendar/Discord as “real work”
- Silent write of any inferred “Nick wants X”
- Other people’s repos
- Auto-send anything off-machine

---

### 7. Deterministic

- Git change list (files, commits, timestamps)
- Last N user/assistant turn bullets (extract, don’t invent)
- Confirmed memory dump for slots referenced by open loops
- Review candidate list (as stored)
- “Open loops” list if explicitly marked
- Trace links / turn ids
- “I don’t have that stored” for personal claims without slots

---

### 8. Model-generated (voice)

- Natural-language continuity narrative
- Ranking/phrasing of next 3 moves
- “Why this next” in one sentence each
- Optional short risk/uncertainty note

Bound by evidence pack: no next-step that requires unstored personal lore.

---

### 9. Review-only

- Inferred open loops (if not marked by you)
- “You might want to remember…” candidates
- Pattern/support extracts
- Any promotion of archive → confirmed
- Suggested renames of next-step priority after the fact

---

### 10. Success after one week of dogfooding

You open Aether **≥5 days** for continuity, not quizzes.

Concrete:

- At least **once per day**: `/where` or open → brief
- At least **3** real next-moves you actually did because the desk said so
- At least **1** correction of memory from work, not from color tests
- You can answer without opening chat logs: “where was I on hybrid fog / RAG / identity”
- Meta self-questions drop to near zero

If you still mostly ask favorite color: **MVP failed**.

---

### 11. Tests / evals that prove it

| Eval | Pass |
|------|------|
| After 3 turns of real work, `/where` mentions those themes | No generic Aether lecture |
| Dirty file + commit, `/changed` lists them | File names correct, no invent |
| Confirmed Brewers/orange only if in substrate | No leak of unconfirmed |
| `/next` items each cite turn id / file / slot | Or refuse |
| Empty day, no history | Honest “no prior session” |
| Personal invent attempt in next-steps | Blocked |
| Regression: hybrid fog on `/where` | Fail |

Unit + one live harness script > more “are you aether?” tests.

---

### 12. Biggest failure modes

1. **Continuity monologue** — hybrid poetry about “threads” with no file/turn evidence
2. **Stale “next”** — suggests work already done
3. **Quiz relapse** — UI still opens to blank chat
4. **Git noise** — dumps 40 files, user ignores
5. **Memory pollution** — auto-remembers every next-step as identity
6. **Wrong scope** — tries to be full IDE agent

---

### 13. Fit to model=voice / memory=self

| Layer | Role |
|--------|------|
| **Memory = self** | Who you are, prefs, held project facts, last open loops that were confirmed/stored |
| **Model = voice** | Speaks the brief and next moves |
| **Governance** | Evidence pack from git+traces+slots; no invent; review candidates separate |
| **Past → present** | Last session + diffs *are* the past that shapes today’s next |

Explaining Aether is optional; **using Aether’s memory of the work** is the job.

---

### 14. API model?

**Local first is enough.** Continuity is mostly retrieval + ranking + short prose. qwen3:14b is fine if the pack is tight.  
Optional stronger model later for messy multi-day synthesis — not a blocker for week 1.

---

### 15. LLC / funding?

**No meaningful change.** Still early. Continuity desk is product seriousness for *you*, not fundability.  
Funding story only gets slightly less fake if you can say “I use it every morning for open loops on a real codebase” — still not “raise now.”

---

### Blunt extras

**Too much infra, not enough job?**  
Yes. You’ve built a governed kitchen and keep tasting the knives.

**What would I build next so Nick uses it daily?**

1. Continuity home card on Workbench open
2. Deterministic git + last-turns pack
3. `/where` `/changed` `/next`
4. Explicit open-loop store + `/done`
5. Kill default blank “chat with the thesis” as the first screen

**What should Nick stop testing (low signal)?**

- `what are you?` / `how do you work?` / `epistemic integrity` as daily probes
- Endless identity typo routes
- Hybrid “list the layers of governance” style meta
- Favorite color after it’s green once per week max
- “Can you explain Aether?” as product validation

Keep a **tiny regression pack** (color, provenance, no invent). Stop living in it.

---

### Next 3 days

**Day 1**

- Continuity pack builder: last N turns + git status/commits for aether-core + confirmed slots
- Deterministic section renderer + model voice only for “next 3” with pack bound

**Day 2**

- Workbench: home Continuity + `/where` `/changed` `/next`
- Open-loop: parse `next:` / button “pin as next” → substrate or SQLite list

**Day 3**

- Live dogfood: morning `/where`, do real work, evening `/changed` + pin one next
- Evals for empty history, dirty tree, no-invent next-steps
- Delete or demote meta demo prompts from dogfood checklist

---

### Next 2 weeks

| Week | Focus |
|------|--------|
| **W1** | Continuity desk reliable for aether-core only; you use it daily |
| **W2** | `/done`, better open-loop extraction (review-only), handoff one-liner “package for Grok” as *export of continuity*, optional second project path |
| **Not W1–2** | Secure packets productization, enterprise, multi-API, phrase-route growth, full agent autonomy |

---

### One-line north star for usefulness

```text
Aether’s first job is to remember the work and put the next honest step in front of you —
not to explain itself.
```

---

### Related docs

- Secure-packet pivot prompt (separate lane, deferred): `docs/plans/AETHER_SECURE_CONTEXT_PACKET_PIVOT_PROMPT_FOR_GROK_2026-07-09.md`
- Product root: `D:\AI_round2\aether-core`
