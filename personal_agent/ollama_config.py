from __future__ import annotations

import os


_LOCAL_OLLAMA_URL = "http://localhost:11434"


def resolve_ollama_base_url() -> str:
    """Return the effective Ollama base URL for the current runtime.

    Desktop local mode may force localhost explicitly so stale shell-wide
    OLLAMA_BASE_URL values do not hijack the app.
    """
    force_local = str(
        os.getenv("CRT_FORCE_LOCAL_OLLAMA")
        or os.getenv("AETHER_FORCE_LOCAL_OLLAMA")
        or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if force_local:
        return _LOCAL_OLLAMA_URL

    desktop_override = str(
        os.getenv("CRT_DESKTOP_OLLAMA_BASE_URL")
        or os.getenv("AETHER_OLLAMA_BASE_URL")
        or ""
    ).strip()
    if desktop_override:
        return desktop_override

    return str(os.getenv("OLLAMA_BASE_URL") or _LOCAL_OLLAMA_URL).strip() or _LOCAL_OLLAMA_URL
