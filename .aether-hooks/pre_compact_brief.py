#!/usr/bin/env python3
"""PreCompact hook: inject substrate snapshot into the new context.

When Claude Code is about to compact the conversation, fetch the
current substrate state + a 24h diff and surface it as additional
context. The post-compact session starts knowing what's in the
substrate, what changed recently, and where state lives — so it
doesn't have to re-discover it.

Outputs JSON with `hookSpecificOutput.additionalContext` field per the
Claude Code hook contract. Silent failure produces an empty hook output
and never blocks compaction.
"""

from __future__ import annotations
import json
import sys
import time
import traceback


def _build_context() -> str:
    from aether.mcp.state import StateStore
    store = StateStore()
    stats = store.stats()
    # Diff the last 24h so the model sees what changed during the
    # session it's about to compact away.
    diff = store.session_diff(time.time() - 86400)
    summary = diff.get("summary", {})

    lines = [
        "[Aether substrate brief — context surfaced before compaction]",
        f"Substrate path: {stats['state_path']}",
        f"Memories: {stats['memory_count']} | Edges: {stats['edge_count']}",
    ]
    belnap = stats.get("belnap_states", {})
    if belnap:
        bits = ", ".join(f"{k}={v}" for k, v in belnap.items())
        lines.append(f"Belnap states: {bits}")
    held = stats.get("held_contradictions", 0)
    evolving = stats.get("evolving_contradictions", 0)
    if held or evolving:
        lines.append(f"Open contradictions: {held} held, {evolving} evolving")
    lines.append(
        f"Last 24h: +{summary.get('memories_added', 0)} memories, "
        f"{summary.get('contradictions_added', 0)} new contradictions, "
        f"{summary.get('trust_changes', 0)} trust changes"
    )

    # Surface a few recent memory texts if any
    new_mems = diff.get("new_memories") or []
    if new_mems:
        lines.append("")
        lines.append("Recent memories (most recent first):")
        for m in sorted(new_mems, key=lambda x: -x.get("created_at", 0))[:5]:
            lines.append(f"  - [{m['memory_id']}] (trust {m['trust']:.2f}) "
                         f"{m['text'][:160]}")

    return "\n".join(lines)


def main() -> int:
    try:
        ctx = _build_context()
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreCompact",
                "additionalContext": ctx,
            },
        }))
    except ImportError:
        # aether-core not installed — return empty hook output, don't block.
        print(json.dumps({}))
    except Exception:
        print(json.dumps({}))
        traceback.print_exc(file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
