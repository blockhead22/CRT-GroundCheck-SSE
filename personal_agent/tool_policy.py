"""Agent tool policy engine.

OpenClaw-style guardrails for autonomous tool execution:
- per-tool enable/disable
- per-tool approval requirements
- per-tool call quotas per run
- channel/user allow and deny lists
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


def _norm_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _norm_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    for value in values:
        token = _norm_token(value)
        if token:
            out.append(token)
    return out


@dataclass(frozen=True)
class ToolExecutionContext:
    """Runtime identity context for policy evaluation."""

    thread_id: str = "default"
    channel: str = "api"
    actor_id: Optional[str] = None
    approved_tools: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ToolPolicyDecision:
    """Policy decision for a single tool invocation."""

    allowed: bool
    reason: str
    requires_approval: bool = False


class AgentToolPolicy:
    """Deterministic policy evaluator for agent tool calls."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "enabled": True,
        "default_allow": True,
        "global_max_calls_per_run": 24,
        "tools": {},
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = self.normalize_config(config or {})

    @classmethod
    def normalize_config(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("agent tool policy config must be an object")

        merged: Dict[str, Any] = dict(cls.DEFAULT_CONFIG)
        merged.update(raw)

        tools_raw = merged.get("tools")
        if tools_raw is None:
            tools_raw = {}
        if not isinstance(tools_raw, dict):
            raise ValueError("agent tool policy 'tools' must be an object")

        tools_out: Dict[str, Dict[str, Any]] = {}
        for tool_name, rule_raw in tools_raw.items():
            name = _norm_token(tool_name)
            if not name:
                continue
            if rule_raw is None:
                rule_raw = {}
            if not isinstance(rule_raw, dict):
                raise ValueError(f"tool policy for '{name}' must be an object")

            max_calls = rule_raw.get("max_calls_per_run")
            if max_calls is not None:
                try:
                    max_calls = int(max_calls)
                except Exception as e:
                    raise ValueError(
                        f"tool policy '{name}'.max_calls_per_run must be an integer"
                    ) from e
                if max_calls < 1:
                    raise ValueError(
                        f"tool policy '{name}'.max_calls_per_run must be >= 1"
                    )

            tools_out[name] = {
                "enabled": bool(rule_raw.get("enabled", True)),
                "require_approval": bool(rule_raw.get("require_approval", False)),
                "max_calls_per_run": max_calls,
                "allowed_channels": _norm_list(rule_raw.get("allowed_channels")),
                "denied_channels": _norm_list(rule_raw.get("denied_channels")),
                "allowed_users": _norm_list(rule_raw.get("allowed_users")),
                "denied_users": _norm_list(rule_raw.get("denied_users")),
            }

        global_max = merged.get("global_max_calls_per_run", 24)
        try:
            global_max = int(global_max)
        except Exception as e:
            raise ValueError("global_max_calls_per_run must be an integer") from e
        if global_max < 1:
            raise ValueError("global_max_calls_per_run must be >= 1")

        return {
            "enabled": bool(merged.get("enabled", True)),
            "default_allow": bool(merged.get("default_allow", True)),
            "global_max_calls_per_run": global_max,
            "tools": tools_out,
        }

    @classmethod
    def from_runtime_config(cls, runtime_cfg: Optional[Dict[str, Any]]) -> "AgentToolPolicy":
        base = runtime_cfg or {}
        section = base.get("agent_tool_policy") if isinstance(base, dict) else {}
        if not isinstance(section, dict):
            section = {}
        return cls(section)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.config)

    def evaluate(
        self,
        *,
        tool_name: str,
        context: Optional[ToolExecutionContext],
        usage_counts: Dict[str, int],
    ) -> ToolPolicyDecision:
        if not self.config.get("enabled", True):
            return ToolPolicyDecision(allowed=True, reason="policy_disabled")

        tool = _norm_token(tool_name)
        if not tool:
            return ToolPolicyDecision(allowed=False, reason="invalid_tool")

        rule = (self.config.get("tools") or {}).get(tool)
        if rule is None:
            if self.config.get("default_allow", True):
                rule = {
                    "enabled": True,
                    "require_approval": False,
                    "max_calls_per_run": None,
                    "allowed_channels": [],
                    "denied_channels": [],
                    "allowed_users": [],
                    "denied_users": [],
                }
            else:
                return ToolPolicyDecision(allowed=False, reason="tool_not_allowlisted")

        total_calls = 0
        for _, count in (usage_counts or {}).items():
            try:
                total_calls += int(count)
            except Exception:
                continue
        if total_calls >= int(self.config.get("global_max_calls_per_run", 24)):
            return ToolPolicyDecision(allowed=False, reason="global_quota_exceeded")

        if not bool(rule.get("enabled", True)):
            return ToolPolicyDecision(allowed=False, reason="tool_disabled")

        channel = _norm_token(getattr(context, "channel", "") if context else "")
        allowed_channels = _norm_list(rule.get("allowed_channels"))
        denied_channels = _norm_list(rule.get("denied_channels"))
        if channel in denied_channels:
            return ToolPolicyDecision(allowed=False, reason="channel_denied")
        if allowed_channels and channel not in allowed_channels:
            return ToolPolicyDecision(allowed=False, reason="channel_not_allowed")

        actor = _norm_token(getattr(context, "actor_id", "") if context else "")
        allowed_users = _norm_list(rule.get("allowed_users"))
        denied_users = _norm_list(rule.get("denied_users"))
        if actor and actor in denied_users:
            return ToolPolicyDecision(allowed=False, reason="actor_denied")
        if allowed_users and actor not in allowed_users:
            return ToolPolicyDecision(allowed=False, reason="actor_not_allowed")

        max_calls = rule.get("max_calls_per_run")
        if max_calls is not None:
            current = int((usage_counts or {}).get(tool, 0) or 0)
            if current >= int(max_calls):
                return ToolPolicyDecision(allowed=False, reason="quota_exceeded")

        if bool(rule.get("require_approval", False)):
            approved_tools = set()
            if context and isinstance(context.approved_tools, set):
                approved_tools = {_norm_token(item) for item in context.approved_tools}
            if tool not in approved_tools:
                return ToolPolicyDecision(
                    allowed=False,
                    reason="approval_required",
                    requires_approval=True,
                )

        return ToolPolicyDecision(allowed=True, reason="allowed")
