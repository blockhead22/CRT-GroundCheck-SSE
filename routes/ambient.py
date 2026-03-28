"""Ambient mode — vision-based screen context analysis.

Accepts a base64 screenshot, sends it to a vision-capable LLM for
description, and stores the result as a low-confidence CRT memory.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, Optional

import litellm
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from personal_agent.crt_core import MemorySource

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Request / Response models ─────────────────────────────────────────

class AmbientAnalyzeRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded PNG screenshot")
    thread_id: str = Field(default="default")
    timestamp: float = Field(default_factory=time.time)


class AmbientAnalyzeResponse(BaseModel):
    description: str
    memory_stored: bool = False
    memory_id: Optional[str] = None


# ── Vision prompt ─────────────────────────────────────────────────────

AMBIENT_VISION_PROMPT = (
    "Describe what the user is doing on their screen. "
    "What application is open? What are they working on? "
    "Are there any errors, code, or notable content visible? "
    "Be concise — 2-3 sentences max."
)


# ── Helpers ───────────────────────────────────────────────────────────

def _call_vision_api(image_b64: str, llm_client) -> str:
    """Call a vision-capable model with the screenshot.

    Tries Anthropic (Claude) first via litellm, falls back to OpenAI GPT-4o-mini.
    """
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                    },
                },
                {
                    "type": "text",
                    "text": AMBIENT_VISION_PROMPT,
                },
            ],
        }
    ]

    # Try Anthropic first
    if llm_client and llm_client.anthropic_available:
        try:
            model_name = llm_client.anthropic_model or "claude-sonnet-4-6"
            litellm_model = model_name if model_name.startswith("anthropic/") else f"anthropic/{model_name}"
            response = litellm.completion(
                model=litellm_model,
                messages=messages,
                max_tokens=200,
                temperature=0.3,
                api_key=llm_client.anthropic_api_key,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("[ambient] Anthropic vision call failed: %s", e)

    # Fallback: OpenAI GPT-4o-mini (has vision)
    if llm_client and llm_client.cloud_available:
        try:
            cloud_model = llm_client.cloud_model or "gpt-4o-mini"
            response = litellm.completion(
                model=cloud_model,
                messages=messages,
                max_tokens=200,
                temperature=0.3,
                api_key=llm_client.cloud_api_key,
                api_base=llm_client.cloud_base_url or None,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("[ambient] OpenAI vision fallback failed: %s", e)

    # Fallback: Cookie Claude (no API key needed)
    try:
        from tests.cloud_providers.providers import CookieProvider
        cookie = CookieProvider()
        result = cookie.complete_with_image(
            system="",
            prompt=AMBIENT_VISION_PROMPT,
            image_b64=image_b64,
            image_media_type="image/png",
            max_tokens=200,
        )
        if result and not getattr(result, "error", None):
            content = getattr(result, "content", "") or ""
            if content.strip():
                logger.info("[ambient] Cookie vision succeeded")
                return content.strip()
        logger.warning("[ambient] Cookie vision returned empty or error: %s", getattr(result, "error", ""))
    except Exception as e:
        logger.warning("[ambient] Cookie vision fallback failed: %s", e)

    raise RuntimeError("No vision-capable API available (need Anthropic or OpenAI key or cookie session)")


def _store_ambient_memory(
    engine,
    description: str,
    timestamp: float,
    thread_id: str,
) -> Optional[str]:
    """Store the vision description as a low-confidence observation memory."""
    try:
        context: Dict[str, Any] = {
            "origin": "ambient_capture",
            "timestamp": timestamp,
            "thread_id": thread_id,
        }
        result = engine.ingest_memory_write(
            text=description,
            confidence=0.5,
            source=MemorySource.SYSTEM,
            context=context,
            user_marked_important=False,
            contradiction_signal=0.0,
            thread_id=thread_id,
            authority="provisional",
            kind="observation",
            source_kind="ambient_vision",
        )
        # ingest_memory_write returns various shapes; try to get an ID
        if isinstance(result, dict):
            return result.get("id") or result.get("memory_id")
        return None
    except Exception as e:
        logger.error("[ambient] Failed to store memory: %s", e)
        return None


# ── Endpoint ──────────────────────────────────────────────────────────

@router.post("/api/ambient/analyze", response_model=AmbientAnalyzeResponse)
def ambient_analyze(req: AmbientAnalyzeRequest, request: Request):
    """Analyze a screenshot and store as ambient observation memory."""

    # Validate base64
    try:
        raw = base64.b64decode(req.image_base64[:100])  # quick sanity check
        if len(req.image_base64) < 100:
            raise ValueError("Image too small")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Get LLM client for API keys
    try:
        llm_client = request.app.state.get_llm_client()
    except Exception:
        llm_client = None

    # Call vision API
    try:
        description = _call_vision_api(req.image_base64, llm_client)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("[ambient] Vision API error: %s", e)
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {e}")

    # Store as memory
    tid = req.thread_id or "default"
    memory_id = None
    memory_stored = False
    try:
        engine = request.app.state.get_engine(tid)
        memory_id = _store_ambient_memory(engine, description, req.timestamp, tid)
        memory_stored = True
    except Exception as e:
        logger.warning("[ambient] Memory storage failed (non-fatal): %s", e)

    # Do NOT log the image — only the text description
    logger.info("[ambient] Analyzed screen: %s", description[:120])

    return AmbientAnalyzeResponse(
        description=description,
        memory_stored=memory_stored,
        memory_id=memory_id,
    )
