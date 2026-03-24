# Agentic Tool Loop

**Sprint 14 / v3.1** — LLM-driven ReAct loop for the main chat pipeline.

## Problem

The previous pipeline classified a message once, pre-built a static plan, executed steps blindly, and formatted a response. The LLM never saw intermediate tool results and never decided what to do next based on what happened.

This meant "read this file then copy it to D:/AI_round2/" would read the file successfully but never copy it — the router picked one tool, ran it, and stopped.

## Solution

A true agentic loop where the LLM:
1. Sees the user's message and available tool definitions
2. Decides which tool(s) to call
3. Executes the tool and sees the result
4. Decides again — another tool, or a final text response
5. Repeats until done or max iterations reached

This is the same ReAct pattern used by `desktop_agent.py` (screenshot -> think -> act -> verify), now applied to the general tool pipeline.

## Architecture

```
User Message
    |
    v
[Intent Classification] (existing, unchanged)
    |
    v
[Agent Loop Enabled?] ----No----> [Legacy Path (classify -> plan -> execute)]
    |
   Yes
    v
+--[AgentToolLoop.run()]--+
|                          |
|  System prompt + tools   |
|  + conversation history  |
|         |                |
|         v                |
|  [LLM chat_with_tools]  |
|         |                |
|    tool_calls?           |
|    /         \           |
|  Yes         No          |
|   |           |          |
|   v           v          |
| [Checkpoint?] [Final text] --> SSE: token + done
|   /     \     |          |
| Yes      No   |          |
|  |        |   |          |
|  v        v   |          |
| SSE:    [Execute tool]   |
| checkpoint  |            |
| (pause)     v            |
|         [Append result   |
|          to messages]    |
|             |            |
|             +---> loop   |
+---------------------------+
```

## Files

| File | Role |
|------|------|
| `personal_agent/agent_tool_loop.py` | Core loop engine, tool execution bridge, checkpoint logic |
| `routes/chat.py` | Integration: agent loop path + checkpoint resume handler |
| `personal_agent/runtime_config.py` | Config defaults for the agent loop |
| `frontend/src/lib/api.ts` | SSE event types and callbacks |

## Configuration

In `crt_runtime_config.json`:

```json
{
  "agent_loop": {
    "enabled": true,
    "model": "auto",
    "max_iterations": 10,
    "show_thinking": true
  }
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Enable the agentic loop (vs legacy classify-once path) |
| `model` | string | `"auto"` | LLM provider: `"local"` (Ollama), `"cloud"`, or `"auto"` |
| `max_iterations` | int | `10` | Max tool calls per request (safety cap, range 1-25) |
| `show_thinking` | bool | `true` | Show LLM reasoning between tool calls in the UI |

## SSE Events

The agent loop emits these events to the frontend via SSE:

| Event Type | When | Payload |
|-----------|------|---------|
| `agent_loop_start` | Loop begins | `tools_available`, `max_iterations` |
| `tool_start` | Before each tool execution | `tool_name`, `input`, `step_index` |
| `tool_result` | After each tool execution | `tool_name`, `status`, `duration_ms`, result preview |
| `agent_thinking_token` | LLM reasoning between tools | Think content, reasoning step |
| `agent_checkpoint` | Layer 3+ tool needs confirmation | `tool_name`, `tool_args`, `checkpoint_tier` |
| `token` | Final text response from LLM | Answer text |
| `agent_loop_complete` | Loop finished | `tools_used`, `iterations`, `total_duration_ms` |
| `done` | Stream complete | Full answer, tool call metadata |

## Checkpoint Flow

Tools with `checkpoint_tier != "none"` (file_write, shell_exec, git_exec, etc.) require user confirmation:

1. Agent loop encounters a Layer 3+ tool call
2. Emits `agent_checkpoint` SSE event with tool details
3. Stores loop state in session DB (`_agent_loop: true`, `_loop_state: {...}`)
4. Pauses and returns to the frontend
5. User sends "yes" or "no" on next message
6. On confirm: executes the tool, re-enters the loop with the result in context
7. On deny: tells the LLM "user denied this action", LLM adapts
8. Supports chained checkpoints (multiple confirmations in one task)

## Tool Support

All tools from `tool_registry.py` are supported:

| Tool | Layer | Checkpoint | Status |
|------|-------|-----------|--------|
| `system_info` | 1 | none | Supported |
| `file_read` | 2 | none | Supported |
| `dir_list` | 1 | none | Supported |
| `project_scan` | 1 | none | Supported |
| `web_search` | 2 | none | Supported |
| `fetch_url` | 2 | none | Supported |
| `memory_recall` | 1 | none | Supported |
| `file_write` | 3 | medium | Supported (checkpoint) |
| `shell_exec` | 4 | high | Supported (checkpoint) |
| `git_exec` | 3 | medium | Supported (checkpoint) |
| `web_browse` | 3 | medium | Supported (checkpoint) |
| `desktop_action` | 5 | high | Supported (checkpoint) |
| `create_commitment` | 2 | none | Supported |
| `list_commitments` | 1 | none | Supported |
| `cancel_commitment` | 2 | medium | Supported (checkpoint) |

## Testing

With `agent_loop.enabled = true`, these should work in a single request:

### 1. Multi-step file operation
```
"read D:\AI_round2\docs\ACTION_EXECUTION.md and copy it to D:\AI_round2\test_copy.md"
```
Expected: file_read -> (sees content) -> file_write (checkpoint) -> confirm -> done

### 2. Web search with synthesis
```
"what's the latest news about AI?"
```
Expected: web_search -> (sees results) -> synthesized response

### 3. Project scan with analysis
```
"scan my project and tell me what needs cleanup"
```
Expected: project_scan -> thoughtful analysis

### 4. File creation
```
"create a new file called test.py with a hello world script"
```
Expected: file_write (checkpoint) -> confirm -> done

### 5. Multi-tool compound request
```
"read the roadmap, check git log, and tell me where we stand"
```
Expected: file_read -> git_exec/shell_exec (checkpoint) -> confirm -> synthesized summary

## Fallback Behavior

If the agent loop fails (LLM error, tool error, etc.), the system automatically falls through to the legacy classify -> plan -> execute path. This ensures no regression — the old pipeline still works as a safety net.

The fallback is logged:
```
[STREAM] Agent tool loop failed, falling back to legacy path: <error>
```

## Relationship to Existing Systems

- **desktop_agent.py** — Reference architecture. Same ReAct pattern, different domain (vision+screenshots vs tools+text)
- **task_agent.py** — Legacy path. Still used as fallback when agent loop is disabled or fails
- **orchestrator.py** — Used for multi_intent/multi_step tasks. Agent loop handles these cases directly now
- **plan_engine.py** — Plan generation still works. Agent loop can coexist with plans
- **response_synthesis.py** — Less critical with agent loop since the LLM synthesizes in-loop, but still available as enhancement
- **CRT governance** — Still runs on final responses via the normal pipeline
