# Aether Local Coder v1

## Goal

Let a small local model complete bounded coding tasks through Aether without
turning the Workbench into a general autonomous-agent harness.

Reference implementation notes were reviewed from:

`C:\Users\block\Downloads\src\src`

The useful lesson is the contract around tools, not the size of the tool catalog.

## Minimum useful loop

```text
User coding request
  -> semantic task planner
  -> workspace search/read tools
  -> proposed patch and test command
  -> explicit user approval
  -> bounded edit
  -> bounded test
  -> visible diff, output, and governed receipt
```

## Initial tool set

1. `workspace_search`
   - Search filenames and file contents.
   - Read-only and workspace-bounded.
   - Return capped, paginated results.

2. `workspace_read`
   - Read a bounded line range.
   - Reject files outside configured workspace roots.
   - Record file hash and modification time for stale-write protection.

3. `workspace_patch_propose`
   - Produce a structured patch without writing it.
   - Show affected paths and the exact proposed diff.

4. `workspace_patch_apply`
   - Require explicit approval for the displayed patch.
   - Reject paths outside configured roots.
   - Reject application when a file changed after it was read.
   - Store an auditable before/after receipt.

5. `workspace_test`
   - Run only configured project test commands.
   - Use a timeout, output cap, and cancellable child process.
   - No arbitrary shell in v1.

6. `workspace_diff`
   - Show the resulting local diff and changed-file summary.
   - Never commit, push, delete, or publish.

## Small-model scaffold

The local model does not need native tool-calling support. Aether can classify
the request, select the next permitted tool, serialize the result into a small
observation packet, and ask the model what to do next.

The loop must have hard limits:

- maximum tool steps per task;
- maximum files read;
- maximum patch size;
- one approved write batch;
- one configured verification command;
- no automatic retry after a failed write;
- stop and ask when evidence is missing or ambiguous.

## Safety contract

- Read operations may run automatically inside configured workspace roots.
- Every write requires a visible patch and explicit approval.
- Existing files must be read before modification.
- Writes fail when the file hash or modification time changed since reading.
- UNC/network paths, secrets files, binaries, and paths outside roots are denied.
- Commands are selected from project-configured test recipes, not generated
  arbitrary PowerShell.
- Destructive file operations, Git writes, network calls, background agents,
  commits, pushes, and pull requests are excluded from v1.

## UI additions

- A **Coder** mode beside Chat.
- A compact task plan showing current step and remaining tool budget.
- Expandable search/read receipts.
- Patch review with Approve and Reject.
- Streaming test output with Stop.
- Final changed-files, test result, and governed decision receipt.

## Graduation order

1. ~~Improve the current read-only search/read tools using bounded line ranges
   and content search.~~ Completed June 20, 2026.
2. ~~Add patch proposal with no write capability.~~ Completed June 20, 2026.
3. ~~Add approval-gated patch application and stale-file rejection.~~ Completed
   June 20, 2026, including natural-language single-file patch planning through
   the selected local Ollama model.
4. Add configured test recipes.
5. Evaluate small-model task completion on a tiny repository fixture.
6. Only after those pass, consider longer-running background coding tasks.
