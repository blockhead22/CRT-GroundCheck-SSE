"""
Cloud provider abstraction for testing.
Three providers: OpenAI (official), CCProxy (local reverse proxy), Cookie (unofficial session).
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests
from curl_cffi.requests import get as cffi_get, post as cffi_post


@dataclass
class ProviderResult:
    content: str
    tokens_used: int
    cost_est: float
    latency_ms: float
    provider: str
    model: str
    parsed: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def try_parse_json(self) -> "ProviderResult":
        """Attempt to parse content as JSON, store in .parsed"""
        try:
            # Handle markdown-wrapped JSON
            text = self.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last lines (```json and ```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines).strip()
            self.parsed = json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            self.error = f"JSON parse failed: {e}"
            self.parsed = None
        return self


class CloudProvider(ABC):
    """Base class for cloud providers."""

    name: str = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int = 300) -> ProviderResult:
        """Send a completion request. Returns structured result."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...


# ── OpenAI Provider ──────────────────────────────────────────────

class OpenAIProvider(CloudProvider):
    """Official OpenAI API via OPENAI_API_KEY."""

    name = "openai"

    # gpt-4o-mini pricing (per 1M tokens)
    INPUT_COST_PER_M = 0.15
    OUTPUT_COST_PER_M = 0.60

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client

    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def complete(self, system: str, prompt: str, max_tokens: int = 300) -> ProviderResult:
        client = self._get_client()
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            elapsed = (time.perf_counter() - start) * 1000
            usage = resp.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = input_tokens + output_tokens
            cost = (input_tokens * self.INPUT_COST_PER_M + output_tokens * self.OUTPUT_COST_PER_M) / 1_000_000
            content = resp.choices[0].message.content or ""
            return ProviderResult(
                content=content,
                tokens_used=total_tokens,
                cost_est=cost,
                latency_ms=elapsed,
                provider=self.name,
                model=self.model,
            ).try_parse_json()
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                content="",
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model=self.model,
                error=str(e),
            )


# ── CCProxy Provider ─────────────────────────────────────────────

class CCProxyProvider(CloudProvider):
    """Anthropic via CCProxy local reverse proxy (localhost:8000)."""

    name = "ccproxy"

    def __init__(self, model: str = "claude-sonnet-4-6", base_url: str = "http://localhost:8000/v1"):
        self.model = model
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key="ccproxy",  # CCProxy doesn't need a real key
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client

    def is_available(self) -> bool:
        """Check if CCProxy is running on localhost:8000."""
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.base_url.rstrip('/v1')}/health", timeout=2)
            return True
        except Exception:
            return False

    def complete(self, system: str, prompt: str, max_tokens: int = 300) -> ProviderResult:
        client = self._get_client()
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            elapsed = (time.perf_counter() - start) * 1000
            usage = resp.usage
            total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
            content = resp.choices[0].message.content or ""
            return ProviderResult(
                content=content,
                tokens_used=total_tokens,
                cost_est=0.0,  # subscription — no per-call cost
                latency_ms=elapsed,
                provider=self.name,
                model=self.model,
            ).try_parse_json()
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                content="",
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model=self.model,
                error=str(e),
            )


# ── Cookie Provider ──────────────────────────────────────────────

class CookieProvider(CloudProvider):
    """Anthropic via claude.ai session cookie (Chrome-based)."""

    name = "cookie"

    def __init__(self):
        self._session = None
        self._chat_id = None

    def _load_session(self):
        if self._session is None:
            from tests.cloud_providers.chrome_session import ClaudeSession, SESSION_FILE
            self._session = ClaudeSession.load(SESSION_FILE)
        return self._session

    def is_available(self) -> bool:
        session = self._load_session()
        return session is not None and bool(session.cookie)

    def _get_headers(self) -> dict:
        session = self._load_session()
        return {
            "Cookie": session.cookie,
            "User-Agent": session.user_agent,
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json",
        }

    def _ensure_chat(self) -> str:
        """Create a chat conversation if needed, return chat_id."""
        if self._chat_id:
            return self._chat_id
        import uuid as _uuid
        session = self._load_session()
        org_id = session.organization_id
        headers = self._get_headers()

        new_uuid = str(_uuid.uuid4())
        resp = cffi_post(
            f"https://claude.ai/api/organizations/{org_id}/chat_conversations",
            headers=headers,
            json={"name": "", "uuid": new_uuid},
            impersonate="chrome",
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            self._chat_id = data.get("uuid", data.get("id", new_uuid))
            return self._chat_id
        raise RuntimeError(f"Failed to create chat: {resp.status_code} {resp.text[:300]}")

    def _upload_image(self, image_bytes: bytes, filename: str = "screenshot.jpg",
                      content_type: str = "image/jpeg") -> Optional[str]:
        """Upload an image to claude.ai and return the file UUID."""
        try:
            from curl_cffi import CurlMime
        except ImportError:
            raise ImportError("curl_cffi required for image upload. Run: pip install curl_cffi")

        session = self._load_session()
        org_id = session.organization_id
        headers = {
            "Cookie": session.cookie,
            "User-Agent": session.user_agent,
        }

        mp = CurlMime()
        mp.addpart(name="file", filename=filename, content_type=content_type, data=image_bytes)
        mp.addpart(name="orgUuid", data=org_id.encode())

        resp = cffi_post(
            f"https://claude.ai/api/{org_id}/upload",
            headers=headers,
            multipart=mp,
            impersonate="chrome",
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            file_uuid = data.get("file_uuid") or data.get("uuid") or data.get("id")
            if file_uuid:
                print(f"[COOKIE] Uploaded image: {file_uuid} ({len(image_bytes)} bytes)")
                return file_uuid
        print(f"[COOKIE] Upload failed: {resp.status_code} {resp.text[:200]}")
        return None

    def complete_with_image(self, system: str, prompt: str, image_b64: str,
                            image_media_type: str = "image/jpeg",
                            max_tokens: int = 1000) -> ProviderResult:
        """Send a prompt with an image to Claude via cookie session.

        Uploads the image first, then sends the prompt with the file UUID.
        """
        import base64 as _b64

        start = time.perf_counter()
        try:
            # Decode base64 image
            image_bytes = _b64.b64decode(image_b64)

            # Determine filename/extension from media type
            ext = "jpg" if "jpeg" in image_media_type else image_media_type.split("/")[-1]
            filename = f"screenshot.{ext}"

            # Upload image
            file_uuid = self._upload_image(image_bytes, filename, image_media_type)
            if not file_uuid:
                elapsed = (time.perf_counter() - start) * 1000
                return ProviderResult(
                    content="",
                    tokens_used=0,
                    cost_est=0.0,
                    latency_ms=elapsed,
                    provider=self.name,
                    model="claude-via-session",
                    error="Failed to upload image to claude.ai",
                )

            # Send completion with file UUID
            session = self._load_session()
            org_id = session.organization_id
            chat_id = self._ensure_chat()
            headers = self._get_headers()

            full_prompt = f"{system}\n\n{prompt}" if system else prompt

            payload = {
                "prompt": full_prompt,
                "timezone": "America/Los_Angeles",
                "model": "claude-sonnet-4-5",
                "attachments": [],
                "files": [file_uuid],
                "rendering_mode": "messages",
            }

            resp = cffi_post(
                f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{chat_id}/completion",
                headers=headers,
                json=payload,
                impersonate="chrome",
                timeout=120,
            )

            full_text = self._parse_sse_response(resp.text)
            elapsed = (time.perf_counter() - start) * 1000

            if not full_text and resp.status_code != 200:
                return ProviderResult(
                    content="",
                    tokens_used=0,
                    cost_est=0.0,
                    latency_ms=elapsed,
                    provider=self.name,
                    model="claude-via-session",
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return ProviderResult(
                content=full_text.strip(),
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model="claude-via-session",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                content="",
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model="claude-via-session",
                error=str(e),
            )

    @staticmethod
    def _parse_sse_response(response_text: str) -> str:
        """Parse SSE response from claude.ai into plain text."""
        full_text = ""
        for line in response_text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            try:
                event_data = json.loads(line[6:])
                evt_type = event_data.get("type", "")
                if evt_type == "content_block_delta":
                    delta = event_data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        full_text += delta.get("text", "")
                elif "completion" in event_data:
                    full_text += event_data["completion"]
            except json.JSONDecodeError:
                pass
        return full_text

    def complete(self, system: str, prompt: str, max_tokens: int = 300) -> ProviderResult:
        start = time.perf_counter()
        try:
            session = self._load_session()
            org_id = session.organization_id
            chat_id = self._ensure_chat()
            headers = self._get_headers()

            full_prompt = f"{system}\n\n{prompt}\n\nRespond with valid JSON only."

            payload = {
                "prompt": full_prompt,
                "timezone": "America/Los_Angeles",
                "model": "claude-sonnet-4-5",
                "attachments": [],
                "files": [],
                "rendering_mode": "messages",
            }

            resp = cffi_post(
                f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{chat_id}/completion",
                headers=headers,
                json=payload,
                impersonate="chrome",
                timeout=120,
            )

            print(f"[COOKIE_DEBUG] HTTP {resp.status_code}, body length={len(resp.text)}, first 300 chars: {resp.text[:300]}")

            full_text = self._parse_sse_response(resp.text)
            elapsed = (time.perf_counter() - start) * 1000

            if not full_text and resp.status_code != 200:
                return ProviderResult(
                    content="",
                    tokens_used=0,
                    cost_est=0.0,
                    latency_ms=elapsed,
                    provider=self.name,
                    model="claude-via-session",
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return ProviderResult(
                content=full_text.strip(),
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model="claude-via-session",
            ).try_parse_json()
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                content="",
                tokens_used=0,
                cost_est=0.0,
                latency_ms=elapsed,
                provider=self.name,
                model="claude-via-session",
                error=str(e),
            )


# ── Factory ──────────────────────────────────────────────────────

PROVIDERS = {
    "openai": OpenAIProvider,
    "ccproxy": CCProxyProvider,
    "cookie": CookieProvider,
}


def get_provider(name: str) -> CloudProvider:
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name}. Choose from: {list(PROVIDERS.keys())}")
    return cls()


def get_available_providers() -> list[CloudProvider]:
    available = []
    for name, cls in PROVIDERS.items():
        try:
            p = cls()
            if p.is_available():
                available.append(p)
        except Exception:
            pass
    return available
