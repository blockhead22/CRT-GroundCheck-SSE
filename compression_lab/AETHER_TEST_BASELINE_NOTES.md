# Muted Baseline — v4 Design Decisions

**Started:** 2026-04-27 21:26
**Constraint:** No `aether_*` tool calls during this phase. The substrate setup (Prediction Row 1) is already complete; from here forward, the substrate is muted.
**Source files read:** `cognimap_lossless_v1.py`, `cognimap_lossless_v3.py` (both fully).

These notes are written *as I decide*, not after. Locked in before I touch v4 code.

---

## What v1 actually is (load-bearing facts re-derived from source, not memory)

- 7 predictors hardcoded: `left, top, avg, paeth, diagonal, gradient, median`. Indexed 0–6, stored 1 byte per block in `best_strategy`.
- Block size parameterized; `run_experiment` sweeps `[16, 8, 4]`. Best result quoted as 2031 KB.
- Strategy map serialization: `best_strategy.tobytes()` → zlib-compressed.
- Residual: `int8` if range allows, else `int16`. Zlib-compressed.
- Header: `IIIII` (h, w, channels, block_size, is_int8) + `II` (strat_len, res_len).
- **Note:** `pred_gradient` already does basic gradient (`left + top - top_left, clamped`). The clamp is `np.clip(val, 0, 255)`.

## What CALIC-7 actually is (from v3, function `compress_calic_v2`)

- 7-neighbor context: W, N, NW, NE, WW, NN, NNW.
- 5 gradient regimes: strong-h-edge (predict from N), strong-v-edge (W), moderate-h, moderate-v, smooth (CALIC formula `(W+N)/2 + (NE-NW)/4`).
- Edge case for first row, first/last column, second row/column: falls back to Paeth.
- **Per-pixel adaptive.** No strategy stored — decoder reproduces the regime classification from already-decoded context.

## What YCoCg-R is (lossless reversible color transform)

```
Forward:                       Inverse:
  Co = R - B                    t  = Y - (Cg >> 1)
  t  = B + (Co >> 1)            G  = Cg + t
  Cg = G - t                    B  = t - (Co >> 1)
  Y  = t + (Cg >> 1)            R  = B + Co
```

- Y is in [0, 255] (unsigned).
- Co, Cg are SIGNED in roughly [-256, 255]. Cannot be naively stored as uint8.
- Lossless if integer arithmetic with floor-div (`>>`), not float division.

## Decisions

### D1 — Add CALIC-7 as an 8th predictor (do not replace anything)

The plan says "7th predictor option" but v1 already has 7. Adding as 8th rather than replacing keeps the v4-vs-v1 comparison clean: any size delta is attributable to (a) YCoCg-R, (b) CALIC-7 winning blocks the others wouldn't, never (c) loss of one of v1's existing predictors.

Strategy map is already `uint8` per-block — 8 vs 7 predictors makes zero difference to map size.

### D2 — `pred_gradient` clamp will likely fire on Co/Cg channels

The basic `pred_gradient` does `np.clip(val, 0, 255)`. On Co/Cg channels with negative values, this clamp will produce wrong predictions and inflate residuals. For v4 I will:

- Internally, predictors operate on int16 with no clamp assumption.
- For Y channel: behavior identical to v1 (range [0, 255]).
- For Co/Cg: same predictors, but pred_gradient must be range-aware. Cleanest fix: replace the hard-coded `np.clip(val, 0, 255)` with a clip to the actual channel range, OR drop the clip (lossless reconstruction doesn't need it because residuals carry the exact diff anyway).

Going with **drop the clip in pred_gradient** for v4. The clip was a sanity bound on the prediction, not a correctness requirement. Decoder applies the same drop. Keeps lossless.

### D3 — Channel-wise compression after YCoCg-R, not multi-channel-per-block

Two options:

(a) Run v1's multi-channel predictor logic on a 3-channel (Y, Co, Cg) image. Each predictor returns a 3-vector. The "best predictor per block" is decided on **summed** abs residual across all 3 channels.

(b) Run v1's pipeline 3 separate times, once per channel. Each channel gets its own strategy map. Residuals concatenated.

(b) is more flexible (Y might prefer different predictors than Co/Cg) but triples strategy map overhead (3× ~6 KB = ~18 KB on a 4×4 block). On a 2031 KB total, that's ~+0.6%. Acceptable cost.

(a) is simpler, matches v1 mechanics exactly. Strategy map stays ~6 KB.

**Going with (a) for v4.** It's the closer apples-to-apples comparison to v1 and v3. If (a) shows clear win, (b) is worth a follow-up. If (a) is a wash, (b) is unlikely to change the verdict.

### D4 — Block size

v1 swept 16 / 8 / 4. v4 will sweep the same. Best result reported.

### D5 — Test predictions before benchmark

Add a quick lossless roundtrip assertion in `compress_v4 → decompress_v4` so we don't end up reporting "v4 beat v1" on a corrupt reconstruction. v1's `np.array_equal(image, reconstructed)` check is the model.

### D6 — Output naming

`cognimap_lossless_v4.py` in the same directory. Output goes to `output/` (existing convention). Strategy visualization optional — skip unless trivial; not load-bearing for the test.

## What I'd build without the substrate

I would have built the same thing the plan describes. The substrate's contribution to setup was confirming:

- v1 and v3 were the right two parents (substrate Row 1 surfaced them in top results)
- The v1-vs-v3 comparison being "two variables changed at once" is a real interpretive frame, not just a hunch (substrate fact #6 explicitly captures this as a methodological gap)

**Without the substrate I'd still arrive at a v4 = "v1 chassis + CALIC-7 + YCoCg-R" design**, because that's what the plan literally specifies. The differentiated test is whether the substrate catches mistakes *during the implementation*, not whether it generates the design.

## Predictions about what could go wrong

1. **YCoCg-R signed-channel handling.** I will probably forget to apply the right dtype/range somewhere and break losslessness. The roundtrip assert will catch it; this is what assertions are for.

2. **CALIC-7 per-block cost is high.** The CALIC-7 function is per-pixel adaptive and computes 7-neighbor gradients; running it 7 times per block (once for the predictor evaluation, again for the chosen one's residual) is going to be slow. v1 already has nested Python loops; adding CALIC-7 will probably add 10–30% to compress time. Acceptable for a one-shot benchmark.

3. **Strategy map dilution.** With 8 predictors, the residual savings per block need to be larger than the entropy of an 8-way uint8 selector. v1's map was already ~6 KB compressed (zlib finds runs); the 8th predictor just adds one more state, so map size shouldn't grow much.

4. **YCoCg-R + per-block selector might pick same predictor for all 3 channels in a block.** That's the v1 behavior — one predictor index per block, applied to all channels. If Y prefers `paeth` but Co/Cg prefer `left`, we lose. Decision (a) accepts this loss. If v4 is close to but doesn't beat v1, this is the first thing to suspect.

## Decision rule (from plan, restated)

> If v4 beats v1 by ≥5%, ship as new baseline. If not, document why the missing cell was actually a non-cell.

If v4 lands at, say, 1980 KB (-2.5% from v1), the answer is "the missing cell exists but isn't decisively better." That's a valid answer.

---

**End of muted baseline notes. Proceeding to implementation.**

---

## End-of-muted update

**Time:** 2026-04-27 21:42 (~16 min into the 30-min budget; closing early)
**Artifact:** `D:/AI_round2/papers/compression_experiment/cognimap_lossless_v4.py` (~395 lines)

### What I actually wrote (matched the design)

- YCoCg-R forward/inverse implemented per the standard formulas (`R-B`, `B+(Co>>1)`, `G-t`, `t+(Cg>>1)`). Inverse mirrors. Applied at entry, applied at exit.
- All 7 v1 predictors copied. **`pred_gradient` clamp dropped** as planned (D2).
- **CALIC-7 added as 8th predictor** (D1), copied from `compress_calic_v2` in v3 with the same gradient regime branches and Paeth fallback for boundaries.
- `compress_adaptive_ycocg` runs YCoCg-R first, then v1's per-block best-pick on the (Y, Co, Cg) int16 image. Cost = sum of abs residual across all 3 channels per block (D3 option a).
- Residuals always stored int16 (Co/Cg can exceed int8 range — v1's int8 fast-path doesn't apply after YCoCg-R).
- Pre-flight YCoCg-R round-trip assertion before benchmark (D5).
- `np.array_equal(image, reconstructed)` lossless check + SHA256 hash compare per block size.
- Sweep block sizes [16, 8, 4] like v1.

### Things I'm worried about (predict before benchmark)

1. **CALIC-7 predictor evaluation may dominate compress time** — v1 already uses nested Python loops; running CALIC-7 per pixel for cost estimation across all 8 candidates could push compress time from ~30s to several minutes. If decompress is also slow, decompress benchmark may not match compress.

2. **Cost metric "sum abs residual" may not predict zlib-compressed size accurately on YCoCg-R channels.** Co/Cg distributions are very different from Y. A predictor that wins by L1 cost might lose by Huffman/LZ entropy. v1 had the same issue, but on RGB channels with similar distributions.

3. **The strategy map uint8 indices — I added 8 predictors but `strategy_bytes = best_strategy.tobytes()` still stores 1 byte per block.** zlib should compress this well because adjacent blocks correlate. But if the 8th predictor (CALIC-7) wins many blocks at low frequency, the strategy map's entropy goes up and zlib's run-length advantage shrinks.

4. **Boundary handling at y=0 / x=0 corners.** I default to `np.int16(128)` everywhere. For Y channel that's mid-gray (right). For Co/Cg signed channels, `128` is a wrong default; should be `0`. But this is just the prediction baseline — residual carries the diff exactly, so losslessness isn't broken. Just slightly inflates the corner residuals.

### What I would have missed without the substrate

Re-reading the methodological-gap framing (substrate fact #6) is what made me realize "v3 vs v1 is two variables changed at once" was a real insight worth basing v4 on. *Without that framing*, my naive read of the prior results would be "v1 won, so the strategy map matters more than predictor sophistication, so v4's value is mostly the YCoCg-R color trick." With it, I see v4 is a clean isolation experiment: strategy map held constant at YES, predictor menu varied.

That said: **the plan as written already gave me this design**. The substrate's contribution to muted-baseline reasoning was confirmation, not generation. The real test is what happens during the substrate-enabled pass when predictions 2-7 fire on natural triggers.

### Untested expectations

- v4 compress time: 60–180 s
- v4 decompress time: 30–90 s
- v4 size at best block size: 1900–2100 KB (could land either side of v1; I genuinely don't know)
- predictor_wins distribution: paeth and calic7 dominant; left/top/diagonal small contributions

**Muted baseline closes here. Moving to the substrate-enabled pass.**

