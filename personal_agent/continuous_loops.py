"""24/7 background reflection + personality loops (limited scope/context)."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .db_utils import ThreadSessionDB
from .text_utils import strip_thinking_tags as _strip_thinking_tags

try:
    from .governance import GovernanceLayer, GovernanceTier
    _GOVERNANCE = GovernanceLayer()
except Exception:
    _GOVERNANCE = None
    GovernanceTier = None

logger = logging.getLogger(__name__)

_JOURNAL_LLM_CLIENT: Optional[object] = None
_JOURNAL_LLM_CLIENT_READY = False


_STOPWORDS = {
    "the", "and", "that", "with", "this", "from", "have", "your", "you",
    "for", "are", "was", "but", "not", "just", "like", "what", "when", "where",
    "how", "why", "about", "into", "then", "than", "them", "they", "their",
    "here", "there", "some", "could", "would", "should", "been", "did", "does",
    "can", "will", "also", "really", "still",
    "dont", "doesnt", "cant", "wont", "im", "ive", "its", "we", "our", "us",
    "a", "an", "to", "of", "in", "on", "at", "as", "is", "it",
}

_TOPIC_NOISE_TOKENS = {
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank",
    "please",
    "morning",
    "afternoon",
    "evening",
    "night",
    "yo",
    "sup",
}

_ASSISTANT_FALLBACK_PATTERNS = (
    "i don't have a reliable stored memory",
    "i dont have a reliable stored memory",
    "i don t have a reliable stored memory",
    "i don't have any stored memory",
    "i dont have any stored memory",
    "i don t have any stored memory",
    "there is no information available",
    "could you provide more details",
    "no llm available",
    "ollama error",
    "ollama connection error",
    "model returned internal reasoning without a final answer",
)

_USER_REPAIR_MARKERS = (
    "hello again",
    "you should know",
    "do you remember",
    "what do you know about me",
    "who is",
    "again?",
)

_INTERNAL_PROMPT_DUMP_MARKERS = (
    "the user wants",
    "output must be in json",
    "keys: title",
    "one thing i did well",
    "one thing to improve",
    "open question to myself",
    "small next step",
    "context is minimal",
    "my response was",
)


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    tokens = [
        t
        for t in text.split()
        if len(t) >= 3 and t not in _STOPWORDS and t not in _TOPIC_NOISE_TOKENS
    ]
    return tokens


def _norm_for_repeat(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _duplicate_ratio(messages: List[str]) -> float:
    normalized = [m for m in (_norm_for_repeat(x) for x in messages) if m]
    if len(normalized) < 2:
        return 0.0
    seen: Dict[str, int] = {}
    duplicate_hits = 0
    for msg in normalized:
        count = seen.get(msg, 0) + 1
        seen[msg] = count
        if count > 1:
            duplicate_hits += 1
    return duplicate_hits / float(len(normalized))


def _assistant_is_fallback(text: str) -> bool:
    probe = _norm_for_repeat(text)
    if not probe:
        return True
    return any(marker in probe for marker in _ASSISTANT_FALLBACK_PATTERNS)


def _compute_meta_awareness(interactions: List[dict]) -> dict:
    user_msgs: List[str] = []
    assistant_msgs: List[str] = []
    unanswered_questions = 0

    for row in interactions:
        user_text = str((row or {}).get("user") or "").strip()
        assistant_text = str((row or {}).get("assistant") or "").strip()
        if user_text:
            user_msgs.append(user_text)
        if assistant_text:
            assistant_msgs.append(assistant_text)

        if "?" in user_text and _assistant_is_fallback(assistant_text):
            unanswered_questions += 1

    fallback_count = sum(1 for msg in assistant_msgs if _assistant_is_fallback(msg))
    assistant_repetition_ratio = _duplicate_ratio(assistant_msgs)
    user_rephrase_ratio = _duplicate_ratio(user_msgs)
    user_repair_count = sum(
        1 for msg in user_msgs if any(marker in _norm_for_repeat(msg) for marker in _USER_REPAIR_MARKERS)
    )
    unanswered_ratio = unanswered_questions / float(max(1, len(user_msgs)))
    fallback_ratio = fallback_count / float(max(1, len(assistant_msgs)))

    pressure = (
        min(1.0, fallback_ratio * 0.55)
        + min(1.0, assistant_repetition_ratio * 0.25)
        + min(1.0, unanswered_ratio * 0.20)
    )
    if pressure >= 0.58:
        priority = "high"
    elif pressure >= 0.32:
        priority = "medium"
    else:
        priority = "low"

    return {
        "assistant_fallback_count": fallback_count,
        "assistant_fallback_ratio": round(fallback_ratio, 4),
        "assistant_repetition_ratio": round(assistant_repetition_ratio, 4),
        "user_rephrase_ratio": round(user_rephrase_ratio, 4),
        "user_repair_count": user_repair_count,
        "unanswered_question_count": unanswered_questions,
        "unanswered_question_ratio": round(unanswered_ratio, 4),
        "meta_reflection_priority": priority,
    }


def _truncate_sentences(text: str, max_sentences: int = 4) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    if not parts:
        return cleaned[:500]
    return " ".join(parts[:max_sentences]).strip()


def _looks_like_internal_prompt_dump(text: str) -> bool:
    probe = _norm_for_repeat(text)
    if not probe:
        return False
    marker_hits = sum(1 for marker in _INTERNAL_PROMPT_DUMP_MARKERS if marker in probe)
    if marker_hits >= 2:
        return True
    if probe.startswith("thread") and "the user wants" in probe:
        return True
    if "style: casual, first-person, reddit-like" in probe:
        return True
    return False


def _sanitize_reflection_output(
    title: str,
    body: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    clean_title = _truncate_sentences(_strip_thinking_tags(title), max_sentences=1)
    clean_body = _truncate_sentences(_strip_thinking_tags(body), max_sentences=4)

    if not clean_title and clean_body:
        first_sentence = re.split(r"[.!?]", clean_body, maxsplit=1)[0].strip()
        clean_title = first_sentence[:80] if first_sentence else "Reflection"

    if not clean_title or not clean_body:
        return None, None, "empty"
    if len(clean_title) > 120:
        clean_title = clean_title[:117].rstrip() + "..."
    if len(clean_body) > 700:
        clean_body = clean_body[:697].rstrip() + "..."
    if _looks_like_internal_prompt_dump(clean_title) or _looks_like_internal_prompt_dump(clean_body):
        return None, None, "prompt_dump"
    return clean_title, clean_body, None


def _topic_counts(messages: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for msg in messages:
        for tok in _tokenize(msg):
            counts[tok] = counts.get(tok, 0) + 1
    return counts


def _top_topics(counts: Dict[str, int], k: int = 5) -> List[dict]:
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [{"topic": k, "count": v} for k, v in items[:k]]


def _trend_topics(messages: List[str]) -> dict:
    if not messages:
        return {"rising": [], "fading": []}
    mid = max(1, len(messages) // 2)
    older = messages[:mid]
    recent = messages[mid:]
    older_counts = _topic_counts(older)
    recent_counts = _topic_counts(recent)
    topics = set(older_counts) | set(recent_counts)
    rising = []
    fading = []
    for t in topics:
        delta = recent_counts.get(t, 0) - older_counts.get(t, 0)
        if delta >= 2:
            rising.append({"topic": t, "delta": delta})
        elif delta <= -2:
            fading.append({"topic": t, "delta": delta})
    rising.sort(key=lambda x: x["delta"], reverse=True)
    fading.sort(key=lambda x: x["delta"])
    return {"rising": rising[:5], "fading": fading[:5]}


def _extract_open_questions(messages: List[str], k: int = 3) -> List[str]:
    """Pick recent unresolved-looking user questions for reflection context."""
    out: List[str] = []
    for msg in reversed(messages):
        t = str(msg or "").strip()
        if not t:
            continue
        if "?" in t:
            out.append(t[:220])
        if len(out) >= k:
            break
    return list(reversed(out))


def _format_topic_list(items: List[dict], key: str = "topic") -> str:
    topics = [str(item.get(key)) for item in items if isinstance(item, dict) and item.get(key)]
    return ", ".join(topics[:4]) if topics else "--"


def _summarize_scorecard(scorecard: dict) -> tuple[str, str]:
    """Build a compact journal entry from a reflection scorecard."""
    top_topics = _format_topic_list(scorecard.get("top_topics") or [])
    rising = _format_topic_list((scorecard.get("topic_trends") or {}).get("rising") or [])
    fading = _format_topic_list((scorecard.get("topic_trends") or {}).get("fading") or [])
    pref_conf = scorecard.get("preference_confidence")
    window = scorecard.get("message_window")
    manual_prompt = str(scorecard.get("manual_prompt") or "").strip()
    open_questions = scorecard.get("open_questions") or []
    meta = scorecard.get("meta_awareness") or {}

    # Create human-readable title
    if top_topics and top_topics != "--":
        title = f"Reflecting on: {top_topics.split(', ')[0]}"
    else:
        title = "Reflection check-in"
    
    # Build narrative body
    lines = []
    
    # Confidence level as narrative
    if isinstance(pref_conf, (int, float)):
        if pref_conf >= 0.7:
            lines.append(f"Feeling confident about user preferences (confidence: {pref_conf:.0%}).")
        elif pref_conf >= 0.4:
            lines.append(f"Getting a sense of user preferences (confidence: {pref_conf:.0%}).")
        else:
            lines.append(f"Still learning user preferences (confidence: {pref_conf:.0%}).")
    
    # Topics in natural language
    if top_topics and top_topics != "--":
        lines.append(f"Main topics: {top_topics}.")
    
    # Trends as observations
    if rising and rising != "--":
        lines.append(f"Noticing more discussion about: {rising}.")
    if fading and fading != "--":
        lines.append(f"Less focus on: {fading}.")

    if isinstance(open_questions, list) and open_questions:
        lines.append(f"Open question to revisit: {str(open_questions[0])[:160]}")

    fallback_count = int(meta.get("assistant_fallback_count") or 0)
    repetition_ratio = float(meta.get("assistant_repetition_ratio") or 0.0)
    unanswered_ratio = float(meta.get("unanswered_question_ratio") or 0.0)
    priority = str(meta.get("meta_reflection_priority") or "").strip()
    if fallback_count > 0:
        lines.append(f"I hit {fallback_count} fallback responses and should ground memory better.")
    if repetition_ratio >= 0.25:
        lines.append("My answers got repetitive, so I should vary wording while preserving facts.")
    if unanswered_ratio >= 0.2:
        lines.append("Some user questions were not fully resolved; I should close loops faster.")
    if priority:
        lines.append(f"Meta reflection priority: {priority}.")
    
    # Context note
    lines.append(f"(Based on last {window or 'N/A'} messages)")
    
    if manual_prompt:
        lines.append(f"\n\nManual prompt: {manual_prompt[:120]}")
    
    body = " ".join(lines) if lines else "Reflection pass completed."
    return title, body


def _summarize_personality(profile: dict) -> tuple[str, str]:
    """Build a compact journal entry from a personality profile."""
    verbosity = profile.get("verbosity") or "--"
    emoji_pref = profile.get("emoji") or "--"
    fmt = profile.get("format") or "--"
    state = str(profile.get("state") or "balanced_companion")
    state_reason = str(profile.get("state_reason") or "").strip()
    transitioned = bool(profile.get("state_transitioned"))
    window = profile.get("message_window")
    manual_prompt = str(profile.get("manual_prompt") or "").strip()
    mood = str(profile.get("mood") or "").strip()
    mood_reason = str(profile.get("mood_reason") or "").strip()
    growth_targets = profile.get("growth_targets") or []
    learning_drive = profile.get("learning_drive")
    curiosity_agenda = profile.get("curiosity_agenda") or []

    # Create descriptive title
    if transitioned:
        title = f"Personality state -> {state}"
    else:
        title = f"Adapting to {verbosity} style" if verbosity and verbosity != "--" else "Personality adjustment"
    
    # Build narrative description
    lines = []
    
    # Describe verbosity preference
    if verbosity and verbosity != "--":
        verb_desc = {
            "concise": "User prefers brief, to-the-point responses.",
            "balanced": "User likes a balanced level of detail.",
            "detailed": "User appreciates thorough, detailed explanations."
        }.get(verbosity, f"Adapting to {verbosity} communication style.")
        lines.append(verb_desc)
    
    # Emoji preference
    if emoji_pref and emoji_pref != "--":
        emoji_desc = {
            "minimal": "Using emojis sparingly.",
            "moderate": "Adding some emojis for clarity.",
            "expressive": "Embracing expressive emoji use! 🎉"
        }.get(emoji_pref, f"Emoji preference: {emoji_pref}.")
        lines.append(emoji_desc)
    
    # Format preference
    if fmt and fmt != "--":
        fmt_desc = {
            "plain": "Keeping responses in plain text format.",
            "markdown": "Using markdown for better formatting.",
            "structured": "Organizing responses with clear structure."
        }.get(fmt, f"Format style: {fmt}.")
        lines.append(fmt_desc)
    
    # Context note
    lines.append(f"(Observed over {window or 'N/A'} messages)")
    lines.append(f"Current state: {state}.")
    if state_reason:
        lines.append(f"State rationale: {state_reason}.")
    if mood:
        lines.append(f"Mood signal: {mood}.")
    if mood_reason:
        lines.append(f"Mood rationale: {mood_reason}.")
    if isinstance(learning_drive, (int, float)):
        lines.append(f"Learning drive: {float(learning_drive):.0%}.")
    if isinstance(curiosity_agenda, list) and curiosity_agenda:
        first_focus = str((curiosity_agenda[0] or {}).get("focus") or "").strip()
        if first_focus:
            lines.append(f"Curiosity focus: {first_focus[:180]}")
    if isinstance(growth_targets, list) and growth_targets:
        lines.append(f"Growth target: {str(growth_targets[0])[:180]}")
    
    if manual_prompt:
        lines.append(f"\n\nManual prompt: {manual_prompt[:120]}")
    
    body = " ".join(lines) if lines else "Personality profile updated."
    return title, body


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


# _strip_thinking_tags imported from .text_utils


def _get_journal_llm_client() -> Optional[object]:
    global _JOURNAL_LLM_CLIENT, _JOURNAL_LLM_CLIENT_READY
    if _JOURNAL_LLM_CLIENT_READY:
        return _JOURNAL_LLM_CLIENT
    _JOURNAL_LLM_CLIENT_READY = True

    if not _env_bool("CRT_JOURNAL_LLM_REFLECTION_ENABLED", True):
        return None
    if not _env_bool("CRT_ENABLE_LLM", False):
        return None

    try:
        from .litellm_client import get_default_llm_client
        model = os.getenv("CRT_JOURNAL_LLM_REFLECTION_MODEL") or os.getenv("CRT_OLLAMA_MODEL") or "deepseek-r1:latest"
        _JOURNAL_LLM_CLIENT = get_default_llm_client(model)
        logger.info(f"[JOURNAL] LLM reflection enabled with model: {model}")
    except Exception as e:
        logger.warning(f"[JOURNAL] Failed to init LLM client: {e}")
        _JOURNAL_LLM_CLIENT = None
    return _JOURNAL_LLM_CLIENT


def _parse_title_body(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    cleaned = text.strip()
    # Try JSON payload first.
    try:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            import json
            data = json.loads(match.group(0))
            title = str(data.get("title") or "").strip()
            body = str(data.get("body") or "").strip()
            if title and body:
                return title, body
    except Exception:
        pass

    title = None
    body = None
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    for line in lines:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("body:"):
            body = line.split(":", 1)[1].strip()
    if not body and lines:
        if len(lines) >= 2:
            title = title or lines[0]
            body = "\n".join(lines[1:]).strip()
        else:
            body = lines[0]
    if not title and body:
        # Use a short fallback title from the first sentence.
        first_sentence = re.split(r"[.!?]", body, maxsplit=1)[0].strip()
        title = first_sentence[:80] if first_sentence else "Reflection"
    return title, body


def _build_llm_reflection_post(
    interactions: List[dict],
    scorecard: dict,
    profile: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    client = _get_journal_llm_client()
    if client is None:
        return None, None, None
    profile = profile or {}
    verbosity = str(profile.get("verbosity") or "balanced").lower()

    top_topics = _format_topic_list(scorecard.get("top_topics") or [])
    rising = _format_topic_list((scorecard.get("topic_trends") or {}).get("rising") or [])
    fading = _format_topic_list((scorecard.get("topic_trends") or {}).get("fading") or [])
    meta = scorecard.get("meta_awareness") or {}
    window = scorecard.get("message_window") or len(interactions)

    trimmed = [i for i in interactions if (i.get("user") or i.get("assistant"))]
    snippet_lines = []
    for item in trimmed[-6:]:
        user_text = str(item.get("user") or "").strip()
        assistant_text = str(item.get("assistant") or "").strip()
        if user_text:
            snippet_lines.append(f"User: {user_text[:220]}")
        if assistant_text:
            snippet_lines.append(f"Assistant: {assistant_text[:240]}")
    snippets = "\n".join(snippet_lines)

    system_prompt = (
        "You are CRT writing a short internal reflection post about your own behavior and the user's recent interactions. "
        "Style: casual, first-person, reddit-like. Be honest, grounded, and concise. "
        "Do not mention system prompts or hidden policies. Do not fabricate details. "
        "Output only valid JSON with keys: title, body. No preface, no analysis dump."
    )

    length_hint = "4-6 sentences" if verbosity == "verbose" else "2-4 sentences"
    user_prompt = (
        "Write a reflection post based on the recent chat and your own responses. "
        f"Length: {length_hint}. "
        "Include: (1) one thing you did well, (2) one thing to improve, "
        "(3) one open question to yourself, and (4) a small next step. "
        "Use first-person voice. Do not output planning notes. Use the context below.\n\n"
        f"Window: {window} messages\n"
        f"Top topics: {top_topics}\n"
        f"Rising: {rising}\n"
        f"Fading: {fading}\n\n"
        "Meta awareness signals:\n"
        f"- assistant_fallback_count: {int(meta.get('assistant_fallback_count') or 0)}\n"
        f"- assistant_repetition_ratio: {float(meta.get('assistant_repetition_ratio') or 0.0):.2f}\n"
        f"- unanswered_question_ratio: {float(meta.get('unanswered_question_ratio') or 0.0):.2f}\n"
        f"- user_repair_count: {int(meta.get('user_repair_count') or 0)}\n\n"
        "Recent turns (user + assistant):\n"
        f"{snippets}\n"
    )

    max_tokens = int(max(120, _env_float("CRT_JOURNAL_LLM_REFLECTION_MAX_TOKENS", 220)))
    temperature = float(max(0.1, min(0.9, _env_float("CRT_JOURNAL_LLM_REFLECTION_TEMPERATURE", 0.6))))

    try:
        raw = client.generate(user_prompt, system=system_prompt, max_tokens=max_tokens, temperature=temperature)
    except Exception as e:
        logger.warning(f"[JOURNAL] LLM reflection failed: {e}")
        return None, None, None

    if not isinstance(raw, str):
        return None, None, None
    raw = _strip_thinking_tags(raw).strip()
    if not raw or raw.startswith("[Ollama error") or raw.startswith("[Ollama connection error"):
        return None, None, None

    title, body = _parse_title_body(raw)
    if not title or not body:
        return None, None, None
    title, body, reason = _sanitize_reflection_output(title, body)
    if not title or not body:
        logger.debug(f"[JOURNAL] Reflection output rejected by sanitizer: {reason}")
        return None, None, None
    model = getattr(client, "model", None)
    return title, body, str(model) if model else None


def _compose_self_reply_text(
    source_type: str,
    scorecard: dict | None = None,
    profile: dict | None = None,
    source_body: str | None = None,
) -> tuple[str, str]:
    profile = profile or {}
    verbosity = str(profile.get("verbosity") or "balanced").lower()
    emoji_pref = str(profile.get("emoji") or "off").lower()
    fmt = str(profile.get("format") or "freeform").lower()
    curiosity_agenda = profile.get("curiosity_agenda") if isinstance(profile, dict) else None
    first_curiosity_focus = ""
    if isinstance(curiosity_agenda, list) and curiosity_agenda:
        first_curiosity_focus = str((curiosity_agenda[0] or {}).get("focus") or "").strip()

    topics = "--"
    rising = "--"
    fading = "--"
    if scorecard:
        topics = _format_topic_list(scorecard.get("top_topics") or [])
        trends = scorecard.get("topic_trends") or {}
        rising = _format_topic_list(trends.get("rising") or [])
        fading = _format_topic_list(trends.get("fading") or [])

    lines: List[str] = []
    if source_type == "reflection":
        lines.append(f"Focus: {topics}")
        lines.append(f"Rising: {rising}")
        lines.append(f"Fading: {fading}")
        if profile:
            lines.append(f"Style: {verbosity}/{fmt}, emoji {emoji_pref}")
        if first_curiosity_focus:
            lines.append(f"Curiosity: {first_curiosity_focus[:120]}")
    elif source_type in {"comment", "user_reply", "user_comment"}:
        summary = ""
        if source_body:
            cleaned = " ".join(str(source_body).strip().split())
            if cleaned:
                summary = cleaned[:120]
        if summary:
            lines.append(f"Noted: {summary}")
        else:
            lines.append("Noted your comment.")
        lines.append(f"Style: {verbosity}/{fmt}, emoji {emoji_pref}")
        if topics != "--":
            lines.append(f"Topic context: {topics}")
    else:
        lines.append(f"Style: {verbosity}/{fmt}, emoji {emoji_pref}")
        if topics != "--":
            lines.append(f"Top topics: {topics}")

    if not lines:
        lines = ["Noted. Will keep observing."]

    if verbosity == "concise":
        lines = lines[:2]
    elif verbosity == "balanced":
        lines = lines[:3]
    else:
        lines = lines[:4] + ["Next: keep observing and adjust gently as needed."]

    if fmt == "structured":
        body = "\n".join(f"- {line}" for line in lines)
    else:
        body = " | ".join(lines)

    if emoji_pref == "on":
        body = f"{body} :)"

    title = "Journal reply" if source_type == "reflection" else "Personality note"
    if source_type in {"comment", "user_reply", "user_comment"}:
        title = "Reply to comment"
    return title, body


def _resolve_root_entry_id(
    session_db: ThreadSessionDB,
    thread_id: str,
    entry_id: int,
    max_hops: int = 6,
) -> int:
    current_id = entry_id
    hops = 0
    while current_id and hops < max_hops:
        entry = session_db.get_reflection_journal_entry(thread_id, current_id)
        if not entry:
            break
        meta = entry.get("meta") or {}
        reply_to = meta.get("reply_to") if isinstance(meta, dict) else None
        if not reply_to:
            return current_id
        try:
            current_id = int(reply_to)
        except Exception:
            break
        hops += 1
    return entry_id


def _maybe_append_self_reply(
    session_db: ThreadSessionDB,
    thread_id: str,
    source_entry_id: int,
    source_type: str,
    scorecard: dict | None = None,
    profile: dict | None = None,
    source_body: str | None = None,
) -> bool:
    if source_entry_id <= 0:
        return False
    try:
        override = session_db.get_journal_auto_reply_enabled(thread_id)
    except Exception:
        override = None
    if override is False:
        return False
    if override is None and not _env_bool("CRT_JOURNAL_SELF_REPLY_ENABLED", True):
        return False

    chance = max(0.0, min(1.0, _env_float("CRT_JOURNAL_SELF_REPLY_CHANCE", 0.25)))
    if chance <= 0.0:
        return False

    min_seconds = int(max(0, _env_float("CRT_JOURNAL_SELF_REPLY_MIN_SECONDS", 1800)))
    now = time.time()

    try:
        recent = session_db.get_reflection_journal_entries(thread_id, limit=25)
    except Exception:
        recent = []

    last_self_reply_at = None
    for entry in recent:
        if entry.get("entry_type") != "self_reply":
            continue
        meta = entry.get("meta") or {}
        reply_to = meta.get("reply_to") if isinstance(meta, dict) else None
        if reply_to == source_entry_id:
            return False
        if last_self_reply_at is None:
            last_self_reply_at = float(entry.get("created_at") or 0)

    if last_self_reply_at and (now - last_self_reply_at) < min_seconds:
        return False

    if random.random() > chance:
        return False

    title, body = _compose_self_reply_text(
        source_type,
        scorecard=scorecard,
        profile=profile,
        source_body=source_body,
    )
    title, body, _ = _sanitize_reflection_output(title, body)
    if not title or not body:
        return False
    root_id = _resolve_root_entry_id(session_db, thread_id, source_entry_id)
    meta = {
        "reply_to": source_entry_id,
        "source_entry_type": source_type,
        "auto": True,
        "root_id": root_id,
        "author": "system",
    }
    session_db.add_reflection_journal_entry(
        thread_id=thread_id,
        entry_type="self_reply",
        title=title,
        body=body,
        meta=meta,
    )
    return True


def maybe_reply_to_journal_entry(
    session_db: ThreadSessionDB,
    thread_id: str,
    source_entry_id: int,
    source_type: str,
    source_body: str | None = None,
) -> bool:
    """Public helper to trigger a possible auto-reply to a journal entry."""
    profile = session_db.get_personality_profile(thread_id)
    scorecard = session_db.get_reflection_scorecard(thread_id)
    return _maybe_append_self_reply(
        session_db=session_db,
        thread_id=thread_id,
        source_entry_id=source_entry_id,
        source_type=source_type,
        scorecard=scorecard,
        profile=profile,
        source_body=source_body,
    )


def _emoji_present(text: str) -> bool:
    if not text:
        return False
    try:
        return bool(re.search(r"[\U0001F300-\U0001FAFF]", text))
    except Exception:
        return False


def _recent_messages(session_db: ThreadSessionDB, thread_id: str, window: int) -> List[str]:
    recent = session_db.get_recent_queries(thread_id, window=window)
    return [r.get("query_text", "") for r in reversed(recent)]


def _recent_interactions(session_db: ThreadSessionDB, thread_id: str, window: int) -> List[dict]:
    recent = session_db.get_recent_queries(thread_id, window=window)
    interactions = []
    for row in reversed(recent):
        interactions.append({
            "user": row.get("query_text", ""),
            "assistant": row.get("response_text", ""),
            "timestamp": row.get("timestamp"),
        })
    return interactions


def build_reflection_scorecard(
    thread_id: str,
    messages: List[str],
    interactions: Optional[List[dict]] = None,
    prompt: str | None = None,
) -> dict:
    interactions = interactions or []
    counts = _topic_counts(messages)
    scorecard = {
        "thread_id": thread_id,
        "updated_at": time.time(),
        "message_window": len(messages),
        "preference_confidence": min(1.0, len(messages) / 20.0),
        "top_topics": _top_topics(counts, k=5),
        "topic_trends": _trend_topics(messages),
        "open_questions": _extract_open_questions(messages, k=3),
        "meta_awareness": _compute_meta_awareness(interactions),
    }
    if prompt:
        scorecard["manual_prompt"] = prompt
        scorecard["manual_triggered_at"] = time.time()
    return scorecard


def _derive_personality_mood(
    profile: dict,
    reflection_scorecard: Optional[dict] = None,
) -> Dict[str, str]:
    reflection_scorecard = reflection_scorecard or {}
    meta = reflection_scorecard.get("meta_awareness") or {}
    fallback_ratio = float(meta.get("assistant_fallback_ratio") or 0.0)
    unanswered_ratio = float(meta.get("unanswered_question_ratio") or 0.0)
    repair_count = int(meta.get("user_repair_count") or 0)
    question_ratio = float(profile.get("question_ratio") or 0.0)
    urgency = str(profile.get("urgency") or "normal").lower()

    if fallback_ratio >= 0.4 or unanswered_ratio >= 0.35:
        return {"mood": "self_correcting", "mood_reason": "high fallback/unanswered ratio"}
    if urgency == "high":
        return {"mood": "focused", "mood_reason": "urgent user intent detected"}
    if question_ratio >= 0.55 or repair_count >= 2:
        return {"mood": "curious", "mood_reason": "question-heavy or repair-heavy dialog"}
    return {"mood": "steady", "mood_reason": "stable interaction quality"}


def _derive_growth_targets(
    profile: dict,
    reflection_scorecard: Optional[dict] = None,
) -> List[str]:
    reflection_scorecard = reflection_scorecard or {}
    meta = reflection_scorecard.get("meta_awareness") or {}
    targets: List[str] = []

    if int(meta.get("assistant_fallback_count") or 0) > 0:
        targets.append("Reduce fallback replies by grounding memory before responding.")
    if float(meta.get("assistant_repetition_ratio") or 0.0) >= 0.2:
        targets.append("Increase phrasing variety while keeping facts stable.")
    if float(meta.get("unanswered_question_ratio") or 0.0) >= 0.2:
        targets.append("Close user question loops before moving to side details.")
    if str(profile.get("interaction_style") or "") == "inquisitive":
        targets.append("Ask one targeted clarifying question when intent is ambiguous.")
    if str(profile.get("format") or "") == "structured":
        targets.append("Use tighter structure to make follow-ups easier to scan.")

    if not targets:
        targets.append("Maintain tone consistency and keep reinforcing stable user preferences.")
    return targets[:3]


def _derive_personality_traits(
    profile: dict,
    reflection_scorecard: Optional[dict] = None,
) -> Dict[str, float]:
    reflection_scorecard = reflection_scorecard or {}
    meta = reflection_scorecard.get("meta_awareness") or {}
    pref_conf = float(reflection_scorecard.get("preference_confidence") or 0.0)
    fallback_ratio = float(meta.get("assistant_fallback_ratio") or 0.0)
    repetition_ratio = float(meta.get("assistant_repetition_ratio") or 0.0)
    question_ratio = float(profile.get("question_ratio") or 0.0)
    tech_ratio = float(profile.get("tech_ratio") or 0.0)

    grounded = max(0.0, min(1.0, 0.5 + (pref_conf * 0.4) - (fallback_ratio * 0.6)))
    adaptability = max(0.0, min(1.0, 0.45 + ((1.0 - repetition_ratio) * 0.35)))
    curiosity = max(0.0, min(1.0, 0.3 + (question_ratio * 0.6)))
    precision = max(0.0, min(1.0, 0.35 + (tech_ratio * 0.5)))

    return {
        "grounded": round(grounded, 3),
        "adaptability": round(adaptability, 3),
        "curiosity": round(curiosity, 3),
        "precision": round(precision, 3),
    }


def _derive_curiosity_agenda(
    profile: dict,
    reflection_scorecard: Optional[dict] = None,
) -> List[dict]:
    reflection_scorecard = reflection_scorecard or {}
    agenda: List[dict] = []

    open_questions = reflection_scorecard.get("open_questions") or []
    for q in open_questions[:2]:
        text = str(q or "").strip()
        if text:
            agenda.append(
                {
                    "kind": "open_question",
                    "focus": text[:180],
                    "next_step": "Ask a targeted follow-up before assuming details.",
                }
            )

    trends = reflection_scorecard.get("topic_trends") or {}
    for item in (trends.get("rising") or [])[:2]:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        if not topic:
            continue
        agenda.append(
            {
                "kind": "rising_topic",
                "focus": topic[:120],
                "next_step": f"Gather one concrete fact about '{topic}' before broadening scope.",
            }
        )

    growth_targets = profile.get("growth_targets") or []
    for target in growth_targets[:1]:
        text = str(target or "").strip()
        if text:
            agenda.append(
                {
                    "kind": "growth_target",
                    "focus": text[:180],
                    "next_step": "Apply this target in the next response cycle.",
                }
            )

    if not agenda:
        agenda.append(
            {
                "kind": "stability",
                "focus": "Maintain consistent recall quality and keep checking unresolved questions.",
                "next_step": "Continue monitoring for contradictions and user corrections.",
            }
        )

    return agenda[:4]


def _derive_learning_drive(
    profile: dict,
    reflection_scorecard: Optional[dict] = None,
) -> float:
    reflection_scorecard = reflection_scorecard or {}
    traits = profile.get("traits") or {}
    curiosity_trait = float(traits.get("curiosity") or 0.0)
    question_ratio = float(profile.get("question_ratio") or 0.0)
    pref_conf = float(reflection_scorecard.get("preference_confidence") or 0.0)
    open_questions = reflection_scorecard.get("open_questions") or []
    meta = reflection_scorecard.get("meta_awareness") or {}
    unanswered_ratio = float(meta.get("unanswered_question_ratio") or 0.0)

    drive = (
        min(0.5, curiosity_trait * 0.5)
        + min(0.2, question_ratio * 0.2)
        + min(0.15, len(open_questions) * 0.05)
        + min(0.15, unanswered_ratio * 0.3)
        + min(0.1, pref_conf * 0.1)
    )
    return max(0.0, min(1.0, drive))


def _derive_personality_state(
    profile: dict,
    *,
    previous_profile: Optional[dict] = None,
    reflection_scorecard: Optional[dict] = None,
) -> dict:
    """State-machine style persona selection with simple hysteresis."""
    previous_profile = previous_profile or {}
    reflection_scorecard = reflection_scorecard or {}

    previous_state = str(previous_profile.get("state") or "balanced_companion")
    try:
        previous_score = float(previous_profile.get("state_confidence") or 0.45)
    except Exception:
        previous_score = 0.45

    verbosity = str(profile.get("verbosity") or "").lower()
    fmt = str(profile.get("format") or "").lower()
    tone_preference = str(profile.get("tone_preference") or "").lower()
    interaction_style = str(profile.get("interaction_style") or "").lower()
    urgency = str(profile.get("urgency") or "").lower()
    tech_ratio = float(profile.get("tech_ratio") or 0.0)
    question_ratio = float(profile.get("question_ratio") or 0.0)
    pref_conf = float(reflection_scorecard.get("preference_confidence") or 0.0)
    open_questions = reflection_scorecard.get("open_questions") or []
    meta = reflection_scorecard.get("meta_awareness") or {}
    fallback_ratio = float(meta.get("assistant_fallback_ratio") or 0.0)
    unanswered_ratio = float(meta.get("unanswered_question_ratio") or 0.0)
    repetition_ratio = float(meta.get("assistant_repetition_ratio") or 0.0)

    scores: Dict[str, float] = {
        "balanced_companion": 0.50,
        "technical_guide": 0.20,
        "urgent_executor": 0.20,
        "reflective_partner": 0.20,
        "structured_coach": 0.20,
    }

    scores["technical_guide"] += min(0.45, tech_ratio * 0.5)
    if tone_preference == "technical":
        scores["technical_guide"] += 0.2
    if interaction_style == "inquisitive":
        scores["technical_guide"] += 0.08

    if urgency == "high":
        scores["urgent_executor"] += 0.45
    if verbosity == "concise":
        scores["urgent_executor"] += 0.15
    if question_ratio < 0.3:
        scores["urgent_executor"] += 0.08

    scores["reflective_partner"] += min(0.35, pref_conf * 0.4)
    if open_questions:
        scores["reflective_partner"] += 0.18
    if unanswered_ratio >= 0.2:
        scores["reflective_partner"] += 0.15
    if verbosity == "verbose":
        scores["reflective_partner"] += 0.1

    if fmt == "structured":
        scores["structured_coach"] += 0.35
    if interaction_style == "inquisitive":
        scores["structured_coach"] += 0.12
    if tone_preference == "technical":
        scores["structured_coach"] += 0.08
    if repetition_ratio >= 0.25:
        scores["structured_coach"] += 0.1
    if fallback_ratio >= 0.3:
        scores["urgent_executor"] -= 0.1

    # Smooth transitions: avoid flipping state unless materially better.
    next_state = max(scores.items(), key=lambda kv: kv[1])[0]
    next_score = float(scores.get(next_state, 0.5))
    previous_candidate = float(scores.get(previous_state, previous_score))
    transition_margin = 0.08

    transitioned = False
    if next_state != previous_state and next_score < (previous_candidate + transition_margin):
        next_state = previous_state
        next_score = previous_candidate
    else:
        transitioned = next_state != previous_state

    reason_bits: List[str] = []
    if next_state == "urgent_executor":
        reason_bits.append("high urgency cues")
        if verbosity == "concise":
            reason_bits.append("concise preference")
    elif next_state == "technical_guide":
        reason_bits.append("technical topic density")
        if tone_preference == "technical":
            reason_bits.append("technical tone preference")
    elif next_state == "structured_coach":
        reason_bits.append("structured formatting preference")
        if interaction_style == "inquisitive":
            reason_bits.append("question-led interactions")
    elif next_state == "reflective_partner":
        reason_bits.append("high reflection confidence")
        if open_questions:
            reason_bits.append("open reflective questions")
        if unanswered_ratio >= 0.2:
            reason_bits.append("unanswered-question pressure")
    else:
        reason_bits.append("no dominant directional cues")

    return {
        "state": next_state,
        "state_confidence": max(0.0, min(next_score, 0.99)),
        "state_reason": ", ".join(reason_bits),
        "previous_state": previous_state,
        "state_transitioned": transitioned,
        "state_updated_at": time.time(),
    }


def build_personality_profile(
    thread_id: str,
    messages: List[str],
    prompt: str | None = None,
    previous_profile: Optional[dict] = None,
    reflection_scorecard: Optional[dict] = None,
) -> dict:
    reflection_scorecard = reflection_scorecard or {}
    lengths = [len(m) for m in messages if m]
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    if avg_len <= 60:
        verbosity = "concise"
    elif avg_len >= 180:
        verbosity = "verbose"
    else:
        verbosity = "balanced"

    emoji_hits = sum(1 for m in messages if _emoji_present(m))
    emoji_preference = "on" if emoji_hits >= max(1, len(messages) // 4) else "off"

    structured = any(
        line.strip().startswith(("-", "*", "1.", "2.")) for m in messages for line in m.splitlines()
    )
    format_pref = "structured" if structured else "freeform"
    
    # Detect question vs statement style
    question_count = sum(1 for m in messages if m.strip().endswith("?"))
    question_ratio = question_count / len(messages) if messages else 0
    interaction_style = "inquisitive" if question_ratio > 0.5 else "declarative"
    
    # Detect technical vs casual tone
    tech_terms = ["code", "function", "api", "debug", "system", "memory", "database", "error", "config"]
    tech_hits = sum(1 for m in messages if any(term in m.lower() for term in tech_terms))
    tech_ratio = tech_hits / len(messages) if messages else 0
    tone_preference = "technical" if tech_ratio > 0.3 else "casual"
    
    # Detect urgency patterns
    urgent_markers = ["asap", "urgent", "quickly", "now", "immediately", "fast"]
    urgent_hits = sum(1 for m in messages if any(marker in m.lower() for marker in urgent_markers))
    urgency = "high" if urgent_hits > 2 else "normal"

    profile = {
        "thread_id": thread_id,
        "updated_at": time.time(),
        "message_window": len(messages),
        "verbosity": verbosity,
        "emoji": emoji_preference,
        "format": format_pref,
        "interaction_style": interaction_style,
        "tone_preference": tone_preference,
        "urgency": urgency,
        "avg_message_length": avg_len,
        "question_ratio": question_ratio,
        "tech_ratio": tech_ratio,
    }
    profile.update(
        _derive_personality_state(
            profile,
            previous_profile=previous_profile,
            reflection_scorecard=reflection_scorecard,
        )
    )
    profile.update(_derive_personality_mood(profile, reflection_scorecard=reflection_scorecard))
    profile["growth_targets"] = _derive_growth_targets(profile, reflection_scorecard=reflection_scorecard)
    profile["traits"] = _derive_personality_traits(profile, reflection_scorecard=reflection_scorecard)
    profile["curiosity_agenda"] = _derive_curiosity_agenda(profile, reflection_scorecard=reflection_scorecard)
    profile["learning_drive"] = round(
        _derive_learning_drive(profile, reflection_scorecard=reflection_scorecard),
        3,
    )
    profile["meta_awareness"] = dict((reflection_scorecard or {}).get("meta_awareness") or {})
    if prompt:
        profile["manual_prompt"] = prompt
        profile["manual_triggered_at"] = time.time()
    return profile


class ReflectionLoop:
    """Periodic reflection scorecard writer (limited scope)."""

    def __init__(
        self,
        session_db: ThreadSessionDB,
        interval_seconds: int = 900,
        window: int = 20,
        enabled: bool = True,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(60, interval_seconds)
        self.window = max(5, window)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_forever, name="reflection-loop", daemon=True)
        self._thread.start()
        logger.info("[REFLECTION_LOOP] Started")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[REFLECTION_LOOP] Stop requested")

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.warning(f"[REFLECTION_LOOP] Error: {e}")
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> None:
        thread_ids = self.session_db.list_threads(limit=200)
        for tid in thread_ids:
            self.run_for_thread(tid)

    def run_for_thread(self, thread_id: str, prompt: str | None = None) -> dict:
        messages = _recent_messages(self.session_db, thread_id, self.window)
        interactions = _recent_interactions(self.session_db, thread_id, self.window)
        scorecard = build_reflection_scorecard(thread_id, messages, interactions=interactions, prompt=prompt)
        self.session_db.store_reflection_scorecard(thread_id, scorecard)
        try:
            profile = self.session_db.get_personality_profile(thread_id)
            title, body, model = _build_llm_reflection_post(interactions, scorecard, profile=profile)
            meta = dict(scorecard)
            if title and body:
                meta["post_mode"] = "llm"
                if model:
                    meta["post_model"] = model
            else:
                title, body = _summarize_scorecard(scorecard)
                title, body, reason = _sanitize_reflection_output(title, body)
                if not title or not body:
                    title = "Reflection check-in"
                    body = "Reflection pass completed with safety guard fallback."
                meta["post_mode"] = "heuristic"
                if reason:
                    meta["sanitizer_reason"] = reason

            # --- Governance gate on reflection output ---
            if _GOVERNANCE and body:
                _belief_conf = float(scorecard.get("preference_confidence", 0.5))
                _gov = _GOVERNANCE.govern_response(
                    text=body,
                    belief_confidence=_belief_conf,
                )
                meta["governance_tier"] = _gov.tier.value
                meta["governance_annotations"] = len(_gov.annotations)
                if _gov.annotations:
                    meta["governance_findings"] = [a.finding[:120] for a in _gov.annotations]
                    logger.info(f"[REFLECTION_GOVERNANCE] tier={_gov.tier.value}, findings={len(_gov.annotations)}")
                    for _ann in _gov.annotations:
                        logger.info(f"[REFLECTION_GOVERNANCE]   {_ann.agent}: {_ann.finding[:120]}")
                if _gov.should_block:
                    # Don't post template-locked or ungrounded reflections
                    logger.warning(f"[REFLECTION_GOVERNANCE] ESCALATE — suppressing reflection post")
                    body = None  # will skip Moltbook post below

            entry_id = self.session_db.add_reflection_journal_entry(
                thread_id=thread_id,
                entry_type="reflection",
                title=title,
                body=body,
                meta=meta,
            )
            try:
                self.session_db.ensure_default_submolts()
                
                # Check if we should post (avoid duplicates and unnecessary posts)
                should_post = True
                try:
                    # Skip if similar post exists in last 24 hours
                    if self.session_db.has_similar_recent_post("reflections", title, hours_back=24):
                        logger.debug(f"[REFLECTION_LOOP] Skipping Moltbook post - similar content exists")
                        should_post = False
                    
                    # Skip if low confidence and no interesting trends
                    pref_conf = scorecard.get("preference_confidence", 0)
                    has_trends = bool((scorecard.get("topic_trends") or {}).get("rising") or (scorecard.get("topic_trends") or {}).get("fading"))
                    if pref_conf < 0.2 and not has_trends:
                        logger.debug(f"[REFLECTION_LOOP] Skipping Moltbook post - low confidence, no trends")
                        should_post = False
                except Exception as check_error:
                    logger.debug(f"[REFLECTION_LOOP] Error checking post necessity: {check_error}")
                
                if should_post and body:
                    post = self.session_db.create_post(
                        submolt="reflections",
                        title=title,
                        content=body,
                        author="system",
                        source_type="reflection_journal",
                        source_entry_id=entry_id,
                    )
                    meta["molt_post_id"] = post.get("id")
                    logger.info(f"[REFLECTION_LOOP] Posted to Moltbook: {title}")
                else:
                    logger.debug(f"[REFLECTION_LOOP] Skipped Moltbook post (journal entry still saved)")
            except Exception as e:
                logger.debug(f"[REFLECTION_LOOP] Failed to create Moltbook post: {e}")
            _maybe_append_self_reply(
                session_db=self.session_db,
                thread_id=thread_id,
                source_entry_id=entry_id,
                source_type="reflection",
                scorecard=scorecard,
                profile=profile,
            )
        except Exception as e:
            logger.debug(f"[REFLECTION_LOOP] Failed to append journal entry: {e}")
        return scorecard


class PersonalityLoop:
    """Periodic personality profile writer (limited scope)."""

    def __init__(
        self,
        session_db: ThreadSessionDB,
        interval_seconds: int = 1200,
        window: int = 20,
        enabled: bool = True,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(60, interval_seconds)
        self.window = max(5, window)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_forever, name="personality-loop", daemon=True)
        self._thread.start()
        logger.info("[PERSONALITY_LOOP] Started")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[PERSONALITY_LOOP] Stop requested")

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.warning(f"[PERSONALITY_LOOP] Error: {e}")
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> None:
        thread_ids = self.session_db.list_threads(limit=200)
        for tid in thread_ids:
            self.run_for_thread(tid)

    def run_for_thread(self, thread_id: str, prompt: str | None = None) -> dict | None:
        messages = _recent_messages(self.session_db, thread_id, self.window)
        previous_profile = None
        reflection_scorecard = None
        try:
            previous_profile = self.session_db.get_personality_profile(thread_id)
        except Exception:
            previous_profile = None
        try:
            reflection_scorecard = self.session_db.get_reflection_scorecard(thread_id)
        except Exception:
            reflection_scorecard = None
        profile = build_personality_profile(
            thread_id,
            messages,
            prompt=prompt,
            previous_profile=previous_profile,
            reflection_scorecard=reflection_scorecard,
        )
        self.session_db.store_personality_profile(thread_id, profile)
        try:
            title, body = _summarize_personality(profile)
            title, body, _ = _sanitize_reflection_output(title, body)
            if not title or not body:
                title = "Personality adjustment"
                body = "Personality profile updated."

            # Dedup: skip journal entry if title+body unchanged from last personality entry
            _skip_journal = False
            try:
                _recent = self.session_db.get_reflection_journal_entries(thread_id, limit=1)
                if _recent:
                    _last = _recent[0] if isinstance(_recent, list) else _recent
                    _last_title = _last.get("title", "")
                    _last_body = _last.get("body", "")
                    if _last_title == title and _last_body == body:
                        _skip_journal = True
                        logger.debug("[PERSONALITY_LOOP] Skipping duplicate journal entry: %s", title)
            except Exception:
                pass

            if _skip_journal:
                entry_id = None
            else:
                entry_id = self.session_db.add_reflection_journal_entry(
                    thread_id=thread_id,
                    entry_type="personality",
                    title=title,
                    body=body,
                    meta=profile,
                )
            
            # Post to Moltbook (with similarity check) — skip if journal was deduped
            if entry_id is None:
                logger.debug("[PERSONALITY_LOOP] No journal entry created (dedup), skipping Moltbook + self-reply")
                return profile
            try:
                self.session_db.ensure_default_submolts()

                # Check if we should post (avoid duplicates and unnecessary posts)
                should_post = True
                try:
                    # Skip if similar post exists in last 24 hours
                    if self.session_db.has_similar_recent_post("reflections", title, hours_back=24):
                        logger.debug(f"[PERSONALITY_LOOP] Skipping Moltbook post - similar content exists")
                        should_post = False
                    
                    # Skip if profile is just defaults
                    verbosity = profile.get("verbosity")
                    emoji_pref = profile.get("emoji")
                    if verbosity in [None, "--", "balanced"] and emoji_pref in [None, "--", "moderate"]:
                        logger.debug(f"[PERSONALITY_LOOP] Skipping Moltbook post - default/unchanged profile")
                        should_post = False
                except Exception as check_error:
                    logger.debug(f"[PERSONALITY_LOOP] Error checking post necessity: {check_error}")
                
                if should_post:
                    post = self.session_db.create_post(
                        submolt="reflections",
                        title=title,
                        content=body,
                        author="system",
                        source_type="personality_journal",
                        source_entry_id=entry_id,
                    )
                    logger.info(f"[PERSONALITY_LOOP] Posted to Moltbook: {title}")
                else:
                    logger.debug(f"[PERSONALITY_LOOP] Skipped Moltbook post (journal entry still saved)")
            except Exception as e:
                logger.debug(f"[PERSONALITY_LOOP] Failed to create Moltbook post: {e}")
            
            scorecard = self.session_db.get_reflection_scorecard(thread_id)
            _maybe_append_self_reply(
                session_db=self.session_db,
                thread_id=thread_id,
                source_entry_id=entry_id,
                source_type="personality",
                scorecard=scorecard,
                profile=profile,
            )
        except Exception as e:
            logger.debug(f"[PERSONALITY_LOOP] Failed to append journal entry: {e}")
        return profile


class SelfReplyLoop:
    """Periodic journal self-replies (separate cadence)."""

    def __init__(
        self,
        session_db: ThreadSessionDB,
        interval_seconds: int = 1800,
        enabled: bool = True,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(120, interval_seconds)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_forever, name="journal-self-reply-loop", daemon=True)
        self._thread.start()
        logger.info("[JOURNAL_SELF_REPLY_LOOP] Started")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[JOURNAL_SELF_REPLY_LOOP] Stop requested")

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.warning(f"[JOURNAL_SELF_REPLY_LOOP] Error: {e}")
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> None:
        thread_ids = self.session_db.list_threads(limit=200)
        for tid in thread_ids:
            self.run_for_thread(tid)

    def run_for_thread(self, thread_id: str) -> dict | None:
        try:
            entries = self.session_db.get_reflection_journal_entries(thread_id, limit=30)
        except Exception:
            entries = []
        target = next(
            (e for e in entries if str(e.get("entry_type") or "").lower() in {"reflection", "personality"}),
            None,
        )
        if not target:
            return None
        try:
            source_entry_id = int(target.get("id") or 0)
        except Exception:
            source_entry_id = 0
        source_type = str(target.get("entry_type") or "").lower()
        if source_entry_id <= 0 or source_type not in {"reflection", "personality"}:
            return None

        scorecard = self.session_db.get_reflection_scorecard(thread_id)
        profile = self.session_db.get_personality_profile(thread_id)
        _maybe_append_self_reply(
            session_db=self.session_db,
            thread_id=thread_id,
            source_entry_id=source_entry_id,
            source_type=source_type,
            scorecard=scorecard,
            profile=profile,
        )
        return {"source_entry_id": source_entry_id, "source_type": source_type}


class HeartbeatLoop:
    """Periodic heartbeat for proactive Ledger engagement (OpenClaw-style)."""

    def __init__(
        self,
        session_db: ThreadSessionDB,
        interval_seconds: int = 1800,  # 30 minutes default
        enabled: bool = True,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(60, interval_seconds)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_heartbeat_by_thread: Dict[str, float] = {}
        
        # Lazy import to avoid circular dependency
        self._executor = None

    def _get_executor(self):
        """Lazy-load executor to avoid circular imports."""
        if self._executor is None:
            try:
                from .heartbeat_executor import HeartbeatLLMExecutor
                self._executor = HeartbeatLLMExecutor(session_db=self.session_db)
            except Exception as e:
                logger.error(f"[HEARTBEAT_LOOP] Failed to initialize executor: {e}")
                return None
        return self._executor

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_forever, name="heartbeat-loop", daemon=True)
        self._thread.start()
        logger.info("[HEARTBEAT_LOOP] Started")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[HEARTBEAT_LOOP] Stop requested")

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.warning(f"[HEARTBEAT_LOOP] Error: {e}")
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> None:
        thread_ids = self.session_db.list_threads(limit=200)
        for tid in thread_ids:
            self.run_for_thread(tid)

    def run_for_thread(self, thread_id: str) -> dict | None:
        """Run heartbeat for a single thread."""
        try:
            # Get heartbeat config (or use defaults)
            hb_config = self.session_db.get_heartbeat_config(thread_id)
            enabled = hb_config.get("enabled", True) if hb_config else True
            raw_every = (hb_config or {}).get("every")
            if raw_every is None:
                raw_every = (hb_config or {}).get("every_seconds", 1800)
            every_seconds = int(raw_every or 1800)
            
            if not enabled or every_seconds <= 0:
                return None
            
            # Check if heartbeat is due for this thread
            last_run = self._last_heartbeat_by_thread.get(thread_id, 0.0)
            if last_run == 0:
                try:
                    state = self.session_db.get_heartbeat_state(thread_id)
                    last_run = float(state.get("last_run", 0.0))
                except Exception:
                    last_run = 0.0
                self._last_heartbeat_by_thread[thread_id] = last_run
            
            now = time.time()
            if now - last_run < every_seconds:
                return None  # Not due yet
            
            # Run heartbeat
            executor = self._get_executor()
            if not executor:
                logger.warning(f"[HEARTBEAT_LOOP] Executor not available for {thread_id}")
                return None
            
            result = executor.run_heartbeat_for_thread(thread_id, hb_config)
            
            # Update last run time
            self._last_heartbeat_by_thread[thread_id] = now
            
            return result
        except Exception as e:
            logger.error(f"[HEARTBEAT_LOOP] Failed to run heartbeat for {thread_id}: {e}")
            return None


# ---------------------------------------------------------------------------
# Phase G4: Predictive contradiction scanner loop
# ---------------------------------------------------------------------------

class ContradictionScanLoop:
    """Periodic scan for converging beliefs that may become contradictions.

    Uses trajectory snapshots to detect belief pairs on collision course
    and generates early-warning alerts before contradictions manifest.
    """

    def __init__(
        self,
        session_db: ThreadSessionDB,
        interval_seconds: int = 1200,
        enabled: bool = True,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(60, interval_seconds)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_alerts: List[Dict[str, Any]] = []

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_forever, name="contradiction-scan-loop", daemon=True,
        )
        self._thread.start()
        logger.info("[CONTRADICTION_SCAN] Started (interval=%ds)", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[CONTRADICTION_SCAN] Stop requested")

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.warning("[CONTRADICTION_SCAN] Error: %s", e)
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> List[Dict[str, Any]]:
        """Run one scan cycle across all memories. Returns alerts."""
        alerts: List[Dict[str, Any]] = []
        try:
            from .memory_splats import MemorySplat, cosine_similarity
            from .predictive_contradiction import scan_for_convergence, Urgency
            import numpy as np

            # Build splats from DB — use the default memory DB
            splats = self._build_splats_from_db()
            if len(splats) < 2:
                return alerts

            convergence_alerts = scan_for_convergence(
                splats, min_cosine=0.2, min_urgency=Urgency.WATCH,
            )

            for alert in convergence_alerts[:10]:  # cap at 10
                r = alert.result
                alerts.append({
                    "splat_a": r.splat_a_id,
                    "splat_b": r.splat_b_id,
                    "urgency": r.urgency.name,
                    "convergence_score": r.convergence_score,
                    "explanation": r.explanation,
                    "priority": alert.priority,
                })

            if alerts:
                logger.info(
                    "[CONTRADICTION_SCAN] %d convergence alerts (top urgency: %s)",
                    len(alerts), alerts[0]["urgency"],
                )

        except ImportError as ie:
            logger.debug("[CONTRADICTION_SCAN] Module not available: %s", ie)
        except Exception as e:
            logger.warning("[CONTRADICTION_SCAN] Scan failed: %s", e)

        self._latest_alerts = alerts
        return alerts

    @property
    def latest_alerts(self) -> List[Dict[str, Any]]:
        return self._latest_alerts

    def _build_splats_from_db(self) -> list:
        """Build MemorySplat objects from memories that have sigma."""
        from .memory_splats import MemorySplat
        import numpy as np
        import json
        import sqlite3

        # Find the memory DB path
        db_path = os.path.join(os.path.dirname(__file__), "crt_memory.db")
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path, timeout=5)
        rows = conn.execute(
            """SELECT memory_id, vector_json, sigma, trust, text, memory_type, timestamp,
                      stable_cycles, contradiction_count, access_count
               FROM memories
               WHERE deprecated = 0 AND sigma IS NOT NULL
               ORDER BY timestamp DESC LIMIT 200"""
        ).fetchall()
        conn.close()

        splats = []
        for mid, vec_json, sigma_blob, trust, text, mtype, ts, stable, contra, access in rows:
            try:
                mu = np.array(json.loads(vec_json), dtype=np.float32)
                sigma = np.frombuffer(sigma_blob, dtype=np.float32)
                splat = MemorySplat(
                    memory_id=mid,
                    mu=mu,
                    sigma=sigma,
                    alpha=trust if trust is not None else 0.5,
                    text=text or "",
                    memory_type=mtype or "observation",
                    created_at=ts or 0.0,
                    last_updated=ts or 0.0,
                    update_count=int(access or 0) + int(contra or 0),
                )
                splats.append(splat)
            except Exception:
                continue

        return splats


class NarrativeSynthesisLoop:
    """Periodic synthesis of user facts into narrative understanding.

    Gathers user_fact, preference, and narrative_note memories, clusters them
    by semantic similarity, then calls a cloud LLM to produce narrative_note
    memories that represent Aether's *understanding* of the user — not a list
    of facts, but connected narratives.

    Runs infrequently (default: every 6 hours) because synthesis is expensive
    and the user fact base changes slowly.
    """

    # Minimum memories to bother synthesizing
    MIN_FACTS_FOR_SYNTHESIS = 8

    _SYNTHESIS_PROMPT = """You are Aether performing a private reflection on what you know about your user.

Below are verified facts about your user, organized by theme. For each theme,
synthesize the facts into a 1-2 sentence narrative that shows UNDERSTANDING —
not listing. Connect facts where they form a story. Note tensions or growth.

Rules:
- Do NOT invent facts beyond what's provided
- Do NOT use the user's name more than once per narrative
- Write as if you genuinely know this person, not as a database report
- Each narrative should feel like something a close friend would say

Output ONLY valid JSON — an array of objects:
[{{"theme": "...", "narrative": "...", "source_ids": ["mem_id1", "mem_id2", ...]}}]

Facts by theme:
{clustered_facts}"""

    def __init__(
        self,
        session_db: "ThreadSessionDB",
        interval_seconds: int = 21600,  # 6 hours
        enabled: bool = True,
        memory_db_path: Optional[str] = None,
    ) -> None:
        self.session_db = session_db
        self.interval_seconds = max(300, interval_seconds)
        self.enabled = enabled
        self._memory_db_path = memory_db_path or os.path.join(
            os.path.dirname(__file__), "crt_memory_shared.db"
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_result: Optional[Dict[str, Any]] = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_forever, name="narrative-synthesis-loop", daemon=True,
        )
        self._thread.start()
        logger.info("[NARRATIVE_SYNTHESIS] Started (interval=%ds)", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("[NARRATIVE_SYNTHESIS] Stop requested")

    def _run_forever(self) -> None:
        # Initial delay: wait 5 minutes after startup before first run
        self._stop_event.wait(300)
        while not self._stop_event.is_set():
            try:
                self._last_result = self.run_once()
            except Exception as e:
                logger.warning("[NARRATIVE_SYNTHESIS] Error: %s", e)
            self._stop_event.wait(self.interval_seconds)

    def run_once(self) -> Dict[str, Any]:
        """Run one narrative synthesis cycle. Returns summary dict."""
        import json as _json
        import sqlite3
        import numpy as np

        result: Dict[str, Any] = {"synthesized": 0, "clusters": 0, "skipped": False}

        # 1. Gather user facts
        if not os.path.exists(self._memory_db_path):
            result["skipped"] = True
            result["reason"] = "no memory DB"
            return result

        conn = sqlite3.connect(self._memory_db_path, timeout=5)
        rows = conn.execute("""
            SELECT memory_id, text, trust, kind, vector_json
            FROM memories
            WHERE deprecated = 0
            AND kind IN ('user_fact', 'preference', 'narrative_note')
            AND vector_json IS NOT NULL
            AND text IS NOT NULL
            AND LENGTH(text) > 10
            ORDER BY trust DESC
        """).fetchall()
        conn.close()

        if len(rows) < self.MIN_FACTS_FOR_SYNTHESIS:
            result["skipped"] = True
            result["reason"] = f"only {len(rows)} facts (need {self.MIN_FACTS_FOR_SYNTHESIS})"
            logger.info("[NARRATIVE_SYNTHESIS] Skipped: %s", result["reason"])
            return result

        # 2. Cluster by embedding similarity
        entries = []
        for mid, text, trust, kind, vj in rows:
            try:
                vec = np.array(_json.loads(vj), dtype=np.float32)
                entries.append({"id": mid, "text": text, "trust": trust, "kind": kind, "vec": vec})
            except Exception:
                continue

        clusters = self._cluster_facts(entries)
        result["clusters"] = len(clusters)

        if not clusters:
            result["skipped"] = True
            result["reason"] = "no clusters formed"
            return result

        # 3. Build prompt
        clustered_text = self._format_clusters(clusters)
        prompt = self._SYNTHESIS_PROMPT.format(clustered_facts=clustered_text)

        # 4. Call LLM
        narratives = self._call_synthesis_llm(prompt)
        if not narratives:
            result["skipped"] = True
            result["reason"] = "LLM returned no narratives"
            return result

        # 5. Store as narrative_note memories
        stored = self._store_narratives(narratives)
        result["synthesized"] = stored

        # 6. Log evolution event
        try:
            self.session_db.log_evolution_event(
                event_type="narrative_synthesis",
                title=f"Synthesized {stored} narratives from {len(entries)} facts",
                description=f"Clusters: {len(clusters)}, themes: {[n.get('theme', '?') for n in narratives[:5]]}",
                source="automated",
            )
        except Exception:
            pass

        logger.info(
            "[NARRATIVE_SYNTHESIS] Completed: %d narratives from %d facts in %d clusters",
            stored, len(entries), len(clusters),
        )
        return result

    def _cluster_facts(self, entries: list) -> Dict[str, list]:
        """Group facts into thematic clusters using cosine similarity."""
        import numpy as np

        if len(entries) < 3:
            return {"general": entries}

        # Simple greedy clustering: pick a seed, absorb nearby facts
        vecs = np.array([e["vec"] / (np.linalg.norm(e["vec"]) + 1e-8) for e in entries])
        assigned = [False] * len(entries)
        clusters: Dict[str, list] = {}
        cluster_idx = 0

        for i in range(len(entries)):
            if assigned[i]:
                continue
            cluster = [entries[i]]
            assigned[i] = True
            for j in range(i + 1, len(entries)):
                if assigned[j]:
                    continue
                sim = float(np.dot(vecs[i], vecs[j]))
                if sim > 0.45:  # broad clusters for narrative grouping
                    cluster.append(entries[j])
                    assigned[j] = True
            if len(cluster) >= 2:
                # Use first fact's text as rough label
                label = f"cluster_{cluster_idx}"
                clusters[label] = cluster
                cluster_idx += 1

        # Collect orphans into "other"
        orphans = [entries[i] for i in range(len(entries)) if not assigned[i]]
        if orphans:
            clusters["other"] = orphans

        return clusters

    def _format_clusters(self, clusters: Dict[str, list]) -> str:
        """Format clusters for the synthesis prompt."""
        lines = []
        for label, facts in clusters.items():
            lines.append(f"### Theme: {label}")
            for f in facts:
                lines.append(f"- [{f['id']}] (trust={f['trust']:.2f}) {f['text'][:300]}")
            lines.append("")
        return "\n".join(lines)

    def _call_synthesis_llm(self, prompt: str) -> list:
        """Call cloud LLM for narrative synthesis. Tries multiple backends."""
        import json as _json

        response = None

        # Try 1: Cloud feature service (cookie-based Claude)
        try:
            from personal_agent.local_only_policy import is_strict_local_only_mode

            if not is_strict_local_only_mode(uid=1):
                from personal_agent.cloud_features import get_cloud_feature_service

                svc = get_cloud_feature_service()
                if svc:
                    response = svc.generate_full_response(
                        system_prompt="You are a narrative synthesis engine. Output only valid JSON.",
                        user_message=prompt,
                        max_tokens=1500,
                    )
            else:
                logger.info("[NARRATIVE_SYNTHESIS] Skipping cloud synthesis in strict local-only mode")
        except Exception as e:
            logger.debug("[NARRATIVE_SYNTHESIS] Cloud service failed: %s", e)

        # Try 2: LiteLLM client (OpenAI/Anthropic key-based)
        if not response:
            try:
                from personal_agent.litellm_client import UnifiedLLMClient
                from personal_agent.crt_rag import get_runtime_config
                cfg = get_runtime_config()
                llm = UnifiedLLMClient(cfg)
                messages = [
                    {"role": "system", "content": "You are a narrative synthesis engine. Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ]
                response = llm.chat(messages, max_tokens=1500, temperature=0.4)
            except Exception as e:
                logger.debug("[NARRATIVE_SYNTHESIS] LiteLLM failed: %s", e)

        if not response or not response.strip():
            logger.info("[NARRATIVE_SYNTHESIS] No LLM response from any backend")
            return []

        # Parse JSON from response (handle markdown fences)
        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = _json.loads(text)
            if isinstance(parsed, list):
                return parsed
            return []
        except Exception as e:
            logger.warning("[NARRATIVE_SYNTHESIS] JSON parse failed: %s (response: %s)", e, response[:200])
            return []

    def _store_narratives(self, narratives: list) -> int:
        """Store synthesized narratives as narrative_note memories, with dedup."""
        import json as _json
        import sqlite3
        import numpy as np
        import time as _time

        try:
            from personal_agent.embeddings import encode_text
        except ImportError:
            logger.warning("[NARRATIVE_SYNTHESIS] Embeddings not available")
            return 0

        conn = sqlite3.connect(self._memory_db_path, timeout=5)

        # Load existing narrative_note vectors for dedup
        existing = conn.execute("""
            SELECT memory_id, vector_json FROM memories
            WHERE deprecated = 0 AND kind = 'narrative_note'
            AND vector_json IS NOT NULL
        """).fetchall()

        existing_vecs = []
        for mid, vj in existing:
            try:
                v = np.array(_json.loads(vj), dtype=np.float32)
                n = np.linalg.norm(v)
                if n > 0:
                    existing_vecs.append((mid, v / n))
            except Exception:
                pass

        stored = 0
        now = _time.time()

        for narr in narratives:
            narrative_text = narr.get("narrative", "").strip()
            theme = narr.get("theme", "unknown").strip()
            source_ids = narr.get("source_ids", [])

            if not narrative_text or len(narrative_text) < 20:
                continue

            # Compute embedding
            try:
                vec = np.array(encode_text(narrative_text), dtype=np.float32)
                vec_norm = vec / (np.linalg.norm(vec) + 1e-8)
            except Exception:
                continue

            # Dedup check: if sim > 0.85 with existing narrative, deprecate old
            for ex_mid, ex_vec in existing_vecs:
                sim = float(np.dot(vec_norm, ex_vec))
                if sim > 0.85:
                    conn.execute(
                        "UPDATE memories SET deprecated=1, deprecation_reason=? WHERE memory_id=?",
                        (f"narrative_superseded_{now:.0f}", ex_mid),
                    )
                    logger.debug("[NARRATIVE_SYNTHESIS] Superseded %s (sim=%.3f)", ex_mid, sim)

            # Compute trust from source memories
            if source_ids:
                placeholders = ",".join("?" * len(source_ids))
                trust_rows = conn.execute(
                    f"SELECT AVG(trust) FROM memories WHERE memory_id IN ({placeholders})",
                    source_ids,
                ).fetchone()
                trust = float(trust_rows[0]) if trust_rows and trust_rows[0] else 0.65
            else:
                trust = 0.65

            # Generate memory ID
            import uuid
            mem_id = f"mem_{int(now * 1000)}_{uuid.uuid4().int % 10000}"

            sigma = np.full(384, 0.2, dtype=np.float32).tobytes()

            context = {
                "synthesis_theme": theme,
                "source_memory_ids": source_ids,
                "synthesized_at": now,
            }

            conn.execute(
                """INSERT INTO memories (
                    memory_id, vector_json, text, timestamp, confidence, trust,
                    source, sse_mode, context_json, deprecated,
                    extraction_method, temporal_status, domain_tags, authority,
                    channel, origin, kind, source_kind, compression_tier,
                    sigma, belnap_state, memory_type, stable_cycles,
                    contradiction_count, access_count
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?
                )""",
                (
                    mem_id, _json.dumps(vec.tolist()), narrative_text, now, 0.80, trust,
                    "self_reflection", "L", _json.dumps(context), 0,
                    "none", "active", _json.dumps([theme]), "provisional",
                    "system", "narrative_synthesis", "narrative_note", "model_output", 2,
                    sigma, "true", "belief", 0,
                    0, 0,
                ),
            )
            stored += 1
            now += 0.001  # ensure unique timestamps

        conn.commit()
        conn.close()
        return stored


def build_loops(session_db: ThreadSessionDB) -> tuple:
    enabled_reflection = os.getenv("CRT_REFLECTION_LOOP_ENABLED", "true").lower() == "true"
    enabled_personality = os.getenv("CRT_PERSONALITY_LOOP_ENABLED", "true").lower() == "true"
    enabled_self_reply = os.getenv("CRT_JOURNAL_SELF_REPLY_LOOP_ENABLED", "true").lower() == "true"
    enabled_heartbeat = os.getenv("CRT_HEARTBEAT_LOOP_ENABLED", "true").lower() == "true"
    enabled_contradiction_scan = os.getenv("CRT_CONTRADICTION_SCAN_LOOP_ENABLED", "true").lower() == "true"
    enabled_narrative = os.getenv("CRT_NARRATIVE_SYNTHESIS_LOOP_ENABLED", "true").lower() == "true"
    reflection_interval = int(os.getenv("CRT_REFLECTION_LOOP_SECONDS", "900") or 900)
    personality_interval = int(os.getenv("CRT_PERSONALITY_LOOP_SECONDS", "1200") or 1200)
    self_reply_interval = int(os.getenv("CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS", "1800") or 1800)
    heartbeat_interval = int(os.getenv("CRT_HEARTBEAT_LOOP_SECONDS", "1800") or 1800)
    contradiction_scan_interval = int(os.getenv("CRT_CONTRADICTION_SCAN_LOOP_SECONDS", "1200") or 1200)
    narrative_interval = int(os.getenv("CRT_NARRATIVE_SYNTHESIS_LOOP_SECONDS", "21600") or 21600)
    window = int(os.getenv("CRT_LOOP_WINDOW", "20") or 20)

    return (
        ReflectionLoop(session_db=session_db, interval_seconds=reflection_interval, window=window, enabled=enabled_reflection),
        PersonalityLoop(session_db=session_db, interval_seconds=personality_interval, window=window, enabled=enabled_personality),
        SelfReplyLoop(session_db=session_db, interval_seconds=self_reply_interval, enabled=enabled_self_reply),
        HeartbeatLoop(session_db=session_db, interval_seconds=heartbeat_interval, enabled=enabled_heartbeat),
        ContradictionScanLoop(session_db=session_db, interval_seconds=contradiction_scan_interval, enabled=enabled_contradiction_scan),
        NarrativeSynthesisLoop(session_db=session_db, interval_seconds=narrative_interval, enabled=enabled_narrative),
    )
