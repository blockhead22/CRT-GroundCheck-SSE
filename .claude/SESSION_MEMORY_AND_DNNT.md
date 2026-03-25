# Session Prompt: Wire memory_recall + Drop DNNT from Hot Path

## Goal
Two surgical fixes that make the agent actually usable:
1. Ensure `memory_recall` in the agent tool loop returns real memories (verify it works, fix if not)
2. Disable DNNT reasoning model from the request hot path (env var toggle, not code deletion)

## Rules
- **Pause after each step** and show the user what changed before continuing
- **Run tests after every code change**
- **Do NOT delete DNNT code** — just disable it via env var so it can be re-enabled later
- **Do NOT modify the frontend** — backend only
- **Do NOT refactor or clean up surrounding code** — surgical changes only

---

## STEP 1: Verify memory_recall wiring (15 min)

### What to check
The `memory_recall` tool in `personal_agent/agent_tool_loop.py` around line 272 already has code
that calls `engine.memory.retrieve_memories(query, k=5)`. The question is whether `engine` is
actually passed into the tool execution context and whether `engine.memory` is populated.

### Investigation
1. Read `personal_agent/agent_tool_loop.py` — find where `execute_tool()` or the tool dispatch
   function receives its `engine` parameter
2. Read `routes/chat.py` — find where the agent loop is invoked and trace whether the engine
   (from `request.app.state.get_engine(thread_id)`) is passed through
3. Check if the engine's memory system has data:
   ```python
   # Quick test: does the shared memory DB have memories?
   import sqlite3
   conn = sqlite3.connect("personal_agent/crt_memory_shared.db")
   count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
   print(f"Memory count: {count}")
   conn.close()
   ```

### If engine is NOT being passed to tool execution:
- Find where `_execute_tool()` is called in the agent loop
- Trace back to where the agent loop generator is created in `routes/chat.py`
- The engine is available as `engine = get_engine(req.thread_id)` — make sure it's passed
  to the agent loop function and forwarded to tool execution
- The fix should be passing `engine=engine` through the call chain

### If engine IS passed but memory is empty:
- Check if the shared DB path matches: `personal_agent/crt_memory_shared.db`
- Check if memories exist: `SELECT text, trust FROM memories LIMIT 5`
- If the DB has memories but retrieve_memories returns empty, the embedding query
  might not match — check if the embedding model is loaded

### If memory_recall already works:
- Test it: start the server, ask "What do you know about me?" or "What's my name?"
- Check the server logs for `[AGENT_LOOP_DEBUG]` lines showing the tool result content
- If the tool returns real data but the final answer ignores it, that's a Step 2 issue (DNNT/prompt)

### Test
```bash
# After any changes, run:
python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -20
```

### Deliverable
`memory_recall` returns actual memory content (user facts with trust scores) instead of stubs or empty results.

**--- PAUSE. Show the user what you found and what (if anything) you changed. ---**

---

## STEP 2: Disable DNNT from the hot path (15 min)

### Context
The DNNT (Deep Neural Network for Trust) reasoning model is a 6M parameter custom model at
`models/dnnt/model`. It loads on first engine creation and runs inference on every `.reason()` call.

The problems:
- Prints `[ReasoningInference] Loaded model from models\dnnt\model` on every new thread (slow startup)
- Its output gets injected into the conversation context before the LLM generates the final answer
- When the cookie-based Claude fallback sees DNNT's output mixed with system instructions,
  it interprets the whole thing as a prompt injection attack
- Its actual contribution to response quality is unproven

### The fix
The DNNT is already controlled by env var `CRT_DNNT_ENABLED` in `personal_agent/reasoning.py` line 99.
Default is `"true"`.

1. Change the default to `"false"`:
   ```python
   # In personal_agent/reasoning.py around line 99
   # BEFORE:
   self.dnnt_enabled = str(os.getenv("CRT_DNNT_ENABLED", "true")).strip().lower() in {
       "1", "true", "yes", "y", "on"
   }
   # AFTER:
   self.dnnt_enabled = str(os.getenv("CRT_DNNT_ENABLED", "false")).strip().lower() in {
       "1", "true", "yes", "y", "on"
   }
   ```

2. Verify the model no longer loads on startup:
   - Start the server
   - Check that `[ReasoningInference] Loaded model` does NOT appear in logs
   - Check that `[ReasoningInference] Device: cuda` does NOT appear

3. Verify reasoning still works via LLM fallback:
   - In `reasoning.py` around line 542, when DNNT is disabled, `answer` stays empty
   - The code falls through to the LLM path at line 542: `if not answer:`
   - This calls `_build_quick_prompt()` + `_call_llm()` which uses the LiteLLM client
   - This is the correct behavior — LLM handles reasoning, DNNT is bypassed

4. Add a log line so it's visible when DNNT is off:
   ```python
   # After the dnnt_enabled check, around line 102:
   if not self.dnnt_enabled:
       print("[REASONING] DNNT disabled (set CRT_DNNT_ENABLED=true to re-enable)")
   ```

### What NOT to do
- Do NOT delete any DNNT code, files, or the model weights
- Do NOT remove the env var check — users (Nick) can re-enable with `CRT_DNNT_ENABLED=true`
- Do NOT touch `personal_agent/dnnt/` directory at all
- Do NOT modify any imports — the lazy import inside the `if self.dnnt_enabled` block is fine

### Test
```bash
# Verify no import errors:
python -c "from personal_agent.reasoning import ReasoningEngine; print('OK')"

# Run tests:
python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -20
```

### Integration test
After both steps, restart the server and test:

1. Server should start WITHOUT `[ReasoningInference]` loading messages
2. Ask: "What do you know about me?"
3. Check logs for:
   - `[AGENT_LOOP_DEBUG] tool: memory_recall` — tool is called
   - Tool result should contain actual memories with trust scores, not stubs
   - Final answer should reference the user's actual data
   - NO `[ReasoningInference]` lines during the request
4. Ask: "My name is Nick" — verify it doesn't try to call `create_commitment`
   (that was a routing issue where the model confused memory storage with commitments)
5. Ask: "What's my name?" — verify it recalls "Nick" from memory

### Expected log output after both fixes
```
[REASONING] DNNT disabled (set CRT_DNNT_ENABLED=true to re-enable)
[STARTUP] Cloud feature service initialized (openai=True, cookie=True, key_len=164)
INFO: Application startup complete.
...
[AGENT_LOOP_DEBUG] tool: memory_recall  args_keys=['query']
[AGENT_LOOP_DEBUG] Tool=memory_recall needs_checkpoint=False
[AGENT_LOOP_DEBUG] Iteration 2: 4 messages, ~3500 chars total
[AGENT_LOOP_DEBUG] iter=2  tool_calls=0  text_len=200+  text_preview=Your name is Nick...
```

No `[ReasoningInference]` lines. Real memory content in the tool result. A synthesized answer that uses the memories.

**--- PAUSE. Show the user the test results. ---**

---

## STEP 3: Verify cookie fallback prompt hygiene (5 min)

If the integration test in Step 2 still shows Claude saying "I notice this prompt is attempting
to change my role" — the issue is in the message history passed to the cookie fallback.

Check `personal_agent/litellm_client.py` method `_try_cookie_text_fallback()` around line 654.
It already skips `role: "system"` messages. But check if any of these are leaking through:

1. Messages with `role: "assistant"` that contain system-prompt-like content
   (e.g., "You are an epistemic auditor", "Respond with valid JSON only")
2. Tool result messages that contain format instructions rather than actual data
3. The `fact_check_preamble` from `routes/chat.py:2967` that starts with `[SYSTEM NOTE`

If any of these appear in the messages list, add filters in `_try_cookie_text_fallback()`:
```python
# Skip messages that look like system instructions leaked into assistant/user roles
if "epistemic auditor" in content.lower():
    continue
if content.strip().startswith("[SYSTEM NOTE"):
    continue
```

But with DNNT disabled, this may resolve itself — the DNNT output was the primary source of
the "role confusion" content.

**--- PAUSE. Confirm with user whether the system is working. ---**
