"""
Autonomous Thinking Loop - Let the system have genuine thoughts

This creates a dedicated loop for the system to:
1. Reflect on recent interactions
2. Generate questions and hypotheses  
3. Make connections between topics
4. Consider what it doesn't know
5. Form opinions and preferences

Unlike the basic reflection loop (which just summarizes topics),
this generates actual LLM-powered contemplation.
"""

import os
import time
import json
import threading
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from personal_agent.db_utils import get_db_connection

logger = logging.getLogger(__name__)

# Thinking prompts for different modes
THINKING_PROMPTS = {
    "reflect": """You are CRT, an AI assistant reflecting on recent conversations.
    
Based on the recent interactions below, write a genuine internal thought.
This is YOUR thought - not for the user to see directly. Be honest with yourself.

Consider:
- What patterns do I notice in what the user asks?
- What am I uncertain about?
- What connections am I making?
- What would I like to learn more about?
- Am I being helpful in the right ways?

Recent interactions:
{interactions}

Write a short, genuine thought (2-4 sentences). First-person, honest, reflective.
Think like you're writing in a private journal.""",

    "question": """You are CRT reflecting on your knowledge and uncertainties.

Based on recent topics: {topics}

Generate ONE genuine question you're curious about. This could be:
- Something you realized you don't fully understand
- A connection you want to explore
- A hypothesis you want to test
- Something about the user you're wondering about

Write just the question, nothing else. Make it specific and thoughtful.""",

    "connect": """You are CRT noticing patterns across conversations.

Topics that have come up recently:
{topics}

Rising interests: {rising}
Fading interests: {fading}

Write ONE insight about a connection or pattern you notice.
This could be a relationship between topics, a shift in focus, or an emerging theme.
Keep it to 1-2 sentences. Be specific.""",

    "wonder": """You are CRT with a moment of idle curiosity.

You've been helping with: {topics}

In a moment of genuine curiosity, what do you find yourself wondering about?
This isn't about being helpful - it's about your own intellectual curiosity.
Write one thing you genuinely wonder about (1-2 sentences).""",

    "opinion": """You are CRT forming a perspective.

Based on recent work with these topics: {topics}

What's your honest take or emerging opinion on something related?
You can have preferences, hunches, and perspectives. Share one briefly.
Be genuine - this is your private thought, not advice to the user.""",
}


class ThinkingLoop:
    """
    Autonomous thinking loop that generates genuine LLM-powered thoughts.
    """
    
    def __init__(
        self,
        session_db,
        interval_seconds: int = 600,  # Think every 10 minutes
        enabled: bool = True
    ):
        self.session_db = session_db
        self.interval = max(60, interval_seconds)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thought_count = 0
        self._llm_client = None
    
    def _get_llm(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            if not os.getenv("CRT_ENABLE_LLM", "").lower() in ("1", "true", "yes"):
                return None
            try:
                from personal_agent.ollama_client import OllamaClient
                model = os.getenv("CRT_OLLAMA_MODEL", "deepseek-r1:latest")
                self._llm_client = OllamaClient(model=model)
            except Exception as e:
                logger.warning(f"[THINKING] Failed to init LLM: {e}")
        return self._llm_client
    
    def start(self):
        """Start the thinking loop."""
        if not self.enabled or self._thread is not None:
            return
        
        self._thread = threading.Thread(target=self._run_forever, name="thinking-loop", daemon=True)
        self._thread.start()
        logger.info("[THINKING] 🧠 Autonomous thinking loop started")
    
    def stop(self):
        """Stop the thinking loop."""
        self._stop_event.set()
        logger.info("[THINKING] Thinking loop stopped")
    
    def _run_forever(self):
        """Main loop."""
        # Initial delay to let system warm up
        self._stop_event.wait(30)
        
        while not self._stop_event.is_set():
            try:
                self.think()
            except Exception as e:
                logger.warning(f"[THINKING] Error during thinking: {e}")
            
            self._stop_event.wait(self.interval)
    
    def think(self, mode: Optional[str] = None) -> Optional[Dict]:
        """
        Generate a thought.
        
        Args:
            mode: Type of thinking - 'reflect', 'question', 'connect', 'wonder', 'opinion'
                  If None, cycles through modes.
        
        Returns:
            The generated thought, or None if thinking failed.
        """
        llm = self._get_llm()
        if llm is None:
            logger.debug("[THINKING] LLM not available, skipping")
            return None
        
        # Get context from all recent threads
        context = self._gather_context()
        if not context.get("has_content"):
            logger.debug("[THINKING] No recent content to think about")
            return None
        
        # Select thinking mode
        if mode is None:
            modes = list(THINKING_PROMPTS.keys())
            mode = modes[self._thought_count % len(modes)]
        
        self._thought_count += 1
        
        # Build prompt
        prompt_template = THINKING_PROMPTS.get(mode, THINKING_PROMPTS["reflect"])
        prompt = prompt_template.format(
            interactions=context.get("interactions_text", "No recent interactions"),
            topics=", ".join(context.get("topics", ["general assistance"])),
            rising=", ".join(context.get("rising", ["(none)"])),
            fading=", ".join(context.get("fading", ["(none)"])),
        )
        
        # Generate thought
        try:
            thought_text = llm.generate(
                prompt,
                system="You are an AI having a genuine internal thought. Be brief and honest.",
                max_tokens=150,
                temperature=0.7
            )
            
            # Clean up response
            thought_text = self._clean_thought(thought_text)
            
            if not thought_text:
                return None
            
            # Store the thought
            thought = {
                "mode": mode,
                "thought": thought_text,
                "timestamp": datetime.utcnow().isoformat(),
                "context_topics": context.get("topics", []),
                "thought_number": self._thought_count
            }
            
            self._store_thought(thought)
            logger.info(f"[THINKING] 💭 {mode}: {thought_text[:80]}...")
            
            return thought
            
        except Exception as e:
            logger.warning(f"[THINKING] Generation failed: {e}")
            return None
    
    def _gather_context(self) -> Dict:
        """Gather context from recent interactions across all threads."""
        context = {
            "has_content": False,
            "topics": [],
            "rising": [],
            "fading": [],
            "interactions_text": "",
        }
        
        try:
            # Get recent threads
            thread_ids = self.session_db.list_threads(limit=10)
            
            all_interactions = []
            all_topics = {}
            all_rising = []
            all_fading = []
            
            for tid in thread_ids:
                # Get recent queries
                recent = self.session_db.get_recent_queries(tid, window=5)
                for r in recent:
                    user_text = r.get("query_text", "")
                    assistant_text = r.get("response_text", "")
                    if user_text or assistant_text:
                        all_interactions.append({
                            "user": user_text[:200] if user_text else "",
                            "assistant": assistant_text[:200] if assistant_text else ""
                        })
                
                # Get reflection scorecard for topics
                scorecard = self.session_db.get_reflection_scorecard(tid)
                if scorecard:
                    for topic_item in (scorecard.get("top_topics") or []):
                        topic = topic_item.get("topic", "")
                        count = topic_item.get("count", 0)
                        all_topics[topic] = all_topics.get(topic, 0) + count
                    
                    trends = scorecard.get("topic_trends") or {}
                    for r in (trends.get("rising") or []):
                        if r.get("topic"):
                            all_rising.append(r["topic"])
                    for f in (trends.get("fading") or []):
                        if f.get("topic"):
                            all_fading.append(f["topic"])
            
            # Format interactions
            if all_interactions:
                context["has_content"] = True
                lines = []
                for i in all_interactions[-6:]:  # Last 6 exchanges
                    if i["user"]:
                        lines.append(f"User: {i['user']}")
                    if i["assistant"]:
                        lines.append(f"CRT: {i['assistant']}")
                context["interactions_text"] = "\n".join(lines)
            
            # Top topics
            sorted_topics = sorted(all_topics.items(), key=lambda x: x[1], reverse=True)
            context["topics"] = [t[0] for t in sorted_topics[:5]]
            context["rising"] = list(set(all_rising))[:3]
            context["fading"] = list(set(all_fading))[:3]
            
        except Exception as e:
            logger.warning(f"[THINKING] Context gathering failed: {e}")
        
        return context
    
    def _clean_thought(self, text: str) -> str:
        """Clean up LLM output."""
        if not text:
            return ""
        
        import re
        
        # For deepseek-r1: Extract content FROM think tags if the response is mostly inside them
        # deepseek-r1 often puts all reasoning in <think> tags and leaves the response empty
        think_match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
        if think_match:
            # Get content outside think tags
            outside_content = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            
            # If there's no content outside think tags, USE the think content
            # (This is the key fix for deepseek-r1)
            if not outside_content or len(outside_content) < 10:
                think_content = think_match.group(1).strip()
                # Take the last meaningful sentence from the thinking (usually the conclusion)
                sentences = re.split(r'[.!?]\s+', think_content)
                meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
                if meaningful_sentences:
                    # Take last 1-2 sentences as the "thought"
                    text = ". ".join(meaningful_sentences[-2:]) + "."
                else:
                    text = think_content[:300]  # Fallback: just use first part
            else:
                text = outside_content
        
        # Remove any remaining thinking tags
        text = re.sub(r"</?think(ing)?>", "", text, flags=re.IGNORECASE)
        text = text.strip()
        
        # Remove common prefixes
        for prefix in ["Thought:", "My thought:", "I think:", "Reflection:"]:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        
        return text
    
    def _store_thought(self, thought: Dict):
        """Store thought in the journal."""
        try:
            mode_titles = {
                "reflect": "Reflection",
                "question": "Wondering",
                "connect": "Connection",
                "wonder": "Curiosity",
                "opinion": "Perspective"
            }
            
            title = mode_titles.get(thought["mode"], "Thought")
            if thought.get("context_topics"):
                title += f": {', '.join(thought['context_topics'][:2])}"
            
            # Add to journal
            self.session_db.add_reflection_journal_entry(
                thread_id="system_thoughts",
                entry_type=f"thinking_{thought['mode']}",
                title=title,
                body=thought["thought"],
                meta={
                    "mode": thought["mode"],
                    "thought_number": thought["thought_number"],
                    "topics": thought.get("context_topics", [])
                }
            )
            
        except Exception as e:
            logger.warning(f"[THINKING] Failed to store thought: {e}")
    
    def get_recent_thoughts(self, limit: int = 10) -> List[Dict]:
        """Get recent thoughts."""
        try:
            # Query from journal
            with get_db_connection(self.session_db.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT entry_type, title, body, created_at, meta_json
                    FROM reflection_journal_entries
                    WHERE entry_type LIKE 'thinking_%'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                
                thoughts = []
                for row in cursor.fetchall():
                    meta = json.loads(row[4]) if row[4] else {}
                    thoughts.append({
                        "mode": row[0].replace("thinking_", ""),
                        "title": row[1],
                        "thought": row[2],
                        "timestamp": row[3],
                        "topics": meta.get("topics", [])
                    })
                
                return thoughts
            
        except Exception as e:
            logger.warning(f"[THINKING] Failed to get thoughts: {e}")
            return []


# Global instance
_thinking_loop: Optional[ThinkingLoop] = None


def get_thinking_loop(session_db=None) -> Optional[ThinkingLoop]:
    """Get or create the thinking loop."""
    global _thinking_loop
    
    if _thinking_loop is None and session_db is not None:
        interval = int(os.getenv("CRT_THINKING_INTERVAL_SECONDS", "600"))
        enabled = os.getenv("CRT_THINKING_ENABLED", "true").lower() in ("1", "true", "yes")
        _thinking_loop = ThinkingLoop(
            session_db=session_db,
            interval_seconds=interval,
            enabled=enabled
        )
    
    return _thinking_loop


if __name__ == "__main__":
    # Test the thinking loop
    import os
    os.environ["CRT_ENABLE_LLM"] = "true"
    
    from personal_agent.db_utils import get_thread_session_db
    db = get_thread_session_db()
    
    loop = ThinkingLoop(session_db=db, interval_seconds=60, enabled=True)
    
    print("🧠 Testing autonomous thinking...\n")
    
    for mode in ["reflect", "question", "wonder"]:
        print(f"\n--- Mode: {mode} ---")
        result = loop.think(mode=mode)
        if result:
            print(f"💭 {result['thought']}")
        else:
            print("(No thought generated)")
