"""Shared dependency contracts for modular route handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from personal_agent.crt_rag import CRTEnhancedRAG


@dataclass(frozen=True)
class RouteDeps:
    """Typed contract for route modules.

    This keeps route extraction incremental: modules can adopt only the fields
    they need without importing `crt_api` internals directly.
    """

    get_engine: Callable[[str], CRTEnhancedRAG]

