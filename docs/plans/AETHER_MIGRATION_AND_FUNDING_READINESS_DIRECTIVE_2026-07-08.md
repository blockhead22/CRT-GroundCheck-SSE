# Aether Migration and Funding Readiness Directive

Date: 2026-07-08

Purpose: preserve the current repo/folder truth and define clear gates for when Aether should move from broad research/thesis work into serious funding search, LLC filing, and clean repo migration.

## Current Folder Truth

`D:\AI_round2\aether-core` is the active, most current sidecar/core implementation.

`D:\AI_round2\workbench` is the active Workbench UI.

`D:\AI_round2\personal_agent` currently contains project-local data referenced by environment config, including `crt_facts.db`.

`D:\crt-core` exists as an older git repo. It is not live in the current Workbench/sidecar process. Treat it as archive / possible open-source ancestor material until explicitly compared against `D:\AI_round2\aether-core`.

Do not delete or overwrite `D:\crt-core` casually. Do not treat it as current truth without a diff/review pass.

## Migration Buckets

### 1. Archive / Reference

Holds old experiments, historical CRT/Aether ideas, GPT/archive-derived materials, old frontend work, legacy labs, old maps, and abandoned prototypes.

Rules:
- Read-only by default.
- Useful for archaeology, prompt mining, and concept recovery.
- Not imported as confirmed memory.
- Not shipped as product code without review.

### 2. Open-Source-Safe

Potential future public repo for generic primitives only.

Good candidates:
- trace/event schemas
- review-candidate schemas
- safety-contract primitives
- small eval harnesses
- generic governed-synthesis examples with no personal data

Keep out:
- Nick-specific memory/archive data
- private GPT logs or transcript bodies
- Workbench personality/support tuning
- private roadmap/funding notes
- proprietary Mirus/Holden product wiring until deliberately sanitized

Open source is a credibility artifact later, not the main lane now.

### 3. Clean Proprietary Working Dir

Future private source of truth for the serious Aether product.

Contains:
- Workbench
- current sidecar/core
- Mirus/Holden/CRT product wiring
- governed memory/review flows
- archive evidence flows
- private labs that directly support product behavior
- funding/demo evidence

This is the repo that should be cleaned first when Aether becomes a business/funding project.

## Funding / LLC Readiness Gates

Aether is ready for a serious funding search when these are true:

1. A clean private repo exists and runs from a fresh checkout.
2. Workbench can demonstrate the core loop end to end:
   - ask a question
   - retrieve governed memory or source-bound evidence
   - form a visible Thinking / Process trace
   - produce a non-canned governed answer
   - create review-only candidates when appropriate
   - prove rejected/deferred candidates do not affect behavior
3. A focused demo pack passes consistently, including:
   - memory recall
   - multi-fact synthesis
   - contradiction / held-tension prompts
   - archive-vs-confirmed-memory boundaries
   - project-context routing
   - code/search tool routing
4. The evidence story is short and legible:
   - raw/local baseline
   - scaffolded RAG baseline
   - governed Aether result
   - failure cases and limits
5. The product claim is narrow:
   - governed local AI workbench for memory, trace, contradiction, and review
   - not a frontier-model competitor
   - not an autonomous self-mutating memory system
6. There is a practical user workflow:
   - daily chat
   - memory review
   - trace inspection
   - archive evidence review
   - project/tool routing
7. Private data boundaries are documented:
   - no raw hidden chain-of-thought as durable truth
   - no silent memory/support/reflection writes
   - archive/GPT logs are evidence, not confirmed facts
8. The repo no longer depends on messy folder state or accidental local paths.

Aether is ready for LLC filing when:

- the private repo/folder cleanup has happened or has a dated execution plan;
- there is a coherent product name/entity direction;
- there is a realistic 60-90 day build plan;
- at least one demo scenario is strong enough to show another person without narrating every caveat;
- the near-term business goal is concrete enough to need contracts, grants, vendors, public presence, or separate finances.

## Not Ready If

Do not start the funding/LLC push if:

- the live system still depends on unknown dirty local state;
- the strongest demos require manual explanation to hide obvious canned behavior;
- archive/GPT material is being treated as confirmed truth;
- the core claim keeps changing every session;
- open-source packaging would consume the next build sprint;
- the product cannot be described in one plain paragraph.

## Current Plain Claim

Aether is a governed local AI workbench that helps smaller/local models behave more reliably by moving memory, evidence, trace, contradiction handling, review, and synthesis scaffolding into an inspectable system around the model.

The current build direction is not "make a smarter model." It is "make local AI behavior more governable, inspectable, and personally useful without silently mutating memory or flattening uncertainty."

## Next Migration Action

When the project enters the funding/LLC phase, run this sequence:

1. Verify `D:\AI_round2\aether-core` tests and Workbench smoke.
2. Snapshot `D:\AI_round2` and `D:\crt-core`.
3. Diff `D:\crt-core` against `D:\AI_round2\aether-core` for reusable open-source-safe primitives.
4. Create the clean private working directory.
5. Move only active product code and necessary docs.
6. Create archive storage for old labs and historical references.
7. Decide later whether to create a tiny open-source-safe repo.

