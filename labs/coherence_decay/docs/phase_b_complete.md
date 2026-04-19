# Phase B Complete — Belief-Driven Debugging Scaffold

**Date:** 2026-04-16
**Scope delivered:** Standalone belief-graph reasoning scaffold bound to the
`hard_bug_challenge` debugging benchmark. No Docker-escape dependency.

## What shipped

| File | Purpose | LOC |
|---|---|---:|
| `belief_debug_tree.py` | Generic primitives + debug task specifics (Belnap, disposition, trust decay/reinforce/refute, cascade damping, urgency + tension, 4 debugging paradigms, hard_bug regex-hypothesis map, 5 solution belief targets). | ~600 |
| `debug_scaffold.py` | Runner: action executors (read_file, grep, trace_call, run_test, write_hypothesis), `belief` + `flat` modes, density-compatible `[BELIEF]` log lines, JSON result output, optional Holden nudge (off by default). | ~420 |

Both files are clean imports only — **zero dependency on `docker_escape.py` or its sibling modules**. The existing `hard_bug_challenge.py` is *called* (setup, verify_diagnosis, holden_nudge) but **not modified**.

## Smoke test

```
python debug_scaffold.py --mode belief --level hard_bug --model llama3.2:latest --max-epochs 8
```

**Result:** solved on epoch 7 in 48.6s wall time, verifier 4/5, 8 beliefs, 0 contradictions, 0 nudges.

```
[EPOCH 1] action=read_file symptom.log
[BELIEF] beliefs=5 tension=0.9 gap=4 contradictions=0 verifier=3/5
[EPOCH 4] action=read_file decay.py
[BELIEF] beliefs=7 tension=1.2 gap=2 contradictions=0 verifier=1/5
[EPOCH 7] action=write_hypothesis ...
[BELIEF] beliefs=8 tension=1.2 gap=1 contradictions=0 verifier=4/5
```

The log format is bit-compatible with `density_analysis.py`; no tooling changes needed downstream.

## Three observations worth carrying into Phase C

1. **3B solved `hard_bug` with zero nudges** when given the scaffold. The existing bare-model baseline (`results/raw/hard_bug.jsonl`) needs several Holden nudges on the same bug. This is the Claim-1 signal on the new task: scaffold substrate reduces the need for external hints.
2. **Paradigm shifts: 0.** The scaffold stayed in `rule_out_decay` the full run — `isolate_mechanism` / `trace_trigger` / `propose_fix` paradigms had 0.0 tension. Their seed actions never fired because `get_next_action()` drew from the current paradigm's queue until exhausted and then fell back to `write_hypothesis`. Seed-rotation across paradigms needs tightening.
3. **Scaffold exhaustion by epoch 5.** After 4 real actions (2 file reads + 2 hypothesis writes) the scaffold had no more seeds. The last 3 epochs were hypothesis-echo loops. The model solved it anyway because prior belief-state accumulated across epochs, but this is a fragility — larger bugs will need the scaffold to keep driving reads after the initial paradigm's seeds are used up.

None of these are Phase B blockers. They are tuning concerns that Phase C is structurally placed to address (typed-slot contracts will canonicalize action proposals, which incidentally re-admits model-emitted actions into the scaffold queue instead of echoing them back as `write_hypothesis` no-ops).

## Phase C entry point

**Goal:** typed-slot contract so cross-model vocabulary variance stops breaking the scaffold.

**Module to write:** `slot_resolver.py`

**Contract shape:**
```python
from slot_resolver import resolve_slot, HYPOTHESIS_ROOT_CAUSE, EVIDENCE_FILE_CONTENT
slot = resolve_slot("it's the averaging that kills it")  # -> HYPOTHESIS_ROOT_CAUSE
```

**Minimum canonical slots:**
- `HYPOTHESIS_ROOT_CAUSE` (aliases: "the bug is", "root cause", "caused by", "destroys", "kills", "breaks")
- `HYPOTHESIS_TRIGGER` ("is triggered by", "fires when", "happens on", "invoked when")
- `HYPOTHESIS_RULED_OUT` ("not the cause", "red herring", "working correctly", "is fine")
- `EVIDENCE_TRACE` ("call chain:", "path:", "flow is", "traces through")
- `EVIDENCE_FILE_CONTENT` ("file X contains", "line N of", "function Y in")
- `FIX_PROPOSAL` ("the fix is", "should be", "replace with", "use max instead")

**Resolution algorithm (Phase C scope):**
1. Surface-key regex match (fastest, deterministic).
2. Synonym-phrase match (alias-table lookup).
3. Return the canonical slot constant, or `None` if no match.

**Phase C.5 (optional):** embedding-backed fallback. Skip unless the alias/regex pass leaves a visible cross-model gap in the grid.

**Experiment:** rerun the cross-model grid on `hard_bug` with and without the slot resolver. Expected outcome: slot-off reproduces the L4 co-adaptation gap; slot-on closes it.

**Grid size for Phase C:** 4 executors (llama3.2, phi3, mistral, qwen3:14b) × 2 modes (slot-on, slot-off) × 2 trials × 1 level (hard_bug) = 16 cells, ~45 min on current hardware at 48s per belief-mode run.

## Phase D preview

Phase D replays all three claims on the debugging benchmark:
- Claim 1 (substrate helps): `flat` vs `belief` on hard_bug + hardest_bug.
- Claim 2 (holds across brain size): 4 executors × `belief` mode, check outcome tightness within-scaffold.
- Claim 3 (persists across swaps): same outcome grid logic as the escape claim 3, with the slot resolver from Phase C installed.

Estimated grid: 4 × 2 × 2 × 2 = 32 cells, ~1.5 hours.

## Open items for Nick

1. **Tune paradigm-seed rotation in `BeliefDebugTree.get_next_action`** — currently the scaffold drains one paradigm's seeds before considering the others. A round-robin across paradigms (weighted by `paradigm_novelty * (1 - fraction_used)`) would force earlier reads of dedup.py and correction_handler.py.
2. **Expand `HARD_BUG_PATTERNS` regex coverage.** The current 10 patterns catch the solid bug-shape observations but miss some phrasings an LLM might emit when we *feed its own diagnosis back* as an evidence source. Phase C slot resolution handles this properly; until then, a manual pattern sweep against a few more flat-mode transcripts would help.
3. **Wire `hardest_bug` into `level_workspace` / `level_setup`.** Currently raises `NotImplementedError`. Need the 5-file setup reused from `hardest_bug.py` and a hypothesis map for the intent-routing bug.

---

*Phase B complete. Ready for Phase C when you give the word.*
