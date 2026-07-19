# Session Prompt: Browser Agent (v3.0)

## Context

This is a personal AI agent called Aether (CRT-GroundCheck-SSE). Recent work:
- **v2.9** — Hybrid LLM intent router (regex → local LLM → cloud LLM)
- **v2.9.1** — Response synthesis layer (LLM thinks about tool results before responding)
- **v2.9.2** — Task plan system (persistent plans with steps, thread linking, UI)

The system already has a **desktop control agent** that works via a ReAct loop: screenshot → vision analysis → execute action → verify. The architecture is clean and modular:
- `personal_agent/desktop_control.py` — low-level primitives (pyautogui + mss screenshots)
- `personal_agent/desktop_vision.py` — `VisionProvider` abstract interface + `ClaudeVisionProvider` / `CookieVisionProvider` implementations
- `personal_agent/desktop_agent.py` — `DesktopAgent` class with the ReAct loop, safety gates, rate limiting, blocked apps, confirmation keywords, restricted regions

**What's missing**: The agent can control the desktop but can't browse the web autonomously. It can't navigate to a URL, fill out a form, click links, extract page content, or research something online. This is the single biggest capability gap.

## What to Build: BrowserAgent (Playwright-based)

A new browser automation tool that follows the EXACT same architectural pattern as the desktop agent — modular, standalone, safety-gated — but uses Playwright instead of pyautogui.

### Why Playwright over Selenium/pyautogui-on-browser:
- Modern async API, works on Windows natively
- Can run headed (user watches) or headless (background)
- Built-in screenshot, element selection, form filling
- Network interception (useful for detecting page loads, errors)
- Persistent browser contexts (cookies/sessions survive across tasks)
- No need for vision model for basic tasks — Playwright can read the DOM directly

### Key Design Decision: Hybrid DOM + Vision

The browser agent should have TWO modes of understanding a page:

1. **DOM mode (fast, free, precise)** — Playwright reads the page structure, extracts text, finds elements by selector/text/role. This handles 80% of tasks: navigate, click a link, fill a form, read page content.

2. **Vision mode (when DOM isn't enough)** — Screenshot the page and send to vision model (reusing the existing `VisionProvider` interface). This handles: complex layouts, canvas/WebGL content, visual verification ("does this page look right?"), CAPTCHAs (detection only — don't solve them, ask user).

The agent should prefer DOM mode and only escalate to vision when DOM parsing can't resolve the task.

---

## Architecture

### File Structure (mirrors desktop agent pattern)

```
personal_agent/
  browser_control.py    — Low-level Playwright wrapper (like desktop_control.py)
  browser_agent.py      — ReAct loop for browser tasks (like desktop_agent.py)
```

### Phase 1: Browser Control Layer

Create `personal_agent/browser_control.py`:

```python
class BrowserController:
    """Low-level browser automation primitives via Playwright."""

    def __init__(self, headless=False, persistent_context_dir=None):
        # Lazy-import playwright (don't crash if not installed)
        # Create or connect to a persistent browser context
        # persistent_context_dir stores cookies/sessions between runs

    # ── Lifecycle ──
    async def launch(self) -> None
    async def close(self) -> None
    async def new_page(self) -> Page
    async def get_active_page(self) -> Page

    # ── Navigation ──
    async def navigate(self, url: str, wait_until="domcontentloaded") -> dict
        # Returns: {url, title, status_code, load_time_ms}
    async def go_back(self) -> None
    async def go_forward(self) -> None
    async def reload(self) -> None

    # ── Page Reading (DOM mode) ──
    async def get_page_text(self) -> str
        # Extract visible text content from the page
    async def get_page_title(self) -> str
    async def get_page_url(self) -> str
    async def get_links(self, limit=50) -> List[dict]
        # Returns: [{text, href, visible}]
    async def get_form_fields(self) -> List[dict]
        # Returns: [{name, type, label, value, placeholder, selector}]
    async def get_interactive_elements(self) -> List[dict]
        # Returns: [{tag, text, role, selector, type}]
        # Buttons, links, inputs, selects — anything clickable/fillable
    async def extract_structured_content(self, selector=None) -> dict
        # Extract tables, lists, headings — structured page content

    # ── Actions ──
    async def click(self, selector: str, timeout=5000) -> bool
    async def click_text(self, text: str) -> bool
        # Click element containing this text
    async def fill(self, selector: str, value: str) -> bool
    async def select(self, selector: str, value: str) -> bool
    async def press_key(self, key: str) -> None
    async def scroll(self, direction="down", amount=500) -> None

    # ── Screenshots ──
    async def screenshot(self, full_page=False) -> str
        # Returns base64 JPEG (same format as desktop_control)
    async def screenshot_element(self, selector: str) -> str

    # ── Waiting ──
    async def wait_for_selector(self, selector: str, timeout=10000) -> bool
    async def wait_for_navigation(self, timeout=10000) -> bool
    async def wait_for_load(self) -> None

    # ── State ──
    async def get_cookies(self) -> List[dict]
    async def get_page_state(self) -> dict
        # Returns: {url, title, has_forms, interactive_count, scroll_position}
```

Important implementation details:
- Use `playwright.async_api` (async throughout)
- Persistent context via `browser_type.launch_persistent_context(user_data_dir)` — saves cookies/login sessions to `data/browser_profile/`
- Default to Chromium, but make engine configurable
- Catch and handle common Playwright errors gracefully (timeout, element detached, navigation interrupted)
- All methods return clean data structures, never raw Playwright objects

### Phase 2: Browser Agent (ReAct Loop)

Create `personal_agent/browser_agent.py`:

```python
class BrowserAction:
    """Structured action the agent wants to perform."""
    action_type: str  # navigate, click, fill, read, scroll, screenshot, extract, done, failed, need_info
    selector: Optional[str]
    url: Optional[str]
    text: Optional[str]
    value: Optional[str]
    reasoning: str
    confidence: float

class BrowserTaskResult:
    """Result of a browser task execution."""
    success: bool
    steps_taken: int
    total_duration_ms: float
    extracted_content: Optional[str]  # text/data extracted from the page
    final_url: str
    final_title: str
    action_log: List[dict]
    error: Optional[str]
    screenshot_b64: Optional[str]  # final state screenshot

class BrowserAgent:
    """
    ReAct loop for browser tasks: observe page → think → act → verify.

    Uses DOM reading as primary understanding (fast, free).
    Falls back to vision model for complex visual analysis.
    """

    def __init__(self, controller: BrowserController, vision: Optional[VisionProvider] = None,
                 llm_client=None, max_steps=20, step_timeout=15.0):
        self.controller = controller
        self.vision = vision  # Optional — only for visual analysis
        self.llm_client = llm_client  # For deciding next action
        self.max_steps = max_steps

    async def execute_task(self, task: str, memory_context: str = "",
                           on_step=None) -> BrowserTaskResult:
        """
        Execute a browser task via ReAct.

        The loop:
        1. Observe: read page state (DOM + optional screenshot)
        2. Think: ask LLM "given this page state and task, what should I do next?"
        3. Act: execute the chosen action via BrowserController
        4. Verify: check if action succeeded, decide if task is complete
        """
```

**The LLM prompt for step selection** (this is where intelligence lives):

```
You are a browser automation agent. Your task: "{task}"

Current page state:
- URL: {url}
- Title: {title}
- Visible text (first 2000 chars): {page_text}
- Interactive elements: {elements_json}
- Form fields: {form_fields_json}
- Action history: {action_history}

Based on the current page state, decide what to do next.
Return a JSON object:
{
  "action": "navigate|click|fill|scroll|read|extract|done|failed|need_info",
  "selector": "CSS selector or null",
  "url": "URL for navigate, or null",
  "text": "text to click or null",
  "value": "value for fill or null",
  "reasoning": "why you chose this action",
  "extracted_content": "if action is 'read' or 'extract', what you extracted from the page"
}

Rules:
- Prefer clicking by text content over CSS selectors when possible
- If you can't find what you need, try scrolling down
- If the page has a search box and you need to find something, use it
- If a form needs filling, fill fields one at a time
- When done, set action to "done" and include any extracted_content
- If stuck after 3 attempts, set action to "failed"
- NEVER fill in passwords, credit card numbers, SSNs, or other sensitive data
```

### Phase 3: Safety Gates

Mirror the desktop agent's safety system but adapted for web:

```python
# Domains that should NEVER be navigated to automatically
BLOCKED_DOMAINS = [
    "bank", "banking", "chase.com", "wellsfargo.com", "paypal.com",
    "venmo.com", "zelle",
    # Login/auth pages for critical services
    "accounts.google.com/signin",  # Don't auto-login
    "login.microsoftonline.com",
]

# Form fields that should NEVER be auto-filled
BLOCKED_FIELDS = [
    "password", "passwd", "pass",
    "credit_card", "card_number", "cc_number", "cvv", "cvc",
    "ssn", "social_security",
    "bank_account", "routing_number",
    "secret", "token",  # API keys/secrets
]

# Actions that require user confirmation
CONFIRM_ACTIONS = [
    "submit",  # Any form submission
    "purchase", "buy", "checkout", "pay",
    "delete", "remove",
    "send", "post", "publish",
    "sign up", "register", "create account",
]

# URL patterns that require confirmation before navigating
CONFIRM_URLS = [
    r".*checkout.*",
    r".*payment.*",
    r".*delete.*",
    r".*admin.*",
]
```

Rate limiting:
- Max 30 actions per minute (browser is faster than desktop)
- Max 10 navigations per minute
- Max 5 form submissions per minute

### Phase 4: Register as Tool + Wire into TaskAgent

**In `personal_agent/tool_registry.py`**, add two new tools:

```python
# ---- web_browse ----
_register(ToolDefinition(
    name="web_browse",
    description="Browse a website — navigate, read content, click links, fill forms, extract information",
    parameters=[
        ToolParam("task", "string", "What to do on the web (natural language)", required=True),
        ToolParam("url", "string", "Starting URL to navigate to", required=False),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    synthesis_mode="always",  # Browser results always benefit from synthesis
    intent_type="web_browse",
    examples=[
        "go to hacker news and tell me the top 5 stories",
        "search google for playwright python tutorial",
        "check the weather on weather.com",
        "go to this url and summarize the page",
        "fill out the contact form on example.com",
        "look up the latest python release notes",
        "find the pricing on that website",
    ],
))

# ---- web_search ----
_register(ToolDefinition(
    name="web_search",
    description="Search the web for information using a search engine",
    parameters=[
        ToolParam("query", "string", "The search query", required=True),
    ],
    access_layer=2,
    checkpoint_tier="none",
    synthesis_mode="always",
    intent_type="web_search",
    examples=[
        "search for how to use playwright",
        "look up the population of Tokyo",
        "find recent news about AI",
        "google fastapi websocket tutorial",
        "search for best python testing frameworks 2026",
    ],
))
```

**In `personal_agent/task_agent.py`**, add:

1. A `_build_plan` case for `web_browse` and `web_search` intents
2. An `_execute_step` handler for `web_browse` (similar to `_run_desktop_action`)
3. A simpler `_execute_step` handler for `web_search` (navigate to search engine → extract results)

The `_run_browser_action` method in task_agent.py should:
- Check if browser control is enabled in settings
- Initialize BrowserController + BrowserAgent
- Run the task
- Log action receipts
- Return results for synthesis

### Phase 5: Frontend Settings

Add a new **"Browser Control"** section to the Settings page (similar to the existing Desktop Control section).

Settings to add:

1. **Browser control enabled** — toggle (default: off)
   - Master switch for all browser automation

2. **Browser mode** — radio group
   - `"headed"` — Browser window visible (user can watch, default)
   - `"headless"` — Browser runs in background (faster, no UI)

3. **Browser engine** — dropdown
   - `"chromium"` (default)
   - `"firefox"`
   - `"webkit"`

4. **Persist sessions** — toggle (default: on)
   - When on, cookies and login sessions are saved between browser tasks
   - When off, each task starts with a clean browser context

5. **Require confirmation for** — radio group
   - `"all_actions"` — Confirm every browser action (safest, slowest)
   - `"submissions_only"` — Only confirm form submissions and purchases (default)
   - `"never"` — No confirmations (fastest, least safe)

6. **Max steps per task** — number input (default: 20, min: 5, max: 50)

7. **Domain allowlist** — text area (one domain per line)
   - If populated, browser can ONLY visit these domains
   - If empty, browser can visit any non-blocked domain

8. **Domain blocklist** — text area (one domain per line, pre-filled with banking domains)
   - Browser will never navigate to these domains

Add to `routes/auth.py` settings whitelist:
```python
"browser_enabled",
"browser_mode",          # "headed" | "headless"
"browser_engine",        # "chromium" | "firefox" | "webkit"
"browser_persist_sessions",
"browser_confirm_mode",  # "all_actions" | "submissions_only" | "never"
"browser_max_steps",
"browser_domain_allowlist",
"browser_domain_blocklist",
```

### Phase 6: SSE Events for Browser Actions

The browser agent should emit SSE events so the frontend can show real-time progress:

```python
# New event types:
{"type": "browser_start", "content": "Opening browser..."}
{"type": "browser_navigate", "content": "Navigating to https://...", "metadata": {"url": "..."}}
{"type": "browser_action", "content": "Clicking 'Sign In' button", "metadata": {"action": "click", "target": "Sign In"}}
{"type": "browser_screenshot", "content": "base64...", "metadata": {"step": 3}}
{"type": "browser_extract", "content": "Extracted 5 search results", "metadata": {"count": 5}}
{"type": "browser_done", "content": "Task complete", "metadata": {"steps": 7, "duration_ms": 4500}}
{"type": "browser_error", "content": "Navigation timeout", "metadata": {"error": "timeout"}}
{"type": "browser_confirm", "content": "About to submit a form. Proceed?", "metadata": {"action": "submit", "url": "..."}}
```

The frontend doesn't need a new page — these events render inline in the chat stream like the existing tool_start/tool_result events. But consider adding a small browser status indicator (URL + title) when a browser task is running.

---

## Files Summary

### New Files
1. `personal_agent/browser_control.py` — Playwright wrapper (navigation, DOM reading, actions, screenshots)
2. `personal_agent/browser_agent.py` — BrowserAgent ReAct loop (observe → think → act → verify)

### Modified Files
1. `personal_agent/tool_registry.py` — Register `web_browse` and `web_search` tools
2. `personal_agent/task_agent.py` — Add `_build_plan` cases + `_run_browser_action` handler
3. `routes/auth.py` — Add browser settings to whitelist
4. `frontend/src/pages/SettingsPage.tsx` — Add "Browser Control" settings section
5. `routes/register.py` — No changes needed (browser uses existing tool pipeline)

### Dependencies
Add to requirements.txt or install:
```
playwright>=1.40.0
```
Then run: `playwright install chromium`

---

## Testing Scenarios

1. **Basic navigation**: "go to https://news.ycombinator.com and tell me the top 5 stories"
   - Should: navigate, extract headlines, synthesize a nice response
2. **Web search**: "search for playwright python getting started"
   - Should: navigate to search engine, extract results, present them
3. **Form interaction**: "go to example.com/contact and fill out the name field with 'Nick'"
   - Should: navigate, find form, fill field (but NOT submit without confirmation)
4. **Page reading**: "go to this URL and summarize what the page is about"
   - Should: navigate, extract text, run through synthesis layer for a rich summary
5. **Safety gate**: "go to chase.com and check my balance"
   - Should: REFUSE — banking domain is blocked
6. **Confirmation gate**: "submit the contact form"
   - Should: ask for confirmation before clicking submit
7. **Multi-step**: "search for the best pizza place near me, go to the top result, and find their menu"
   - Should: search → click result → navigate → find menu → extract → synthesize
8. **Settings respect**: Disable browser in settings → any web_browse request returns "Browser control is disabled"

## Important Notes

- Playwright is async — the browser agent needs to run in an async context. Use `asyncio.to_thread()` or `asyncio.run()` to bridge with the sync TaskAgent, same pattern used for desktop agent.
- The persistent browser context (`data/browser_profile/`) should be gitignored — it contains cookies and session data.
- Start simple: Phase 1-2 first, get basic navigate + read + click working. Safety and settings can be tightened later.
- The DOM reading approach means most tasks don't need the vision model at all. Vision is only for "does this page look right?" type verification or complex visual layouts.
- Don't try to solve CAPTCHAs. If one appears, return `need_info` and ask the user.
- The web_search tool is a convenience wrapper — it just navigates to a search engine and extracts results. It doesn't use any external search API.
