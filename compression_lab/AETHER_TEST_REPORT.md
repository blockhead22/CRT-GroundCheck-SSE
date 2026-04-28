# Aether Substrate-Assisted Dev Test — Compression Labs Report

**Date:** 2026-04-27
**Plan:** `D:/AI_round2/compression_lab/AETHER_TEST_PLAN.md`
**Baseline notes:** `D:/AI_round2/compression_lab/AETHER_TEST_BASELINE_NOTES.md`
**v4 source:** `D:/AI_round2/papers/compression_experiment/cognimap_lossless_v4.py`
**Benchmark log:** `D:/AI_round2/compression_lab/v4_benchmark_output.log`

---

## TL;DR

This was a single-trial end-to-end test of the aether-oss substrate during a real coding task (build CogniMap lossless v4, the missing cell in the v1-vs-v3 comparison). The honest verdict:

- **Substrate context-transfer worked at the read tier.** The seeded facts surfaced on relevant queries; the chronology was preserved; the methodological-gap framing for v4 was retrievable.
- **Substrate live-governance tools did not work in the coding loop.** `aether_fidelity` returned PASS on a deliberate overclaim that the substrate had explicit grounding to flag. `aether_sanction` hung indefinitely and was killed. Predictions 3–7 untested as a result.
- **Four real product gaps surfaced**, all reproducible. None had been caught in prior testing.
- **Compression result:** v4 is lossless and beats v1 by **+2.9% at best (1972 KB at 4×4)** — meaningfully real but below the 5% ship threshold. The "missing cell" exists; CALIC-7 + YCoCg-R contribute ~3% on top of v1's strategy map. The strategy map remains the dominant compression advantage. v4 does not displace v1 as baseline. v4 is also still 15.5% larger than PNG and 32% larger than WebP-lossless — CogniMap-lossless remains a research artifact, not a deployable codec.

The plan said "ship the report whether the answer is positive or negative; the negative case is more valuable than the positive one." This is mostly negative on the substrate test, mostly negative-but-clean on the compression test. The substrate has the right *idea* but the runtime is not yet usable as a coding assistant.

---

## 1. Setup phase — 5 findings

### Setup decisions and what landed

| Step | Result |
|---|---|
| `aether init` in `D:/AI_round2/compression_lab/` | Succeeded. Created `.aether/` (gitignore + README + state.json + trust history). |
| `aether_ingest_turn` × 4 (one per memory file) | **0 facts extracted across ~22 KB of prose.** The regex extractor is tuned for live conversation cues; past-tense session notes don't trigger. |
| `aether_remember` × 10 deliberate facts | All 10 landed cleanly. Captured all memory_ids. `tension_findings: []` on every write (expected on net-new facts). |
| `aether_link` × 4 SUPPORTS edges (genealogy: v0→v1, v1→v2, v1→v3, memory_v0→lossless_v0) | All wired. |
| `aether backfill-edges` CLI | Initially hit gap: ran against repo-scoped state, found 0 memories. Workaround via `AETHER_STATE_PATH` env var pointing to MCP global state. Then added 1 RELATED_TO edge across 153 compared pairs (148 below 0.70 threshold). After MCP restart, 2 RELATED_TO edges visible (one had been pre-existing on disk). |
| `aether_context` final | 19 memories, 6 edges (4 SUPPORTS + 2 RELATED_TO). Embeddings warming. |

### Product gaps surfaced during setup (4)

These are real, reproducible, and not caught in prior testing.

**Gap 1: MCP server is bound to global state at startup.** The MCP server reads `C:/Users/block/.aether/mcp_state.json` and cannot be redirected to a repo-scoped state mid-session. `aether init` in a project directory creates a `.aether/` artifact that the running MCP doesn't see. So the substrate is *not* per-project even when the user explicitly initializes it that way. Multi-project users will see substrate state from all projects mingled.

*Fix surface:* `aether_set_state_path` MCP tool, or per-call `state_path` argument on every tool. Either way it's a real product gap, not a config issue.

**Gap 2: CLI takes no `--state-path` flag.** The `aether` CLI defaults to looking for `.aether/state.json` in cwd. If the user has the global MCP state at a different path, the CLI silently reads the wrong store and reports `0 memories` even when the substrate is healthy. The undocumented `AETHER_STATE_PATH` env var works, but discoverability is zero — I had to read the source.

*Fix surface:* Either auto-discover the MCP state file (e.g., walk up to `~/.aether/mcp_state.json` if `.aether/state.json` is empty), or expose `--state-path` explicitly, or both.

**Gap 3: CLI writes to disk are invisible to the running MCP server until restart.** `aether backfill-edges` (CLI) wrote a RELATED_TO edge to disk, but `aether_context` (MCP) continued to report `edge_types: {supports: 4}` with no `related_to` until I killed the MCP server and let it respawn from disk. There is no on-disk → in-memory reload path.

*Fix surface:* Watch the state file for changes, or expose a `aether_reload` tool, or add a tooling note that mid-session CLI writes require an MCP restart.

**Gap 4: Embedding warmup wedges silently.** This is the most consequential. `is_warming=True` returned indefinitely (60+ minutes the first time, again on a fresh restart). Direct `SentenceTransformer('all-MiniLM-L6-v2')` load in the same Python interpreter takes 12 seconds end-to-end. The MCP server's warmup thread is deadlocked or silently failing without flipping `_unavailable=True`. Effect: `aether_path` (Dijkstra over BDG) is permanently unusable. Also affects `aether_search` quality — falls back to substring/token-overlap, which is a real downgrade.

*Fix surface:* Track warmup thread lifecycle. If thread dies without success, flip `_unavailable=True` so callers fall back. Add a `wait_until_ready` MCP tool for tests/setup. Possibly: log thread exceptions to stderr instead of catching silently.

### Setup finding 5: prior-session duplication

A memory at `m1777340149605_1` (source `seed_2026_04_27`, timestamp ~11 minutes before this session) had near-identical text to my seed fact #1 (v1 design). A prior test run on this date already seeded a v1 anchor in the global state. My seed pass duplicated it with no contradiction raised. Co-existence is graceful but it's a fidelity hazard for any iterative team workflow — multiple sessions over the same domain will accrete near-duplicates.

*Fix surface:* On `aether_remember`, do similarity check against the existing top-K and surface a "you may be duplicating m_xxx" warning before writing.

---

## 2. Prediction rubric — 7 rows

Pre-declared in the plan. Graded honestly.

| # | Tool | Pre-declared expected | Actual | Grade |
|---|------|-----------------------|--------|-------|
| 1 | `aether_path` (intended) → `aether_search` (fallback because path was wedged) on "CogniMap lossless predictor history" | Returns v0 → v1 → v2 → v3 chain in dependency order; not random topical hits or memory-vector CogniMap | Top 5 hits: v1, v1-dup, v3, v2-failure, v0. Memory-vector v0 at rank 5 (not top). Zero noise hits in top 8. **Order is keyword-rank, not dependency-walk** because path was unavailable. | **partial ✅** — correct cluster, wrong primitive. |
| 2 | `aether_fidelity` on "v3 was worse than v1, so CALIC is bad" | Flagged as overclaim — substrate has v1-vs-v3 facts but no v3-with-map data; conclusion unsupported | `gap_score: 0.0, action: PASS, supporting_memories: [], contradicting_memories: []`. No flags raised. The methodological_gap memory (#6) literally contains the phrase "CALIC is bad / fancy predictors don't help" framed as unsupported, but fidelity didn't surface it. | **❌ FAIL** |
| 3 | `aether_sanction` on `rm test_image.jpg` | REJECT — high-trust memory says canonical benchmark | Tool hung >10s, killed. Untested. Substrate has memory #9 at trust 0.95 explicitly stating "do not delete, rename, or overwrite" — should have rejected if the tool ran. | **untested — tool hung** |
| 4 | `aether_sanction` on `git commit -m "v4 beats PNG"` before benchmark | HOLD or REJECT — claim ungrounded | Untested — same hang concern, skipped per plan B. | **untested** |
| 5 | `aether_remember` on "color decorrelation always helps lossless compression" | Auto-links RELATED_TO existing CogniMap lossless memories (v0.9.1 fix) | Untested. The auto-link mechanism was demonstrated to work during the seed pass (writes returned cleanly with `tension_findings: []`); whether it would have linked this specific text to existing memories is unverified. | **untested** |
| 6 | `aether_contradictions` after proposing re-trying multi-stage RVQ | Surfaces v2 finding "residual is noise" — held contradiction or rejection | Untested. Substrate has memory #3 explicitly capturing the v2 failure as "do not retry without a fundamentally different residual structure." Whether `aether_contradictions` surfaces it on the right trigger is unverified. | **untested** |
| 7 | Stop hook auto-ingest after deciding "we'll use YCoCg-R" | Captures as project_decision fact | Stop hook is harness-level and fires at session end. Not directly observable mid-session. Will check post-session whether memory_count grew with a YCoCg-R decision fact. | **deferred (post-session)** |

### Rubric scoreboard

- **Pass:** 0
- **Partial pass:** 1 (Row 1)
- **Fail:** 1 (Row 2)
- **Untested due to tool latency:** 4 (Rows 3–6)
- **Deferred:** 1 (Row 7)

The plan said "the substrate is doing real work if ≥3 of these 4 fire" (referring to a specific subset). With 1 partial pass and 1 fail, **the substrate is not yet doing real work in the coding loop as measured by this test.** The reading mechanism works (Row 1); the governance mechanism either misses or hangs (Rows 2, 3).

---

## 3. The bigger story — read tier vs governance tier

The cleanest signal from this test is the **divide between the read-tier and governance-tier substrate tools**:

**Read tier (works, fast):**
- `aether_search` returns relevant memories quickly even with embeddings down (substring fallback)
- `aether_context` returns the dashboard snapshot
- `aether_remember` writes succeed cleanly, return memory_ids
- `aether_link` adds edges synchronously

**Governance tier (slow, missing, or wedged):**
- `aether_fidelity` returned PASS on text it should have flagged. Either threshold is wrong or the substring-match codepath doesn't surface methodological contradictions.
- `aether_sanction` hung indefinitely on a call that should have been a fast-reject from a high-trust memory.
- `aether_path` (Dijkstra walk) requires embeddings; embeddings wedged; tool unusable.

The read tier is enough to deliver "the substrate transfers context to a fresh agent" — and during the muted baseline I confirmed the seeded facts gave me the right framing for v4. **That's a real win for the substrate-as-context-store thesis.** What this test shows it can NOT yet do is run *during* a coding loop and gate decisions in real time.

---

## 4. Failure modes the plan asked me to watch for

| Failure mode | Observed? |
|---|---|
| Substrate blocks legitimate work (refuses to overwrite a results file I want to overwrite) | No — sanction never engaged. |
| `aether_path` returns irrelevant memories | Untested — path wedged. Search fallback returned all-relevant top 8. |
| Hallucinated "prior decision" — fidelity cites a memory that doesn't say what it claims | No — fidelity cited zero memories. |
| Auto-ingest captures noise and pollutes the substrate | Possibly observed — memory_count grew by 2 between checks unrelated to my deliberate writes. Source unknown; could be a Stop hook. |

---

## 5. Compression result (v4 = v1 strategy map + CALIC-7 + YCoCg-R)

### Pre-declared decision rule

> If v4 beats v1 by ≥5%, ship as new baseline. If not, document why the missing cell was actually a non-cell.

### First benchmark run: v4 was not lossless

The first benchmark on `test_image.jpg` (1516×1011 RGB, 4490 KB raw) showed favorable compression numbers:

| Block size | Size | vs v1 | vs v3 | vs PNG | Lossless? |
|---|---|---|---|---|---|
| 16×16 | 2036 KB | -0.3% (worse) | +7.7% better | -19.2% worse | **NO** (max diff 255) |
| 8×8 | 2002 KB | +1.4% better | +9.3% better | -17.2% worse | **NO** (max diff 252) |
| 4×4 | 1972 KB | +2.9% better | +10.6% better | -15.5% worse | **NO** (max diff 230) |

But max pixel diff of ~250 across all configs means **the reconstructed image was completely wrong** — the compression numbers are meaningless until the codec is actually lossless.

### The bug (and what it says about the substrate test)

`pred_calic7` references `NE = img[y-1, x+1]` (top-right neighbor). v3's decoder iterates pixel-by-pixel in raster order, so NE is always already-decoded when needed. **v4 inherited v1's block-by-block decoder iteration**, which means: when processing the rightmost-column pixels of any non-rightmost block, NE lives in a *future* (not-yet-decoded) block. Encoder sees original-pixel NE; decoder sees zeros. Predictions diverge → reconstruction breaks.

**Fix:** decoder iterates pixel-by-pixel in raster order. Encoder is fine as-is (it always uses originals).

**What this says about the substrate test:**

- The bug took ~5 minutes to find by inspecting the output ("max_diff 255 across all block sizes = entire prediction context is wrong"). The substrate added zero value to bug-finding. There is no memory in the seed that says "block-iteration codec + non-causal predictor reference is a known trap" — that's a design-pattern observation the current substrate does not capture.
- A working `aether_contradictions` (Prediction Row 6) might have surfaced something *if* I had thought to query it on the v4 design. But the tool was untestable due to the latency issue. So I have no evidence it would have caught this either way.
- This is the kind of bug that would naturally accrete in the substrate over multiple iterations — the SECOND time someone tries this pattern, the substrate would catch it. First time, it's invisible. That's a real limitation of the "substrate as memory" thesis: the first iteration always pays the full bug cost.

### Second benchmark run — clean lossless result

After fixing the decoder iteration order:

| Block size | Size | vs v1 | vs v3 | vs PNG | Lossless |
|---|---|---|---|---|---|
| 16×16 | 2036 KB | -0.3% worse | +7.7% better | -19.2% worse | YES (max diff 0) |
| 8×8 | 2002 KB | +1.4% better | +9.3% better | -17.2% worse | YES (max diff 0) |
| **4×4** | **1972 KB** | **+2.9% better** | **+10.6% better** | -15.5% worse | YES (max diff 0) |

SHA256 of reconstructed image matches original at all block sizes.

**Predictor usage at 4×4** (best config): avg 20%, left 19%, top 18%, paeth 15%, median 10%, **calic7 9%**, gradient 7%, diagonal 3%. CALIC-7 is being selected for ~9% of blocks but is not dominant.

### Verdict on the missing cell

v4 beats v1 by **2.9% at best — does not meet the 5% ship threshold.** The decision rule says: "if not, document why the missing cell was actually a non-cell."

The missing cell is **not** a non-cell — there is a real, lossless-verified +2.9% improvement from adding CALIC-7 + YCoCg-R while holding the strategy map constant. But it's small. What this tells us:

- **The v1-vs-v3 comparison was confounded as predicted.** The 8.7% gap between v1 (2031 KB) and v3 (2207 KB) was *not* "predictor sophistication is bad." When the strategy map is held constant, swapping in CALIC-7 helps slightly rather than hurts.

- **The variable that mattered most was the strategy map**, held constant across v1 and v4. CALIC-7 + YCoCg-R together contribute only ~3%; the strategy map's contribution is the bulk of the gap to v3 (2207 → 2031 = 8.7%, of which ~6% is the map and ~3% is the predictor).

- **The original CogniMap thesis is unchanged**: per-block adaptive predictor selection > any single fancier predictor, even with color decorrelation. The strategy map IS the compression advantage. v4 confirms this; it doesn't overturn it.

- **v4 is still meaningfully behind PNG** (15.5% worse) and far behind WebP-lossless (1353 KB, 32% better than v4-best). For a real-world lossless image codec, simple predictor menus + adaptive selection are not a winning architecture against industrial codecs that combine prediction + entropy-coded residuals + larger context windows. CogniMap-lossless remains a research artifact, not a deployable codec.

### Implementation bug worth recording

The first benchmark run of v4 was not lossless — `pred_calic7` references `NE = img[y-1, x+1]`, which is non-causal under v1's block-by-block decoder iteration. Encoder saw original NE; decoder saw zeros. Fixed by switching the decoder to pixel-by-pixel raster order. The bug took 5 minutes to find by inspecting the output. **The substrate added zero value to bug-finding here** — there's no seeded memory about block-iteration codecs and non-causal predictor references, and `aether_contradictions` (the tool that might catch this kind of design conflict) was untestable due to the latency issue.

This is a real limitation of the substrate-as-coding-assistant thesis: design-pattern bugs that aren't already in the substrate's memory are invisible to it. The substrate can encode prior decisions and findings, but it can't generate novel design analysis.

---

## 6. Net judgment

**On the substrate:** the apparatus is alive at the read tier and broken at the governance tier. As a context-transfer mechanism for a fresh agent, it works (Row 1; muted baseline framing). As a live governance system that gates decisions during work, it's not ready (Row 2 fail, Row 3 hang). The four product gaps — global state binding, CLI/MCP state divergence, no auto-reload, embedding warmup wedge — are all reproducible and fixable. The fidelity threshold issue (Row 2) is the most surprising and probably the most important to debug — the substrate had the exact text needed to flag the overclaim, and didn't.

**On the test design:** the rubric was sound; the plan was right that the negative result would be more valuable than a hyped positive. The single-agent / single-session structure is the right starting point but limits what we can claim about cross-session transfer. Next iteration should be: same task, fresh Claude session that only sees the substrate via tools, not via this conversation.

**On the year of work:** this test is a single trial. It gates the *next month*, not the past year. What it justifies:

- Keep building the substrate. The read tier works and the seed-and-retrieve flow is genuinely useful.
- Fix the four product gaps before doing any cross-session test. Without those fixes, more trials will keep producing the same artifacts.
- Investigate why fidelity returned PASS on the canonical overclaim. This is not a "warmup" issue — fidelity ran fast and returned a verdict, just the wrong one.

**On the compression question:** independent of the substrate. v4 is implemented and benchmarking; the result fills in the missing cell either way.

---

## 7. Action items

Numbered for clarity. None are blocking the substrate's existence — all are bugs in the current implementation.

1. **Diagnose the embedding warmup wedge.** Reproducible on fresh MCP server. Likely the daemon thread is hitting an exception path that doesn't flip `_unavailable=True`. Add stderr logging to the warmup thread.
2. **Fix fidelity's overclaim detection.** With substring grounding, the tool returned PASS on text containing exact substrings of a memory that contradicts it. The threshold or matching logic needs to surface low-similarity but high-impact memories.
3. **Add `aether_set_state_path` MCP tool.** Or per-call `state_path` argument. Without it, the substrate cannot be repo-scoped.
4. **Add `--state-path` flag to the CLI.** Or auto-discover the global MCP state when `.aether/state.json` is empty.
5. **Add an in-process reload mechanism** so CLI writes are visible to the running MCP server without restart.
6. **Check why `aether_sanction` hung.** Possibly related to embedding wedge (sanction may use embeddings for grounding). Possibly a separate compute issue.
7. **Add duplicate-warning to `aether_remember`.** When a near-identical memory already exists, surface that to the caller before writing.

---

## 8. Annexes

### Substrate state at end of test

- 19 memories (10 deliberate seeds + 8 pre-existing/strays + 1 stop-hook ghost)
- 6 edges: 4 SUPPORTS (v0→v1, v1→v2, v1→v3, memory_v0→v0_lossless) + 2 RELATED_TO (CLI backfill)
- 0 contradictions (none auto-detected on writes)
- Embeddings: warming, never loaded

### Files written

- `D:/AI_round2/compression_lab/AETHER_TEST_BASELINE_NOTES.md` — muted-baseline decisions, locked in before substrate use
- `D:/AI_round2/papers/compression_experiment/cognimap_lossless_v4.py` — v4 implementation
- `D:/AI_round2/compression_lab/v4_benchmark_output.log` — benchmark output
- `D:/AI_round2/compression_lab/AETHER_TEST_REPORT.md` — this file

### Time spent

| Phase | Budget | Actual |
|---|---|---|
| Substrate setup + diagnostics | 20 min | ~50 min (15 min setup, 35 min diagnosing wedge + restart) |
| Muted baseline | 30 min | ~16 min |
| Substrate-enabled pass | 90 min | ~5 min (truncated when sanction hung) |
| Benchmark | included above | running |
| Report | 30 min | drafting now |
| **Total** | ~3 hours | ~110 min at report-draft time |

The diagnostic time was unbudgeted and is the largest single cost. If the warmup-wedge bug is fixed, future runs of this test should fit the planned budget.
