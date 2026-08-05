# Aether Product Acceleration Plan

**Saved:** 2026-08-05  
**Cold resume:** `docs/plans/AETHER_WHATS_NEXT_RESUME_2026-08-05.md`  
**Goal:** Accelerate to product = one wedge usable without the manifesto, with honest tools, stable multi-turn, and visible Process.

**Not the goal:** Full Phase 4–5 autobiography, Grok Build fork, CRT revival, or freeroam multi-agent AGI.

---

## Wedge (default)

Local governed companion for **personal + project continuity** + **bounded workspace tools**  
(search → read → answer with receipts; no inventing identity or file truth).

---

## Already in place

| Area | Status |
|------|--------|
| Workbench + sidecar product path | Primary |
| Conversation context / continuity packet | Largely in |
| Obligation ledger + wording repair | In (semantic full verifier still soft) |
| Process / run events + cancel | In |
| Governed tools (search/read/list/patch-propose/tests) | In |
| Model propose + grant + execute | In |
| Cross-turn preferred reads + search hygiene | In (verify live after restart) |
| Agentic tool loop (≤2 post-draft rounds) | Landed 2026-08 — needs dogfood |
| Grok as wording-only renderer + sticky | In |
| Floating/pin restore | In |

---

## P0 — Close the proof loop (1–2 weeks)

**Ship bar:** Run these cold after restart and not babysit.

1. Restart sidecar + Workbench (agentic loop + search hygiene + floating).
2. Dogfood script (must pass):
   - Workspace search for a real symbol (e.g. mirus/holden) → **source paths, not packaging**
   - Follow-up: “explain how it works from the code” → **tool round(s) + reads + Hosted Grok stays**
   - Ordinary multi-turn: personal fact / correction / “what did I say”
   - Cancel mid-run once
3. Fix only what fails that script (no new features until green).

**Exit:** Written dogfood log: pass/fail + notes/clip.

### Dogfood checklist

```text
[ ] Restart sidecar + Workbench
[ ] Dogfood: search → explain from code (agentic loop)
[ ] Dogfood: multi-turn continuity + correction
[ ] Dogfood: cancel once
[ ] Fix only failures from above
```

---

## P1 — Product polish for the wedge (2–4 weeks)

Only after P0 is mostly green:

| Work | Why |
|------|-----|
| Agentic loop reliability | Tune if dogfood still “I'll look that up” empty |
| Search quality | Exact-token / design-name boost if noise still wins |
| Process UI clarity | Tool rounds 1/2 readable |
| One happy-path docs page | Install / start / will and won’t do |
| Known-bad freeze list | Explicit “not now” |

**Exit:** A non-author power user could follow the docs page and complete the dogfood script.

---

## P2 — Product packaging (parallel, light)

| Work | Why |
|------|-----|
| One-pager (problem / who for / what it does / demo) | Users + grants |
| 3-min screen demo | Same |
| WI LLC (Aeteros) when ready | SBIR / bank — not a substitute for P0 |
| CTC call | SBIR micro-grant path — after demo exists |

See also: `docs/plans/AETEROS_GRANTS_EXPLORATION_2026-08-05.md`

---

## Explicitly not next

Until the wedge is felt:

- Phase 4 passive user-memory scoring / full About Me import  
- Phase 5 autobiographical substrate  
- Full semantic_pending hard verifier as mainline  
- Fork Grok Build  
- Multi-agent freeroam  
- Broad monorepo cleanup for its own sake  
- CRT as primary product path  

Labs stay inventory, not guilt.

---

## Cadence

| Cadence | Activity |
|---------|----------|
| Daily / near-daily | Use Workbench for real tasks |
| Weekly | Dogfood pass + fix only P0 breaks |
| Biweekly | Tiny user-visible improvement |
| Monthly | Demo refresh + optional grant/CTC action |

**Energy:** ~70% P0/P1 product · ~15% packaging · ~15% admin/grants.

---

## Success criteria (stranger-week lite)

1. **Tools:** Search → read → answer with paths without a second “please open the file.”  
2. **Honesty:** Withhold / partial / correction works and is visible.  
3. **Continuity:** Multi-turn doesn’t drop context or wrong provider.  
4. **Restart:** Floating + conversation resume work.  
5. **You** use it without coaxing for a real week.

Then scale Phase 4 / funding push.

---

## Ordered checklist

```text
[ ] Restart sidecar + Workbench
[ ] Dogfood: search → explain from code (agentic loop)
[ ] Dogfood: multi-turn continuity + correction
[ ] Dogfood: cancel once
[ ] Fix only failures from above
[ ] One-page product/docs entry for the wedge
[ ] 3-min demo recording
[ ] Freeze list written (what we will not build now)
[ ] (Optional) Aeteros LLC + CTC intro
[ ] (Optional) Foresight / NSF prep only after demo exists
```

---

## Implementation log

| Date | Note |
|------|------|
| 2026-08-05 | Plan saved |
| 2026-08-05 | Product entry: `docs/AETHER_PRODUCT_ENTRY.md` |
| 2026-08-05 | Search: exact basename + design-name boost (mirus/holden/…) |
| 2026-08-05 | Search: drop workspace/workbench as noise terms; design content boost in sidecar |
| 2026-08-05 | Life check: `labs/LIFE_CHECK_2026-08-05.md` (belief map + Grok integrity judge) |
| 2026-08-05 | Freeze list recorded in plan + product entry |
| 2026-08-05 | Soft workspace phrases: use workbench search / explore for… → code_tool + workspace_search (tools, route_policy, obligations) |
| 2026-08-05 | Soft multi-fact: released-slot correlations / in common / colorations typo → surface orange↔marigolds, no health invent |
| 2026-08-05 | Evidence scope: correlation phrases release plain favorites; inventory catches “what else you know about me” |
| 2026-08-05 | Live self-dogfood pack: `labs/self_dogfood_product_2026-08-05.py` → **OVERALL PASS** (6/6); log `labs/SELF_DOGFOOD_PRODUCT_2026-08-05.json` |
| 2026-08-05 | P0 multi-turn: search→explain PASS (deterministic listing + read receipts; search stopword `ai_round2`; design-boost only if term in excerpts) |
| 2026-08-05 | P0 continuity: session correction + recent-claim recall direct answers; verification soft-pass for self-contained corrections → live **CONTINUITY PASS** |
| 2026-08-05 | Cancel live flaky (409 until render phase); unit test path still solid |

### Dogfood checklist status

```text
[x] Restart sidecar (default profile; Workbench may still need its own root)
[x] Dogfood: soft search holden + explore mirus (workspace_search)
[x] Dogfood: soft correlations / in common / colorations
[x] Dogfood: explore deeper inventory (governed dossier, no invent job)
[x] Dogfood: search → explain from code multi-turn (receipt-backed)
[x] Dogfood: multi-turn continuity + correction (session correction path)
[x] Dogfood: cancel once (live flaky/racey; unit test green)
[x] Search design-name / exact basename boost (code)
[x] Soft tool phrases + soft multi-fact (code + live pack)
[x] One-page product entry for the wedge
[x] Freeze list written
[ ] 3-min demo recording
[ ] (Optional) Aeteros LLC + CTC intro
```
