# Sub-Agents & Orchestration

**Version:** v2.6 (March 24, 2026)
**Sprint:** 8
**Files:** `personal_agent/sub_agents.py`, `personal_agent/orchestrator.py`

---

## Overview

Complex requests get decomposed into subtasks, each handled by a specialized sub-agent. Independent subtasks run in parallel via `asyncio.gather()`. Trust follows CRT's weakest-link principle: the merged result trust is the minimum across all branches.

Example: "check my system and read the config file" → SystemInfoAgent + FileAgent run concurrently → results merged with `min(trust_a, trust_b)`.

---

## Architecture

```
User: "check my system and then commit the changes"
                │
                ▼
        ┌───────────────┐
        │ TaskOrchestrator│
        │  (decompose)   │
        └───────┬───────┘
                │
    ┌───────────┴───────────┐
    ▼                       ▼
┌──────────┐         ┌──────────┐
│SubTask 1 │         │SubTask 2 │
│system_info│  ──→   │git_action │  (depends_on: task 1)
└─────┬────┘         └─────┬────┘
      ▼                     ▼
┌──────────────┐    ┌──────────────┐
│SystemInfoAgent│    │  GitAgent    │
└──────────────┘    └──────────────┘
```

---

## Sub-Agent Protocol

### SubTask

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Unique identifier |
| `intent_type` | str | Routing key (e.g. "system_info", "file_read") |
| `message` | str | The user's message or extracted sub-message |
| `slots` | Dict | Extracted parameters (path, command, etc.) |
| `depends_on` | List[str] | Task IDs that must complete first |
| `input_from` | Dict[str, str] | Parameter name → source task_id for data piping |

### SubTaskResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Matches the SubTask |
| `agent_name` | str | Which agent handled it |
| `status` | str | "ok" or "error" |
| `output` | Any | The actual result data |
| `output_preview` | str | Truncated to 200 chars for display |
| `confidence` | float | Agent's confidence in the result |
| `source_trust` | float | Trust of input data |
| `propagated_trust` | float | `min(confidence, source_trust)` |
| `duration_ms` | int | Execution time |
| `receipt_id` | str | ActionReceipt ID for audit trail |

### Trust Propagation

Each agent has a fixed confidence level:

| Agent | Confidence | Rationale |
|-------|-----------|-----------|
| SystemInfoAgent | 0.95 | Read-only system data |
| FileAgent (read) | 0.95 | Read-only file access |
| FileAgent (write) | 0.90 | Writes are verified |
| CommitmentAgent | 0.90 | Deterministic operations |
| ShellAgent | 0.85 | External process output |
| GitAgent | 0.85 | External process output |
| DesktopToolAgent | 0.80 | Vision-dependent |
| WebFetchAgent | 0.70 | External source, unverified |
| GenerationAgent | 0.60 | LLM output, needs verification |

Propagated trust = `min(agent_confidence, source_data_trust)`. The weakest link always wins.

---

## 8 Concrete Agents

### SystemInfoAgent
- **Capabilities:** `system_info`
- **Action:** Calls `system_info.get_system_snapshot()` + `format_snapshot_text()`
- **Source trust:** 1.0 (local hardware data)

### FileAgent
- **Capabilities:** `file_read`, `file_write`, `dir_list`, `project_scan`
- **Action:** Dispatches to `file_tools.read_file()`, `write_file()`, `list_directory()`, `scan_project()`
- **Uses different confidence keys:** 0.95 for reads, 0.90 for writes

### ShellAgent
- **Capabilities:** `shell_exec`
- **Action:** Calls `shell_tools.execute_command(command, cwd)`

### GitAgent
- **Capabilities:** `git_action`
- **Action:** Calls `shell_tools.execute_git(args, cwd)`
- **Fallback:** Regex extracts git subcommand from message if no args provided; defaults to `git status`

### WebFetchAgent
- **Capabilities:** `url_fetch`, `service_action`
- **Action:** Calls `task_agent._http_get(url)`
- **Source trust:** 0.70 (external unverified data)

### DesktopToolAgent
- **Capabilities:** `desktop_action`
- **Action:** Creates `DesktopAgent` with vision provider + memory context, runs the full ReAct loop

### GenerationAgent
- **Capabilities:** `generate_content`, `llm_respond`
- **Action:** Builds prompt, calls `llm.chat(prompt)`
- **Confidence:** 0.60 (LLM output needs CRT verification)

### CommitmentAgent
- **Capabilities:** `create_commitment`, `list_commitments`, `cancel_commitment`
- **Action:** Delegates to `commitments` module functions with extracted slots

---

## TaskOrchestrator

### Decomposition

`decompose(message, triage_result) → List[SubTask]`

- **Single intent:** returns one SubTask
- **Multi-intent:** creates one SubTask per sub-intent from the triage result's `intents` list, then runs `_detect_dependencies()` to wire up edges

### Dependency Detection

Four rules, checked in order:

1. **Sequential language:** "then", "after that", "once that", "when done" → chains all tasks sequentially
2. **generate_content → file_write:** pipes generated `content` into the write task
3. **url_fetch → llm_respond/service_action:** pipes `fetched_content`
4. **Otherwise:** tasks are independent (parallel)

### Execution

`execute(subtasks, ctx) → OrchestratorResult` (async):

1. Creates orchestration ID, emits `orchestration_start` SSE event
2. **Ready detection:** tasks whose dependencies are all satisfied
3. **Blocked detection:** tasks whose dependencies failed → marked as errors
4. **Input piping:** resolves `input_from` by copying completed task outputs into slots, including `_source_trust` propagation
5. **Parallel execution:** `asyncio.gather(*ready_tasks)`
6. **Deadlock detection:** remaining tasks with unsatisfied deps
7. **Trust merge:** `min(all propagated_trusts)` — weakest link
8. Logs orchestration receipt, emits `orchestration_done`

### SSE Events

| Event | When | Payload |
|-------|------|---------|
| `orchestration_start` | Execution begins | orchestration_id, subtask_count |
| `subtask_start` | Agent begins work | task_id, agent_name, intent_type |
| `subtask_done` | Agent completes | task_id, status, duration_ms, preview |
| `orchestration_done` | All tasks complete | merged_trust, completed, failed, duration_ms |

---

## Frontend Integration

`AgentThinkingStrip.tsx` renders orchestration progress:
- Shows each subtask with agent name and status
- Parallel tasks shown side-by-side
- Trust propagation visualized on completion

---

## Schema Changes

The `action_receipts` table gained two columns:
- `agent_name` — which sub-agent created the receipt
- `orchestration_id` — links receipts to the same orchestration run
