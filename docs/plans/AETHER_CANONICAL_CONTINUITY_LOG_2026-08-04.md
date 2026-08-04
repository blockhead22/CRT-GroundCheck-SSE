# Aether Canonical Continuity Log

**Snapshot date:** 2026-08-04
**Workspace:** `D:\AI_round2`
**Status:** Saved continuity checkpoint; no implementation lane is implicitly active

This is the operational restart packet after the July 30 live golden-path
acceptance. It supersedes the July 20 packet for current Git, runtime, and
next-step state. The July 20 packet remains the detailed product/research
history and authority-boundary record.

## Start Here

Read in this order:

```text
D:\AI_round2\docs\plans\AETHER_CANONICAL_CONTINUITY_LOG_2026-08-04.md
D:\AI_round2\docs\plans\AETHER_UNIFIED_ROADMAP_2026-07-16.md
D:\AI_round2\docs\plans\AETHER_CURRENT_STATE.md
D:\AI_round2\docs\plans\AETHER_CANONICAL_CONTINUITY_LOG_2026-07-20.md
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
```

Do not restart broad archive archaeology. Read older plans only for a named
missing mechanism or disputed decision.

## One-Line State

Aether remains a working local-first governed-assistant prototype. Its value is
the explicit evidence, memory review, contradiction, authority, verification,
repair, and durable public trace wrapped around replaceable models, not an
attempt to beat foundation-model progress or claim AGI.

The bounded continuity/task-authority gate and the July 30 live golden-path
gate are closed. No product code has changed since that acceptance. There is no
silent active lane as of this checkpoint.

## Verified Repository State

Snapshot taken 2026-08-04 before writing this packet.

Root repository:

```text
path:   D:\AI_round2
branch: codex/repo-cleanup-archive
HEAD:   5dba33df8 Add tool-approval policy and auto-approve setting
origin: origin/codex/repo-cleanup-archive at the same commit
state:  clean before this continuity update
```

Nested runtime repository:

```text
path:   D:\AI_round2\aether-core
branch: master
HEAD:   7689f38 Treat runtime identity queries as self-contained
origin: origin/master at the same commit
state:  clean
```

`aether-core` is a separate nested Git repository. Root Git status is never
enough to establish the runtime state.

## Changes Since the July 20 Packet

### Governed exact-patch approval

The real sidecar and Workbench now expose a persisted tool-approval policy.
The default remains manual. A ready exact patch may be applied only through an
explicit approval endpoint or an explicit opt-in policy. Applies are bound to
the proposed file hash and produce receipts distinguishing
`explicit_review` from `policy_auto_approve`.

Live acceptance proved:

- proposal-only mode leaves the file unchanged;
- stale file content is rejected with HTTP 409;
- explicit approval applies exactly once with a durable receipt;
- opt-in auto-approval records a different approval mode;
- the policy can be returned to manual/off.

Automatic shell authority, arbitrary writes, retrieval escalation, and silent
policy mutation remain outside this grant.

### Completion-verification repairs

Two false reference failures were repaired in `aether-core`:

1. A current-turn runtime identity query such as "what model answered this
   message?" no longer requires prior conversation context. It is checked
   against the authoritative runtime receipt.
2. A same-prompt transform such as "Treat it as review-only evidence" now
   recognizes its local antecedent instead of being misclassified as a
   cross-turn reference.

Both repairs have focused and sidecar regression coverage.

## July 30 Live Golden-Path Acceptance

The real Workbench, sidecar, and Ollama path ran against an isolated synthetic
profile at:

```text
C:\Users\block\AppData\Local\Temp\AetherGoldenPath-20260730
```

The normal Aether profile, private archive, and production workspace were not
modified by the acceptance run.

Result: `PASS`.

Verified scenarios:

- Workbench, sidecar, and Ollama startup;
- authoritative current-turn runtime identity and public 5/5 trace;
- memory write, recall, explicit correction, and retained superseded history;
- persistence across multiple sidecar restarts;
- two confirmed current values classified as a held contradiction, with both
  surfaced instead of silently selecting a winner;
- manual patch proposal, stale-hash rejection, explicit apply, and opt-in
  policy auto-apply;
- bounded review-only archive search with zero profile-memory writes;
- rendered Workbench interaction with no console errors or error overlay;
- cleanup with ports 5175, 8765, and 11434 closed.

Verification evidence:

```text
backend focused/regression tests: 33 passed
Workbench UI tests:               73 passed
Electron tests:                   26 passed
Workbench production build:      passed
git diff check:                   passed
```

The receipt and screenshots remain at the isolated acceptance root:

```text
golden-path-acceptance-report.md
golden-path-acceptance-receipt.json
identity-gate-pass.png
identity-trace-pass.png
settings-manual-default.png
held-contradiction-pass.png
```

## Current Runtime State

Checked 2026-08-04:

```text
Workbench/Vite 127.0.0.1:5175: stopped
Aether sidecar 127.0.0.1:8765: stopped
Ollama 127.0.0.1:11434: stopped
```

An open browser tab at the Workbench URL is not evidence that the services are
running. Re-check the actual TCP ports and `/health` before live claims.

Current global Aether substrate snapshot:

```text
state path:              C:\Users\block\.aether\mcp_state.json
memories:                438
edges:                   3732
Belnap T:                436
Belnap Both:             2
related_to edges:        3692
contradicts edges:       40
held contradictions:     1
evolving contradictions:1
embeddings available:    yes
embeddings loaded:       no
embeddings state:        warming
```

This substrate snapshot is observational. It does not promote, resolve, or
delete any memory or contradiction.

## Authority and Safety Invariants

Preserve these boundaries:

```text
No raw hidden chain-of-thought stored as truth.
No automatic profile-memory writes from model output or archive material.
No automatic task authority from prose or model proposals.
No automatic workspace execution from continuity alignment.
No silent tool escalation, model switching, or policy mutation.
No cross-profile evidence leakage.
No stale-revision acceptance.
Rejected, revoked, and superseded state remains behaviorally inert.
Archive-derived material remains review-only until explicitly promoted.
```

Normal human-facing synthesis may be model-generated from governed evidence.
Deterministic output remains appropriate for authority boundaries, runtime
identity, exact receipts, and safe fallback, not as a replacement for every
answer.

## Current Decisions and Non-Decisions

Decided:

- the July 30 golden path is accepted;
- exact-patch auto-approval is opt-in and the tested profile was restored to
  manual/off;
- the failed semantic-task proposer remains disconnected;
- the governed hosted read-only tool lab is not a production permission grant;
- distribution work was previously passed over for that round.

Not decided by this checkpoint:

- whether desktop distribution should resume now;
- whether to reopen semantic intake with a new mechanism and untouched holdout;
- which daily-use workflow becomes the next product wedge;
- whether exact-patch auto-approval should ever be recommended beyond isolated
  or explicitly trusted workspaces.

## Recommended Next Work

The smallest evidence-backed ladder is:

1. Automate the July 30 isolated golden-path gate into one repeatable command
   that creates a synthetic profile, runs the checks, emits a receipt, and
   cleans up only its own processes.
2. Reduce the observed 30-32 second local `qwen3:14b` exact-patch proposal
   latency without weakening hash binding, verification, or approval receipts.
3. Select and dogfood one real recurring daily loop:
   `capture -> governed memory/task -> reminder/continuity -> review`.
4. Resume distribution readiness only after an explicit lane decision.

Do not substitute another broad research lab for a selected product miss.

## Fast Resume Checks

```powershell
git -C D:\AI_round2 status --short --branch
git -C D:\AI_round2\aether-core status --short --branch
git -C D:\AI_round2 rev-parse HEAD
git -C D:\AI_round2\aether-core rev-parse HEAD
Get-NetTCPConnection -LocalPort 5175,8765,11434 -State Listen -ErrorAction SilentlyContinue
```

If code changes touch the July 30 gate, rerun the focused backend checks plus:

```powershell
cd D:\AI_round2\workbench
npm test
npm run build
```

Rendered frontend changes still require an actual browser check of page
identity, meaningful content, interaction, console health, error overlays, and
screenshots.

## Clean Restart Prompt

```text
We are continuing Aether in D:\AI_round2.

Read first:
1. docs/plans/AETHER_CANONICAL_CONTINUITY_LOG_2026-08-04.md
2. docs/plans/AETHER_UNIFIED_ROADMAP_2026-07-16.md
3. docs/plans/AETHER_CURRENT_STATE.md
4. docs/plans/AETHER_CANONICAL_CONTINUITY_LOG_2026-07-20.md

Repository state at the checkpoint:
- root repo: codex/repo-cleanup-archive at 5dba33df8;
- nested aether-core: master at 7689f38;
- both matched origin and were clean before the continuity-doc update;
- check both Git statuses before editing.

The July 30 isolated golden-path gate passed runtime identity, governed memory,
restart persistence, held contradiction, exact-patch approval/stale rejection,
archive non-write boundaries, rendered UI, and cleanup. The normal profile was
not used for the gate.

All three local services were stopped on August 4. Do not infer a live runtime
from a stale browser tab.

No implementation lane is implicitly active. The recommended next slice is to
automate the isolated gate, then choose a concrete daily-use loop or explicitly
resume distribution. Preserve all authority and no-write boundaries.
```

## Final Continuity Statement

The project did not become obsolete because models improved. The durable value
is the local, inspectable contract around evidence, personal continuity,
authority, contradiction, writes, and verification. The July 30 gate proved
that contract across the real product path. The next phase should make that
proof cheap to repeat and connect it to one daily behavior that matters.
