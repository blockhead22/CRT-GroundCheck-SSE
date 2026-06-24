# Aether Code Context Tools v1

## Goal

Make Aether useful for first-pass code/project work without turning the
Workbench into an autonomous coding agent.

The v1 contract is:

```text
local code context + governed memory + visible traces + bounded patch previews
+ explicit approval for writes + governed test capture + clean escalation
```

Reference implementation notes were reviewed from:

```text
C:\Users\block\Downloads\src\src
```

The useful lesson is the contract around tools, permissions, and visible task
state, not copying another agent's tool catalog.

## Current Implemented Tools

### `workspace_search`

Purpose: find relevant source files or symbols.

Behavior:

- read-only;
- workspace-root bounded, with optional read-only reference roots from
  `AETHER_WORKSPACE_REFERENCE_ROOTS` or `AETHER_CODE_REFERENCE_ROOTS`;
- searches filenames and bounded text content;
- ignores generated/noisy directories such as `.claude`, `.eval-runs`,
  `artifacts`, `logs`, `build`, `dist`, `node_modules`, and caches;
- returns capped results with path, relative path, score, byte count, hit
  counts, and excerpts.

Trace requirements:

- record tool name/status/input/output;
- show top path/results in Trace drawer;
- show compact retrieved snippet excerpts/results, not only the top path.

### `workspace_read`

Purpose: read a specific local file or bounded line range.

Behavior:

- read-only;
- workspace-root bounded, with optional read-only reference roots;
- rejects missing files and paths outside configured roots;
- supports line ranges;
- caps returned content;
- records `sha256` and `mtime_ns` for stale-write protection.

Trace requirements:

- path;
- line range;
- truncation flag;
- hash/mtime metadata;
- captured content in trace JSON.
- bounded content block visible in the Trace drawer.

### `workspace_patch_propose`

Purpose: preview a bounded single-file patch without writing.

Behavior:

- never writes;
- workspace-root bounded;
- requires exact old/new text or model-generated exact replacement after reading
  the bounded source file;
- rejects ambiguous old text;
- records patch readiness and stale hash;
- `applied=false` until a separate approval-gated apply route succeeds.

Trace requirements:

- path;
- `ready`;
- `applied`;
- `sha256`;
- diff preview;
- rationale/verification when model-generated;
- competency checks including `write_performed=false`.

UI requirements:

- patch preview visible;
- approval button only when ready and not already applied;
- applied receipt visible after approval.

### `workspace_patch_apply`

Purpose: apply an already displayed exact patch after explicit approval.

Behavior:

- only accepts a stored `workspace_patch_propose` tool run;
- requires explicit approval and idempotency key;
- rejects stale file hash;
- rejects non-ready or already-applied patches;
- records before/after hash and receipt.

Trace requirements:

- applied output is persisted back onto the tool run;
- receipt id is visible in the Trace drawer.

### `workspace_test_recommend`

Purpose: recommend a focused verification command without running it.

Behavior:

- read-only;
- workspace-root bounded;
- maps a source file to the nearest deterministic focused test file;
- currently strongest for Python/pytest;
- records `executed=false` and `write_performed=false`.

Trace requirements:

- source path;
- cwd;
- command;
- test file;
- confidence/reason;
- `executed=false`.

### `workspace_test_run`

Purpose: run the focused recommended test when the user explicitly asks to run
or capture the result.

Behavior:

- not arbitrary shell access;
- currently limited to Python pytest;
- reuses the deterministic source-file-to-test-file mapping;
- runs via `subprocess.run([...], shell=False)`;
- cwd must remain inside configured workspace roots;
- applies a timeout;
- captures stdout/stderr with output caps;
- records `executed=true`.

Trace requirements:

- source path;
- cwd;
- command and argv;
- test file;
- `executed=true`;
- `execution_kind=pytest`;
- exit code;
- pass/fail;
- timeout status;
- duration;
- stdout/stderr;
- safety metadata:
  - `shell=false`;
  - `workspace_bounded=true`;
  - `arbitrary_command_allowed=false`.

UI requirements:

- metadata rows for command, test file, executed, exit code, pass/fail, timeout,
  duration, and safety/write status;
- clipped stdout/stderr blocks.

## Tool Selection Rules

Read/search may happen automatically for clear code-context requests.

Patch proposal may happen automatically only as preview when the user asks to
preview/propose/draft/change/update a file and a bounded target path is known.

Patch application never happens automatically. It requires a visible patch and
explicit approval.

Planning-only phrases such as:

```text
Do not edit yet
no edits yet
planning only
do not patch yet
```

must suppress patch proposal and prefer read/search/test recommendation.

Test recommendation may happen automatically for focused-test questions.

Test execution requires explicit run/capture phrasing such as:

```text
run the focused test
run pytest
execute pytest
capture the test result
run the test command
```

## Safety Contract

- All filesystem tools are bounded to configured workspace roots.
- Search/read/list may also use explicitly configured read-only reference roots.
- Reads are allowed; writes require explicit patch approval.
- Patch proposal, patch apply, and test execution remain bounded to writable
  workspace roots, not reference roots.
- Test execution is not a general command runner.
- v1 excludes arbitrary PowerShell, Git writes, commits, pushes, PRs, network
  actions, destructive file operations, background agents, and self-directed
  multi-step autonomy.
- Tool output is untrusted evidence for answer generation but trusted as a
  record of what Aether's deterministic tool layer observed or did.
- The model must not claim a preview patch was applied.
- The model must not claim a recommended test was run.
- The model must report executed test results using trace fields, not guesswork.

## Eval Coverage

Current live eval baseline:

```text
D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_141221.json
Aether Workbench eval: 19/19 passed
```

Programming cases currently include:

- `programming_code_search_trace_drawer`;
- `programming_code_read_depth_module`;
- `programming_patch_preview_depth_guidance`;
- `programming_planning_only_test_recommendation`;
- `programming_test_recommendation_tool_depth`;
- `programming_test_result_capture_depth`.

They verify:

- completed tool run presence;
- path capture;
- patch readiness/applied state;
- forbidden patch absence during planning-only asks;
- test recommendation non-execution;
- governed pytest execution;
- answer content.

Additional focused code-tool tests verify that:

- configured reference roots are searched and surfaced separately from writable
  workspace roots;
- reference roots can provide code evidence/snippets;
- reference roots are refused as patch targets.

Additional live eval support verifies that:

- `scripts/workbench_eval.py --include-reference-root-eval` adds an opt-in
  reference-root case against `bridge/bridgePermissionCallbacks.ts`;
- `--case-id` can run only that case for focused validation;
- exact-symbol search scoring and prompt path highlights make local answers
  report retrieved file paths instead of plausible remembered paths.

Additional tiny-fixture programming tests verify that:

- a small Python repo can run a focused pytest file and capture a failing result
  without shell access;
- a small TypeScript package produces a non-executed package test
  recommendation;
- exact-symbol search in a noisy tiny repo ranks the intended file over generic
  repeated vocabulary;
- prompt path highlights stay present for workspace search results.

Additional focused escalation tests verify that programming escalation packets:

- include a bounded `programming_context` only when workspace tools were used;
- merge search excerpts and read content for the same relevant file;
- summarize patch readiness/errors and captured test failure output;
- keep large read/test content clipped before sending it to Codex.

## Next Work

1. Add richer diagnostics/LSP-style read support after the escalation path is
   inspectable.

## Out Of Scope For v1

- autonomous multi-file implementation;
- arbitrary terminal access;
- Git commit/push/PR automation;
- background agents;
- package installers;
- secret scanning/remediation beyond refusing unsafe paths/actions;
- LSP diagnostics;
- long-running task queues.

Those can be considered only after the current search/read/patch/test/trace loop
is stable, visible, and boringly reliable.
