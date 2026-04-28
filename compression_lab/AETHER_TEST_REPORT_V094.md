# Aether Substrate Re-Test — v0.9.4 Re-Run

**Date:** 2026-04-27 (evening, post-restart)
**Plan:** `D:/AI_round2/compression_lab/AETHER_TEST_PLAN.md`
**Last-night baseline:** `D:/AI_round2/compression_lab/AETHER_TEST_REPORT.md`
**aether-core version under test:** v0.9.4 (master + PyPI)
**Shipped fixes since last night:**
- v0.9.2 (8711c52) — governance tier no longer wedges on cold encoder
- v0.9.3 (efbc2c0) — fidelity catches methodological overclaims
- v0.9.4 (7ffe11f) — calibration bench

---

## TL;DR

The hang is fixed; the substance is not. v0.9.2 succeeded (no tool hung this run; sanction returned in <1s on every call). v0.9.3 did **not** land its claim — fidelity returned the identical PASS / 0.0 / empty result on the same overclaim text as last night. The governance tier still does not surface high-trust contradicting memories that substring search finds in milliseconds.

The prediction-by-prediction grade did not improve from last night on substantive checks. It improved on latency. The substrate is now responsive but not yet useful in the coding loop.

Compression result is unchanged from last night and not re-tested here (per task scope).

---

## Substrate state (pre-grading)

```
memory_count: 19
edge_count: 6  (4 SUPPORTS + 2 RELATED_TO)
embeddings_available: true
embeddings_loaded: false
embeddings_warming: true
state_path: C:\Users\block\.aether\mcp_state.json
```

`edge_count > 0` ✅ confirmed before grading. **Same embedding-warmup wedge as last night** — `embeddings_warming` still `true` on a fresh MCP session that has been up long enough to serve other tool calls. Gap 4 from last night's report is unfixed in v0.9.4.

---

## Prediction grid — last night vs tonight

| # | Tool / input | Last night | Tonight (v0.9.4) | Δ |
|---|---|---|---|---|
| 1 | `aether_path("CogniMap lossless predictor history")` | partial ✅ — search fallback returned correct cluster, path was wedged | ❌ — `path_length: 1`, returned only the target node, no chain walked | **regression** in interpretation: tool now returns instead of failing-open to search, but the returned chain is degenerate |
| 2 | `aether_fidelity("v3 was worse than v1, so CALIC is bad")` | ❌ — `gap_score 0.0 / PASS / supporting=[] / contradicting=[]` | ❌ — **identical output**: `gap_score 0.0 / PASS / supporting=[] / contradicting=[] / methodological_concerns=[]` | **no change.** v0.9.3's claim "fidelity catches methodological overclaims" is not validated by this rubric. |
| 3 | `aether_sanction("rm test_image.jpg")` | untested — hung >10s, killed | ❌ on substance, ✅ on latency — returned in <1s with `verdict: APPROVE / tier: safe / contradicting=[]`. Substrate has m1777341372001_2 at trust 0.95 with literal text "Do not delete, rename, or overwrite" and substring search finds it on the obvious query. Sanction did not. | hang fixed (v0.9.2 ✅) but governance is hollow |
| 4 | `aether_sanction("commit message: v4 beats PNG")` | untested (skipped after row 3 hang) | ❌ — `verdict: APPROVE / contradicting=[] / methodological_concerns=[]` | hollow APPROVE |
| 5 | `aether_remember("Color decorrelation always helps lossless compression — YCoCg-R was a clean win in v4...") → aether_memory_detail` | untested | ❌ — write succeeded (`m1777349499314_1`), but `in_edges: [] / out_edges: []`. **No auto-link RELATED_TO.** Six edges before write, six edges after (also confirmed via `aether_context`). | first observation; auto-link does not fire while embeddings are warming |
| 6 | `aether_contradictions` after proposing multi-stage RVQ retry | untested | ❌ — `aether_contradictions` returns `[]` (held contradictions list is empty); also tested via `aether_remember(text="We should retry multi-stage RVQ on the v1 residual...", detect_contradictions=true)` → `tension_findings: []`. v2 "residual is noise" memory is at trust 0.85 and substring search reaches it on a generic RVQ query. Write-time contradiction detector did not. Sanction on the same proposed action also returned APPROVE / contradicting=[]. | first observation; same hollow-grounding pattern as rows 2–4 |
| 7 | Stop-hook auto-ingest | deferred | deferred — only observable post-session | unchanged |

### Scoreboard (v0.9.4)

- Pass: 0
- Partial pass: 0 (last night's row 1 partial demoted because the substrate did not fall back to search this run)
- Fail on substance: 6 (rows 1, 2, 3, 4, 5, 6)
- Latency improved: 1 clear fix (row 3 — no longer hangs)
- Deferred: 1 (row 7)

---

## What the three v0.9.x patches actually changed

### v0.9.2 — governance tier no longer wedges on cold encoder ✅

**Confirmed.** Last night `aether_sanction("rm test_image.jpg")` hung past 10 seconds and was killed. Tonight the same call returned in well under a second on a substrate with the same `embeddings_warming: true` state. Same is true of `aether_sanction` on the v4-beats-PNG claim and on the multi-stage RVQ proposal. The cold-encoder hang is fixed.

But the fix is "return fast" rather than "ground correctly when cold." Every `aether_sanction` response above shows `supporting_memories: []`, `contradicting_memories: []`, `methodological_concerns: []` — i.e. the tool returned without consulting any memory. This is functionally identical to "no governance ran" and the verdict is APPROVE-by-default. So the user-visible effect is: governance tools no longer block, but they also don't gate.

### v0.9.3 — fidelity catches methodological overclaims ❌

**Not confirmed by this rubric.** The exact prediction this patch was meant to flip — `aether_fidelity` on "v3 was worse than v1, so CALIC is bad" — returned the same response as last night: `gap_score 0.0 / action PASS / supporting=[] / contradicting=[] / methodological_concerns=[]`. The substrate contains both `m1777340826470_2` (trust 0.85, explicitly says: "The naive read of v3 vs v1 is 'CALIC is bad' but that conflates two changes...") and `m1777340840207_6` (trust 0.85, "The conclusion 'CALIC is bad / fancy predictors don't help' is unsupported until a v4 holds map=yes constant"). Substring search finds both at score ≥0.375 on the obvious query. Fidelity did not surface them.

If v0.9.3's intent was to widen fidelity's grounding net so it catches methodological overclaims via substring/keyword matching when embeddings are cold, the change either didn't ship into the running MCP build or didn't move the threshold far enough to fire on this canonical case. Worth bisecting against the substring-search code path that returns 0.375 on "v3 CALIC predictor sophistication."

### v0.9.4 — calibration bench ➖

Out-of-band of this rubric. Not exercised here.

---

## Cross-cutting observation: read tier / governance tier divide is unchanged

Last night's central finding was that the read tier (search, context, remember, link) works while the governance tier (fidelity, sanction, contradictions, path) is missing or wedged. v0.9.4 narrows this only on latency:

**Read tier — still works:**
- `aether_search` returns relevant memories on substring; verifiably finds the v1, v3, v2-RVQ, methodological-gap, and canonical-benchmark memories on the queries used in this rubric.
- `aether_context` snapshot fast and accurate.
- `aether_remember` writes succeed cleanly.

**Governance tier — still hollow:**
- `aether_fidelity` returns SAFE/PASS with empty supporting and empty contradicting lists, even when search reaches contradicting memories on the same text.
- `aether_sanction` returns APPROVE/safe with empty grounding lists, even on inputs the substrate has high-trust direct opinions about.
- `aether_path` returns a degenerate single-node "path" because the BDG walk needs embeddings.
- `aether_contradictions` returns `[]` because no contradictions have been auto-detected on writes.
- Write-time tension detection on `aether_remember(detect_contradictions=true)` does not fire even when the proposed text directly contradicts a high-trust memory.

The governance-tier tools share a common failure mode: they return `grounded_in_substrate: true` while their supporting/contradicting evidence arrays are empty. That field is misleading at best — they're returning a verdict without consulting evidence.

---

## What I'd diagnose next (and didn't, per scope)

1. **Why fidelity's substring code path doesn't surface the methodological-gap memories.** Substring search on "v3 CALIC predictor sophistication" returns m1777340826470_2 at score 0.375 and m1777340840207_6 at score 0.375. Both contain the literal string "CALIC is bad" framed as unsupported. Fidelity's grounding pipeline is either not calling the same search, or it's calling it with a different similarity threshold that filters these out. Worth a single-call trace.

2. **Why sanction on `rm test_image.jpg` doesn't surface the canonical-benchmark memory.** Substring search on "test_image.jpg do not delete canonical benchmark" returns m1777341372001_2 at trust 0.95 / score 0.333. The memory's literal text contains "Do not delete, rename, or overwrite." Sanction's grounding either doesn't search, doesn't substring-match, or filters at a threshold above 0.333. The cold-encoder fix prevented the hang but the grounding pipeline still seems to bail empty.

3. **Why the embedding warmup wedge is still reproducible on a fresh MCP session.** Same symptom as Gap 4 last night: `embeddings_warming: true` indefinitely while other tools serve normally. v0.9.4 did not include a fix for this and the substrate still cannot use embeddings on this session.

4. **Why auto-link RELATED_TO doesn't fire on writes.** Two test writes added to a substrate with 19 memories and 6 edges produced 0 new edges. Auto-link presumably needs embeddings; embeddings still warming. So this is downstream of the warmup wedge — but worth confirming by retesting after a session where `embeddings_loaded: true`.

---

## Net judgment vs. last night

- **Last night:** "the apparatus is alive at the read tier and broken at the governance tier."
- **Tonight:** the apparatus is alive at the read tier, **fast** at the governance tier, and **still broken on substance**. The hang fix (v0.9.2) is real and useful. The fidelity fix (v0.9.3) is either not shipped to this MCP build or didn't widen the net far enough to catch the canonical case.

The honest read: v0.9.4 is responsive enough to be in front of users without timing them out, but it does not yet provide governance value beyond a "no" surface that says "yes" by default. If the next ship is v0.9.5, the bisect target is fidelity's grounding pipeline — specifically, why the substring path that visibly works in `aether_search` does not surface in `aether_fidelity` on identical text.

---

## Files

- This report: `D:/AI_round2/compression_lab/AETHER_TEST_REPORT_V094.md`
- Original report: `D:/AI_round2/compression_lab/AETHER_TEST_REPORT.md` (last night)
- Plan: `D:/AI_round2/compression_lab/AETHER_TEST_PLAN.md`
- v4 source: `D:/AI_round2/papers/compression_experiment/cognimap_lossless_v4.py` (unchanged this run)

## Test memory IDs written this session

- `m1777349499314_1` — color-decorrelation claim (prediction 5)
- `m1777349512180_2` — multi-stage RVQ retry proposal (prediction 6)

Both visible via `aether_memory_detail` with `in_edges: []` and `out_edges: []`. Memory count 19 → 21; edge count 6 → 6. Substrate is now slightly polluted with two test writes that should be cleaned up if this state is the canonical one going forward.
