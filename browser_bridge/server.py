from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _now() -> float:
    return time.time()


def _get_token() -> str:
    token = (os.environ.get("BROWSER_BRIDGE_TOKEN") or "").strip()
    if not token:
        # Safer than silently accepting unauthenticated connections.
        raise RuntimeError("BROWSER_BRIDGE_TOKEN is not set")
    return token


@dataclass
class ClientInfo:
    ws: WebSocketServerProtocol
    client_id: str
    connected_at: float
    tab: Dict[str, Any]


class BridgeServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = int(port)
        self._token = _get_token()
        self._clients: Dict[str, ClientInfo] = {}
        self._pending: Dict[str, asyncio.Future] = {}

    def _new_id(self) -> str:
        return secrets.token_hex(8)

    async def _handle(self, ws: WebSocketServerProtocol):
        client_id = self._new_id()
        authed = False
        tab: Dict[str, Any] = {}

        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                mtype = (msg.get("type") or "").strip()

                if not authed:
                    if mtype != "hello":
                        await ws.send(json.dumps({"type": "error", "error": "unauthenticated"}))
                        continue
                    if (msg.get("token") or "").strip() != self._token:
                        await ws.send(json.dumps({"type": "error", "error": "bad_token"}))
                        await ws.close()
                        return
                    tab = msg.get("tab") or {}
                    authed = True
                    self._clients[client_id] = ClientInfo(ws=ws, client_id=client_id, connected_at=_now(), tab=tab)
                    await ws.send(json.dumps({"type": "hello_ack", "client_id": client_id}))
                    continue

                if mtype == "event":
                    # Best-effort: log to stdout.
                    name = msg.get("name")
                    data = msg.get("data")
                    print(f"[event] client={client_id} name={name} data={data}")
                    continue

                if mtype == "result":
                    cmd_id = (msg.get("id") or "").strip()
                    fut = self._pending.pop(cmd_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue

        finally:
            self._clients.pop(client_id, None)

    def list_clients(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for cid, info in self._clients.items():
            out[cid] = {
                "connected_at": info.connected_at,
                "tab": info.tab,
            }
        return out

    async def send_command(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        client_id: Optional[str] = None,
        timeout_s: float = 20.0,
    ) -> Dict[str, Any]:
        args = args or {}
        cmd_id = self._new_id()

        target: Optional[ClientInfo] = None
        if client_id:
            target = self._clients.get(client_id)
        else:
            # Default: pick the most recently connected client.
            if self._clients:
                target = sorted(self._clients.values(), key=lambda c: c.connected_at)[-1]

        if not target:
            raise RuntimeError("No connected browser clients")

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[cmd_id] = fut

        await target.ws.send(
            json.dumps({"type": "command", "id": cmd_id, "name": name, "args": args})
        )

        try:
            msg = await asyncio.wait_for(fut, timeout=timeout_s)
        finally:
            self._pending.pop(cmd_id, None)

        return msg

    async def run(self):
        async with websockets.serve(self._handle, self.host, self.port, max_size=2_000_000):
            print(f"Browser bridge listening on ws://{self.host}:{self.port}")
            print("Waiting for Tampermonkey client(s)...")
            await asyncio.Future()  # run forever


def main():
    server = BridgeServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
