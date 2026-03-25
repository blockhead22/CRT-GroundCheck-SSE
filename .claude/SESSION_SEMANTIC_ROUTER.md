# Session Prompt: Semantic Router Swap

## Goal
Replace the 3-tier hybrid intent classifier (regex + LLM routing + embedding fallback) with
the `semantic-router` package. The output format (`TaskIntent`) stays the same. The consumption
code in `routes/chat.py` doesn't change. Only the classification internals change.

## Rules
- **Pause after each step** and show the user what changed before continuing
- **Run tests after every code change**
- **Do NOT modify routes/chat.py** beyond updating the import path for `classify_intent`
- **Do NOT modify task_agent.py execution logic** — only the classification functions
- **Do NOT delete old files until Step 6** — keep them for reference
- **Preserve the TaskIntent dataclass exactly** — it's the API contract consumed everywhere
- **Preserve regex fast-paths** — they're fast, accurate, and don't need replacing

---

## Architecture Overview

### Current System (3 tiers + cache)
```
User Message
  -> Route Learning Cache (SQLite, 24h window, normalized match)
  -> Tier 1: Regex patterns (30+ compiled regexes, ~0.90+ confidence)
  -> Tier 2: LLM Router (Ollama qwen3:14b with tool-calling, ~0.70+ threshold)
  -> Tier 3: Cloud escalation (if hybrid mode, ~0.60+ threshold)
  -> Fallback: Embedding classifier (all-MiniLM-L6-v2, cosine similarity)
  -> Final: conversational
```

### New System (regex + semantic-router)
```
User Message
  -> Tier 1: Regex fast-paths (KEEP — file paths, URLs, git, shell patterns)
  -> Tier 2: Semantic Router (REPLACE all LLM + embedding routing)
  -> Final: conversational fallback
```

### What Gets Deleted
- `personal_agent/llm_intent_router.py` (507 lines) — LLM-based Tier 2/3
- `personal_agent/semantic_intent_router.py` (605 lines) — embedding fallback
- `personal_agent/route_learning.py` (384 lines) — cache + pattern learning
- `data/route_learning.db` — route learning cache DB
- `data/intent_corrections.db` — correction feedback DB
- Total: ~1,496 lines deleted

### What Gets Created
- `personal_agent/semantic_router_classifier.py` (~200-300 lines) — new classifier using semantic-router
- `personal_agent/route_definitions.py` (~150 lines) — route configs as data, not code

### What Stays Unchanged
- `TaskIntent` dataclass in `task_agent.py:505-513`
- Regex fast-paths in `task_agent.py:777-1247` (the `classify_intent()` function)
- All consumption code in `routes/chat.py` that reads `_task_intent`
- `routes/intents.py` API endpoints (may need minor import updates)
- All execution logic in `task_agent.py` (_run_task_intent, _describe_action, etc.)

---

## STEP 1: Install and validate semantic-router (15 min)

### Install
```bash
# Install into project venv
.venv/Scripts/pip install semantic-router
```

### Smoke test
Create `tests/test_semantic_router_smoke.py`:
```python
"""Smoke test: semantic-router can classify CRT intent types."""
from semantic_router import Route, RouteLayer
from semantic_router.encoders import HuggingFaceEncoder

def test_basic_routing():
    """Verify semantic-router works with our intent types."""
    encoder = HuggingFaceEncoder(name="all-MiniLM-L6-v2")

    file_read = Route(
        name="file_read",
        utterances=[
            "read the file at /home/user/test.txt",
            "show me the contents of README.md",
            "what's in config.json",
            "cat the log file",
            "open and read data.csv",
        ]
    )

    memory_recall = Route(
        name="memory_recall",
        utterances=[
            "what do you know about me",
            "what's my name",
            "do you remember my favorite color",
            "what have I told you before",
            "recall what I said yesterday",
        ]
    )

    conversational = Route(
        name="conversational",
        utterances=[
            "hello how are you",
            "tell me a joke",
            "what do you think about the weather",
            "thanks for your help",
            "that's interesting",
        ]
    )

    rl = RouteLayer(encoder=encoder, routes=[file_read, memory_recall, conversational])

    result = rl("show me what's in package.json")
    assert result.name == "file_read", f"Expected file_read, got {result.name}"

    result = rl("what's my favorite food")
    assert result.name == "memory_recall", f"Expected memory_recall, got {result.name}"

    result = rl("hey there, good morning")
    assert result.name == "conversational", f"Expected conversational, got {result.name}"

def test_none_route():
    """Messages that don't match any route should return None."""
    encoder = HuggingFaceEncoder(name="all-MiniLM-L6-v2")

    specific = Route(
        name="git_action",
        utterances=[
            "commit the changes",
            "push to main branch",
            "create a new git branch",
        ]
    )

    rl = RouteLayer(encoder=encoder, routes=[specific])

    # This should NOT match git_action
    result = rl("what's the meaning of life")
    # result.name may be None for no match
    print(f"Unmatched result: name={result.name}")
```

Run: `python -m pytest tests/test_semantic_router_smoke.py -xvs`

Verify the encoder loads (should reuse the already-cached all-MiniLM-L6-v2) and classifications work.

**--- PAUSE. Show results. ---**

---

## STEP 2: Create route definitions (30 min)

### File: `personal_agent/route_definitions.py`

This file defines all routes as data. The utterances come from the existing prototype phrases
in `semantic_intent_router.py` lines 25-224. There are 24 intent types with 7-30 seed phrases each.

Create routes for ALL of these intent types:

| Route Name | Source in semantic_intent_router.py |
|---|---|
| `file_read` | lines ~25-40 |
| `file_write` | lines ~41-55 |
| `dir_list` | lines ~56-65 |
| `project_scan` | lines ~66-78 |
| `shell_exec` | lines ~79-93 |
| `git_action` | lines ~94-108 |
| `system_info` | lines ~109-120 |
| `url_fetch` | lines ~121-133 |
| `web_browse` | lines ~134-145 |
| `web_search` | lines ~146-158 |
| `desktop_action` | lines ~159-170 |
| `skill_install` | lines ~171-178 |
| `service_action` | lines ~179-188 |
| `imperative_task` | lines ~189-198 |
| `create_commitment` | lines ~199-210 |
| `list_commitments` | lines ~211-218 |
| `cancel_commitment` | lines ~219-224 |
| `memory_recall` | ADD NEW — "what do you know about me", "recall", "remember" etc. |
| `conversational` | General chat, greetings, thanks, opinions |

Structure:
```python
"""Route definitions for semantic-router based intent classification.

Each route is a dict with 'name' and 'utterances'. These get converted to
semantic_router.Route objects at init time. Edit this file to add/modify
routes — no code changes needed.
"""
from typing import List, Dict

ROUTE_DEFINITIONS: List[Dict] = [
    {
        "name": "file_read",
        "utterances": [
            "read the file at this path",
            "show me the contents of README.md",
            "what's in config.json",
            # ... 10-15 utterances per route, pulled from semantic_intent_router.py
        ]
    },
    # ... all routes
]

# Routes that map to route="task" in TaskIntent
TASK_ROUTES = {
    "file_read", "file_write", "dir_list", "project_scan",
    "shell_exec", "git_action", "system_info", "url_fetch",
    "web_browse", "web_search", "desktop_action", "skill_install",
    "service_action", "imperative_task", "create_commitment",
    "list_commitments", "cancel_commitment", "memory_recall",
    "multi_step", "task_continuation",
}

# Routes that map to route="conversational"
CONVERSATIONAL_ROUTES = {"conversational"}

# Default confidence when semantic-router matches
DEFAULT_CONFIDENCE = 0.85

# When no route matches, fall back to conversational
FALLBACK_ROUTE = "conversational"
FALLBACK_CONFIDENCE = 0.50
```

**--- PAUSE. Show route definitions for review. ---**

---

## STEP 3: Create the new classifier (1-2 hours)

### File: `personal_agent/semantic_router_classifier.py`

This replaces `llm_intent_router.py`, `semantic_intent_router.py`, and `route_learning.py`
with a single file.

```python
"""Intent classifier using semantic-router.

Replaces:
- llm_intent_router.py (LLM-based Tier 2/3 routing)
- semantic_intent_router.py (embedding fallback)
- route_learning.py (cache + pattern learning)

The semantic-router package handles all of this with one encoder + route layer.
"""
import os
from typing import Optional, List
from semantic_router import Route, RouteLayer
from semantic_router.encoders import HuggingFaceEncoder

from .route_definitions import (
    ROUTE_DEFINITIONS, TASK_ROUTES, CONVERSATIONAL_ROUTES,
    DEFAULT_CONFIDENCE, FALLBACK_ROUTE, FALLBACK_CONFIDENCE,
)

# Lazy singleton
_router_instance: Optional["SemanticRouterClassifier"] = None


def get_router() -> "SemanticRouterClassifier":
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouterClassifier()
    return _router_instance


class SemanticRouterClassifier:
    """Classify user messages into intent types using semantic similarity."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        print(f"[SEMANTIC_ROUTER] Initializing with {model_name}...")
        self.encoder = HuggingFaceEncoder(name=model_name)

        routes = []
        for rd in ROUTE_DEFINITIONS:
            routes.append(Route(
                name=rd["name"],
                utterances=rd["utterances"],
            ))

        self.route_layer = RouteLayer(encoder=self.encoder, routes=routes)
        print(f"[SEMANTIC_ROUTER] Loaded {len(routes)} routes")

    def classify(self, message: str) -> tuple:
        """Classify a message. Returns (route_name, confidence).

        route_name is one of the defined route names or FALLBACK_ROUTE.
        confidence is a float 0.0-1.0.
        """
        result = self.route_layer(message)

        if result.name is None:
            return (FALLBACK_ROUTE, FALLBACK_CONFIDENCE)

        # semantic-router returns a similarity score
        # Map it to our confidence range
        confidence = DEFAULT_CONFIDENCE
        if hasattr(result, 'similarity_score') and result.similarity_score is not None:
            confidence = min(result.similarity_score, 0.99)

        return (result.name, confidence)
```

### Key design decisions:
1. **Reuse the same embedding model** (all-MiniLM-L6-v2) — already cached on disk
2. **No LLM calls for routing** — pure embedding similarity, ~5ms per classify vs ~2-5s for Ollama
3. **No route learning DB** — semantic-router handles similarity matching natively
4. **No corrections DB** — can be added later via semantic-router's built-in dynamic routes

### Wire into classify_intent_hybrid

Modify `personal_agent/task_agent.py` function `classify_intent_hybrid()` (around line 1291).

**Current flow (lines 1291-1380):**
```
1. Check route_learning cache
2. Run regex classify_intent()
3. If regex returns conversational → try LLM router
4. If LLM returns low confidence → try cloud escalation
5. If all fail → try embedding classifier
6. Final fallback → conversational
```

**New flow:**
```
1. Run regex classify_intent() — KEEP, fast and high-confidence
2. If regex returns conversational → try semantic router
3. Map result to TaskIntent
4. Final fallback → conversational
```

The new `classify_intent_hybrid()`:
```python
def classify_intent_hybrid(
    message: str,
    active_task=None,
    attached_paths: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
) -> TaskIntent:
    """Classify intent using regex fast-path + semantic router."""

    # Tier 1: Regex fast-paths (unchanged)
    regex_result = classify_intent(message, active_task=active_task)

    # If regex matched something specific (not just conversational fallback), use it
    if regex_result.intent_type != "conversational" and regex_result.confidence >= 0.85:
        return regex_result

    # Tier 2: Semantic Router
    try:
        from .semantic_router_classifier import get_router
        router = get_router()
        route_name, confidence = router.classify(message)

        # Determine route category
        if route_name in TASK_ROUTES:
            route = "task"
        elif route_name in CONVERSATIONAL_ROUTES:
            route = "conversational"
        else:
            route = "conversational"

        # Build slots from message (basic extraction)
        slots = {"raw_message": message}
        if attached_paths:
            slots["attached_paths"] = attached_paths

        result = TaskIntent(
            route=route,
            intent_type=route_name,
            slots=slots,
            confidence=confidence,
            reason=f"semantic_router_match",
            source="semantic_router",
        )

        # Debug logging
        print(f"[SEMANTIC_ROUTER] {route_name} (conf={confidence:.2f}) for: {message[:80]}")

        return result

    except Exception as e:
        print(f"[SEMANTIC_ROUTER] Classification failed: {e}")

    # Final fallback
    return TaskIntent(
        route="conversational",
        intent_type="conversational",
        slots={"raw_message": message},
        confidence=0.50,
        reason="all_classifiers_failed",
        source="fallback",
    )
```

### Slot extraction
The old LLM router extracted slots (file paths, URLs, commands) from the message using
the LLM's tool-calling output. Semantic Router doesn't do this — it only classifies.

For slot extraction, add a simple helper that uses regex patterns (already available in
task_agent.py as compiled regexes) to pull out paths, URLs, and commands AFTER classification.
This is a lightweight function, not an LLM call:

```python
def _extract_slots(message: str, intent_type: str, attached_paths: List[str] = None) -> dict:
    """Extract action parameters from message based on intent type."""
    slots = {"raw_message": message}
    if attached_paths:
        slots["attached_paths"] = attached_paths

    # File paths (drive letters, unix paths, [file: X] tags)
    path_match = re.search(r'[A-Z]:[/\\][\w./\\-]+|/[\w./\\-]+|\[file:\s*([^\]]+)\]', message)
    if path_match and intent_type in ("file_read", "file_write", "dir_list"):
        slots["path"] = path_match.group(1) or path_match.group(0)

    # URLs
    url_match = re.search(r'https?://\S+', message)
    if url_match and intent_type in ("url_fetch", "web_browse"):
        slots["url"] = url_match.group(0)

    # Search queries (strip "search for", "google", etc.)
    if intent_type == "web_search":
        query = re.sub(r'^(search\s+(?:for|the\s+web\s+for)?|google)\s+', '', message, flags=re.I)
        slots["query"] = query.strip()

    # Memory queries
    if intent_type == "memory_recall":
        slots["query"] = message

    return slots
```

### Test
```bash
python -m pytest tests/test_semantic_router_smoke.py tests/ -x -q --timeout=60 2>&1 | tail -30
```

**--- PAUSE. Show the classifier and test results. ---**

---

## STEP 4: Write comprehensive tests (30 min)

### File: `tests/test_semantic_router_classifier.py`

Test the following scenarios:

1. **Route accuracy** — each intent type classifies correctly with representative messages:
   - "read the file config.json" → file_read
   - "create a new file called test.py" → file_write
   - "list the directory contents" → dir_list
   - "git commit -m 'fix'" → git_action
   - "run npm install" → shell_exec
   - "what's my CPU usage" → system_info
   - "go to google.com" → web_browse / url_fetch
   - "search the web for python tutorials" → web_search
   - "remind me to call dentist tomorrow" → create_commitment
   - "what do you know about me" → memory_recall
   - "hello, how are you today" → conversational
   - "open chrome and go to youtube" → desktop_action

2. **Slot extraction** — verify path, URL, query extraction works:
   - "read D:/projects/test.txt" → slots["path"] = "D:/projects/test.txt"
   - "fetch https://example.com" → slots["url"] = "https://example.com"
   - "search for react tutorials" → slots["query"] = "react tutorials"

3. **Regex priority** — verify regex fast-paths still fire for high-confidence patterns:
   - "[file: /home/user/test.txt] read this" → file_read via regex (not semantic router)
   - "D:/AI_round2/README.md copy this" → file_read via regex

4. **Edge cases**:
   - Empty string → conversational fallback
   - Very long message (500+ chars) → doesn't crash
   - Non-English text → returns something (doesn't crash)

5. **Performance** — classification takes < 50ms per message (no LLM calls)

### Run
```bash
python -m pytest tests/test_semantic_router_classifier.py -xvs --timeout=60
```

**--- PAUSE. Show test results. ---**

---

## STEP 5: Integration test (30 min)

### Wire into the actual server

1. Update the import in `classify_intent_hybrid` to use the new classifier
2. Start the server: `python crt_api.py`
3. Verify startup shows `[SEMANTIC_ROUTER] Loaded N routes` instead of LLM router init

### Test these messages through the actual UI or curl:

```bash
# Should route to memory_recall → agent loop → actual memories
curl -X POST http://localhost:8123/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What do you know about me?", "thread_id": "test_thread"}'

# Should route to file_read
curl -X POST http://localhost:8123/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Read D:/AI_round2/README.md", "thread_id": "test_thread"}'

# Should route to conversational
curl -X POST http://localhost:8123/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?", "thread_id": "test_thread"}'
```

### What to check in server logs:
- `[SEMANTIC_ROUTER] memory_recall (conf=0.XX)` — router is being used
- `[INTENT_DEBUG]` line should show `source='semantic_router'` not `source='llm_local'`
- No `[OLLAMA]` calls for routing (only for the agent loop tool calls)
- Response times should be faster (no 2-5s LLM routing call)

### If routing is wrong:
- Check which route was selected and what the confidence was
- Add more utterances to the misclassified route in `route_definitions.py`
- Re-test — no code changes needed, just data changes

**--- PAUSE. Show integration test results. ---**

---

## STEP 6: Delete old files + clean up (15 min)

### Delete these files:
- `personal_agent/llm_intent_router.py` (507 lines)
- `personal_agent/semantic_intent_router.py` (605 lines)
- `personal_agent/route_learning.py` (384 lines)

### Update imports:
- `routes/intents.py` — update any imports that reference deleted modules
- `personal_agent/task_agent.py` — remove imports of LLMIntentRouter, SemanticIntentRouter,
  RouteLearningDB
- Any test files that import from deleted modules — update or delete

### Do NOT delete:
- `data/route_learning.db` — keep for reference, mark deprecated
- `data/intent_corrections.db` — keep for reference
- `tests/test_semantic_intent_router.py` — delete (tests old embedding classifier)

### Update requirements.txt:
```
semantic-router>=0.1.0
```

### Verify:
```bash
# No import errors
python -c "from personal_agent.task_agent import classify_intent; print('OK')"

# All tests pass
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -20

# Server starts clean
python crt_api.py
```

**--- PAUSE. Show cleanup results. ---**

---

## STEP 7: Commit (5 min)

```bash
git add personal_agent/semantic_router_classifier.py personal_agent/route_definitions.py
git add tests/test_semantic_router_classifier.py tests/test_semantic_router_smoke.py
git add personal_agent/task_agent.py routes/intents.py
git add -u  # stage deletions
git commit -m "Replace 3-tier intent classifier with semantic-router

Deleted:
- llm_intent_router.py (507 lines) — LLM-based routing via Ollama/cloud
- semantic_intent_router.py (605 lines) — embedding fallback classifier
- route_learning.py (384 lines) — cache + pattern learning

Created:
- semantic_router_classifier.py (~250 lines) — semantic-router wrapper
- route_definitions.py (~150 lines) — all routes as config data

Benefits:
- No LLM calls for routing (~5ms vs ~2-5s per classification)
- Routes are data, not code — edit utterances to change behavior
- ~1,500 lines deleted, ~400 added
- Same accuracy, dramatically faster

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**--- DONE ---**

## Performance Expectations

| Metric | Before (LLM routing) | After (semantic-router) |
|---|---|---|
| Classification time | 2-5s (Ollama) | ~5-10ms |
| Lines of code | ~1,496 | ~400 |
| External dependencies | Ollama running, embedding model | embedding model only |
| Accuracy | Good (LLM understands nuance) | Good (24 routes x 10-15 utterances) |
| Adding new routes | Code changes in 3 files | Add utterances to route_definitions.py |

## Known Trade-offs
- **Slot extraction is simpler.** The LLM router extracted rich slots via tool-calling schema.
  The new regex-based slot extraction is less sophisticated. If this becomes a problem,
  slot extraction can be done as a second pass after classification (ask the LLM to extract
  params only, not classify — much cheaper and only when needed).
- **No learning/adaptation.** The route learning cache gradually promoted common routes to
  regex patterns. Semantic Router doesn't learn from corrections automatically. This can be
  added later via semantic-router's dynamic route API.
- **No multi-step detection.** The LLM router could detect multi-step plans. The new system
  classifies individual intents. Multi-step detection in `routes/chat.py` (compound intent
  upgrade) still works as before.
