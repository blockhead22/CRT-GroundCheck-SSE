# Work Prompt: v2.9 — Hybrid Intent Router + LLM Tool-Calling Loop

## Context

You are working on **Aether/CRT**, a personal AI agent with memory governance, tool execution, and multi-channel delivery. The codebase is at `D:/AI_round2/`.

The current intent classification system (v2.2) uses **regex patterns + embedding similarity** to route user messages to tools. This is breaking on basic requests — e.g. `"[file: ACTION_EXECUTION.md] read this file and tell me what its about"` runs the full cosmetic pipeline (reading context → searching memory → reasoning → drafting) but never actually executes the `file_read` tool. The regex/embedding layer misclassifies or fails to wire extracted parameters into the execution plan, and there's no fallback.

**The core problem:** intent classification is a language understanding task, but we're solving it with regex and cosine similarity instead of letting an LLM do what it's good at.

## Goal

Replace the current two-stage classifier (regex → embedding) with a **three-tier hybrid router** that adds LLM-based tool calling as the authoritative fallback. Add a **self-improving feedback loop** where successful LLM-routed tasks generate new regex patterns over time, making the system faster and cheaper with use.

User-selectable routing modes via the existing Settings panel:
- **Local-only**: regex → local LLM (no cloud calls ever)
- **Cloud-only**: regex → cloud LLM (skip local LLM)
- **Hybrid (default)**: regex → local LLM → cloud LLM escalation if confidence is low

---

## Architecture

```
User message arrives
  │
  ├─ Tier 1: REGEX (instant, free)
  │   Existing pattern matching from intent_router.py
  │   If confidence >= 0.90 → execute immediately
  │   If no match or low confidence → fall through
  │
  ├─ Tier 2: LLM ROUTER (local or cloud, based on setting)
  │   Send message + tool definitions to LLM
  │   LLM returns: which tool(s) to call + parameters
  │   This IS the classification — no separate classify step
  │   The LLM naturally handles novel phrasings, multi-step, ambiguity
  │
  └─ Tier 3: CLOUD ESCALATION (if hybrid mode + local LLM uncertain)
      Same as Tier 2 but uses cloud model for complex/multi-step tasks
      Only fires if local LLM confidence is low or task is multi-turn

After successful task completion:
  → Log (message_text, intent_type, tool_calls, success) to learning DB
  → Pattern extractor runs periodically (heartbeat or on-demand)
  → After N successful similar messages → auto-generate regex pattern
  → New pattern added to Tier 1 → future similar messages skip LLM entirely
```

---

## Key Files to Understand Before Starting

Read these files thoroughly before writing any code:

### Classification & Routing
- `personal_agent/intent_router.py` (320 lines) — Regex patterns, `Intent` enum, `classify()` method
- `personal_agent/semantic_intent_router.py` (605 lines) — Embedding router, `IntentScore`, prototype system, corrections DB
- `personal_agent/task_agent.py` (5400+ lines) — **The big one.** `classify_intent_hybrid()` (line ~1157-1295), `_build_plan()`, `_execute_step()`, `_INTENT_TOOL_MAP`, `AgentStep`, `TaskIntent` dataclass. This is where regex and embedding results merge and where tools get dispatched
- `personal_agent/model_router.py` (337 lines) — `RoutedModel`, model selection logic, cloud escalation policy

### Tool System
- `personal_agent/task_agent.py` — `_execute_step()` (line ~3695-3772) is the tool dispatcher. It's a giant if/elif chain. Also `_TOOL_SCHEMAS` (line ~2501-2750) and `_INTENT_TOOL_MAP` (line ~1374-1387)
- `personal_agent/sub_agents.py` — SubAgent ABC, 8 concrete agents (SystemInfo, File, Shell, Git, WebFetch, Desktop, Generation, Commitment)
- `personal_agent/orchestrator.py` — Multi-intent decomposition and dependency graph execution

### Settings & Config
- `routes/auth.py` (lines 217-266) — `GET/PATCH /api/auth/settings`, whitelisted setting keys. Already has `cloud_slot_classification`, `cloud_escalation_policy`, `generation_mode`, etc.
- `frontend/src/components/SettingsModal.tsx` — Settings UI with tabs (Profile, Cloud, Desktop, etc.)
- `personal_agent/model_router.py` — `CRT_PRODUCT_MODE` env var controls local_only vs hybrid

### Learning System
- `personal_agent/semantic_intent_router.py` — `intent_corrections` table schema, `record_correction()`, `_apply_learned_corrections()`
- `personal_agent/heartbeat_executor.py` — `review_corrections()` auto-promotes corrections to prototypes

### Chat Pipeline
- `routes/chat.py` (5500+ lines) — Full message flow from `/api/chat/send` and `/api/chat/stream`. SSE event emission. This is where `classify_intent()` gets called and where the task agent is invoked

---

## Implementation Plan

### Phase 1: Tool Definition Schema

Create a unified tool definition format that both the LLM router and the existing dispatcher can use. This replaces the implicit knowledge scattered across `_INTENT_TOOL_MAP` and `_execute_step()`.

**New file: `personal_agent/tool_registry.py`**

```python
@dataclass
class ToolDefinition:
    name: str                           # "file_read", "shell_exec", etc.
    description: str                    # Human-readable, used in LLM prompt
    parameters: Dict[str, ToolParam]    # JSON-schema-like param definitions
    access_layer: int                   # 1-6 from the access layer model
    checkpoint_tier: str                # "none", "medium", "high"
    examples: List[str]                 # Example user messages (for regex generation later)

TOOL_REGISTRY: Dict[str, ToolDefinition] = { ... }
```

Populate from existing tools in `_execute_step()`. Every tool that exists today gets a definition. The registry is the single source of truth — `_INTENT_TOOL_MAP` and the if/elif chain in `_execute_step()` should reference it.

Generate an LLM-compatible tool description format (similar to OpenAI function calling schema) from the registry for use in Tier 2/3.

### Phase 2: LLM Router

**New file: `personal_agent/llm_intent_router.py`**

This is the core new component. It takes a user message and tool definitions, sends them to an LLM, and gets back structured tool calls.

```python
class LLMIntentRouter:
    def __init__(self, llm_client, tool_registry: Dict[str, ToolDefinition]):
        ...

    async def classify(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,  # For multi-turn context
        attached_paths: Optional[List[str]] = None,
    ) -> TaskIntent:
        """
        Send message + tool schemas to LLM.
        LLM responds with tool_calls or conversational response.
        Parse into TaskIntent format compatible with existing pipeline.
        """
```

**System prompt for the router LLM:**
- "You are a tool router. Given the user's message, decide which tool(s) to call."
- Include all tool definitions from registry
- Include conversation history if available (this enables multi-turn!)
- Ask for structured JSON output: `{"tool": "file_read", "params": {"path": "..."}, "confidence": 0.95}`
- If no tool matches → return `{"tool": null, "route": "conversational"}`

**Important:** This must work with both local (Ollama) and cloud (OpenAI/Claude) models. Use the existing `model_router.py` infrastructure for model selection. The router LLM call should be lightweight — small max_tokens, low temperature, structured output mode if the model supports it.

### Phase 3: Hybrid Router Integration

**Modify: `personal_agent/task_agent.py`**

Replace `classify_intent_hybrid()` with a new three-tier flow:

```python
def classify_intent_hybrid(message, active_task, settings):
    # Tier 1: Regex (existing, untouched)
    regex_result = regex_classify(message)
    if regex_result.confidence >= 0.90:
        log_classification(message, regex_result, source="regex")
        return regex_result

    # Tier 2: LLM Router
    routing_mode = settings.get("routing_mode", "hybrid")  # local_only | cloud_only | hybrid

    if routing_mode == "cloud_only":
        llm_result = await cloud_llm_router.classify(message, history)
    else:
        llm_result = await local_llm_router.classify(message, history)

    if llm_result.confidence >= 0.70:
        log_classification(message, llm_result, source="llm_local")
        return llm_result

    # Tier 3: Cloud escalation (hybrid mode only)
    if routing_mode == "hybrid":
        cloud_result = await cloud_llm_router.classify(message, history)
        log_classification(message, cloud_result, source="llm_cloud")
        return cloud_result

    # Fallback: conversational
    return TaskIntent(route="conversational", ...)
```

**Key decisions:**
- The existing regex patterns stay untouched as Tier 1. They're fast and free — no reason to remove them
- The semantic embedding router (`semantic_intent_router.py`) can be **deprecated** — the LLM router does everything it does but better. Don't delete it yet, just stop calling it in the hybrid flow. Keep it available as a setting if users want the old behavior
- `_build_plan()` and `_execute_step()` should not need major changes — `TaskIntent` is the interface contract between classification and execution. The LLM router just produces `TaskIntent` objects with better accuracy

### Phase 4: Settings Panel — Routing Mode

**Modify: `routes/auth.py`**
- Add `routing_mode` to whitelisted settings keys (values: `local_only`, `cloud_only`, `hybrid`)
- Add `routing_llm_model` for specifying which model to use for routing (default: whatever's configured as local)

**Modify: `frontend/src/components/SettingsModal.tsx`**
- Add a "Routing" section/tab (or add to existing Cloud tab)
- Three-way toggle: Local Only / Cloud Only / Hybrid
- Show explanation text for each mode:
  - Local Only: "Regex patterns + local LLM. No cloud calls for routing. Free but less accurate on novel requests."
  - Cloud Only: "Regex patterns + cloud LLM. Most accurate, uses API tokens for classification."
  - Hybrid: "Regex → local LLM → cloud escalation. Best balance of speed, cost, and accuracy."
- Optional: model selector for routing LLM (dropdown of available models)

### Phase 5: Self-Improving Feedback Loop

**New file: `personal_agent/route_learning.py`**

```python
class RouteLearningDB:
    """SQLite table tracking successful classifications for pattern generation."""

    # Schema:
    # route_log (
    #   id INTEGER PRIMARY KEY,
    #   message_text TEXT,
    #   message_normalized TEXT,  -- lowercase, stripped
    #   intent_type TEXT,
    #   tool_calls TEXT,  -- JSON array of tools used
    #   source TEXT,  -- "regex" | "llm_local" | "llm_cloud"
    #   success BOOLEAN,  -- did the task complete without error?
    #   timestamp REAL
    # )

    def log_classification(self, message, intent, source, success): ...

    def get_pattern_candidates(self, min_occurrences=5) -> List[PatternCandidate]:
        """
        Find intent types where LLM-routed messages cluster into patterns.
        Group by normalized message similarity, return clusters with 5+ successes.
        """

    def generate_regex_pattern(self, candidate: PatternCandidate) -> Optional[str]:
        """
        Given a cluster of similar successful messages, generate a regex pattern.
        Use the LLM to generalize: "Given these 5 messages that all mapped to file_read,
        write a regex pattern that would match similar messages."
        """
```

**Integration with heartbeat:**
- Add `review_route_patterns()` to `heartbeat_executor.py`
- Runs periodically (every ~30 min or configurable)
- Calls `get_pattern_candidates()` → `generate_regex_pattern()`
- New patterns get added to `intent_router.py`'s pattern list at runtime
- Patterns are also persisted to a `learned_patterns` SQLite table so they survive restarts
- Each learned pattern includes its origin (which messages generated it) for auditability

**The virtuous cycle:**
1. Day 1: Most messages go through LLM router (Tier 2/3)
2. Week 1: Common patterns auto-generate regex rules
3. Week 2+: 80%+ of messages hit Tier 1 regex, LLM only fires for genuinely novel requests
4. System gets faster and cheaper over time with zero manual work

### Phase 6: Wire Up Execution

Make sure the LLM router's output actually connects to tool execution properly. This is where the file_read bug lives.

**Key fix in `_build_plan()`:**
- Currently `_build_plan()` takes a `TaskIntent` and builds `AgentStep` objects
- The LLM router should return tool calls with explicit parameters (file path, command, etc.)
- `_build_plan()` should pass these parameters through to `AgentStep.input` without lossy transformation
- Test specifically: `"[file: ACTION_EXECUTION.md] read this file"` → `file_read` tool with `path=ACTION_EXECUTION.md` → actual file content returned

**Verify the full pipeline works for each tool type:**
- system_info: "how's my system"
- file_read: "[file: X] read this" and "read the file X"
- file_write: "create a file called X with Y"
- dir_list: "what's in this folder"
- project_scan: "what's the git status"
- shell_exec: "run npm install"
- git_action: "commit these changes"
- url_fetch: "fetch https://example.com"
- commitments: "remind me at 5pm to do X"
- desktop_action: "open notepad"

---

## What NOT to Change

- **CRT memory system** — don't touch memory, trust, contradictions, belief synthesis, volatility. That's stable and working
- **Sub-agent system** (`sub_agents.py`, `orchestrator.py`) — keep the orchestrator. The LLM router classifies; the orchestrator still handles multi-intent decomposition and parallel execution
- **Checkpoint gating** — the access layer model (Layers 1-6) and confirmation gates stay. The LLM router feeds into the same `gate_task_intent()` flow
- **SSE event format** — keep all existing event types. The frontend expects them. Add new events if needed but don't change existing ones
- **Telegram integration** — `channels/base.py` consumes SSE events. As long as the event contract is preserved, Telegram works
- **Heartbeat system** — add to it (pattern review), don't restructure it
- **Frontend chat components** — only touch `SettingsModal.tsx` for the routing mode toggle. The chat UI, message rendering, action cards, etc. stay as-is

---

## Testing Checklist

After implementation, verify these scenarios work end-to-end:

1. **Basic file read**: `"[file: ROADMAP.md] read this file and summarize it"` → actually reads the file and returns content
2. **Novel phrasing**: `"what does my system look like right now"` → routes to system_info even though it's not a regex pattern
3. **Multi-intent**: `"check my system and list the files in /data"` → orchestrator runs both
4. **Regex fast path**: `"git status"` → hits regex at 0.90+, never touches LLM
5. **Settings respect**: Switch to local_only → verify no cloud calls happen for routing
6. **Learning loop**: Send 5+ similar messages via LLM route → verify pattern candidate appears in DB after heartbeat
7. **Conversational fallback**: `"what do you think about the weather"` → routes to conversational, not a tool
8. **Checkpoint preservation**: `"delete all files in /tmp"` → still triggers high-tier checkpoint gate regardless of which tier classified it

---

## Order of Operations

1. **Phase 1** (Tool Registry) — foundation, everything else depends on it
2. **Phase 2** (LLM Router) — the core new capability
3. **Phase 6** (Wire Up Execution) — immediately test that tools actually fire
4. **Phase 3** (Hybrid Integration) — plug the new router into the existing pipeline
5. **Phase 4** (Settings) — user control
6. **Phase 5** (Learning Loop) — the long-term payoff

Phases 1-3 + 6 are today's core work. Phases 4-5 can be done in the same session or a follow-up.

---

## Environment Notes

- Python backend with FastAPI, SQLite databases
- Frontend: React + TypeScript + Vite
- Local LLM: Ollama (default model: qwen3:14b, configurable via `CRT_OLLAMA_MODEL`)
- Cloud LLMs: OpenAI (gpt-5.4-thinking) and Claude (Anthropic), configurable
- Settings stored per-user in auth DB, fetched via `GET /api/auth/settings`
- All tool execution goes through `CRTTaskAgent.run_stream()` which emits SSE events
- The `_execute_step()` if/elif chain is the final dispatcher — tools run here

---

## ROADMAP Entry (add when complete)

```markdown
### v2.9 (March 2X)
- [ ] Hybrid LLM intent router — three-tier classification: regex (instant) → local LLM → cloud LLM escalation
- [ ] Tool definition registry — unified schema for all 17 tools, single source of truth for names, params, descriptions
- [ ] LLM-as-router — tool definitions sent to LLM, model picks tools + fills parameters naturally
- [ ] Routing mode setting — Settings panel toggle: Local Only / Cloud Only / Hybrid
- [ ] Self-improving pattern learning — successful LLM-routed tasks auto-generate regex patterns via heartbeat
- [ ] Route learning DB — SQLite tracking of classifications, success rates, pattern candidates
- [ ] Deprecated semantic embedding router — LLM router subsumes its role, embedding router available as legacy option
- [ ] Fix: file_read and other tools actually execute when classified (parameter wiring fix in _build_plan)
```
