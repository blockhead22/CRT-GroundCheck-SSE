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

# In-memory registry for async dispatches (lives for the server process lifetime)
_ACTIVE_DISPATCHES: Dict[str, Dict] = {}

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


@mcp.tool()
def aether_opinion_variance(topic_query: str = "", min_entries: int = 3) -> str:
    """Show how Aether's responses on the same topic drift over time.

    Returns per-topic variance metrics: response drift, belief flip rate,
    opinion convergence, and belief stability. Use this to understand how
    consistent Aether's beliefs and opinions are.

    Args:
        topic_query: Optional filter — show topics matching this text.
        min_entries: Minimum entries for a topic to be shown (default 3).
    """
    data = _get("/api/variance/topics", {"min_entries": min_entries})
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    topics = data.get("topics", [])
    if topic_query:
        topics = [t for t in topics if topic_query.lower() in (t.get("label") or "").lower()]
    if not topics:
        return "No topics with enough entries found. Keep chatting and run /api/variance/analyze to cluster."
    lines = [f"{len(topics)} topic(s):\n"]
    for t in topics:
        m = t.get("metrics") or {}
        lines.append(
            f"  [{t.get('topic_id')}] \"{t.get('label', '?')}\" "
            f"({t.get('entry_count', 0)} entries)\n"
            f"    drift={m.get('mean_drift', '?'):.3f}  "
            f"flip_rate={m.get('belief_flip_rate', '?'):.2f}  "
            f"stability={m.get('belief_stability', '?'):.2f}  "
            f"convergence={m.get('convergence_direction', '?')}"
        )
    snapshot = data.get("snapshot")
    if snapshot:
        lines.append(f"\nGlobal: {snapshot.get('num_topics', 0)} topics, "
                      f"avg_drift={snapshot.get('avg_drift', 0):.3f}, "
                      f"avg_stability={snapshot.get('avg_belief_stability', 0):.2f}")
    return "\n".join(lines)


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


# ===========================================================================
# Tier 5: Agent Dispatch & Metrics
# ===========================================================================

@mcp.tool()
def aether_dispatch(
    task: str,
    project_path: str = ".",
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    scope_files: str = "",
) -> str:
    """Dispatch a coding task to Claude Code and capture full execution metrics.

    Aether acts as the epistemic orchestrator — dispatching the task with
    project context, then capturing token usage, cost, and output for
    governance tracking.

    Args:
        task: The coding task to dispatch (e.g. "Add dark mode toggle to settings page").
        project_path: Path to the project root (default current directory).
        model: Claude model to use (default claude-sonnet-4-20250514).
        max_tokens: Max output tokens (default 4096).
        scope_files: Comma-separated file paths to scope the task (optional).
    """
    import subprocess
    import time
    import os

    # Resolve Claude CLI binary
    try:
        from personal_agent.cookie_orchestrator import ClaudeCliBrain
        cli_bin = ClaudeCliBrain._resolve_bin()
    except Exception:
        cli_bin = "claude"

    # Build the prompt with context
    prompt_parts = [task]
    if scope_files:
        prompt_parts.append(f"\nScope to these files: {scope_files}")

    # Fetch relevant context from Aether memory
    try:
        context = _get("/api/memory/search", {"q": task, "limit": 3, "thread_id": "default"})
        if isinstance(context, list) and context:
            context_lines = []
            for m in context:
                context_lines.append(f"- [{m.get('kind', '?')}] {m.get('text', '')[:100]}")
            prompt_parts.append(f"\nRelevant context from memory:\n" + "\n".join(context_lines))
    except Exception:
        pass

    full_prompt = "\n".join(prompt_parts)

    # Dispatch via Claude CLI with JSON output for metrics
    cmd = [
        cli_bin,
        "-p", full_prompt,
        "--model", model,
        "--output-format", "json",
    ]
    if project_path and project_path != ".":
        cmd.extend(["--cwd", project_path])

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=project_path if project_path != "." else None,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if proc.returncode != 0:
            error_text = (proc.stderr or proc.stdout or "unknown error").strip()[:500]
            # Log failed dispatch
            _post("/api/memory/store", {
                "text": f"[agent_dispatch:failed] task=\"{task[:60]}\" error=\"{error_text[:100]}\"",
                "source": "agent_dispatch",
                "confidence": 0.3,
                "thread_id": "default",
            })
            return f"Dispatch FAILED (exit {proc.returncode}):\n{error_text}"

        # Parse JSON response for metrics
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"result": proc.stdout.strip(), "usage": {}}

        content = result.get("result", proc.stdout.strip())
        session_id = result.get("session_id", "unknown")
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_tokens", 0)
        cache_create = usage.get("cache_creation_tokens", 0)

        # Estimate cost
        cost = 0.0
        try:
            from personal_agent.cloud_usage_logger import _estimate_cost
            cost = _estimate_cost(model, input_tokens, output_tokens)
        except Exception:
            pass

        # Track metrics in CRT
        metrics_text = (
            f"[agent_dispatch:success] task=\"{task[:60]}\" "
            f"model={model} tokens_in={input_tokens} tokens_out={output_tokens} "
            f"cache_read={cache_read} cost=${cost:.4f} elapsed={elapsed_ms:.0f}ms "
            f"session={session_id}"
        )
        _post("/api/memory/store", {
            "text": metrics_text,
            "source": "agent_dispatch",
            "confidence": 0.9,
            "thread_id": "default",
        })

        # Update cost accumulator
        try:
            from personal_agent.litellm_client import get_default_llm_client
            get_default_llm_client()._request_cost_usd += cost
        except Exception:
            pass

        # Build response
        lines = [
            f"✓ Dispatch complete ({elapsed_ms:.0f}ms)",
            f"  model: {model}",
            f"  tokens: {input_tokens} in / {output_tokens} out",
            f"  cache: {cache_read} read / {cache_create} create",
            f"  cost: ${cost:.4f}",
            f"  session: {session_id}",
            f"",
            f"--- Output ---",
            content[:3000],
        ]
        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return f"Dispatch TIMEOUT after {elapsed_ms:.0f}ms"
    except FileNotFoundError:
        return f"Claude CLI not found at '{cli_bin}'. Install Claude Code first."


@mcp.tool()
def aether_dispatch_async(
    task: str,
    project_path: str = ".",
    model: str = "claude-sonnet-4-20250514",
    scope_files: str = "",
) -> str:
    """Dispatch a coding task to Claude Code asynchronously with an await loop.

    Unlike aether_dispatch (synchronous), this:
    1. Starts the Claude Code task in a background subprocess
    2. Returns a dispatch_id immediately
    3. Use aether_dispatch_status(dispatch_id) to poll for completion
    4. When complete, metrics are captured and governance checks run

    This enables Aether to dispatch multiple agents and await their results,
    or continue other work while the agent executes.

    Args:
        task: The coding task to dispatch.
        project_path: Path to the project root (default current directory).
        model: Claude model to use (default claude-sonnet-4-20250514).
        scope_files: Comma-separated file paths to scope the task (optional).
    """
    import subprocess
    import time
    import uuid
    import threading

    # Resolve Claude CLI binary
    try:
        from personal_agent.cookie_orchestrator import ClaudeCliBrain
        cli_bin = ClaudeCliBrain._resolve_bin()
    except Exception:
        cli_bin = "claude"

    # Build prompt with context
    prompt_parts = [task]
    if scope_files:
        prompt_parts.append(f"\nScope to these files: {scope_files}")

    # Fetch relevant context from Aether memory
    try:
        context = _get("/api/memory/search", {"q": task, "limit": 3, "thread_id": "default"})
        if isinstance(context, list) and context:
            context_lines = [f"- [{m.get('kind', '?')}] {m.get('text', '')[:100]}" for m in context]
            prompt_parts.append(f"\nRelevant context from memory:\n" + "\n".join(context_lines))
    except Exception:
        pass

    full_prompt = "\n".join(prompt_parts)
    dispatch_id = str(uuid.uuid4())[:12]

    # Store dispatch record
    _ACTIVE_DISPATCHES[dispatch_id] = {
        "task": task,
        "model": model,
        "status": "running",
        "started_at": time.time(),
        "result": None,
        "metrics": None,
        "error": None,
    }

    # Launch in background thread
    def _run():
        t0 = time.perf_counter()
        try:
            cmd = [
                cli_bin, "-p", full_prompt,
                "--model", model,
                "--output-format", "json",
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,  # 5 min for async
                cwd=project_path if project_path != "." else None,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if proc.returncode != 0:
                _ACTIVE_DISPATCHES[dispatch_id]["status"] = "failed"
                _ACTIVE_DISPATCHES[dispatch_id]["error"] = (proc.stderr or proc.stdout or "")[:500]
                _ACTIVE_DISPATCHES[dispatch_id]["metrics"] = {"elapsed_ms": elapsed_ms}
                return

            # Parse JSON output
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError:
                result = {"result": proc.stdout.strip(), "usage": {}}

            usage = result.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            # Estimate cost
            cost = 0.0
            try:
                from personal_agent.cloud_usage_logger import _estimate_cost
                cost = _estimate_cost(model, input_tokens, output_tokens)
            except Exception:
                pass

            _ACTIVE_DISPATCHES[dispatch_id]["status"] = "complete"
            _ACTIVE_DISPATCHES[dispatch_id]["result"] = result.get("result", proc.stdout.strip())
            _ACTIVE_DISPATCHES[dispatch_id]["metrics"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read": usage.get("cache_read_tokens", 0),
                "cost": cost,
                "elapsed_ms": elapsed_ms,
                "session_id": result.get("session_id", "unknown"),
            }

            # Store in CRT memory
            _post("/api/memory/store", {
                "text": (
                    f"[agent_dispatch:success] task=\"{task[:60]}\" "
                    f"model={model} tokens_in={input_tokens} tokens_out={output_tokens} "
                    f"cost=${cost:.4f} elapsed={elapsed_ms:.0f}ms dispatch_id={dispatch_id}"
                ),
                "source": "agent_dispatch",
                "confidence": 0.9,
                "thread_id": "default",
            })

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _ACTIVE_DISPATCHES[dispatch_id]["status"] = "timeout"
            _ACTIVE_DISPATCHES[dispatch_id]["error"] = f"Timeout after {elapsed_ms:.0f}ms"
        except Exception as e:
            _ACTIVE_DISPATCHES[dispatch_id]["status"] = "error"
            _ACTIVE_DISPATCHES[dispatch_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"dispatch-{dispatch_id}")
    thread.start()

    return (
        f"✓ Dispatched async task (id: {dispatch_id})\n"
        f"  task: {task[:80]}\n"
        f"  model: {model}\n"
        f"  status: running\n\n"
        f"Poll with: aether_dispatch_status(\"{dispatch_id}\")"
    )


@mcp.tool()
def aether_dispatch_status(dispatch_id: str) -> str:
    """Check the status of an async dispatch.

    Returns current status (running/complete/failed/timeout) and metrics
    when complete. Call this to poll for results after aether_dispatch_async.

    Args:
        dispatch_id: The dispatch ID returned by aether_dispatch_async.
    """
    record = _ACTIVE_DISPATCHES.get(dispatch_id)
    if not record:
        return f"No dispatch found with id '{dispatch_id}'. Active dispatches: {list(_ACTIVE_DISPATCHES.keys())}"

    import time
    elapsed = time.time() - record["started_at"]
    status = record["status"]

    if status == "running":
        return (
            f"⏳ Still running ({elapsed:.0f}s elapsed)\n"
            f"  task: {record['task'][:80]}\n"
            f"  model: {record['model']}"
        )

    if status == "complete":
        m = record["metrics"] or {}
        result_preview = str(record.get("result") or "")[:2000]
        return (
            f"✓ Complete ({m.get('elapsed_ms', 0):.0f}ms)\n"
            f"  tokens: {m.get('input_tokens', 0)} in / {m.get('output_tokens', 0)} out\n"
            f"  cost: ${m.get('cost', 0):.4f}\n"
            f"  session: {m.get('session_id', '?')}\n\n"
            f"--- Output ---\n{result_preview}"
        )

    # failed/timeout/error
    return (
        f"✗ {status} ({elapsed:.0f}s)\n"
        f"  task: {record['task'][:80]}\n"
        f"  error: {record.get('error', 'unknown')}"
    )


@mcp.tool()
def aether_dispatch_list() -> str:
    """List all active and recent dispatches with their status.

    Shows dispatch_id, task, status, and elapsed time for each.
    """
    if not _ACTIVE_DISPATCHES:
        return "No dispatches. Use aether_dispatch_async to start one."

    import time
    now = time.time()
    lines = [f"{len(_ACTIVE_DISPATCHES)} dispatch(es):\n"]
    for did, rec in _ACTIVE_DISPATCHES.items():
        elapsed = now - rec["started_at"]
        status = rec["status"]
        icon = "⏳" if status == "running" else "✓" if status == "complete" else "✗"
        lines.append(
            f"  {icon} {did} [{status}] {elapsed:.0f}s — {rec['task'][:60]}"
        )
    return "\n".join(lines)


@mcp.tool()
def aether_dispatch_metrics(limit: int = 10) -> str:
    """Show recent agent dispatch metrics — tasks, tokens, costs, success rates.

    Returns a summary of recent aether_dispatch calls tracked in CRT memory.

    Args:
        limit: Max dispatch records to show (default 10).
    """
    data = _get("/api/memory/search", {
        "q": "agent_dispatch success OR failed",
        "limit": limit,
        "thread_id": "default",
    })
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    if isinstance(data, list):
        dispatches = [m for m in data if "[agent_dispatch:" in (m.get("text") or "")]
        if not dispatches:
            return "No dispatch records found. Use aether_dispatch to run a task first."

        total = len(dispatches)
        successes = sum(1 for d in dispatches if ":success]" in (d.get("text") or ""))
        failures = total - successes

        lines = [
            f"Agent dispatch history ({total} records):",
            f"  success: {successes}  failures: {failures}  rate: {successes/max(total,1)*100:.0f}%",
            "",
        ]
        for i, d in enumerate(dispatches, 1):
            text = d.get("text", "")
            trust = d.get("trust", 0)
            lines.append(f"  {i}. T:{trust:.2f} {text[:120]}")
        return "\n".join(lines)
    return "No dispatch data available."


@mcp.tool()
def aether_self_model() -> str:
    """Get Aether's current self-awareness state — what it knows about itself.

    Returns the 7 self-model slots: uncertainty domains, correction patterns,
    trust trajectory, known blindspots, growing confidence, user relationship,
    and response style.
    """
    data = _get("/api/self-model/default")
    if isinstance(data, dict) and "error" in data:
        return _fmt(data)
    slots = data.get("self_model_awareness", {})
    if not slots:
        return "Self-model not yet populated. Run a heartbeat reflection first."
    lines = ["Aether Self-Model:"]
    for slot, value in slots.items():
        if value:
            lines.append(f"  {slot}: {value[:120]}")
    return "\n".join(lines)


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
