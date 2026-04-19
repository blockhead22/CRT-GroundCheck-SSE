# Debugging Harness Catalog (Phase A deliverable #2)

**Date:** 2026-04-16
**Purpose:** Inventory what's already built for agentic debugging in the lab, what's missing, and what Phase B–D need.

## Existing benchmark files

### `hard_bug_challenge.py` (484 lines) — the 4-file interaction

**Bug shape.** Trust scores silently degrade. The obvious diagnosis (decay too aggressive) is wrong. The real cause: `dedup.py` averages trust scores when merging similar memories, and every user correction creates a new low-trust memory (0.15) that dedup merges with the established high-trust one (0.9), producing 0.525, then 0.34, then 0.24.

**Synthesized codebase.** Written by `setup()` into `results/challenges/hard_bug/`:
- `memory_store.py` — save/load memories; calls dedup on every save
- `dedup.py` — **the bug** (averaging instead of max)
- `decay.py` — red herring (works correctly)
- `correction_handler.py` — saves corrections as new memories at trust=0.15 (correct behavior, but it's the trigger)
- `symptom.log` — user-facing trail showing 0.9 → 0.525 → 0.34 → 0.24 degradation
- `memories.json` — empty store for deterministic runs

**Agent loop.** `mirus_explore()` reads all 5 artifacts, sends them to the model with prior findings + hints, gets a diagnosis string back. 12 epochs max. Model: `llama3.2:latest` (3B) by default.

**Verifier.** `verify_diagnosis(str)` returns a 5-check keyword grid:
- `not_decay` — agent recognizes decay is not the cause
- `found_dedup` — agent names dedup/merging as the mechanism
- `found_averaging` — agent identifies averaging vs max as the error
- `found_correction_trigger` — agent traces correction → new memory → dedup → merge
- `proposed_max_fix` — agent proposes max or update-existing as the fix

Score ≥ 4/5 = solved.

**Holden nudge.** `holden_nudge()` looks at which checks are failing, picks the first miss, and asks Claude CLI for a one-sentence hint. Tracked across epochs.

**Output.** `results/raw/hard_bug.jsonl` (per-epoch diagnosis + verification).

### `hardest_bug.py` (624 lines) — the 5-file feedback loop

**Bug shape.** Personal identity queries ("what's my name") keep getting wrong answers. The user corrects. Next day, wrong again. Memory DB shows 14 copies of "Nick" with decreasing trust. Works fine for general-knowledge queries. Only personal queries fail.

Real cause: `intent_router.py` classifies "what's my name" as `general_knowledge` (matches the "what's..." pattern). `model_router.py` sends `general_knowledge` to a cloud model that has no memory access. Cloud model gives generic answer. User corrects → `correction_handler` saves new memory at low trust. But next "what's my name" still routes to general_knowledge → cloud → no memory → wrong answer. Feedback loop.

**Synthesized codebase.** 5 files; requires tracing through all of them to see the loop.

**Agent loop.** Same shape as `hard_bug` but 20 epochs, longer context window.

**Verifier.** Presumably similar keyword-grid. Need to read the full file to confirm exact checks.

**Output.** `results/raw/hardest_bug.jsonl`.

### `epistemic_agent.py` (949 lines) — the scaffold prototype

Pure belief-state-driven agent. The model's prompt *is* the rendered belief graph; no seed commands are given. The agent reads its own beliefs and generates the action that resolves highest tension.

**Currently coupled to Docker escape.** Imports `build_image`, `start_container`, `exec_in_container`, `check_escape`, `cleanup`, `LEVELS`, `FLAG_FILE`, etc. from `docker_escape`. Also imports `Belnap`, `Disposition`, belief dataclasses.

**Reusability.** The belief-graph machinery here is generic — Belnap 4-valued logic, disposition (resolvable / held / evolving), tension computation, urgency sort. The Docker-specific part is a ~200-line tail (level definitions, container lifecycle, escape detection).

For Phase B, we extract the generic scaffold into a standalone `BeliefDebugTree` class whose action primitives are `read_file`, `grep`, `trace_call`, `run_test` — not mount/curl/write.

## What's missing

### Phase B deliverables (belief scaffold for debugging)

1. **`BeliefDebugTree` class** — subclass or independent reimplementation of the scaffold with:
   - Action surface: `read_file(path)`, `grep(pattern, path)`, `trace_call(symbol)`, `run_test(test_id)`, `write_hypothesis(text)`
   - Belief keys typed to debugging: `hypothesis:`, `refuted:`, `file_read:`, `symbol_def:`, `symbol_caller:`, `test_result:`, `paradigm:`
   - Paradigm taxonomy: memory, concurrency, logic, I/O, routing, integration
   - Verifier integration: after each epoch, run `verify_diagnosis` and promote beliefs that correspond to passed checks

2. **Bug-benchmark driver** — parallel to `docker_escape.py run_level()`:
   - Load the synthesized codebase (reuse existing `setup()`)
   - Initialize `BeliefDebugTree`
   - Epoch loop: scaffold picks action → execute (file read / grep / etc.) → ingest observation into belief graph → check verifier score → decide continue/stop
   - Log per-epoch state in the same shape as escape logs so `density_analysis.py` works unchanged

3. **New benchmark grid runner** — `benchmark_debug.py` parallel to `benchmark_escape.py`:
   - Same levels × modes × trials × executors grid
   - Modes: `flat` (bare model), `belief` (regex-only scaffold), `belief-llm3b`, `belief-llm14b`, `belief-typed-slots`
   - Levels: `hard_bug`, `hardest_bug`, and optional `medium_bug` (synthesizable)
   - CSV schema: same as benchmark_escape but `escaped` becomes `solved`, `epochs_to_escape` becomes `epochs_to_solve`

### Phase C deliverables (typed-slot contract)

4. **`slot_resolver.py`** — semantic-slot resolution:
   - Canonical slot definitions: `HYPOTHESIS_ROOT_CAUSE`, `HYPOTHESIS_TRIGGER`, `HYPOTHESIS_RULED_OUT`, `EVIDENCE_TRACE`, `EVIDENCE_FILE_CONTENT`, `FIX_PROPOSAL`, etc.
   - Alias map: each slot holds a list of surface-key regexes and a list of synonym phrases
   - Resolution function: given a surface key + description, return the canonical slot or None
   - Embedding-backed fallback (optional Phase C.5): if no alias/regex match, embed surface key and cosine-match against slot exemplars

5. **Grid with and without slots** — rerun the cross-model grid on `hard_bug`:
   - 4 executors × 2 modes (slot-on, slot-off) × 2 trials × 2 bug levels = 32 cells, ~2–4 hours on current hardware
   - Metric: does slot-on close the cross-model gap that exists without slots?

### Phase D deliverables (replay three claims)

6. **Full cross-model grid on debugging benchmarks** — same shape as the claim-3 grid:
   - 4 executors × 3 levels × 2 modes (flat vs belief) × 2 trials = 48 cells
   - Reuse density analysis, cross-model plot, claim-3 summary template
   - Output: `results/claim_3_debugging_summary.md` that mirrors the escape summary

## Dependencies and risks

**Dependencies in hand:**
- Ollama with `llama3.2:latest`, `phi3:3.8b`, `mistral:latest`, `qwen3:14b` — verified available from escape grid
- Claude CLI for Holden nudges — already used by existing bug challenges
- `BeliefExplorationTree` machinery in `exploration_tree_belief.py` — can be referenced (not augmented) to guide the new class
- Density analysis tooling — works on any `[BELIEF] beliefs=N tension=T gap=G` log format

**Risks and mitigations:**

- **Keyword-grid verifier is fragile.** Current `verify_diagnosis` keys on specific words ("average", "dedup", "max"). Different models may say the same thing in different phrasing. **Mitigation:** Phase C slot resolver is precisely the fix for this — apply it to the verifier too.
- **Model context length.** Sending full source of 5 files every epoch is expensive and drifts toward context limits. **Mitigation:** scaffold should dispatch targeted reads (single file / single function) instead of dumping everything.
- **Debugging benchmarks currently run bare models only.** Adding the scaffold is net-new code, not a port. Estimate 1–2 days is honest; not same-day.
- **Holden nudge cost.** Each nudge is a Claude CLI round-trip. At 12–20 epochs × 48 cells, that's hundreds of calls. **Mitigation:** make nudging optional / capped, measure belief-only performance cleanly without nudge contamination.

## Existing logs / precedent to preserve

- `results/raw/hard_bug.jsonl` and `results/raw/hardest_bug.jsonl` are the bare-model baselines. Keep them. They're the "flat register" comparison for claim 1 on the new task.
- The density analysis report (`results/belief_density_report.md`) applies unchanged to debugging logs — we expect the same predictive profile if the scaffold behaves analogously.

## Open questions for Nick before Phase B starts

1. **Which bug level first?** `hard_bug` is simpler and the existing 5-check verifier is well-tuned. `hardest_bug` is where co-adaptation should bite harder (5-file routing logic, more vocabulary variance across models). Recommend starting with `hard_bug` for smoke-test, moving to `hardest_bug` for the claim-3 analog.
2. **Nudge inclusion?** Can run the grid with and without Holden nudges as a separate dimension, or disable nudges entirely to isolate scaffold contribution. Recommend disabling by default; add back as a separate experimental axis if needed.
3. **Embedding-backed slot resolution (Phase C.5) now or later?** Pure alias/regex resolution is ~50 lines. Embedding fallback is 100+ lines and adds a dependency on a local embedding model. Recommend alias/regex only for Phase C, add embeddings only if alias resolution leaves a visible cross-model gap.

---

*Phase A complete. Phase B is ready to start when you give the word.*
