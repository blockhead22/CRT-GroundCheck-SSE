---
name: session_2026_03_31_prompt_boundary
description: Prompt cache boundary shipped — static CRT epistemology prefix with 5 axioms, dynamic evidence below boundary, Anthropic cache_control support, unified across all prompt paths
type: project
---

## Session: 2026-03-31 (night, continued)

### Prompt Cache Boundary — SHIPPED

Static epistemology above the line, dynamic evidence below. The model can't be prompted into abandoning belief/speech separation because the axioms are in the immutable prefix.

**New file: `personal_agent/prompt_prefix.py`**
- `STATIC_PREFIX` — 2355 chars of immutable CRT epistemology:
  1. Belief/speech separation (structural, not optional)
  2. Earned trust (0.0-1.0 scores, model cannot override)
  3. Contradiction tolerance (acknowledge both sides, never silently pick)
  4. Compaction awareness (compressed beliefs marked, treat with uncertainty)
  5. Provenance matters (principal > model_output > tool_receipt when stale)
- `BOUNDARY_MARKER` — `--- DYNAMIC EVIDENCE BELOW ---`
- `build_system_prompt(dynamic_parts=[], structured=False)`:
  - `structured=False` → flat string with boundary marker (CLI, OpenAI, Ollama)
  - `structured=True` → list of content blocks with `cache_control: {"type": "ephemeral"}` on static prefix (Anthropic Messages API)

### API Provider Changes
- `AnthropicBrain.complete()` — auto-detects boundary marker in string prompts, splits into cached/uncached content blocks. Logs cache hit/miss via `[ANTHROPIC_CACHE]`.
- `ClaudeCliBrain.complete()` — flattens structured blocks to string for `--system-prompt` CLI flag. Benefits from consistent epistemology even without cache_control.

### Prompt Path Unification
- **Cloud primary** (`routes/chat.py ~3458`) — replaced 20-line hardcoded preamble with `build_system_prompt(dynamic_parts=[time, memories, self_model, context_feed])`
- **Bypass** (`routes/chat.py ~3241`) — replaced single-line identity with `build_system_prompt(dynamic_parts=[context_feed])`
- **Agent tool loop** (`agent_tool_loop.py ~44`) — replaced `_AGENT_SYSTEM_PROMPT` with `_get_agent_system_prompt()` using shared prefix + tool rules

### What This Means
All three prompt paths now share the same 5 epistemic axioms. Previously:
- Cloud primary had a 20-line CRT explanation
- Bypass had "You are Aether. Respond naturally."
- Agent loop had its own identity + tool rules

Now all start with identical epistemology. The axioms are immutable. The evidence is fluid.

### Test Results
- Prefix consistency: same 2355 chars across calls
- Flat string: boundary splits correctly, both halves present
- Structured blocks: 2 blocks, cache_control on first only
- Empty dynamic: prefix only, no boundary marker
- Agent prompt: 3444 chars, uses shared prefix + tool rules
