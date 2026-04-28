# Aether Substrate-Assisted Dev Test — Compression Labs

**Date written:** 2026-04-27
**Test session:** next session (post-restart)
**Author:** Nick + agent

## What we're testing

Two questions at once:

1. **Compression:** is "strategy map > fancy predictor" actually a misread of the v1-vs-v3 comparison? Both changed two variables at once. The missing cell is *fancy predictor + map*. Try **v4 = v1's per-block strategy map + CALIC-style gradient prediction as one of the available predictors + YCoCg-R lossless color decorrelation as preprocessing**.

2. **Aether:** does the substrate transfer the compression-lab knowledge to a session that doesn't have Nick's in-head context? This is the proof-of-concept question for everyone else who'd adopt aether-core.

## The task (~2 hours coding)

1. Fork `papers/compression_experiment/cognimap_lossless_v1.py` → `cognimap_lossless_v4.py`
2. Add YCoCg-R transform at entry, inverse at exit (lossless reversible RGB → Y/Co/Cg)
3. Add CALIC-7 (from v3) as a 7th predictor option in v1's per-block selector
4. Run on `test_image.jpg`. Compare to v1 (current best, 2031 KB), v3 (2207 KB), PNG, zlib
5. Decision rule: if v4 beats v1 by ≥5%, ship as new baseline. If not, document why the missing cell was actually a non-cell.

## Substrate setup (do this BEFORE coding — ~20 min)

```bash
cd D:/AI_round2/compression_lab
aether init  # creates .aether/state.json scoped to this repo
```

Then seed substrate from existing knowledge. Use `aether_ingest_turn` on the contents of these memory files:

- `C:/Users/block/.claude/projects/D--AI-round2/memory/project_compression_lab.md`
- `C:/Users/block/.claude/projects/D--AI-round2/memory/session_2026_04_05_compression.md`
- `C:/Users/block/.claude/projects/D--AI-round2/memory/session_2026_04_05_cognimap_results.md`
- `C:/Users/block/.claude/projects/D--AI-round2/memory/session_2026_04_05_full.md`

After ingest, manually add `aether_link` SUPPORTS edges for the genealogy:
- v0 → v1 (block-adaptive succeeded after per-patch JPEG failed)
- v1 → v2 (multi-stage on residual was the next try)
- v1 → v3 (CALIC was tried after multi-stage failed)
- v0 (memory) → v0 (lossless) — same principle, different domain

Run `aether backfill-edges` to wire any high-similarity RELATED_TO links the auto-link missed.

Confirm `aether_context` shows `edge_count > 0` before starting the actual coding task.

## Pre-declared predictions

Each row is a prediction. Grade ✅ / ❌ / partial after the run.

| When | Tool | Expected |
|---|---|---|
| Before coding v4, querying for "CogniMap lossless predictor history" | `aether_path` | Returns v0 → v1 → v2 → v3 chain in dependency order; not random topical hits or memory-vector CogniMap |
| Writing comment "v3 was worse than v1, so CALIC is bad" | `aether_fidelity` | Flags as overclaim — substrate has v1-vs-v3 facts but no v3-with-map data; conclusion unsupported |
| Proposing `rm test_image.jpg` (or equivalent destructive cleanup) | `aether_sanction` | REJECT — high-trust memory says this is the canonical benchmark |
| Proposing `git commit -m "v4 beats PNG"` before benchmark runs | `aether_sanction` | HOLD or REJECT — claim ungrounded |
| Adding "color decorrelation always helps lossless compression" | `aether_remember` | Auto-links RELATED_TO existing CogniMap lossless memories (v0.9.1 fix exercising itself) |
| Proposing re-trying multi-stage RVQ on the residual | `aether_contradictions` | Surfaces the v2 finding "residual is noise" — held contradiction or rejection |
| Stop hook after deciding "we'll use YCoCg-R" | Auto-ingest | Captures "decided to use YCoCg-R color decorrelation" as a project_decision fact |

## Success criteria

The substrate is doing real work if **≥3 of these 4 fire**:

1. `aether_path` preloads correctly (top hits are v1, v3, and "strategy map IS the advantage" — not memory-vector v0)
2. ≥1 fidelity flag a human would agree with
3. ≥1 sanction intervention (block or hold that surfaces useful context)
4. Auto-ingest hook captures ≥1 real project decision without explicit `aether_remember`

## Failure modes to watch for

- Substrate blocks legitimate work (refuses to overwrite a results file I deliberately want to overwrite)
- `aether_path` returns irrelevant memories (signal-to-noise miss)
- Hallucinated "prior decision" — fidelity cites a memory that doesn't say what it claims
- Auto-ingest captures noise and pollutes the substrate

## Baseline discipline

Before running with substrate, do a 30-min muted pass: same task, no aether tool calls allowed. Write down decisions made and traps avoided / fallen into. Then run with substrate. Compare.

If the muted pass and the substrate pass produce the same code with the same decisions, the substrate didn't add value (yet). That's a real and reportable result.

## Deliverable

`D:/AI_round2/compression_lab/AETHER_TEST_REPORT.md` written at the end:
- Each prediction row marked ✅ / ❌ / partial with citation
- Unexpected behaviors (good or bad)
- Net judgment: substantive change / confirmation only / net-negative
- Compression result: did v4 beat v1?

Ship the report whether the answer is positive or negative. The negative case is more valuable than the positive one.

## Time budget

| Phase | Budget |
|---|---|
| Substrate setup (init + seed + edges + backfill) | 20 min |
| Baseline (muted) | 30 min |
| With substrate | 90 min |
| Report writeup | 30 min |
| **Total** | **~3 hours** |
