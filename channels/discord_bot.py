"""Discord bot channel for CRT/Aether.

Bridges Discord messages to the CRT engine via the CRTBridge (HTTP/SSE).
Same pipeline as Telegram and web — all governance layers apply.

Setup:
    1. Create a bot at https://discord.com/developers/applications
    2. Enable Message Content Intent in the Bot settings
    3. Set environment variable: DISCORD_BOT_TOKEN=<your-token>
    4. Optionally set DISCORD_ALLOWED_CHANNELS=<comma-separated channel IDs>
    5. Run: python -m channels.discord_bot

The bot supports:
    - Regular messages (in allowed channels or DMs) -> routed through CRT engine
    - !help       -> command list
    - !conflicts  -> show open contradictions
    - !facts      -> show stored facts
    - !trust      -> show trust stats
    - !reset      -> reset thread memory
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

import discord
from discord import Intents, Message

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from channels.base import ChannelMessage, ChannelResponse, CRTBridge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
CRT_API_URL = os.getenv("CRT_API_URL", "http://127.0.0.1:8000")
DISCORD_LIVE_LOG_PATH = os.getenv("DISCORD_LIVE_LOG_PATH", "ai_logs/discord_live.jsonl")
DISCORD_CMD_PREFIX = os.getenv("DISCORD_CMD_PREFIX", "!")

# Optional: restrict to specific Discord channel IDs
_allowed_raw = os.getenv("DISCORD_ALLOWED_CHANNELS", "")
ALLOWED_CHANNELS: Set[int] = set()
if _allowed_raw.strip():
    for cid in _allowed_raw.split(","):
        cid = cid.strip()
        if cid.isdigit():
            ALLOWED_CHANNELS.add(int(cid))

# Optional: restrict to specific Discord user IDs
_allowed_users_raw = os.getenv("DISCORD_ALLOWED_USERS", "")
ALLOWED_USERS: Set[int] = set()
if _allowed_users_raw.strip():
    for uid in _allowed_users_raw.split(","):
        uid = uid.strip()
        if uid.isdigit():
            ALLOWED_USERS.add(int(uid))

# ---------------------------------------------------------------------------
# Bridge setup
# ---------------------------------------------------------------------------

bridge = CRTBridge(api_url=CRT_API_URL)

# Bot startup time — ignore messages before this
_BOT_START_TIME: float = time.time()

# ---------------------------------------------------------------------------
# Live logging (mirrors Telegram live feed)
# ---------------------------------------------------------------------------

def _append_live_log(event: Dict[str, Any]) -> None:
    try:
        path = Path(DISCORD_LIVE_LOG_PATH)
        if not path.is_absolute():
            path = Path(_project_root) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("[DISCORD] live-log append failed: %s", e)


def _emit_live_event(
    *,
    event_type: str,
    text: str,
    message: Optional[Message] = None,
    response: Optional[ChannelResponse] = None,
    thread_id: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a structured event to the live log."""
    event: Dict[str, Any] = {
        "event_type": event_type,
        "text": text[:2000],
        "thread_id": thread_id or "",
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "channel": "discord",
    }
    if message:
        event["discord_user_id"] = str(message.author.id)
        event["discord_user_name"] = str(message.author)
        event["discord_channel_id"] = str(message.channel.id)
        event["discord_guild_id"] = str(message.guild.id) if message.guild else "DM"
        event["discord_message_id"] = str(message.id)
    if response:
        event["gates_passed"] = response.gates_passed
        event["contradiction_detected"] = response.contradiction_detected
        event["route"] = response.route
        event["intent_type"] = response.intent_type
    if extras:
        event.update(extras)
    _append_live_log(event)


# ---------------------------------------------------------------------------
# Thread ID derivation
# ---------------------------------------------------------------------------

def _thread_id_for(message: Message) -> str:
    """Derive a CRT thread ID from a Discord message.

    DMs get a per-user thread. Guild channels get a per-channel thread.
    Discord threads/forums get their own thread ID.
    """
    if message.guild is None:
        # DM
        return f"discord_dm_{message.author.id}"
    # Guild channel or thread
    channel = message.channel
    if hasattr(channel, "parent_id") and channel.parent_id:
        # Discord thread inside a channel
        return f"discord_{message.guild.id}_{channel.id}"
    return f"discord_{message.guild.id}_{channel.id}"


# ---------------------------------------------------------------------------
# Discord client
# ---------------------------------------------------------------------------

intents = Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)


def _is_allowed(message: Message) -> bool:
    """Check if this message should be processed."""
    # Ignore bots (including self)
    if message.author.bot:
        return False
    # User allowlist (if set)
    if ALLOWED_USERS and message.author.id not in ALLOWED_USERS:
        return False
    # Channel allowlist (if set) — DMs always allowed
    if ALLOWED_CHANNELS and message.guild is not None:
        if message.channel.id not in ALLOWED_CHANNELS:
            return False
    return True


async def _send_bridge(text: str, message: Message) -> Optional[ChannelResponse]:
    """Send a message through the CRT bridge (runs in executor to avoid blocking)."""
    thread_id = _thread_id_for(message)

    cm = ChannelMessage(
        text=text,
        thread_id=thread_id,
        sender_id=str(message.author.id),
        sender_name=str(message.author),
        channel="discord",
        raw={
            "message_id": str(message.id),
            "channel_id": str(message.channel.id),
            "guild_id": str(message.guild.id) if message.guild else None,
        },
    )

    _emit_live_event(
        event_type="inbound",
        text=text,
        message=message,
        thread_id=thread_id,
    )

    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, bridge.send, cm)
    except Exception as e:
        logger.error("[DISCORD] Bridge error: %s", e)
        _emit_live_event(
            event_type="error",
            text=f"Bridge error: {e}",
            message=message,
            thread_id=thread_id,
        )
        return None

    _emit_live_event(
        event_type="response",
        text=response.text[:2000] if response else "(empty)",
        message=message,
        response=response,
        thread_id=thread_id,
    )

    return response


async def _send_reply(message: Message, text: str) -> None:
    """Send a reply, splitting into chunks if needed (Discord 2000 char limit)."""
    if not text or not text.strip():
        text = "(No response generated)"

    # Split on paragraph boundaries if too long
    chunks = []
    remaining = text
    while len(remaining) > 1900:
        # Find a good split point
        split_at = remaining[:1900].rfind("\n\n")
        if split_at < 500:
            split_at = remaining[:1900].rfind("\n")
        if split_at < 500:
            split_at = 1900
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    chunks.append(remaining)

    for chunk in chunks:
        try:
            await message.reply(chunk, mention_author=False)
        except discord.HTTPException as e:
            logger.error("[DISCORD] Failed to send reply: %s", e)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _cmd_help(message: Message) -> None:
    help_text = (
        "**Aether (CRT) Discord Bot**\n\n"
        "Just send a message and I'll respond through the full CRT pipeline.\n\n"
        "**Commands:**\n"
        f"`{DISCORD_CMD_PREFIX}help` — This help message\n"
        f"`{DISCORD_CMD_PREFIX}conflicts` — Show open contradictions\n"
        f"`{DISCORD_CMD_PREFIX}facts` — Show stored facts\n"
        f"`{DISCORD_CMD_PREFIX}trust` — Show trust stats\n"
        f"`{DISCORD_CMD_PREFIX}reset` — Reset thread memory\n"
    )
    await message.reply(help_text, mention_author=False)


async def _cmd_conflicts(message: Message) -> None:
    thread_id = _thread_id_for(message)
    try:
        import requests as req
        resp = req.get(
            f"{CRT_API_URL}/api/ledger/open",
            params={"thread_id": thread_id, "limit": 10},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("contradictions", [])
            if not items:
                await message.reply("No open contradictions.", mention_author=False)
                return
            lines = [f"**Open Contradictions ({len(items)}):**"]
            for c in items[:10]:
                claim = (c.get("claim_a", "") or "")[:80]
                lines.append(f"- {claim}...")
            await message.reply("\n".join(lines), mention_author=False)
        else:
            await message.reply(f"API error: {resp.status_code}", mention_author=False)
    except Exception as e:
        await message.reply(f"Error: {e}", mention_author=False)


async def _cmd_facts(message: Message) -> None:
    thread_id = _thread_id_for(message)
    try:
        import requests as req
        resp = req.get(
            f"{CRT_API_URL}/api/profile",
            params={"thread_id": thread_id},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            slots = data.get("slots", {})
            if not slots:
                await message.reply("No stored facts yet.", mention_author=False)
                return
            lines = ["**Known Facts:**"]
            for k, v in list(slots.items())[:20]:
                lines.append(f"- **{k}**: {v}")
            await message.reply("\n".join(lines), mention_author=False)
        else:
            await message.reply(f"API error: {resp.status_code}", mention_author=False)
    except Exception as e:
        await message.reply(f"Error: {e}", mention_author=False)


async def _cmd_trust(message: Message) -> None:
    thread_id = _thread_id_for(message)
    try:
        import requests as req
        resp = req.get(
            f"{CRT_API_URL}/api/memory/trust-delta",
            params={"thread_id": thread_id, "limit": 5},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            deltas = data if isinstance(data, list) else data.get("deltas", [])
            if not deltas:
                await message.reply("No recent trust changes.", mention_author=False)
                return
            lines = ["**Recent Trust Changes:**"]
            for d in deltas[:5]:
                text = (d.get("text", "") or "")[:60]
                old = d.get("old_trust", "?")
                new = d.get("new_trust", "?")
                lines.append(f"- {text}... ({old} -> {new})")
            await message.reply("\n".join(lines), mention_author=False)
        else:
            await message.reply(f"API error: {resp.status_code}", mention_author=False)
    except Exception as e:
        await message.reply(f"Error: {e}", mention_author=False)


async def _cmd_reset(message: Message) -> None:
    await message.reply(
        "Thread memory reset is not yet supported from Discord. "
        "Use the web UI to manage threads.",
        mention_author=False,
    )


_COMMANDS = {
    "help": _cmd_help,
    "conflicts": _cmd_conflicts,
    "facts": _cmd_facts,
    "trust": _cmd_trust,
    "reset": _cmd_reset,
}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@client.event
async def on_ready():
    print(f"[DISCORD] Bot online: {client.user} (ID: {client.user.id})")
    print(f"[DISCORD] Guilds: {[g.name for g in client.guilds]}")
    if ALLOWED_CHANNELS:
        print(f"[DISCORD] Allowed channels: {ALLOWED_CHANNELS}")
    if ALLOWED_USERS:
        print(f"[DISCORD] Allowed users: {ALLOWED_USERS}")
    print(f"[DISCORD] CRT API: {CRT_API_URL}")
    print(f"[DISCORD] Command prefix: {DISCORD_CMD_PREFIX}")


@client.event
async def on_message(message: Message):
    # Gate: ignore bots, check allowlists
    if not _is_allowed(message):
        return

    text = message.content.strip()
    if not text:
        return

    # Check for commands
    if text.startswith(DISCORD_CMD_PREFIX):
        cmd_name = text[len(DISCORD_CMD_PREFIX):].split()[0].lower()
        handler = _COMMANDS.get(cmd_name)
        if handler:
            await handler(message)
            return

    # Check if bot is mentioned or in DM (for guild channels, require mention)
    in_dm = message.guild is None
    mentioned = client.user in message.mentions if client.user else False

    # In guild channels: only respond if mentioned or in allowed channel
    if not in_dm and not mentioned and ALLOWED_CHANNELS and message.channel.id in ALLOWED_CHANNELS:
        # In an allowed channel — respond to everything
        pass
    elif not in_dm and not mentioned:
        # Not mentioned in a non-allowed guild channel — ignore
        return

    # Strip the mention from the message text
    if mentioned and client.user:
        text = text.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "").strip()

    if not text:
        return

    # Show typing indicator while processing
    async with message.channel.typing():
        response = await _send_bridge(text, message)

    if response:
        await _send_reply(message, response.text)
    else:
        await _send_reply(message, "Sorry, I couldn't process that. The CRT engine may be unavailable.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not DISCORD_BOT_TOKEN:
        print(
            "ERROR: DISCORD_BOT_TOKEN not set.\n"
            "Create a bot at https://discord.com/developers/applications\n"
            "Then set the token:\n"
            "  Windows PowerShell:\n"
            "     $env:DISCORD_BOT_TOKEN = 'your-token-here'\n"
            "  Linux/Mac:\n"
            "     export DISCORD_BOT_TOKEN=your-token-here\n"
        )
        sys.exit(1)

    print(f"[DISCORD] Starting Aether Discord bot...")
    print(f"[DISCORD] CRT API: {CRT_API_URL}")
    client.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
