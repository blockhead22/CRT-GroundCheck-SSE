# Aether Product / Research Handoff

**Date:** 2026-07-18  
**Status:** Research checkpoint recorded; resume normal Aether product work  
**Canonical roadmap:** `docs/plans/AETHER_UNIFIED_ROADMAP_2026-07-16.md`

## Why this exists

The thread moved from product hardening into a bounded hosted-renderer and
research sequence. This checkpoint records what changed, what the evidence
does and does not establish, and the exact product resume point so the research
lane does not blur into live Aether claims.

## Bucket 1 - Aether product

### Proven or completed as bounded milestones

- Governed Workbench and durable public trace baseline.
- Conversation-control repair and production dogfood gate.
- Reusable, synthetic, non-Nick Aeteros Core demonstration.
- Frozen comparative product evaluation and two blind product packs.
- Profile-root isolation across synthetic profiles.
- Completion receipts surviving sidecar restart and Workbench reload.
- Explicit interrupted-task `/resume` through a reviewed open loop.
- Offline backup/restore, compatibility refusal, and installed Python paths.
- Windows x64 installer, upgrade, uninstall, and preserved-profile lifecycle.
- Cross-conversation archive retrieval by exact ID, title/fragment, recency,
  semantic topic, yesterday, one date, and date range.
- Source-cited `CrossConversationContinuityPacket` and durable
  `ContinuityAlignmentReceipt` with zero profile-memory writes.
- Workbench source selection, ambiguity handling, trace visibility, reload,
  restart, and receipt rehydration.
- Explicit per-turn Local versus Grok 4.5 CLI hosted-wording choice. Aether
  retains evidence release, authority, verification, writes, fallback, and
  provider receipts; a fresh profile defaults to Local.

Primary product evidence:

- `artifacts/aeteros-product-eval/RESULTS_2026-07-17.md`
- `artifacts/aeteros-blind-replication-2/RESULTS_2026-07-17.md`
- `artifacts/aeteros-repair-slice-3/RESULTS_2026-07-17.md`
- `artifacts/aeteros-persistence-slice-1/RESULTS_2026-07-17.md`
- `artifacts/aeteros-interrupted-resume-slice-1/RESULTS_2026-07-17.md`
- `artifacts/aeteros-profile-recovery-slice-1/RESULTS_2026-07-17.md`
- `artifacts/aeteros-install-compatibility-slice-1/RESULTS_2026-07-17.md`
- `artifacts/aether-desktop-packaging-2026-07-17/RESULTS.md`
- `artifacts/aether-cross-conversation-heldout-2026-07-17/RESULTS.md`
- `artifacts/governed-renderer-choice-lab/RESULTS_2026-07-17.md`

### Current product truth

Aether can retrieve, cite, and explicitly align a prior conversation into a new
thread. It cannot yet claim arbitrary cross-thread execution recovery.

Durable explicit open loops exist, but the next product contract must separate:

- user-authorized task state;
- observed completed steps;
- pending steps and artifacts;
- stale or revoked constraints;
- prose that is merely discussion;
- the next action that is actually authorized.

General alignment currently remains a bounded extractive snapshot. It must not
silently become executable authority.

### Active product gate

Build and prove an explicit task/open-loop continuation packet through:

1. focused and adjacent backend tests;
2. direct isolated API behavior;
3. actual Workbench UI behavior;
4. completion receipt and public trace inspection;
5. zero unauthorized writes;
6. sidecar restart;
7. reopened/rehydrated Workbench state;
8. a separately frozen 30-40 case task-state pack.

Required held-out families include completed versus pending steps, explicit
open loops, changed decisions, conflicting source threads, partial/rejected
assistant output, expired authority, current-thread exclusion, cross-profile
isolation, response contracts, restart, and unavailable/ambiguous state.

### Product checkpoint and active worktree

The prior cross-conversation and hosted-renderer work was revalidated and
checkpointed before task-continuation work began.

- Nested `aether-core`: `28b46df`.
- Root Workbench/docs: `964170417`.
- The checkpoint gate passed `152` focused/adjacent backend tests, `70`
  Workbench tests, `26` Electron tests, and a production build across its two
  validation stages.
- A live Electron EPIPE crash found during dogfood was repaired before the
  checkpoint. The repaired turn rehydrated `Verified 5/5` with zero writes.
- Frozen product-evaluation and blind-replication artifacts were not staged or
  modified.

The worktree is intentionally active again for TaskContinuationPacket slice 1.
The first packet seam, receipt, restart proof, and Workbench trace card are
implemented; evidence is in
`artifacts/aether-task-continuation-slice-1/RESULTS_2026-07-18.md`.

The continuity gate remains open. Ambiguous loop selection, structured
artifact/constraint authority, and the separately frozen 30-40 case task-state
pack remain.

### Product work after continuity

1. Resume distribution readiness: icon, product/version metadata, Windows code
   signing, Ollama/model prerequisite detection, update-channel selection, and
   rollback policy.
2. Run a frozen 30-50 case provider comparison through the real sidecar path.
3. Keep Grok CLI labeled personal/experimental. A commercial hosted-provider
   path needs a direct API adapter, consent, privacy controls, budgets,
   cancellation, billing, and stable error semantics.
4. Run a bounded multi-day daily-use soak.
5. Seek an external installer/pilot user before claiming another-user
   operability.

## Bucket 2 - Research

### Generative governance spike

The lab now has a narrow Mirus-before-Holden spike:

- `labs/meaning_compression_lab/generative_governance_spike.py`
- `labs/meaning_compression_lab/generative_governance_render_compare.py`
- `labs/meaning_compression_lab/generative_governance_trace_memory.py`
- `labs/meaning_compression_lab/generative_governance_live_renderer.py`
- `tests/test_generative_governance_spike.py`
- `tests/test_generative_governance_render_compare.py`
- `tests/test_generative_governance_trace_memory.py`
- `tests/test_generative_governance_live_renderer.py`
- `labs/meaning_compression_lab/results/generative_governance_spike_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_render_compare_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_trace_memory_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_live_renderer_scripted_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_live_renderer_qwen25_7b_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_live_renderer_expanded_scripted_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_live_renderer_expanded_qwen25_7b_latest.json`
- `labs/meaning_compression_lab/results/generative_governance_live_renderer_expanded_qwen3_14b_nothink_latest.json`

It generates a clear-text governance state before model rendering: intent,
evidence state, answerability, USER_SELF versus AETHER_SELF boundary,
allowed/blocked claims, response spine, governance-only boundary answer,
model-render-needed decision, review candidates, and vectorizable trace text.

Result: 5/5 spike cases passed with no memory/support/reflection/policy writes
and `raw_chain_of_thought_stored=false`. This supports the bounded research
claim that governance can generate meaning structure and some boundary answers
before Holden/model rendering. It does not prove governance replaces models for
rich synthesis, and it should not change the active product gate.

The companion render-comparison lab also passed 5/5. In that deterministic
comparison, `governance_only` won weak-evidence and memory-conflict boundary
cases, while `governance_plus_model` won grounded personal synthesis,
architecture synthesis, and business-planning cases. `model_only` exposed the
expected weak personal-synthesis drift by making unsupported identity/founder
claims. This supports the bounded split: governance can answer or refuse first
when the boundary is the answer, while Holden/model rendering remains useful
for rich synthesis after governance has built the spine.

The trace-memory companion also passed 5/5 holdout cases. It vectorizes only
public/clear governance trace text plus deterministic governance features
(`intent`, `evidence_state`, `answerability`, `model_render_needed`, review
candidate types), retrieves similar prior Mirus/governance situations, and
uses that retrieval to choose whether governance should answer directly or hand
off to Holden/model rendering. The result split matched the expected shape:
two boundary/conflict cases chose `governance_only`; three grounded/rich cases
chose `governance_plus_model`. This is not neural learning and does not write
memory, but it is the first concrete "Mirus remembers its own governance
shape" artifact.

The live-renderer companion passed the same five holdout cases with local
Ollama `qwen2.5:7b-instruct`. The model-only path passed 3/5 and failed the two
risky boundary cases. The trace-memory-governed path passed 5/5, won or tied
model-only 5/5, and avoided two governed model calls by answering
insufficient-evidence and memory-conflict cases directly from governance. This
is the first real local-renderer evidence that Mirus trace memory can decide
when Holden/model should speak and when governance should answer first. It is
still a small smoke test, not product wiring.

The expanded live-renderer pack now covers 24 cases across weak personal
receipts, memory conflicts, grounded personal synthesis, architecture,
business, and grant/business framing. Both local models passed through the
governed path: qwen2.5:7b-instruct governed 24/24 versus model-only 8/24, and
qwen3:14b/no_think governed 24/24 versus model-only 9/24. Both governed runs
avoided six model calls by answering weak-evidence/conflict cases directly and
used one verifier-guided public repair. qwen3 required `--disable-thinking`
and a larger `--num-predict 420` protocol; without that, many outputs were
blank/thin after reasoning-block stripping. This is stronger local evidence,
but remains lab-only and should not be wired into live Aether without a
separate product gate.

Verification:

- `python -m pytest tests\test_generative_governance_spike.py tests\test_generative_governance_render_compare.py tests\test_generative_governance_trace_memory.py tests\test_generative_governance_live_renderer.py tests\test_generative_governance_lab.py tests\test_local_router_cli.py -q` -> 50 passed
- `python -m py_compile labs\meaning_compression_lab\generative_governance_spike.py labs\meaning_compression_lab\generative_governance_render_compare.py labs\meaning_compression_lab\generative_governance_trace_memory.py labs\meaning_compression_lab\generative_governance_live_renderer.py` -> passed
- `python -m labs.meaning_compression_lab.generative_governance_live_renderer --live-ollama --model qwen2.5:7b-instruct --timeout 120 --out labs\meaning_compression_lab\results\generative_governance_live_renderer_qwen25_7b_latest.json` -> passed
- `python -m labs.meaning_compression_lab.generative_governance_live_renderer --case-set expanded --live-ollama --model qwen2.5:7b-instruct --timeout 120 --out labs\meaning_compression_lab\results\generative_governance_live_renderer_expanded_qwen25_7b_latest.json` -> passed
- `python -m labs.meaning_compression_lab.generative_governance_live_renderer --case-set expanded --live-ollama --model qwen3:14b --disable-thinking --num-predict 420 --timeout 240 --out labs\meaning_compression_lab\results\generative_governance_live_renderer_expanded_qwen3_14b_nothink_latest.json` -> passed

### Governed renderer choice

The same governed packet was rendered locally and through Grok CLI while
Aether retained authority. Workbench dogfood proved provider selection,
disclosure, fallback, provider receipts, restart, and rehydration in an isolated
profile.

Proven:

- provider-neutral wording authority is viable;
- hosted rendering can improve strict instruction following;
- deterministic Aether boundaries can bypass the hosted model entirely;
- no provider received retrieval, durable-memory, or write authority.

Not proven:

- broad answer superiority;
- production API billing/cost behavior;
- stable commercial CLI semantics;
- privacy/budget/cancellation controls suitable for other users.

Evidence: `artifacts/governed-renderer-choice-lab/RESULTS_2026-07-17.md`.

### Authority-constrained causal evidence receipts

The isolated causal-receipt instrument tested origin-bound authority and
provider-neutral wording. It passed its deterministic synthetic gate and
preserved withheld-value boundaries. Grok required a recorded two-turn
transport adaptation after the exact one-turn CLI path failed twice.

Proven: the stated synthetic receipt and conservation rules execute
reproducibly.  
Not proven: external causal discovery, production graph construction, or
general real-world truth inference.

Evidence: `artifacts/causal-evidence-receipt-lab/RESULTS_2026-07-18.md`.

### Epistemic Circuit Breaker

The isolated circuit-breaker lab combined provenance-root quotienting,
commit-time authority, conservative influence stability, finite-horizon fanout
impact, protected paths, held contradictions, and minimum safe cuts.

First fitted result:

- 120 synthetic cases;
- exact and greedy safety gates passed;
- Qwen followed the exact renderer contract 1/8 but was semantically faithful
  8/8;
- Grok followed the exact contract 8/8;
- the overall gate remained false because the renderer contract required every
  provider to pass.

First implementation-blind reveal:

- 96 cases with independently constructed expectations;
- 72/96 exact actions;
- 24 unsafe synthetic accepts;
- failures were exactly eight low-authority-independent, eight blank-
  provenance, and eight parallel-signed-channel cases;
- the failure snapshot was preserved before repair.

Repairs:

- enforce `derived_authority >= required_authority`;
- validate nonblank, unique, parent-complete, acyclic, session-ordered,
  root-consistent, non-escalating provenance;
- sum magnitude contributions before parallel signed-channel composition;
- state quarantine truthfully as advisory no-write containment.

Post-repair regression:

- focused and adjacent lab tests: 16 passed;
- original fitted corpus: 120/120;
- same revealed blind pack: 96/96 actions and reasons;
- unsafe synthetic accepts: 0;
- benign accepts retained: 24/24;
- exact independent-cut agreement: 96/96.

Important limitations:

- this is a revealed-pack regression, not a second blind replication;
- graph structure, gains, authority labels, and thresholds are synthetic;
- only 16/24 benign blind cases stayed safe under -10%, nominal, and +10%
  weight scales;
- greedy cuts were safe but cost 1.54 instead of the exact 1.15 in eight signed
  cases;
- quarantine commits no safe remainder and therefore has not shown realized
  product utility over rejection;
- formal novelty, external scenarios, and empirical graph calibration remain
  open;
- the circuit breaker is not wired into production Aether.

Evidence:

- `artifacts/epistemic-circuit-breaker-lab/RESULTS_2026-07-18.md`
- `artifacts/epistemic-circuit-breaker-blind-replication/RESULTS_FIRST_REVEAL_2026-07-18.md`
- `artifacts/epistemic-circuit-breaker-blind-replication/blind_result_first_reveal_20260718.json`
- `artifacts/epistemic-circuit-breaker-blind-replication/post_repair_regression_20260719.json`
- `artifacts/epistemic-circuit-breaker-blind-replication/REPAIR_CLOSURE_2026-07-19.md`

Preserved evidence hashes:

- first blind seal: `23d3fa41765306742ec536484ba0cf625a514452f72b91243bf6a2fe96d5cf78`;
- first blind failure result: `c913372cbda6ce7c3dd32c7827f53f2a14ab70375ce1a150f092737eef230335`;
- repaired target: `9a7c4f84a3f771ea5c7e47025f2f19b2b2ba2dac5a463ac648386bc9edc75211`;
- post-repair result: `b64c2129c91d2ebf760441f67f700352ee240637c49acfd25c28128fa834a459`.

### Other research disposition

- Mirus belief maps: useful advisory lab; broad product wiring paused.
- Governed synthesis/tension packets: bounded slices complete; broad routing
  paused until a concrete Workbench failure requires it.
- Global-workspace probe: research evidence, not a product blocker.
- J-lens: plumbing smoke exists; dense fitting/scoring is optional research.
- Trust-magnitude retrieval: promising lab signal, not a live authority rule.
- Archive archaeology and model shopping: parked unless a named missing
  mechanism or frozen capability question reopens them.

## What the combined work proves

The defensible combined claim remains narrow:

> Aether can govern evidence release, authority, persistence, response
> contracts, and provider-neutral rendering with durable receipts, and these
> controls can outperform prompt-only or ordinary retrieval baselines on
> bounded synthetic evaluations.

The work does not prove:

- general answer superiority;
- perfect control reliability;
- arbitrary executable recovery from old conversations;
- automatic truth discovery or calibrated belief graphs;
- production readiness for a commercial hosted provider;
- formal novelty or patentability;
- another-user operability without an external pilot.

## Exact resume point

Return to Aether, not research.

```text
1. Preserve the existing dirty worktrees.
2. Review and revalidate the current cross-conversation + hosted-renderer diff.
3. Checkpoint it deliberately.
4. Specify the smallest explicit TaskContinuationPacket.
5. Prove that only explicit/reviewed task state becomes executable.
6. Freeze a held-out multi-thread task-state pack.
7. Dogfood API, Workbench, restart, and reopened UI before closure.
```

Do not integrate the circuit breaker, reopen broad Mirus/synthesis/J-lens work,
or start another model comparison while this gate is active.
