"""Tooling API routes: model listing for the Tooling settings tab."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tooling", tags=["tooling"])


# Hardcoded cloud / anthropic model catalogues (these don't have free list APIs)
_CLOUD_MODELS: List[Dict[str, str]] = [
    {"name": "gpt-4o", "label": "GPT-4o"},
    {"name": "gpt-4o-mini", "label": "GPT-4o Mini"},
    {"name": "gpt-4.1", "label": "GPT-4.1"},
    {"name": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
    {"name": "gpt-4.1-nano", "label": "GPT-4.1 Nano"},
]

_ANTHROPIC_MODELS: List[Dict[str, str]] = [
    {"name": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
    {"name": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
    {"name": "claude-haiku-3-5", "label": "Claude Haiku 3.5"},
]


@router.get("/models")
async def list_available_models() -> Dict[str, Any]:
    """Return available models from all providers.

    Local models are fetched live from Ollama; cloud / anthropic are static
    catalogues since those APIs don't expose a free model-list endpoint.
    """
    local_models: List[Dict[str, Any]] = []
    try:
        import ollama as _ollama  # type: ignore

        resp = _ollama.list()
        # ollama.list() returns {"models": [{"name": ..., "size": ..., ...}, ...]}
        raw_models = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
        for m in raw_models:
            if isinstance(m, dict):
                name = m.get("name", m.get("model", ""))
                size_bytes = m.get("size", 0)
            else:
                name = getattr(m, "name", getattr(m, "model", ""))
                size_bytes = getattr(m, "size", 0)
            size_gb = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else ""
            local_models.append({"name": name, "size": size_gb})
    except Exception as exc:
        logger.warning("[TOOLING] Failed to list Ollama models: %s", exc)

    return {
        "local": local_models,
        "cloud": _CLOUD_MODELS,
        "anthropic": _ANTHROPIC_MODELS,
    }
