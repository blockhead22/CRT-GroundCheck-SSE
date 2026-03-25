# Session Prompt: Replace LLM Client Layer with LiteLLM

## Goal
Replace the 3-file custom LLM client layer (~1,751 lines) with LiteLLM.
Preserve all existing behavior: local Ollama, cloud OpenAI-compatible, Anthropic,
thinking model support, role-based routing, rate limiting, and prompt scrubbing.

## IMPORTANT: Pause between every step. After completing each step, say:
## "--- STEP N COMPLETE. Ready for next step? ---" and WAIT for the user to say "go".

## Do NOT skip steps. Do NOT combine steps. Run tests after every step.

---

## Pre-flight: Read before touching anything

Read ALL of these files first. Do not edit anything until you understand the full picture:

```
D:\AI_round2\personal_agent\hybrid_llm_client.py    (668 lines — the main router)
D:\AI_round2\personal_agent\ollama_client.py         (621 lines — local LLM)
D:\AI_round2\personal_agent\anthropic_client.py      (462 lines — Claude API)
D:\AI_round2\personal_agent\cloud_features.py        (832 lines — cookie auth + cloud routing)
D:\AI_round2\personal_agent\rate_limiter.py           (rate limiting for Anthropic)
D:\AI_round2\personal_agent\cloud_usage_logger.py    (359 lines — usage tracking)
D:\AI_round2\personal_agent\cloud_usage_tracker.py   (403 lines — usage DB)
```

Also read the .env file at D:\AI_round2\.env for current API keys/config.

Understand these patterns before proceeding:
- Three-tier routing: local (Ollama) → cloud (OpenAI-compatible) → Anthropic
- Model prefix routing: "local:model", "cloud:model", "anthropic:model", "role:answer"
- Thinking model detection: qwen3, deepseek-r1, qwq get inflated token budgets
- _resolve_visible_text() strips <think> tags from thinking models
- Cookie-based Claude auth via CLAUDE_SESSION_COOKIE (no API key)
- Cloud prompt scrubbing via CloudPromptPolicy
- Quality gate: if Ollama returns empty, fall through to Anthropic (just added 2026-03-24)

---

## STEP 1: Install LiteLLM and verify Ollama connectivity

```bash
cd D:\AI_round2
pip install litellm
```

Write a throwaway test script `tests/test_litellm_smoke.py`:

```python
"""Smoke test: verify LiteLLM can talk to local Ollama and return a response."""
import litellm

# Test 1: Basic Ollama call
response = litellm.completion(
    model="ollama/qwen3:14b",
    messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
    api_base="http://localhost:11434",
    timeout=60
)
print("Ollama response:", response.choices[0].message.content)

# Test 2: Verify tool calling works through LiteLLM→Ollama
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather for a location",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"]
        }
    }
}]
response = litellm.completion(
    model="ollama/qwen3:14b",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
    api_base="http://localhost:11434",
    timeout=120
)
msg = response.choices[0].message
print("Tool calls:", msg.tool_calls if msg.tool_calls else "None")
print("Content:", msg.content or "(empty)")
```

Run it: `python tests/test_litellm_smoke.py`

If Ollama isn't running or the model isn't available, check `ollama list` and adjust the model name.

**Success criteria:** Both calls return non-empty responses. Tool call test returns either a tool_call or text.

--- PAUSE: "STEP 1 COMPLETE. Ready for next step?" ---

---

## STEP 2: Create litellm_client.py — the replacement module

Create `D:\AI_round2\personal_agent\litellm_client.py`

This single file replaces hybrid_llm_client.py + ollama_client.py + anthropic_client.py.

It must expose these exact interfaces (the rest of the codebase calls these):

```python
class UnifiedLLMClient:
    """Drop-in replacement for HybridLLMClient using LiteLLM."""

    def __init__(self, config: dict):
        """
        config keys:
            ollama_model: str           (default from CRT_OLLAMA_MODEL or "qwen3:14b")
            ollama_base_url: str        (default "http://localhost:11434")
            cloud_model: str            (default from CRT_CLOUD_MODEL)
            cloud_api_key: str          (default from OPENAI_API_KEY)
            cloud_base_url: str         (default from CRT_CLOUD_BASE_URL)
            anthropic_model: str        (default from CRT_ANTHROPIC_MODEL or "claude-sonnet-4-6")
            anthropic_api_key: str      (default from ANTHROPIC_API_KEY)
            product_mode: str           (local_only | hybrid_verified | cloud_only)
            model_roles: dict           (role name → model string, e.g. {"answer": "ollama/qwen3:14b"})
            fallback_enabled: bool      (default True — if primary returns empty, try next tier)
            rate_limit_rpm: int         (Anthropic RPM, default 50)
            rate_limit_tpd: int         (Anthropic TPD, default 1_000_000)
        """

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.7, stream: bool = False, model: str = None) -> str:
        """Single-prompt generation. Returns text."""

    def chat(self, messages: list, max_tokens: int = 1024,
             temperature: float = 0.7, model: str = None) -> str:
        """Multi-turn chat. Returns text."""

    def chat_with_tools(self, messages: list, tools: list, max_tokens: int = 4096,
                        temperature: float = 0.3, model: str = None) -> dict:
        """
        Tool-calling chat. Returns:
        {
            "tool_calls": [{"name": str, "arguments": dict}, ...],
            "content": str,
            "used_tools": bool
        }
        """

    def chat_stream(self, messages: list, max_tokens: int = 1024,
                    temperature: float = 0.7, model: str = None):
        """Streaming chat. Yields (token, type) tuples where type is 'text' or 'thinking'."""

    def chat_with_image(self, prompt: str, image_b64: str, image_media_type: str = "image/png",
                        max_tokens: int = 1024, temperature: float = 0.5, model: str = None) -> str:
        """Vision chat. Routes to a vision-capable model."""
```

### Key implementation details:

**Model resolution:** Translate the existing prefix system to LiteLLM model strings:
- "local:qwen3:14b" → "ollama/qwen3:14b" with api_base
- "cloud:gpt-4o-mini" → "gpt-4o-mini" (uses OPENAI_API_KEY)
- "anthropic:claude-sonnet-4-6" → "anthropic/claude-sonnet-4-6"
- "role:answer" → look up model_roles["answer"], then resolve that
- No prefix → use product_mode default tier

**Thinking model support:**
```python
THINKING_MODELS = {"qwen3", "deepseek-r1", "qwq"}

def _is_thinking_model(self, model: str) -> bool:
    base = model.split("/")[-1].split(":")[0].lower()
    return any(t in base for t in self.THINKING_MODELS)

def _resolve_visible_text(self, content: str, thinking: str = "") -> str:
    """Extract visible text, stripping <think>...</think> tags."""
    if not content:
        content = ""
    import re
    visible = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if not visible and thinking:
        # Recover from thinking-only response
        visible = thinking.strip()
    return visible
```

For thinking models, inflate max_tokens:
```python
if self._is_thinking_model(resolved_model):
    effective_max = max(max_tokens * 4, 8192)
```

**Fallback/quality gate logic:**
```python
def chat_with_tools(self, messages, tools, ...):
    tiers = self._get_tier_order()  # based on product_mode
    for model_str, kwargs in tiers:
        try:
            response = litellm.completion(model=model_str, messages=messages,
                                          tools=tools, **kwargs)
            result = self._parse_tool_response(response)
            # Quality gate: if empty, try next tier
            if result["tool_calls"] or result["content"].strip():
                return result
            print(f"[LITELLM] {model_str} returned empty, trying next tier")
        except Exception as e:
            print(f"[LITELLM] {model_str} failed: {e}, trying next tier")
    # All tiers failed
    return {"tool_calls": [], "content": "", "used_tools": False}
```

**Rate limiting:** Use LiteLLM's built-in Router for rate limiting instead of the custom PersonalRateLimiter:
```python
from litellm import Router

router = Router(model_list=[
    {"model_name": "anthropic-default", "litellm_params": {
        "model": "anthropic/claude-sonnet-4-6",
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "rpm": int(os.getenv("CRT_ANTHROPIC_RPM", "50")),
        "tpm": int(os.getenv("CRT_ANTHROPIC_TPD", "1000000")) // 1440  # daily → per-minute
    }},
    {"model_name": "ollama-default", "litellm_params": {
        "model": "ollama/qwen3:14b",
        "api_base": "http://localhost:11434"
    }}
], fallbacks=[{"ollama-default": ["anthropic-default"]}])
```

**Prompt scrubbing:** Keep the existing CloudPromptPolicy._scrub_prompt_for_cloud() method.
Copy it into litellm_client.py as a static method. Apply it before any cloud/anthropic call.

**Cookie-based Claude auth:** LiteLLM does NOT support cookie auth natively.
Keep cloud_features.py's CookieProvider as-is for now — it handles a separate concern
(the CRT reasoning/trust checks, not the main generation path). Do NOT try to replace
the cookie provider in this migration. Just leave cloud_features.py untouched.

### Factory function (replaces create_primary_llm_client):

```python
def create_llm_client(runtime_cfg: dict = None) -> UnifiedLLMClient:
    """Factory matching the old create_primary_llm_client signature."""
    cfg = runtime_cfg or {}
    return UnifiedLLMClient({
        "ollama_model": cfg.get("local_model") or os.getenv("CRT_OLLAMA_MODEL", "qwen3:14b"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "cloud_model": os.getenv("CRT_CLOUD_MODEL", "gpt-4o-mini"),
        "cloud_api_key": os.getenv("OPENAI_API_KEY"),
        "cloud_base_url": os.getenv("CRT_CLOUD_BASE_URL"),
        "anthropic_model": os.getenv("CRT_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "product_mode": os.getenv("CRT_PRODUCT_MODE", "hybrid_verified"),
        "model_roles": {},  # populated from CRT_MODEL_ROLE_* env vars
        "fallback_enabled": True,
        "rate_limit_rpm": int(os.getenv("CRT_ANTHROPIC_RPM", "50")),
        "rate_limit_tpd": int(os.getenv("CRT_ANTHROPIC_TPD", "1000000")),
    })
```

**Write comprehensive tests** in `tests/test_litellm_client.py`:
- Test model resolution (prefix → LiteLLM model string) — unit test, no LLM call
- Test _resolve_visible_text with <think> tags — unit test
- Test _is_thinking_model detection — unit test
- Test tier ordering for each product_mode — unit test
- Test quality gate (mock LiteLLM returning empty, verify fallback) — mock test
- Test generate() with Ollama — integration test (skip if Ollama unavailable)
- Test chat_with_tools() with Ollama — integration test
- Test rate limit config passes through — unit test

Run: `python -m pytest tests/test_litellm_client.py -v`

**Success criteria:** All unit tests pass. Integration tests pass if Ollama is running.

--- PAUSE: "STEP 2 COMPLETE. Ready for next step?" ---

---

## STEP 3: Migrate crt_api.py (the main entry point)

`crt_api.py` is where `create_primary_llm_client()` is called at startup and the client
is stored on `app.state`.

Read crt_api.py and find:
- The import of `create_primary_llm_client` from `hybrid_llm_client`
- Where the client is stored (likely `app.state.llm_client` or similar)
- Any direct references to HybridLLMClient type

Change:
```python
# OLD
from personal_agent.hybrid_llm_client import create_primary_llm_client, HybridLLMClient

# NEW
from personal_agent.litellm_client import create_llm_client, UnifiedLLMClient
```

Update the startup code to use `create_llm_client()`. The rest of crt_api.py should work
because UnifiedLLMClient exposes the same methods (generate, chat, chat_with_tools, chat_stream).

Do NOT change cloud_features.py initialization — it uses its own OpenAICompatibleClient
and CookieProvider. Leave that path untouched.

Run: `python -c "from personal_agent.litellm_client import create_llm_client; print('OK')"`
Then start the server briefly to verify it boots: `python crt_api.py` — confirm no import errors in the first 10 seconds of startup output.

**Success criteria:** Server starts without import errors. The LLM client initializes.

--- PAUSE: "STEP 3 COMPLETE. Ready for next step?" ---

---

## STEP 4: Migrate the 16 files that import OllamaClient directly

These files import OllamaClient or call `get_ollama_client()` directly, bypassing the hybrid layer.
Each one needs to be updated to use UnifiedLLMClient instead.

**Files to migrate (in order — do them one at a time, test after each batch):**

### Batch A: Core agent files (most critical)
```
personal_agent/agent_loop.py          — line 41
personal_agent/agent_reasoning.py     — line 20
personal_agent/response_synthesis.py  — line 278
personal_agent/thinking_loop.py       — line 136
```

For each file:
1. Read the file
2. Find the import: `from personal_agent.ollama_client import OllamaClient` or `get_ollama_client`
3. Find where the client is instantiated or used
4. Replace with: the UnifiedLLMClient instance from the app state / passed as parameter
5. If the file creates its OWN OllamaClient instance, change it to accept a client parameter
   or import create_llm_client

**Pattern:** Most of these files call `get_ollama_client(model)` to get a throwaway client.
Replace with a module-level or passed-in UnifiedLLMClient that routes via model prefix:

```python
# OLD
from personal_agent.ollama_client import get_ollama_client
client = get_ollama_client("qwen3:14b")
result = client.chat(messages)

# NEW
# Option A: Accept client as parameter (preferred)
def my_function(llm_client, ...):
    result = llm_client.chat(messages, model="local:qwen3:14b")

# Option B: Module-level lazy client (if threading through params is too invasive)
from personal_agent.litellm_client import create_llm_client
_client = None
def _get_client():
    global _client
    if _client is None:
        _client = create_llm_client()
    return _client
```

Prefer Option A when the caller already has a client reference.
Use Option B only when the function is called from too many places to thread a parameter.

### Batch B: Route handlers
```
routes/chat.py        — lines 1541, 1705
routes/agent.py       — line 209
```

These likely get the LLM client from the request's app state. Update the import and
ensure they use the new client.

### Batch C: Support modules
```
personal_agent/llm_intent_router.py    — line 470
personal_agent/llm_extractor.py        — line 366
personal_agent/llm_drift_assessor.py   — line 86
personal_agent/heartbeat_system.py     — line 802
personal_agent/continuous_loops.py     — line 446
```

Same pattern as Batch A.

### Batch D: Non-critical (tests, tools)
```
run_eval.py                              — line 79
tests/test_ollama_client_visibility.py  — line 5
tools/crt_stress_test.py                — line 119
tools/crt_adaptive_stress_test.py       — line 36
```

For test files: update imports. For stress test tools: update to use UnifiedLLMClient.
The test_ollama_client_visibility.py tests may need to be rewritten or deleted since
the OllamaClient is being removed.

### Batch E: AnthropicClient direct imports
```
routes/desktop.py                       — line 95
tests/desktop_control/test_vision.py    — line 238
personal_agent/task_agent.py            — line 4436
```

These use AnthropicClient directly (for vision, desktop control). Replace with
UnifiedLLMClient.chat_with_image() or model="anthropic:claude-sonnet-4-6".

After each batch, run: `python -c "from routes.chat import router; print('OK')"`
and `python -m pytest tests/ -x -q --timeout=30` to catch import errors early.

**Success criteria:** No file in the project imports from ollama_client or anthropic_client
(except cloud_features.py which is exempt). Grep to verify:
```bash
grep -rn "from personal_agent.ollama_client" --include="*.py" D:\AI_round2
grep -rn "from personal_agent.anthropic_client" --include="*.py" D:\AI_round2
```
Only cloud_features.py and hybrid_llm_client.py (about to be deleted) should remain.

--- PAUSE: "STEP 4 COMPLETE. Ready for next step?" ---

---

## STEP 5: Integration test — full server boot + chat round-trip

Start the server:
```bash
cd D:\AI_round2
python crt_api.py
```

Verify in the startup output:
- No import errors
- LLM client initializes (should see LiteLLM model list or similar)
- Server reaches "Uvicorn running on http://127.0.0.1:8123"

Then test a basic chat via curl or the test suite:
```bash
curl -X POST http://127.0.0.1:8123/api/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"hello\", \"thread_id\": \"test-litellm\"}"
```

Verify:
1. Response streams back (SSE events)
2. [OLLAMA] debug prints are gone (replaced by [LITELLM] prints)
3. No tracebacks in server output

Then test a task route (the agent loop):
```bash
curl -X POST http://127.0.0.1:8123/api/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"D:/AI_round2/docs/ACTION_EXECUTION.md copy this file to D:/AI_round2/test_copy.md\", \"thread_id\": \"test-litellm-task\"}"
```

Verify:
1. Intent routes to task
2. Agent loop enters (look for [AGENT_LOOP_GATE] prints)
3. Tool calls work (file_read at minimum)
4. If Ollama returns empty on iteration 2, fallback to Anthropic fires

Clean up test file: `del D:\AI_round2\test_copy.md` if created.

**Success criteria:** Basic chat and task execution work end-to-end through LiteLLM.

--- PAUSE: "STEP 5 COMPLETE. Ready for next step?" ---

---

## STEP 6: Delete old files and clean up

Only after Steps 1-5 all pass:

1. Delete the old client files:
```
D:\AI_round2\personal_agent\ollama_client.py
D:\AI_round2\personal_agent\anthropic_client.py
D:\AI_round2\personal_agent\hybrid_llm_client.py
```

2. Delete or update old tests:
```
D:\AI_round2\tests\test_ollama_client_visibility.py  → delete
D:\AI_round2\tests\test_hybrid_generation_stack.py   → rewrite for UnifiedLLMClient
```

3. Delete the smoke test: `D:\AI_round2\tests\test_litellm_smoke.py`

4. Update requirements.txt / pyproject.toml:
   - Add: `litellm>=1.40.0`
   - Remove: `httpx` if no other file uses it (ollama_client was the main consumer)

5. Final grep to confirm no dangling imports:
```bash
grep -rn "ollama_client\|OllamaClient\|get_ollama_client" --include="*.py" D:\AI_round2
grep -rn "anthropic_client\|AnthropicClient" --include="*.py" D:\AI_round2
grep -rn "hybrid_llm_client\|HybridLLMClient\|create_primary_llm_client" --include="*.py" D:\AI_round2
```

Only litellm_client.py references should remain.

6. Run full test suite: `python -m pytest tests/ -v --timeout=60`

**Success criteria:** No references to old files. All tests pass. Server boots clean.

--- PAUSE: "STEP 6 COMPLETE. Ready for next step?" ---

---

## STEP 7: Commit and document

1. Stage all changes:
```bash
git add personal_agent/litellm_client.py tests/test_litellm_client.py
git add -u  # stages deletions and modifications
```

2. Commit:
```
Replace custom LLM client layer with LiteLLM

- Delete hybrid_llm_client.py, ollama_client.py, anthropic_client.py (~1,751 lines)
- Add litellm_client.py with UnifiedLLMClient (~400 lines)
- Preserve: model prefix routing, thinking model support, quality gate fallback,
  rate limiting, prompt scrubbing
- LiteLLM handles provider abstraction, retries, timeouts
- cloud_features.py cookie auth path unchanged
- All tests pass
```

3. Add a note to CHANGELOG or commit message about env var compatibility:
   All CRT_* env vars still work. No config changes needed.

**Success criteria:** Clean commit. `git status` shows nothing untracked.

--- STEP 7 COMPLETE. Migration done. ---

---

## What was NOT migrated (intentionally):

- **cloud_features.py** — Uses CookieProvider for cookie-based Claude auth. LiteLLM doesn't
  support this. Left as-is. This handles CRT reasoning checks, not main generation.
- **cloud_usage_logger.py / cloud_usage_tracker.py** — Usage tracking. LiteLLM has its own
  callbacks for this but migrating the tracking DB schema is a separate task.
- **rate_limiter.py** — If nothing else imports it after the migration, it can be deleted.
  Check with grep first.

## Rollback plan:
All old files are in git history. If something breaks badly:
```bash
git checkout HEAD~1 -- personal_agent/hybrid_llm_client.py personal_agent/ollama_client.py personal_agent/anthropic_client.py
```
