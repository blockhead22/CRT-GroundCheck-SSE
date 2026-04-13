"""Preference / formatting / confirmation helpers extracted from routes/chat.py."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from personal_agent.episodic_memory import get_episodic_manager

logger = logging.getLogger(__name__)


def _format_style_instruction(
    style_profile: Optional[Dict[str, Any]],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> str:
    if not style_profile:
        return ""
    label = str(style_profile.get("tone_label") or "balanced").lower()
    personality_profile = personality_profile or {}
    verbosity_pref = str(personality_profile.get("verbosity") or "").lower()
    emoji_pref = str(personality_profile.get("emoji") or "").lower()
    format_pref = str(personality_profile.get("format") or "").lower()
    if label == "playful":
        base = (
            "Tone: playful and witty when appropriate; mirror the user's humor. "
            "Shift to serious and grounded when the topic is serious. Keep language natural and not overly formal."
        )
    elif label == "serious":
        base = (
            "Tone: calm, direct, and empathetic. Avoid jokes unless the user cues humor. "
            "Keep language natural and not overly formal."
        )
    elif label == "adaptive":
        base = (
            "Tone: adaptive; light when the user is playful, grounded when the user is serious. "
            "Keep a warm, consistent voice. Keep language natural and not overly formal."
        )
    else:
        base = (
            "Tone: friendly and flexible; lightly playful when the user is playful, "
            "and serious when they are serious. Keep language natural and not overly formal."
        )

    verbosity_line = ""
    if verbosity_pref == "concise":
        verbosity_line = "Prefer concise responses unless detail is explicitly requested."
    elif verbosity_pref == "verbose":
        verbosity_line = "Prefer detailed responses with concrete steps and examples."

    emoji_line = ""
    if emoji_pref == "off":
        emoji_line = "Avoid emojis unless the user uses them first."
    elif emoji_pref == "on":
        emoji_line = "Emojis are welcome if they match the tone."

    format_line = ""
    if format_pref == "structured":
        format_line = "Prefer structured formatting (short sections or bullets) when it helps clarity."
    elif format_pref == "freeform":
        format_line = "Prefer natural paragraphs over heavy bulleting unless requested."

    extras = " ".join([s for s in [verbosity_line, emoji_line, format_line] if s])
    return f"{base} {extras}".strip()


def _detect_response_mood(
    response: str,
    thinking: str = "",
    confidence: float = 0.7,
    contradiction_detected: bool = False,
) -> Dict[str, Any]:
    """Detect the mood/tone of a response for UI visualization."""
    response_lower = response.lower()
    thinking_lower = thinking.lower() if thinking else ""

    triggers: List[str] = []
    mood = "calm"
    intensity = 0.3
    thinking_depth = min(1.0, len(thinking) / 2000) if thinking else 0.0

    warm_words = [
        "happy", "glad", "great", "wonderful", "love", "enjoy", "excited",
        "welcome", "pleasure", "delighted", "awesome", "fantastic", "\U0001f60a", "\U0001f389",
    ]
    warm_count = sum(1 for w in warm_words if w in response_lower)

    playful_words = [
        "haha", "lol", "funny", "joke", "silly", "\U0001f604", "\U0001f602", "\U0001f923",
        "quirky", "whimsical", "amusing", "teasing",
    ]
    playful_count = sum(1 for w in playful_words if w in response_lower)

    intense_words = [
        "important", "critical", "crucial", "significant", "challenge",
        "complex", "difficult", "serious", "careful", "warning", "consider",
        "however", "but", "actually", "contradiction", "conflict",
    ]
    intense_count = sum(1 for w in intense_words if w in response_lower or w in thinking_lower)

    curious_words = [
        "interesting", "wonder", "curious", "fascinating", "intriguing",
        "hmm", "perhaps", "maybe", "what if", "\U0001f914",
    ]
    curious_count = sum(1 for w in curious_words if w in response_lower or w in thinking_lower)

    uncertain_words = [
        "unsure", "uncertain", "don't know", "not sure", "might be",
        "possibly", "i think", "seems like", "could be",
    ]
    uncertain_count = sum(1 for w in uncertain_words if w in response_lower)

    deep_thinking_words = [
        "analyzing", "considering", "evaluating", "weighing",
        "multiple", "factors", "implications", "reasoning",
        "therefore", "because", "evidence", "conclusion",
    ]
    deep_count = sum(1 for w in deep_thinking_words if w in thinking_lower)

    counts = {
        "warm": warm_count,
        "playful": playful_count,
        "intense": intense_count + (2 if contradiction_detected else 0),
        "curious": curious_count,
        "uncertain": uncertain_count,
    }

    max_mood = max(counts, key=counts.get)  # type: ignore[arg-type]
    max_count = counts[max_mood]

    if max_count >= 2:
        mood = max_mood
        triggers.append(f"{mood}_keywords")

    if contradiction_detected:
        intensity = max(intensity, 0.7)
        triggers.append("contradiction")

    if thinking_depth > 0.5:
        intensity = max(intensity, 0.5 + thinking_depth * 0.3)
        triggers.append("deep_thinking")

    if deep_count >= 3:
        intensity = max(intensity, 0.6)
        mood = "intense"
        triggers.append("complex_reasoning")

    if confidence < 0.5:
        mood = "uncertain"
        intensity = 0.4
        triggers.append("low_confidence")

    if playful_count >= 2:
        mood = "playful"
        intensity = min(0.6, intensity)

    if warm_count >= 3:
        mood = "warm"
        intensity = max(0.4, min(0.7, intensity))

    return {
        "mood": mood,
        "intensity": round(min(1.0, intensity), 2),
        "thinking_depth": round(thinking_depth, 2),
        "triggers": triggers,
    }


def _get_verbosity_preference(thread_id: str, memory_system) -> Optional[str]:
    try:
        episodic_mgr = get_episodic_manager(memory_system=memory_system)
        ctx = episodic_mgr.get_user_context()
        prefs = ctx.get("preferences", {}) if isinstance(ctx, dict) else {}
        response_style = prefs.get("response_style", {}) if isinstance(prefs, dict) else {}
        verbosity = response_style.get("verbosity", {}) if isinstance(response_style, dict) else {}
        value = verbosity.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    except Exception as e:
        logger.debug(f"[PREF] Failed to read verbosity preference for {thread_id}: {e}")
        return None


def _get_preference_profile(thread_id: str, memory_system) -> Dict[str, Any]:
    """Load episodic preferences payload for routing/prompt adaptation."""
    try:
        episodic_mgr = get_episodic_manager(memory_system=memory_system)
        ctx = episodic_mgr.get_user_context()
        prefs = ctx.get("preferences", {}) if isinstance(ctx, dict) else {}
        if isinstance(prefs, dict):
            return prefs
    except Exception as e:
        logger.debug(f"[PREF] Failed to load preference profile for {thread_id}: {e}")
    return {}


def _format_preference_instruction(preference_profile: Optional[Dict[str, Any]]) -> str:
    """Create concise, high-confidence preference constraints for stream prompts."""
    if not isinstance(preference_profile, dict):
        return ""

    response_style = preference_profile.get("response_style")
    if not isinstance(response_style, dict):
        response_style = preference_profile
    code_style = preference_profile.get("code_style")
    if not isinstance(code_style, dict):
        code_style = {}

    def _pref_value(pref_map: Dict[str, Any], key: str) -> tuple[str, float]:
        raw = pref_map.get(key)
        if isinstance(raw, dict):
            val = str(raw.get("value") or "").strip().lower()
            try:
                conf = float(raw.get("confidence") or 0.0)
            except Exception:
                conf = 0.0
            return val, conf
        if raw is None:
            return "", 0.0
        return str(raw).strip().lower(), 0.5

    lines: List[str] = []

    verbosity, verbosity_conf = _pref_value(response_style, "verbosity")
    if verbosity_conf >= 0.6:
        if verbosity == "concise":
            lines.append("Keep responses concise unless the user asks for detail.")
        elif verbosity == "verbose":
            lines.append("Provide detailed responses with context by default.")

    fmt, fmt_conf = _pref_value(response_style, "format")
    if fmt_conf >= 0.6:
        if fmt == "structured":
            lines.append("Prefer structured formatting (sections/lists) when helpful.")
        elif fmt == "freeform":
            lines.append("Prefer natural prose over list-heavy formatting.")

    emoji, emoji_conf = _pref_value(response_style, "emoji_usage")
    if emoji_conf >= 0.6:
        if emoji == "none":
            lines.append("Do not use emoji.")
        elif emoji == "minimal":
            lines.append("Use emoji sparingly.")

    citation, citation_conf = _pref_value(response_style, "citation_style")
    if citation_conf >= 0.6 and citation == "required":
        lines.append("When providing factual claims, include sources where possible.")

    language, language_conf = _pref_value(code_style, "language")
    if language_conf >= 0.6 and language:
        lines.append(f"For code examples, prefer {language} unless user asks otherwise.")

    if not lines:
        return ""
    return "LEARNED USER PREFERENCES:\n" + "\n".join(f"- {line}" for line in lines)


def _normalize_confirmation_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_confirmation_yes(text: str) -> bool:
    normalized = _normalize_confirmation_text(text)
    if not normalized:
        return False
    direct = {
        "yes",
        "y",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "do it",
        "confirm",
        "confirmed",
        "please do",
        "set it",
        "schedule it",
    }
    if normalized in direct:
        return True
    return bool(
        re.search(
            r"\b(confirm|go ahead|sounds good|that works|please schedule|yes please)\b",
            normalized,
        )
    )


def _is_confirmation_no(text: str) -> bool:
    normalized = _normalize_confirmation_text(text)
    if not normalized:
        return False
    direct = {
        "no",
        "n",
        "nope",
        "nah",
        "cancel",
        "stop",
        "nevermind",
        "never mind",
        "dont",
        "don't",
        "do not",
    }
    if normalized in direct:
        return True
    return bool(re.search(r"\b(cancel|don't schedule|do not schedule|skip it)\b", normalized))


def _format_reminder_time(ts: Optional[float]) -> str:
    try:
        value = float(ts or 0.0)
    except Exception:
        value = 0.0
    if value <= 0:
        return "the requested time"
    try:
        return datetime.fromtimestamp(value).strftime("%A, %B %d at %I:%M %p")
    except Exception:
        return "the requested time"
