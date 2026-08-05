# Aether — Product Entry (Happy Path)

**What this is:** A short entry for using Aether Workbench as a **product**, not a research dump.

**Related plans:**  
- Acceleration: `docs/plans/AETHER_PRODUCT_ACCELERATION_2026-08-05.md`  
- Grants: `docs/plans/AETEROS_GRANTS_EXPLORATION_2026-08-05.md`

---

## What Aether is

**Aether** is a local governed personal AI companion:

- **Models speak** (local Ollama and/or hosted Grok as wording).
- **Aether decides** what may be believed, released, and which tools may run.
- **You can see** Process (how the answer formed), traces, and correct memory.

It is **not** a freeroam coding agent and **not** a promise of AGI.

---

## What it will do

- Keep multi-turn continuity when evidence is released.
- **Withhold** or stay partial when evidence is missing or conflicted.
- Run **bounded workspace tools** (search, read, list; patch only with approval).
- Run a **short agentic tool loop** after a draft when more evidence is needed (propose → Aether grant → re-render), with a hard budget.
- Prefer **source code** over packaging/venv shadows in search.

## What it will not do

- Invent who you are or rewrite durable identity from vibes.
- Give the model free shell or ambient tools.
- Auto-apply patches without policy/approval.
- Replace foundation models.

---

## Start (dev / monorepo)

1. **Ollama** running (local models) if you use Local render.
2. **Sidecar** on port **8765** (`aether-core` workbench sidecar).
3. **Workbench** UI (Electron or Vite dev on the ports you use, e.g. 5175).
4. Optional: select **Grok 4.5** as answer renderer in Settings (wording only).

Restart sidecar after pulling tool/loop changes so dogfood hits new code.

---

## First-session dogfood (product bar)

1. **Search:**  
   `do a workspace search for mirus`  
   → Expect paths under `aether-core\aether\sidecar\...`, not `.packaging\...\site-packages`.

2. **Explain from code:**  
   `explain how it works from the source files`  
   → Expect Process tool rounds / reads and an answer with real paths.

3. **Continuity:**  
   State a preference, then ask what you said / correct it.

4. **Cancel:**  
   Start a long turn and hit Cancel once.

If any step fails, fix that before new features.

---

## Product names

| Name | Role |
|------|------|
| **Aeteros** | Umbrella / future entity |
| **Aether** | The companion product |
| **Workbench** | Local UI proof surface |

---

## Freeze list (not now)

- CRT as primary product path  
- Fork Grok Build as the home of Aether  
- Full autobiographical substrate (Phase 5) before stranger-week  
- Unbounded multi-agent freeroam  

---

## When something feels wrong

- Check **Process** / Trace for tool receipts and provider (Hosted Grok vs Local).  
- Restart sidecar after code pulls.  
- Prefer explicit “search” / “read this file” if the loop under-fires — then file a dogfood note.
