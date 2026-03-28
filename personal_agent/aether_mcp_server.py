"""Aether MCP Server — exposes CRT belief state, memories, contradictions,
and context to external AI tools (Claude Code, Cursor, etc.).

Each tool is a thin HTTP wrapper calling the Aether backend at
http://127.0.0.1:8000/api/... so no logic is duplicated.

Registration for Claude Code (~/.claude/settings.json or .claude/settings.json):
    {
        "mcpServers": {
            "aether": {
                "command": "python",
                "args": ["-m", "personal_agent.aether_mcp_server"],
                "cwd": "D:/AI_round2"
            }
        }
    }
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, Optional

import httpx
from mcp.server import FastMCP

logger = logging.getLogger("aether-mcp")

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 30.0

mcp = FastMCP(
    "aether",
    instructions=(
        "Aether provides full access to a personal AI's belief state, memories, "
        "contradictions, and context. Use aether_search to find memories, "
        "aether_profile for user info, aether_contradictions for open conflicts, "
        "aether_context for a dashboard overview. Write tools (aether_remember, "
        "aether_correct, aether_resolve) modify the belief state. "
        "aether_ask sends a question to Aether for a full response."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET request to the Aether backend. Returns parsed JSON or error dict."""
    try:
        r = httpx.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "Aether backend not reachable at " + BASE_URL}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """POST request to the Aether backend. Returns parsed JSON or error dict."""
    try:
        r = httpx.post(f"{BASE_URL}{path}", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "Aether backend not reachable at " + BASE_URL}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def _fmt(data: Any) -> str:
    """Format response data as readable text."""
    if isinstance(data, dict) and "error" in data:
        return f"ERROR: {data['error']}"
    return json.dumps(data, indent=2, default=str)


# ===========================================================================
# Tier 1: Read
# ===========================================================================

@mcp.tool()
def aether_search(query: str, limit: int = 5) -> str:
    """Semantic search across Aether's memory bank.

    Returns memories ranked by relevance with text, trust score, timestamp,
    and kind (observation, preference, fact, etc.).

    Args:
        query: Natural-language search query.
        limit: Max results to return (default 5).
    """
    data = _get("/api/memory/search", {"q": query, "limit": limit, "thread_id": "default"})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    if isinstance(data, list):
        lines = [f"Found {len(data)} memories:\n"]
        for i, m in enumerate(data, 1):
            lines.append(
                f"{i}. [{m.get('kind', '?')}] {m.get('text', '')}\n"
                f"   trust={m.get('trust', '?')}  id={m.get('id', '?')}  "
                f"ts={m.get('timestamp', '?')}"
            )
        return "\n".join(lines)
    return _fmt(data)


@mcp.tool()
def aether_profile() -> str:
    """Get the user profile snapshot — name, known facts, preferences.

    Call this at the start of a session to personalize your responses.
    """
    data = _get("/api/profile", {"thread_id": "default"})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    parts = []
    if data.get("name"):
        parts.append(f"Name: {data['name']}")
    if data.get("facts"):
        parts.append("Facts:")
        for f in data["facts"]:
            parts.append(f"  - {f}")
    if data.get("preferences"):
        parts.append("Preferences:")
        for p in data["preferences"]:
            parts.append(f"  - {p}")
    return "\n".join(parts) if parts else _fmt(data)


@mcp.tool()
def aether_contradictions(limit: int = 5) -> str:
    """List open contradictions in Aether's belief state.

    Returns conflicting memory pairs with their trust scores and slots.
    Use aether_resolve to close a contradiction.

    Args:
        limit: Max contradictions to return (default 5).
    """
    data = _get("/api/contradictions/work-items", {"limit": limit})
    if isinstance(data, dict) and "error" in data:
        # Fallback to ledger/open
        data = _get("/api/ledger/open", {"limit": limit})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    if isinstance(data, list):
        if not data:
            return "No open contradictions."
        lines = [f"{len(data)} open contradiction(s):\n"]
        for i, c in enumerate(data, 1):
            lines.append(
                f"{i}. slot={c.get('slot', '?')}  "
                f"ledger_id={c.get('ledger_id', '?')}\n"
                f"   values: {c.get('values', c.get('memory_texts', '?'))}\n"
                f"   trusts: {c.get('trusts', '?')}"
            )
        return "\n".join(lines)
    return _fmt(data)


@mcp.tool()
def aether_context(thread_id: str = "default") -> str:
    """Dashboard overview — memory count, contradiction count, recent activity.

    Gives a quick snapshot of the current state of Aether's belief system.

    Args:
        thread_id: Conversation thread (default "default").
    """
    data = _get("/api/dashboard/overview", {"thread_id": thread_id})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    parts = []
    for key, val in data.items():
        parts.append(f"{key}: {val}")
    return "\n".join(parts) if parts else _fmt(data)


# ===========================================================================
# Tier 2: Analyze
# ===========================================================================

@mcp.tool()
def aether_belief_history(slot: str) -> str:
    """Show how a belief (fact slot) evolved over time.

    Returns a timeline of values with trust changes, useful for
    understanding why Aether believes what it believes.

    Args:
        slot: The fact slot name (e.g. "user.name", "user.job").
    """
    data = _get(f"/api/facts/history/{slot}")
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    if isinstance(data, list):
        if not data:
            return f"No history found for slot '{slot}'."
        lines = [f"Belief history for '{slot}' ({len(data)} entries):\n"]
        for entry in data:
            lines.append(
                f"  {entry.get('timestamp', '?')}: "
                f"{entry.get('value', entry.get('text', '?'))} "
                f"(trust={entry.get('trust', '?')})"
            )
        return "\n".join(lines)
    return _fmt(data)


@mcp.tool()
def aether_memory_detail(memory_id: str) -> str:
    """Deep dive on a single memory — full text, provenance, trust, volatility.

    Args:
        memory_id: The memory UUID to inspect.
    """
    data = _get(f"/api/memory/{memory_id}")
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    parts = []
    parts.append(f"Memory: {data.get('id', memory_id)}")
    parts.append(f"Text: {data.get('text', '?')}")
    parts.append(f"Trust: {data.get('trust', '?')}")
    parts.append(f"Kind: {data.get('kind', '?')}")
    parts.append(f"Source: {data.get('source', '?')}")
    parts.append(f"Timestamp: {data.get('timestamp', '?')}")
    if data.get("volatility") is not None:
        parts.append(f"Volatility: {data['volatility']}")
    return "\n".join(parts)


@mcp.tool()
def aether_volatile(limit: int = 10) -> str:
    """List high-risk memories sorted by volatility / contradiction risk.

    These are memories most likely to flip or be contradicted.

    Args:
        limit: Max results (default 10).
    """
    data = _get("/api/volatile-memories", {"limit": limit})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    if isinstance(data, list):
        if not data:
            return "No volatile memories found."
        lines = [f"{len(data)} volatile memories:\n"]
        for i, m in enumerate(data, 1):
            lines.append(
                f"{i}. {m.get('text', '?')}\n"
                f"   trust={m.get('trust', '?')}  "
                f"volatility={m.get('volatility', '?')}  "
                f"id={m.get('id', '?')}"
            )
        return "\n".join(lines)
    return _fmt(data)


# ===========================================================================
# Tier 3: Write
# ===========================================================================

@mcp.tool()
def aether_remember(text: str, kind: str = "observation", confidence: float = 0.7) -> str:
    """Store a new memory in Aether's belief state.

    Args:
        text: The memory text to persist.
        kind: Memory kind — observation, preference, fact, correction (default "observation").
        confidence: Initial confidence 0.0-1.0 (default 0.7).
    """
    data = _post("/api/memory/store", {
        "text": text,
        "source": "mcp_client",
        "confidence": confidence,
        "thread_id": "default",
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    return (
        f"Stored memory.\n"
        f"  id: {data.get('id', data.get('memory_id', '?'))}\n"
        f"  trust: {data.get('trust', '?')}"
    )


@mcp.tool()
def aether_correct(memory_id: str, new_text: str) -> str:
    """Correct an existing memory's text.

    This triggers CRT drift-aware trust evolution and fact reclassification.

    Args:
        memory_id: ID of the memory to correct.
        new_text: The corrected text.
    """
    data = _post("/api/copilot/correct", {
        "memory_id": memory_id,
        "corrected_text": new_text,
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    return f"Memory corrected.\n{_fmt(data)}"


@mcp.tool()
def aether_resolve(ledger_id: str, method: str = "user_clarified", new_status: str = "resolved") -> str:
    """Resolve an open contradiction.

    Args:
        ledger_id: The contradiction ledger ID (from aether_contradictions).
        method: Resolution method — user_clarified, accept_both, reflection_merge (default "user_clarified").
        new_status: Target status (default "resolved").
    """
    data = _post("/api/ledger/resolve", {
        "ledger_id": ledger_id,
        "method": method,
        "new_status": new_status,
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    return f"Contradiction resolved.\n{_fmt(data)}"


# ===========================================================================
# Tier 4: Act
# ===========================================================================

@mcp.tool()
def aether_ingest(file_path: str, thread_id: str = "default") -> str:
    """Ingest a document file into Aether's memory.

    Chunks the file and stores each chunk as a memory. Supports text,
    markdown, PDF, and other common formats.

    Args:
        file_path: Absolute path to the file to ingest.
        thread_id: Thread context (default "default").
    """
    data = _post("/api/ingest/file", {
        "file_path": file_path,
        "thread_id": thread_id,
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    return (
        f"Ingested: {data.get('filename', '?')}\n"
        f"  chars: {data.get('chars_ingested', '?')}\n"
        f"  chunks: {data.get('chunks_stored', data.get('chunk_count', '?'))}\n"
        f"  success: {data.get('success', '?')}"
    )


@mcp.tool()
def aether_ask(message: str, thread_id: str = "default") -> str:
    """Ask Aether a question and get a full response (non-streaming).

    This sends a message through Aether's full pipeline — memory retrieval,
    contradiction checking, belief-grounded reasoning — and returns the
    response text.

    Args:
        message: The question or message to send.
        thread_id: Conversation thread (default "default").
    """
    data = _post("/api/chat/send", {
        "message": message,
        "thread_id": thread_id,
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    # Extract the response text from the chat response
    response_text = data.get("response", data.get("text", data.get("reply", "")))
    if response_text:
        return response_text
    return _fmt(data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the Aether MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Aether MCP Server")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    logger.info("Aether MCP server starting")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
