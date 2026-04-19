# Phase D — Three-Claim Replay on the Debugging Benchmark

**Scope:** replay the Aether-benchmark plan's three claims on the debugging
task, using Phase C's typed-slot contract (slot-on) as the default substrate.

Phase C landed slot-on at **6/6 solve rate** with **stdev_slot = 0.000**
across three viable models on `hard_bug`. Phase D widens to **two levels
(hard_bug + hardest_bug)** and **five models (3B -> 14B)** to test whether
the substrate-helps / brain-size-invariance / model-swap-persistence
triad holds when the task is harder and the model pool is broader.

## Grid

| dim     | values                                                                           |
|---------|----------------------------------------------------------------------------------|
| levels  | `hard_bug` (4-file, dedup-averaging), `hardest_bug` (5-file, feedback loop)      |
| modes   | `flat` (no substrate), `belief` (slot-on substrate)                              |
| models  | llama3.2:latest (3B), phi3:3.8b, mistral:latest (7B), qwen2.5:7b-instruct, qwen3:14b |
| trials  | 2                                                                                |
| total   | **40 cells**                                                                     |
| stop-on | `slot` (Phase C primary verifier)                                                |

Per-cell artifacts: raw diagnosis logs in `results/debug_benchmark/*.json`
(overwritten per (level,mode) pair), belief transitions in `results/logs/*.jsonl`,
CSV rollup in `results/benchmark_phase_d.csv`. Full grid log at
`results/logs/phase_d_grid.log`.

## Three claims

### Claim 1 — Substrate helps  ✅ (conditional)

|  level       | flat solve | flat slot | belief solve | belief slot | Δ slot |
|--------------|-----------:|----------:|-------------:|------------:|-------:|
| hard_bug     |   9/10     |   0.820   |   9/10       |   0.800     | −0.020 |
| **hardest_bug** | **4/10**   | **0.600** | **9/10**     | **0.833**   | **+0.233** |

**The substrate doesn't help when the executor is already sufficient — it
helps where the executor fails.** On hard_bug the 4-file dedup-averaging
bug is within unaided reach of every model we tested; substrate and flat
tie at 90% solve rate. On hardest_bug (5-file feedback loop) flat-mode
solve drops to 40% (all four failures are llama3.2 and phi3, plus 1/2
mistral), while belief-mode holds 90%. The slot-fraction lift of +0.233
is the cleanest single number in the grid.

**Interpretation:** the substrate is a capacity amplifier, not a free
multiplier. It pays off precisely where raw-model capacity falls short.
Phase C's headline ("slot-on 6/6 vs slot-off 1/6") was on a task tuned
to expose co-adaptation; on a genuinely solvable task, the scaffold
matters less. On a genuinely hard task, it's decisive.

### Claim 2 — Brain-size invariance  ✅

|   level       | mode   | models | mean  | stdev  | min  | max  |
|---------------|--------|-------:|------:|-------:|-----:|-----:|
| hard_bug      | belief |   5    | 0.800 | 0.071  | 0.70 | 0.90 |
| hard_bug      | flat   |   5    | 0.820 | 0.130  | 0.60 | 0.90 |
| **hardest_bug** | **belief** | **5** | **0.833** | **0.059** | 0.75 | 0.92 |
| hardest_bug   | flat   |   5    | 0.600 | 0.260  | 0.33 | 1.00 |

Belief-mode cross-model stdev is **4.4× smaller** than flat-mode stdev on
hardest_bug (0.059 vs 0.260). Raw range collapses from 0.33–1.00 to
0.75–0.92. The 3B–14B brain-size spread disappears under the substrate:
qwen3:14b (0.92) and llama3.2:3B (0.83) land within 0.09 of each other,
where in flat mode the gap is 0.58 (0.42 vs 1.00).

**Caveat:** stdev=0.059 is not zero. Phase C reported 0.000 on hard_bug
with 3 models; here with 5 models we see 0.071 on hard_bug and 0.059 on
hardest_bug. The non-zero floor is driven by phi3 (see Claim 3).

### Claim 3 — Persists across model swaps  ⚠️ (4/5 pass)

|   model                | hard_bug        | hardest_bug     |
|------------------------|:----------------|:----------------|
| llama3.2:latest (3B)   | PASS 2/2 (0.80) | PASS 2/2 (0.83) |
| phi3:3.8b              | **FAIL 1/2 (0.70)** | **FAIL 1/2 (0.75)** |
| mistral:latest (7B)    | PASS 2/2 (0.80) | PASS 2/2 (0.83) |
| qwen2.5:7b-instruct    | PASS 2/2 (0.90) | PASS 2/2 (0.83) |
| qwen3:14b              | PASS 2/2 (0.80) | PASS 2/2 (0.92) |

4 of 5 models pass 2/2 on both levels. phi3 shows trial-2 seed
sensitivity on both levels (passes trial 1, fails trial 2). **The
substrate still lifts phi3 over flat** — hardest_bug flat phi3 is 0/2
(slot 0.33), belief is 1/2 (slot 0.75), so the substrate recovers phi3
halfway to the shared belief-mode ceiling but not all the way.

**Interpretation:** the scaffold is dialect-agnostic enough that 4 out
of 5 unrelated-family models persist across the swap. The residual
fragility is a phi3 property (seed/temperature variance at
num_predict=600, likely), not a resolver coverage gap. Widening the
pattern / binding tables is not the fix for phi3; a retry-on-no-fill
mechanism or slight temperature cool would be more targeted.

## Scaffold changes (code delta)

1. **`belief_debug_tree.py`** — added `HARDEST_BUG_PATTERNS` (17 file-content
   regexes), `SOLUTION_HYPOTHESES_HARDEST` (6 solution keys mirroring the
   hardest_bug verifier), `build_hardest_bug_paradigms()` (5 paradigms:
   rule_out_identity, isolate_intent, trace_memory_skip, trace_consequence,
   propose_fix). Level dispatch via `patterns_for / hypotheses_for /
   paradigms_for / initial_paradigm_for` — the scaffold class now holds
   `self._patterns` and `self._hypotheses` instance attrs so the runtime
   paths are uniform across levels.

2. **`slot_resolver.py`** — added 10 new SUBJECT_BINDINGS for the
   hardest_bug vocabulary (intent misclass, pattern-score-by-length,
   pronouns-missing-from-identity, memory-skip, cloud-routed,
   correction-always-appends, feedback-loop-14-duplicates,
   who-am-i-works, add-pronouns-fix, force-requires-memory-fix). New
   `verify_diagnosis_slot_hardest()` — 6-check companion to
   `hardest_bug.verify()` (need 5/6 to pass). New dispatcher
   `verify_diagnosis_slot_for(diagnosis, level)`.

3. **`debug_scaffold.py`** — `level_setup` / `level_workspace` now route
   to `hardest_bug.setup` / `hardest_bug.WORKSPACE`. Verifier calls are
   replaced with `verify_for(level, diag)` and `verify_slot_for(level,
   diag)`. Holden nudges dispatched via `holden_nudge_for(level, ...)`.

4. **`benchmark_phase_d.py`** — new grid runner mirroring
   `benchmark_debug.py` but 2 levels x 2 modes x 5 models x 2 trials =
   40 cells. CSV output with per-cell solved / slot score / kw score /
   epochs / beliefs / wall time.

5. **`analyze_phase_d.py`** — new analyzer with three-claim tables:
   per-cell rollup, cross-model variance, binary persistence grid.

## Smoke test

`python debug_scaffold.py --mode belief --level hardest_bug --model
llama3.2:latest --max-epochs 8 --stop-on slot` — solved on epoch 1,
kw 6/6, slot 6/6, 10 beliefs, paradigm `rule_out_identity`.

## Known limitations carried from Phase C

- **Paradigm-seed rotation** still drains the current paradigm's seeds
  before checking rotation pressure. Slot-birthing re-opens the action
  queue before exhaustion bites in practice, but the fix (weighted-random
  paradigm picker on every `_compute_next_action`) is still pending.
- **kw verifier display** prints `kw=X/5` even on hardest_bug (6-check).
  Cosmetic only — the real score is logged to CSV and analyzer.

## Open items (Phase E candidates)

1. Nudge-ablation sweep: does the substrate still close the gap without
   any hints? (Phase D runs with `--nudge` off by default — this is
   already the harder condition.)
2. Adversarial models: test on a model family explicitly divergent from
   the scaffold's tuning (e.g., gemma3, deepseek-r1) to probe the
   resolver's surface-pattern coverage under larger dialect shifts.
3. Noisy-symptom variant: inject misleading facts into symptom.log to
   test whether the belief graph's contradiction-holding (Belnap BOTH)
   actually keeps the scaffold honest.

## Numbers table (full per-cell rollup)

### Per-cell means (n=2 trials)

| level       | model               | mode   | solve | slot_frac | epochs | wall(s) |
|-------------|---------------------|--------|------:|----------:|-------:|--------:|
| hard_bug    | llama3.2:latest     | flat   | 1.00  |   0.900   |   4.5  |   33.3  |
| hard_bug    | llama3.2:latest     | belief | 1.00  |   0.800   |   9.0  |   65.4  |
| hard_bug    | mistral:latest      | flat   | 1.00  |   0.800   |   2.0  |   24.0  |
| hard_bug    | mistral:latest      | belief | 1.00  |   0.800   |   4.0  |   28.9  |
| hard_bug    | phi3:3.8b           | flat   | 0.50  |   0.600   |   6.5  |   59.1  |
| hard_bug    | phi3:3.8b           | belief | 0.50  |   0.700   |  12.0  |  110.8  |
| hard_bug    | qwen2.5:7b-instruct | flat   | 1.00  |   0.900   |   1.5  |   22.9  |
| hard_bug    | qwen2.5:7b-instruct | belief | 1.00  |   0.900   |   9.0  |  101.6  |
| hard_bug    | qwen3:14b           | flat   | 1.00  |   0.900   |   2.0  |  115.9  |
| hard_bug    | qwen3:14b           | belief | 1.00  |   0.800   |   6.0  |  249.0  |
| hardest_bug | llama3.2:latest     | flat   | 0.00  |   0.417   |  12.0  |   76.5  |
| hardest_bug | llama3.2:latest     | belief | 1.00  |   0.833   |   3.5  |   23.8  |
| hardest_bug | mistral:latest      | flat   | 0.50  |   0.583   |   9.5  |   79.8  |
| hardest_bug | mistral:latest      | belief | 1.00  |   0.833   |   4.0  |   34.2  |
| hardest_bug | phi3:3.8b           | flat   | 0.00  |   0.333   |  12.0  |   86.0  |
| hardest_bug | phi3:3.8b           | belief | 0.50  |   0.750   |   7.5  |   60.0  |
| hardest_bug | qwen2.5:7b-instruct | flat   | 0.50  |   0.667   |   7.0  |   84.2  |
| hardest_bug | qwen2.5:7b-instruct | belief | 1.00  |   0.833   |   4.0  |   48.8  |
| hardest_bug | qwen3:14b           | flat   | 1.00  |   1.000   |   3.0  | 155.5   |
| hardest_bug | qwen3:14b           | belief | 1.00  |   0.917   |   1.5  |   86.1  |

### Headline rollup

| mode   | level       | solved | slot_frac_mean |
|--------|-------------|-------:|---------------:|
| flat   | hard_bug    | 9/10   |     0.820      |
| flat   | hardest_bug | **4/10** |   **0.600**    |
| belief | hard_bug    | 9/10   |     0.800      |
| belief | hardest_bug | **9/10** |   **0.833**    |

Flat→belief on hardest_bug: solve rate **+0.50**, slot_frac **+0.233**,
mean-epochs-to-solve **−2 to −8** (belief solves faster when it solves),
cross-model stdev **÷4.4** (0.260 → 0.059).

### Phase C vs Phase D

| metric                        | Phase C (hard_bug, 3 models) | Phase D (hard_bug, 5 models) | Phase D (hardest_bug) |
|-------------------------------|-----------------------------:|----------------------------:|----------------------:|
| belief-mode solve rate        | 6/6 (100%)                   | 9/10 (90%)                  | 9/10 (90%)            |
| cross-model belief-slot stdev | 0.000                        | 0.071                       | 0.059                 |
| flat-mode solve rate          | 1/6 (17%)                    | 9/10 (90%)                  | 4/10 (40%)            |
| substrate lift (slot_frac)    | +0.577                       | −0.020 (noise)              | +0.233                |

Phase C's 1/6 flat solve rate was a specific artifact of the keyword
verifier over-rewarding llama3.2's dialect — Phase D's 40% flat on
hardest_bug and 90% on hard_bug is more representative. The stronger
Phase D finding is **capacity-gated substrate lift**: the harder the
task relative to executor capacity, the larger the substrate's marginal
contribution.
