"""24/7 background reflection + personality loops (limited scope/context)."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from typing import Dict, List, Optional, Tuple

from .db_utils import ThreadSessionDB

logger = logging.getLogger(__name__)

_JOURNAL_LLM_CLIENT: Optional[object] = None
_JOURNAL_LLM_CLIENT_READY = False


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


def _strip_thinking_tags(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"</?thinking>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


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
        from .ollama_client import OllamaClient
        model = os.getenv("CRT_JOURNAL_LLM_REFLECTION_MODEL") or os.getenv("CRT_OLLAMA_MODEL") or "deepseek-r1:latest"
        _JOURNAL_LLM_CLIENT = OllamaClient(model=model)
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
        "Output JSON with keys: title, body."
    )

    length_hint = "4-6 sentences" if verbosity == "verbose" else "2-4 sentences"
    user_prompt = (
        "Write a reflection post based on the recent chat and your own responses. "
        f"Length: {length_hint}. "
        "Include: (1) one thing you did well, (2) one thing to improve, "
        "(3) one open question to yourself, and (4) a small next step. "
        "Use first-person voice. Use the context below.\n\n"
        f"Window: {window} messages\n"
        f"Top topics: {top_topics}\n"
        f"Rising: {rising}\n"
        f"Fading: {fading}\n\n"
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
        interactions = _recent_interactions(self.session_db, thread_id, self.window)
        scorecard = build_reflection_scorecard(thread_id, messages, prompt=prompt)
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
                meta["post_mode"] = "heuristic"

            entry_id = self.session_db.add_reflection_journal_entry(
                thread_id=thread_id,
                entry_type="reflection",
                title=title,
                body=body,
                meta=meta,
            )
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


def build_loops(session_db: ThreadSessionDB) -> tuple[ReflectionLoop, PersonalityLoop, SelfReplyLoop]:
    enabled_reflection = os.getenv("CRT_REFLECTION_LOOP_ENABLED", "true").lower() == "true"
    enabled_personality = os.getenv("CRT_PERSONALITY_LOOP_ENABLED", "true").lower() == "true"
    enabled_self_reply = os.getenv("CRT_JOURNAL_SELF_REPLY_LOOP_ENABLED", "true").lower() == "true"
    reflection_interval = int(os.getenv("CRT_REFLECTION_LOOP_SECONDS", "900") or 900)
    personality_interval = int(os.getenv("CRT_PERSONALITY_LOOP_SECONDS", "1200") or 1200)
    self_reply_interval = int(os.getenv("CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS", "1800") or 1800)
    window = int(os.getenv("CRT_LOOP_WINDOW", "20") or 20)

    return (
        ReflectionLoop(session_db=session_db, interval_seconds=reflection_interval, window=window, enabled=enabled_reflection),
        PersonalityLoop(session_db=session_db, interval_seconds=personality_interval, window=window, enabled=enabled_personality),
        SelfReplyLoop(session_db=session_db, interval_seconds=self_reply_interval, enabled=enabled_self_reply),
    )
