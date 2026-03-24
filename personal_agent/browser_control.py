"""
Browser control module — low-level Playwright automation primitives.

Pure automation library with ZERO knowledge of the agent system.
Uses Playwright for browser automation, screenshots, DOM reading.

Mirrors the architecture of desktop_control.py.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )
    HAS_PLAYWRIGHT = True
except ImportError as _e:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright import failed: %s", _e)
except Exception as _e:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright import error (non-ImportError): %s", _e)

logger.info("browser_control imports: playwright=%s", HAS_PLAYWRIGHT)


class BrowserController:
    """Low-level browser automation primitives via Playwright."""

    def __init__(
        self,
        headless: bool = False,
        persistent_context_dir: Optional[str] = None,
        engine: str = "chromium",
    ) -> None:
        if not HAS_PLAYWRIGHT:
            raise ImportError(
                "playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        self.headless = headless
        self.persistent_context_dir = persistent_context_dir
        self.engine = engine  # "chromium", "firefox", "webkit"

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._action_history: List[Dict[str, Any]] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def launch(self) -> None:
        """Launch browser and create initial page."""
        self._playwright = await async_playwright().start()

        browser_type = getattr(self._playwright, self.engine, self._playwright.chromium)

        if self.persistent_context_dir:
            # Persistent context saves cookies/sessions between runs
            self._context = await browser_type.launch_persistent_context(
                user_data_dir=self.persistent_context_dir,
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                accept_downloads=False,
            )
            # Persistent contexts come with a page already
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()
        else:
            self._browser = await browser_type.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                accept_downloads=False,
            )
            self._page = await self._context.new_page()

        logger.info(
            "[BROWSER] Launched %s (headless=%s, persistent=%s)",
            self.engine, self.headless, bool(self.persistent_context_dir),
        )

    async def close(self) -> None:
        """Close browser and cleanup."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("[BROWSER] Close error: %s", e)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None

    async def new_page(self) -> Page:
        """Open a new tab/page."""
        if not self._context:
            raise RuntimeError("Browser not launched. Call launch() first.")
        self._page = await self._context.new_page()
        return self._page

    async def get_active_page(self) -> Page:
        """Get the current active page."""
        if not self._page:
            raise RuntimeError("No active page. Call launch() first.")
        return self._page

    # ── Navigation ─────────────────────────────────────────────────────────

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> Dict[str, Any]:
        """Navigate to a URL. Returns page info."""
        page = await self.get_active_page()
        t0 = time.time()
        try:
            response = await page.goto(url, wait_until=wait_until, timeout=30000)
            status_code = response.status if response else 0
        except Exception as e:
            logger.warning("[BROWSER] Navigation error: %s", e)
            status_code = 0

        load_time_ms = round((time.time() - t0) * 1000)
        result = {
            "url": page.url,
            "title": await page.title(),
            "status_code": status_code,
            "load_time_ms": load_time_ms,
        }
        action = {"type": "navigate", "url": url, "ts": time.time(), **result}
        self._action_history.append(action)
        return result

    async def go_back(self) -> None:
        """Navigate back in history."""
        page = await self.get_active_page()
        await page.go_back(timeout=10000)

    async def go_forward(self) -> None:
        """Navigate forward in history."""
        page = await self.get_active_page()
        await page.go_forward(timeout=10000)

    async def reload(self) -> None:
        """Reload current page."""
        page = await self.get_active_page()
        await page.reload(timeout=15000)

    # ── Page Reading (DOM mode) ────────────────────────────────────────────

    async def get_page_text(self, max_length: int = 5000) -> str:
        """Extract visible text content from the page."""
        page = await self.get_active_page()
        try:
            text = await page.evaluate("""() => {
                // Get visible text, skip hidden elements and scripts
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const el = node.parentElement;
                            if (!el) return NodeFilter.FILTER_REJECT;
                            const tag = el.tagName.toLowerCase();
                            if (['script', 'style', 'noscript', 'svg'].includes(tag))
                                return NodeFilter.FILTER_REJECT;
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden')
                                return NodeFilter.FILTER_REJECT;
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                const texts = [];
                let node;
                while (node = walker.nextNode()) {
                    const t = node.textContent.trim();
                    if (t) texts.push(t);
                }
                return texts.join('\\n');
            }""")
            return text[:max_length] if text else ""
        except Exception as e:
            logger.warning("[BROWSER] get_page_text error: %s", e)
            return ""

    async def get_page_title(self) -> str:
        """Get the page title."""
        page = await self.get_active_page()
        return await page.title()

    async def get_page_url(self) -> str:
        """Get the current page URL."""
        page = await self.get_active_page()
        return page.url

    async def get_links(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Extract links from the page. Returns [{text, href, visible}]."""
        page = await self.get_active_page()
        try:
            links = await page.evaluate(f"""() => {{
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.slice(0, {limit}).map(a => {{
                    const rect = a.getBoundingClientRect();
                    return {{
                        text: (a.textContent || '').trim().substring(0, 100),
                        href: a.href,
                        visible: rect.width > 0 && rect.height > 0,
                    }};
                }});
            }}""")
            return links or []
        except Exception as e:
            logger.warning("[BROWSER] get_links error: %s", e)
            return []

    async def get_form_fields(self) -> List[Dict[str, Any]]:
        """Extract form fields from the page. Returns [{name, type, label, value, placeholder, selector}]."""
        page = await self.get_active_page()
        try:
            fields = await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll(
                    'input, textarea, select'
                ));
                return inputs.map((el, i) => {
                    // Try to find associated label
                    let label = '';
                    if (el.id) {
                        const labelEl = document.querySelector(`label[for="${el.id}"]`);
                        if (labelEl) label = labelEl.textContent.trim();
                    }
                    if (!label && el.closest('label')) {
                        label = el.closest('label').textContent.trim();
                    }
                    if (!label) label = el.getAttribute('aria-label') || '';

                    // Build a unique selector
                    let selector = '';
                    if (el.id) selector = '#' + el.id;
                    else if (el.name) selector = `[name="${el.name}"]`;
                    else selector = `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`;

                    return {
                        name: el.name || '',
                        type: el.type || el.tagName.toLowerCase(),
                        label: label.substring(0, 100),
                        value: el.value || '',
                        placeholder: el.placeholder || '',
                        selector: selector,
                    };
                });
            }""")
            return fields or []
        except Exception as e:
            logger.warning("[BROWSER] get_form_fields error: %s", e)
            return []

    async def get_interactive_elements(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get clickable/fillable elements. Returns [{tag, text, role, selector, type}]."""
        page = await self.get_active_page()
        try:
            elements = await page.evaluate(f"""() => {{
                const selectors = 'a, button, input, textarea, select, [role="button"], [role="link"], [role="tab"], [onclick], [tabindex]';
                const els = Array.from(document.querySelectorAll(selectors));
                return els.slice(0, {limit}).map((el, i) => {{
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) return null;

                    let selector = '';
                    if (el.id) selector = '#' + el.id;
                    else if (el.name) selector = `[${{el.tagName.toLowerCase()}}][name="${{el.name}}"]`;
                    else {{
                        // Use text content or nth-of-type
                        const tag = el.tagName.toLowerCase();
                        const text = (el.textContent || '').trim().substring(0, 30);
                        if (text && tag === 'a') selector = `a:has-text("${{text}}")`;
                        else if (text && tag === 'button') selector = `button:has-text("${{text}}")`;
                        else selector = `${{tag}}:nth-of-type(${{i + 1}})`;
                    }}

                    return {{
                        tag: el.tagName.toLowerCase(),
                        text: (el.textContent || '').trim().substring(0, 100),
                        role: el.getAttribute('role') || '',
                        selector: selector,
                        type: el.type || '',
                    }};
                }}).filter(Boolean);
            }}""")
            return elements or []
        except Exception as e:
            logger.warning("[BROWSER] get_interactive_elements error: %s", e)
            return []

    async def extract_structured_content(self, selector: Optional[str] = None) -> Dict[str, Any]:
        """Extract structured content (headings, tables, lists) from the page."""
        page = await self.get_active_page()
        try:
            content = await page.evaluate(f"""(rootSelector) => {{
                const root = rootSelector
                    ? document.querySelector(rootSelector)
                    : document.body;
                if (!root) return {{ headings: [], tables: [], lists: [] }};

                const headings = Array.from(root.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(h => ({{
                    level: parseInt(h.tagName[1]),
                    text: h.textContent.trim().substring(0, 200),
                }}));

                const tables = Array.from(root.querySelectorAll('table')).slice(0, 5).map(t => {{
                    const rows = Array.from(t.querySelectorAll('tr')).slice(0, 20).map(tr =>
                        Array.from(tr.querySelectorAll('td, th')).map(cell =>
                            cell.textContent.trim().substring(0, 100)
                        )
                    );
                    return rows;
                }});

                const lists = Array.from(root.querySelectorAll('ul, ol')).slice(0, 10).map(list =>
                    Array.from(list.querySelectorAll(':scope > li')).slice(0, 20).map(li =>
                        li.textContent.trim().substring(0, 200)
                    )
                );

                return {{ headings, tables, lists }};
            }}""", selector)
            return content or {"headings": [], "tables": [], "lists": []}
        except Exception as e:
            logger.warning("[BROWSER] extract_structured_content error: %s", e)
            return {"headings": [], "tables": [], "lists": []}

    # ── Actions ────────────────────────────────────────────────────────────

    async def click(self, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """Click an element by CSS selector."""
        page = await self.get_active_page()
        try:
            await page.click(selector, timeout=timeout)
            action = {"type": "click", "selector": selector, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "click", "selector": selector, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    async def click_text(self, text: str, timeout: int = 5000) -> Dict[str, Any]:
        """Click an element containing this text."""
        page = await self.get_active_page()
        try:
            await page.get_by_text(text, exact=False).first.click(timeout=timeout)
            action = {"type": "click_text", "text": text, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "click_text", "text": text, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        """Fill a form field by selector."""
        page = await self.get_active_page()
        try:
            await page.fill(selector, value, timeout=5000)
            action = {"type": "fill", "selector": selector, "value": value, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "fill", "selector": selector, "value": value, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    async def select(self, selector: str, value: str) -> Dict[str, Any]:
        """Select an option from a dropdown."""
        page = await self.get_active_page()
        try:
            await page.select_option(selector, value, timeout=5000)
            action = {"type": "select", "selector": selector, "value": value, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "select", "selector": selector, "value": value, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    async def press_key(self, key: str) -> Dict[str, Any]:
        """Press a keyboard key."""
        page = await self.get_active_page()
        try:
            await page.keyboard.press(key)
            action = {"type": "key_press", "key": key, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "key_press", "key": key, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    async def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        """Scroll the page. direction: 'up' or 'down'."""
        page = await self.get_active_page()
        delta = amount if direction == "down" else -amount
        try:
            await page.evaluate(f"window.scrollBy(0, {delta})")
            action = {"type": "scroll", "direction": direction, "amount": amount, "success": True, "ts": time.time()}
        except Exception as e:
            action = {"type": "scroll", "direction": direction, "amount": amount, "success": False, "error": str(e), "ts": time.time()}
        self._action_history.append(action)
        return action

    # ── Screenshots ────────────────────────────────────────────────────────

    async def screenshot(self, full_page: bool = False) -> str:
        """Take a screenshot. Returns base64 JPEG (same format as desktop_control)."""
        page = await self.get_active_page()
        try:
            png_bytes = await page.screenshot(full_page=full_page, type="jpeg", quality=75)
            return base64.b64encode(png_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("[BROWSER] Screenshot error: %s", e)
            return ""

    async def screenshot_element(self, selector: str) -> str:
        """Screenshot a specific element. Returns base64 JPEG."""
        page = await self.get_active_page()
        try:
            element = page.locator(selector).first
            png_bytes = await element.screenshot(type="jpeg", quality=75)
            return base64.b64encode(png_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("[BROWSER] Element screenshot error: %s", e)
            return ""

    # ── Waiting ────────────────────────────────────────────────────────────

    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for an element to appear. Returns True if found."""
        page = await self.get_active_page()
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_for_navigation(self, timeout: int = 10000) -> bool:
        """Wait for navigation to complete."""
        page = await self.get_active_page()
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_for_load(self) -> None:
        """Wait for page to fully load."""
        page = await self.get_active_page()
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # networkidle can timeout on busy pages — that's OK

    # ── State ──────────────────────────────────────────────────────────────

    async def get_cookies(self) -> List[Dict[str, Any]]:
        """Get all cookies for the current context."""
        if not self._context:
            return []
        try:
            return await self._context.cookies()
        except Exception:
            return []

    async def get_page_state(self) -> Dict[str, Any]:
        """Get a summary of the current page state."""
        page = await self.get_active_page()
        try:
            state = await page.evaluate("""() => ({
                url: location.href,
                title: document.title,
                has_forms: document.querySelectorAll('form').length > 0,
                interactive_count: document.querySelectorAll(
                    'a, button, input, textarea, select, [role="button"]'
                ).length,
                scroll_position: { x: window.scrollX, y: window.scrollY },
                page_height: document.documentElement.scrollHeight,
                viewport_height: window.innerHeight,
            })""")
            return state or {}
        except Exception as e:
            return {"url": page.url, "title": "", "error": str(e)}

    # ── History ────────────────────────────────────────────────────────────

    def get_action_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action history."""
        return self._action_history[-limit:]

    def clear_history(self) -> None:
        """Clear action history buffer."""
        self._action_history.clear()
