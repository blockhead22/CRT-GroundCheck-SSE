"""
Time-Based Greeting System

Generates contextual greetings based on:
- Time since last interaction (minutes/hours/days)
- Time of day (morning/afternoon/evening)
- User's name from GlobalUserProfile
- Configuration from runtime_config.py

Respects config toggles and allows template customization.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .db_utils import get_thread_session_db, ThreadSessionDB
from .user_profile import GlobalUserProfile

logger = logging.getLogger(__name__)


def get_greeting_config(runtime_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract greeting configuration from runtime config."""
    cfg = runtime_config.get("greeting") if isinstance(runtime_config, dict) else None
    return cfg if isinstance(cfg, dict) else {}


def is_greeting_enabled(runtime_config: Dict[str, Any]) -> bool:
    """Check if greeting system is enabled."""
    cfg = get_greeting_config(runtime_config)
    return bool(cfg.get("enabled", True))


def get_time_of_day() -> str:
    """Get current time of day category."""
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def format_time_delta(seconds: float) -> Tuple[str, str]:
    """
    Format time delta into human-readable string and category.
    
    Returns:
        (formatted_string, category) where category is "minutes", "hours", "days", or "weeks"
    
    Examples:
        - 300 seconds -> ("5 minutes", "minutes")
        - 7200 seconds -> ("2 hours", "hours")
        - 172800 seconds -> ("2 days", "days")
    """
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7
    
    if minutes < 2:
        return "just now", "minutes"
    elif minutes < 60:
        mins = int(minutes)
        return f"{mins} minute{'s' if mins != 1 else ''}", "minutes"
    elif hours < 24:
        hrs = int(hours)
        return f"{hrs} hour{'s' if hrs != 1 else ''}", "hours"
    elif days < 7:
        d = int(days)
        return f"{d} day{'s' if d != 1 else ''}", "days"
    else:
        w = int(weeks)
        return f"{w} week{'s' if w != 1 else ''}", "weeks"


class GreetingSystem:
    """
    Generates contextual, time-aware greetings for chat sessions.
    
    Uses:
    - Thread session tracking DB for last_active timestamp
    - GlobalUserProfile for user's name
    - Runtime config for templates and toggles
    """
    
    # Default templates (can be overridden via config)
    DEFAULT_TEMPLATES = {
        "new_user": "Hello! I'm your AI assistant. I'm here to help you with questions and tasks.",
        "returning_minutes": "Welcome back!",
        "returning_hours": "Welcome back! It's been {time_delta} since we last chatted.",
        "returning_days": "Hey {name}! It's been {time_delta}. Good to see you again!",
        "returning_weeks": "It's been a while, {name}! ({time_delta}) Welcome back.",
        "morning": "Good morning{name_suffix}!",
        "afternoon": "Good afternoon{name_suffix}!",
        "evening": "Good evening{name_suffix}!",
        "night": "Hello{name_suffix}!",
    }
    
    def __init__(
        self, 
        runtime_config: Dict[str, Any],
        session_db: Optional[ThreadSessionDB] = None,
        user_profile: Optional[GlobalUserProfile] = None
    ):
        self.runtime_config = runtime_config
        self.config = get_greeting_config(runtime_config)
        self.session_db = session_db or get_thread_session_db()
        self.user_profile = user_profile or GlobalUserProfile()
        
        # Load templates from config or use defaults
        self.templates = {
            **self.DEFAULT_TEMPLATES,
            **(self.config.get("templates") or {})
        }
        
        # Greeting style: "time_based" (default), "time_of_day", "simple"
        self.style = self.config.get("style", "time_based")
    
    def get_user_name(self) -> Optional[str]:
        """Get user's name from profile."""
        try:
            fact = self.user_profile.get_fact("name")
            if fact and fact.value:
                # Return first name only for friendlier greeting
                return fact.value.split()[0]
        except Exception as e:
            logger.debug(f"[GREETING] Could not get user name: {e}")
        return None
    
    def should_show_greeting(self, thread_id: str) -> bool:
        """
        Determine if greeting should be shown for this thread.
        
        Returns True if:
        - Greeting is enabled in config
        - Greeting hasn't been shown yet in this session
        - This is the first message in the thread
        """
        if not is_greeting_enabled(self.runtime_config):
            return False
        
        session = self.session_db.get_or_create_session(thread_id)
        
        # Don't show greeting if already shown
        if session.get('greeting_shown'):
            return False
        
        # Show greeting on first message
        if session.get('message_count', 0) == 0:
            return True
        
        # Show greeting if returning after significant time (configurable)
        min_absence_seconds = self.config.get("min_absence_for_greeting", 3600)  # 1 hour default
        time_since_last = time.time() - session.get('last_active', time.time())
        
        return time_since_last > min_absence_seconds
    
    def generate_greeting(self, thread_id: str) -> Optional[str]:
        """
        Generate a contextual greeting for the thread.
        
        Returns None if greeting should not be shown.
        """
        if not self.should_show_greeting(thread_id):
            return None
        
        session = self.session_db.get_or_create_session(thread_id)
        user_name = self.get_user_name()
        
        # Determine greeting based on style and context
        if self.style == "simple":
            greeting = self._generate_simple_greeting(user_name)
        elif self.style == "time_of_day":
            greeting = self._generate_time_of_day_greeting(user_name)
        else:  # "time_based" (default)
            greeting = self._generate_time_based_greeting(session, user_name)
        
        # Mark greeting as shown
        self.session_db.mark_greeting_shown(thread_id)
        
        return greeting
    
    def _generate_simple_greeting(self, user_name: Optional[str]) -> str:
        """Generate a simple greeting."""
        if user_name:
            return f"Hello, {user_name}!"
        return "Hello!"
    
    def _generate_time_of_day_greeting(self, user_name: Optional[str]) -> str:
        """Generate greeting based on time of day."""
        tod = get_time_of_day()
        template = self.templates.get(tod, "Hello{name_suffix}!")
        
        name_suffix = f", {user_name}" if user_name else ""
        return template.format(name_suffix=name_suffix, name=user_name or "")
    
    def _generate_time_based_greeting(
        self, 
        session: dict, 
        user_name: Optional[str]
    ) -> str:
        """
        Generate greeting based on time since last interaction.
        
        Combines time delta info with time-of-day for natural greetings.
        """
        last_active = session.get('last_active', 0)
        first_created = session.get('first_created', time.time())
        message_count = session.get('message_count', 0)
        
        # New user (never interacted)
        if message_count == 0 or last_active == 0:
            template = self.templates.get("new_user", "Hello! I'm your AI assistant.")
            return self._format_template(template, user_name=user_name)
        
        # Calculate time since last interaction
        time_since = time.time() - last_active
        time_str, category = format_time_delta(time_since)
        
        # Select template based on absence duration
        template_key = f"returning_{category}"
        template = self.templates.get(template_key, self.templates.get("returning_hours", "Welcome back!"))
        
        # Format with variables
        return self._format_template(
            template,
            user_name=user_name,
            time_delta=time_str,
        )
    
    def _format_template(
        self, 
        template: str, 
        user_name: Optional[str] = None,
        time_delta: str = "",
    ) -> str:
        """Format template with available variables."""
        # Handle name variations
        name = user_name or "there"
        name_suffix = f", {user_name}" if user_name else ""
        
        try:
            return template.format(
                name=name,
                name_suffix=name_suffix,
                time_delta=time_delta,
            )
        except KeyError:
            # Template has unrecognized placeholders, return as-is
            return template


def get_time_based_greeting(
    thread_id: str,
    runtime_config: Dict[str, Any],
    session_db: Optional[ThreadSessionDB] = None,
    user_profile: Optional[GlobalUserProfile] = None
) -> Optional[str]:
    """
    Convenience function to generate a greeting for a thread.
    
    Args:
        thread_id: Thread identifier
        runtime_config: CRT runtime configuration
        session_db: Optional ThreadSessionDB instance
        user_profile: Optional GlobalUserProfile instance
        
    Returns:
        Greeting string if one should be shown, None otherwise
    """
    system = GreetingSystem(
        runtime_config=runtime_config,
        session_db=session_db,
        user_profile=user_profile
    )
    return system.generate_greeting(thread_id)
