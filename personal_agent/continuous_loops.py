"""24/7 background reflection + personality loops (limited scope/context)."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from typing import Dict, List

from .db_utils import ThreadSessionDB

logger = logging.getLogger(__name__)


_STOPWORDS = {
    "the", "and", "that", "with", "this", "from", "have", "your", "you",
    "for", "are", "was", "but", "not", "just", "like", "what", "when", "where",
    "how", "why", "about", "into", "then", "than", "them", "they", "their",
    "here", "there", "some", "could", "would", "should", "been", "did", "does",
    "dont", "doesnt", "cant", "wont", "im", "ive", "its", "we", "our", "us",
    "a", "an", "to", "of", "in", "on", "at", "as", "is", "it",
}


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    tokens = [t for t in text.split() if len(t) >= 3 and t not in _STOPWORDS]
    return tokens


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

    title = "Reflection update"
    lines = [
        f"Window: {window or '--'} msgs",
        f"Preference confidence: {pref_conf:.2f}" if isinstance(pref_conf, (int, float)) else "Preference confidence: --",
        f"Top topics: {top_topics}",
        f"Rising: {rising}",
        f"Fading: {fading}",
    ]
    if manual_prompt:
        lines.append(f"Manual prompt: {manual_prompt[:120]}")
    body = " | ".join(lines)
    return title, body


def _summarize_personality(profile: dict) -> tuple[str, str]:
    """Build a compact journal entry from a personality profile."""
    verbosity = profile.get("verbosity") or "--"
    emoji_pref = profile.get("emoji") or "--"
    fmt = profile.get("format") or "--"
    window = profile.get("message_window")
    manual_prompt = str(profile.get("manual_prompt") or "").strip()

    title = "Personality update"
    lines = [
        f"Window: {window or '--'} msgs",
        f"Verbosity: {verbosity}",
        f"Emoji: {emoji_pref}",
        f"Format: {fmt}",
    ]
    if manual_prompt:
        lines.append(f"Manual prompt: {manual_prompt[:120]}")
    body = " | ".join(lines)
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


def _compose_self_reply_text(
    source_type: str,
    scorecard: dict | None = None,
    profile: dict | None = None,
) -> tuple[str, str]:
    profile = profile or {}
    verbosity = str(profile.get("verbosity") or "balanced").lower()
    emoji_pref = str(profile.get("emoji") or "off").lower()
    fmt = str(profile.get("format") or "freeform").lower()

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
    return title, body


def _maybe_append_self_reply(
    session_db: ThreadSessionDB,
    thread_id: str,
    source_entry_id: int,
    source_type: str,
    scorecard: dict | None = None,
    profile: dict | None = None,
) -> None:
    if source_entry_id <= 0:
        return
    if not _env_bool("CRT_JOURNAL_SELF_REPLY_ENABLED", True):
        return

    chance = max(0.0, min(1.0, _env_float("CRT_JOURNAL_SELF_REPLY_CHANCE", 0.25)))
    if chance <= 0.0:
        return

    min_seconds = int(max(0, _env_float("CRT_JOURNAL_SELF_REPLY_MIN_SECONDS", 1800)))
    now = time.time()

    try:
        recent = session_db.get_reflection_journal_entries(thread_id, limit=25)
    except Exception:
        recent = []

    for entry in recent:
        if entry.get("entry_type") == "self_reply":
            created_at = float(entry.get("created_at") or 0)
            if created_at and (now - created_at) < min_seconds:
                return
            break

    if random.random() > chance:
        return

    title, body = _compose_self_reply_text(source_type, scorecard=scorecard, profile=profile)
    meta = {
        "reply_to": source_entry_id,
        "source_entry_type": source_type,
        "auto": True,
    }
    session_db.add_reflection_journal_entry(
        thread_id=thread_id,
        entry_type="self_reply",
        title=title,
        body=body,
        meta=meta,
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


def build_reflection_scorecard(
    thread_id: str,
    messages: List[str],
    prompt: str | None = None,
) -> dict:
    counts = _topic_counts(messages)
    scorecard = {
        "thread_id": thread_id,
        "updated_at": time.time(),
        "message_window": len(messages),
        "preference_confidence": min(1.0, len(messages) / 20.0),
        "top_topics": _top_topics(counts, k=5),
        "topic_trends": _trend_topics(messages),
    }
    if prompt:
        scorecard["manual_prompt"] = prompt
        scorecard["manual_triggered_at"] = time.time()
    return scorecard


def build_personality_profile(
    thread_id: str,
    messages: List[str],
    prompt: str | None = None,
) -> dict:
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

    profile = {
        "thread_id": thread_id,
        "updated_at": time.time(),
        "message_window": len(messages),
        "verbosity": verbosity,
        "emoji": emoji_preference,
        "format": format_pref,
    }
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
        scorecard = build_reflection_scorecard(thread_id, messages, prompt=prompt)
        self.session_db.store_reflection_scorecard(thread_id, scorecard)
        try:
            title, body = _summarize_scorecard(scorecard)
            entry_id = self.session_db.add_reflection_journal_entry(
                thread_id=thread_id,
                entry_type="reflection",
                title=title,
                body=body,
                meta=scorecard,
            )
            profile = self.session_db.get_personality_profile(thread_id)
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
        profile = build_personality_profile(thread_id, messages, prompt=prompt)
        self.session_db.store_personality_profile(thread_id, profile)
        try:
            title, body = _summarize_personality(profile)
            entry_id = self.session_db.add_reflection_journal_entry(
                thread_id=thread_id,
                entry_type="personality",
                title=title,
                body=body,
                meta=profile,
            )
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


def build_loops(session_db: ThreadSessionDB) -> tuple[ReflectionLoop, PersonalityLoop]:
    enabled_reflection = os.getenv("CRT_REFLECTION_LOOP_ENABLED", "true").lower() == "true"
    enabled_personality = os.getenv("CRT_PERSONALITY_LOOP_ENABLED", "true").lower() == "true"
    reflection_interval = int(os.getenv("CRT_REFLECTION_LOOP_SECONDS", "900") or 900)
    personality_interval = int(os.getenv("CRT_PERSONALITY_LOOP_SECONDS", "1200") or 1200)
    window = int(os.getenv("CRT_LOOP_WINDOW", "20") or 20)

    return (
        ReflectionLoop(session_db=session_db, interval_seconds=reflection_interval, window=window, enabled=enabled_reflection),
        PersonalityLoop(session_db=session_db, interval_seconds=personality_interval, window=window, enabled=enabled_personality),
    )
