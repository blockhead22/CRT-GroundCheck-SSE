"""CRT Companion policy helpers.

This module encodes *enforceable* boundary checks that support:
- provenance requirements for tool/external memories
- future permission-tier tool use

It is intentionally small: policy enforcement should be testable and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PermissionTier(str, Enum):
    SILENT = "silent"          # Tier 0
    ASK_ONCE = "ask_once"      # Tier 1
    ALWAYS_ASK = "always_ask"  # Tier 2


@dataclass(frozen=True)
class ToolProvenance:
    tool: str
    retrieved_at: str  # ISO8601 string
    source: str        # URL or file path
    query: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    excerpt: Optional[str] = None


def validate_external_memory_context(context: Optional[Dict[str, Any]]) -> None:
    """Validate that external/tool memories include provenance.

    Raises:
        ValueError: if required provenance is missing.
    """
    if not context:
        raise ValueError("EXTERNAL memories require context with provenance")

    prov = context.get("provenance")
    if not isinstance(prov, dict):
        raise ValueError("EXTERNAL memories require context['provenance'] as a dict")

    for key in ("tool", "retrieved_at", "source"):
        if not prov.get(key):
            raise ValueError(f"EXTERNAL memories require provenance.{key}")
