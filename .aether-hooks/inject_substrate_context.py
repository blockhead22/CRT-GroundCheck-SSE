#!/usr/bin/env python3
"""UserPromptSubmit hook: search the Aether substrate for the user's
prompt and inject relevant memories as additional context.

This is the read-side counterpart to stop_auto_ingest.py. Together
they put the substrate on both sides of the loop:

    user prompt -> [search substrate, inject matches] -> Claude
    Claude reply -> [extract facts, write to substrate] -> ...

Without this hook, the substrate is *available* to Claude (via MCP
tools) but not *used* automatically — Claude would have to remember
to call `aether_search` itself before answering. With this hook,
relevant memories land in every prompt regardless of Claude's choice.

Wire in `.claude/settings.local.json`:

    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python D:/AI_round2/.aether-hooks/inject_substrate_context.py",
            "timeout": 5
          }
        ]
      }
    ]

Output protocol (Claude Code):
    JSON to stdout with shape
        {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                "additionalContext": "..."}}
    The additionalContext string gets prepended to the user prompt.

Defensive:
- Never blocks the user prompt. Errors -> empty context, exit 0.
- Outputs nothing (empty additionalContext) when no relevant memories
  are found. Avoids cluttering the prompt with noise.
- Hard timeout of 5s in settings.json — if substrate is unhealthy,
  Claude Code skips the hook and the user keeps moving.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path


_DEBUG_LOG = Path.home() / ".aether" / "user_prompt_inject.log"


def _debug(line: str) -> None:
    """Append-only audit log: one line per hook fire so the user can
    verify the read-side hook is in the loop."""
    try:
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {line}\n")
    except Exception:
        pass


def _emit(additional_context: str) -> None:
    """Print the Claude Code hook protocol response to stdout."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
    print(json.dumps(payload))


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _debug("BAD_JSON_PAYLOAD")
        _emit("")
        return 0

    prompt = (
        payload.get("prompt")
        or payload.get("user_prompt")
        or payload.get("user_message")
        or ""
    )
    if not isinstance(prompt, str) or len(prompt.strip()) < 3:
        _debug(f"SKIP  prompt_len={len(prompt) if isinstance(prompt, str) else 0}")
        _emit("")
        return 0

    try:
        from aether.mcp.state import StateStore
    except ImportError:
        _debug("AETHER_NOT_INSTALLED")
        _emit("")
        return 0

    try:
        store = StateStore()
        results = store.search(prompt, limit=5)
    except Exception as e:
        _debug(f"SEARCH_ERROR  {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stderr)
        _emit("")
        return 0

    # Filter out low-confidence noise. Score threshold matches
    # GROUNDING_MIN_SCORE so we surface what compute_grounding would have
    # used. F#9(b): also drop fully-demoted entries (trust <= 0) so
    # corrected-away memories don't leak back into the prompt.
    relevant = [
        r for r in results
        if r.get("score", 0) >= 0.15 and r.get("trust", 0) > 0.0
    ]
    _debug(
        f"FIRE  prompt_len={len(prompt)}  candidates={len(results)}  "
        f"relevant={len(relevant)}"
    )

    if not relevant:
        _emit("")
        return 0

    # Format. Keep it terse and bracketed so Claude can both spot and ignore
    # the section if irrelevant. Trust + source signal authority; the
    # contradicting flag (when present in future) signals "treat with care."
    lines = [
        "<aether_substrate>",
        "The following memories from your belief substrate match this prompt. "
        "Treat as prior context — high-trust facts you previously stored. "
        "If a memory contradicts the user's framing, surface that.",
    ]
    for r in relevant[:3]:
        text = (r.get("text") or "").strip()
        if len(text) > 400:
            text = text[:397] + "..."
        trust = r.get("trust", 0.0)
        source = r.get("source") or "unknown"
        mid = r.get("memory_id", "")
        lines.append(
            f"- [trust={trust:.2f}, source={source}, id={mid}] {text}"
        )
    lines.append("</aether_substrate>")

    additional_context = "\n".join(lines)
    _debug(f"INJECT  {len(additional_context)} chars, {len(relevant[:3])} memories")
    _emit(additional_context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
