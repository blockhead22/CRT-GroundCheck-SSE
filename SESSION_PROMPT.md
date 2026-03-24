# Session Prompt: Response Synthesis Layer (v2.9.1)

## Context

This is a personal AI agent called Aether. The v2.9 hybrid routing layer was just completed — messages now flow through a three-tier classifier (regex → local LLM → cloud LLM) that correctly identifies intent and routes to the right tool. Tools execute and return results.

**The problem**: After tools execute, responses are flat and mechanical. The system dumps raw tool output back to the user with no interpretation, no synthesis, no awareness of WHY the user asked. It's a conveyor belt — message in, tool fires, raw output out.

**Example of the current behavior**:
- User says: "[file: ACTION_EXECUTION.md] read this file and tell me what it's about"
- System correctly routes to `file_read`, reads the file
- Response: dumps the first 50 lines in a code block with line count and byte size
- What the user actually wanted: "Here's what this file covers — it defines how action execution works in the pipeline. The key sections are X, Y, Z. Based on what you're building, this is relevant because..."

**The core issue in code**: In `personal_agent/task_agent.py` around line 2122, there's a block that handles read-only tool results (`file_read`, `dir_list`, `project_scan`, `system_info`). It explicitly says "never let the LLM summarize (it hallucinates)" and returns deterministic formatted output. This was a reasonable safety measure when the system had no good LLM integration, but now it's the wall preventing intelligent responses.

Similarly, other tool types (commitments, desktop actions, skill installs) all have hardcoded deterministic response templates. The LLM is never given the chance to think about tool results and craft a response that serves the user's actual intent.

## What to Build: Response Synthesis Layer

### Architecture

After tools execute and return results, add a synthesis step where the LLM receives:
1. The user's original message (the "why")
2. The conversation history (context)
3. The tool results (the "what")
4. A system prompt that says: "You have these results. The user asked for X. Respond naturally — interpret, synthesize, expand, connect dots. Don't just dump data."

```
Current flow:
  Route → Execute Tool → Format Output Deterministically → Return

New flow:
  Route → Execute Tool → LLM Synthesis Pass → Return Rich Response
```

### Key Design Decisions

1. **The synthesis LLM call uses the SAME routing mode setting** (local/cloud/hybrid from settings). If user is in local-only mode, synthesis runs on local LLM. If cloud, it uses cloud. This keeps the user in control of costs.

2. **Synthesis is optional per tool type** — some tools genuinely should return deterministic output (e.g., `shell_exec` should show stdout). Add a `synthesis_mode` field to `ToolDefinition` in `tool_registry.py`:
   - `"always"` — always run synthesis (file_read, project_scan, memory_recall)
   - `"on_request"` — synthesize only if the user's message implies they want interpretation ("tell me about", "summarize", "what does this mean")
   - `"never"` — return raw output (shell_exec, git_exec — user wants exact output)
   - `"smart"` — let the synthesis prompt decide based on message context (default)

3. **Synthesis prompt carries the user's intent forward** — this is the critical piece. The synthesis LLM doesn't just see tool output. It sees the original message and understands what the user was trying to accomplish. This is what creates "intent and purpose" in the response.

4. **Guard against hallucination** — the synthesis prompt must instruct the LLM to ONLY reference information from the actual tool results. It should expand and interpret, but never invent data that isn't in the results. Include the raw tool output as a JSON block so the LLM has ground truth.

### Implementation Plan

#### Phase 1: Add synthesis_mode to ToolDefinition

In `personal_agent/tool_registry.py`:
- Add `synthesis_mode: str = "smart"` field to the `ToolDefinition` dataclass
- Set appropriate modes for each registered tool:
  - `file_read` → `"smart"` (synthesize when user says "tell me about" / "summarize", raw when they say "show me the file")
  - `dir_list` → `"on_request"`
  - `project_scan` → `"always"` (project scans always benefit from interpretation)
  - `system_info` → `"smart"`
  - `shell_exec` → `"never"`
  - `git_exec` → `"never"`
  - `memory_recall` → `"always"`
  - `create_commitment` → `"never"` (confirmations should be crisp)
  - `desktop_action` → `"never"`
  - `generate_content` → `"never"` (the generated content IS the response)
  - `fetch_url` → `"smart"`

#### Phase 2: Build the SynthesisEngine

Create `personal_agent/response_synthesis.py`:

```python
class ResponseSynthesizer:
    """Takes tool results + user intent and generates a thoughtful response."""

    def __init__(self, llm_client, mode="hybrid"):
        self.llm_client = llm_client
        self.mode = mode  # "local", "cloud", "hybrid"

    def should_synthesize(self, tool_name, user_message, tool_result) -> bool:
        """Decide whether to run synthesis based on tool's synthesis_mode and user intent."""
        # Check tool's synthesis_mode from registry
        # Check if user message implies wanting interpretation
        # Return True/False

    def synthesize(self, user_message, conversation_history, tool_results, intent) -> str:
        """Run the synthesis LLM pass."""
        # Build synthesis prompt
        # Call LLM (local or cloud based on mode setting)
        # Return the synthesized response
```

The synthesis system prompt should be something like:

```
You are responding to a user who asked: "{user_message}"

Tools were executed and returned these results:
{tool_results_json}

Your job: Respond naturally to what the user actually needs. Don't dump raw data — interpret it, explain what matters, connect it to context, and anticipate follow-up questions.

Rules:
- ONLY reference information present in the tool results. Never invent or hallucinate data.
- If the tool returned an error, explain what went wrong and suggest fixes.
- If the results are simple, keep the response concise. Don't over-explain.
- If the results are complex (large file, project scan), highlight what's important and summarize.
- Match the user's energy — casual question gets casual answer, detailed question gets detailed analysis.
- If relevant, suggest what the user might want to do next.
```

#### Phase 3: Wire into TaskAgent

In `personal_agent/task_agent.py`, replace the deterministic response blocks (the big if/elif chain around line 2052-2160) with:

```python
# After tools execute, before yielding the final response:
synthesizer = get_response_synthesizer()  # Uses current routing mode setting

if synthesizer.should_synthesize(intent.intent_type, message, steps):
    yield {"type": "status", "content": "thinking about results"}
    answer = synthesizer.synthesize(
        user_message=message,
        conversation_history=conversation_history,
        tool_results=[step.to_dict() for step in steps],
        intent=intent,
    )
    yield {"type": "token", "content": answer}
else:
    # Keep deterministic output for tools that don't need synthesis
    answer = self._format_deterministic_response(intent, steps)
    yield {"type": "token", "content": answer}
```

Move the existing deterministic formatting into `_format_deterministic_response()` so it's preserved as a fallback.

#### Phase 4: Settings Integration

The synthesis layer should read the `routing_mode` setting from the user's settings to determine whether to use local or cloud LLM for synthesis. This is already available via the settings infrastructure wired in v2.9.

Add a new setting: `synthesis_enabled` (boolean, default True) — allows user to toggle synthesis off entirely and get raw tool output if they prefer speed over depth.

In `routes/auth.py`, add `"synthesis_enabled"` to the settings whitelist.

In the frontend SettingsPage, add a toggle under the Intent Routing section:
- "Response Synthesis" — toggle on/off
- Description: "When enabled, the system interprets tool results and responds with context. When disabled, raw tool output is returned."

#### Phase 5: Conversational Response Enhancement

This is the other half of the "intent and purpose" problem. Right now when the router classifies a message as `conversational` (no tool needed), it goes through the standard CRT pipeline which generates a response. But that response also lacks depth.

In `routes/chat.py`, the conversational path should benefit from the same philosophy: the LLM should be given a system prompt that encourages expansion, dot-connecting, follow-up suggestions, and natural flow — not just answering the literal question.

This is a lighter touch — modify the system prompt used for conversational responses to include:
- "Expand on interesting points"
- "Connect to what you know about the user from memory"
- "Suggest relevant follow-ups"
- "Match the user's energy and formality"

DON'T make this a separate LLM call — just enhance the existing system prompt for the conversational generation.

#### Phase 6: Multi-tool Synthesis

For messages that trigger multiple tools (future: the LLM router can return multiple tool calls), the synthesis layer should receive ALL results together and weave them into a coherent response.

Example: User says "compare my changelog to the roadmap and tell me where we are"
- Tools: `file_read(CHANGELOG.md)` + `file_read(ROADMAP.md)` + `git_exec(['log', '--oneline', '-15'])`
- Synthesis: Receives all three results, compares them, identifies what's done vs remaining, suggests priorities

This is stretch for today but the architecture should support it from the start. The `synthesize()` method already takes a list of tool results.

## Files to Modify

1. **`personal_agent/tool_registry.py`** — Add `synthesis_mode` field to ToolDefinition
2. **`personal_agent/response_synthesis.py`** — NEW FILE — ResponseSynthesizer class
3. **`personal_agent/task_agent.py`** — Replace deterministic response chain with synthesis pass
4. **`routes/auth.py`** — Add `synthesis_enabled` to settings whitelist
5. **`frontend/src/pages/SettingsPage.tsx`** — Add synthesis toggle to UI
6. **`routes/chat.py`** — Enhance conversational system prompt (light touch)

## Testing

After implementation, these should work naturally:

1. `"[file: ROADMAP.md] read this and tell me what it's about"` → Should return an interpretation of the roadmap, not a code block dump
2. `"what's my system looking like?"` → Should return a natural language summary with context, not raw CPU/RAM numbers
3. `"scan this project"` → Should return insights about the project structure, not just a file tree
4. `"git status"` → Should still return raw git output (synthesis_mode: "never")
5. `"run npm install"` → Should still return raw shell output (synthesis_mode: "never")

## Important Notes

- Keep the deterministic response code as a fallback — don't delete it. Move it to a helper method.
- The synthesis LLM call should be FAST. Use the local model by default, cloud only if routing_mode is "cloud".
- If synthesis fails for any reason, fall back to deterministic output silently.
- The pipeline status should emit "thinking about results" during synthesis so the UI shows the user something is happening.
- Guard the synthesis prompt carefully against hallucination. The LLM must only work with data from the tool results, never invent information.
