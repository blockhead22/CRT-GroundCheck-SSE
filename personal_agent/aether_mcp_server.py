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
        "Aether is a belief substrate — a persistent, contradiction-aware trust "
        "state that outlives any single model or session. The aether_* tools "
        "expose the belief state: aether_search (recall with trust + contradiction "
        "metadata), aether_profile, aether_contradictions, aether_context for a "
        "dashboard snapshot, aether_belief_history to see how a belief's trust "
        "evolved, aether_volatile / aether_opinion_variance for per-domain "
        "volatility. Write tools (aether_remember, aether_correct, aether_resolve, "
        "aether_ingest) update the belief state — aether_correct triggers "
        "backprop through the belief dependency graph. aether_ask invokes a full "
        "Aether turn; aether_dispatch* spawns Claude Code as executor with "
        "Aether as governor. aether_self_model introspects. "
        "The crt_* tools cover episodic memory + fact-checking: crt_get_user_context "
        "at session start for personalization, crt_get_pending_fact_checks for "
        "prior mistakes to acknowledge, crt_fact_check_response to verify a "
        "draft, crt_search_sessions for past-session recall, crt_get_learning_stats "
        "for system health, crt_run_trust_decay to manually age memories. "
        "DIFFERENTIATOR TOOLS (the substrate-unique ones): aether_fidelity grades "
        "a draft response's grounding in belief state; aether_lineage shows 'why "
        "do I believe this' via BDG edges; aether_cascade_preview dry-runs a "
        "trust change to see blast radius; aether_session_diff briefs a client "
        "on what changed since last connect; aether_done_shape suggests "
        "success/absence criteria for a task; aether_done_check grades a "
        "response against declared criteria; aether_sanction is a pre-action "
        "governance gate returning APPROVE/HOLD/REJECT for irreversible work."
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


# ===========================================================================
# Merged from crt_mcp_server.py (2026-04-15) — episodic memory + fact-check
# tools that used to live in a separate MCP server. Kept with the crt_ prefix
# to flag the subsystem; they complement the aether_ tools above.
# ===========================================================================

@mcp.tool()
def crt_get_user_context(include_summaries: int = 3) -> str:
    """Get comprehensive user context from episodic memory for personalization.

    Returns learned preferences, behavioral patterns, recent session
    summaries, and known entities/concepts. Use this at the START of a
    session to adapt your tone, style, and content to the user.

    Args:
        include_summaries: Number of recent session summaries to include (default 3).
    """
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        manager = get_episodic_manager()
        context = manager.get_user_context(include_summaries=include_summaries)
        prompt = manager.build_context_prompt()
        context["context_prompt"] = prompt
        return json.dumps(context, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "Episodic memory module not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] get_user_context failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def crt_get_pending_fact_checks(thread_id: str = "", limit: int = 10) -> str:
    """Retrieve pending fact-check findings from auto-verification.

    The auto fact-checker runs after every response and compares the
    response text against stored memories. If it detects hallucinations
    or contradictions, it stores findings here. Call at the start of
    each turn to see if past responses had issues.

    Args:
        thread_id: Filter to a specific conversation thread (optional).
        limit: Maximum findings to return (default 10).
    """
    try:
        from personal_agent.auto_fact_checker import get_pending_fact_checks
        tid = thread_id if thread_id else None
        checks = get_pending_fact_checks(thread_id=tid, limit=limit)
        return json.dumps({"pending": len(checks), "findings": checks}, indent=2, default=str)
    except ImportError:
        return json.dumps({"pending": 0, "findings": [], "note": "Auto fact-checker not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] get_pending_fact_checks failed: %s", e)
        return json.dumps({"pending": 0, "findings": [], "error": str(e)})


@mcp.tool()
def crt_fact_check_response(thread_id: str, query: str, response: str) -> str:
    """Verify a draft response against stored memories NOW (synchronous).

    Unlike the automatic post-response check, this runs synchronously
    so you can see the result before sending your response.

    Args:
        thread_id: The conversation thread ID.
        query: The user's question.
        response: Your draft response text to verify.
    """
    try:
        from groundcheck import GroundCheck
        from groundcheck.types import Memory
        import sqlite3
        import os
        from pathlib import Path

        db_path = None
        env = os.environ.get("GROUNDCHECK_DB", "").strip()
        if env:
            p = Path(env)
            if p.is_file():
                db_path = p
        if not db_path:
            for candidate in [
                Path("D:/groundcheck/.groundcheck/memory.db"),
                Path.home() / ".groundcheck" / "memory.db",
            ]:
                if candidate.is_file():
                    db_path = candidate
                    break
        if not db_path:
            return json.dumps({"error": "GroundCheck DB not found"})

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, text, trust, source, timestamp FROM memories ORDER BY trust DESC"
        ).fetchall()
        conn.close()

        memories = [
            Memory(id=r["id"], text=r["text"], trust=r["trust"], timestamp=r["timestamp"])
            for r in rows
        ]
        if not memories:
            return json.dumps({"passed": True, "note": "No memories to verify against"})

        gc = GroundCheck()
        report = gc.verify(response, memories, mode="permissive")
        result = {
            "passed": report.passed,
            "confidence": report.confidence,
            "hallucinations": report.hallucinations or [],
            "corrected": report.corrected,
            "contradictions": [
                {"slot": c.slot, "values": c.values, "most_trusted_value": c.most_trusted_value}
                for c in (report.contradiction_details or [])
            ],
        }
        if not report.passed:
            try:
                from personal_agent.auto_fact_checker import schedule_fact_check
                mem_dicts = [
                    {"text": m.text, "trust": m.trust, "source": "user", "id": m.id}
                    for m in memories
                ]
                schedule_fact_check(thread_id, query, response, mem_dicts)
            except Exception:
                pass
        return json.dumps(result, indent=2, default=str)
    except ImportError as e:
        return json.dumps({"error": f"Missing dependency: {e}"})
    except Exception as e:
        logger.warning("[CRT_MCP] fact_check_response failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def crt_run_trust_decay(force: bool = False) -> str:
    """Manually trigger a trust decay pass on stored memories.

    Ages stale memories (reduces trust) and reinforces recently used
    or corrected memories (boosts trust). Normally runs automatically
    during idle time.

    Args:
        force: If True, bypass the minimum interval rate limit.
    """
    try:
        from personal_agent.trust_decay import run_trust_decay_pass
        import personal_agent.trust_decay as td
        if force:
            td._last_decay_ts = 0.0
        result = run_trust_decay_pass()
        return json.dumps(result, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "Trust decay module not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] run_trust_decay failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def crt_get_learning_stats() -> str:
    """Get active learning system statistics.

    Returns gate event counts, correction rates, model version, training
    history, and pending corrections.
    """
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        stats = coordinator.get_stats(force_refresh=True)
        return json.dumps(stats.to_dict(), indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "Active learning module not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] get_learning_stats failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def crt_search_sessions(topic: str, limit: int = 5) -> str:
    """Search past conversation sessions by topic.

    Use when the user asks "what did we talk about regarding X?" or
    when you need context from past sessions about a specific subject.

    Args:
        topic: Topic to search for (e.g., "database", "authentication").
        limit: Maximum sessions to return (default 5).
    """
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        summaries = manager.db.search_summaries_by_topic(topic, limit=limit)
        results = [
            {
                "summary": s.summary_text,
                "topics": s.topics,
                "entities": s.entities_mentioned,
                "facts_learned": s.facts_learned,
                "unresolved": s.unresolved_items,
                "message_count": s.message_count,
                "timestamp": s.timestamp,
            }
            for s in summaries
        ]
        return json.dumps({"found": len(results), "sessions": results}, indent=2, default=str)
    except ImportError:
        return json.dumps({"found": 0, "sessions": [], "note": "Episodic memory not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] search_sessions failed: %s", e)
        return json.dumps({"found": 0, "sessions": [], "error": str(e)})


# ===========================================================================
# Differentiator tools (2026-04-15) — the substrate-angle tools that make
# Aether distinct from "yet another memory MCP". These expose belief-state
# primitives no other MCP provides: fidelity grading, belief lineage,
# cascade preview, session diff, done-shape contracts, action sanction.
# ===========================================================================

@mcp.tool()
def aether_fidelity(response: str, query: str, thread_id: str = "") -> str:
    """Grade a draft response against the belief substrate.

    Returns three orthogonal scores (belief_fidelity, request_alignment,
    factual_grounding) plus a composite. Low composite = the response
    may be ungrounded in stored facts or off-topic for the query.

    Call this BEFORE sending a response that references user facts.
    Unlike sanction, this is grading not gating.

    Args:
        response: Your draft response text.
        query: The user's original question/prompt.
        thread_id: Optional — which thread's memories to check against.
    """
    try:
        from personal_agent.fidelity_mirror import check_fidelity
        # Pull retrieval memories to ground against. Prefer thread-scoped if given.
        mems_payload = _post("/api/memory/search", {
            "query": query[:500],
            "k": 10,
            **({"thread_id": thread_id} if thread_id else {}),
        })
        mems = []
        if isinstance(mems_payload, dict) and "results" in mems_payload:
            mems = [
                {"text": m.get("text", "")[:300],
                 "trust": m.get("trust", 0.5),
                 "memory_id": m.get("memory_id", m.get("id", ""))}
                for m in mems_payload["results"][:10]
            ]
        fid = check_fidelity(response=response, query=query, memories=mems)
        return json.dumps({
            "belief_fidelity": fid.belief_fidelity,
            "request_alignment": fid.request_alignment,
            "factual_grounding": fid.factual_grounding,
            "composite": fid.composite,
            "passed": fid.passed,
            "findings": fid.findings,
            "memories_checked": len(mems),
            "latency_ms": fid.latency_ms,
        }, indent=2)
    except ImportError:
        return json.dumps({"error": "fidelity_mirror not available"})
    except Exception as e:
        logger.warning("[MCP] aether_fidelity failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def aether_lineage(memory_id: str, hops: int = 2) -> str:
    """Why do I believe this? Returns the BDG edges around a memory.

    Shows direct supporters, contradictors, correction history, and
    the local contradiction density. Use when the user asks "how do
    you know X?" or "what evidence supports this?"

    Args:
        memory_id: The memory's ID (from aether_search or aether_memory_detail).
        hops: Graph hops to traverse (default 2; higher = more context, more noise).
    """
    try:
        from personal_agent.memory_graph import get_live_bdg, EdgeType
        live = get_live_bdg()
        if live is None:
            return json.dumps({"error": "LiveBDG not initialized"})
        live.ensure_built()
        mg = getattr(live, "memory_graph", None) or getattr(live, "graph", None)
        if mg is None:
            return json.dumps({"error": "MemoryGraph not accessible on LiveBDG"})

        node = mg.get_memory(memory_id) if hasattr(mg, "get_memory") else None
        if node is None:
            return json.dumps({"error": f"memory_id not found: {memory_id}"})

        supports, contradicts = [], []
        if hasattr(mg, "get_neighbors"):
            try:
                neighbors = mg.get_neighbors(memory_id, hops=hops)
                for nid, meta in neighbors:
                    edge_type = meta.get("edge_type") or meta.get("type", "related")
                    entry = {"id": nid, "edge": str(edge_type),
                             "weight": round(float(meta.get("weight", 0.5)), 3)}
                    if "contradict" in str(edge_type).lower():
                        contradicts.append(entry)
                    else:
                        supports.append(entry)
            except Exception:
                pass

        contra_density = 0.0
        if hasattr(mg, "contradiction_density"):
            try:
                contra_density = float(mg.contradiction_density(memory_id))
            except Exception:
                pass

        # Pull correction history from the memory detail endpoint
        detail = _get(f"/api/memory/detail", {"memory_id": memory_id})
        correction_history = []
        trust_curve = []
        if isinstance(detail, dict):
            correction_history = detail.get("correction_events", [])[:10]
            trust_curve = detail.get("trust_history", [])[:20]

        return json.dumps({
            "memory": {
                "id": memory_id,
                "text": (node.text if hasattr(node, 'text') else "")[:300],
                "trust": float(getattr(node, 'trust', 0.5)),
                "kind": str(getattr(node, 'kind', 'unknown')),
            },
            "supports": supports[:20],
            "contradicts": contradicts[:20],
            "correction_history": correction_history,
            "trust_curve": trust_curve,
            "contradiction_density": round(contra_density, 3),
        }, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "memory_graph not available"})
    except Exception as e:
        logger.warning("[MCP] aether_lineage failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def aether_cascade_preview(memory_id: str, new_trust: float) -> str:
    """Dry-run: if this memory's trust shifted to `new_trust`, what else moves?

    Returns the set of beliefs that would be affected by the cascade,
    with their projected new trust. NO actual mutation — pure simulation.

    Use before aether_correct on a high-connectivity belief to see blast radius.

    Args:
        memory_id: The memory to hypothetically revise.
        new_trust: Target trust value (0.0–1.0).
    """
    try:
        from personal_agent.memory_graph import get_live_bdg
        live = get_live_bdg()
        if live is None:
            return json.dumps({"error": "LiveBDG not initialized"})
        live.ensure_built()
        bdg = getattr(live, "bdg", None)
        if bdg is None:
            return json.dumps({"error": "BeliefDependencyGraph not accessible"})

        # Fetch current trust to compute delta
        mg = getattr(live, "memory_graph", None) or getattr(live, "graph", None)
        cur = 0.5
        if mg is not None and hasattr(mg, "get_memory"):
            n = mg.get_memory(memory_id)
            if n is not None:
                cur = float(getattr(n, 'trust', 0.5))
        delta = float(new_trust) - cur
        if abs(delta) < 1e-6:
            return json.dumps({"affected": [], "note": "delta ≈ 0, nothing to cascade",
                               "current_trust": cur})

        # propagate_cascade returns CascadeResult — a dry run by nature (computes impacts)
        result = bdg.propagate_cascade(source_id=memory_id, delta_0=abs(delta))
        affected_list = []
        affected_map = getattr(result, "affected", {}) or {}
        depth_map = getattr(result, "depth_map", {}) or {}
        for nid, impact in sorted(affected_map.items(), key=lambda x: -abs(x[1]))[:30]:
            # impact magnitude applied in delta's direction
            projected_delta = impact * (1 if delta < 0 else -1)  # downstream trusts move opposite
            affected_list.append({
                "memory_id": nid,
                "impact_magnitude": round(float(impact), 4),
                "distance": int(depth_map.get(nid, 0)),
            })
        return json.dumps({
            "source": memory_id,
            "current_trust": round(cur, 3),
            "proposed_trust": round(float(new_trust), 3),
            "delta": round(delta, 3),
            "affected": affected_list,
            "total_impact": round(float(getattr(result, "total_impact", 0.0)), 4),
            "max_depth": int(getattr(result, "max_depth_reached", 0)),
            "width": int(getattr(result, "max_width", 0) or 0),
            "note": "DRY-RUN ONLY — no mutation. Apply via aether_correct.",
        }, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "memory_graph not available"})
    except Exception as e:
        logger.warning("[MCP] aether_cascade_preview failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def aether_session_diff(thread_id: str, since_ts: float = 0.0) -> str:
    """What changed in the belief state since `since_ts` (Unix epoch).

    Call on session connect — returns new memories, trust shifts,
    new contradictions, resolved items, and any open holds. This is
    the session-continuity briefing no memory MCP today provides.

    Args:
        thread_id: Thread to scope the diff to.
        since_ts: Unix timestamp. 0 = entire session history.
    """
    try:
        # Backend aggregator endpoint — fall back to piecemeal if missing
        agg = _get("/api/session/diff", {"thread_id": thread_id, "since_ts": since_ts})
        if isinstance(agg, dict) and "error" not in agg:
            return _fmt(agg)

        # Piecemeal fallback: use existing endpoints
        trust = _get("/api/memory/trust-delta", {"thread_id": thread_id, "since_ts": since_ts, "limit": 20})
        open_contras = _get("/api/ledger/open", {"thread_id": thread_id, "limit": 50})
        result = {
            "thread_id": thread_id,
            "since_ts": since_ts,
            "trust_shifts": trust if isinstance(trust, (list, dict)) else [],
            "open_contradictions": open_contras if isinstance(open_contras, (list, dict)) else [],
            "note": "Aggregator endpoint /api/session/diff not found — piecemeal fallback used.",
        }

        # Try session_state render as a prose summary
        try:
            from personal_agent.session_state import get_or_create_session, render_away_resume_diff
            sess = get_or_create_session(thread_id)
            prose = render_away_resume_diff(sess)
            if prose:
                result["summary_prose"] = prose
        except Exception:
            pass

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.warning("[MCP] aether_session_diff failed: %s", e)
        return json.dumps({"error": str(e)})


# Task-type heuristics for aether_done_shape
_DONE_SHAPE_PATTERNS = [
    # (pattern, task_type, success_template, absence_template)
    (r"\b(find|locate|search|show me|where is)\b",
     "search",
     ["Concrete location(s) identified with file:line or memory_id",
      "Relevance to the query confirmed"],
     ["Alternate names/synonyms ruled out",
      "Obvious candidate files explicitly checked and cleared"]),
    (r"\b(explain|describe|walk me through|how does)\b",
     "explanation",
     ["Core mechanism named with specifics",
      "At least one concrete example cited"],
     ["Claims of 'does not exist' backed by file/line evidence"]),
    (r"\b(implement|build|create|add|write|make)\b",
     "implementation",
     ["Target file(s) modified or created",
      "Behavior verified (ran tests or executed code)",
      "No regression in adjacent functionality"],
     ["No silent catch-all except: pass patterns introduced",
      "No secrets/tokens committed"]),
    (r"\b(fix|repair|resolve|debug)\b",
     "bugfix",
     ["Root cause identified (not just symptom)",
      "Fix applied and verified via execution",
      "Related sites checked for same bug"],
     ["No regression introduced",
      "Fix isn't a workaround that masks the real issue"]),
    (r"\b(audit|review|assess|check|analyze)\b",
     "audit",
     ["Full target scope traversed (not sampled)",
      "Findings categorized by severity or type"],
     ["Low-hanging-fruit categories explicitly checked and excluded"]),
    (r"\b(compare|diff|contrast)\b",
     "comparison",
     ["Both sides read independently",
      "Similarities AND differences enumerated"],
     ["Sides not conflated — each evidenced separately"]),
    (r"\b(list|enumerate|count|show all)\b",
     "enumeration",
     ["Complete list returned (not a sample)",
      "Count provided"],
     ["Exclusions explicitly flagged if any"]),
]


@mcp.tool()
def aether_done_shape(task: str) -> str:
    """Suggest success_criteria + absence_criteria for a task.

    The 'done-shape' — what would PROVE the task is complete, and what
    evidence is required to defensibly say 'no/absent'. Agents call this
    before planning and hold the shape as a persistent target.

    NOTE: current impl is pure regex heuristic. LLM-generated criteria
    is planned as a fallback when confidence < 0.5 — see fog_talk.

    Args:
        task: The task description in natural language.
    """
    import re as _rx
    t_lower = task.lower()
    matched_type = "generic"
    success, absence = [], []
    confidence = 0.0
    for pat, ttype, succ, absn in _DONE_SHAPE_PATTERNS:
        if _rx.search(pat, t_lower):
            matched_type = ttype
            success.extend(succ)
            absence.extend(absn)
            confidence = 0.7  # heuristic hit
            break
    if not success:
        # Generic fallback
        matched_type = "generic"
        success = [
            "User's literal request addressed in the response",
            "Claims grounded in tool results or explicit memory references",
        ]
        absence = [
            "Claims of absence/negation backed by concrete evidence",
            "No hallucinated file paths, functions, or symbols",
        ]
        confidence = 0.3
    return json.dumps({
        "task": task[:200],
        "task_type": matched_type,
        "success_criteria": success,
        "absence_criteria": absence,
        "confidence": confidence,
        "method": "heuristic",  # future: "llm" when fallback shipped
        "note": ("Heuristic match. For complex/ambiguous tasks, consider "
                 "hand-editing criteria before use.") if confidence < 0.5 else None,
    }, indent=2)


@mcp.tool()
def aether_done_check(task: str, response: str, tool_trail: str,
                      success_criteria: str, absence_criteria: str) -> str:
    """Grade a draft response against declared done-shape criteria.

    Returns FILLED/UNFILLED per slot with evidence. If any UNFILLED,
    the caller should NOT respond — instead issue more tool calls or
    revise the response.

    This is the gap check that prevents premature 'done' claims.

    Args:
        task: Original task description.
        response: Draft response text.
        tool_trail: Pipe-separated tool calls + results (e.g. "search_code(...) -> ok: def foo|file_read(auth.py) -> ok: <content>").
        success_criteria: Newline-separated criteria from aether_done_shape.
        absence_criteria: Newline-separated absence criteria.
    """
    try:
        from personal_agent.fidelity_mirror import _encode, _cosine_sim
        import numpy as np

        # Combine response + tool trail as the evidence pool
        evidence = (response + "\n" + tool_trail)[:8000]
        evidence_vec = _encode(evidence)
        if evidence_vec is None:
            return json.dumps({"error": "encoding failed"})

        # Hybrid scoring: cosine similarity OR keyword overlap.
        # MiniLM embeddings are weak on exact-term matching (e.g. "file:line"
        # vs "line 59" barely correlate). Lexical overlap is a second signal.
        evidence_lower = evidence.lower()
        import re as _rx

        def _keyword_signal(criterion: str) -> float:
            # Extract content words 4+ chars, compute ratio present in evidence.
            tokens = _rx.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", criterion.lower())
            stop = {"with", "that", "this", "from", "into", "their", "there",
                    "been", "were", "your", "have", "what", "which", "also"}
            tokens = [t for t in tokens if t not in stop]
            if not tokens:
                return 0.0
            hits = sum(1 for t in tokens if t in evidence_lower)
            return hits / len(tokens)

        # HEURISTIC LIMITATION (2026-04-15): these thresholds work for concrete
        # criteria ("test passes", "file exists") but under-score abstract meta-
        # criteria ("relevance confirmed", "synonyms ruled out"). LLM-grading is
        # the planned fallback — see fog_talk note.
        COS_THRESHOLD = 0.20
        KW_THRESHOLD = 0.40

        def _score(crit_list_str):
            out = []
            for line in [ln.strip() for ln in crit_list_str.split("\n") if ln.strip()]:
                c_vec = _encode(line)
                cos_sim = float(_cosine_sim(evidence_vec, c_vec)) if c_vec is not None else 0.0
                kw_sig = _keyword_signal(line)
                filled = (cos_sim >= COS_THRESHOLD) or (kw_sig >= KW_THRESHOLD)
                out.append({
                    "criterion": line,
                    "cosine": round(cos_sim, 3),
                    "keyword_overlap": round(kw_sig, 3),
                    "filled": filled,
                    "evidence_snippet": evidence[:150] if filled else "",
                })
            return out

        success_results = _score(success_criteria)
        absence_results = _score(absence_criteria)
        all_filled = all(r["filled"] for r in success_results + absence_results)
        unfilled = [r["criterion"] for r in success_results + absence_results if not r["filled"]]

        return json.dumps({
            "task": task[:200],
            "success_results": success_results,
            "absence_results": absence_results,
            "all_filled": all_filled,
            "unfilled_count": len(unfilled),
            "unfilled": unfilled,
            "should_respond": all_filled,
            "recommendation": ("Response is grounded — safe to send."
                               if all_filled else
                               f"Do NOT respond yet. {len(unfilled)} criteria unfilled. "
                               "Issue more tool calls or revise."),
            "note": "Scores are cosine similarity between evidence pool and each criterion.",
        }, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "encoding tools not available"})
    except Exception as e:
        logger.warning("[MCP] aether_done_check failed: %s", e)
        return json.dumps({"error": str(e)})


# Risk heuristics for aether_sanction
_HIGH_RISK_VERBS = [
    "delete", "drop", "truncate", "rm -rf", "git push --force",
    "force push", "wipe", "purge", "reset --hard", "DROP TABLE",
    "send to", "email", "publish", "deploy to production", "go live",
    "charge", "withdraw", "transfer", "authorize payment",
]
_MED_RISK_VERBS = [
    "update", "modify", "change", "overwrite", "merge", "rebase",
    "migrate", "refactor", "rename", "move",
]


@mcp.tool()
def aether_sanction(action: str, context: str = "") -> str:
    """Pre-action governance gate: should this action be taken given belief state?

    Returns APPROVE | HOLD | REJECT with supporting + contradicting memories
    and risk factors. Use BEFORE any irreversible action (git push, delete,
    send, deploy, charge).

    APPROVE = belief state supports the action.
    HOLD = unresolved contradiction or missing evidence; ask user.
    REJECT = belief state contradicts or high risk with low support.

    Args:
        action: What you're about to do (e.g., "git push --force to main").
        context: Optional context (files, user claims, prior steps).
    """
    try:
        # 1. Classify risk level from verb
        a_lower = action.lower()
        risk_level = "low"
        risk_factors = []
        for verb in _HIGH_RISK_VERBS:
            if verb.lower() in a_lower:
                risk_level = "high"
                risk_factors.append(f"high-risk verb detected: '{verb}'")
                break
        if risk_level != "high":
            for verb in _MED_RISK_VERBS:
                if verb.lower() in a_lower:
                    risk_level = "medium"
                    risk_factors.append(f"medium-risk verb: '{verb}'")
                    break

        # 2. Recall relevant memories for both action and context
        query = f"{action} {context}"[:400]
        mems_payload = _post("/api/memory/search", {"query": query, "k": 8})
        supporting, contradicting = [], []
        if isinstance(mems_payload, dict) and "results" in mems_payload:
            for m in mems_payload["results"][:8]:
                entry = {
                    "id": m.get("memory_id", m.get("id", "")),
                    "text": m.get("text", "")[:200],
                    "trust": m.get("trust", 0.5),
                    "contradicted": bool(m.get("contradiction_count", 0)),
                }
                # Treat contradicted memories as contradicting evidence
                if entry["contradicted"]:
                    contradicting.append(entry)
                elif entry["trust"] >= 0.6:
                    supporting.append(entry)

        # 3. Check open contradictions on the topic
        open_contras = _get("/api/ledger/open", {"limit": 30})
        relevant_contras = []
        if isinstance(open_contras, list):
            for c in open_contras:
                topic = str(c.get("topic", "") or c.get("slot", "")).lower()
                if topic and any(w in query.lower() for w in topic.split()[:3]):
                    relevant_contras.append({
                        "id": c.get("id", ""),
                        "topic": c.get("topic", c.get("slot", "")),
                        "status": c.get("status", "open"),
                    })
                    risk_factors.append(f"open contradiction on related topic: {topic[:50]}")

        # 4. Verdict logic
        supp_count = len(supporting)
        contra_count = len(contradicting) + len(relevant_contras)

        if risk_level == "high":
            if contra_count > 0 or supp_count == 0:
                verdict = "REJECT"
                reasoning = (f"High-risk action with "
                             f"{contra_count} contradicting signal(s) and "
                             f"{supp_count} supporting. Do not proceed without "
                             "explicit user confirmation.")
            elif supp_count >= 2:
                verdict = "HOLD"
                reasoning = (f"High-risk action with {supp_count} supporting signals "
                             "but no contradictions. Ask user to confirm before acting.")
            else:
                verdict = "HOLD"
                reasoning = f"High-risk action with weak support ({supp_count}). Confirm with user."
        elif risk_level == "medium":
            if contra_count > supp_count:
                verdict = "HOLD"
                reasoning = (f"Medium-risk action with more contradicting ({contra_count}) "
                             f"than supporting ({supp_count}) signals.")
            else:
                verdict = "APPROVE"
                reasoning = (f"Medium-risk action with {supp_count} supporting signals, "
                             f"{contra_count} contradicting. Proceed with caution.")
        else:
            verdict = "APPROVE"
            reasoning = f"Low-risk action. Belief state does not conflict."

        return json.dumps({
            "action": action[:300],
            "verdict": verdict,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "supporting_memories": supporting,
            "contradicting_memories": contradicting,
            "open_contradictions": relevant_contras,
            "reasoning": reasoning,
            "note": ("This is governance advisory. The client is responsible for "
                     "honoring HOLD/REJECT verdicts."),
        }, indent=2, default=str)
    except Exception as e:
        logger.warning("[MCP] aether_sanction failed: %s", e)
        return json.dumps({"error": str(e)})


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
