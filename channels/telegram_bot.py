"""Telegram bot channel for CRT-GroundCheck.

Bridges Telegram messages to the CRT engine via the CRTBridge (HTTP or direct).

Setup:
    1. Create a bot via @BotFather on Telegram → get a token
    2. Set environment variable: TELEGRAM_BOT_TOKEN=<your-token>
    3. Optionally set TELEGRAM_ALLOWED_USERS=<comma-separated user IDs>
    4. Run: python -m channels.telegram_bot

The bot supports:
    - Regular messages → routed through CRT engine
    - /start       → welcome message
    - /reset       → reset thread memory
    - /conflicts   → show open contradictions
    - /facts       → show stored facts
    - /trust       → show trust stats for current thread
    - /important   → mark next message as important
    - /help        → command list
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

import requests

# Ensure project root is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from channels.base import CRTBridge, ChannelMessage, ChannelResponse

logger = logging.getLogger(__name__)

try:
    from telegram import Update, ReactionTypeEmoji
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
    from telegram.constants import ParseMode, ChatAction
except ImportError:
    logger.error(
        "python-telegram-bot is not installed. Run: pip install python-telegram-bot"
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CRT_API_URL = os.getenv("CRT_API_URL", "http://127.0.0.1:8000")
TELEGRAM_PROACTIVE_ENABLED = _env_bool("TELEGRAM_PROACTIVE_ENABLED", True)
TELEGRAM_PROACTIVE_POLL_SECONDS = _env_float("TELEGRAM_PROACTIVE_POLL_SECONDS", 8.0)
TELEGRAM_PROACTIVE_BATCH_SIZE = _env_int("TELEGRAM_PROACTIVE_BATCH_SIZE", 5)
TELEGRAM_PROACTIVE_RETRY_SECONDS = _env_int("TELEGRAM_PROACTIVE_RETRY_SECONDS", 120)
TELEGRAM_LIVE_LOG_PATH = os.getenv("TELEGRAM_LIVE_LOG_PATH", "ai_logs/telegram_live.jsonl")

# Optional: restrict to specific Telegram user IDs
_allowed_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "8793030650")
ALLOWED_USERS: Set[int] = set()
if _allowed_raw.strip():
    for uid in _allowed_raw.split(","):
        uid = uid.strip()
        if uid.isdigit():
            ALLOWED_USERS.add(int(uid))


# ---------------------------------------------------------------------------
# Bridge setup
# ---------------------------------------------------------------------------

bridge = CRTBridge(api_url=CRT_API_URL)

# Startup timestamp — messages older than this are stale backlog
_BOT_START_TIME: float = time.time()


def _append_live_log(event: Dict[str, Any]) -> None:
    try:
        path = Path(TELEGRAM_LIVE_LOG_PATH)
        if not path.is_absolute():
            path = Path(_project_root) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("[TG] live-log append failed: %s", e)


def _emit_live_event(
    *,
    event_type: str,
    text: str,
    update: Optional[Update] = None,
    response: Optional[ChannelResponse] = None,
    thread_id: Optional[str] = None,
) -> None:
    user_id = None
    chat_id = None
    sender_name = None
    message_id = None
    if update is not None:
        try:
            user_id = update.effective_user.id if update.effective_user else None
            chat_id = update.effective_chat.id if update.effective_chat else None
            sender_name = _sender_name(update)
            message_id = update.message.message_id if update.message else None
        except Exception:
            pass

    payload: Dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": datetime.now(timezone.utc).isoformat(),
        "channel": "telegram",
        "event_type": event_type,
        "text": str(text or ""),
        "thread_id": str(thread_id or ""),
        "chat_id": chat_id,
        "user_id": user_id,
        "sender_name": sender_name,
        "message_id": message_id,
    }
    if response is not None:
        payload["gate_reason"] = response.gate_reason
        payload["gates_passed"] = bool(response.gates_passed)
        payload["contradiction_detected"] = bool(response.contradiction_detected)
    _append_live_log(payload)


def _notifications_worker_id() -> str:
    host = socket.gethostname() or "host"
    return f"telegram-bot:{host}:{os.getpid()}"


def _claim_outbound_notifications() -> list[Dict[str, Any]]:
    try:
        resp = requests.post(
            f"{CRT_API_URL}/api/notifications/claim",
            json={
                "worker_id": _notifications_worker_id(),
                "channel": "telegram",
                "limit": max(1, TELEGRAM_PROACTIVE_BATCH_SIZE),
            },
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
    except Exception as e:
        logger.debug("[TG] Failed to claim proactive notifications: %s", e)
    return []


def _ack_outbound_notification(notification_id: str) -> None:
    if not notification_id:
        return
    try:
        requests.post(
            f"{CRT_API_URL}/api/notifications/{notification_id}/ack",
            timeout=15,
        )
    except Exception as e:
        logger.debug("[TG] Failed to ACK proactive notification %s: %s", notification_id, e)


def _fail_outbound_notification(notification_id: str, error: str) -> None:
    if not notification_id:
        return
    try:
        requests.post(
            f"{CRT_API_URL}/api/notifications/{notification_id}/fail",
            json={
                "error": (error or "")[:500],
                "retry_in_seconds": max(5, TELEGRAM_PROACTIVE_RETRY_SECONDS),
            },
            timeout=15,
        )
    except Exception as e:
        logger.debug("[TG] Failed to mark proactive notification failed %s: %s", notification_id, e)


def _notification_chat_id(item: Dict[str, Any]) -> Optional[int]:
    destination = item.get("destination_id")
    if destination is not None and str(destination).strip():
        try:
            return int(str(destination).strip())
        except Exception:
            return None
    thread_id = str(item.get("thread_id") or "").strip()
    if thread_id.startswith("tg_"):
        raw = thread_id[len("tg_") :].strip()
        if raw:
            try:
                return int(raw)
            except Exception:
                return None
    return None


def _render_notification_text(item: Dict[str, Any]) -> str:
    content = str(item.get("content") or "").strip()
    if not content:
        content = "You have a new proactive update."
    category = str(item.get("category") or "").strip().lower()
    if category == "reminder" and not content.lower().startswith("reminder"):
        return f"Reminder: {content}"
    return content


async def _poll_proactive_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TELEGRAM_PROACTIVE_ENABLED:
        return
    loop = asyncio.get_event_loop()
    claimed: list[Dict[str, Any]] = await loop.run_in_executor(None, _claim_outbound_notifications)
    if not claimed:
        return

    for item in claimed:
        notification_id = str(item.get("notification_id") or "").strip()
        if not notification_id:
            continue
        chat_id = _notification_chat_id(item)
        if chat_id is None:
            await loop.run_in_executor(
                None,
                lambda nid=notification_id: _fail_outbound_notification(
                    nid,
                    "missing_or_invalid_destination",
                ),
            )
            continue

        text = _truncate(_render_notification_text(item))
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            await loop.run_in_executor(None, lambda nid=notification_id: _ack_outbound_notification(nid))
        except Exception as e:
            logger.warning("[TG] Failed sending proactive notification %s: %s", notification_id, e)
            await loop.run_in_executor(
                None,
                lambda nid=notification_id, err=str(e): _fail_outbound_notification(nid, err),
            )


def _thread_id_for(update: Update) -> str:
    """Generate a CRT thread_id from the Telegram chat.

    Uses ``tg_<chat_id>`` so each Telegram chat gets isolated memory.
    """
    chat_id = update.effective_chat.id if update.effective_chat else 0
    return f"tg_{chat_id}"


def _sender_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "unknown"
    parts = [user.first_name or "", user.last_name or ""]
    return " ".join(p for p in parts if p).strip() or user.username or "unknown"


def _sender_id(update: Update) -> str:
    user = update.effective_user
    return str(user.id) if user else "0"


def _is_allowed(update: Update) -> bool:
    """Check if the sender is in the allowlist (if one is configured)."""
    if not ALLOWED_USERS:
        return True  # No allowlist = open to anyone who finds the bot
    user = update.effective_user
    return user is not None and user.id in ALLOWED_USERS


def _escape_markdown_v2(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2.

    We only escape outside of code blocks to preserve formatting.
    """
    # For simplicity, send as plain text or HTML instead of MarkdownV2.
    # MarkdownV2 escaping is notoriously finicky.
    return text


def _truncate(text: str, max_len: int = 4096) -> str:
    """Telegram messages cap at 4096 chars."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 30] + "\n\n... (truncated)"


# ---------------------------------------------------------------------------
# Emoji reactions — pick contextual emoji for the user's incoming message
# ---------------------------------------------------------------------------

# Telegram only allows a restricted set of emoji for reactions.
# See: https://core.telegram.org/bots/api#reactiontypeemoji
# Common usable ones: 👍 👎 ❤️ 🔥 🎉 😢 🤔 👀 🤯 💯

def _pick_reaction_emoji(resp: ChannelResponse) -> Optional[str]:
    """Choose a reaction emoji based on response metadata.

    Returns a single emoji string, or None to skip the reaction.
    """
    meta = resp.metadata or {}
    confidence = meta.get("confidence") or resp.confidence or 0.7
    mode = meta.get("mode", "")
    agent_activated = meta.get("agent_activated", False)

    # Contradiction detected → surprised face
    if resp.contradiction_detected:
        return "🤔"

    # Agent activated (web search, research, multi-step) → fire
    if agent_activated:
        return "🔥"

    # Web search results present → eyes (looking it up)
    web_results = meta.get("web_search_results") or meta.get("retrieved_memories") or []
    if isinstance(mode, str) and "search" in mode.lower():
        return "👀"

    # High confidence → thumbs up
    if isinstance(confidence, (int, float)) and confidence >= 0.9:
        return "👍"

    # Uncertainty mode → thinking
    if mode == "uncertainty":
        return "🤔"

    # Default: no reaction (don't spam)
    return None


def _pick_response_prefix(resp: ChannelResponse, user_text: str) -> str:
    """Pick a contextual emoji prefix for the bot's text reply."""
    meta = resp.metadata or {}
    confidence = meta.get("confidence") or resp.confidence or 0.7
    mode = meta.get("mode", "")
    agent_activated = meta.get("agent_activated", False)

    # Contradiction
    if resp.contradiction_detected:
        return "⚠️ "

    # Agent activated
    if agent_activated:
        return "🤖 "

    # Web search
    tl = (user_text or "").lower()
    if any(p in tl for p in ("search", "look up", "latest news", "recent news", "weather", "price of", "who won")):
        return "🔍 "

    # High confidence factual recall
    if isinstance(confidence, (int, float)) and confidence >= 0.9:
        return "✅ "

    # Uncertainty
    if mode == "uncertainty":
        return "🤔 "

    # Greeting detection
    greetings = ("hello", "hi ", "hey ", "good morning", "good evening", "good afternoon", "howdy", "sup", "what's up")
    if any(tl.startswith(g) or tl == g.strip() for g in greetings):
        return "👋 "

    return ""


async def _react_to_message(update: Update, emoji: str) -> None:
    """Set an emoji reaction on the user's message. Silently fails if unsupported."""
    try:
        await update.message.set_reaction(
            reaction=[ReactionTypeEmoji(emoji)],
            is_big=False,
        )
    except Exception as e:
        # Reactions may fail in groups, old clients, or restricted bots
        logger.debug("[TG] Failed to set reaction %s: %s", emoji, e)


# ---------------------------------------------------------------------------
# Flag for /important command
# ---------------------------------------------------------------------------

_important_flags: Set[int] = set()  # chat_ids where next message is marked important


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    if not _is_allowed(update):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return

    name = _sender_name(update)
    await update.message.reply_text(
        f"👋 Hey {name}! I'm Aether, your CRT-powered assistant.\n\n"
        "🧠 I remember what you tell me\n"
        "⚖️ I detect contradictions and never silently overwrite facts\n"
        "🔍 I can search the web for real-time info\n"
        "🤖 I have an agent mode for multi-step tasks\n\n"
        "Just send me a message to get started, or type /help for commands."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    if not _is_allowed(update):
        return

    await update.message.reply_text(
        "📋 Commands:\n\n"
        "👋 /start — Welcome message\n"
        "❓ /help — This list\n"
        "🔍 /search <query> — Web search\n"
        "⚠️ /conflicts — Show open contradictions\n"
        "🧠 /facts — Show stored facts about you\n"
        "📊 /trust — Trust stats for this thread\n"
        "⭐ /important — Mark your next message as important\n"
        "🔄 /reset — Reset this thread's memory\n"
        "🆔 /id — Show your Telegram user ID\n\n"
        "💡 Tips:\n"
        "• Say \"search for [topic]\" to web search\n"
        "• I react with emoji to show what I'm doing\n"
        "• 👀 = processing, 👍 = confident, 🤔 = uncertain"
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /id — useful for setting up TELEGRAM_ALLOWED_USERS."""
    user = update.effective_user
    chat = update.effective_chat
    await update.message.reply_text(
        f"User ID: {user.id}\nChat ID: {chat.id}"
    )


async def cmd_conflicts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /conflicts — query open contradictions."""
    if not _is_allowed(update):
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    msg = ChannelMessage(
        text="How many contradictions do I have? List them.",
        thread_id=_thread_id_for(update),
        sender_id=_sender_id(update),
        sender_name=_sender_name(update),
        channel="telegram",
    )
    resp = bridge.send(msg)
    _emit_live_event(
        event_type="command",
        text=f"/conflicts -> {resp.text}",
        update=update,
        response=resp,
        thread_id=msg.thread_id,
    )
    await update.message.reply_text(_truncate(resp.text))


async def cmd_facts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /facts — show stored facts."""
    if not _is_allowed(update):
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    msg = ChannelMessage(
        text="What facts do you know about me?",
        thread_id=_thread_id_for(update),
        sender_id=_sender_id(update),
        sender_name=_sender_name(update),
        channel="telegram",
    )
    resp = bridge.send(msg)
    _emit_live_event(
        event_type="command",
        text=f"/facts -> {resp.text}",
        update=update,
        response=resp,
        thread_id=msg.thread_id,
    )
    await update.message.reply_text(_truncate(resp.text))


async def cmd_trust(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /trust — show trust statistics."""
    if not _is_allowed(update):
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    msg = ChannelMessage(
        text="Show me the trust statistics and memory health for this conversation.",
        thread_id=_thread_id_for(update),
        sender_id=_sender_id(update),
        sender_name=_sender_name(update),
        channel="telegram",
    )
    resp = bridge.send(msg)
    _emit_live_event(
        event_type="command",
        text=f"/trust -> {resp.text}",
        update=update,
        response=resp,
        thread_id=msg.thread_id,
    )
    await update.message.reply_text(_truncate(resp.text))


async def cmd_important(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /important — flag next message as important."""
    if not _is_allowed(update):
        return

    chat_id = update.effective_chat.id
    _important_flags.add(chat_id)
    await update.message.reply_text(
        "Got it — your next message will be marked as important (higher trust weight)."
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query> — shortcut for web search."""
    if not _is_allowed(update):
        return

    query = " ".join(context.args) if context.args else ""
    if not query.strip():
        await update.message.reply_text("Usage: /search <your query>\n\nExample: /search latest AI news")
        return

    await update.effective_chat.send_action(ChatAction.TYPING)
    await _react_to_message(update, "👀")

    msg = ChannelMessage(
        text=f"search for {query}",
        thread_id=_thread_id_for(update),
        sender_id=_sender_id(update),
        sender_name=_sender_name(update),
        channel="telegram",
    )

    loop = asyncio.get_event_loop()
    resp: ChannelResponse = await loop.run_in_executor(None, bridge.send, msg)
    _emit_live_event(
        event_type="command",
        text=f"/search {query} -> {resp.text}",
        update=update,
        response=resp,
        thread_id=msg.thread_id,
    )

    reaction_emoji = _pick_reaction_emoji(resp)
    if reaction_emoji:
        await _react_to_message(update, reaction_emoji)

    reply_text = "🔍 " + resp.text
    await update.message.reply_text(_truncate(reply_text))


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset — reset thread memory."""
    if not _is_allowed(update):
        return

    thread_id = _thread_id_for(update)
    try:
        import requests as req_lib

        resp = req_lib.post(
            f"{CRT_API_URL}/api/thread/reset",
            json={"thread_id": thread_id},
            timeout=30,
        )
        if resp.status_code == 200:
            await update.message.reply_text(
                "Thread memory has been reset. Starting fresh."
            )
        else:
            await update.message.reply_text(
                f"Reset failed (HTTP {resp.status_code}). Is the CRT server running?"
            )
    except Exception as e:
        await update.message.reply_text(f"Reset failed: {e}")


# ---------------------------------------------------------------------------
# Message handler (the main one)
# ---------------------------------------------------------------------------


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages — route through CRT engine."""
    if not _is_allowed(update):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return

    text = update.message.text
    if not text or not text.strip():
        return

    # Skip stale messages that were queued while bot was offline
    if update.message.date:
        msg_ts = update.message.date.timestamp()
        if msg_ts < _BOT_START_TIME - 10:  # 10s grace period
            logger.info("[TG] Skipping stale message (%.0fs old): %s",
                        _BOT_START_TIME - msg_ts, text[:60])
            return

    chat_id = update.effective_chat.id

    # Check if /important flag was set
    is_important = chat_id in _important_flags
    if is_important:
        _important_flags.discard(chat_id)

    # Show typing indicator
    await update.effective_chat.send_action(ChatAction.TYPING)

    # React with 👀 immediately to show we're processing
    await _react_to_message(update, "👀")

    msg = ChannelMessage(
        text=text,
        thread_id=_thread_id_for(update),
        sender_id=_sender_id(update),
        sender_name=_sender_name(update),
        channel="telegram",
        important=is_important,
        raw={
            "message_id": update.message.message_id,
            "chat_id": chat_id,
            "date": str(update.message.date) if update.message.date else None,
        },
    )
    _emit_live_event(
        event_type="inbound",
        text=text,
        update=update,
        thread_id=msg.thread_id,
    )

    # Run the blocking bridge.send() in a thread pool to not block the event loop
    loop = asyncio.get_event_loop()
    resp: ChannelResponse = await loop.run_in_executor(None, bridge.send, msg)

    # Update reaction based on response (replaces the 👀)
    reaction_emoji = _pick_reaction_emoji(resp)
    if reaction_emoji:
        await _react_to_message(update, reaction_emoji)

    # Build the reply with contextual emoji prefix
    prefix = _pick_response_prefix(resp, text)
    reply_text = resp.text

    # If a contradiction was detected, add a visual indicator
    if resp.contradiction_detected:
        reply_text = "⚠️ Contradiction detected!\n\n" + reply_text
        prefix = ""  # Already has the contradiction banner

    # If gates failed for a non-error reason, note it subtly
    if not resp.gates_passed and resp.gate_reason and resp.gate_reason not in (
        "connection_error",
        "error",
        "engine_error",
    ):
        reply_text += "\n\n🔒 (reconstruction gate active)"

    # Apply prefix
    if prefix:
        reply_text = prefix + reply_text

    await update.message.reply_text(_truncate(reply_text))
    _emit_live_event(
        event_type="outbound",
        text=reply_text,
        update=update,
        response=resp,
        thread_id=msg.thread_id,
    )


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error("Telegram bot error: %s", context.error, exc_info=context.error)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        print(
            "ERROR: TELEGRAM_BOT_TOKEN not set.\n"
            "\n"
            "To set up:\n"
            "  1. Message @BotFather on Telegram\n"
            "  2. Create a new bot with /newbot\n"
            "  3. Copy the token\n"
            "  4. Set the environment variable:\n"
            "     $env:TELEGRAM_BOT_TOKEN = 'your-token-here'\n"
            "  5. (Optional) Restrict access:\n"
            "     $env:TELEGRAM_ALLOWED_USERS = '123456789'\n"
            "     Use /id command to find your user ID\n"
            "  6. Run this script again\n"
        )
        sys.exit(1)

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    print("=" * 60)
    print("CRT-GroundCheck Telegram Bot")
    print("=" * 60)
    print(f"  API URL:  {CRT_API_URL}")
    if ALLOWED_USERS:
        print(f"  Allowed users: {ALLOWED_USERS}")
    else:
        print("  Allowed users: ALL (no restriction)")
    print(
        "  Proactive notifications: "
        f"{'ON' if TELEGRAM_PROACTIVE_ENABLED else 'OFF'} "
        f"(poll={max(2.0, float(TELEGRAM_PROACTIVE_POLL_SECONDS)):.1f}s, batch={max(1, int(TELEGRAM_PROACTIVE_BATCH_SIZE))})"
    )
    print()
    print("  Make sure the CRT API server is running:")
    print("    python crt_api.py")
    print()
    print("  Bot is starting...")
    print("=" * 60)

    # Retry loop — if the network is slow or unavailable, keep trying
    # with exponential backoff instead of crashing.
    max_retries = 0  # 0 = infinite retries
    base_delay = 5   # seconds
    max_delay = 120  # cap backoff at 2 minutes
    attempt = 0

    while True:
        attempt += 1
        try:
            app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Register handlers
            app.add_handler(CommandHandler("start", cmd_start))
            app.add_handler(CommandHandler("help", cmd_help))
            app.add_handler(CommandHandler("id", cmd_id))
            app.add_handler(CommandHandler("conflicts", cmd_conflicts))
            app.add_handler(CommandHandler("facts", cmd_facts))
            app.add_handler(CommandHandler("trust", cmd_trust))
            app.add_handler(CommandHandler("important", cmd_important))
            app.add_handler(CommandHandler("search", cmd_search))
            app.add_handler(CommandHandler("reset", cmd_reset))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            app.add_error_handler(error_handler)

            if TELEGRAM_PROACTIVE_ENABLED and app.job_queue is not None:
                app.job_queue.run_repeating(
                    _poll_proactive_notifications,
                    interval=max(2.0, float(TELEGRAM_PROACTIVE_POLL_SECONDS)),
                    first=5.0,
                    name="crt_proactive_notifications",
                )
                logger.info(
                    "[TG] Proactive notification polling enabled (interval=%.1fs, batch=%d).",
                    max(2.0, float(TELEGRAM_PROACTIVE_POLL_SECONDS)),
                    max(1, int(TELEGRAM_PROACTIVE_BATCH_SIZE)),
                )
            elif TELEGRAM_PROACTIVE_ENABLED:
                logger.warning("[TG] JobQueue unavailable; proactive notification polling disabled.")

            # Start polling — drop_pending_updates=True skips messages queued while bot was offline
            logger.info(
                "Telegram bot started (attempt %d). Polling for messages (dropping stale backlog)...",
                attempt,
            )
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
            break  # clean exit from run_polling (e.g. SIGINT)

        except (KeyboardInterrupt, SystemExit):
            logger.info("Telegram bot shutting down.")
            break

        except Exception as exc:
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "Telegram bot connection failed (attempt %d): %s — retrying in %ds...",
                attempt, exc, delay,
            )
            if max_retries and attempt >= max_retries:
                logger.error("Max retries (%d) reached. Giving up.", max_retries)
                sys.exit(1)
            try:
                time.sleep(delay)
            except KeyboardInterrupt:
                logger.info("Telegram bot shutting down during retry wait.")
                break


if __name__ == "__main__":
    main()
