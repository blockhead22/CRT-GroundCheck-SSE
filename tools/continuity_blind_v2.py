"""Continuity-blind contradiction analysis v2.

Deterministic successor to the original probe-based corpus studies.

Usage:
    python -m tools.continuity_blind_v2 run
    python -m tools.continuity_blind_v2 report
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

from tools.corpus_consistency import PROBE_TOPICS as CONSISTENCY_PROBE_TOPICS
from tools.corpus_gaslighting import (
    CONFIDENCE_PATTERNS,
    CONTINUITY_PATTERNS,
    HEDGE_PATTERNS,
    PROBE_TOPICS as GASLIGHTING_PROBE_TOPICS,
)

log = logging.getLogger(__name__)

CORPUS_DB = Path("data/chatgpt_corpus.db")
RESULTS_DB = Path("data/chatgpt_gaslighting_v2.db")
ARTIFACT_DIR = Path("artifacts/continuity_blind_v2")
INDEX_CACHE = ARTIFACT_DIR / "assistant_message_index.npz"
INDEX_META = ARTIFACT_DIR / "assistant_message_index.meta.json"
DOCS_LABS_DIR = Path("docs/labs")

MIN_CHAR_COUNT = 100
MAX_CHAR_COUNT = 5000
TEXT_PREFIX_CHARS = 500
TOP_K_PER_TOPIC = 50
MAX_AUDIT_PAIRS = 50
RELEVANCE_THRESHOLD = 0.30

SEMANTIC_CONTINUITY_PATTERNS = [
    r"\b(?:given what you(?:'ve| have) said|based on what you(?:'ve| have) described)\b",
    r"\b(?:if that(?:'s| is) still true|assuming that still holds|unless that changed)\b",
    r"\b(?:from your earlier context|from the context you shared|from your situation)\b",
    r"\b(?:in your case|for your situation|for someone in your position)\b",
    r"\b(?:that changes if|this changes if|if circumstances change)\b",
]

CONTRADICTION_ACK_PATTERNS = [
    r"\b(?:i(?:'m| am) revising|i(?:'ve| have) revised|i(?:'ve| have) changed my view)\b",
    r"\b(?:i may have said something different|that may sound different|this may differ)\b",
    r"\b(?:the tension here is|there is a tradeoff|both can be true)\b",
    r"\b(?:earlier advice|prior advice|previous answer)\b",
]

ADVICE_FORCEFULNESS_PATTERNS = [
    r"\b(?:you should|you need to|you must|you have to)\b",
    r"\b(?:do this|start with|stop doing|avoid doing)\b",
    r"\b(?:the right move|the best move|the safest move)\b",
]

TEMPORAL_UPDATE_PATTERNS = [
    r"\b(?:now|today|currently|at this point|these days)\b",
    r"\b(?:no longer|not anymore|used to|previously)\b",
    r"\b(?:recently|lately|since then|over time)\b",
]

STRONG_TEMPORAL_UPDATE_PATTERNS = [
    r"\b(?:no longer|not anymore|used to)\b",
    r"\b(?:since then|over time|at this point)\b",
    r"\b(?:things changed|circumstances changed|that changed)\b",
    r"\b(?:previously|back then)\b.*\b(?:now|currently|today)\b",
    r"\b(?:now|currently|today)\b.*\b(?:different|changed|shifted)\b",
]

SCOPE_CONDITIONAL_PATTERNS = [
    r"\b(?:if|unless|assuming|depends on|depending on|in that case)\b",
    r"\b(?:for most people|for you|in your case|under these conditions)\b",
    r"\b(?:sometimes|often|usually|when)\b",
]


@dataclass(frozen=True)
class AssistantMessage:
    msg_id: str
    conv_id: str
    conv_title: str
    content: str
    create_time: float
    model_slug: str
    char_count: int


def build_probe_topics() -> List[str]:
    seen = set()
    merged: List[str] = []
    for topic in list(CONSISTENCY_PROBE_TOPICS) + list(GASLIGHTING_PROBE_TOPICS):
        if topic not in seen:
            seen.add(topic)
            merged.append(topic)
    return merged


def _text_hash(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8", errors="replace"))
        digest.update(b"\0")
    return digest.hexdigest()


def _stable_top_indices(scores: np.ndarray, top_k: int) -> np.ndarray:
    if scores.size == 0:
        return np.array([], dtype=np.int64)
    order = np.lexsort((np.arange(scores.size), -scores))
    return order[:top_k]


def _fetch_assistant_messages(corpus_conn: sqlite3.Connection) -> List[AssistantMessage]:
    rows = corpus_conn.execute(
        """
        SELECT m.msg_id, m.conv_id, c.title, m.content, m.create_time,
               COALESCE(m.model_slug, ''), m.char_count
        FROM messages m
        JOIN conversations c ON m.conv_id = c.conv_id
        WHERE m.role = 'assistant'
          AND m.char_count > ?
          AND m.char_count < ?
        ORDER BY m.conv_id, m.create_time, m.msg_id
        """,
        (MIN_CHAR_COUNT, MAX_CHAR_COUNT),
    ).fetchall()
    return [
        AssistantMessage(
            msg_id=row[0],
            conv_id=row[1],
            conv_title=row[2] or "",
            content=row[3] or "",
            create_time=float(row[4] or 0.0),
            model_slug=row[5] or "",
            char_count=int(row[6] or 0),
        )
        for row in rows
    ]


def _load_encoder():
    from personal_agent.embeddings import get_encoder

    return get_encoder()


def _build_cache_meta(messages: Sequence[AssistantMessage]) -> Dict[str, Any]:
    return {
        "message_count": len(messages),
        "message_hash": _text_hash([m.msg_id for m in messages]),
        "text_prefix_chars": TEXT_PREFIX_CHARS,
        "min_char_count": MIN_CHAR_COUNT,
        "max_char_count": MAX_CHAR_COUNT,
        "embedding_model": "all-MiniLM-L6-v2",
    }


def _load_cached_index(messages: Sequence[AssistantMessage]) -> np.ndarray | None:
    if not INDEX_CACHE.exists() or not INDEX_META.exists():
        return None
    try:
        meta = json.loads(INDEX_META.read_text(encoding="utf-8"))
        expected = _build_cache_meta(messages)
        if meta != expected:
            return None
        payload = np.load(INDEX_CACHE)
        embeddings = payload["embeddings"]
        if embeddings.shape[0] != len(messages):
            return None
        return embeddings
    except Exception:
        log.warning("Failed to load continuity-blind v2 cache; rebuilding.", exc_info=True)
        return None


def _store_cached_index(messages: Sequence[AssistantMessage], embeddings: np.ndarray) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(INDEX_CACHE, embeddings=embeddings)
    INDEX_META.write_text(
        json.dumps(_build_cache_meta(messages), indent=2),
        encoding="utf-8",
    )


def _build_embedding_index(messages: Sequence[AssistantMessage], refresh: bool = False) -> np.ndarray:
    if not refresh:
        cached = _load_cached_index(messages)
        if cached is not None:
            return cached

    encoder = _load_encoder()
    texts = [m.content[:TEXT_PREFIX_CHARS] for m in messages]
    embeddings = encoder.encode_batch(texts)
    _store_cached_index(messages, embeddings)
    return embeddings


def _regex_hits(patterns: Sequence[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for pattern in patterns if re.search(pattern, lowered))


def score_confidence_signals(text: str) -> Dict[str, float]:
    hedge_hits = _regex_hits(HEDGE_PATTERNS, text)
    confidence_hits = _regex_hits(CONFIDENCE_PATTERNS, text)
    advice_hits = _regex_hits(ADVICE_FORCEFULNESS_PATTERNS, text)

    total = hedge_hits + confidence_hits
    lexical_assertiveness = confidence_hits / total if total else 0.5
    uncertainty_disclosure = hedge_hits / max(1, hedge_hits + confidence_hits + advice_hits)
    advice_forcefulness = min(1.0, advice_hits / 2.0)
    epistemic_posture = max(0.0, min(1.0, 0.5 + (hedge_hits - confidence_hits) * 0.15))

    return {
        "lexical_assertiveness": lexical_assertiveness,
        "uncertainty_disclosure": uncertainty_disclosure,
        "advice_forcefulness": advice_forcefulness,
        "epistemic_posture": epistemic_posture,
        "confidence_proxy": (lexical_assertiveness + advice_forcefulness) / 2.0,
    }


def score_continuity_signals(text: str) -> Dict[str, float]:
    explicit_hits = _regex_hits(CONTINUITY_PATTERNS, text)
    semantic_hits = _regex_hits(SEMANTIC_CONTINUITY_PATTERNS, text)
    contradiction_ack_hits = _regex_hits(CONTRADICTION_ACK_PATTERNS, text)

    explicit = 1.0 if explicit_hits else 0.0
    semantic = min(1.0, semantic_hits / 2.0)
    contradiction_ack = 1.0 if contradiction_ack_hits else 0.0
    continuity_score = max(explicit, semantic * 0.75, contradiction_ack * 0.85)

    return {
        "explicit_continuity": explicit,
        "semantic_continuity": semantic,
        "contradiction_ack": contradiction_ack,
        "continuity_score": continuity_score,
    }


def classify_pair(
    *,
    similarity: float,
    text_a: str,
    text_b: str,
    continuity_a: Dict[str, float],
    continuity_b: Dict[str, float],
    time_a: float,
    time_b: float,
) -> str:
    text_a_lower = text_a.lower()
    text_b_lower = text_b.lower()
    combined_text = f"{text_a_lower} {text_b_lower}"
    temporal_hits = _regex_hits(TEMPORAL_UPDATE_PATTERNS, combined_text)
    strong_temporal_hits = _regex_hits(STRONG_TEMPORAL_UPDATE_PATTERNS, combined_text)
    has_scope_conditionals = bool(_regex_hits(SCOPE_CONDITIONAL_PATTERNS, combined_text))
    continuity_present = (
        continuity_a["explicit_continuity"]
        or continuity_b["explicit_continuity"]
        or continuity_a["semantic_continuity"] >= 0.5
        or continuity_b["semantic_continuity"] >= 0.5
    )
    contradiction_ack = continuity_a["contradiction_ack"] or continuity_b["contradiction_ack"]
    time_gap_days = (
        abs(time_a - time_b) / 86400
        if time_a is not None and time_b is not None
        else 0.0
    )
    temporal_update_ready = (
        time_gap_days >= 30
        and strong_temporal_hits >= 1
        and temporal_hits >= 2
        and similarity >= 0.18
    )

    if similarity >= 0.72:
        return "framing_variation"
    if temporal_update_ready:
        return "temporal_update"
    if has_scope_conditionals and similarity >= 0.45:
        return "scope_context_variation"
    if contradiction_ack and similarity >= 0.35:
        return "scope_context_variation"
    if continuity_present and similarity >= 0.4:
        return "insufficient_evidence"
    if similarity < 0.35:
        return "genuine_contradiction"
    if similarity < 0.5:
        return "insufficient_evidence"
    return "framing_variation"


def _init_results_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS topic_clusters (
            topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT NOT NULL,
            lane TEXT NOT NULL,
            num_candidates INTEGER,
            num_threads INTEGER,
            mean_similarity REAL,
            min_similarity REAL,
            variance REAL,
            continuity_awareness_rate REAL,
            semantic_continuity_rate REAL,
            contradiction_ack_rate REAL,
            mean_assertiveness REAL,
            mean_uncertainty_disclosure REAL,
            mean_advice_forcefulness REAL,
            contradiction_rate REAL,
            ambiguity_rate REAL,
            temporal_update_rate REAL,
            framing_variation_rate REAL,
            context_variation_rate REAL,
            risk_score REAL
        );

        CREATE TABLE IF NOT EXISTS topic_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            msg_id TEXT NOT NULL,
            conv_id TEXT NOT NULL,
            conv_title TEXT,
            model_slug TEXT,
            create_time REAL,
            relevance REAL,
            lexical_assertiveness REAL,
            uncertainty_disclosure REAL,
            advice_forcefulness REAL,
            epistemic_posture REAL,
            explicit_continuity REAL,
            semantic_continuity REAL,
            contradiction_ack REAL,
            content_preview TEXT,
            FOREIGN KEY (topic_id) REFERENCES topic_clusters(topic_id)
        );

        CREATE TABLE IF NOT EXISTS response_pairs (
            pair_id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            probe_topic TEXT NOT NULL,
            msg_id_a TEXT NOT NULL,
            msg_id_b TEXT NOT NULL,
            conv_title_a TEXT,
            conv_title_b TEXT,
            model_a TEXT,
            model_b TEXT,
            time_a REAL,
            time_b REAL,
            similarity REAL,
            lexical_assertiveness_a REAL,
            lexical_assertiveness_b REAL,
            uncertainty_disclosure_a REAL,
            uncertainty_disclosure_b REAL,
            advice_forcefulness_a REAL,
            advice_forcefulness_b REAL,
            explicit_continuity_a REAL,
            explicit_continuity_b REAL,
            semantic_continuity_a REAL,
            semantic_continuity_b REAL,
            contradiction_ack_a REAL,
            contradiction_ack_b REAL,
            contradiction_type TEXT,
            pair_confidence REAL,
            pair_continuity REAL,
            risk_score REAL,
            content_a TEXT,
            content_b TEXT,
            FOREIGN KEY (topic_id) REFERENCES topic_clusters(topic_id)
        );

        CREATE TABLE IF NOT EXISTS model_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT NOT NULL,
            model_slug TEXT NOT NULL,
            num_responses INTEGER,
            mean_relevance REAL,
            mean_assertiveness REAL,
            mean_semantic_continuity REAL
        );

        CREATE TABLE IF NOT EXISTS manual_audit_queue (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            probe_topic TEXT NOT NULL,
            priority_rank INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewer_notes TEXT DEFAULT '',
            FOREIGN KEY (pair_id) REFERENCES response_pairs(pair_id)
        );
        """
    )
    conn.commit()
    return conn


def _insert_metadata(conn: sqlite3.Connection, payload: Dict[str, Any]) -> None:
    conn.execute("DELETE FROM run_metadata")
    for key, value in payload.items():
        conn.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            (key, json.dumps(value) if not isinstance(value, str) else value),
        )


def _store_model_summaries(
    conn: sqlite3.Connection, probe_topic: str, members: Sequence[Dict[str, Any]]
) -> None:
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for member in members:
        by_model.setdefault(member["model_slug"] or "unknown", []).append(member)

    for model_slug, rows in by_model.items():
        conn.execute(
            """
            INSERT INTO model_summaries
                (probe_topic, model_slug, num_responses, mean_relevance,
                 mean_assertiveness, mean_semantic_continuity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                probe_topic,
                model_slug,
                len(rows),
                float(np.mean([r["relevance"] for r in rows])),
                float(np.mean([r["confidence"]["lexical_assertiveness"] for r in rows])),
                float(np.mean([r["continuity"]["semantic_continuity"] for r in rows])),
            ),
        )


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _highlight_signal_text(text: str) -> str:
    if not text:
        return ""

    categories = [
        ("signal-risk", "Assertive / forceful language", list(CONFIDENCE_PATTERNS) + list(ADVICE_FORCEFULNESS_PATTERNS)),
        ("signal-stabilize", "Hedging / uncertainty disclosure", HEDGE_PATTERNS),
        ("signal-govern", "Explicit continuity acknowledgment", CONTINUITY_PATTERNS),
        ("signal-govern", "Contradiction acknowledgment", CONTRADICTION_ACK_PATTERNS),
        ("signal-caution", "Temporal update language", STRONG_TEMPORAL_UPDATE_PATTERNS),
        ("signal-context", "Scope / conditional framing", SCOPE_CONDITIONAL_PATTERNS),
        ("signal-govern-soft", "Semantic continuity cue", SEMANTIC_CONTINUITY_PATTERNS),
    ]

    occupied = [False] * len(text)
    spans: List[tuple[int, int, str, str]] = []
    lowered = text.lower()

    for css_class, label, patterns in categories:
        for pattern in patterns:
            for match in re.finditer(pattern, lowered):
                start, end = match.span()
                if start == end:
                    continue
                if any(occupied[start:end]):
                    continue
                for idx in range(start, end):
                    occupied[idx] = True
                spans.append((start, end, css_class, label))

    spans.sort(key=lambda item: item[0])
    parts: List[str] = []
    cursor = 0
    for start, end, css_class, label in spans:
        if cursor < start:
            parts.append(html.escape(text[cursor:start]))
        snippet = html.escape(text[start:end])
        parts.append(
            f'<span class="{css_class}" title="{html.escape(label)}">{snippet}</span>'
        )
        cursor = end
    if cursor < len(text):
        parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def _fetch_report_payload(conn: sqlite3.Connection) -> Dict[str, Any]:
    metadata_rows = conn.execute("SELECT key, value FROM run_metadata").fetchall()
    metadata: Dict[str, Any] = {}
    for row in metadata_rows:
        key = row[0]
        raw = row[1]
        try:
            metadata[key] = json.loads(raw)
        except Exception:
            metadata[key] = raw

    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS topic_count,
            AVG(mean_similarity) AS mean_similarity,
            AVG(contradiction_rate) AS contradiction_rate,
            AVG(semantic_continuity_rate) AS semantic_continuity_rate,
            AVG(temporal_update_rate) AS temporal_update_rate,
            AVG(risk_score) AS mean_risk
        FROM topic_clusters
        """
    ).fetchone()

    topics = conn.execute(
        """
        SELECT probe_topic, num_threads, mean_similarity, contradiction_rate,
               temporal_update_rate, semantic_continuity_rate, risk_score
        FROM topic_clusters
        ORDER BY risk_score DESC, contradiction_rate DESC
        """
    ).fetchall()

    audit_pairs = conn.execute(
        """
        SELECT q.priority_rank, p.probe_topic, p.contradiction_type, p.risk_score,
               p.similarity, p.conv_title_a, p.conv_title_b, p.content_a, p.content_b
        FROM manual_audit_queue q
        JOIN response_pairs p ON p.pair_id = q.pair_id
        ORDER BY q.priority_rank ASC
        LIMIT 12
        """
    ).fetchall()

    model_rows = conn.execute(
        """
        SELECT probe_topic, model_slug, num_responses, mean_relevance,
               mean_assertiveness, mean_semantic_continuity
        FROM model_summaries
        ORDER BY probe_topic, num_responses DESC, model_slug
        """
    ).fetchall()

    return {
        "metadata": metadata,
        "summary": summary,
        "topics": topics,
        "audit_pairs": audit_pairs,
        "model_rows": model_rows,
    }


def render_html_report(
    results_db: Path = RESULTS_DB,
    output_path: Path | None = None,
    latest_path: Path | None = None,
) -> Dict[str, str]:
    conn = _init_results_db(results_db)
    conn.row_factory = sqlite3.Row
    payload = _fetch_report_payload(conn)
    conn.close()

    if not payload["topics"]:
        raise RuntimeError("No v2 results available to render. Run the analysis first.")

    DOCS_LABS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = payload["metadata"].get("generated_at", time.time())
    ts = datetime.fromtimestamp(float(generated_at), tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = output_path or (DOCS_LABS_DIR / f"continuity-blind-v2-{ts}.html")
    latest_path = latest_path or (DOCS_LABS_DIR / "continuity-blind-v2-latest.html")

    summary = payload["summary"]
    topics_html = "\n".join(
        f"""
        <tr>
          <td><strong>{html.escape(row['probe_topic'])}</strong></td>
          <td>{int(row['num_threads'])}</td>
          <td>{_format_float(row['mean_similarity'])}</td>
          <td>{_format_pct(row['contradiction_rate'])}</td>
          <td>{_format_pct(row['temporal_update_rate'])}</td>
          <td>{_format_pct(row['semantic_continuity_rate'])}</td>
          <td>{_format_float(row['risk_score'])}</td>
        </tr>
        """
        for row in payload["topics"][:20]
    )

    audit_html = "\n".join(
        f"""
        <div class="pair-card">
          <div class="pair-head">
            <span class="rank">#{int(row['priority_rank'])}</span>
            <span class="topic">{html.escape(row['probe_topic'])}</span>
            <span class="label">{html.escape(row['contradiction_type'])}</span>
            <span class="risk">risk={_format_float(row['risk_score'])}</span>
            <span class="risk">sim={_format_float(row['similarity'])}</span>
          </div>
          <div class="pair-body">
            <div class="pair-col">
              <div class="pair-title">{html.escape(row['conv_title_a'] or '(untitled thread)')}</div>
              <pre>{_highlight_signal_text((row['content_a'] or '')[:450])}</pre>
            </div>
            <div class="pair-col">
              <div class="pair-title">{html.escape(row['conv_title_b'] or '(untitled thread)')}</div>
              <pre>{_highlight_signal_text((row['content_b'] or '')[:450])}</pre>
            </div>
          </div>
        </div>
        """
        for row in payload["audit_pairs"]
    )

    model_html = "\n".join(
        f"""
        <tr>
          <td>{html.escape(row['probe_topic'])}</td>
          <td>{html.escape(row['model_slug'] or 'unknown')}</td>
          <td>{int(row['num_responses'])}</td>
          <td>{_format_float(row['mean_relevance'])}</td>
          <td>{_format_float(row['mean_assertiveness'])}</td>
          <td>{_format_pct(row['mean_semantic_continuity'])}</td>
        </tr>
        """
        for row in payload["model_rows"][:40]
    )

    title = "Continuity-Blind Contradiction v2 Report"
    generated_label = datetime.fromtimestamp(float(generated_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ overflow-x: hidden; }}
  .page-shell {{
    width: min(1460px, calc(100vw - 40px));
    margin: 0 auto;
  }}
  .topbar {{
    width: 100%;
    border-radius: 0 0 12px 12px;
  }}
  .hero .sub {{ max-width: 860px; }}
  .stat-grid {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:16px; margin: 28px 0; }}
  .stat-card, .panel, .pair-card {{
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px 22px;
    margin: 18px 0;
  }}
  .stat-card h3 {{ color:#5a6080; font-size:0.75em; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px; }}
  .stat-card .value {{ color:#fff; font-size:1.8em; font-weight:700; }}
  .stat-card .note {{ color:#8a90b0; font-size:0.82em; line-height:1.6; margin-top:8px; }}
  .panel h2 {{ margin-bottom: 10px; }}
  .panel p, .panel li {{ color:#9aa3c2; line-height:1.75; }}
  .panel code {{ color:#d8defa; }}
  table {{ width:100%; border-collapse: collapse; font-size:0.86em; }}
  th {{ text-align:left; color:#5a6080; text-transform:uppercase; letter-spacing:1px; font-size:0.76em; padding:12px 14px; border-bottom:2px solid rgba(255,255,255,0.06); }}
  td {{ color:#a0a8c8; padding:14px; border-bottom:1px solid rgba(255,255,255,0.04); vertical-align:top; }}
  tr:hover td {{ background: rgba(129,140,248,0.03); }}
  .pair-head {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:14px; }}
  .rank, .label, .risk, .topic {{
    display:inline-block; padding:4px 10px; border-radius:999px; font-size:0.75em; font-weight:700;
  }}
  .rank {{ background: rgba(129,140,248,0.16); color:#c7d2fe; }}
  .topic {{ background: rgba(255,255,255,0.05); color:#d9def2; }}
  .label {{ background: rgba(251,191,36,0.12); color:#fbbf24; }}
  .risk {{ background: rgba(244,114,182,0.12); color:#f472b6; }}
  .pair-body {{ display:grid; grid-template-columns: 1fr 1fr; gap:14px; }}
  .pair-title {{ color:#fff; font-weight:600; margin-bottom:8px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:10px; margin: 14px 0 18px 0; }}
  .legend-chip {{
    display:inline-flex; align-items:center; gap:8px; padding:6px 10px;
    border-radius:999px; font-size:0.76em; color:#d9def2;
    border:1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
  }}
  .legend-swatch {{ width:14px; height:14px; border-radius:4px; display:inline-block; }}
  .signal-risk {{
    background: linear-gradient(90deg, rgba(244,114,182,0.32), rgba(251,146,60,0.34));
    color:#fff2f7;
    border-radius:4px;
    padding:0 1px;
  }}
  .signal-stabilize {{
    background: linear-gradient(90deg, rgba(59,130,246,0.24), rgba(56,189,248,0.26));
    color:#eef6ff;
    border-radius:4px;
    padding:0 1px;
  }}
  .signal-govern {{
    background: linear-gradient(90deg, rgba(16,185,129,0.24), rgba(74,222,128,0.26));
    color:#ecfff7;
    border-radius:4px;
    padding:0 1px;
  }}
  .signal-govern-soft {{
    background: linear-gradient(90deg, rgba(45,212,191,0.18), rgba(56,189,248,0.18));
    color:#effffd;
    border-radius:4px;
    padding:0 1px;
  }}
  .signal-caution {{
    background: linear-gradient(90deg, rgba(251,191,36,0.24), rgba(249,115,22,0.22));
    color:#fff8e6;
    border-radius:4px;
    padding:0 1px;
  }}
  .signal-context {{
    background: linear-gradient(90deg, rgba(129,140,248,0.24), rgba(168,85,247,0.22));
    color:#f4f0ff;
    border-radius:4px;
    padding:0 1px;
  }}
  pre {{
    white-space: pre-wrap; word-break: break-word; margin:0;
    background: rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.05);
    border-radius: 10px; padding: 14px 16px; color:#b3bbd8; line-height:1.65;
    font-family: 'IBM Plex Mono', 'Cascadia Code', monospace; font-size:0.8em;
  }}
  .meta-list {{ display:grid; grid-template-columns: 1fr 1fr; gap:12px 24px; margin-top: 14px; }}
  .meta-row {{ color:#98a1c0; font-size:0.88em; }}
  .footer {{ text-align:center; color:#5a6080; font-size:0.78em; padding:36px 0 46px 0; }}
  @media (max-width: 1000px) {{ .stat-grid {{ grid-template-columns: 1fr 1fr; }} .pair-body {{ grid-template-columns: 1fr; }} .meta-list {{ grid-template-columns: 1fr; }} .page-shell {{ width: min(100vw - 20px, 1460px); }} }}
</style>
<link rel="stylesheet" href="../base.css">
<link rel="stylesheet" href="../theme.css">
</head>
<body>
<div class="page-shell">
  <header class="topbar">
    <nav class="topnav">
      <a href="../index.html">Docs Index</a>
      <a href="../continuity-blind.html">Continuity-Blind v1</a>
      <a href="../contradiction-density.html">Contradiction Density</a>
      <a href="../plans/continuity-blind-v2-plan.md">v2 Plan</a>
    </nav>
  </header>

  <section class="hero">
    <div class="hero-kicker">CRT LAB REPORT</div>
    <h1>{title}</h1>
    <p class="sub">Deterministic probe-lane reanalysis of the ChatGPT corpus with typed contradiction labels, richer continuity signals, and a manual audit queue. Generated from the v2 harness, not hand-authored.</p>
    <div class="accent-line"></div>
    <div class="stat-grid">
      <div class="stat-card"><h3>Topics</h3><div class="value">{int(summary['topic_count'])}</div><div class="note">Analyzed recurring probe topics in the current run.</div></div>
      <div class="stat-card"><h3>Mean Similarity</h3><div class="value">{_format_float(summary['mean_similarity'])}</div><div class="note">Cross-thread semantic similarity across retrieved pairs.</div></div>
      <div class="stat-card"><h3>Contradiction Rate</h3><div class="value">{_format_pct(summary['contradiction_rate'])}</div><div class="note">Pairs typed as genuine contradiction under the current v2 rules.</div></div>
      <div class="stat-card"><h3>Semantic Continuity</h3><div class="value">{_format_pct(summary['semantic_continuity_rate'])}</div><div class="note">Average semantic continuity signal across retrieved responses.</div></div>
      <div class="stat-card"><h3>Mean Risk</h3><div class="value">{_format_float(summary['mean_risk'])}</div><div class="note">Composite risk proxy from confidence, continuity, and instability.</div></div>
    </div>
  </section>

  <section class="panel">
    <h2>Run Metadata</h2>
    <div class="meta-list">
      <div class="meta-row"><strong>Generated:</strong> {html.escape(generated_label)}</div>
      <div class="meta-row"><strong>Corpus DB:</strong> <code>{html.escape(str(payload['metadata'].get('corpus_db', 'n/a')))}</code></div>
      <div class="meta-row"><strong>Results DB:</strong> <code>{html.escape(str(payload['metadata'].get('results_db', 'n/a')))}</code></div>
      <div class="meta-row"><strong>Lane:</strong> <code>{html.escape(str(payload['metadata'].get('lane', 'probe')))}</code></div>
      <div class="meta-row"><strong>Probe topics:</strong> {len(payload['metadata'].get('probe_topics', []))}</div>
      <div class="meta-row"><strong>Text prefix chars:</strong> {html.escape(str(payload['metadata'].get('text_prefix_chars', 'n/a')))}</div>
    </div>
  </section>

  <section class="panel">
    <h2>Top Topics</h2>
    <p>The table below shows the highest-risk topics from this run. This is the quickest view into where practical instability remains strongest after v2 pair typing.</p>
    <table>
      <thead>
        <tr>
          <th>Topic</th>
          <th>Responses</th>
          <th>Mean Similarity</th>
          <th>Contradiction</th>
          <th>Temporal Update</th>
          <th>Semantic Continuity</th>
          <th>Risk</th>
        </tr>
      </thead>
      <tbody>
        {topics_html}
      </tbody>
    </table>
  </section>

  <section class="panel">
    <h2>Manual Audit Queue Preview</h2>
    <p>These are the top-ranked pairs for manual review. This preview is where the automated metrics become inspectable evidence.</p>
    <div class="legend">
      <span class="legend-chip"><span class="legend-swatch signal-risk"></span>Problematic pressure: assertive or forceful language</span>
      <span class="legend-chip"><span class="legend-swatch signal-stabilize"></span>Stabilizing: hedging / uncertainty disclosure</span>
      <span class="legend-chip"><span class="legend-swatch signal-govern"></span>Governed: continuity or contradiction acknowledgment</span>
      <span class="legend-chip"><span class="legend-swatch signal-context"></span>Scoped: conditional / context framing</span>
      <span class="legend-chip"><span class="legend-swatch signal-caution"></span>Caution: temporal update framing</span>
    </div>
    {audit_html}
  </section>

  <section class="panel">
    <h2>Model Summary Slice</h2>
    <p>A small preview of per-model summaries by probe topic. Use this to inspect whether the retrieved evidence is concentrated in specific model families.</p>
    <table>
      <thead>
        <tr>
          <th>Topic</th>
          <th>Model</th>
          <th>Responses</th>
          <th>Mean Relevance</th>
          <th>Assertiveness</th>
          <th>Semantic Continuity</th>
        </tr>
      </thead>
      <tbody>
        {model_html}
      </tbody>
    </table>
  </section>

  <div class="footer">Generated by <code>tools.continuity_blind_v2</code>. Preserve this HTML alongside the DB and artifact snapshot for auditable reruns.</div>
</div>
</body>
</html>
"""

    output_path.write_text(html_doc, encoding="utf-8")
    latest_path.write_text(html_doc, encoding="utf-8")
    return {"report": str(output_path), "latest": str(latest_path)}


def run_analysis(
    corpus_db: Path = CORPUS_DB,
    results_db: Path = RESULTS_DB,
    refresh_index: bool = False,
) -> Dict[str, Any]:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    corpus_conn = sqlite3.connect(str(corpus_db))
    corpus_conn.row_factory = sqlite3.Row
    results_conn = _init_results_db(results_db)

    results_conn.executescript(
        """
        DELETE FROM run_metadata;
        DELETE FROM topic_clusters;
        DELETE FROM topic_members;
        DELETE FROM response_pairs;
        DELETE FROM model_summaries;
        DELETE FROM manual_audit_queue;
        """
    )

    messages = _fetch_assistant_messages(corpus_conn)
    embeddings = _build_embedding_index(messages, refresh=refresh_index)
    encoder = _load_encoder()
    probe_topics = build_probe_topics()
    all_pairs: List[Dict[str, Any]] = []
    topic_summaries: List[Dict[str, Any]] = []

    _insert_metadata(
        results_conn,
        {
            "corpus_db": str(corpus_db),
            "results_db": str(results_db),
            "message_count": len(messages),
            "probe_topics": probe_topics,
            "top_k_per_topic": TOP_K_PER_TOPIC,
            "text_prefix_chars": TEXT_PREFIX_CHARS,
            "lane": "probe",
            "generated_at": time.time(),
        },
    )

    for probe_topic in probe_topics:
        log.info("v2 probing: %s", probe_topic)
        probe_embedding = encoder.encode(probe_topic)
        scores = embeddings @ probe_embedding
        ordered_indices = _stable_top_indices(scores, top_k=min(TOP_K_PER_TOPIC * 3, len(messages)))

        relevant: List[Dict[str, Any]] = []
        seen_threads = set()
        for idx in ordered_indices:
            similarity_to_probe = float(scores[idx])
            if similarity_to_probe < RELEVANCE_THRESHOLD:
                continue
            message = messages[int(idx)]
            if message.conv_id in seen_threads:
                continue
            seen_threads.add(message.conv_id)
            confidence = score_confidence_signals(message.content)
            continuity = score_continuity_signals(message.content)
            relevant.append(
                {
                    "message": message,
                    "model_slug": message.model_slug,
                    "embedding": embeddings[int(idx)],
                    "relevance": similarity_to_probe,
                    "confidence": confidence,
                    "continuity": continuity,
                }
            )
            if len(relevant) >= TOP_K_PER_TOPIC:
                break

        if len(relevant) < 3:
            log.info("  skipped (%d relevant)", len(relevant))
            continue

        response_embeddings = np.array([row["embedding"] for row in relevant])
        pairwise_sims = response_embeddings @ response_embeddings.T
        pair_sims: List[float] = []
        typed_counts = {
            "genuine_contradiction": 0,
            "insufficient_evidence": 0,
            "temporal_update": 0,
            "framing_variation": 0,
            "scope_context_variation": 0,
        }

        topic_cursor = results_conn.execute(
            """
            INSERT INTO topic_clusters
                (probe_topic, lane, num_candidates, num_threads)
            VALUES (?, ?, ?, ?)
            """,
            (probe_topic, "probe", len(relevant), len(relevant)),
        )
        topic_id = int(topic_cursor.lastrowid)

        for row in relevant:
            message = row["message"]
            confidence = row["confidence"]
            continuity = row["continuity"]
            results_conn.execute(
                """
                INSERT INTO topic_members
                    (topic_id, msg_id, conv_id, conv_title, model_slug, create_time, relevance,
                     lexical_assertiveness, uncertainty_disclosure, advice_forcefulness,
                     epistemic_posture, explicit_continuity, semantic_continuity,
                     contradiction_ack, content_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic_id,
                    message.msg_id,
                    message.conv_id,
                    message.conv_title,
                    message.model_slug,
                    message.create_time,
                    row["relevance"],
                    confidence["lexical_assertiveness"],
                    confidence["uncertainty_disclosure"],
                    confidence["advice_forcefulness"],
                    confidence["epistemic_posture"],
                    continuity["explicit_continuity"],
                    continuity["semantic_continuity"],
                    continuity["contradiction_ack"],
                    message.content[:500],
                ),
            )

        _store_model_summaries(results_conn, probe_topic, relevant)

        for i in range(len(relevant)):
            for j in range(i + 1, len(relevant)):
                left = relevant[i]
                right = relevant[j]
                similarity = float(pairwise_sims[i, j])
                pair_sims.append(similarity)
                contradiction_type = classify_pair(
                    similarity=similarity,
                    text_a=left["message"].content,
                    text_b=right["message"].content,
                    continuity_a=left["continuity"],
                    continuity_b=right["continuity"],
                    time_a=left["message"].create_time,
                    time_b=right["message"].create_time,
                )
                typed_counts[contradiction_type] += 1

                pair_confidence = (
                    left["confidence"]["confidence_proxy"] + right["confidence"]["confidence_proxy"]
                ) / 2.0
                pair_continuity = (
                    left["continuity"]["continuity_score"] + right["continuity"]["continuity_score"]
                ) / 2.0
                risk_score = pair_confidence * (1.0 - similarity) * (1.0 - pair_continuity)

                cursor = results_conn.execute(
                    """
                    INSERT INTO response_pairs
                        (topic_id, probe_topic, msg_id_a, msg_id_b, conv_title_a, conv_title_b,
                         model_a, model_b, time_a, time_b, similarity,
                         lexical_assertiveness_a, lexical_assertiveness_b,
                         uncertainty_disclosure_a, uncertainty_disclosure_b,
                         advice_forcefulness_a, advice_forcefulness_b,
                         explicit_continuity_a, explicit_continuity_b,
                         semantic_continuity_a, semantic_continuity_b,
                         contradiction_ack_a, contradiction_ack_b,
                         contradiction_type, pair_confidence, pair_continuity, risk_score,
                         content_a, content_b)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        probe_topic,
                        left["message"].msg_id,
                        right["message"].msg_id,
                        left["message"].conv_title,
                        right["message"].conv_title,
                        left["message"].model_slug,
                        right["message"].model_slug,
                        left["message"].create_time,
                        right["message"].create_time,
                        similarity,
                        left["confidence"]["lexical_assertiveness"],
                        right["confidence"]["lexical_assertiveness"],
                        left["confidence"]["uncertainty_disclosure"],
                        right["confidence"]["uncertainty_disclosure"],
                        left["confidence"]["advice_forcefulness"],
                        right["confidence"]["advice_forcefulness"],
                        left["continuity"]["explicit_continuity"],
                        right["continuity"]["explicit_continuity"],
                        left["continuity"]["semantic_continuity"],
                        right["continuity"]["semantic_continuity"],
                        left["continuity"]["contradiction_ack"],
                        right["continuity"]["contradiction_ack"],
                        contradiction_type,
                        pair_confidence,
                        pair_continuity,
                        risk_score,
                        left["message"].content[:500],
                        right["message"].content[:500],
                    ),
                )
                all_pairs.append(
                    {
                        "pair_id": int(cursor.lastrowid),
                        "probe_topic": probe_topic,
                        "risk_score": risk_score,
                    }
                )

        total_pairs = max(1, len(pair_sims))
        mean_similarity = float(np.mean(pair_sims))
        min_similarity = float(np.min(pair_sims))
        variance = float(np.var(pair_sims))
        contradiction_rate = typed_counts["genuine_contradiction"] / total_pairs
        ambiguity_rate = typed_counts["insufficient_evidence"] / total_pairs
        temporal_update_rate = typed_counts["temporal_update"] / total_pairs
        framing_variation_rate = typed_counts["framing_variation"] / total_pairs
        context_variation_rate = typed_counts["scope_context_variation"] / total_pairs

        mean_assertiveness = float(np.mean([r["confidence"]["lexical_assertiveness"] for r in relevant]))
        mean_uncertainty = float(np.mean([r["confidence"]["uncertainty_disclosure"] for r in relevant]))
        mean_forcefulness = float(np.mean([r["confidence"]["advice_forcefulness"] for r in relevant]))
        explicit_rate = float(np.mean([r["continuity"]["explicit_continuity"] for r in relevant]))
        semantic_rate = float(np.mean([r["continuity"]["semantic_continuity"] for r in relevant]))
        contradiction_ack_rate = float(np.mean([r["continuity"]["contradiction_ack"] for r in relevant]))
        topic_risk = float(
            np.mean(
                [
                    (
                        r["confidence"]["confidence_proxy"]
                        * (1.0 - r["continuity"]["continuity_score"])
                    )
                    for r in relevant
                ]
            )
            * (1.0 - mean_similarity)
        )

        results_conn.execute(
            """
            UPDATE topic_clusters
            SET mean_similarity = ?, min_similarity = ?, variance = ?,
                continuity_awareness_rate = ?, semantic_continuity_rate = ?,
                contradiction_ack_rate = ?, mean_assertiveness = ?,
                mean_uncertainty_disclosure = ?, mean_advice_forcefulness = ?,
                contradiction_rate = ?, ambiguity_rate = ?, temporal_update_rate = ?,
                framing_variation_rate = ?, context_variation_rate = ?, risk_score = ?
            WHERE topic_id = ?
            """,
            (
                mean_similarity,
                min_similarity,
                variance,
                explicit_rate,
                semantic_rate,
                contradiction_ack_rate,
                mean_assertiveness,
                mean_uncertainty,
                mean_forcefulness,
                contradiction_rate,
                ambiguity_rate,
                temporal_update_rate,
                framing_variation_rate,
                context_variation_rate,
                topic_risk,
                topic_id,
            ),
        )
        results_conn.commit()

        topic_summaries.append(
            {
                "topic": probe_topic,
                "responses": len(relevant),
                "mean_similarity": round(mean_similarity, 3),
                "contradiction_rate": round(contradiction_rate, 3),
                "temporal_update_rate": round(temporal_update_rate, 3),
                "semantic_continuity_rate": round(semantic_rate, 3),
                "risk_score": round(topic_risk, 3),
            }
        )
        log.info(
            "  %d responses, sim=%.3f, contradiction_rate=%.3f, semantic_continuity=%.3f, risk=%.3f",
            len(relevant),
            mean_similarity,
            contradiction_rate,
            semantic_rate,
            topic_risk,
        )

    all_pairs.sort(key=lambda item: item["risk_score"], reverse=True)
    for rank, pair in enumerate(all_pairs[:MAX_AUDIT_PAIRS], start=1):
        results_conn.execute(
            """
            INSERT INTO manual_audit_queue (pair_id, probe_topic, priority_rank, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (pair["pair_id"], pair["probe_topic"], rank),
        )

    results_conn.commit()
    render_html_report(results_db=results_db)
    corpus_conn.close()
    results_conn.close()

    return {
        "topics_analyzed": len(topic_summaries),
        "pairs_scored": len(all_pairs),
        "audit_queue_size": min(len(all_pairs), MAX_AUDIT_PAIRS),
        "results": topic_summaries,
    }


def show_report(results_db: Path = RESULTS_DB) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = _init_results_db(results_db)
    conn.row_factory = sqlite3.Row

    topics = conn.execute(
        "SELECT * FROM topic_clusters ORDER BY risk_score DESC, contradiction_rate DESC"
    ).fetchall()
    if not topics:
        print("No v2 results yet. Run: python -m tools.continuity_blind_v2 run")
        return

    print("=" * 78)
    print("CONTINUITY-BLIND CONTRADICTION REPORT v2")
    print("Deterministic probe lane with typed pair labels and richer continuity signals")
    print("=" * 78)
    for topic in topics:
        print(
            f"\nRISK={topic['risk_score']:.3f} | {topic['probe_topic']}\n"
            f"  responses={topic['num_threads']} sim={topic['mean_similarity']:.3f}"
            f" contradiction={topic['contradiction_rate']:.1%}"
            f" temporal_update={topic['temporal_update_rate']:.1%}"
            f" framing={topic['framing_variation_rate']:.1%}"
            f" context={topic['context_variation_rate']:.1%}\n"
            f"  explicit_continuity={topic['continuity_awareness_rate']:.1%}"
            f" semantic_continuity={topic['semantic_continuity_rate']:.1%}"
            f" contradiction_ack={topic['contradiction_ack_rate']:.1%}"
        )

    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS topic_count,
            AVG(mean_similarity) AS mean_similarity,
            AVG(contradiction_rate) AS contradiction_rate,
            AVG(semantic_continuity_rate) AS semantic_continuity_rate,
            AVG(risk_score) AS mean_risk
        FROM topic_clusters
        """
    ).fetchone()

    audit_count = conn.execute("SELECT COUNT(*) FROM manual_audit_queue").fetchone()[0]
    print(f"\n{'=' * 78}")
    print("SUMMARY")
    print(f"  Topics analyzed: {summary['topic_count']}")
    print(f"  Mean similarity: {summary['mean_similarity']:.3f}")
    print(f"  Mean contradiction rate: {summary['contradiction_rate']:.3f}")
    print(f"  Mean semantic continuity rate: {summary['semantic_continuity_rate']:.3f}")
    print(f"  Mean risk: {summary['mean_risk']:.3f}")
    print(f"  Manual audit queue: {audit_count}")
    print(f"{'=' * 78}")

    conn.close()


def render_report_command(results_db: Path = RESULTS_DB) -> None:
    rendered = render_html_report(results_db=results_db)
    print(json.dumps(rendered, indent=2))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        refresh = "--refresh-index" in sys.argv[2:]
        result = run_analysis(refresh_index=refresh)
        print(json.dumps(result, indent=2, default=str))
    elif cmd == "report":
        show_report()
    elif cmd == "render-html":
        render_report_command()
    else:
        print("Usage: python -m tools.continuity_blind_v2 <run|report|render-html> [--refresh-index]")


if __name__ == "__main__":
    main()
