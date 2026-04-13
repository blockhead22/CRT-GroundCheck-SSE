from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synthesis / sentiment helpers
# ---------------------------------------------------------------------------

def _is_synthesis_query(engine: "CRTEnhancedRAG", text: str) -> bool:
    """True if the user asks to synthesize/summarize multiple facts.

    Sprint 9: delegates to belief_synthesis.classify_synthesis_query() which
    covers thematic, trajectory, and contradiction-aware patterns.
    Keeps legacy patterns as fallback for backward compatibility.
    """
    from personal_agent.belief_synthesis import classify_synthesis_query
    return classify_synthesis_query(text) is not None


def _detect_sentiment_contradiction(
    engine: "CRTEnhancedRAG",
    user_query: str,
    retrieved: List[Tuple[Any, float]],
) -> Optional[str]:
    """Detect implicit contradictions in sentiment/intent within retrieved memories.

    For example:
    - Query: "Am I happy at TechCorp?"
    - Memories: ["I just got promoted at TechCorp", "I'm thinking about changing jobs"]
    - Result: "You seem to have mixed feelings - you got promoted but are considering leaving"
    """
    if not retrieved:
        return None

    query_lower = user_query.lower()

    # Detect queries asking about sentiment/happiness/satisfaction
    if not any(word in query_lower for word in ["happy", "satisfied", "feel", "enjoy", "like"]):
        return None

    # Look for contradictory signals in retrieved memories
    positive_signals = []
    negative_signals = []

    for mem, _score in retrieved[:10]:
        text = mem.text.lower()

        # Positive signals
        if any(word in text for word in ["promoted", "promotion", "excited", "love", "great", "happy", "enjoy"]):
            positive_signals.append(mem.text)

        # Negative signals
        if any(phrase in text for phrase in ["changing jobs", "looking for", "thinking about leaving", "quit", "frustrated", "unhappy"]):
            negative_signals.append(mem.text)

    # If we have both positive and negative signals, surface the contradiction
    if positive_signals and negative_signals:
        answer_parts = ["I notice some mixed signals:"]
        if positive_signals:
            answer_parts.append(f"  Positive: {positive_signals[0]}")
        if negative_signals:
            answer_parts.append(f"  Concerning: {negative_signals[0]}")
        answer_parts.append("\nCan you help me understand what's really going on?")
        return "\n".join(answer_parts)

    return None


# ---------------------------------------------------------------------------
# Copilot GroundCheck Context Bridge
# ---------------------------------------------------------------------------

_COPILOT_QUERY_PATTERNS = (
    "copilot", "what is copilot", "copilot doing", "copilot context",
    "copilot memories", "copilot working on", "copilot session",
    "what does copilot", "copilot know", "copilot remember",
    "copilot stored", "copilot learned", "groundcheck mcp",
    "mcp memories", "mcp context", "what has been stored",
    "what have you stored", "what's in groundcheck",
    "whats in groundcheck", "vscode context", "vs code context",
)


def _is_copilot_context_query(engine: "CRTEnhancedRAG", text: str) -> bool:
    """True if the user is asking about Copilot / GroundCheck MCP context."""
    t = (text or "").strip().lower()
    return any(p in t for p in _COPILOT_QUERY_PATTERNS)


def _fetch_copilot_context(engine: "CRTEnhancedRAG", query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Read recent memories from the GroundCheck MCP database (Copilot's memory).

    Returns a list of dicts with keys: text, trust, source, namespace,
    thread_id, timestamp, created_at.
    """
    import sqlite3 as _sqlite3
    from pathlib import Path as _Path
    import os as _os

    candidates = [
        _Path(_os.environ.get("GROUNDCHECK_DB", "")) if _os.environ.get("GROUNDCHECK_DB") else None,
        _Path("D:/groundcheck/.groundcheck/memory.db"),
        _Path("../.groundcheck/memory.db"),
        _Path(".groundcheck/memory.db"),
    ]
    db_path = None
    for p in candidates:
        if p and p.is_file():
            db_path = p
            break
    if not db_path:
        logger.warning("[COPILOT_CTX] GroundCheck MCP database not found")
        return []

    try:
        conn = _sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = _sqlite3.Row

        # Check for namespace column
        col_names = {r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()}
        ns_col = "namespace" if "namespace" in col_names else "'default' as namespace"

        rows = conn.execute(
            f"SELECT text, trust, source, {ns_col}, thread_id, timestamp, created_at "
            f"FROM memories ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

        results = []
        for r in rows:
            results.append({
                "text": r["text"],
                "trust": r["trust"],
                "source": r["source"] or "unknown",
                "namespace": r["namespace"] if "namespace" in col_names else "default",
                "thread_id": r["thread_id"],
                "timestamp": r["timestamp"],
                "created_at": r["created_at"] if "created_at" in col_names else None,
            })
        conn.close()
        logger.info("[COPILOT_CTX] Fetched %d memories from MCP database", len(results))
        return results
    except Exception as e:
        logger.warning("[COPILOT_CTX] Failed to read MCP database: %s", e)
        return []


# ---------------------------------------------------------------------------
# Web Search Bridge  -  DuckDuckGo search for real-time information
# ---------------------------------------------------------------------------

_WEB_SEARCH_PATTERNS = (
    "search for", "search the web", "search duckduckgo", "search ddg",
    "look up", "look it up", "find out about",
    "using duckduckgo", "with duckduckgo", "via duckduckgo",
    "use duckduckgo", "use duck duck go",
    "duckduckgo", "duck duck go",
    "using web", "can you research", "research if",
    "latest news", "recent news", "current news", "what happened",
    "what's happening", "whats happening", "breaking news",
    "state of the union", "election results", "weather in", "weather today",
    "weather forecast", "weather tomorrow",
    "score of", "price of", "stock price", "who won",
    "search online", "web search", "can you search",
    "find me", "find information",
    "today's news", "news about", "news on",
    # Direct URL fetch patterns
    "http://", "https://",
    "read http", "read https", "fetch http", "fetch https",
    "open http", "open https", "visit http", "visit https",
    "go to http", "go to https",
)

_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)


def _is_web_search_query(engine: "CRTEnhancedRAG", text: str) -> bool:
    """True if the user is asking for a web search / real-time information."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # Don't trigger on meta-questions about the search tool itself
    if "how does" in t and "search" in t:
        return False
    return any(p in t for p in _WEB_SEARCH_PATTERNS)


def _extract_search_query(engine: "CRTEnhancedRAG", text: str) -> str:
    """Extract the actual search query from the user's message.

    Strips common prefixes like 'search for', 'look up', etc.
    """
    t = (text or "").strip()
    tl = t.lower()
    prefixes = [
        "search for", "search the web for", "search duckduckgo for",
        "search ddg for", "look up", "google", "find out about",
        "can you search for", "can you search", "can you look up",
        "can you research if", "can you research", "research if", "research",
        "search online for", "web search for", "web search",
        "use duckduckgo to search for", "use duck duck go to search for",
        "use duckduckgo", "use duck duck go",
        "find me", "find information about", "find information on",
    ]
    for prefix in prefixes:
        if tl.startswith(prefix):
            t = t[len(prefix):].strip().lstrip(":")
            tl = t.lower()
            break
    # Remove tool-instruction suffixes while preserving the actual topic.
    t = re.sub(
        r"^\s*using\s+web\s*(?:,?\s*and\s+duck\s*duck\s*go)?\s*,?\s*can\s+you\s+"
        r"(?:research|check|look\s+up)\s*(?:if)?\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b(using|with|via)\s+duck\s*duck\s*go\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(using|with|via)\s+duckduckgo\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip(" .,:;!?")
    # If no prefix matched, use the full text as the search query
    return t


def _fetch_url_content(engine: "CRTEnhancedRAG", url: str) -> List[Dict[str, Any]]:
    """Fetch and return content from a direct URL."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        # Strip HTML tags for plain text
        text = re.sub(r"<[^>]+>", "", content)
        text = re.sub(r"\s+", " ", text).strip()[:8000]
        logger.info("[URL_FETCH] %s -> %d chars", url, len(text))
        return [{"title": url, "url": url, "snippet": text}]
    except Exception as e:
        logger.warning("[URL_FETCH] Failed to fetch %s: %s", url, e)
        return []


def _run_web_search(engine: "CRTEnhancedRAG", query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Run a DuckDuckGo web search (or direct URL fetch) and return results.

    If the query contains a URL, fetches that URL directly instead of searching.
    Uses multi-angle research mode for comprehensive, balanced results.
    Returns a list of dicts with keys: title, url, snippet.
    """
    url_match = _URL_RE.search(query)
    if url_match:
        return _fetch_url_content(engine, url_match.group(0))

    try:
        from personal_agent.web_search import WebSearchTool
        searcher = WebSearchTool(max_results=max_results)
        response = searcher.research(query, max_results=max_results)
        if response.error:
            logger.warning("[WEB_SEARCH] Search error: %s", response.error)
            return []
        results = []
        for r in response.results:
            results.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
            })
        logger.info("[WEB_SEARCH] '%s' -> %d results (research mode)", query, len(results))
        return results
    except Exception as e:
        logger.warning("[WEB_SEARCH] Failed: %s", e)
        return []


def _build_web_evidence_packet(engine: "CRTEnhancedRAG", query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a citation-bearing evidence packet from web search results."""
    try:
        from datetime import datetime
        from personal_agent.evidence_packet import Citation, EvidencePacket

        citations: List[Citation] = []
        for result in results[:10]:
            url = str(result.get("url") or result.get("href") or "").strip()
            snippet = str(result.get("snippet") or result.get("body") or "").strip()
            if not url or not snippet:
                continue

            quote = re.sub(r"\s+", " ", snippet).strip()
            if len(quote) > 260:
                quote = quote[:257].rstrip() + "..."

            citations.append(
                Citation(
                    quote_text=quote,
                    source_url=url,
                    char_offset=(0, min(len(quote), 260)),
                    fetched_at=datetime.now(),
                    confidence=0.72,
                )
            )

        packet = EvidencePacket.create(
            query=query,
            summary="",
            citations=citations,
        )
        return packet.to_dict()
    except Exception as e:
        logger.warning("[WEB_SEARCH] Failed to build evidence packet: %s", e)
        return {
            "packet_id": None,
            "query": query,
            "summary": "",
            "citations": [],
            "created_at": None,
            "trust": 0.4,
            "lane": "notes",
        }


def _format_web_fetch_failed_answer(engine: "CRTEnhancedRAG", query: str) -> str:
    """Explicit failure response for real-time web queries."""
    q = (query or "").strip() or "that query"
    return (
        f"Web fetch failed for \"{q}\", so I cannot provide a real-time answer with citations right now. "
        "Please retry in a moment."
    )


def _enforce_web_answer_policy(
    engine: "CRTEnhancedRAG",
    answer: str,
    web_results: List[Dict[str, Any]],
    evidence_packet: Optional[Dict[str, Any]],
) -> str:
    """Ensure web answers include citations and a source list."""
    citations = (evidence_packet or {}).get("citations") or []
    if not citations:
        return _format_web_fetch_failed_answer(
            engine,
            (evidence_packet or {}).get("query") or "",
        )

    out = (answer or "").strip()
    if not out:
        out = "I fetched web results but could not synthesize a reliable summary."

    if not re.search(r"\[\d+\]", out):
        out = f"{out} [1]"

    if "sources:" not in out.lower():
        lines: List[str] = []
        for i, citation in enumerate(citations[:6], start=1):
            url = str((citation or {}).get("source_url") or "").strip()
            if not url:
                continue
            title = ""
            if i - 1 < len(web_results):
                title = str((web_results[i - 1] or {}).get("title") or "").strip()
            if title:
                lines.append(f"[{i}] {title} - {url}")
            else:
                lines.append(f"[{i}] {url}")
        if lines:
            out = f"{out.rstrip()}\n\nSources:\n" + "\n".join(lines)

    return out


def _sanitize_web_mode_answer(engine: "CRTEnhancedRAG", answer: str) -> str:
    """Remove memory-framed phrasing from web-mode responses."""
    out = str(answer or "").strip()
    if not out:
        return out

    replacements = [
        (r"(?i)\byes,\s*according to (?:my|the)\s+memory\b", "Yes, based on web results"),
        (r"(?i)\baccording to (?:my|the)\s+memory\b", "Based on web results"),
        (r"(?i)\bi retrieved the following from your memory:\s*", ""),
        (r"(?i)\bthe answer to that query was\b", "The current web evidence indicates"),
    ]
    for pattern, repl in replacements:
        out = re.sub(pattern, repl, out)
    return out.strip()


def _is_capability_connector_query(engine: "CRTEnhancedRAG", query: str) -> bool:
    """True for binary compatibility questions like connector/input support."""
    q = str(query or "").strip().lower()
    if not q:
        return False
    has_capability = any(k in q for k in ("can ", "does ", "support", "use ", "work with", "accept", "input"))
    has_connector = any(
        k in q for k in ("3.5", "3.5mm", "3.5 mm", "jack", "connector", "lav", "lavalier", "trs", "trrs")
    )
    return has_capability and has_connector


def _build_web_fulfillment_answer(
    engine: "CRTEnhancedRAG",
    *,
    query: str,
    web_results: List[Dict[str, Any]],
) -> Optional[str]:
    """Build a deterministic answer for binary web compatibility questions.

    This avoids hallucinated memory framing and explicitly returns yes/no/unclear
    based on retrieved snippets.
    """
    if not _is_capability_connector_query(engine, query):
        return None
    if not web_results:
        return None

    ql = str(query or "").lower()
    focus_transmitter = any(
        k in ql for k in ("transmitter", "actual mic part", "on the mic", "not the receiver")
    )

    yes_hits: List[Tuple[int, str, str, bool]] = []
    no_hits: List[Tuple[int, str, str, bool]] = []
    for idx, result in enumerate((web_results or [])[:6], start=1):
        title = str((result or {}).get("title") or "").strip()
        snippet = str((result or {}).get("snippet") or "").strip()
        blob = f"{title} {snippet}".lower()
        if not blob.strip():
            continue

        has_35 = bool(re.search(r"\b3\.?5\s*mm\b|\b3\.?5mm\b", blob))
        has_lav_or_mic = any(k in blob for k in ("lav", "lavalier", "microphone", "mic"))
        has_input = any(k in blob for k in ("input", "jack", "port", "connector", "plug", "supports", "support"))
        tx_side = any(k in blob for k in ("transmitter", "tx", "mic body", "actual mic", "on the mic"))
        rx_only = ("receiver" in blob) and (not tx_side)

        neg = any(
            p in blob
            for p in (
                "does not support",
                "doesn't support",
                "not supported",
                "no 3.5",
                "without 3.5",
                "no 3.5mm",
                "not compatible",
            )
        )

        if neg and (has_35 or has_lav_or_mic):
            no_hits.append((idx, title, snippet, tx_side))
            continue

        if has_35 and has_lav_or_mic and has_input:
            if rx_only and focus_transmitter:
                # Receiver-only mention does not satisfy a transmitter-specific ask.
                no_hits.append((idx, title, snippet, tx_side))
            else:
                yes_hits.append((idx, title, snippet, tx_side))

    yes_tx_hits = [h for h in yes_hits if h[3]]

    lines: List[str] = []
    if focus_transmitter and yes_hits and not yes_tx_hits:
        lines.append(
            "I found web evidence for 3.5 mm lav compatibility, but the snippets do not clearly prove "
            "that this is on the transmitter (not the receiver)."
        )
        chosen = yes_hits[:2]
    elif yes_hits and len(yes_hits) >= max(1, len(no_hits)):
        lines.append("Yes. Based on current web results, this appears to support a 3.5 mm lav input.")
        chosen = (yes_tx_hits[:2] if (focus_transmitter and yes_tx_hits) else yes_hits[:2])
    elif no_hits and len(no_hits) > len(yes_hits):
        lines.append("No. Current web snippets indicate this does not support the requested 3.5 mm lav input.")
        chosen = no_hits[:2]
    else:
        lines.append(
            "I could not verify this conclusively from the current web snippets. "
            "I need clearer source wording about connector type and input side."
        )
        chosen = (yes_hits + no_hits)[:2]

    for idx, _title, snippet, _tx_side in chosen:
        s = re.sub(r"\s+", " ", str(snippet or "")).strip()
        if not s:
            continue
        if len(s) > 180:
            s = s[:177].rstrip() + "..."
        lines.append(f"- [{idx}] {s}")

    return "\n".join(lines).strip()
