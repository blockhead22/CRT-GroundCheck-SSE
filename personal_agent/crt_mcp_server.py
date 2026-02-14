"""CRT MCP Server — exposes CRT-specific tools via Model Context Protocol.

These tools complement the GroundCheck MCP server with higher-order
capabilities: episodic memory, auto fact-checking, trust decay, and
active learning insights.

Usage in .vscode/mcp.json:
    {
        "servers": {
            "crt": {
                "command": "d:\\AI_round2\\.venv\\Scripts\\python.exe",
                "args": ["-m", "personal_agent.crt_mcp_server"]
            }
        }
    }
"""

from __future__ import annotations

import json
import logging
import sys

from mcp.server import FastMCP

logger = logging.getLogger("crt-mcp")

mcp = FastMCP(
    "crt",
    instructions=(
        "CRT provides higher-order memory and self-improvement tools. "
        "Use crt_get_user_context at the start of sessions to personalize "
        "responses using learned preferences, patterns, and session history. "
        "Use crt_get_pending_fact_checks to surface mistakes from previous "
        "turns and self-correct. Use crt_fact_check_response after composing "
        "a response to verify it against stored facts. Use crt_run_trust_decay "
        "to manually trigger memory aging when requested."
    ),
)


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

        # Also attach the pre-built prompt snippet
        prompt = manager.build_context_prompt()
        context["context_prompt"] = prompt

        return json.dumps(context, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "Episodic memory module not available"})
    except Exception as e:
        logger.warning("[CRT_MCP] get_user_context failed: %s", e)
        return json.dumps({"error": str(e)})


@mcp.tool()
def crt_get_pending_fact_checks(
    thread_id: str = "",
    limit: int = 10,
) -> str:
    """Retrieve pending fact-check findings from auto-verification.

    The auto fact-checker runs after every response and compares the
    response text against stored memories. If it detects hallucinations
    or contradictions, it stores findings here.

    Call this at the start of each turn to see if past responses had
    issues. If findings exist, acknowledge them:
        "I noticed I got X wrong last time — let me correct that."

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
def crt_fact_check_response(
    thread_id: str,
    query: str,
    response: str,
) -> str:
    """Verify a draft response against stored memories NOW (synchronous).

    Unlike the automatic post-response check, this runs synchronously
    so you can see the result before sending your response. Use this
    when you want to double-check a response that references user facts.

    Returns verification result with any hallucinations or contradictions.

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

        # Find the GroundCheck DB
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

        # Load memories
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, text, trust, source, timestamp FROM memories ORDER BY trust DESC"
        ).fetchall()
        conn.close()

        memories = [
            Memory(
                text=r["text"],
                trust=r["trust"],
                source=r["source"] or "user",
                memory_id=r["id"],
                timestamp=r["timestamp"],
            )
            for r in rows
        ]

        if not memories:
            return json.dumps({"passed": True, "note": "No memories to verify against"})

        gc = GroundCheck()
        report = gc.verify(response, memories, mode="permissive")

        result = {
            "passed": report.passed,
            "confidence": report.confidence,
            "hallucinated_facts": {
                k: {"slot": v.slot, "value": v.value}
                for k, v in (report.hallucinated_facts or {}).items()
            },
            "contradictions": [
                {
                    "slot": c.slot,
                    "values": c.values,
                    "most_trusted_value": c.most_trusted_value,
                }
                for c in (report.contradiction_details or [])
            ],
        }

        # If check failed, also store for the auto-corrector
        if not report.passed:
            try:
                from personal_agent.auto_fact_checker import schedule_fact_check

                mem_dicts = [
                    {"text": m.text, "trust": m.trust, "source": m.source, "memory_id": m.memory_id}
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

    This ages stale memories (reduces trust) and reinforces recently
    used or corrected memories (boosts trust). Normally runs
    automatically during idle time, but you can trigger it manually.

    Args:
        force: If True, run even if the minimum interval hasn't elapsed.
    """
    try:
        from personal_agent.trust_decay import run_trust_decay_pass, _last_decay_ts, MIN_PASS_INTERVAL_SECS
        import personal_agent.trust_decay as td

        if force:
            # Reset the last-run timestamp to bypass rate limiting
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

    Returns gate event counts, correction rates, model version,
    training history, and pending corrections. Useful for understanding
    how the system is improving over time.
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

    Use this when the user asks "What did we talk about regarding X?"
    or you need context from past sessions about a specific subject.

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


def main():
    """Entry point for the CRT MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="CRT MCP Server")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    logger.info("CRT MCP server starting")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
