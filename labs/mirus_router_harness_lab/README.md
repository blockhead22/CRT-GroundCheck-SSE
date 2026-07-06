# Mirus Router Harness Lab

Purpose: reuse the original CRT tool-routing logic with minimal changes and test
whether the old semantic tool-discovery pattern is useful for Mirus-style
candidate discovery.

What is ripped from the original code:

- `personal_agent.llm_intent_router.LLMIntentRouter`
- `personal_agent.tool_registry.ToolDefinition`
- `personal_agent.tool_registry.ToolParam`
- the original tool-call parsing behavior, including no-tool conversational
  fallback and native multi-tool call handling

What this lab adds:

- a small Mirus-facing tool schema list
- a deterministic `ScriptedToolCallingClient` so tests do not require Ollama
- review-only candidate payloads for memory facts and relations
- JSON result artifacts under `results/`

Safety boundary:

- no production Aether sidecar changes
- no memory writes
- no support/reflection writes
- no raw hidden chain-of-thought storage
- all extracted facts are review-only candidates

Run:

```powershell
python -m pytest tests\test_mirus_router_harness_lab.py -q
python -m labs.mirus_router_harness_lab.original_router_lab --write
```

Next useful experiment:

Replace `ScriptedToolCallingClient` with a small local tool-calling model and
compare:

- current deterministic extraction
- original router plus small-model tool calls
- original router plus repair/retry when candidate payload is malformed

