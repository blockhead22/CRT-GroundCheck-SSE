"""Special-request handlers extracted from routes/chat.py."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.runtime_paths import resolve_agent_runs_db_path
from ..deps import sanitize_thread_id


def _safe_print(msg: str) -> None:
    """Print to console, replacing unencodable characters (Windows cp1252 fix)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


# ---------------------------------------------------------------------------
# _build_loop_acknowledgment
# ---------------------------------------------------------------------------

def _build_loop_acknowledgment(
    message: str,
    intent,
    *,
    history_messages: Optional[List[Dict[str, str]]] = None,
) -> str:
    history_messages = history_messages or []
    ack_text = ""
    try:
        from personal_agent.task_agent import triage_message as _triage_message
        from personal_agent.task_agent import _generate_acknowledgment as _generate_ack

        _triage = _triage_message(message, intent)
        ack_text = str(_triage.acknowledgment or "").strip()
        if not ack_text:
            ack_text = str(_generate_ack(intent, message) or "").strip()
    except Exception:
        ack_text = ""

    # Lazy import — _resolve_personal_history_reference lives in chat.py
    from ..chat import _resolve_personal_history_reference

    resolved_query, resolved_topic, inferred = _resolve_personal_history_reference(message, history_messages)
    if resolved_topic == "health_history":
        if inferred:
            return "This sounds like a follow-up to your health-history thread, so I'm pulling that context back in before I answer."
        return "I'm going to pull together the relevant health-history context first, then answer directly."
    if resolved_query:
        return "I'm going to pull the relevant personal-history context back in first, then answer directly."

    if not ack_text:
        ack_text = "I'm going to look into that first, then I'll report back."

    if getattr(intent, "route", "") == "conversational" and (
        "look into that first" in ack_text.lower() or "tell you what i found" in ack_text.lower()
    ):
        return "I'm going to think that through for a moment, then I'll answer directly."

    return ack_text


# ---------------------------------------------------------------------------
# _is_bare_web_search_command / _resolve_bare_web_search_command
# ---------------------------------------------------------------------------

def _is_bare_web_search_command(text: str) -> bool:
    """True for generic search commands without a concrete topic/query."""
    t = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not t:
        return False

    command_markers = (
        "use duckduckgo",
        "use duck duck go",
        "duckduckgo and web search",
        "duck duck go and web search",
        "use web search",
        "web search",
        "search the web",
        "search online",
    )
    if not any(m in t for m in command_markers):
        return False

    # If the user already specified a topical query, this is not a bare command.
    # Examples to keep as non-bare:
    # - "search the web for dji mic 2 lav input"
    # - "can you check X using duckduckgo"
    if any(m in t for m in ("search for ", "for ", "about ", "on ", "regarding ", "using duckduckgo")):
        # still bare if the whole message is essentially just a command phrase
        trimmed = t
        for m in command_markers:
            trimmed = trimmed.replace(m, " ")
        trimmed = re.sub(r"[^a-z0-9\s]", " ", trimmed)
        words = [w for w in trimmed.split() if w and w not in {"use", "and", "please", "can", "you"}]
        return len(words) <= 2

    return True


def _resolve_bare_web_search_command(
    *,
    message: str,
    session_db: Any,
    thread_id: str,
) -> str:
    """Map bare 'use web search' commands to the last substantive user question."""
    q = str(message or "").strip()
    if not q or not _is_bare_web_search_command(q):
        return q
    if session_db is None:
        return q

    try:
        recent = session_db.get_recent_queries(thread_id, window=12)
    except Exception:
        recent = []

    # get_recent_queries() already returns newest-first; pick the latest
    # substantive user query that is not another bare search command.
    for row in recent:
        prev_q = str((row or {}).get("query_text") or "").strip()
        if not prev_q:
            continue
        if prev_q.lower() == q.lower():
            continue
        if _is_bare_web_search_command(prev_q):
            continue
        prev_l = prev_q.lower()
        if re.match(r"^(search (the web|online|duckduckgo|ddg) for|web search for)\b", prev_l):
            return prev_q
        return f"search the web for {prev_q}"

    return q


# ---------------------------------------------------------------------------
# _post_answer_quick_check
# ---------------------------------------------------------------------------

def _post_answer_quick_check(
    *,
    answer: str,
    retrieved_memories: List[Dict[str, Any]],
    session_db: "Any",
    thread_id: str,
) -> Optional[str]:
    """Quick post-answer validation — catches "I don't know" when we actually do.

    Runs AFTER answer tokens are streamed but BEFORE ``done`` is emitted.
    No LLM call — pure pattern matching + data lookup.  Target: <500ms.
    Returns a correction string or None.
    """
    if not answer:
        return None

    answer_lower = answer.lower()

    # Patterns that indicate the system claims ignorance
    ignorance_phrases = (
        "i don't have",
        "i don't know",
        "not stored",
        "no memory",
        "no stored memory",
        "don't have specific",
        "don't have that stored",
        "haven't learned",
        "i have no information",
        "not in my memory",
        "i don't have enough context",
    )

    claims_ignorance = any(phrase in answer_lower for phrase in ignorance_phrases)
    if not claims_ignorance:
        return None

    # Check if retrieved memories actually contain relevant data
    high_trust_facts: List[str] = []
    for mem in (retrieved_memories or []):
        if not isinstance(mem, dict):
            continue
        trust = float(mem.get("trust") or mem.get("confidence") or 0)
        text = str(mem.get("text") or "").strip()
        source = str(mem.get("source") or "").lower()
        if trust >= 0.5 and text and source in ("user", "inferred"):
            # Skip very short or meta entries
            if len(text) > 10 and not text.lower().startswith(("how can i", "hello", "i'm here")):
                high_trust_facts.append(text[:200])

    if high_trust_facts:
        # We have data but claimed we don't — correct ourselves
        facts_preview = "; ".join(high_trust_facts[:3])
        return f"Wait — I actually do have some relevant memories: {facts_preview}"

    # Check recent conversation history for relevant context
    try:
        if session_db and hasattr(session_db, "get_recent_queries"):
            recent = session_db.get_recent_queries(thread_id, window=2)
            for row in (recent or []):
                if not isinstance(row, dict):
                    continue
                prev_query = str(row.get("query_text") or "").strip()
                # If the user just told us something substantial in the previous turn
                if len(prev_query) > 100:
                    return (
                        f"Actually, you just shared some information with me in our recent conversation. "
                        f"Let me look at that more carefully."
                    )
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# _is_architecture_explanation_request
# ---------------------------------------------------------------------------

def _is_architecture_explanation_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if len(t) > 1000:
        return False
    # Do not hijack explicit profile/memory submissions into the doc-grounded lane.
    # Example: "Here is an about me ... I'm building CRT ..."
    profile_markers = (
        "here is an about me",
        "here's an about me",
        "question: here is an about me",
        "about me:",
        "here is my bio",
        "here's my bio",
        "my bio:",
        "remember this about me",
        "store this about me",
        "save this about me",
        "for your memory",
    )
    if any(m in t for m in profile_markers):
        return False
    # Also avoid doc-lane hijack when the user is giving profile-like content.
    if "about me" in t and any(
        m in t
        for m in (
            "my name is",
            "i'm ",
            "i am ",
            "i work",
            "i build",
            "i value",
            "focused on",
        )
    ):
        return False
    # Only route to doc-grounded answers for very specific technical terms.
    # General questions like "how do you work" or "who are you" should go through
    # the LLM path where the self-aware system prompt can answer naturally.
    needles = (
        "crt architecture",
        "system architecture",
        "reconstruction gate",
        "reconstruction gates",
        "trust-weighted memories",
        "trust weighted memories",
        "contradiction preservation",
        "contradiction ledger",
        "coherence priority",
        "cognitive-reflective transformer",
        "cognitive reflective transformer",
        "crt whitepaper",
        "crt spec",
        "functional spec",
    )
    return any(n in t for n in needles)


# ---------------------------------------------------------------------------
# _classify_and_store_feedback
# ---------------------------------------------------------------------------

def _classify_and_store_feedback(thread_id: str, message: str) -> None:
    """Layer 6: Classify the user's message as implicit feedback on the last orchestrator run.

    Looks at the most recent orchestrator run (last 5 minutes) and classifies
    the user's follow-up message as validation, correction, or neutral.
    Updates the run's user_feedback field in agent_runs.db.
    """
    import sqlite3, time, re

    db_path = str(resolve_agent_runs_db_path())
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path, timeout=3)
    conn.row_factory = sqlite3.Row

    # Find the most recent run within 5 minutes that has no feedback yet
    cutoff = time.time() - 300
    row = conn.execute(
        "SELECT run_id, intent FROM agent_runs "
        "WHERE timestamp > ? AND user_feedback IS NULL "
        "ORDER BY timestamp DESC LIMIT 1",
        (cutoff,),
    ).fetchone()

    if not row:
        conn.close()
        return

    run_id = row["run_id"]

    # Classify the message as feedback
    _POSITIVE = re.compile(
        r"\b(good|great|nice|right|exactly|yes|yeah|correct|agree|"
        r"that('s| is) (good|right|fair|true|interesting|helpful)|"
        r"thank|makes sense|fair point|well said|love|impressive|"
        r"let'?s|want to find out|together)\b",
        re.IGNORECASE,
    )
    _NEGATIVE = re.compile(
        r"\b(no[,.]|wrong|incorrect|that('s| is) not|push back|"
        r"disagree|but (actually|really|I think)|"
        r"design flaw|you('re| are) (wrong|not right|missing)|"
        r"sophisticated constraint|just (pattern|constraint|performing)|"
        r"how do you know|are you sure)\b",
        re.IGNORECASE,
    )

    pos_hits = len(_POSITIVE.findall(message))
    neg_hits = len(_NEGATIVE.findall(message))

    if pos_hits > neg_hits:
        feedback = "validated"
    elif neg_hits > pos_hits:
        feedback = "corrected"
    elif pos_hits > 0 and neg_hits > 0:
        feedback = "mixed"
    else:
        feedback = "continued"  # neutral continuation

    conn.execute(
        "UPDATE agent_runs SET user_feedback = ? WHERE run_id = ?",
        (feedback, run_id),
    )
    conn.commit()
    conn.close()
    _safe_print(f"[FEEDBACK] Run {run_id[:25]} <- {feedback} (pos={pos_hits}, neg={neg_hits})")


# ---------------------------------------------------------------------------
# Contradiction inventory / work-plan / MCP tools / doc helpers
# ---------------------------------------------------------------------------

def _is_contradiction_inventory_request(text: str) -> bool:
    """Detect user requests asking about contradictions/conflicts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if not any(k in t for k in ("contradict", "inconsisten", "conflict")):
        return False
    needles = (
        "what contradictions",
        "which contradictions",
        "any contradictions",
        "are there contradictions",
        "do you have contradictions",
        "contradictions have you",
        "contradictions did you",
        "contradictions detected",
        "contradictions found",
        "what conflicts",
        "any conflicts",
        "in our conversation",
        "in our chat",
    )
    return any(n in t for n in needles)


def _extract_workplan_items(text: str) -> Dict[int, str]:
    """Parse 'Items N (label)' pairs from a stored work-plan sentence."""
    out: Dict[int, str] = {}
    for num_s, label in re.findall(r"(\d+)\s*\(([^)]+)\)", str(text or "")):
        try:
            num = int(num_s)
        except Exception:
            continue
        clean = " ".join(str(label).strip().split())
        if clean:
            out[num] = clean
    return out


def _load_latest_workplan_from_groundcheck() -> Optional[Tuple[str, str, Dict[int, str]]]:
    """Return (memory_id, text, parsed_items) for the latest GroundCheck work-plan row."""
    try:
        from personal_agent.memory_bridge import find_groundcheck_db

        db_path = find_groundcheck_db()
    except Exception:
        return None
    if not db_path:
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, text, timestamp
            FROM memories
            WHERE lower(text) LIKE '%work plan%'
               OR lower(text) LIKE '%plan for aether%'
               OR lower(text) LIKE '%item %(%'
               OR lower(text) LIKE '%items %(%'
            ORDER BY timestamp DESC
            LIMIT 20
            """
        ).fetchall()
        for row in rows:
            text = str(row["text"] or "").strip()
            parsed = _extract_workplan_items(text)
            if parsed:
                return str(row["id"]), text, parsed
    except Exception:
        return None
    finally:
        conn.close()
    return None


def _load_latest_workplan_from_crt_memory(
    engine: Any,
    *,
    thread_id: Optional[str] = None,
) -> Optional[Tuple[str, str, Dict[int, str]]]:
    """Fallback work-plan loader from CRT memory when GroundCheck lookup misses."""
    if engine is None:
        return None
    mem = getattr(engine, "memory", None)
    if mem is None:
        return None
    try:
        all_mems = mem._load_all_memories()  # internal helper; best-effort fallback path
    except Exception:
        return None
    if not all_mems:
        return None

    tid = sanitize_thread_id(str(thread_id or "default")) if thread_id else None
    scoped = []
    for m in all_mems:
        m_tid = str(getattr(m, "thread_id", "") or "").strip()
        if tid and m_tid and m_tid != tid:
            continue
        scoped.append(m)

    scoped.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
    for m in scoped[:120]:
        text = str(getattr(m, "text", "") or "").strip()
        if not text:
            continue
        tl = text.lower()
        if "work plan" not in tl and "item" not in tl:
            continue
        parsed = _extract_workplan_items(text)
        if not parsed:
            continue
        mem_id = str(getattr(m, "memory_id", "") or getattr(m, "id", "") or "")
        if mem_id:
            return mem_id, text, parsed
    return None


def _load_latest_groundcheck_memory_by_phrase(
    phrases: Tuple[str, ...],
    *,
    limit: int = 8,
) -> Optional[Tuple[str, str]]:
    """Return latest (memory_id, text) matching any lowercase phrase."""
    try:
        from personal_agent.memory_bridge import find_groundcheck_db

        db_path = find_groundcheck_db()
    except Exception:
        return None
    if not db_path:
        return None

    lowered = [str(p or "").strip().lower() for p in phrases if str(p or "").strip()]
    if not lowered:
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        where = " OR ".join("lower(text) LIKE ?" for _ in lowered)
        params = [f"%{p}%" for p in lowered] + [max(1, int(limit))]
        rows = conn.execute(
            f"""
            SELECT id, text, timestamp
            FROM memories
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        for row in rows:
            text = str(row["text"] or "").strip()
            if text:
                return str(row["id"]), text
    except Exception:
        return None
    finally:
        conn.close()
    return None


def _try_answer_workplan_question(
    message: str,
    *,
    engine: Any = None,
    thread_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Deterministic answer path for numbered work-plan item questions."""
    q = str(message or "").strip()
    if not q:
        return None
    ql = q.lower()
    if not any(k in ql for k in ("work plan", "plan item", "plan items", " item ", "items ", "number ")):
        return None

    loaded = _load_latest_workplan_from_groundcheck()
    if not loaded and engine is not None:
        loaded = _load_latest_workplan_from_crt_memory(engine, thread_id=thread_id)
    if not loaded:
        return None
    source_id, source_text, items = loaded
    if not items:
        return None

    explicit_targets = [int(n) for n in re.findall(r"(?:item|number)\s*(\d+)", ql)]
    numeric_targets = []
    for n in re.findall(r"\b\d+\b", ql):
        try:
            iv = int(n)
        except Exception:
            continue
        if iv in items:
            numeric_targets.append(iv)

    requested = [n for n in explicit_targets if n in items]
    if not requested:
        requested = numeric_targets
    requested = list(dict.fromkeys(requested))  # preserve order, dedupe

    if "next" in ql and requested:
        pivot = requested[-1]
        higher = sorted([n for n in items.keys() if n > pivot])
        if higher:
            nxt = higher[0]
            return {
                "answer": f"Item {nxt}: {items[nxt]}.",
                "source_memory_id": source_id,
                "source_text": source_text,
                "items": {str(k): v for k, v in sorted(items.items())},
            }

    summary_like = (
        "summarize" in ql
        or "summary" in ql
        or ("plan items" in ql and len(requested) >= 2)
        or ("all" in ql and "item" in ql)
    )

    if not requested and summary_like:
        requested = sorted(items.keys())
    if not requested:
        return None

    if "just the label" in ql and len(requested) == 1:
        answer = items[requested[0]]
    elif len(requested) == 1:
        n = requested[0]
        answer = f"Item {n}: {items[n]}."
    else:
        parts = [f"Item {n}: {items[n]}" for n in requested if n in items]
        answer = "; ".join(parts) + "."

    return {
        "answer": answer,
        "source_memory_id": source_id,
        "source_text": source_text,
        "items": {str(k): v for k, v in sorted(items.items())},
    }


def _try_answer_mcp_tools_question(message: str) -> Optional[Dict[str, Any]]:
    """Deterministic answer path for MCP tools expansion memory queries."""
    q = str(message or "").strip()
    if not q:
        return None
    ql = q.lower()
    if not ("mcp" in ql and "tool" in ql):
        return None

    loaded = _load_latest_groundcheck_memory_by_phrase(
        ("mcp tools expansion ideas", "new tools to build"),
        limit=8,
    )
    if not loaded:
        return None
    source_id, source_text = loaded

    tools = re.findall(r"\b(?:cogniforge|crt)_[a-z0-9_]+\b", source_text.lower())
    tool_list: List[str] = []
    for t in tools:
        if t not in tool_list:
            tool_list.append(t)

    if not tool_list:
        return None

    picked: Optional[str] = None
    if any(k in ql for k in ("topic", "rising", "fading", "drift")) and "crt_topic_drift" in tool_list:
        picked = "crt_topic_drift"
    elif "code context" in ql and "crt_search_code_context" in tool_list:
        picked = "crt_search_code_context"
    elif "project memory" in ql and "crt_project_memory" in tool_list:
        picked = "crt_project_memory"

    if picked is None:
        picked = tool_list[0]

    if any(k in ql for k in ("one tool", "name one", "just one", "single")):
        answer = picked
    else:
        answer = ", ".join(tool_list)

    return {
        "answer": answer,
        "source_memory_id": source_id,
        "source_text": source_text,
        "tools": tool_list,
    }


def _load_doc_text(doc_map: Dict[str, Any], doc_id: str) -> str:
    info = doc_map.get(doc_id)
    if not info:
        return ""
    path = info.get("path")
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")  # type: ignore[arg-type]
    except Exception:
        return ""


def _score_snippet(snippet: str, q_words: List[str]) -> float:
    s = snippet.lower()
    score = 0.0
    for w in q_words:
        if not w:
            continue
        if w in s:
            score += 1.0
    score *= 1.0 / max(1.0, (len(snippet) / 800.0))
    return score


def _answer_from_docs(
    query: str,
    doc_map: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    q = (query or "").strip()
    ql = q.lower()
    q_words = [w for w in re.split(r"[^a-z0-9_]+", ql) if len(w) >= 3]

    doc_ids = [
        "how_it_works",
        "crt_whitepaper",
        "crt_quick_reference",
        "project_summary",
        "crt_dashboard_guide",
        "architecture",
        "functional_spec",
    ]

    candidates: List[Tuple[float, str, str]] = []
    for did in doc_ids:
        txt = _load_doc_text(doc_map, did)
        if not txt:
            continue
        parts = [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
        for p in parts:
            if len(p) < 60:
                continue
            if len(p) > 1600:
                p = p[:1600] + "\u2026"
            sc = _score_snippet(p, q_words)
            if sc <= 0:
                continue
            candidates.append((sc, did, p))

    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:6]

    lines: List[str] = []
    lines.append("This is a design/spec explanation (doc-grounded), not a personal memory claim.")
    lines.append("")
    lines.append(f"Question: {q}")
    lines.append("")

    if not top:
        lines.append("I could not find a relevant section in the local docs set.")
        lines.append(
            'Try asking about a specific component (e.g., "reconstruction gates", '
            '"contradiction ledger", "trust-weighted memories").'
        )
        return "\n".join(lines), []

    prompt_items: List[Dict[str, Any]] = []
    for i, (_sc, did, snippet) in enumerate(top, start=1):
        title = str((doc_map.get(did) or {}).get("title") or did)
        lines.append(f"{i}. From {title}:")
        lines.append(snippet)
        lines.append("")
        prompt_items.append(
            {
                "memory_id": f"doc:{did}",
                "text": f"DOC[{did}]: {snippet}",
                "source": "docs",
                "trust": None,
                "confidence": None,
            }
        )

    lines.append(
        "If you want, tell me which part to go deeper on "
        "(gates, memory, ledger, coherence), and I\u2019ll expand that section."
    )
    return "\n".join(lines).strip(), prompt_items
