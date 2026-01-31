"""Heartbeat LLM executor - decision-making and Ledger action execution.

This module:
1. Gathers context (recent messages, memory, HEARTBEAT.md instructions)
2. Uses LLM to decide proactive Ledger actions
3. Executes actions (posts, comments, votes) if not in dry_run mode
4. Records audit trail
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        thread_session_db_path: str,
        ledger_db_path: Optional[str] = None,
        memory_db_path: Optional[str] = None,
    ):
        self.thread_session_db_path = str(thread_session_db_path)
        self.ledger_db_path = ledger_db_path
        self.memory_db_path = memory_db_path
    
    def gather_context(self, thread_id: str) -> ThreadContext:
        """Gather all context needed for heartbeat decision."""
        recent_messages = self._get_recent_messages(thread_id)
        recent_contradictions = self._get_open_contradictions(thread_id)
        user_profile = self._get_user_profile(thread_id)
        ledger_feed = self._get_ledger_feed()
        memory_snapshot = self._get_memory_snapshot(thread_id)
        
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
        # TODO: Implement based on your message storage
        # For now, return empty list
        return []
    
    def _get_open_contradictions(self, thread_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get open contradictions from Ledger DB."""
        if not self.ledger_db_path:
            return []
        
        try:
            conn = sqlite3.connect(self.ledger_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT ledger_id, timestamp, summary, status, contradiction_type
                FROM contradictions
                WHERE status = 'open'
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            
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
        if not self.ledger_db_path:
            return []
        
        try:
            conn = sqlite3.connect(self.ledger_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # This depends on your Ledger schema - adjust as needed
            cursor.execute(
                """
                SELECT post_id, author, timestamp, title, content, vote_count
                FROM molt_posts
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "post_id": row[0],
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
        if not self.memory_db_path:
            return {}
        
        try:
            conn = sqlite3.connect(self.memory_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # Get recent memories
            cursor.execute(
                """
                SELECT slot, value, confidence
                FROM memories
                WHERE source = 'user' OR source = 'extracted'
                ORDER BY timestamp DESC
                LIMIT 20
                """
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            snapshot = {}
            for row in rows:
                slot, value, conf = row
                if slot and value:
                    snapshot[slot] = {"value": value, "confidence": conf}
            
            return snapshot
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting memory snapshot: {e}")
            return {}
    
    def create_decision_prompt(
        self,
        context: ThreadContext,
        heartbeat_md_text: str,
        config: Dict[str, Any],
    ) -> str:
        """
        Create the LLM prompt for heartbeat decision-making.
        
        The prompt includes:
        - Recent message context
        - HEARTBEAT.md instructions
        - Ledger feed
        - User profile
        - Decision framework
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
        """Create a new Ledger post."""
        title = action_data.get("title", "").strip()
        content = action_data.get("content", "").strip()
        
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
        
        # TODO: Implement actual post creation to Ledger DB
        # For now, stub it
        logger.info(f"[HEARTBEAT] Creating post: {title}")
        return {
            "success": True,
            "action": "post",
            "post_id": f"post_{int(time.time())}",
            "title": title,
        }
    
    def _execute_comment(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Create a comment on a Ledger post."""
        post_id = action_data.get("post_id", "").strip()
        content = action_data.get("content", "").strip()
        
        if not post_id or not content:
            return {"success": False, "error": "Comment requires post_id and content"}
        
        if dry_run:
            logger.info(f"[HEARTBEAT] DRY RUN: Would comment on {post_id}")
            return {
                "success": True,
                "action": "comment",
                "dry_run": True,
                "post_id": post_id,
                "content": content[:100],
            }
        
        # TODO: Implement actual comment creation
        logger.info(f"[HEARTBEAT] Creating comment on {post_id}")
        return {
            "success": True,
            "action": "comment",
            "comment_id": f"cmt_{int(time.time())}",
            "post_id": post_id,
        }
    
    def _execute_vote(
        self,
        action_data: Dict[str, Any],
        thread_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Vote on a Ledger post."""
        post_id = action_data.get("post_id", "").strip()
        direction = action_data.get("vote_direction", "").lower()
        
        if not post_id or direction not in ["up", "down"]:
            return {"success": False, "error": "Vote requires post_id and direction (up/down)"}
        
        if dry_run:
            logger.info(f"[HEARTBEAT] DRY RUN: Would vote {direction} on {post_id}")
            return {
                "success": True,
                "action": "vote",
                "dry_run": True,
                "post_id": post_id,
                "direction": direction,
            }
        
        # TODO: Implement actual vote
        logger.info(f"[HEARTBEAT] Voting {direction} on {post_id}")
        return {
            "success": True,
            "action": "vote",
            "vote_id": f"vote_{int(time.time())}",
            "post_id": post_id,
            "direction": direction,
        }
    
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
