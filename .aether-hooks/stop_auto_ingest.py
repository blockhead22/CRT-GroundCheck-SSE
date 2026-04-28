#!/usr/bin/env python3
"""Stop hook: extract high-signal facts from the last turn into Aether.

Standalone copy of the plugin's auto_ingest_hook.py — wired at the
project level so this works whether or not the Claude Code plugin is
installed/enabled.

Reads the Stop-event JSON payload on stdin, pulls user_message and
assistant_response from the transcript, then calls
`aether.memory.ingest_turn` against the local substrate. Writes are
deduped against the substrate before commit.

Never fails the hook chain — all errors are logged to stderr and
the script exits 0.
"""

from __future__ import annotations
import json
import sys
import traceback


def _read_stdin_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


def _last_message(payload: dict, *roles: str) -> str:
    """Pull the most recent message of any role in `roles`."""
    for key in ("messages", "transcript", "history"):
        seq = payload.get(key)
        if isinstance(seq, list):
            for entry in reversed(seq):
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role") or entry.get("type")
                if role in roles:
                    content = entry.get("content") or entry.get("text") or ""
                    if isinstance(content, list):
                        content = " ".join(
                            seg.get("text", "") if isinstance(seg, dict) else str(seg)
                            for seg in content
                        )
                    if content:
                        return str(content)
    # Direct fallback fields
    if "user" in roles and isinstance(payload.get("last_user_message"), str):
        return payload["last_user_message"]
    if "assistant" in roles and isinstance(payload.get("last_assistant_message"), str):
        return payload["last_assistant_message"]
    return ""


def main() -> int:
    payload = _read_stdin_payload()
    user_msg = _last_message(payload, "user", "human")
    asst_msg = _last_message(payload, "assistant", "claude", "ai")

    if not user_msg and not asst_msg:
        return 0

    try:
        from aether.mcp.state import StateStore
        from aether.memory import ingest_turn
    except ImportError:
        # aether-core not installed — silent skip.
        return 0

    try:
        store = StateStore()
        writes = ingest_turn(
            store,
            user_message=user_msg or None,
            assistant_response=asst_msg or None,
        )
        if writes:
            print(f"[aether auto-ingest] wrote {len(writes)} fact(s)",
                  file=sys.stderr)
            for w in writes:
                print(f"  - ({w.get('signal')}) trust={w['trust']:.2f} "
                      f"-> {w['memory_id']}",
                      file=sys.stderr)
    except Exception:
        print("[aether auto-ingest] error (suppressed):", file=sys.stderr)
        traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main())
