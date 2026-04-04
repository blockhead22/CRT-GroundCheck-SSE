"""
Intent-Gated Tool Access — CRT #10

The model doesn't see tools that aren't relevant to the classified intent.
This is proactive gating ("don't show the gun") vs Claude Code's reactive
gating ("let them hold the gun, check if they're allowed to fire").

Two layers:
B) Static intent-to-toolset mapping — defines the floor
C) Earned tool access — execution beliefs shift the ceiling

The static map is the starting position. Execution data from
tool_verification.py and execution_beliefs.py can demote unreliable
tools (require checkpoint) or promote reliable ones (skip checkpoint).

Philosophy:
- Conversational queries don't need bash.
- Research doesn't need file_write.
- The model shouldn't decide what's available. The intent classifier does.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static Intent-to-Toolset Map (Layer B)
# ---------------------------------------------------------------------------

# Each intent type maps to the set of tools it's allowed to see.
# Tools not in the set are invisible to the model for that intent.

INTENT_TOOLSETS: Dict[str, Set[str]] = {
    "conversational": {
        "memory_recall",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
    },
    "identity": {
        "memory_recall",
        "introspect",
    },
    "philosophical": {
        "memory_recall",
        "introspect",
    },
    "research": {
        "memory_recall",
        "web_search",
        "fetch_url",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
    },
    "broad_recall": {
        "memory_recall",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
    },
    "user_reflection": {
        "memory_recall",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
    },
    "file_read": {
        "file_read",
        "dir_list",
        "search_code",
        "memory_recall",
        "introspect",
    },
    "dir_list": {
        "dir_list",
        "file_read",
        "memory_recall",
        "introspect",
    },
    "project_scan": {
        "dir_list",
        "file_read",
        "search_code",
        "memory_recall",
        "introspect",
    },
    "task_continuation": {
        "memory_recall",
        "file_read",
        "dir_list",
        "search_code",
        "introspect",
    },
    "code_task": {
        "memory_recall",
        "file_read",
        "file_write",
        "dir_list",
        "search_code",
        "shell_exec",
        "git_exec",
        "diff_file",
        "code_intel",
        "run_python",
        "plan_create",
        "introspect",
    },
    "file_task": {
        "memory_recall",
        "file_read",
        "file_write",
        "dir_list",
        "search_code",
        "image_read",
        "introspect",
    },
    "reminder": {
        "memory_recall",
        "memory_store",
    },
    "memory_task": {
        "memory_recall",
        "memory_store",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
        "gpt_log_promote",
    },
    "gpt_log_search": {
        "gpt_log_search",
        "gpt_log_context",
        "gpt_log_promote",
        "memory_recall",
        "introspect",
    },
    "gpt_log_context": {
        "gpt_log_search",
        "gpt_log_context",
        "gpt_log_promote",
        "memory_recall",
        "introspect",
    },
    "gpt_log_promote": {
        "gpt_log_search",
        "gpt_log_context",
        "gpt_log_promote",
        "memory_recall",
        "memory_store",
        "introspect",
    },
    "task": {
        # Generic task — broad access
        "memory_recall",
        "web_search",
        "fetch_url",
        "file_read",
        "file_write",
        "dir_list",
        "search_code",
        "shell_exec",
        "code_intel",
        "run_python",
        "plan_create",
        "memory_store",
        "introspect",
        "gpt_log_search",
        "gpt_log_context",
        "gpt_log_promote",
    },
}

# Fallback: if intent not in map, use this set
DEFAULT_TOOLSET: Set[str] = {
    "memory_recall",
    "web_search",
    "introspect",
    "gpt_log_search",
    "gpt_log_context",
}

# Full toolset (for reference / override)
ALL_TOOLS: Set[str] = {
    "memory_recall", "web_search", "fetch_url",
    "file_read", "file_write", "dir_list", "search_code",
    "shell_exec", "git_exec", "diff_file", "code_intel",
    "run_python", "plan_create", "memory_store",
    "image_read", "introspect",
    "gpt_log_search", "gpt_log_context", "gpt_log_promote",
}


_EXPLICIT_NETWORK_INTENTS = {
    "web_search",
    "research",
    "web_browse",
    "url_fetch",
    "service_action",
}


def _is_local_only_mode() -> bool:
    try:
        import auth as _auth_mod

        routing_mode = str(_auth_mod.get_user_setting(1, "routing_mode", "hybrid") or "hybrid").strip().lower()
        generation_mode = str(_auth_mod.get_user_setting(1, "generation_mode", "local") or "local").strip().lower()
        return routing_mode == "local_only" or generation_mode == "local_only"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Earned Tool Access (Layer C)
# ---------------------------------------------------------------------------

# Tools with error rates above this threshold get demoted to checkpoint-required
DEMOTION_ERROR_THRESHOLD = 0.30

# Tools with clean records (0 errors, 5+ uses) get promoted to skip-checkpoint
PROMOTION_MIN_USES = 5
PROMOTION_MAX_ERROR_RATE = 0.05


def _get_tool_reliability() -> Dict[str, Dict[str, Any]]:
    """Load tool reliability data from execution beliefs.

    Returns {tool_name: {"total": N, "errors": N, "error_rate": float}}
    """
    try:
        from .execution_beliefs import get_execution_model
        em = get_execution_model()
        beliefs = em.get_beliefs()
        reliability = {}
        for b in beliefs:
            if b.category == "tool_reliability" and b.sample_size > 0:
                # Parse tool name from claim
                # Claims look like: "shell_exec fails 30% of the time"
                parts = b.claim.split()
                if parts:
                    tool_name = parts[0]
                    reliability[tool_name] = {
                        "total": b.sample_size,
                        "error_rate": b.metric,
                        "confidence": b.confidence,
                    }
        return reliability
    except Exception:
        return {}


def get_demoted_tools() -> Set[str]:
    """Tools that should require checkpoint approval due to high error rates."""
    reliability = _get_tool_reliability()
    demoted = set()
    for tool, stats in reliability.items():
        if stats.get("error_rate", 0) > DEMOTION_ERROR_THRESHOLD:
            demoted.add(tool)
            logger.debug(f"[TOOL_GATE] Demoted {tool}: error_rate={stats['error_rate']:.0%}")
    return demoted


def get_promoted_tools() -> Set[str]:
    """Tools that can skip checkpoint due to clean track record."""
    reliability = _get_tool_reliability()
    promoted = set()
    for tool, stats in reliability.items():
        if (stats.get("total", 0) >= PROMOTION_MIN_USES
                and stats.get("error_rate", 0) <= PROMOTION_MAX_ERROR_RATE):
            promoted.add(tool)
    return promoted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tools_for_intent(
    intent_type: str,
    route: Optional[str] = None,
) -> Set[str]:
    """Get the set of tools available for a given intent.

    Checks the static map first (Layer B), then adjusts based on
    earned execution data (Layer C).

    Args:
        intent_type: Classified intent ("conversational", "code_task", etc.)
        route: Optional routing label for more specific matching.

    Returns:
        Set of tool names the model should see.
    """
    # Layer B: Static mapping
    # Try intent_type first, then route, then default
    toolset = INTENT_TOOLSETS.get(intent_type)
    if toolset is None and route:
        toolset = INTENT_TOOLSETS.get(route)
    if toolset is None:
        toolset = DEFAULT_TOOLSET.copy()
    else:
        toolset = toolset.copy()

    # Layer C: Earned adjustments (demote unreliable tools)
    try:
        demoted = get_demoted_tools()
        # Don't remove demoted tools — just flag them. The checkpoint
        # system handles approval. But log it for awareness.
        if demoted & toolset:
            logger.info(f"[TOOL_GATE] Demoted tools in active set: {demoted & toolset}")
    except Exception:
        pass

    # In local-only mode, don't expose network-search tools unless the
    # classified intent explicitly asked for them. This keeps local recall
    # and file workflows from opportunistically drifting onto the web.
    if _is_local_only_mode() and intent_type not in _EXPLICIT_NETWORK_INTENTS:
        toolset.discard("web_search")
        if intent_type not in {"url_fetch", "service_action"}:
            toolset.discard("fetch_url")

    return toolset


def filter_orchestrator_tools(
    full_tool_block: str,
    allowed_tools: Set[str],
) -> str:
    """Filter the orchestrator's tool description block to only show allowed tools.

    Takes the ORCHESTRATOR_SYSTEM prompt's tool list section and removes
    lines for tools not in allowed_tools.

    Args:
        full_tool_block: The "Available actions:" section from ORCHESTRATOR_SYSTEM
        allowed_tools: Set of tool names to keep

    Returns:
        Filtered tool block with only allowed tool lines
    """
    lines = full_tool_block.split("\n")
    filtered = []
    for line in lines:
        # Tool lines look like: - {"action": "tool_call", "tool": "file_read", ...
        if '"tool_call"' in line and '"tool":' in line:
            # Extract tool name
            import re
            match = re.search(r'"tool":\s*"(\w+)"', line)
            if match:
                tool_name = match.group(1)
                if tool_name in allowed_tools:
                    filtered.append(line)
                # else: tool not allowed, skip this line
            else:
                filtered.append(line)  # couldn't parse, keep it
        else:
            filtered.append(line)  # non-tool line (think, respond, ask_user, etc.)
    return "\n".join(filtered)


def get_agent_loop_filter(intent_type: str, route: Optional[str] = None) -> Optional[List[str]]:
    """Get the tool_filter list for the agent tool loop.

    Returns None if all tools should be available (backwards compat),
    or a list of tool names to include.
    """
    allowed = get_tools_for_intent(intent_type, route)
    if allowed >= ALL_TOOLS:
        return None  # no filtering needed
    return list(allowed)
