"""Self-improving Route Learning for CRT.

Tracks successful LLM-routed classifications and generates regex patterns
over time, so common requests graduate from Tier 2/3 (LLM) to Tier 1 (regex).

Sprint 13 / v2.9

The virtuous cycle:
  Day 1:  Most messages go through LLM router (Tier 2/3)
  Week 1: Common patterns auto-generate regex rules
  Week 2+: 80%+ of messages hit Tier 1 regex, LLM only for novel requests
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default database path
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "route_learning.db"
)


@dataclass
class PatternCandidate:
    """A cluster of similar messages that mapped to the same intent."""
    intent_type: str
    messages: List[str]
    count: int
    avg_confidence: float
    suggested_pattern: Optional[str] = None


class RouteLearningDB:
    """SQLite-backed learning database for route classification outcomes."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS route_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_text TEXT NOT NULL,
                    message_normalized TEXT NOT NULL,
                    intent_type TEXT NOT NULL,
                    tool_calls TEXT,
                    source TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_type TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    origin_messages TEXT,
                    created_at REAL NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_route_log_intent
                ON route_log(intent_type, success)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_route_log_source
                ON route_log(source)
            """)

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize message text for grouping."""
        t = text.lower().strip()
        # Remove [file: ...] attachments for grouping
        t = re.sub(r'\[file:\s*[^\]]+\]', '[FILE]', t)
        # Remove specific file paths/names
        t = re.sub(r'[\w/\\]+\.\w{1,10}', '[PATH]', t)
        # Remove URLs
        t = re.sub(r'https?://\S+', '[URL]', t)
        # Collapse whitespace
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def log_classification(
        self,
        message: str,
        intent_type: str,
        source: str,
        *,
        success: bool = True,
        confidence: float = 0.0,
        tool_calls: Optional[List[str]] = None,
    ) -> None:
        """Record a classification outcome."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO route_log
                       (message_text, message_normalized, intent_type, tool_calls,
                        source, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        message,
                        self._normalize(message),
                        intent_type,
                        json.dumps(tool_calls or []),
                        source,
                        1 if success else 0,
                        confidence,
                        time.time(),
                    ),
                )
        except Exception as e:
            logger.warning("[ROUTE_LEARNING] log_classification failed: %s", e)

    def get_pattern_candidates(self, min_occurrences: int = 5) -> List[PatternCandidate]:
        """
        Find intent types where LLM-routed messages cluster into patterns.
        Only considers messages classified by LLM (not regex) that succeeded.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """SELECT intent_type, message_normalized, COUNT(*) as cnt,
                              AVG(confidence) as avg_conf,
                              GROUP_CONCAT(message_text, '|||')
                       FROM route_log
                       WHERE source IN ('llm_local', 'llm_cloud')
                         AND success = 1
                       GROUP BY intent_type, message_normalized
                       HAVING cnt >= ?
                       ORDER BY cnt DESC
                       LIMIT 20""",
                    (min_occurrences,),
                ).fetchall()

                candidates = []
                for intent_type, normalized, count, avg_conf, messages_joined in rows:
                    # Skip if we already have a learned pattern for this normalized form
                    existing = conn.execute(
                        """SELECT 1 FROM learned_patterns
                           WHERE intent_type = ? AND active = 1
                           LIMIT 1""",
                        (intent_type,),
                    ).fetchone()
                    # Still include — new patterns may cover different phrasings

                    messages = messages_joined.split("|||")[:10]  # Keep top 10 examples
                    candidates.append(PatternCandidate(
                        intent_type=intent_type,
                        messages=messages,
                        count=count,
                        avg_confidence=avg_conf,
                    ))

                return candidates
        except Exception as e:
            logger.warning("[ROUTE_LEARNING] get_pattern_candidates failed: %s", e)
            return []

    def save_learned_pattern(
        self,
        intent_type: str,
        pattern: str,
        origin_messages: List[str],
    ) -> None:
        """Persist a newly generated regex pattern."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO learned_patterns
                       (intent_type, pattern, origin_messages, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        intent_type,
                        pattern,
                        json.dumps(origin_messages[:5]),
                        time.time(),
                    ),
                )
                logger.info(
                    "[ROUTE_LEARNING] Saved learned pattern: %s → %s",
                    intent_type, pattern,
                )
        except Exception as e:
            logger.warning("[ROUTE_LEARNING] save_learned_pattern failed: %s", e)

    def lookup_recent(self, message: str, max_age_hours: int = 24) -> Optional[Dict[str, Any]]:
        """Look up a recent successful classification for a similar message.

        Returns {"intent_type": str, "confidence": float, "source": str} or None.
        """
        try:
            normalized = self._normalize(message)
            cutoff = time.time() - (max_age_hours * 3600)
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """SELECT intent_type, confidence, source
                       FROM route_log
                       WHERE message_normalized = ?
                         AND success = 1
                         AND timestamp > ?
                       ORDER BY timestamp DESC
                       LIMIT 1""",
                    (normalized, cutoff),
                ).fetchone()
                if row:
                    return {"intent_type": row[0], "confidence": row[1], "source": row[2]}
        except Exception as e:
            logger.debug("[ROUTE_LEARNING] lookup_recent failed: %s", e)
        return None

    def get_learned_patterns(self) -> List[Tuple[str, str]]:
        """Get all active learned patterns as (intent_type, pattern) tuples."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT intent_type, pattern FROM learned_patterns WHERE active = 1"
                ).fetchall()
                return [(r[0], r[1]) for r in rows]
        except Exception as e:
            logger.warning("[ROUTE_LEARNING] get_learned_patterns failed: %s", e)
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the learning database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM route_log").fetchone()[0]
                by_source = dict(conn.execute(
                    "SELECT source, COUNT(*) FROM route_log GROUP BY source"
                ).fetchall())
                success_rate = conn.execute(
                    "SELECT AVG(success) FROM route_log"
                ).fetchone()[0] or 0
                patterns = conn.execute(
                    "SELECT COUNT(*) FROM learned_patterns WHERE active = 1"
                ).fetchone()[0]
                return {
                    "total_classifications": total,
                    "by_source": by_source,
                    "success_rate": round(success_rate, 3),
                    "active_patterns": patterns,
                }
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Pattern generation
# ---------------------------------------------------------------------------

def generate_regex_from_examples(
    intent_type: str,
    messages: List[str],
    llm_client=None,
) -> Optional[str]:
    """
    Generate a regex pattern from a cluster of similar messages.

    If an LLM client is available, uses it to generalize.
    Otherwise, uses simple heuristic pattern generation.
    """
    if not messages:
        return None

    # Try LLM-based generation first
    if llm_client is not None:
        try:
            examples = "\n".join(f"  - {m}" for m in messages[:8])
            prompt = f"""Given these user messages that all map to the "{intent_type}" tool intent:
{examples}

Write a single Python regex pattern (case-insensitive) that would match similar messages.
The pattern should be general enough to catch variations but specific enough to avoid false positives.

Rules:
- Use (?:...) for non-capturing groups
- Start with ^ if the pattern should match from the beginning
- Use \\b for word boundaries
- Return ONLY the regex pattern string, nothing else

Pattern:"""
            raw = llm_client.generate(prompt, max_tokens=150, temperature=0.2)
            # Extract the pattern from the response
            pattern = raw.strip().strip('"').strip("'").strip("`")
            # Validate it compiles
            re.compile(pattern, re.IGNORECASE)
            return pattern
        except Exception as e:
            logger.debug("[ROUTE_LEARNING] LLM pattern generation failed: %s", e)

    # Fallback: simple heuristic — find common words
    try:
        words_per_msg = [set(re.findall(r'\w+', m.lower())) for m in messages]
        common = words_per_msg[0]
        for ws in words_per_msg[1:]:
            common &= ws
        # Remove stop words
        common -= {"the", "a", "an", "is", "are", "my", "me", "i", "this", "that", "it", "and", "or", "to", "in", "of", "for", "with", "on", "at"}
        if common:
            # Build a simple pattern from common words
            pattern_parts = sorted(common, key=len, reverse=True)[:3]
            pattern = r"(?:" + "|".join(re.escape(w) for w in pattern_parts) + r")"
            re.compile(pattern, re.IGNORECASE)
            return pattern
    except Exception as e:
        logger.debug("[ROUTE_LEARNING] Heuristic pattern generation failed: %s", e)

    return None


# ---------------------------------------------------------------------------
# Heartbeat integration
# ---------------------------------------------------------------------------

def review_route_patterns(
    db_path: Optional[str] = None,
    llm_client=None,
    min_occurrences: int = 5,
) -> List[Tuple[str, str]]:
    """
    Review route learning DB and generate new patterns from clusters.
    Called from heartbeat_executor.py periodically.

    Returns: list of (intent_type, pattern) tuples that were newly created.
    """
    db = RouteLearningDB(db_path)
    candidates = db.get_pattern_candidates(min_occurrences)

    if not candidates:
        return []

    new_patterns = []
    for candidate in candidates:
        pattern = generate_regex_from_examples(
            candidate.intent_type,
            candidate.messages,
            llm_client=llm_client,
        )
        if pattern:
            db.save_learned_pattern(
                candidate.intent_type,
                pattern,
                candidate.messages,
            )
            new_patterns.append((candidate.intent_type, pattern))
            logger.info(
                "[ROUTE_LEARNING] Generated pattern for %s: %s (from %d examples)",
                candidate.intent_type, pattern, candidate.count,
            )

    return new_patterns


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

_global_db: Optional[RouteLearningDB] = None


def get_route_learning_db(db_path: Optional[str] = None) -> RouteLearningDB:
    """Get or create the global route learning DB instance."""
    global _global_db
    if _global_db is None:
        _global_db = RouteLearningDB(db_path)
    return _global_db
