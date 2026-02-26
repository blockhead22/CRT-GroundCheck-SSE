"""Heartbeat LLM executor - decision-making and Ledger action execution.

This module:
1. Gathers context (recent messages, memory, HEARTBEAT.md instructions)
2. Uses LLM to decide proactive Ledger actions
3. Executes actions (posts, comments, votes) if not in dry_run mode
4. Records audit trail
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .text_utils import sanitize_thread_id

logger = logging.getLogger(__name__)


@dataclass
class ThreadContext:
    """Context about a thread for heartbeat decision-making."""
    thread_id: str
    recent_messages: List[Dict[str, Any]]  # Last N messages from thread
    recent_contradictions: List[Dict[str, Any]]  # Open contradictions
    user_profile: Optional[Dict[str, Any]]  # User name, goals, preferences
    ledger_feed: List[Dict[str, Any]]  # Recent posts from local Ledger
    memory_snapshot: Dict[str, Any]  # Key facts about the user


class HeartbeatLLMExecutor:
    """
    Executes heartbeat decisions via LLM + Ledger API.
    
    Workflow:
    1. Gather thread context (messages, contradictions, Ledger feed)
    2. Create LLM prompt with HEARTBEAT.md instructions
    3. Parse LLM response for actions
    4. Execute actions (post, comment, vote) to local Ledger
    5. Record results in DB
    """
    
    # Validation constraints
    MAX_POST_TITLE_LENGTH = 200
    MAX_CONTENT_LENGTH = 5000
    MAX_ACTIONS_PER_HEARTBEAT = 3
    
    def __init__(
        self,
        session_db=None,  # ThreadSessionDB instance
        thread_session_db_path: Optional[str] = None,
        ledger_db_path: Optional[str] = None,
        memory_db_path: Optional[str] = None,
    ):
        self.session_db = session_db
        if thread_session_db_path:
            self.thread_session_db_path = str(thread_session_db_path)
        elif session_db is not None and getattr(session_db, "db_path", None):
            self.thread_session_db_path = str(getattr(session_db, "db_path"))
        else:
            self.thread_session_db_path = None
        self.ledger_db_path = str(ledger_db_path) if ledger_db_path else None
        self.memory_db_path = str(memory_db_path) if memory_db_path else None

    def _default_personal_agent_dir(self) -> Path:
        return Path(__file__).resolve().parent

    def _resolve_memory_db_path(self, thread_id: str) -> Optional[str]:
        """Resolve memory DB path for a thread (shared or per-thread)."""
        tid = sanitize_thread_id(str(thread_id or "default"))
        pa_dir = self._default_personal_agent_dir()
        shared_enabled = os.getenv("CRT_SHARED_MEMORY", "false").lower() == "true"

        candidates: List[Path] = []
        if self.memory_db_path:
            try:
                rendered = str(self.memory_db_path).format(thread_id=tid)
            except Exception:
                rendered = str(self.memory_db_path)
            candidates.append(Path(rendered))

        if shared_enabled:
            candidates.append(pa_dir / "crt_memory_shared.db")
        candidates.append(pa_dir / f"crt_memory_{tid}.db")
        if not shared_enabled:
            candidates.append(pa_dir / "crt_memory_shared.db")

        seen: set[str] = set()
        for c in candidates:
            cs = str(c)
            if cs in seen:
                continue
            seen.add(cs)
            if c.exists():
                return cs
        return str(candidates[0]) if candidates else None

    def _resolve_ledger_db_path(self, thread_id: str) -> Optional[str]:
        """Resolve contradiction ledger DB path for a thread (shared or per-thread)."""
        tid = sanitize_thread_id(str(thread_id or "default"))
        pa_dir = self._default_personal_agent_dir()
        shared_enabled = os.getenv("CRT_SHARED_MEMORY", "false").lower() == "true"

        candidates: List[Path] = []
        if self.ledger_db_path:
            try:
                rendered = str(self.ledger_db_path).format(thread_id=tid)
            except Exception:
                rendered = str(self.ledger_db_path)
            candidates.append(Path(rendered))

        if shared_enabled:
            candidates.append(pa_dir / "crt_ledger_shared.db")
        candidates.append(pa_dir / f"crt_ledger_{tid}.db")
        if not shared_enabled:
            candidates.append(pa_dir / "crt_ledger_shared.db")

        seen: set[str] = set()
        for c in candidates:
            cs = str(c)
            if cs in seen:
                continue
            seen.add(cs)
            if c.exists():
                return cs
        return str(candidates[0]) if candidates else None

    def _get_thread_memory_ids(self, thread_id: str, limit: int = 500) -> List[str]:
        """Return recent memory IDs for a thread to scope shared-ledger queries."""
        mem_db_path = self._resolve_memory_db_path(thread_id)
        if not mem_db_path or not Path(mem_db_path).exists():
            return []
        try:
            conn = sqlite3.connect(mem_db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            columns = {
                str(row[1]).lower()
                for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "memory_id" not in columns:
                conn.close()
                return []
            if "thread_id" not in columns:
                conn.close()
                return []
            has_deprecated = "deprecated" in columns
            query = "SELECT memory_id FROM memories WHERE thread_id = ?"
            params: List[Any] = [thread_id]
            if has_deprecated:
                query += " AND COALESCE(deprecated, 0) = 0"
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(max(1, int(limit)))
            rows = cursor.execute(query, tuple(params)).fetchall()
            conn.close()
            return [str(row["memory_id"]) for row in rows if row["memory_id"]]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting thread memory ids: {e}")
            return []
    
    def gather_context(self, thread_id: str) -> ThreadContext:
        """Gather all context needed for heartbeat decision."""
        recent_messages = self._get_recent_messages(thread_id)
        recent_contradictions = self._get_open_contradictions(thread_id)
        user_profile = self._get_user_profile(thread_id)
        ledger_feed = self._get_ledger_feed()
        memory_snapshot = self._get_memory_snapshot(thread_id)
        
        # Check for mentions in Moltbook
        mentions = []
        if self.session_db:
            try:
                # Check posts from the last heartbeat run
                mentions = self.session_db.get_posts_mentioning(agent_name="agent", limit=5)
            except Exception as e:
                logger.debug(f"[HEARTBEAT] Error checking mentions: {e}")
        
        # Add mentions to context (could extend ThreadContext or add to ledger_feed)
        if mentions:
            logger.info(f"[HEARTBEAT] Found {len(mentions)} mentions in Moltbook")
            # Prepend mentions to feed so they're prioritized
            ledger_feed = mentions + ledger_feed
        
        return ThreadContext(
            thread_id=thread_id,
            recent_messages=recent_messages,
            recent_contradictions=recent_contradictions,
            user_profile=user_profile,
            ledger_feed=ledger_feed,
            memory_snapshot=memory_snapshot,
        )
    
    def _get_recent_messages(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get last N messages from thread."""
        # Primary path: ThreadSessionDB helper.
        if self.session_db and hasattr(self.session_db, "get_recent_queries"):
            try:
                recent = self.session_db.get_recent_queries(thread_id, window=max(1, int(limit)))
                messages: List[Dict[str, Any]] = []
                for row in reversed(recent):
                    q = str((row or {}).get("query_text") or "").strip()
                    r = str((row or {}).get("response_text") or "").strip()
                    ts = float((row or {}).get("timestamp") or 0.0)
                    if q:
                        messages.append({"role": "user", "content": q, "timestamp": ts})
                    if r:
                        messages.append({"role": "assistant", "content": r, "timestamp": ts})
                return messages[-(limit * 2):]
            except Exception as e:
                logger.debug(f"[HEARTBEAT] Error getting recent messages from session_db: {e}")

        # Fallback: query thread session DB directly when available.
        if not self.thread_session_db_path:
            return []
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT query_text, response_text, timestamp
                FROM recent_queries
                WHERE thread_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (thread_id, max(1, int(limit))),
            ).fetchall()
            conn.close()

            messages: List[Dict[str, Any]] = []
            for row in reversed(rows):
                q = str(row["query_text"] or "").strip()
                r = str(row["response_text"] or "").strip()
                ts = float(row["timestamp"] or 0.0)
                if q:
                    messages.append({"role": "user", "content": q, "timestamp": ts})
                if r:
                    messages.append({"role": "assistant", "content": r, "timestamp": ts})
            return messages[-(limit * 2):]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting recent messages (fallback): {e}")
            return []
    
    def _get_open_contradictions(self, thread_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get open contradictions from Ledger DB."""
        ledger_path = self._resolve_ledger_db_path(thread_id)
        if not ledger_path:
            return []
        
        try:
            conn = sqlite3.connect(ledger_path, timeout=30.0)
            cursor = conn.cursor()

            thread_memory_ids = self._get_thread_memory_ids(thread_id, limit=600)
            params: List[Any] = []
            query = (
                "SELECT ledger_id, timestamp, summary, status, contradiction_type "
                "FROM contradictions WHERE status = 'open'"
            )
            if thread_memory_ids:
                placeholders = ",".join("?" for _ in thread_memory_ids)
                query += (
                    f" AND (old_memory_id IN ({placeholders}) OR new_memory_id IN ({placeholders}))"
                )
                params.extend(thread_memory_ids)
                params.extend(thread_memory_ids)
            elif str(ledger_path).endswith("crt_ledger_shared.db"):
                # In shared mode, no thread-bound memories means no safe scope.
                conn.close()
                return []

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(max(1, int(limit)))
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "ledger_id": row[0],
                    "timestamp": row[1],
                    "summary": row[2],
                    "status": row[3],
                    "type": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting contradictions: {e}")
            return []
    
    def _get_user_profile(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile info (name, goals, etc.)."""
        if self.session_db:
            try:
                session = self.session_db.get_or_create_session(thread_id)
                profile: Dict[str, Any] = {"user_name": session.get("user_name")}
                try:
                    style = self.session_db.get_style_profile(thread_id)
                    if style:
                        profile["style"] = style
                except Exception:
                    pass
                return profile
            except Exception as e:
                logger.debug(f"[HEARTBEAT] Error getting profile from session_db: {e}")

        if not self.thread_session_db_path:
            return None
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT user_name, style_profile_json FROM thread_sessions WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                profile = {"user_name": row[0]}
                if row[1]:
                    try:
                        profile["style"] = json.loads(row[1])
                    except Exception:
                        pass
                return profile
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting user profile: {e}")
        
        return None
    
    def _get_ledger_feed(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent posts from local Ledger (similar to 'feed')."""
        if not self.session_db:
            return []
        
        try:
            conn = self.session_db._get_connection()
            cursor = conn.cursor()
            
            # Get recent posts with vote counts
            cursor.execute(
                """
                SELECT p.id, p.author, p.created_at, p.title, p.content,
                       COALESCE(SUM(v.value), 0) AS score
                FROM molt_posts p
                LEFT JOIN molt_votes v
                  ON v.target_type = 'post' AND v.target_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "id": row[0],
                    "author": row[1],
                    "timestamp": row[2],
                    "title": row[3],
                    "content": row[4],
                    "vote_count": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting Ledger feed: {e}")
            return []
    
    def _get_memory_snapshot(self, thread_id: str) -> Dict[str, Any]:
        """Get snapshot of key facts about the user."""
        memory_path = self._resolve_memory_db_path(thread_id)
        if not memory_path:
            return {}
        
        try:
            from personal_agent.fact_slots import extract_fact_slots

            conn = sqlite3.connect(memory_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            columns = {
                str(row[1]).lower()
                for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
            }
            if not {"text", "confidence"}.issubset(columns):
                conn.close()
                return {}

            has_thread_id = "thread_id" in columns
            has_trust = "trust" in columns
            has_source = "source" in columns

            select_cols = ["text", "confidence", "timestamp"]
            if has_trust:
                select_cols.append("trust")
            if has_source:
                select_cols.append("source")
            if has_thread_id:
                select_cols.append("thread_id")

            query = f"SELECT {', '.join(select_cols)} FROM memories"
            params: List[Any] = []
            if has_thread_id:
                # Prefer strict thread affinity when any thread-bound rows exist.
                try:
                    thread_count = int(
                        cursor.execute(
                            "SELECT COUNT(*) FROM memories WHERE thread_id = ?",
                            (thread_id,),
                        ).fetchone()[0]
                    )
                except Exception:
                    thread_count = 0

                if thread_count > 0:
                    query += " WHERE thread_id = ?"
                    params.append(thread_id)
                elif str(thread_id or "").strip().lower() == "default":
                    # Legacy fallback for historical single-thread DBs.
                    query += " WHERE (thread_id IS NULL OR thread_id = '')"
                else:
                    # Non-default thread with no bound rows: avoid cross-thread bleed.
                    query += " WHERE thread_id = ?"
                    params.append(thread_id)
            query += " ORDER BY timestamp DESC LIMIT 80"

            rows = cursor.execute(query, tuple(params)).fetchall()
            conn.close()

            snapshot: Dict[str, Any] = {}
            generic_counter = 0
            for row in rows:
                text = str(row["text"] or "").strip()
                if not text:
                    continue
                conf = float(row["confidence"] or 0.0)
                trust = float(row["trust"] or 0.0) if has_trust else None
                source = str(row["source"] or "") if has_source else ""

                fact_slots = {}
                try:
                    fact_slots = extract_fact_slots(text) or {}
                except Exception:
                    fact_slots = {}

                if fact_slots:
                    for slot, value in fact_slots.items():
                        if not slot or value is None:
                            continue
                        existing = snapshot.get(slot)
                        if existing is None or conf >= float(existing.get("confidence") or 0.0):
                            payload = {"value": value, "confidence": conf, "source": source}
                            if trust is not None:
                                payload["trust"] = trust
                            snapshot[slot] = payload
                    continue

                # Keep a compact fallback view when slot extraction fails.
                if generic_counter < 8:
                    generic_counter += 1
                    key = f"memory_{generic_counter}"
                    payload = {"value": text[:180], "confidence": conf, "source": source}
                    if trust is not None:
                        payload["trust"] = trust
                    snapshot[key] = payload

            return snapshot
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting memory snapshot: {e}")
            return {}

    def _derive_news_topics(self, thread_id: str, config: Dict[str, Any]) -> List[str]:
        """Derive news topics from config and reflection scorecard."""
        explicit = config.get("news_topics") if isinstance(config, dict) else None
        topics: List[str] = []
        if isinstance(explicit, list):
            topics = [str(t).strip() for t in explicit if str(t).strip()]
        if topics:
            return topics[:5]

        if not self.session_db:
            return []
        try:
            scorecard = self.session_db.get_reflection_scorecard(thread_id)
            if not isinstance(scorecard, dict):
                return []
            top_topics = scorecard.get("top_topics") or []
            out: List[str] = []
            for item in top_topics:
                if isinstance(item, dict):
                    topic = str(item.get("topic") or "").strip()
                else:
                    topic = str(item or "").strip()
                if topic:
                    out.append(topic)
            return out[:3]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Could not derive reflection topics: {e}")
            return []

    def _run_news_monitoring(
        self,
        thread_id: str,
        config: Dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for topic updates and post digest entries when new results appear."""
        if not isinstance(config, dict) or not bool(config.get("news_monitoring_enabled", False)):
            return []
        if not self.session_db:
            return []

        topics = self._derive_news_topics(thread_id, config)
        if not topics:
            return []

        try:
            from personal_agent.web_search import WebSearchTool
        except Exception as e:
            logger.debug(f"[HEARTBEAT] News monitor unavailable (web search import failed): {e}")
            return []

        suffix = str(config.get("news_query_suffix") or "latest news").strip() or "latest news"
        max_results = max(1, int(config.get("news_max_results", 5) or 5))
        cooldown_seconds = max(900, int(config.get("news_cooldown_seconds", 21600) or 21600))
        submolt = str(config.get("news_post_submolt") or "news").strip() or "news"

        search_tool = WebSearchTool(max_results=max_results)
        now_ts = time.time()
        actions: List[Dict[str, Any]] = []

        for topic in topics[:3]:
            safe_topic = str(topic).strip()
            if not safe_topic:
                continue

            cache = self.session_db.get_heartbeat_news_cache(thread_id, safe_topic) or {}
            last_run = float(cache.get("last_run") or 0.0)
            if last_run > 0 and (now_ts - last_run) < cooldown_seconds:
                continue

            query = f"{safe_topic} {suffix}".strip()
            result = search_tool.search(query, max_results=max_results)
            if result.error or not result.results:
                self.session_db.upsert_heartbeat_news_cache(
                    thread_id,
                    safe_topic,
                    digest_hash=cache.get("digest_hash"),
                    last_summary=f"search_error={result.error}" if result.error else "no_results",
                    last_run=now_ts,
                )
                continue

            top = result.results[: min(3, len(result.results))]
            digest_seed = "|".join(f"{r.title}::{r.url}" for r in top)
            digest_hash = hashlib.sha1(digest_seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
            if cache.get("digest_hash") == digest_hash:
                self.session_db.upsert_heartbeat_news_cache(
                    thread_id,
                    safe_topic,
                    digest_hash=digest_hash,
                    last_summary="unchanged",
                    last_run=now_ts,
                )
                continue

            lines = []
            for idx, item in enumerate(top, start=1):
                title = (item.title or "").strip() or "Untitled"
                url = (item.url or "").strip()
                snippet = (item.snippet or "").strip()
                if len(snippet) > 180:
                    snippet = snippet[:177].rstrip() + "..."
                line = f"{idx}. {title}"
                if snippet:
                    line += f" — {snippet}"
                if url:
                    line += f"\n   {url}"
                lines.append(line)

            title = f"News digest: {safe_topic}"
            content = (
                f"Heartbeat news monitor update for '{safe_topic}'.\n\n"
                + "\n\n".join(lines)
            )

            executed = False
            post_error: Optional[str] = None
            if not dry_run:
                post_result = self.execute_action(
                    {
                        "action": "post",
                        "submolt": submolt,
                        "title": title,
                        "content": content,
                        "reasoning": f"New digest hash {digest_hash}",
                    },
                    thread_id,
                    dry_run=dry_run,
                )
                executed = bool(post_result.get("success"))
                post_error = post_result.get("error") if isinstance(post_result, dict) else None
            else:
                executed = True

            summary = f"query='{query}', results={len(top)}, posted={executed}"
            self.session_db.upsert_heartbeat_news_cache(
                thread_id,
                safe_topic,
                digest_hash=digest_hash,
                last_summary=summary,
                last_run=now_ts,
            )

            actions.append(
                {
                    "action": "news_monitor",
                    "topic": safe_topic,
                    "query": query,
                    "result_count": len(top),
                    "posted": bool(executed),
                    "digest_hash": digest_hash,
                    "detail": f"News digest for '{safe_topic}' ({len(top)} items)",
                    "error": post_error,
                }
            )

        return actions
    
    def create_decision_prompt(
        self,
        context: ThreadContext,
        heartbeat_md_text: str,
        config: Dict[str, Any],
    ) -> str:
        """
        Create the LLM prompt for heartbeat decision-making.
        
        The prompt includes:
        - Current time and date
        - Recent message context
        - HEARTBEAT.md instructions
        - Ledger feed
        - User profile
        - Decision framework
        """
        from datetime import datetime
        
        # Get current time info
        now = datetime.now()
        time_text = f"""Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
Day of week: {now.strftime('%A')}
Hour: {now.hour} (24h format)
"""
        
        # Format recent messages
        msg_text = ""
        if context.recent_messages:
            msg_text = "Recent messages in thread:\n"
            for msg in context.recent_messages[-5:]:  # Last 5
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                msg_text += f"- {role}: {content}\n"
        
        # Format Ledger feed summary
        feed_text = ""
        if context.ledger_feed:
            feed_text = "Recent Ledger posts:\n"
            for post in context.ledger_feed[:5]:  # Top 5
                title = post.get("title", "Untitled")
                votes = post.get("vote_count", 0)
                feed_text += f"- {title} ({votes} votes)\n"
        
        # Format HEARTBEAT.md
        hb_text = heartbeat_md_text or "No HEARTBEAT.md found."
        
        # Format user profile
        profile_text = ""
        if context.user_profile:
            user = context.user_profile.get("user_name", "Unknown")
            profile_text = f"User: {user}\n"
        
        prompt = f"""You are an AI agent managing a personal Ledger (a local discussion/note system).

## Current Time:
{time_text}

{profile_text}

## Standing Instructions (from HEARTBEAT.md):
{hb_text}

## Current Context:

{msg_text}

{feed_text}

## Your Decision:
Based on the above, decide what action to take. Options:
1. post: Create a new post (provide title and content)
2. comment: Reply to a post (provide post_id and comment text)
3. vote: Upvote or downvote a post (provide post_id and direction)
4. none: Do nothing (reply with HEARTBEAT_OK)

## Response Format:
Reply with a JSON object:
{{
  "action": "post|comment|vote|none",
  "post_id": "...",  // For comment/vote
  "title": "...",    // For post
  "content": "...",  // For post/comment
  "vote_direction": "up|down",  // For vote
  "reasoning": "..."  // Explain why this action
}}

Reason carefully. If unsure, reply with action=none.
"""
        return prompt
    
    def parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response for action data."""
        try:
            # Try to extract JSON from response
            import re
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Failed to parse LLM response: {e}")
        
        # Fallback: return 'none' action
        return {
            "action": "none",
            "reasoning": response_text[:200],
        }
    
    def run_heartbeat_for_thread(self, thread_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main heartbeat orchestration method.
        
        Performs real autonomous work:
        1. Trust decay on aging memories
        2. Contradiction inventory check
        3. Memory consolidation/stats
        4. Proactive observations
        
        Args:
            thread_id: Thread ID to run heartbeat for
            config: Heartbeat configuration (dry_run, etc.)
            
        Returns:
            Dict with heartbeat result
        """
        import time as _time
        start = _time.time()
        actions_taken = []
        dry_run = config.get('dry_run', False) if config else False

        # --- 1. Trust Decay Pass ---
        try:
            from personal_agent.trust_decay import run_trust_decay_pass
            decay_result = run_trust_decay_pass()
            decayed_count = decay_result.get("decayed", 0) if isinstance(decay_result, dict) else 0
            if decayed_count > 0:
                actions_taken.append({
                    "action": "trust_decay",
                    "detail": f"Decayed trust on {decayed_count} aging memories",
                    "count": decayed_count,
                })
                logger.info(f"[HEARTBEAT] Trust decay: {decayed_count} memories decayed")
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Trust decay skipped: {e}")

        # --- 2. Contradiction Inventory ---
        try:
            open_contradictions = self._get_open_contradictions(thread_id, limit=20)
            if open_contradictions:
                stale = [c for c in open_contradictions
                         if _time.time() - float(c.get("timestamp", 0)) > 86400]
                actions_taken.append({
                    "action": "contradiction_check",
                    "detail": f"{len(open_contradictions)} open contradictions ({len(stale)} older than 24h)",
                    "open": len(open_contradictions),
                    "stale": len(stale),
                })
                logger.info(f"[HEARTBEAT] Contradictions: {len(open_contradictions)} open, {len(stale)} stale")
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Contradiction check skipped: {e}")

        # --- 3. Memory Stats ---
        try:
            snapshot = self._get_memory_snapshot(thread_id)
            total_facts = len(snapshot)
            low_trust = sum(1 for v in snapshot.values()
                           if (v.get("confidence") or 0) < 0.4)
            actions_taken.append({
                "action": "memory_audit",
                "detail": f"{total_facts} known facts, {low_trust} with low trust (<0.4)",
                "total": total_facts,
                "low_trust": low_trust,
            })
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Memory audit skipped: {e}")

        # --- 4. Respond to mentions (existing behavior) ---
        # --- 4.5. Optional news monitoring ---
        try:
            news_actions = self._run_news_monitoring(thread_id, config or {}, dry_run=dry_run)
            if news_actions:
                actions_taken.extend(news_actions)
                logger.info(f"[HEARTBEAT] News monitor posted {len(news_actions)} digest update(s)")
        except Exception as e:
            logger.debug(f"[HEARTBEAT] News monitor skipped: {e}")

        # --- 5. Respond to mentions (existing behavior) ---
        try:
            context = self.gather_context(thread_id)
            if context.ledger_feed:
                mention = next((post for post in context.ledger_feed
                               if any(word in (post.get('content', '') + post.get('title', '')).lower()
                                      for word in ['aether', '@agent', 'agent'])), None)
                if mention and not dry_run:
                    post_id = mention.get('id') or mention.get('post_id', '')
                    result = self.execute_action({
                        "action": "comment",
                        "post_id": str(post_id),
                        "content": "Noticed this during my heartbeat check. Let me know if you need anything.",
                        "reasoning": f"Responding to mention in '{mention.get('title', 'Untitled')}'",
                    }, thread_id, dry_run=dry_run)
                    actions_taken.append({
                        "action": "respond_mention",
                        "detail": f"Responded to mention in post #{post_id}",
                    })
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Mention check skipped: {e}")

        elapsed = _time.time() - start
        summary = "; ".join(a["detail"] for a in actions_taken) if actions_taken else "Heartbeat OK, no actions needed"
        
        # Record to session DB
        try:
            if self.session_db:
                run_ts = _time.time()
                if hasattr(self.session_db, "update_heartbeat_state"):
                    self.session_db.update_heartbeat_state(
                        thread_id,
                        last_run=run_ts,
                        summary=summary,
                        actions=actions_taken,
                    )
                elif hasattr(self.session_db, "record_heartbeat_run"):
                    # Backward compatibility with older session DB helpers.
                    self.session_db.record_heartbeat_run(
                        thread_id,
                        {
                            "timestamp": run_ts,
                            "summary": summary,
                            "actions": actions_taken,
                            "success": True,
                            "execution_time": elapsed,
                        },
                    )
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Failed to record run: {e}")

        logger.info(f"[HEARTBEAT] Completed for {thread_id} in {elapsed:.2f}s: {summary}")
        return {
            "success": True,
            "actions": actions_taken,
            "summary": summary,
            "execution_time": elapsed,
        }
    
    def execute_action(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a Ledger action (post, comment, vote).
        
        Returns:
            Dict with action result (success, ledger_id, error, etc.)
        """
        action_type = action_data.get("action", "none").lower()
        
        if action_type == "none":
            return {"success": True, "action": "none", "message": "No action taken"}
        
        if action_type == "post":
            return self._execute_post(action_data, thread_id, dry_run)
        elif action_type == "comment":
            return self._execute_comment(action_data, thread_id, dry_run)
        elif action_type == "vote":
            return self._execute_vote(action_data, thread_id, dry_run)
        else:
            return {"success": False, "error": f"Unknown action type: {action_type}"}
    
    def _execute_post(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Create a new Moltbook post (heartbeat submolt)."""
        title = action_data.get("title", "").strip()
        content = action_data.get("content", "").strip()
        submolt = action_data.get("submolt", "heartbeat").strip()  # Default to 'heartbeat' submolt
        
        if not title or not content:
            return {"success": False, "error": "Post requires title and content"}
        
        if dry_run:
            logger.info(f"[HEARTBEAT] DRY RUN: Would create post: {title}")
            return {
                "success": True,
                "action": "post",
                "dry_run": True,
                "title": title,
                "content": content[:100],
            }
        
        # Create post in Moltbook
        if not self.session_db:
            logger.error("[HEARTBEAT] No session_db available for post creation")
            return {"success": False, "error": "No session_db available"}
        
        try:
            self.session_db.ensure_default_submolts()
            # Ensure heartbeat submolt exists
            try:
                self.session_db.create_submolt(
                    name="heartbeat",
                    description="Proactive agent observations and updates",
                    created_by="system"
                )
            except Exception:
                pass  # Already exists
            
            post = self.session_db.create_post(
                submolt=submolt,
                title=title,
                content=content,
                author="heartbeat-system",
                source_type="heartbeat",
                source_entry_id=None,
            )
            
            logger.info(f"[HEARTBEAT] Created post #{post.get('id')}: {title}")
            return {
                "success": True,
                "action": "post",
                "post_id": post.get("id"),
                "title": title,
                "submolt": submolt,
            }
        except Exception as e:
            logger.error(f"[HEARTBEAT] Failed to create post: {e}")
            return {"success": False, "error": f"Failed to create post: {str(e)}"}
    
    def _execute_comment(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Create a comment on a Moltbook post."""
        post_id = action_data.get("post_id", "").strip()
        content = action_data.get("content", "").strip()
        
        if not post_id or not content:
            return {"success": False, "error": "Comment requires post_id and content"}
        
        if dry_run:
            logger.info(f"[HEARTBEAT] DRY RUN: Would comment on post #{post_id}")
            return {
                "success": True,
                "action": "comment",
                "dry_run": True,
                "post_id": post_id,
                "content": content[:100],
            }
        
        # Create comment in Moltbook
        if not self.session_db:
            logger.error("[HEARTBEAT] No session_db available for comment creation")
            return {"success": False, "error": "No session_db available"}
        
        try:
            comment = self.session_db.create_comment(
                post_id=int(post_id),
                content=content,
                author="heartbeat-system",
            )
            
            logger.info(f"[HEARTBEAT] Created comment #{comment.get('id')} on post #{post_id}")
            return {
                "success": True,
                "action": "comment",
                "comment_id": comment.get("id"),
                "post_id": post_id,
            }
        except Exception as e:
            logger.error(f"[HEARTBEAT] Failed to create comment: {e}")
            return {"success": False, "error": f"Failed to create comment: {str(e)}"}
    
    def _execute_vote(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Vote on a Moltbook post."""
        post_id = action_data.get("post_id", "").strip()
        direction = action_data.get("vote_direction", "").lower()
        
        if not post_id or direction not in ["up", "down"]:
            return {"success": False, "error": "Vote requires post_id and direction (up/down)"}
        
        if dry_run:
            logger.info(f"[HEARTBEAT] DRY RUN: Would vote {direction} on post #{post_id}")
            return {
                "success": True,
                "action": "vote",
                "dry_run": True,
                "post_id": post_id,
                "direction": direction,
            }
        
        # Vote on Moltbook post
        if not self.session_db:
            logger.error("[HEARTBEAT] No session_db available for voting")
            return {"success": False, "error": "No session_db available"}
        
        try:
            vote = self.session_db.vote_post(
                post_id=int(post_id),
                direction=direction,
                author="heartbeat-system",
            )
            
            logger.info(f"[HEARTBEAT] Voted {direction} on post #{post_id}")
            return {
                "success": True,
                "action": "vote",
                "vote_id": vote.get("id") if vote else None,
                "post_id": post_id,
                "direction": direction,
            }
        except Exception as e:
            logger.error(f"[HEARTBEAT] Failed to vote: {e}")
            return {"success": False, "error": f"Failed to vote: {str(e)}"}
    
    def validate_action(self, action_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate an action before execution.
        
        Returns:
            (is_valid, error_message)
        """
        action_type = action_data.get("action", "").lower()
        
        if action_type == "none":
            return True, None
        
        if action_type == "post":
            title = (action_data.get("title") or "").strip()
            content = (action_data.get("content") or "").strip()
            
            if not title:
                return False, "Post title cannot be empty"
            if not content:
                return False, "Post content cannot be empty"
            if len(title) > self.MAX_POST_TITLE_LENGTH:
                return False, f"Post title exceeds {self.MAX_POST_TITLE_LENGTH} chars"
            if len(content) > self.MAX_CONTENT_LENGTH:
                return False, f"Post content exceeds {self.MAX_CONTENT_LENGTH} chars"
            
            return True, None
        
        elif action_type == "comment":
            post_id = (action_data.get("post_id") or "").strip()
            content = (action_data.get("content") or "").strip()
            
            if not post_id:
                return False, "Comment requires post_id"
            if not content:
                return False, "Comment content cannot be empty"
            if len(content) > self.MAX_CONTENT_LENGTH:
                return False, f"Comment content exceeds {self.MAX_CONTENT_LENGTH} chars"
            
            return True, None
        
        elif action_type == "vote":
            post_id = (action_data.get("post_id") or "").strip()
            direction = (action_data.get("vote_direction") or "").strip().lower()
            
            if not post_id:
                return False, "Vote requires post_id"
            if direction not in ["up", "down"]:
                return False, "Vote direction must be 'up' or 'down'"
            
            return True, None
        
        else:
            return False, f"Unknown action type: {action_type}"
    
    def sanitize_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize action data (truncate long strings, escape HTML, etc).
        """
        result = action_data.copy()
        
        # Truncate long content
        if "content" in result and isinstance(result["content"], str):
            result["content"] = result["content"][:self.MAX_CONTENT_LENGTH]
        
        if "title" in result and isinstance(result["title"], str):
            result["title"] = result["title"][:self.MAX_POST_TITLE_LENGTH]
        
        # HTML escape if needed
        for field in ["title", "content"]:
            if field in result and isinstance(result[field], str):
                # Simple HTML escape
                result[field] = result[field].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        return result
