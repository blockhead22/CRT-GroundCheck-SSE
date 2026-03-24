"""
Browser ReAct agent — the core observe → think → act → verify loop.

Standalone and testable without the full CRT pipeline.
Uses DOM reading as primary understanding (fast, free, precise).
Falls back to vision model for complex visual analysis.

Mirrors the architecture of desktop_agent.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Action types ─────────────────────────────────────────────────────────

class BrowserActionType(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    CLICK_TEXT = "click_text"
    FILL = "fill"
    SELECT = "select"
    SCROLL = "scroll"
    PRESS_KEY = "press_key"
    READ = "read"          # extract page content
    EXTRACT = "extract"    # extract structured content
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    GO_BACK = "go_back"
    DONE = "done"
    FAILED = "failed"
    NEED_INFO = "need_info"


@dataclass
class BrowserAction:
    """Structured action the agent wants to perform."""
    action_type: BrowserActionType
    selector: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    value: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0
    extracted_content: Optional[str] = None  # data extracted from page


@dataclass
class BrowserTaskResult:
    """Result of a browser task execution."""
    success: bool
    steps_taken: int
    total_duration_ms: float
    extracted_content: Optional[str] = None
    final_url: str = ""
    final_title: str = ""
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    screenshot_b64: Optional[str] = None
    task_summary: str = ""


# ── Safety lists ─────────────────────────────────────────────────────────

# Domains that should NEVER be navigated to automatically
BLOCKED_DOMAINS = [
    "chase.com", "wellsfargo.com", "bankofamerica.com", "citi.com",
    "usbank.com", "capitalone.com", "ally.com", "schwab.com",
    "fidelity.com", "vanguard.com", "tdameritrade.com",
    "paypal.com", "venmo.com",
    "accounts.google.com/signin",
    "login.microsoftonline.com",
    "login.live.com",
]

# Domain keywords that trigger blocking
BLOCKED_DOMAIN_KEYWORDS = [
    "bank", "banking",
]

# Form fields that should NEVER be auto-filled
BLOCKED_FIELDS = [
    "password", "passwd", "pass", "pwd",
    "credit_card", "card_number", "cc_number", "cc-number",
    "cvv", "cvc", "ccv",
    "ssn", "social_security", "social-security",
    "bank_account", "routing_number", "account_number",
    "secret", "token", "api_key", "apikey",
]

# Actions that require user confirmation
CONFIRM_ACTIONS = [
    "submit", "purchase", "buy", "checkout", "pay",
    "delete", "remove",
    "send", "post", "publish",
    "sign up", "register", "create account",
]

# URL patterns that require confirmation before navigating
CONFIRM_URL_PATTERNS = [
    r".*checkout.*",
    r".*payment.*",
    r".*delete.*",
    r".*admin.*",
]


# ── Rate limiting ────────────────────────────────────────────────────────

MAX_ACTIONS_PER_MINUTE = 30
MAX_NAVIGATIONS_PER_MINUTE = 10
MAX_SUBMISSIONS_PER_MINUTE = 5


class _RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

    def allow(self) -> bool:
        now = time.time()
        cutoff = now - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_per_minute:
            return False
        self._timestamps.append(now)
        return True


# ── LLM prompt for action selection ──────────────────────────────────────

_ACTION_SELECTION_SYSTEM = """You are a browser automation agent. You observe web page state and decide the next action to take.

You MUST respond with a single JSON object. No markdown, no extra text. Just valid JSON.

SAFETY RULES:
- NEVER fill in passwords, credit card numbers, SSNs, or other sensitive data
- NEVER submit forms without being explicitly told to
- NEVER interact with banking or payment pages
- If you encounter a CAPTCHA, use action "need_info" to ask the user"""

_ACTION_SELECTION_TEMPLATE = """TASK: {task}

Current page state:
- URL: {url}
- Title: {title}
- Visible text (first 2000 chars):
{page_text}

Interactive elements:
{elements_json}

Form fields:
{form_fields_json}

Previous actions taken:
{action_history}

{memory_context}

Based on the current page state, decide what to do next.
Return a JSON object:
{{
  "action": "navigate|click|click_text|fill|select|scroll|press_key|read|extract|go_back|wait|done|failed|need_info",
  "selector": "CSS selector or null",
  "url": "URL for navigate, or null",
  "text": "text to click (for click_text) or null",
  "value": "value for fill/select, or null",
  "reasoning": "why you chose this action",
  "confidence": 0.0,
  "extracted_content": "if action is 'read'/'extract'/'done', relevant content extracted from the page text above"
}}

Rules:
- Prefer clicking by text content (click_text) over CSS selectors when possible
- If you can't find what you need, try scrolling down
- If the page has a search box and you need to find something, use it
- If a form needs filling, fill fields one at a time
- When done, set action to "done" and include extracted_content with any data you found
- If stuck after 3 attempts on the same thing, set action to "failed"
- ONLY output valid JSON. No markdown wrapping."""


class BrowserAgent:
    """
    ReAct loop for browser tasks: observe page → think → act → verify.

    Uses DOM reading as primary understanding (fast, free).
    Falls back to vision model for complex visual analysis.
    """

    def __init__(
        self,
        controller,  # BrowserController
        vision=None,  # Optional[VisionProvider] — only for visual fallback
        llm_client=None,  # For deciding next action
        max_steps: int = 20,
        step_timeout: float = 15.0,
        confirm_mode: str = "submissions_only",
        domain_allowlist: Optional[List[str]] = None,
        domain_blocklist: Optional[List[str]] = None,
    ) -> None:
        self.controller = controller
        self.vision = vision
        self.llm_client = llm_client
        self.max_steps = max_steps
        self.step_timeout = step_timeout
        self.confirm_mode = confirm_mode
        self.domain_allowlist = domain_allowlist or []
        self.domain_blocklist = domain_blocklist or []
        self._running = False

        # Rate limiters
        self._action_limiter = _RateLimiter(MAX_ACTIONS_PER_MINUTE)
        self._nav_limiter = _RateLimiter(MAX_NAVIGATIONS_PER_MINUTE)
        self._submit_limiter = _RateLimiter(MAX_SUBMISSIONS_PER_MINUTE)

    async def execute_task(
        self,
        task: str,
        start_url: Optional[str] = None,
        memory_context: str = "",
        on_step: Optional[Callable] = None,
    ) -> BrowserTaskResult:
        """
        Execute a browser task via the ReAct loop.

        Args:
            task: natural language task description
            start_url: optional starting URL to navigate to first
            memory_context: verified facts from CRT memory
            on_step: callback(step_num, action_dict) for logging/UI
        """
        self._running = True
        action_log: List[Dict[str, Any]] = []
        start_time = time.time()
        consecutive_failures = 0

        logger.info("[BROWSER_AGENT] Starting task: %s", task)

        # Navigate to start URL if provided
        if start_url:
            if self._is_blocked_domain(start_url):
                return BrowserTaskResult(
                    success=False,
                    steps_taken=0,
                    total_duration_ms=0,
                    error=f"Blocked: cannot navigate to '{start_url}' (security restriction)",
                    action_log=action_log,
                )

            nav_result = await self.controller.navigate(start_url)
            action_log.append({
                "step": 0,
                "action_type": "navigate",
                "url": start_url,
                "reasoning": "Navigate to starting URL",
                "result": nav_result,
                "ts": time.time(),
            })

        for step in range(self.max_steps):
            if not self._running:
                return BrowserTaskResult(
                    success=False,
                    steps_taken=step,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    action_log=action_log,
                    error="Cancelled by user",
                )

            try:
                # 1. Rate limit check
                if not self._action_limiter.allow():
                    logger.warning("[BROWSER_AGENT] Rate limit hit — too many actions/min")
                    return BrowserTaskResult(
                        success=False,
                        steps_taken=step,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error="Rate limit: too many actions per minute",
                    )

                # 2. Observe — read page state via DOM
                page_state = await self.controller.get_page_state()
                page_text = await self.controller.get_page_text(max_length=2000)
                elements = await self.controller.get_interactive_elements(limit=30)
                form_fields = await self.controller.get_form_fields()

                # 3. Think — ask LLM for next action
                action = await self._decide_next_action(
                    task=task,
                    page_state=page_state,
                    page_text=page_text,
                    elements=elements,
                    form_fields=form_fields,
                    action_history=action_log[-5:],
                    memory_context=memory_context,
                )

                if action is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        return BrowserTaskResult(
                            success=False,
                            steps_taken=step + 1,
                            total_duration_ms=(time.time() - start_time) * 1000,
                            action_log=action_log,
                            error="LLM failed to produce valid actions after 3 attempts",
                        )
                    continue

                consecutive_failures = 0

                # 4. Terminal states
                if action.action_type == BrowserActionType.DONE:
                    logger.info("[BROWSER_AGENT] Task complete after %d steps", step + 1)
                    screenshot = await self.controller.screenshot()
                    return BrowserTaskResult(
                        success=True,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        extracted_content=action.extracted_content,
                        final_url=page_state.get("url", ""),
                        final_title=page_state.get("title", ""),
                        action_log=action_log,
                        screenshot_b64=screenshot,
                        task_summary=action.reasoning,
                    )

                if action.action_type == BrowserActionType.FAILED:
                    logger.warning("[BROWSER_AGENT] Task failed: %s", action.reasoning)
                    return BrowserTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=action.reasoning,
                        final_url=page_state.get("url", ""),
                    )

                if action.action_type == BrowserActionType.NEED_INFO:
                    logger.info("[BROWSER_AGENT] Needs clarification: %s", action.reasoning)
                    return BrowserTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=f"Need clarification: {action.reasoning}",
                    )

                # 5. Safety checks
                if action.action_type == BrowserActionType.NAVIGATE:
                    if self._is_blocked_domain(action.url or ""):
                        action_log.append({
                            "step": step + 1,
                            "action_type": "blocked",
                            "reasoning": f"Domain blocked: {action.url}",
                            "ts": time.time(),
                        })
                        return BrowserTaskResult(
                            success=False,
                            steps_taken=step + 1,
                            total_duration_ms=(time.time() - start_time) * 1000,
                            action_log=action_log,
                            error=f"Blocked: cannot navigate to '{action.url}' (security restriction)",
                        )
                    if not self._nav_limiter.allow():
                        action_log.append({
                            "step": step + 1, "action_type": "rate_limited",
                            "reasoning": "Too many navigations per minute", "ts": time.time(),
                        })
                        await asyncio.sleep(2.0)
                        continue

                if action.action_type == BrowserActionType.FILL:
                    if self._is_blocked_field(action.selector or "", form_fields):
                        action_log.append({
                            "step": step + 1,
                            "action_type": "blocked",
                            "reasoning": f"Blocked field: {action.selector}",
                            "ts": time.time(),
                        })
                        continue

                # Confirmation gate
                if self._needs_confirmation(action, page_state):
                    action_log.append({
                        "step": step + 1,
                        "action_type": "needs_confirmation",
                        "reasoning": f"Action requires confirmation: {action.reasoning}",
                        "ts": time.time(),
                    })
                    # For now, skip actions that need confirmation in auto mode
                    # The task_agent layer handles actual user confirmation
                    return BrowserTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=f"Confirmation required: {action.reasoning}",
                    )

                # 6. Execute the action
                result = await self._execute_action(action)

                # 7. Log
                log_entry = {
                    "step": step + 1,
                    "action_type": action.action_type.value,
                    "target": action.selector or action.text or action.url or "",
                    "reasoning": action.reasoning,
                    "confidence": action.confidence,
                    "result": result,
                    "ts": time.time(),
                }
                if action.extracted_content:
                    log_entry["extracted_content"] = action.extracted_content
                action_log.append(log_entry)

                if on_step:
                    on_step(step + 1, log_entry)

                # 8. Small pause between actions
                if action.action_type == BrowserActionType.WAIT:
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.3)

            except Exception as e:
                logger.error("[BROWSER_AGENT] Step %d error: %s", step + 1, e)
                action_log.append({
                    "step": step + 1,
                    "error": str(e),
                    "ts": time.time(),
                })
                continue

        # Hit max steps
        final_state = await self.controller.get_page_state()
        return BrowserTaskResult(
            success=False,
            steps_taken=self.max_steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            action_log=action_log,
            error=f"Hit max steps ({self.max_steps}) without completing task",
            final_url=final_state.get("url", ""),
            final_title=final_state.get("title", ""),
        )

    def stop(self) -> None:
        """Abort the current task."""
        self._running = False

    # ── Action dispatch ───────────────────────────────────────────────────

    async def _execute_action(self, action: BrowserAction) -> Dict[str, Any]:
        """Dispatch a BrowserAction to the controller."""
        match action.action_type:
            case BrowserActionType.NAVIGATE:
                return await self.controller.navigate(action.url or "")
            case BrowserActionType.CLICK:
                return await self.controller.click(action.selector or "")
            case BrowserActionType.CLICK_TEXT:
                return await self.controller.click_text(action.text or "")
            case BrowserActionType.FILL:
                return await self.controller.fill(action.selector or "", action.value or "")
            case BrowserActionType.SELECT:
                return await self.controller.select(action.selector or "", action.value or "")
            case BrowserActionType.SCROLL:
                direction = action.value or "down"
                return await self.controller.scroll(direction=direction)
            case BrowserActionType.PRESS_KEY:
                return await self.controller.press_key(action.text or "Enter")
            case BrowserActionType.READ:
                text = await self.controller.get_page_text(max_length=5000)
                return {"type": "read", "text_length": len(text), "success": True}
            case BrowserActionType.EXTRACT:
                content = await self.controller.extract_structured_content(action.selector)
                return {"type": "extract", "content": content, "success": True}
            case BrowserActionType.GO_BACK:
                await self.controller.go_back()
                return {"type": "go_back", "success": True}
            case BrowserActionType.WAIT:
                await asyncio.sleep(2.0)
                return {"type": "wait", "success": True}
            case BrowserActionType.SCREENSHOT:
                b64 = await self.controller.screenshot()
                return {"type": "screenshot", "has_data": bool(b64), "success": True}
            case _:
                return {"type": "unknown", "error": f"Unknown action: {action.action_type}"}

    # ── LLM decision-making ───────────────────────────────────────────────

    async def _decide_next_action(
        self,
        task: str,
        page_state: Dict[str, Any],
        page_text: str,
        elements: List[Dict[str, Any]],
        form_fields: List[Dict[str, Any]],
        action_history: List[Dict[str, Any]],
        memory_context: str = "",
    ) -> Optional[BrowserAction]:
        """Ask LLM what to do next given current page state."""
        if not self.llm_client:
            logger.error("[BROWSER_AGENT] No LLM client — cannot decide actions")
            return None

        # Format action history for the prompt
        history_lines = []
        for entry in action_history:
            action_type = entry.get("action_type", "?")
            target = entry.get("target", "")
            reasoning = entry.get("reasoning", "")
            history_lines.append(f"  - {action_type}: {target} ({reasoning})")
        history_text = "\n".join(history_lines) if history_lines else "  None yet — this is the first step."

        # Format elements for prompt (compact)
        elements_compact = []
        for el in elements[:25]:
            text = el.get("text", "")[:60]
            selector = el.get("selector", "")
            tag = el.get("tag", "")
            elements_compact.append(f"  [{tag}] \"{text}\" → {selector}")
        elements_text = "\n".join(elements_compact) if elements_compact else "  (no interactive elements found)"

        # Format form fields
        fields_compact = []
        for f in form_fields:
            name = f.get("name", "")
            ftype = f.get("type", "")
            label = f.get("label", "")
            selector = f.get("selector", "")
            fields_compact.append(f"  [{ftype}] name=\"{name}\" label=\"{label}\" → {selector}")
        fields_text = "\n".join(fields_compact) if fields_compact else "  (no form fields)"

        memory_section = f"\nKnown context:\n{memory_context}" if memory_context else ""

        prompt = _ACTION_SELECTION_TEMPLATE.format(
            task=task,
            url=page_state.get("url", "?"),
            title=page_state.get("title", "?"),
            page_text=page_text[:2000],
            elements_json=elements_text,
            form_fields_json=fields_text,
            action_history=history_text,
            memory_context=memory_section,
        )

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system=_ACTION_SELECTION_SYSTEM,
                max_tokens=500,
                temperature=0.3,
            )
            return self._parse_action_response(response)
        except Exception as e:
            logger.error("[BROWSER_AGENT] LLM call failed: %s", e)
            return None

    def _parse_action_response(self, response: str) -> Optional[BrowserAction]:
        """Parse LLM JSON response into a BrowserAction."""
        try:
            # Strip markdown code blocks if present
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            data = json.loads(text)

            action_str = data.get("action", "failed")
            try:
                action_type = BrowserActionType(action_str)
            except ValueError:
                logger.warning("[BROWSER_AGENT] Unknown action type: %s", action_str)
                action_type = BrowserActionType.FAILED

            return BrowserAction(
                action_type=action_type,
                selector=data.get("selector"),
                url=data.get("url"),
                text=data.get("text"),
                value=data.get("value"),
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.5)),
                extracted_content=data.get("extracted_content"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[BROWSER_AGENT] Failed to parse LLM response: %s — %s", e, response[:200])
            return None

    # ── Safety checks ─────────────────────────────────────────────────────

    def _is_blocked_domain(self, url: str) -> bool:
        """Check if a URL points to a blocked domain."""
        url_lower = url.lower()

        # Check explicit blocked domains
        for domain in BLOCKED_DOMAINS:
            if domain in url_lower:
                return True

        # Check blocked keywords in domain
        for keyword in BLOCKED_DOMAIN_KEYWORDS:
            if keyword in url_lower:
                return True

        # Check user-configured blocklist
        for domain in self.domain_blocklist:
            if domain.lower() in url_lower:
                return True

        # Check user-configured allowlist (if set, only allow listed domains)
        if self.domain_allowlist:
            allowed = any(d.lower() in url_lower for d in self.domain_allowlist)
            if not allowed:
                return True

        return False

    def _is_blocked_field(self, selector: str, form_fields: List[Dict[str, Any]]) -> bool:
        """Check if a form field should not be auto-filled."""
        selector_lower = selector.lower()

        # Check against blocked field names/types
        for blocked in BLOCKED_FIELDS:
            if blocked in selector_lower:
                return True

        # Check the actual field metadata
        for f in form_fields:
            if f.get("selector") == selector:
                name = (f.get("name") or "").lower()
                ftype = (f.get("type") or "").lower()
                label = (f.get("label") or "").lower()
                for blocked in BLOCKED_FIELDS:
                    if blocked in name or blocked in ftype or blocked in label:
                        return True
                # Also block password-type inputs
                if ftype == "password":
                    return True
                break

        return False

    def _needs_confirmation(self, action: BrowserAction, page_state: Dict[str, Any]) -> bool:
        """Check if this action should require user confirmation."""
        if self.confirm_mode == "never":
            return False

        if self.confirm_mode == "all_actions":
            return True

        # "submissions_only" mode — check for dangerous actions
        target = (action.text or action.selector or "").lower()
        reasoning = action.reasoning.lower()

        # Check if clicking a submit-like button
        if action.action_type in (BrowserActionType.CLICK, BrowserActionType.CLICK_TEXT):
            for keyword in CONFIRM_ACTIONS:
                if keyword in target or keyword in reasoning:
                    return True

        # Check URL patterns
        url = page_state.get("url", "")
        for pattern in CONFIRM_URL_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                if action.action_type in (BrowserActionType.CLICK, BrowserActionType.CLICK_TEXT, BrowserActionType.FILL):
                    return True

        return False

    # ── Sync bridge ───────────────────────────────────────────────────────

    def execute_task_sync(
        self,
        task: str,
        start_url: Optional[str] = None,
        memory_context: str = "",
        on_step: Optional[Callable] = None,
    ) -> BrowserTaskResult:
        """Sync wrapper for execute_task. Creates/reuses event loop.

        For use from synchronous code (e.g., TaskAgent._run_browser_action).
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in an async context — use a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.execute_task(task, start_url, memory_context, on_step),
                    )
                    return future.result(timeout=self.max_steps * self.step_timeout)
            else:
                return loop.run_until_complete(
                    self.execute_task(task, start_url, memory_context, on_step)
                )
        except RuntimeError:
            # No event loop exists
            return asyncio.run(
                self.execute_task(task, start_url, memory_context, on_step)
            )

    def launch_sync(self) -> None:
        """Sync wrapper for controller.launch()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self.controller.launch())
                    future.result(timeout=30)
            else:
                loop.run_until_complete(self.controller.launch())
        except RuntimeError:
            asyncio.run(self.controller.launch())

    def close_sync(self) -> None:
        """Sync wrapper for controller.close()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self.controller.close())
                    future.result(timeout=10)
            else:
                loop.run_until_complete(self.controller.close())
        except RuntimeError:
            asyncio.run(self.controller.close())
        except Exception:
            pass


# ── Web search convenience ───────────────────────────────────────────────

async def run_web_search(controller, query: str, max_results: int = 10) -> Dict[str, Any]:
    """Quick web search — navigate to search engine, extract results.

    This is a convenience function for the web_search tool.
    Does not require the full ReAct agent loop.
    """
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    try:
        nav_result = await controller.navigate(search_url)

        # Wait for results to load
        await controller.wait_for_load()

        # Extract search results from Google's DOM
        page = await controller.get_active_page()
        results = await page.evaluate(f"""() => {{
            const results = [];
            // Google search result divs
            const items = document.querySelectorAll('div.g, div[data-hveid]');
            for (const item of items) {{
                const link = item.querySelector('a[href]');
                const title = item.querySelector('h3');
                const snippet = item.querySelector('[data-sncf], .VwiC3b, [style*="-webkit-line-clamp"]');
                if (link && title) {{
                    results.push({{
                        title: title.textContent.trim(),
                        url: link.href,
                        snippet: snippet ? snippet.textContent.trim().substring(0, 300) : '',
                    }});
                }}
                if (results.length >= {max_results}) break;
            }}
            return results;
        }}""")

        return {
            "success": True,
            "query": query,
            "results": results or [],
            "results_count": len(results or []),
            "search_url": search_url,
        }
    except Exception as e:
        logger.error("[BROWSER_AGENT] Web search failed: %s", e)
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": str(e),
        }
