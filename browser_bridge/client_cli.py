from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict

import websockets


DEFAULT_URL = "ws://127.0.0.1:8765"


def _token() -> str:
    t = (os.environ.get("BROWSER_BRIDGE_TOKEN") or "").strip()
    if not t:
        raise RuntimeError("BROWSER_BRIDGE_TOKEN is not set")
    return t


async def _run_command(command: str, args: Dict[str, Any]) -> None:
    url = (os.environ.get("BROWSER_BRIDGE_URL") or DEFAULT_URL).strip()

    async with websockets.connect(url, max_size=2_000_000) as ws:
        await ws.send(json.dumps({"type": "hello", "token": _token(), "tab": {"title": "cli", "url": "cli"}}))
        # Wait for ack
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("type") == "hello_ack":
                break

        await ws.send(json.dumps({"type": "command", "id": "cli", "name": command, "args": args}))

        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("type") == "result" and msg.get("id") == "cli":
                print(json.dumps(msg, indent=2))
                return


def main() -> None:
    ap = argparse.ArgumentParser(description="Browser bridge CLI")
    ap.add_argument(
        "command",
        choices=["get-page-text", "get-selection", "query-text"],
        help="Command to send to the connected browser client",
    )
    ap.add_argument("--selector", type=str, default="", help="CSS selector for query-text")
    ap.add_argument("--timeout", type=float, default=20.0, help="Timeout (best-effort)")
    args = ap.parse_args()

    cmd_map = {
        "get-page-text": "get_page_text",
        "get-selection": "get_selection",
        "query-text": "query_selector_text",
    }

    payload: Dict[str, Any] = {}
    if args.command == "query-text":
        payload["selector"] = args.selector

    asyncio.run(_run_command(cmd_map[args.command], payload))


if __name__ == "__main__":
    main()
