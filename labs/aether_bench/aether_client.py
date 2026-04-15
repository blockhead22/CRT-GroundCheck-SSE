"""Minimal Aether HTTP client for the Warm arm of aether_bench.

The harness exposes a small subset of Aether's capabilities to the LLM as
OpenAI-style tool schemas. When the brain invokes a tool, the harness calls
the corresponding method here and feeds the result back into the chat loop.

Keep this file small. It is NOT a full Aether SDK — it is the minimum
needed to prove Claim 1 (Warm helps) and Claim 3 (persistence across
brain swaps). Add tools only if a task demonstrably needs them.

Env:
    AETHER_BASE_URL     default http://127.0.0.1:8000
    AETHER_THREAD_ID    default 'aether_bench'
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = os.environ.get("AETHER_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
THREAD_ID = os.environ.get("AETHER_THREAD_ID", "aether_bench")
TIMEOUT = float(os.environ.get("AETHER_TIMEOUT_S", "20"))


def _req(method: str, path: str, *, params: dict | None = None,
         body: dict | None = None) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")
    except HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Aether HTTP {e.code} on {method} {path}: {body_txt}") from e
    except URLError as e:
        raise RuntimeError(f"Aether unreachable at {BASE_URL}: {e.reason}") from e


# --- Operations exposed to the brain ---------------------------------------

def search(query: str, k: int = 5, min_trust: float = 0.0) -> list[dict]:
    """Recall memories matching query. Returns trimmed dicts."""
    rows = _req("GET", "/api/memory/search",
                params={"thread_id": THREAD_ID, "q": query,
                        "k": k, "min_trust": min_trust}) or []
    return [{
        "text": r.get("text"),
        "trust": r.get("trust"),
        "kind": r.get("kind"),
        "timestamp": r.get("timestamp"),
    } for r in rows]


def store(text: str, confidence: float = 0.75, kind: str = "observation") -> dict:
    """Persist a fact to Aether. Source='mcp_client' (already in MemorySource enum)."""
    return _req("POST", "/api/memory/store", body={
        "text": text,
        "thread_id": THREAD_ID,
        "confidence": confidence,
        "kind": kind,
        "source": "mcp_client",
    }) or {}


# --- OpenAI tool schemas ---------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "aether_search",
            "description": "Recall persisted facts from the Aether belief substrate. "
                           "Use BEFORE answering any question where prior context, "
                           "user preferences, or earlier-session facts may matter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "natural-language search"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aether_remember",
            "description": "Persist a fact or user preference to the Aether belief "
                           "substrate so it survives across sessions and brain swaps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": ["observation", "preference", "fact"]},
                },
                "required": ["text"],
            },
        },
    },
]


def execute(name: str, args: dict) -> dict:
    """Dispatch a tool call from the brain. Returns a JSON-safe dict.
    Errors are returned as {"error": ...} rather than raised, so the LLM
    loop can continue gracefully."""
    t0 = time.perf_counter()
    try:
        if name == "aether_search":
            result = {"hits": search(query=args["query"], k=int(args.get("k", 5)))}
        elif name == "aether_remember":
            result = store(text=args["text"], kind=args.get("kind", "observation"))
        else:
            result = {"error": f"unknown tool: {name}"}
    except Exception as e:
        result = {"error": str(e)}
    result["_latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


def ping() -> bool:
    """Cheap reachability check — used at harness startup in Warm arm."""
    try:
        _req("GET", "/api/memory/search",
             params={"thread_id": THREAD_ID, "q": "ping", "k": 1})
        return True
    except Exception:
        return False
