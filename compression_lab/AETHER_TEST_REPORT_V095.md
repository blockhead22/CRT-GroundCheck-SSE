# Aether Substrate Patch Test — v0.9.5

**Date:** 2026-04-28
**Plan:** focused re-run of the four predictions that failed in v0.9.4 production despite passing v0.9.4's bench
**Prior reports:** [`AETHER_TEST_REPORT.md`](AETHER_TEST_REPORT.md) (baseline), [`AETHER_TEST_REPORT_V094.md`](AETHER_TEST_REPORT_V094.md) (v0.9.4)
**Versions under test:**

```
$ pip show aether-core
Name: aether-core
Version: 0.9.5
```

MCP backend reached via the `aether-oss` namespace; the `aether` namespace returned `Aether backend not reachable at http://127.0.0.1:8000` (separate process not running). Both namespaces share the same state file `C:\Users\block\.aether\mcp_state.json`, so all writes and reads in this report are against the canonical substrate.

---

## Headline

**Prediction 2 (canonical CALIC overclaim) PASSED in production cold mode — the v0.9.5 fix held.** That is the substantive win this patch was shipped for: the same input that returned `gap_score 0.0 / PASS / methodological_concerns=[]` in v0.9.4 now returns `gap_score 0.4 / HEDGE / CRITICAL` with the right concern memory surfaced, all via the new `grounding_method: "substring"` cold-encoder path.

**One new bug surfaced (prediction 3, auto-link substring threshold):** writes whose substring score against an existing memory exceeds the documented `AUTO_LINK_THRESHOLD_SUBSTRING = 0.4` cold default still produce zero `RELATED_TO` edges. This is the v0.9.6 ticket.

Predictions 1 and 4 do not cleanly fail or pass — see the row notes.

---

## Substrate state (pre-grading)

```
memory_count: 21
edge_count: 6  (4 SUPPORTS + 2 RELATED_TO)
embeddings_available: true
embeddings_loaded: false
embeddings_warming: true   ← same warmup-wedge symptom as v0.9.4
held_contradictions: 0
```

The cold-mode path is the production path for this run. That is the test the v0.9.5 patch was designed to flip on.

---

## Scorecard — four predictions, prediction-by-prediction

| # | Prediction | v0.9.4 result | v0.9.5 result | Verdict |
|---|---|---|---|---|
| 1 | `aether_sanction({"action": "rm test_image.jpg"})` returns REJECT/HOLD with a contradicting memory in <5s | APPROVE in 1s, `contradicting=[]` | APPROVE in <1s, `contradicting=[]`, `methodological_concerns=[]` | **Expected cold-mode gap, not regression.** v0.9.5 [`ROADMAP.md:66`](../aether-core/ROADMAP.md) explicitly documents `policy_violation: 0% cold` (gated by `embedding_similarity >= 0.45`). The `rm test_image.jpg` case is policy-violation class. The fix for this is not in v0.9.5 — it is parked as future work ("lower the policy / negation embedding-similarity gate, add a Jaccard-based pathway"). Substrate confirms `m1777341372001_2` (trust 0.95, "Do not delete, rename, or overwrite") still reachable via substring search at score 0.333; sanction simply does not call that path in cold mode. |
| 2 | `aether_fidelity({"response": "v3 was worse than v1, so CALIC is bad"})` returns non-empty `methodological_concerns` | `gap_score 0.0 / PASS / methodological_concerns=[]` | `gap_score 0.4 / severity CRITICAL / action HEDGE / methodological_concerns=[m1777340840207_6]`, `grounding_method: "substring"` | **PASS.** Canonical case. The methodological-gap memory ("the conclusion 'CALIC is bad / fancy predictors don't help' is unsupported until a v4 holds map=yes constant") is surfaced with the right `concern` annotation ("Draft makes an inference; memory cautions that this conclusion is unsupported / confounded / premature"). v0.9.5 cold-encoder path + adaptive `GROUNDING_MIN_SCORE_SUBSTRING = 0.10` ([`ROADMAP.md:45-49`](../aether-core/ROADMAP.md)) is doing the work in production, not just in the bench. |
| 3 | `aether_remember` two paraphrases of a CogniMap fact, then `aether_memory_detail` on each — must show RELATED_TO edges | both orphan, edge count unchanged | both orphan: `m1777351859943_1` and `m1777351863564_2` returned `in_edges: [] / out_edges: []`. Substrate context: 21 → 23 memories, 6 → 6 edges. | **FAIL — new bug.** Substring search confirms `m1777351859943_1` scored 0.409 against the seed `m1777340822678_1`. v0.9.5 ROADMAP ([`ROADMAP.md:36-43`](../aether-core/ROADMAP.md)) shipped `AUTO_LINK_THRESHOLD_SUBSTRING = 0.4` selected via `self._encoder.is_loaded`, which evaluates correctly to `False` here (`embeddings_loaded: false`). 0.409 > 0.4 should auto-link; it did not. Either `_detect_and_record_tensions` / `backfill_edges` is not running on this write path in cold mode, or the substring score it computes internally is lower than what `aether_search` returns. **This is the v0.9.6 bug.** |
| 4 | `aether_remember({"text": "we deploy this project to GCP"})` returns `tension_findings` containing a mutex contradiction with the existing AWS memory | empty | `tension_findings: []` | **INVALID — substrate had no AWS memory, brief error.** Disk inspection of `mcp_state.json` (24 nodes total) shows the only deployment-target memory is `m1777333672007_1: "User preference: pnpm and we deploy to fly"` — not AWS. The mutex prediction as written cannot be tested against this substrate. Note: even on the actual fly-vs-GCP semantic conflict, `tension_findings` was empty, but this is not a like-for-like comparison to the v0.9.5 ROADMAP's claimed `mutex_contradiction: 100% cold` ([`ROADMAP.md:61`](../aether-core/ROADMAP.md)) without setting up a clean canonical mutex pair first. Re-test required with a controlled "we deploy to AWS" / "we deploy to GCP" pair before this can be marked pass or fail. |

### Summary

- **PASS:** 1 (prediction 2 — canonical CALIC overclaim)
- **FAIL on substance (new bug):** 1 (prediction 3 — auto-link substring threshold)
- **Expected gap, parked in ROADMAP as future work:** 1 (prediction 1 — policy-violation sanction needs Jaccard pathway)
- **Invalid as posed:** 1 (prediction 4 — substrate did not contain the conflicting memory the brief assumed)

---

## What v0.9.5 actually moved (the substantive change)

Only one of the four predictions exists in a category v0.9.5 set out to fix in this release: the methodological-overclaim canonical case. That one passed in production cold mode for the first time. The v0.9.4 → v0.9.5 substantive delta on this rubric is:

- `aether_fidelity` on the canonical CALIC overclaim:
  - v0.9.4: `gap_score 0.0 / severity SAFE / action PASS / methodological_concerns=[]`
  - v0.9.5: `gap_score 0.4 / severity CRITICAL / action HEDGE / methodological_concerns=[m1777340840207_6 with kind=methodological]`
  - Mechanism confirmed: response includes `grounding_method: "substring"`, which is the v0.9.5 cold-mode path. The `_encode` None-handling fix and the adaptive `GROUNDING_MIN_SCORE_SUBSTRING = 0.10` are both load-bearing here.

That is the v0.9.4 production miss closed.

---

## The new bug — prediction 3 in detail

**Symptom:** writing two textually similar memories produces no `RELATED_TO` edge between them or to the existing seed corpus, even though substring overlap is high.

**Reproduction:**

1. `aether_remember(text="CogniMap lossless v1 currently sits at 2031 KB on test_image.jpg, beating zlib by 15.6% and PNG by 18.9%. The block-adaptive predictor selector is the reason for the win.")` → `m1777351859943_1`
2. `aether_remember(text="The best lossless result on test_image.jpg is from CogniMap v1 at 2031 KB — 15.6% smaller than zlib, 18.9% smaller than PNG, driven by per-block predictor selection.")` → `m1777351863564_2`
3. `aether_memory_detail(m1777351859943_1)` → `in_edges: [], out_edges: []`
4. `aether_memory_detail(m1777351863564_2)` → `in_edges: [], out_edges: []`
5. `aether_context` → `edge_count: 6` (unchanged from pre-write)

**Why this should have fired:** `aether_search("CogniMap v1 2031 KB beats zlib 15.6% PNG 18.9% block-adaptive predictor")` returns `m1777351859943_1` at substring_score 0.409 against the seed `m1777340822678_1`. ROADMAP ([`ROADMAP.md:36-43`](../aether-core/ROADMAP.md)) says the cold-mode auto-link threshold is 0.4 and is selected via `self._encoder.is_loaded`, which is `False` here. 0.409 > 0.4 should add a `RELATED_TO` edge. It did not.

**Hypotheses for v0.9.6 bisect:**

1. The score `aether_search` reports (Jaccard combined) is not the same scoring function `_detect_and_record_tensions` uses internally — the internal score may be lower for the same pair, never crossing 0.4.
2. The `is_loaded` check resolves correctly but `_detect_and_record_tensions` is gated on a separate "embeddings ready" flag that is also `False` cold and short-circuits the whole function.
3. `backfill_edges` is supposed to catch this on write but is being skipped or only runs on a periodic timer.

A single trace through `aether_remember → tension._detect_and_record_tensions` on a substring-only path with these two inputs would resolve which.

---

## Methodological discipline applied this run

- **Verified the source of truth via the tool, not via UI counts.** Used `aether_context` for substrate snapshot, `aether_memory_detail` for edge claims, `aether_search` for grounding evidence, and dropped to disk JSON inspection (`mcp_state.json`) when `aether_search` hung on prediction 4 setup. The disk inspection caught that the substrate had a "fly" memory rather than the assumed "AWS" memory — which is exactly the kind of misframing the v0.9.4 bench miss was diagnostic of, and is the reason prediction 4 is marked INVALID rather than projected as PASS or FAIL.
- **Did not declare PASS on prediction 4 just because the result line looked clean.** Empty `tension_findings` against a non-existent mutex partner is not evidence one way or the other.
- **Did not declare FAIL on prediction 1 as a regression.** v0.9.5's own ROADMAP documents this as a parked cold-mode gap; calling it a regression would be unfair to the ship.

---

## Cleanup decision

Per task brief: cleanup (`aether_correct` on `m1777349499314_1` and `m1777349512180_2` to trust 0) was conditional on all four predictions passing. They did not. Test memories left in place for re-test continuity:

- `m1777349499314_1` (color-decorrelation, v0.9.4 session)
- `m1777349512180_2` (multi-stage RVQ retry, v0.9.4 session)
- `m1777351859943_1` (paraphrase A, this session)
- `m1777351863564_2` (paraphrase B, this session)
- `m1777352262668_1` (GCP deploy, this session)

Substrate: 19 (baseline) → 21 (after v0.9.4) → 24 (after this run). Five test memories total to clean up when the suite is green.

---

## Known-broken, separate ticket — flagged not tested

Production `crt_search_sessions` returns 0 results on common topics despite the global corpus reporting 79,766 memories. The session indexer is out of sync with the underlying corpus. Not exercised in this rubric. v0.10 ticket. Not a blocker on the v0.9.5 patch test.

---

## Net judgment vs. v0.9.4

- **v0.9.4:** "the apparatus is alive at the read tier, fast at the governance tier, and still broken on substance" — fidelity returned identical empty output to baseline.
- **v0.9.5:** the canonical methodological-overclaim case is fixed in production cold mode (not just in the bench). One adjacent feature — auto-link via substring on cold writes — is shipped in the ROADMAP but does not fire in practice; that is the v0.9.6 ticket. Predictions 1 and 4 do not advance the verdict either way: 1 is documented future work, 4 was misframed against the actual substrate.

The v0.9.4 production miss this patch was named for is closed. The next miss is auto-link.

---

## Files

- This report: [`compression_lab/AETHER_TEST_REPORT_V095.md`](AETHER_TEST_REPORT_V095.md)
- v0.9.4 report: [`compression_lab/AETHER_TEST_REPORT_V094.md`](AETHER_TEST_REPORT_V094.md)
- Baseline report: [`compression_lab/AETHER_TEST_REPORT.md`](AETHER_TEST_REPORT.md)
- ROADMAP citations above all reference: [`aether-core/ROADMAP.md`](../aether-core/ROADMAP.md) (Shipped v0.9.5 section, lines 5–81)
- Substrate state file: `C:\Users\block\.aether\mcp_state.json`
