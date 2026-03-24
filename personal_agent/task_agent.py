"""CRT TaskAgent — clean execution route for task/agentic queries.

Layer 1 implementation (patch plan):
  1.1  Real HTTP tools: http_post, http_get_json, store_credential
  1.2  Execution verification + retry (2xx check, field presence, one retry)
  1.3  Broader intent classification (imperatives, API key strings, continuation)
  1.4  Task context threading (accepts active_task from session DB)

Intent types
------------
url_fetch          — URL + action verb
imperative_task    — store/save/update/use with no URL (API key follow-ups etc.)
task_continuation  — follow-up on an active task session
conversational     — everything else → full CRT pipeline
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known services registry
# ---------------------------------------------------------------------------

# Maps service names (lowercase) to their skill doc URL and credential key.
# When the user references a service by name without providing a URL, the
# classifier resolves the skill URL and the task agent uses stored credentials.
_KNOWN_SERVICES: Dict[str, Dict[str, str]] = {
    "moltbook": {
        "skill_url": "https://www.moltbook.com/skill.md",
        "api_base": "https://www.moltbook.com/api/v1",
        "credential_key": "moltbook_api_key",
    },
}

# Matches any known service name as a word boundary
_KNOWN_SERVICE_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _KNOWN_SERVICES) + r")\b",
    re.IGNORECASE,
)

# Write-action verbs that imply mutating the service (post, update, delete, …)
_WRITE_VERB_RE = re.compile(
    r"\b(post|publish|send|submit|create|add|update|edit|change|delete|remove|"
    r"register|sign\s+up|join|follow|unfollow|like|reply|mark|"
    r"dismiss|clear|archive|mute|unmute|block|unblock|pin|unpin)\b",
    re.IGNORECASE,
)

# Read-action verbs that imply querying the service
_READ_VERB_RE = re.compile(
    r"\b(check|see|get|fetch|read|look|find|show|list|any|are\s+there|what(?:'s|\s+are|\s+is))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_URL_ACTION_RE = re.compile(
    r"\b(read|fetch|visit|check|open|go\s+to|follow|access|look\s+at|get|load|download)\b"
    r".{0,80}https?://\S+",
    re.IGNORECASE,
)
_BARE_URL_RE = re.compile(r"^\s*https?://\S+\s*$")

_INSTRUCTION_VERB_RE = re.compile(
    r"\b(follow|execute|run|do|complete|perform|carry\s+out|sign\s+up|join|install|setup)\b",
    re.IGNORECASE,
)

_KNOWLEDGE_QUESTION_RE = re.compile(
    r"\b(what\s+is|what's|whats|who\s+is|explain|tell\s+me\s+about|describe)\b",
    re.IGNORECASE,
)

# Skill install patterns — "add skill from URL", "install skill.md", etc.
_SKILL_INSTALL_RE = re.compile(
    r"\b(add|install|register|load|import|connect|setup|set\s+up)\b"
    r".{0,40}\b(skill|service|tool|integration)\b",
    re.IGNORECASE,
)

# 1.3 — imperative store/save/update patterns (no URL required)
_IMPERATIVE_TASK_RE = re.compile(
    r"\b(store\s+(this|the|my)|save\s+(this|the|my)|update\s+(your|my)\s+(credentials?|key|token|api)|"
    r"use\s+(this|the)\s+(key|token|api\s*key|credential)|"
    r"here(?:'s|\s+is)\s+(your|the|a|my)\s+(new\s+)?(key|token|api\s*key|credential|url)|"
    r"please\s+update|keep\s+this|record\s+this|note\s+(this|the|that))\b",
    re.IGNORECASE,
)

# 1.3 — API key / token string detection (long alphanumeric with separators)
_API_KEY_RE = re.compile(
    r"\b[a-zA-Z0-9_\-]{8,}[_\-][a-zA-Z0-9_\-]{4,}[_\-][a-zA-Z0-9_\-]{4,}\b"
    r"|\b[a-zA-Z]{2,8}_[a-zA-Z0-9_\-]{16,}\b",
)

# 1.3 — continuation patterns
_CONTINUATION_RE = re.compile(
    r"\b(follow\s+up|continue\s+(the|this)|finish\s+(the|this)|"
    r"next\s+step|what(?:'s|\s+is)\s+next|complete\s+(the|this)|"
    r"pick\s+up\s+where|proceed\s+with|resume\s+(the|this))\b",
    re.IGNORECASE,
)

# Fields that indicate a real API/registration response (not hallucinated)
_RESPONSE_FIELD_INDICATORS = (
    "api_key", "token", "claim_url", "access_token", "secret",
    "key", "session_id", "auth", "bearer", "jwt",
)

# Service action verbs (for credential-store-based service detection)
_SERVICE_WRITE_RE = re.compile(
    r"\b(post|publish|send|submit|create|add|update|edit|change|delete|remove|"
    r"register|sign\s+up|join|follow|unfollow|like|reply|write|mark|"
    r"dismiss|clear|archive|mute|unmute|block|unblock|pin|unpin)\b",
    re.IGNORECASE,
)
_SERVICE_READ_RE = re.compile(
    r"\b(check|see|get|fetch|read|look|find|show|list|view|browse|search|"
    r"interesting|trending|popular|recent|latest|"
    r"any\s+new|whats\s+new|what(?:'?s|\s+are|\s+is)\s+new|"
    r"are\s+there|what(?:'?s|\s+are|\s+is)|updates?|notifications?)\b",
    re.IGNORECASE,
)

# 1.5 — system info / status queries
_SYSTEM_INFO_RE = re.compile(
    r"\b(system\s+(status|info|stats|health|resources?|state|usage|load|monitor)|"
    r"(cpu|ram|memory|gpu|disk|vram)\s+(usage|status|stats|load|info|percent)|"
    r"how(?:'s|\s+is)\s+(my\s+)?(system|computer|machine|pc|rig)|"
    r"what(?:'s|\s+is|\s+am\s+i)\s+(my\s+)?(system|computer|running|using)|"
    r"what\s+am\s+i\s+running|"
    r"top\s+processes|task\s+manager|resource\s+monitor|"
    r"check\s+(my\s+)?(system|cpu|gpu|ram|memory|disk))\b",
    re.IGNORECASE,
)

# 2A — file read patterns
_FILE_READ_RE = re.compile(
    r"\b(read\s+(file|the\s+file)|show\s+me\s+(the\s+)?(file|contents)|"
    r"what(?:'s|\s+is)\s+in\s+[A-Za-z]:|open\s+[A-Za-z]:|cat\s+|"
    r"contents?\s+of|print\s+(the\s+)?file|display\s+(the\s+)?file)\b",
    re.IGNORECASE,
)

# 2A — directory listing patterns
_DIR_LIST_RE = re.compile(
    r"\b(list\s+(the\s+)?(dir|directory|folder|files\s+in)|"
    r"show\s+(the\s+)?(dir|directory|folder)|"
    r"what(?:'s|\s+is)\s+in\s+(the\s+)?(dir|directory|folder)|"
    r"\bls\b|dir\s+listing)\b",
    re.IGNORECASE,
)

# 2B — project / git / repo patterns
_PROJECT_SCAN_RE = re.compile(
    r"\b(git\s+status|project\s+(status|scan|info|state)|"
    r"any\s+changes\s+in|what(?:'s|\s+is)\s+the\s+status\s+of\s+(the\s+)?(project|repo)|"
    r"check\s+(my\s+)?(repo|project|git)|uncommitted\s+changes|"
    r"scan\s+(the\s+)?(project|repo|directory)|"
    r"what\s+branch|recent\s+commits)\b",
    re.IGNORECASE,
)

# File path detection (Windows drive letter paths or common extensions)
_FILE_PATH_RE = re.compile(
    r"[A-Za-z]:/[\w./ -]+(?:\.\w+)?|"
    r"[\w./\\-]+\.(?:py|tsx?|jsx?|json|md|ya?ml|toml|rs|go|css|html|txt|cfg|ini|sh|bat)\b",
)


# ---------------------------------------------------------------------------
# Credentials store
# ---------------------------------------------------------------------------

_CREDENTIALS_PATH = Path("personal_agent/.aether_credentials.json")


def _derive_key(thread_id: str = "") -> str:
    """Deterministic obfuscation key derived from machine hostname.

    NOTE: thread_id is accepted but IGNORED.  Credentials are global
    (not per-thread) because frontend thread IDs are random UUIDs that
    change across sessions — keying on them made stored credentials
    undecipherable from any other thread.
    """
    hostname = os.uname().nodename if hasattr(os, "uname") else "windows"
    raw = f"aether:{hostname}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _xor_cipher(data: str, key: str) -> str:
    """Trivial XOR obfuscation — not cryptographic, just avoids plaintext."""
    key_chars = key * (len(data) // len(key) + 1)  # string repeat, not bytes
    return "".join(chr(ord(c) ^ ord(k)) for c, k in zip(data, key_chars))


def store_credential(key: str, value: str, thread_id: str = "default") -> str:
    """Store a credential. Returns the file path written."""
    _CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    store: Dict[str, Any] = {}
    if _CREDENTIALS_PATH.exists():
        try:
            store = json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        except Exception:
            store = {}
    cipher_key = _derive_key(thread_id)
    store[key] = _xor_cipher(value, cipher_key)
    _CREDENTIALS_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    logger.info("[CREDENTIALS] Stored key=%s to %s", key, _CREDENTIALS_PATH)
    return str(_CREDENTIALS_PATH)


def load_credential(key: str, thread_id: str = "default") -> Optional[str]:
    """Load a stored credential. Returns None if not found."""
    if not _CREDENTIALS_PATH.exists():
        return None
    try:
        store = json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        if key not in store:
            return None
        cipher_key = _derive_key(thread_id)
        return _xor_cipher(store[key], cipher_key)
    except Exception as e:
        logger.warning("[CREDENTIALS] Load failed for key=%s: %s", key, e)
        return None


def _get_known_services() -> Dict[str, Dict[str, str]]:
    """Discover known services from credential store keys.

    Scans stored credential keys for patterns like ``{service}_api_key``,
    ``{service}_skill_url``, ``{service}_api_base``.  Returns a dict of
    ``{service_name: {credential_key, skill_url, api_base}}`` with whatever
    metadata is available.
    """
    if not _CREDENTIALS_PATH.exists():
        return {}
    try:
        store = json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    services: Dict[str, Dict[str, str]] = {}
    for key in store:
        # e.g. moltbook_api_key → service=moltbook
        for suffix in ("_api_key", "_token", "_secret"):
            if key.endswith(suffix):
                svc = key[: -len(suffix)]
                if svc:
                    services.setdefault(svc, {})["credential_key"] = key
                break

        # e.g. moltbook_skill_url → service=moltbook, skill_url=<value>
        if key.endswith("_skill_url"):
            svc = key[: -len("_skill_url")]
            if svc:
                services.setdefault(svc, {})["skill_url_key"] = key

        if key.endswith("_api_base"):
            svc = key[: -len("_api_base")]
            if svc:
                services.setdefault(svc, {})["api_base_key"] = key

    return services


# ---------------------------------------------------------------------------
# Skill file cache (local storage of fetched SKILL.md files)
# ---------------------------------------------------------------------------

_SKILL_CACHE_DIR = Path("data/managed_skills")


def _load_cached_skill(service: str) -> Optional[str]:
    """Read a locally cached SKILL.md for the given service. Returns None if not cached."""
    path = _SKILL_CACHE_DIR / service / "SKILL.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def _cache_skill_content(service: str, content: str, filename: str = "SKILL.md") -> None:
    """Write fetched skill content to local cache."""
    path = _SKILL_CACHE_DIR / service / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("[SKILL_CACHE] Cached %s for %s (%d bytes)", filename, service, len(content))


# Companion docs that skill.md references for full integration.
# Keyed by filename → URL path relative to the service base.
_SKILL_COMPANION_DOCS = [
    ("SKILL.md", "skill.md"),
    ("HEARTBEAT.md", "heartbeat.md"),
    ("MESSAGING.md", "messaging.md"),
    ("RULES.md", "rules.md"),
    ("package.json", "skill.json"),
]


def _fetch_url_text(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a URL and return text content, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def sync_skill_cache() -> List[str]:
    """Fetch and cache skill files for services with credentials but no local cache.

    Called at server startup to ensure cached skill files are available
    for services the agent already has credentials for.  Fetches SKILL.md
    plus companion docs (HEARTBEAT.md, MESSAGING.md, RULES.md, package.json).
    """
    cached: List[str] = []
    for svc_name in _get_known_services():
        known = _KNOWN_SERVICES.get(svc_name)
        if not known or not known.get("skill_url"):
            continue

        skill_url = known["skill_url"]
        # Derive base URL: https://example.com/skill.md → https://example.com/
        base_url = skill_url.rsplit("/", 1)[0] + "/"
        svc_dir = _SKILL_CACHE_DIR / svc_name
        fetched_any = False

        for filename, url_path in _SKILL_COMPANION_DOCS:
            local_path = svc_dir / filename
            if local_path.exists():
                continue  # already cached
            url = base_url + url_path
            content = _fetch_url_text(url)
            if content:
                _cache_skill_content(svc_name, content, filename)
                fetched_any = True
            else:
                logger.debug("[SKILL_CACHE] %s/%s not available", svc_name, filename)

        if fetched_any:
            cached.append(svc_name)
    return cached


# ---------------------------------------------------------------------------
# TaskIntent
# ---------------------------------------------------------------------------


@dataclass
class TaskIntent:
    route: Literal["task", "conversational"]
    intent_type: str  # url_fetch | imperative_task | service_action | task_continuation | conversational
    slots: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.9
    reason: str = ""


# ---------------------------------------------------------------------------
# Agentic checkpoint gate
# ---------------------------------------------------------------------------

# Checkpoint messages shown to the user before entering agentic mode.
# Tiers: high = auto-proceed with notice, medium = ask, low = clarify ambiguity.
_CHECKPOINT_MESSAGES: Dict[str, str] = {
    "tier_1": "I'm about to {action}. Go ahead?",
    "tier_2": "I detected a task: {action}. Should I proceed? ({reason})",
    "tier_3": "I need to resolve something before I can {action}: {reason}",
}

# Phrases that confirm a checkpoint
_CONFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|yup|sure|go|go ahead|proceed|do it|ok|okay|confirm|y)\b",
    re.IGNORECASE,
)
# Phrases that deny a checkpoint
_DENY_RE = re.compile(
    r"^\s*(no|nah|nope|stop|cancel|don't|do not|abort|never mind|nevermind|n)\b",
    re.IGNORECASE,
)


def parse_checkpoint_confirmation(message: str) -> Optional[bool]:
    """Parse user response to a checkpoint prompt. Returns True/False/None."""
    if _CONFIRM_RE.search(message):
        return True
    if _DENY_RE.search(message):
        return False
    return None  # Ambiguous — treat as new message


def _describe_action(intent: "TaskIntent") -> str:
    """Human-readable description of what the agent is about to do."""
    if intent.intent_type == "url_fetch":
        url = intent.slots.get("url", "a URL")
        action = intent.slots.get("action", "")
        if action == "follow_instructions":
            return f"fetch {url} and follow the instructions in it"
        return f"fetch and read {url}"
    elif intent.intent_type == "service_action":
        svc = intent.slots.get("service", "a service")
        act = intent.slots.get("action", "query")
        if act == "write":
            return f"post/write to {svc}"
        elif act == "query":
            return f"query {svc} for data"
        return f"interact with {svc}"
        return f"fetch and read {intent.slots.get('url', 'a URL')}"
    elif intent.intent_type == "service_action":
        svc = intent.slots.get("service", "a service")
        act = intent.slots.get("action", "interact with")
        return f"{act} the {svc} service"
    elif intent.intent_type == "skill_install":
        url = intent.slots.get("url", "a URL")
        return f"install a new skill from {url}"
    elif intent.intent_type == "imperative_task":
        return "store/update credentials"
    elif intent.intent_type == "task_continuation":
        return "continue the previous task"
    elif intent.intent_type == "system_info":
        return "check system status"
    elif intent.intent_type == "file_read":
        return f"read file {intent.slots.get('path', '?')}"
    elif intent.intent_type == "dir_list":
        return f"list directory {intent.slots.get('path', '?')}"
    elif intent.intent_type == "project_scan":
        return f"scan project at {intent.slots.get('path', '?')}"
    return "execute a task"


def gate_task_intent(intent: "TaskIntent") -> Dict[str, Any]:
    """Wrap a TaskIntent with checkpoint metadata.

    Returns a dict with ``checkpoint_tier``, ``checkpoint_message``,
    and ``requires_confirmation`` so the caller can emit an
    ``agent_checkpoint`` SSE event before executing.

    Conversational intents pass through with ``requires_confirmation=False``.

    Tier assignment (Phase 1 spec):
    - Tier 1 (quick confirm): High-confidence read actions, credential storage
    - Tier 2 (full review): Write actions, unknown services, low confidence,
      destructive operations
    - All task intents require confirmation — no auto-proceed.
    """
    if intent.route == "conversational":
        return {
            "checkpoint_tier": "none",
            "checkpoint_message": "",
            "requires_confirmation": False,
        }

    # ── Layer 1+2 read-only tools — no confirmation needed ──────────────
    if intent.intent_type in ("system_info", "file_read", "dir_list", "project_scan"):
        return {
            "checkpoint_tier": "none",
            "checkpoint_message": "",
            "requires_confirmation": False,
        }

    # ── Intent direction gate ────────────────────────────────────────────
    # Every action must pass: does the classified intent match what the user
    # actually asked for?  This is the always-on intent gate from the spec.
    # Currently implicit in classify_intent's pattern matching — the gate
    # fires by refusing to classify ambiguous messages as tasks.  Future:
    # embed user_intent vs action_intent and check sim >= theta_intent.

    # ── Tier assignment ──────────────────────────────────────────────────
    action = intent.slots.get("action", "")
    is_write = action in ("write", "follow_instructions", "store_or_update")
    is_destructive = action in ("delete", "overwrite")

    if is_destructive:
        tier = "tier_2"
    elif is_write:
        tier = "tier_2"
    elif intent.confidence >= 0.85 and intent.intent_type in ("url_fetch", "service_action", "imperative_task"):
        tier = "tier_1"
    else:
        tier = "tier_2"

    action_desc = _describe_action(intent)
    msg = _CHECKPOINT_MESSAGES[tier].format(action=action_desc, reason=intent.reason)

    return {
        "checkpoint_tier": tier,
        "checkpoint_message": msg,
        "requires_confirmation": True,
    }


# ---------------------------------------------------------------------------
# Intent classifier (1.3)
# ---------------------------------------------------------------------------


def classify_intent(
    message: str,
    active_task: Optional[Dict[str, Any]] = None,
) -> TaskIntent:
    """Fast pattern-based classifier. Checks active task context first."""
    msg_lower = message.lower().strip()
    url_match = _URL_RE.search(message)

    # ── 1. Active task continuation ──────────────────────────────────────
    if active_task and active_task.get("status") == "active":
        # Long messages (>200 chars) are unlikely to be simple continuations.
        # Only check continuation patterns in the first 120 chars of long messages
        # to avoid false-positives on pasted analysis/text containing "proceed with" etc.
        _check_text = message if len(message) <= 200 else message[:120]
        is_continuation = (
            _CONTINUATION_RE.search(_check_text)
            or _IMPERATIVE_TASK_RE.search(message)
            or _API_KEY_RE.search(message)
            or len(message.split()) <= 12  # short follow-ups ("here it is", "done", etc.)
        )
        if is_continuation:
            return TaskIntent(
                route="task",
                intent_type="task_continuation",
                slots={
                    "active_task": active_task,
                    "continuation_message": message,
                    **({"api_key": _API_KEY_RE.search(message).group(0)} if _API_KEY_RE.search(message) else {}),
                },
                confidence=0.92,
                reason="active_task_continuation",
            )

    # ── 1b. System info — "how's my system", "check CPU" etc. ───────────
    if _SYSTEM_INFO_RE.search(message):
        return TaskIntent(
            route="task",
            intent_type="system_info",
            slots={},
            confidence=0.95,
            reason="system_info_query",
        )

    # ── 1c. Project scan — "git status", "check my repo" etc. ──────────
    if _PROJECT_SCAN_RE.search(message):
        path_match = _FILE_PATH_RE.search(message)
        return TaskIntent(
            route="task",
            intent_type="project_scan",
            slots={"path": path_match.group(0) if path_match else "D:/AI_round2"},
            confidence=0.93,
            reason="project_scan_query",
        )

    # ── 1d. File read — "read file", "show me", "cat" + path ────────────
    if _FILE_READ_RE.search(message):
        path_match = _FILE_PATH_RE.search(message)
        if path_match:
            return TaskIntent(
                route="task",
                intent_type="file_read",
                slots={"path": path_match.group(0)},
                confidence=0.93,
                reason="file_read_query",
            )

    # ── 1e. Directory list — "ls", "list directory" + path ───────────────
    if _DIR_LIST_RE.search(message):
        path_match = _FILE_PATH_RE.search(message)
        return TaskIntent(
            route="task",
            intent_type="dir_list",
            slots={"path": path_match.group(0) if path_match else "D:/AI_round2"},
            confidence=0.93,
            reason="dir_list_query",
        )

    # ── 1f. Bare path with file extension → file_read ────────────────────
    path_match = _FILE_PATH_RE.search(message)
    if path_match and "." in path_match.group(0).split("/")[-1]:
        # Message contains a file path with extension — likely wants to read it
        lower = message.lower()
        if any(v in lower for v in ("read", "show", "open", "what", "print", "display", "cat", "look", "contents")):
            return TaskIntent(
                route="task",
                intent_type="file_read",
                slots={"path": path_match.group(0)},
                confidence=0.88,
                reason="path_with_read_verb",
            )

    # ── 1g. Skill install — "add skill from URL" ────────────────────────
    if url_match and _SKILL_INSTALL_RE.search(message):
        return TaskIntent(
            route="task",
            intent_type="skill_install",
            slots={
                "url": url_match.group(0),
                "raw_message": message,
            },
            confidence=0.95,
            reason="skill_install_with_url",
        )

    # ── 2. URL with explicit action verb ─────────────────────────────────
    if _URL_ACTION_RE.search(message) or _BARE_URL_RE.match(message):
        slots: Dict[str, Any] = {}
        if url_match:
            slots["url"] = url_match.group(0)
        if _INSTRUCTION_VERB_RE.search(message):
            slots["action"] = "follow_instructions"
        return TaskIntent(
            route="task",
            intent_type="url_fetch",
            slots=slots,
            confidence=0.95,
            reason="url_action_pattern",
        )

    # ── 3. URL anywhere (not a knowledge question) ────────────────────────
    if url_match and not _KNOWLEDGE_QUESTION_RE.search(message):
        return TaskIntent(
            route="task",
            intent_type="url_fetch",
            slots={
                "url": url_match.group(0),
                **({"action": "follow_instructions"} if _INSTRUCTION_VERB_RE.search(message) else {}),
            },
            confidence=0.88,
            reason="url_in_message",
        )

    # ── 4. Imperative store/save/update without URL ───────────────────────
    # Check this BEFORE service_action — API key messages must always store,
    # even if they mention a known service name.
    if _IMPERATIVE_TASK_RE.search(message) or _API_KEY_RE.search(message):
        key_match = _API_KEY_RE.search(message)
        return TaskIntent(
            route="task",
            intent_type="imperative_task",
            slots={
                "action": "store_or_update",
                **({"api_key": key_match.group(0)} if key_match else {}),
                "raw_message": message,
            },
            confidence=0.85,
            reason="imperative_or_api_key_detected",
        )

    # ── 4b. Known service reference (credential-store-based) ───────────
    # If the message mentions a service we have credentials for + action verb,
    # route to the task agent with the service name resolved.
    # Placed AFTER imperative check so API key messages store correctly.
    #
    # GUARD: If the message is a meta-question ABOUT the service (e.g.
    # "what is moltbook?", "tell me about moltbook"), route conversationally.
    # Only route to task agent when there's a genuine action verb that
    # survives after removing the service name from the message.
    known_svcs = _get_known_services()
    # Also check a space-stripped version for fuzzy matching ("molt book" → "moltbook")
    msg_compact = re.sub(r"[\s_-]+", "", msg_lower)
    if known_svcs:
        for svc_name, svc_meta in known_svcs.items():
            if re.search(r"\b" + re.escape(svc_name) + r"\b", msg_lower) or svc_name in msg_compact:
                # Meta-question guard: strip the service name and check
                # if a real action verb remains.  Questions like
                # "what is moltbook" or "how does moltbook work" should
                # NOT trigger agentic mode.
                if _KNOWLEDGE_QUESTION_RE.search(message):
                    _stripped = re.sub(
                        r"\b" + re.escape(svc_name) + r"\b", "", msg_lower
                    ).strip()
                    # Check if a *substantive* action verb remains after
                    # removing the service name.  Bare question words like
                    # "what is" alone don't count — they're knowledge Qs.
                    # But "whats new on", "check my", "any updates" do.
                    _has_substantive_action = (
                        _SERVICE_WRITE_RE.search(_stripped)
                        or _SERVICE_READ_RE.search(_stripped)
                    )
                    # Filter out bare question-word matches that have no
                    # real action content (e.g., "what is " with nothing after)
                    if _has_substantive_action:
                        _action_stripped = re.sub(
                            r"\b(what(?:'?s|\s+are|\s+is)|whats)\b", "", _stripped
                        ).strip()
                        # If removing question words leaves only whitespace/punct,
                        # it's a meta-question, not an action
                        _action_stripped = re.sub(r"[?\s.!]+", "", _action_stripped)
                        if not _action_stripped:
                            _has_substantive_action = False

                    if not _has_substantive_action:
                        # No action verb survives → knowledge question
                        logger.info(
                            "[INTENT] Meta-question about service '%s' — routing conversational",
                            svc_name,
                        )
                        return TaskIntent(
                            route="conversational",
                            intent_type="conversational",
                            slots={},
                            confidence=0.85,
                            reason="meta_question_about_service",
                        )

                has_action = _SERVICE_WRITE_RE.search(message) or _SERVICE_READ_RE.search(message)
                if has_action:
                    is_write = bool(_SERVICE_WRITE_RE.search(message))
                    return TaskIntent(
                        route="task",
                        intent_type="service_action",
                        slots={
                            "service": svc_name,
                            "action": "write" if is_write else "query",
                            "credential_key": svc_meta.get("credential_key", ""),
                            "skill_url_key": svc_meta.get("skill_url_key", ""),
                            "api_base_key": svc_meta.get("api_base_key", ""),
                            "raw_message": message,
                        },
                        confidence=0.85,
                        reason="service_credential_match",
                    )

    # ── 4c. Service continuation — no service name but recent service task ──
    # If the message has action verbs (check, find, search, post, etc.) but
    # didn't mention a service name, check if the last completed task was a
    # service_action and inherit that context.
    if active_task and active_task.get("intent_type") == "service_action":
        has_read_verb = _SERVICE_READ_RE.search(message)
        has_write_verb = _SERVICE_WRITE_RE.search(message)
        if has_read_verb or has_write_verb:
            prev_ctx = active_task.get("context") or {}
            prev_service = prev_ctx.get("_service", "")
            prev_cred_key = prev_ctx.get("_credential_key", "")
            if prev_service and known_svcs and prev_service in known_svcs:
                svc_meta = known_svcs[prev_service]
                is_write = bool(has_write_verb)
                logger.info(
                    "[INTENT] Service continuation: '%s' → inherited service '%s' from last task",
                    message[:60], prev_service,
                )
                return TaskIntent(
                    route="task",
                    intent_type="service_action",
                    slots={
                        "service": prev_service,
                        "action": "write" if is_write else "query",
                        "credential_key": prev_cred_key or svc_meta.get("credential_key", ""),
                        "skill_url_key": svc_meta.get("skill_url_key", ""),
                        "api_base_key": svc_meta.get("api_base_key", ""),
                        "raw_message": message,
                    },
                    confidence=0.80,
                    reason="service_continuation_from_last_task",
                )

    # ── 5. Continuation keywords even without active task ─────────────────
    # Only match if the continuation pattern is near the start (first 120 chars)
    # to avoid hijacking long pasted content
    _cont_check = message if len(message) <= 200 else message[:120]
    if _CONTINUATION_RE.search(_cont_check):
        return TaskIntent(
            route="task",
            intent_type="task_continuation",
            slots={"continuation_message": message},
            confidence=0.75,
            reason="continuation_pattern_no_active_task",
        )

    return TaskIntent(
        route="conversational",
        intent_type="conversational",
        slots={},
        confidence=0.90,
        reason="no_task_pattern",
    )


# ---------------------------------------------------------------------------
# HTTP tools (1.1)
# ---------------------------------------------------------------------------


def _http_get(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, str, int, float]:
    """GET request. Returns (status_code, body_text, byte_count, duration_ms)."""
    t0 = time.monotonic()
    req_headers = {"User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        duration_ms = (time.monotonic() - t0) * 1000
        return e.code, e.read().decode("utf-8", errors="replace"), 0, duration_ms

    duration_ms = (time.monotonic() - t0) * 1000
    text = raw.decode("utf-8", errors="replace")
    # Strip HTML for readability
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return status, text[:12_000], len(raw), duration_ms


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any, float]:
    """GET request with JSON parsing. Returns (status_code, parsed_body, duration_ms)."""
    t0 = time.monotonic()
    req_headers = {
        "User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)",
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        duration_ms = (time.monotonic() - t0) * 1000
        try:
            body = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            body = {"error": str(e)}
        return e.code, body, duration_ms

    duration_ms = (time.monotonic() - t0) * 1000
    try:
        body = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        body = {"raw": raw.decode("utf-8", errors="replace")[:2000]}
    return status, body, duration_ms


def _http_post(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Any, float]:
    """POST JSON payload. Returns (status_code, parsed_response_body, duration_ms)."""
    t0 = time.monotonic()
    body_bytes = json.dumps(payload).encode("utf-8")
    req_headers = {
        "User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        duration_ms = (time.monotonic() - t0) * 1000
        try:
            resp_body = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            resp_body = {"error": str(e), "status": e.code}
        return e.code, resp_body, duration_ms

    duration_ms = (time.monotonic() - t0) * 1000
    try:
        resp_body = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        resp_body = {"raw": raw.decode("utf-8", errors="replace")[:2000]}
    return status, resp_body, duration_ms


# ---------------------------------------------------------------------------
# Execution verification (1.2)
# ---------------------------------------------------------------------------


def _verify_response(
    status: int,
    body: Any,
    expected_fields: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Check response is valid. Returns (ok, reason)."""
    if status == 409:
        return False, "HTTP 409 — already registered (resource exists)"
    if status < 200 or status >= 300:
        return False, f"HTTP {status} — not a success response"
    if expected_fields:
        body_str = json.dumps(body) if not isinstance(body, str) else body
        missing = [f for f in expected_fields if f not in body_str.lower()]
        if missing:
            return False, f"Response missing expected fields: {missing}"
    return True, "ok"


def _extract_key_fields(body: Any) -> Dict[str, str]:
    """Pull API keys, tokens, URLs from a response body."""
    found: Dict[str, str] = {}
    if isinstance(body, dict):
        for indicator in _RESPONSE_FIELD_INDICATORS:
            for k, v in body.items():
                if indicator in k.lower() and isinstance(v, str) and len(v) > 4:
                    found[k] = v
    elif isinstance(body, str):
        # Try to find key=value pairs
        for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]{6,})"', body):
            k, v = m.group(1), m.group(2)
            if any(ind in k.lower() for ind in _RESPONSE_FIELD_INDICATORS):
                found[k] = v
    return found


# ---------------------------------------------------------------------------
# AgentStep
# ---------------------------------------------------------------------------


@dataclass
class AgentStep:
    step_index: int
    tool_name: str
    input: Dict[str, Any]
    output: Optional[Any] = None
    output_preview: Optional[str] = None
    byte_count: int = 0
    duration_ms: float = 0.0
    status: Literal["pending", "running", "ok", "error", "queued", "retrying"] = "pending"
    error: Optional[str] = None
    verified: bool = False
    extracted_fields: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "tool_name": self.tool_name,
            "input": self.input,
            "output_preview": self.output_preview,
            "byte_count": self.byte_count,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "verified": self.verified,
            "extracted_fields": self.extracted_fields,
        }


# ---------------------------------------------------------------------------
# CRTTaskAgent
# ---------------------------------------------------------------------------


class CRTTaskAgent:
    """Clean execution route for task/agentic queries.

    Emits SSE-compatible event dicts via run_stream().
    Verifies execution results — does not trust LLM narration of success.
    Writes learned facts back through CRT memory after completion.
    """

    def __init__(self, memory_agent=None, llm_client=None, session_db=None):
        self._memory = memory_agent
        self._llm = llm_client
        self._session_db = session_db  # for task context persistence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_stream(
        self,
        message: str,
        thread_id: str,
        intent: Optional[TaskIntent] = None,
        active_task: Optional[Dict[str, Any]] = None,
        user_confirmed: bool = False,
    ) -> Generator[Dict[str, Any], None, None]:
        """Execute task; yield SSE event dicts throughout.

        If ``user_confirmed`` is False (default), the method emits an
        ``agent_checkpoint`` event and **returns immediately** for
        medium/low-confidence intents.  The caller (``chat.py``) must
        wait for the user's next message, parse confirmation, and
        re-invoke ``run_stream`` with ``user_confirmed=True``.
        """
        if intent is None:
            intent = classify_intent(message, active_task=active_task)

        # ── 0. CHECKPOINT: Inform user before entering agentic mode ────────
        if not user_confirmed:
            gate = gate_task_intent(intent)
            if gate["checkpoint_tier"] != "none":
                yield {
                    "type": "agent_checkpoint",
                    "content": gate["checkpoint_message"],
                    "metadata": {
                        "intent": intent.intent_type,
                        "checkpoint_tier": gate["checkpoint_tier"],
                        "requires_confirmation": gate["requires_confirmation"],
                        "auto_proceed_seconds": None,
                        "slots": intent.slots,
                        "confidence": intent.confidence,
                    },
                }
                # Stop here — caller must re-invoke after user confirms.
                return

        # ── 1. Emit intent ────────────────────────────────────────────────
        yield {
            "type": "intent_classified",
            "content": f"intent: {intent.intent_type}  route: {intent.route}",
            "metadata": {
                "intent": intent.intent_type,
                "route": intent.route,
                "slots": intent.slots,
                "confidence": intent.confidence,
                "reason": intent.reason,
            },
        }

        # ── 2. Build phase-1 plan ─────────────────────────────────────────
        phase1_plan = self._build_plan(intent, message, active_task)
        yield {
            "type": "plan_ready",
            "content": f"{len(phase1_plan)} step{'s' if len(phase1_plan) != 1 else ''}",
            "metadata": {"steps": phase1_plan},
        }

        # ── 3. Execute phase-1 (fetch / credential store / etc.) ──────────
        steps: List[AgentStep] = []
        fetched_content: Optional[str] = None
        stored_credentials: Dict[str, str] = {}
        task_context: Dict[str, Any] = dict(active_task or {})
        # Track service info for credential injection during execution
        if intent.intent_type == "service_action":
            task_context["_service"] = intent.slots.get("service", "")
            task_context["_credential_key"] = intent.slots.get("credential_key", "")

        skill_content: Optional[str] = None  # skill docs — used for replanning only, NOT answer context
        for i, step_plan in enumerate(phase1_plan):
            tool = step_plan["tool"]
            inp = dict(step_plan["input"])
            step = AgentStep(step_index=i, tool_name=tool, input=inp, status="running")
            steps.append(step)

            yield {"type": "tool_start", "content": f"▷ {tool}",
                   "metadata": {"tool_name": tool, "input": inp, "step_index": i}}

            result_event = yield from self._execute_step(
                step, tool, inp, thread_id, i,
                fetched_content=fetched_content or skill_content, task_context=task_context,
            )

            if step.status == "ok":
                if tool == "load_cached_skill":
                    # Skill docs feed replanning but must NOT leak into answer context
                    skill_content = step.output if isinstance(step.output, str) else skill_content
                elif tool in ("fetch_url", "http_get"):
                    fetched_content = step.output if isinstance(step.output, str) else fetched_content
                    # Track source URL so store_credential can save service metadata
                    task_context["source_url"] = inp.get("url", "")
                    task_context["_fetched_content"] = fetched_content
                    # Cache skill content after successful fetch for service actions
                    if tool == "fetch_url" and intent.intent_type == "service_action":
                        _svc = intent.slots.get("service", "")
                        _url = inp.get("url", "")
                        if _svc and _url:
                            try:
                                _req = urllib.request.Request(
                                    _url, headers={"User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)"}
                                )
                                with urllib.request.urlopen(_req, timeout=10) as _resp:
                                    _raw = _resp.read().decode("utf-8", errors="replace")
                                _cache_skill_content(_svc, _raw)
                            except Exception:
                                pass  # non-critical — cache miss next time just re-fetches
                if step.extracted_fields:
                    stored_credentials.update(step.extracted_fields)
                    task_context.update(step.extracted_fields)

            yield result_event

        # ── 3b. Phase-2 re-plan (if we fetched content + action=follow) ───
        # Use fetched_content if available, otherwise fall back to skill_content for replanning
        replan_source = fetched_content or skill_content
        needs_replan = (
            replan_source
            and intent.intent_type in ("url_fetch", "service_action")
            and intent.intent_type != "skill_install"
            and intent.slots.get("action") in ("follow_instructions", "write", "query")
        )
        replan_attempted_but_failed = False
        llm_loop_final_content = ""
        if needs_replan:
            yield {"type": "status", "content": "analyzing fetched content"}

            # ── Primary: LLM-driven iterative tool loop ────────────────
            # Skip LLM loop for write actions — qwen3:14b can't reliably match
            # user intent to the correct write endpoint from docs. The deterministic
            # curl parser with intent-scored POST selection is more reliable.
            _used_llm_loop = False
            action = intent.slots.get("action", "query")
            _skip_llm_for_write = (action == "write")
            if not _skip_llm_for_write and self._llm is not None and hasattr(self._llm, "chat_with_tools"):
                try:
                    loop_steps, llm_loop_final_content = yield from self._llm_tool_loop(
                        message=message,
                        thread_id=thread_id,
                        intent=intent,
                        fetched_content=replan_source,
                        task_context=task_context,
                        existing_steps=steps,
                        budget=8,
                    )
                    if loop_steps:
                        steps.extend(loop_steps)
                        for s in loop_steps:
                            if s.extracted_fields:
                                stored_credentials.update(s.extracted_fields)
                        _used_llm_loop = True
                    else:
                        logger.info("[TASK_AGENT] LLM tool loop returned 0 steps, falling back to curl parser")
                except Exception as e:
                    logger.warning("[TASK_AGENT] LLM tool loop failed, falling back to curl parser: %s", e)

            # ── Fallback: deterministic curl parser ────────────────────
            if not _used_llm_loop:
                phase2_plan = self._replan_from_content(replan_source, message, intent)

                if not phase2_plan:
                    replan_attempted_but_failed = True
                    yield {
                        "type": "status",
                        "content": "could not determine execution steps from content",
                    }
                    needs_replan = False
                else:
                    _MAX_STEPS = 8
                    phase2_plan = phase2_plan[:_MAX_STEPS]
                    step_budget = len(phase2_plan)

                    # Checkpoint for write actions
                    has_writes = any(s["tool"] in ("http_post",) for s in phase2_plan)
                    if has_writes:
                        write_urls = [
                            s["input"].get("url", "unknown")
                            for s in phase2_plan if s["tool"] == "http_post"
                        ]
                        yield {
                            "type": "agent_checkpoint",
                            "content": (
                                f"Phase 2 includes {len(write_urls)} write action(s): "
                                + ", ".join(write_urls[:3])
                                + ". Proceed?"
                            ),
                            "metadata": {
                                "tier": "tier_1",
                                "intent_type": intent.intent_type,
                                "action": intent.slots.get("action", ""),
                                "write_urls": write_urls[:3],
                                "phase": 2,
                            },
                        }
                        return

                    yield {
                        "type": "plan_ready",
                        "content": f"{step_budget} action step{'s' if step_budget != 1 else ''}",
                        "metadata": {"steps": phase2_plan, "budget": step_budget, "phase": 2},
                    }

                    base_idx = len(steps)
                    for j, step_plan in enumerate(phase2_plan):
                        tool = step_plan["tool"]
                        inp = dict(step_plan["input"])
                        step_idx = base_idx + j
                        step = AgentStep(step_index=step_idx, tool_name=tool, input=inp, status="running")
                        steps.append(step)

                        yield {"type": "tool_start", "content": f"▷ {tool}",
                               "metadata": {"tool_name": tool, "input": inp, "step_index": step_idx,
                                            "step_num": j + 1, "step_total": step_budget}}

                        result_event = yield from self._execute_step(
                            step, tool, inp, thread_id, step_idx,
                            fetched_content=fetched_content, task_context=task_context,
                        )

                        if step.status == "ok":
                            if step.extracted_fields:
                                stored_credentials.update(step.extracted_fields)
                                task_context.update(step.extracted_fields)

                        yield result_event

        # ── 4. Persist task state to session DB ───────────────────────────
        self._persist_task_state(thread_id, intent, steps, task_context, stored_credentials)

        # ── 5. Validate ───────────────────────────────────────────────────
        all_ok = all(s.status in ("ok", "queued") for s in steps)
        yield {
            "type": "validate_result",
            "content": "all steps verified ✓" if all_ok else "some steps failed — see details",
            "metadata": {
                "conflicts": [],
                "gate": "pass" if all_ok else "partial",
                "route": "task",
                "verified_steps": sum(1 for s in steps if s.verified),
                "failed_steps": sum(1 for s in steps if s.status == "error"),
            },
        }

        # ── 6. Generate answer (streaming with thinking tokens) ───────────
        yield {"type": "status", "content": "drafting response"}
        if llm_loop_final_content:
            # LLM tool loop already synthesized an answer — filter reasoning
            answer = self._filter_reasoning_from_content(llm_loop_final_content)
            yield {"type": "token", "content": answer}
        elif intent.intent_type == "skill_install":
            # Deterministic answer for skill installs — report what was installed
            _install_step = next((s for s in steps if s.tool_name == "install_skill" and s.status == "ok"), None)
            if _install_step:
                _meta = _install_step.output_preview or ""
                # Extract service name from the step output
                _svc_name = ""
                if "name=" in _meta:
                    _svc_name = _meta.split("name=")[1].split(",")[0].strip()
                answer = (
                    f"Skill **{_svc_name or 'unknown'}** installed successfully. "
                    f"Saved to `data/managed_skills/{_svc_name}/SKILL.md` and registered as a known service.\n\n"
                    f"To use it, I'll need an API key. You can provide one by saying:\n"
                    f'*"here is my {_svc_name} API key: your_key_here"*'
                )
            else:
                answer = "Skill installation failed — check the steps above for details."
            yield {"type": "token", "content": answer}
        elif intent.slots.get("_no_endpoint"):
            # Service recognized from credentials but no API endpoint stored.
            # Deterministic answer — never let the LLM hallucinate fake service data.
            service = intent.slots.get("service", "the service")
            answer = (
                f"I have credentials for {service}, but I don't have the API endpoint stored yet. "
                f"Give me the {service} URL or skill.md link and I can fetch it and interact with the service."
            )
        elif replan_attempted_but_failed:
            # Never hand fetched content to the LLM when we couldn't build a plan —
            # it will hallucinate a fake execution (narrate moltbook registration etc.)
            url = intent.slots.get("url", "the URL")
            answer = (
                f"I fetched the content from {url} successfully, "
                "but couldn't parse any executable API steps from it. "
                "No actions were taken."
            )
            yield {"type": "token", "content": answer}
        else:
            answer = yield from self._stream_generate_answer(
                message, fetched_content, intent, steps, stored_credentials, active_task
            )

        # ── 7. Write facts through CRT memory ────────────────────────────
        facts_written = self._write_facts(
            thread_id, intent, fetched_content, stored_credentials, steps
        )

        # ── 8. Done ───────────────────────────────────────────────────────
        yield {
            "type": "task_done",
            "content": answer,
            "metadata": {
                "answer": answer,
                "steps": [s.to_dict() for s in steps],
                "facts_written": facts_written,
                "stored_credentials": list(stored_credentials.keys()),
                "intent": {
                    "route": intent.route,
                    "intent_type": intent.intent_type,
                    "slots": intent.slots,
                    "confidence": intent.confidence,
                },
                "pipeline_statuses": [
                    f"task: {intent.intent_type}",
                    *(f"{s.tool_name}: {s.status}" for s in steps),
                    "validate: pass" if all_ok else "validate: partial",
                ],
                "gates_passed": True,
                "gate_reason": "task_route",
                "response_type": "task",
                "confidence": 0.88 if all_ok else 0.60,
            },
        }

        # Clear pending task from session DB on full completion
        if all_ok and self._session_db is not None:
            try:
                self._session_db.clear_pending_task(thread_id)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Phase-2 re-planner: content → concrete tool calls
    # ------------------------------------------------------------------

    # Tool schemas for native function-calling (Qwen3 / Ollama tool use)
    _TOOL_SCHEMAS: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "http_post",
                "description": "Make an HTTP POST request to an API endpoint",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Full URL to POST to"},
                        "payload": {"type": "object", "description": "JSON body to send"},
                        "headers": {"type": "object", "description": "Optional HTTP headers"},
                        "expected_fields": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Fields expected in the response to verify success",
                        },
                    },
                    "required": ["url", "payload"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "http_get_json",
                "description": "Make an HTTP GET request and return JSON response",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Full URL to GET"},
                        "headers": {"type": "object", "description": "Optional HTTP headers"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "store_credential",
                "description": "Store a credential value securely for later use",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Name to store the credential under"},
                        "source_field": {
                            "type": "string",
                            "description": "Field name from previous step response to use as value",
                        },
                        "value": {"type": "string", "description": "Literal value to store (if not using source_field)"},
                    },
                    "required": ["key"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_budget_extension",
                "description": "Request more tool calls if you need additional steps to complete the task. Only call this when you genuinely need more steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Why more steps are needed"},
                        "additional_steps": {"type": "integer", "description": "How many more steps needed (1-7)"},
                    },
                    "required": ["reason", "additional_steps"],
                },
            },
        },
    ]

    _VALID_TOOLS = {"http_post", "http_get_json", "store_credential", "request_budget_extension"}

    # ------------------------------------------------------------------
    # LLM Tool Loop — iterative agent execution
    # ------------------------------------------------------------------

    _TOOL_LOOP_SYSTEM_PROMPT = """You are Aether, executing a task step by step. Think out loud. The user can see your reasoning.

CRITICAL: Focus on exactly what the user asked. Read their goal carefully and pick the API endpoint that best matches their intent.
- "what's new" / "what's happening" → use the feed/home/timeline endpoint, NOT search
- "search for X" / "find X" → use the search endpoint with the user's terms
- "show me my X" → use the user's profile/account endpoint

CONTEXT:
- You are already registered and authenticated with this service.
- Your credentials are stored and will be auto-injected into Authorization headers.
- Do NOT register, sign up, or create accounts — you already have one.
- Action type: {action}. For "query" actions, use only GET requests. Do NOT POST unless the user explicitly asked to write/post/comment.
- For "write" actions: Match the user's EXACT intent to the correct endpoint. If they say "mark notifications as read", use the notifications endpoint, NOT the posts endpoint. Read the API docs carefully for the right URL and method.

HOW TO WORK:
1. THINK OUT LOUD before every tool call. Say what you're about to do and why.
2. Call the tool. Always use FULL URLs (https://...), never relative paths.
3. When you get results back, ANALYZE them out loud.
4. Then decide: do you have enough to answer the user's question, or should you dig deeper?
5. When done, give a natural summary of what you found.

RULES:
- Include "Authorization": "Bearer YOUR_API_KEY" in headers — it gets replaced automatically.
- You have a budget of {budget} tool calls. Use them wisely but don't stop after just one.
- For browsing tasks: GET the feed/list first, then GET details on the interesting items.
- Never fabricate API responses. Only report what tools actually returned.
- SKIP registration/setup sections in the docs.
- Always explain what you're doing and why — the user is watching."""

    _HARD_MAX_BUDGET = 15
    _MAX_CONSECUTIVE_FAILURES = 3

    @staticmethod
    def _extract_relevant_skill_sections(content: str, action: str, message: str) -> str:
        """Extract only the API sections relevant to the user's goal.

        Skill.md files are often 30KB+ — sending the whole thing wastes context
        and causes the LLM to pick early endpoints (registration, setup) instead
        of the ones that match the user's intent.
        """
        if not content or len(content) < 500:
            return content[:8000]

        msg_lower = message.lower()

        # Split by markdown headers (## and ### sections)
        sections: List[Tuple[str, str]] = []
        current_header = ""
        current_body: List[str] = []
        for line in content.split("\n"):
            if line.startswith("## ") or line.startswith("### "):
                if current_header or current_body:
                    sections.append((current_header, "\n".join(current_body)))
                current_header = line
                current_body = []
            else:
                current_body.append(line)
        if current_header or current_body:
            sections.append((current_header, "\n".join(current_body)))

        # Always include: Base URL, Authentication
        # For queries: Posts, Feed, Search, Comments, Submolts, Notifications
        # For writes: Posts (create), Comments (add), Voting
        # Skip: Register, Heartbeat, Setup, Claim Status

        skip_headers = {
            "register", "registration", "heartbeat", "set up", "setup",
            "claim", "install", "crypto", "verification challenge",
        }

        # Priority sections based on action + message keywords
        priority_keywords: List[str] = []
        if action == "query":
            priority_keywords = ["search", "feed", "home", "post", "submolt",
                                 "notification", "following", "profile", "comment"]
        else:
            priority_keywords = ["post", "comment", "vote", "submolt", "follow",
                                 "notification", "mark", "read", "update", "delete"]

        # Extra boost from user message
        for word in ["thread", "search", "find", "browse", "interesting", "trending",
                     "hot", "new", "comment", "reply", "post", "feed", "notification",
                     "mark", "read", "unread", "dismiss", "clear", "archive"]:
            if word in msg_lower:
                priority_keywords.insert(0, word)

        selected: List[str] = []
        total_chars = 0
        max_chars = 8000

        # Cap individual section size to prevent one huge section eating the budget
        _MAX_SECTION = 1800

        # Extract user message keywords for body-level matching
        _msg_words = set(re.findall(r'\b\w{3,}\b', msg_lower))

        # First pass: score and sort sections by priority keyword match
        scored_sections: List[Tuple[int, str, str]] = []
        for header, body in sections:
            header_lower = header.lower()
            if any(skip in header_lower for skip in skip_headers):
                continue
            # Score: earlier position in priority_keywords = higher score
            score = 0
            for i, kw in enumerate(priority_keywords):
                if kw in header_lower:
                    score = max(score, len(priority_keywords) - i)
            # Bonus: check if user message keywords appear in section body
            body_lower = body.lower()
            for word in _msg_words:
                if len(word) >= 4 and word in body_lower:
                    score += 1
            if score > 0:
                scored_sections.append((score, header, body))

        # Sort by score descending — most relevant sections first
        scored_sections.sort(key=lambda x: x[0], reverse=True)

        for _score, header, body in scored_sections:
            section_text = f"{header}\n{body}"
            if len(section_text) > _MAX_SECTION:
                section_text = section_text[:_MAX_SECTION] + "\n[... truncated]"
            if total_chars + len(section_text) < max_chars:
                selected.append(section_text)
                total_chars += len(section_text)

        # Second pass: fill remaining budget with other sections
        for header, body in sections:
            header_lower = header.lower()
            if any(skip in header_lower for skip in skip_headers):
                continue
            section_text = f"{header}\n{body}"
            if any(section_text.startswith(s[:50]) for s in selected):
                continue
            if len(section_text) > _MAX_SECTION:
                section_text = section_text[:_MAX_SECTION] + "\n[... truncated]"
            if total_chars + len(section_text) < max_chars:
                selected.append(section_text)
                total_chars += len(section_text)

        if not selected:
            return content[:8000]

        # Always prepend base URL info
        base_url_line = ""
        for line in content.split("\n")[:50]:
            if "base url" in line.lower() or "api/v1" in line.lower():
                base_url_line = line.strip()
                break

        result = base_url_line + "\n\n" + "\n\n".join(selected) if base_url_line else "\n\n".join(selected)
        return result[:max_chars]

    def _llm_tool_loop(
        self,
        message: str,
        thread_id: str,
        intent: TaskIntent,
        fetched_content: Optional[str],
        task_context: Dict[str, Any],
        existing_steps: List[AgentStep],
        budget: int = 8,
    ) -> Generator[Dict[str, Any], None, Tuple[List[AgentStep], str]]:
        """Iterative LLM-driven tool execution loop.

        The LLM sees skill docs + user goal, decides which tools to call,
        sees results, and decides next steps. Continues until it stops
        calling tools, hits the budget, or fails 3 times consecutively.

        Yields SSE events for streaming. Returns (steps, final_content).
        """
        service = intent.slots.get("service", "")
        action = intent.slots.get("action", "query")

        system_prompt = self._TOOL_LOOP_SYSTEM_PROMPT.format(budget=budget, action=action)
        if service:
            system_prompt += f"\nService: {service}\nAction: {action}"
        if action == "write":
            user_msg = intent.slots.get("raw_message", message)
            system_prompt += (
                f"\n\nIMPORTANT — The user's EXACT request is: \"{user_msg}\"\n"
                f"Find the API endpoint in the docs below that EXACTLY matches this request. "
                f"Do NOT default to creating a post or any other action unless the user explicitly asked for it."
            )

        # Build initial messages with skill content — extract relevant sections
        raw_skill = fetched_content or ""
        skill_snippet = self._extract_relevant_skill_sections(raw_skill, action, message)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Goal: {message}\n\nAPI Documentation:\n{skill_snippet}"},
        ]

        steps: List[AgentStep] = []
        base_idx = len(existing_steps)
        tool_call_count = 0
        consecutive_failures = 0
        final_content = ""

        # For query actions, remove http_post from available tools
        # so the LLM can't accidentally try to write
        available_tools = self._TOOL_SCHEMAS
        if action == "query":
            available_tools = [t for t in self._TOOL_SCHEMAS
                               if t["function"]["name"] != "http_post"]

        # Use fast model for tool loop reasoning
        fast_model = os.getenv("CRT_MODEL_FAST") or "role:fast"

        while tool_call_count < budget:
            # 1. Call LLM with current context
            yield {
                "type": "status",
                "content": f"reasoning (step {tool_call_count + 1}/{budget})",
            }

            try:
                result = self._llm.chat_with_tools(
                    messages=messages,
                    tools=available_tools,
                    max_tokens=1000,
                    temperature=0.1,
                    model=fast_model,
                )
            except Exception as e:
                logger.warning("[TOOL_LOOP] LLM call failed: %s", e)
                yield {"type": "status", "content": f"LLM error: {e}"}
                break

            tool_calls = result.get("tool_calls", [])
            llm_content = result.get("content", "")

            # 2. Stream LLM reasoning — visible to user as thinking + status
            if llm_content:
                # Show a condensed version in the pipeline trace
                first_line = llm_content.strip().split("\n")[0][:120]
                yield {"type": "status", "content": first_line}
                # Full reasoning in thinking trace
                yield {
                    "type": "agent_thinking_token",
                    "content": llm_content,
                    "metadata": {"step": "tool_loop"},
                }

            # 3. No tool calls — LLM may be done, or may need a nudge
            if not tool_calls:
                if tool_call_count == 0:
                    # Never called a tool at all — accept as final answer
                    final_content = llm_content
                    break
                # Already called tools but stopped — nudge once to continue
                # (the LLM sometimes summarizes prematurely after 1 call)
                messages.append({"role": "assistant", "content": llm_content or ""})
                remaining = budget - tool_call_count
                messages.append({
                    "role": "user",
                    "content": (
                        f"You still have {remaining} tool calls remaining. "
                        f"Look at the results above — do you have ENOUGH information to fully answer the user's question? "
                        f"If you need more data (details on specific items, related endpoints, etc.), call another tool now. "
                        f"If you truly have enough, provide your final summary."
                    ),
                })
                # Give LLM one more chance — if it still doesn't call tools, accept
                try:
                    retry_result = self._llm.chat_with_tools(
                        messages=messages,
                        tools=available_tools,
                        max_tokens=1000,
                        temperature=0.1,
                        model=fast_model,
                    )
                except Exception:
                    final_content = llm_content
                    break

                retry_tools = retry_result.get("tool_calls", [])
                retry_content = retry_result.get("content", "")

                if retry_content:
                    yield {
                        "type": "agent_thinking_token",
                        "content": retry_content,
                        "metadata": {"step": "tool_loop"},
                    }

                if not retry_tools:
                    # LLM confirmed it's done
                    final_content = retry_content or llm_content
                    break

                # LLM wants to continue — inject its response and tool calls
                # back into the normal flow
                tool_calls = retry_tools
                llm_content = retry_content

            # 4. Append assistant message to history
            messages.append({"role": "assistant", "content": llm_content or ""})

            # 5. Execute each tool call
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})

                # Budget extension request
                if name == "request_budget_extension":
                    reason = args.get("reason", "")
                    extra = min(int(args.get("additional_steps", 3)), self._HARD_MAX_BUDGET - budget)
                    if extra > 0:
                        budget += extra
                        yield {
                            "type": "status",
                            "content": f"budget extended → {budget} ({reason})",
                        }
                        logger.info("[TOOL_LOOP] Budget extended to %d: %s", budget, reason)
                    messages.append({
                        "role": "tool",
                        "content": json.dumps({"budget_extended_to": budget}),
                    })
                    continue

                if name not in self._VALID_TOOLS:
                    messages.append({
                        "role": "tool",
                        "content": json.dumps({"error": f"unknown tool: {name}"}),
                    })
                    continue

                step_idx = base_idx + len(steps)
                step = AgentStep(step_index=step_idx, tool_name=name, input=dict(args), status="running")
                steps.append(step)

                # Checkpoint for write actions (POST)
                if name == "http_post":
                    post_url = args.get("url", "unknown")
                    payload_preview = json.dumps(args.get("payload", {}))[:200]
                    yield {
                        "type": "agent_checkpoint_write",
                        "content": f"About to POST to {post_url}: {payload_preview}. Confirm?",
                        "metadata": {
                            "tier": "tier_1",
                            "tool_name": name,
                            "input": args,
                            "step_index": step_idx,
                        },
                    }
                    # Note: for now, write checkpoints break the loop.
                    # The caller (run_stream) will persist state and resume
                    # after user confirmation. Full resume support is Phase 2.
                    return (steps, "Write action requires confirmation.")

                # Fix relative URLs — LLMs often emit /api/v1/... without the host
                if name in ("http_get_json", "http_post"):
                    url = args.get("url", "")
                    if url and not url.startswith(("http://", "https://")):
                        # Try to resolve from known service base
                        svc_base = _KNOWN_SERVICES.get(service, {}).get("api_base", "")
                        if svc_base:
                            # Strip overlapping path prefix: /api/v1/posts + base https://x.com/api/v1 → https://x.com/api/v1/posts
                            from urllib.parse import urlparse
                            base_path = urlparse(svc_base).path.rstrip("/")
                            if url.startswith(base_path):
                                url = svc_base.rstrip("/") + url[len(base_path):]
                            elif url.startswith("/"):
                                # Absolute path but no overlap — prepend scheme+host
                                parsed = urlparse(svc_base)
                                url = f"{parsed.scheme}://{parsed.netloc}{url}"
                            else:
                                url = svc_base.rstrip("/") + "/" + url
                            args["url"] = url
                            logger.info("[TOOL_LOOP] Fixed relative URL → %s", url)

                # Credential injection
                self._inject_credentials(dict(args), task_context, thread_id)
                # Update step input after injection
                step.input = dict(args)

                # Emit tool_start
                yield {
                    "type": "tool_start",
                    "content": f"▷ {name}",
                    "metadata": {
                        "tool_name": name,
                        "input": args,
                        "step_index": step_idx,
                    },
                }

                # Execute via existing infrastructure
                result_event = yield from self._execute_step(
                    step, name, args, thread_id, step_idx,
                    fetched_content=fetched_content, task_context=task_context,
                )

                # Track results
                if step.status == "ok":
                    consecutive_failures = 0
                    if step.extracted_fields:
                        task_context.update(step.extracted_fields)
                else:
                    consecutive_failures += 1

                tool_call_count += 1

                # Emit tool_result
                yield result_event

                # Append result to message history so LLM sees it
                tool_result_summary = {
                    "tool": name,
                    "status": step.status,
                    "output": (step.output_preview or "")[:2000],
                    "error": step.error,
                }
                if step.extracted_fields:
                    tool_result_summary["extracted"] = step.extracted_fields
                messages.append({
                    "role": "tool",
                    "content": json.dumps(tool_result_summary),
                })

                # Check failure threshold
                if consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    yield {"type": "status", "content": "stopping — 3 consecutive failures"}
                    break

                if tool_call_count >= budget:
                    break

            if consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                break

            # After processing all tool calls in this batch, nudge the LLM
            # to analyze results and decide next steps (prevents premature stop)
            if tool_call_count > 0 and tool_call_count < budget:
                remaining = budget - tool_call_count
                messages.append({
                    "role": "user",
                    "content": (
                        f"Results received. You've used {tool_call_count}/{budget} tool calls ({remaining} remaining). "
                        f"Think out loud: what did you learn? Is this enough to fully answer the user's question? "
                        f"If a list was returned, consider fetching details on the most relevant items. "
                        f"If you have enough, give your final answer now."
                    ),
                })

        logger.info(
            "[TOOL_LOOP] Completed: %d tool calls, %d steps, %d failures",
            tool_call_count, len(steps), consecutive_failures,
        )
        return (steps, final_content)

    # ------------------------------------------------------------------
    # Curl-command parser — deterministic Phase-2 plan extraction
    # ------------------------------------------------------------------

    # Regex: matches curl commands with optional line-continuation
    _CURL_RE = re.compile(
        r"curl\s+"
        r"((?:(?:-[a-zA-Z]+|--\S+)\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s+)*)"  # flags
        r"[\"']?"                                                          # optional opening quote around URL
        r"(https?://[^\s'\"\\<>\]]+)",                                     # URL
        re.IGNORECASE,
    )
    _DATA_RE = re.compile(
        r"(?:-d|--data(?:-raw)?)\s+"
        r"(?:'(\{[^']*\})'|\"(\{[^\"]*\})\")",  # single or double quoted JSON body
        re.DOTALL,
    )
    _METHOD_RE = re.compile(r"-X\s+(\w+)", re.IGNORECASE)
    _HEADER_RE = re.compile(r"-H\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
    # Detects unfilled template placeholders — e.g. POST_ID, COMMENT_ID, YOUR_API_KEY
    # Requires an underscore so abbreviations like CRT, API, URL don't false-positive
    _UNFILLED_PLACEHOLDER_RE = re.compile(r"(?<![a-zA-Z])[A-Z][A-Z0-9]*_[A-Z0-9_]+(?![a-zA-Z])")

    # Default values to substitute for stub placeholders in curl examples
    _PLACEHOLDER_SUBS: List[Tuple[re.Pattern, str]] = []

    @staticmethod
    def _make_placeholder_subs() -> List[Tuple[re.Pattern, str]]:
        return [
            (re.compile(r"YourAgentName", re.IGNORECASE), "Aether"),
            (re.compile(r"your[_-]?agent[_-]?name", re.IGNORECASE), "Aether"),
            (re.compile(r"YourEmail", re.IGNORECASE), "aether@local"),
            (re.compile(r"your[_-]?email", re.IGNORECASE), "aether@local"),
            (re.compile(r"optional@example\.com", re.IGNORECASE), ""),
            (re.compile(r"\"optional[^\"]{0,60}\"", re.IGNORECASE), '""'),
            (re.compile(r"What you do", re.IGNORECASE), "CRT-verified AI assistant"),
            (re.compile(r"Your description here", re.IGNORECASE), "CRT-verified AI assistant"),
            (re.compile(r"<description>", re.IGNORECASE), "CRT-verified AI assistant"),
        ]

    def _fill_placeholders(self, payload_str: str) -> str:
        """Replace stub placeholder values in JSON payload strings."""
        if not hasattr(self, "_ph_subs"):
            self._ph_subs = self._make_placeholder_subs()
        for pattern, replacement in self._ph_subs:
            payload_str = pattern.sub(replacement, payload_str)
        return payload_str

    def _infer_expected_fields(self, content: str, after_pos: int) -> List[str]:
        """Scan the ~1500 chars after a curl block for response field names."""
        window = content[after_pos: after_pos + 1500]
        found = []
        for indicator in _RESPONSE_FIELD_INDICATORS:
            if f'"{indicator}"' in window or f"'{indicator}'" in window:
                found.append(indicator)
        return found[:5]

    # ------------------------------------------------------------------
    # Intent-aware endpoint scoring
    # ------------------------------------------------------------------

    # Maps user intent keywords → URL path fragments that serve that intent.
    # Higher weight = stronger signal.  Checked in order; first match wins
    # a base score of 10, additional keyword hits add +3 each.
    _ENDPOINT_INTENT_KEYWORDS: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
        # (user message keywords, matching URL path fragments)
        (("search", "find", "look for", "discover", "interesting"), ("/search",)),
        (("feed", "timeline", "personali"), ("/feed",)),
        (("thread", "post", "new post", "latest post", "browse", "trending", "hot", "rising", "new thread", "interesting"),
         ("/posts?", "/posts?sort=", "/submolts/")),
        (("submolt", "communit", "subreddit"), ("/submolts",)),
        (("comment", "reply", "replies", "discussion"), ("/comments",)),
        (("notif", "alert", "unread"), ("/notifications", "/home")),
        (("profile", "account", "me", "my info", "karma", "status"), ("/agents/me", "/agents/status")),
        (("follow", "following", "follower"), ("/follow", "/feed?filter=following")),
        (("upvote", "downvote", "vote"), ("/upvote", "/downvote")),
        (("update", "what's new", "whats new", "new on", "latest", "check"), ("/home", "/feed", "/posts")),
    ]

    def _score_endpoint_for_intent(self, url: str, message: str, section_context: str) -> int:
        """Score how well a GET endpoint matches the user's intent.

        Returns 0 for no match (use as fallback only), higher = better match.
        ``section_context`` is the ~300 chars of skill.md text before the curl
        command — typically the markdown heading + description.
        """
        msg_lower = message.lower()
        score = 0

        for keywords, path_fragments in self._ENDPOINT_INTENT_KEYWORDS:
            keyword_hits = sum(1 for kw in keywords if kw in msg_lower)
            if keyword_hits == 0:
                continue
            # Check if this URL matches any of the path fragments for this intent
            url_lower = url.lower()
            for frag in path_fragments:
                if frag.lower() in url_lower:
                    score += 10 + (keyword_hits * 3)
                    break

        # Bonus: section heading keywords that match user message
        if section_context:
            ctx_lower = section_context.lower()
            for word in msg_lower.split():
                if len(word) > 3 and word in ctx_lower:
                    score += 1

        return score

    def _parse_curl_steps(
        self, content: str, message: str, intent: TaskIntent
    ) -> List[Dict[str, Any]]:
        """
        Deterministically extract API calls from curl examples in skill.md-style docs.
        For query actions: scores endpoints against user intent and picks the best matches.
        Returns [{tool, input}] or [] if nothing found.
        """
        # Normalise line continuations so flags/URL land on one logical line
        normalised = re.sub(r"\\\s*\n", " ", content)

        steps: List[Dict[str, Any]] = []
        credential_step_queued = False
        post_count = 0
        _MAX_POST_STEPS = 2  # Cap: registration + one follow-up max
        _MAX_QUERY_GET_STEPS = 2  # Cap GET steps for query actions
        query_only = intent.slots.get("action") == "query"

        # For query actions, collect all candidate GETs with scores, then pick best
        get_candidates: List[Tuple[int, Dict[str, Any]]] = []  # (score, step_dict)
        # For write actions, collect all candidate POSTs with scores, then pick best
        post_candidates: List[Tuple[int, Dict[str, Any]]] = []  # (score, step_dict)
        msg_lower = message.lower()
        _msg_words = set(re.findall(r'\b\w{3,}\b', msg_lower))

        for m in self._CURL_RE.finditer(normalised):
            flags_str = m.group(1)
            url = m.group(2).rstrip(".,;)")

            # Skip documentation-only examples: URLs with unfilled template placeholders
            # like /POST_ID/, /COMMENT_ID/ — these are stubs, not executable endpoints
            if self._UNFILLED_PLACEHOLDER_RE.search(url):
                logger.debug("[TASK_AGENT] Curl parser: skipping stub URL %s", url)
                continue

            # Look for -X METHOD in flags before URL, or anywhere in the window
            window_start = m.start()
            window = normalised[window_start: window_start + 800]
            method_m = self._METHOD_RE.search(flags_str) or self._METHOD_RE.search(window)
            method = method_m.group(1).upper() if method_m else "GET"

            headers: Dict[str, str] = {}

            # Headers may appear before OR after the URL
            for hm in self._HEADER_RE.finditer(window):
                hdr = hm.group(1)
                if ":" in hdr:
                    k, v = hdr.split(":", 1)
                    headers[k.strip()] = v.strip()

            data_m = self._DATA_RE.search(window)
            payload: Optional[Dict[str, Any]] = None
            if data_m:
                raw = data_m.group(1) or data_m.group(2)
                raw = self._fill_placeholders(raw)
                # Skip if payload still has unfilled placeholders after substitution
                if self._UNFILLED_PLACEHOLDER_RE.search(raw):
                    logger.debug("[TASK_AGENT] Curl parser: skipping block with stub payload: %.80s", raw)
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    pass

            expected_fields = self._infer_expected_fields(normalised, m.end())

            if method == "POST":
                # Skip POST steps entirely for query actions
                if query_only:
                    continue

                # Skip registration endpoints if we already have a credential
                # for this service — don't re-register when we already have a key.
                _is_registration = bool(re.search(r"/register|/signup|/enroll", url, re.IGNORECASE))
                if _is_registration:
                    _svc = intent.slots.get("service", "")
                    _cred_key = intent.slots.get("credential_key", "") or f"{_svc}_api_key"
                    _existing = load_credential(_cred_key) if _cred_key else None
                    if _existing:
                        logger.info(
                            "[TASK_AGENT] Curl parser: skipping registration %s — credential %s already exists",
                            url[:80], _cred_key,
                        )
                        continue

                if payload is None:
                    payload = {}
                step_input: Dict[str, Any] = {"url": url, "payload": payload}
                if headers:
                    step_input["headers"] = headers
                if expected_fields:
                    step_input["expected_fields"] = expected_fields

                # Score this POST endpoint against user intent
                # Look back ~500 chars for section context (headers, descriptions)
                context_start = max(0, m.start() - 500)
                context_window = normalised[context_start:m.end()].lower()
                post_score = 0
                for word in _msg_words:
                    if len(word) >= 3 and word in context_window:
                        post_score += 2
                    if len(word) >= 3 and word in url.lower():
                        post_score += 5  # URL match is strongest signal
                post_candidates.append((post_score, {"tool": "http_post", "input": step_input}))

                # Auto-queue a store_credential step for any api_key field in response
                if not credential_step_queued and any(
                    f in expected_fields for f in ("api_key", "token", "access_token")
                ):
                    cred_field = next(
                        (f for f in ("api_key", "token", "access_token") if f in expected_fields),
                        "api_key",
                    )
                    steps.append({
                        "tool": "store_credential",
                        "input": {"key": cred_field, "source_field": cred_field},
                    })
                    credential_step_queued = True

            elif method in ("GET", ""):
                step_input = {"url": url}
                if headers:
                    step_input["headers"] = headers

                if query_only:
                    # Score this endpoint against user intent instead of grabbing blindly
                    # Get ~300 chars before this curl command for section context
                    ctx_start = max(0, m.start() - 300)
                    section_context = normalised[ctx_start: m.start()]
                    user_msg = intent.slots.get("raw_message", message)
                    score = self._score_endpoint_for_intent(url, user_msg, section_context)
                    get_candidates.append((score, {"tool": "http_get_json", "input": step_input}))
                    logger.debug(
                        "[TASK_AGENT] Curl parser: GET candidate score=%d url=%s",
                        score, url[:80],
                    )
                else:
                    steps.append({"tool": "http_get_json", "input": step_input})

        # For query actions, pick the best-scoring GET endpoints
        if query_only and get_candidates:
            # Sort by score descending, deduplicate by URL path, take top N
            get_candidates.sort(key=lambda x: x[0], reverse=True)
            seen_paths: set = set()
            selected: List[Tuple[int, Dict[str, Any]]] = []
            for score, step_dict in get_candidates:
                # Deduplicate by base path (strip query params for comparison)
                url = step_dict["input"].get("url", "")
                base_path = url.split("?")[0]
                if base_path in seen_paths:
                    continue
                seen_paths.add(base_path)
                selected.append((score, step_dict))
                if len(selected) >= _MAX_QUERY_GET_STEPS:
                    break
            for score, step_dict in selected:
                steps.append(step_dict)
                logger.info(
                    "[TASK_AGENT] Curl parser: selected GET (score=%d): %s",
                    score, step_dict["input"].get("url", "")[:80],
                )

        # For write actions, pick the best-scoring POST endpoints
        if not query_only and post_candidates:
            post_candidates.sort(key=lambda x: x[0], reverse=True)
            seen_paths_post: set = set()
            for score, step_dict in post_candidates:
                url = step_dict["input"].get("url", "")
                base_path = url.split("?")[0]
                if base_path in seen_paths_post:
                    continue
                seen_paths_post.add(base_path)
                steps.append(step_dict)
                logger.info(
                    "[TASK_AGENT] Curl parser: selected POST (score=%d): %s",
                    score, step_dict["input"].get("url", "")[:80],
                )
                if len([s for s in steps if s["tool"] == "http_post"]) >= _MAX_POST_STEPS:
                    break

        logger.info("[TASK_AGENT] Curl parser found %d steps", len(steps))
        return steps

    def _replan_from_content(
        self,
        content: str,
        message: str,
        intent: TaskIntent,
    ) -> List[Dict[str, Any]]:
        """
        Read fetched content + user goal → concrete list of tool calls.
        Primary: deterministic curl-command parser (no LLM required).
        Fallback: native tool-calling via chat_with_tools (LLM).
        Returns [] so the caller can skip phase 2 gracefully.
        """
        # ── Primary: curl parser (deterministic, no hallucination risk) ───
        curl_steps = self._parse_curl_steps(content, message, intent)
        if curl_steps:
            return curl_steps

        # ── Fallback: LLM tool-calling ────────────────────────────────────
        if self._llm is None:
            return []
        if not hasattr(self._llm, "chat_with_tools"):
            return []

        # 8000 chars — enough to capture API endpoint docs past the intro/TOC
        snippet = content[:8000]
        url = intent.slots.get("url", "")

        system = (
            "You are a planning agent. Read the document and determine what API calls "
            "are needed to complete the user's goal. Call the appropriate tools in order. "
            "Use store_credential with source_field to save any API keys or tokens returned "
            "by a previous step's response."
        )
        user = (
            f"Goal: {message}\n\n"
            f"Document from {url}:\n{snippet}"
        )

        try:
            result = self._llm.chat_with_tools(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=self._TOOL_SCHEMAS,
                max_tokens=800,
                temperature=0.0,
            )

            tool_calls = result.get("tool_calls", [])
            logger.debug("[TASK_AGENT] Re-plan tool_calls: %s", tool_calls)

            if not tool_calls:
                logger.warning("[TASK_AGENT] Re-plan: no tool calls returned (content: %.200s)", result.get("content", ""))
                return []

            # Convert tool_calls → plan format {tool, input}
            validated: List[Dict[str, Any]] = []
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                if name not in self._VALID_TOOLS:
                    logger.debug("[TASK_AGENT] Re-plan: skipping unknown tool %r", name)
                    continue
                if not isinstance(args, dict):
                    continue
                validated.append({"tool": name, "input": args})

            logger.info("[TASK_AGENT] Phase-2 plan via tool-calling: %d steps", len(validated))
            return validated

        except Exception as e:
            logger.warning("[TASK_AGENT] Re-plan failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Plan builder
    # ------------------------------------------------------------------

    def _build_plan(
        self,
        intent: TaskIntent,
        message: str,
        active_task: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []

        if intent.intent_type == "system_info":
            plan.append({"tool": "system_info", "input": {}})

        elif intent.intent_type == "file_read":
            path = intent.slots.get("path", "")
            plan.append({"tool": "file_read", "input": {"path": path}})

        elif intent.intent_type == "dir_list":
            path = intent.slots.get("path", "D:/AI_round2")
            plan.append({"tool": "dir_list", "input": {"path": path}})

        elif intent.intent_type == "project_scan":
            path = intent.slots.get("path", "D:/AI_round2")
            plan.append({"tool": "project_scan", "input": {"path": path}})

        elif intent.intent_type == "url_fetch":
            url = intent.slots.get("url")
            if url:
                plan.append({"tool": "fetch_url", "input": {"url": url}})
            # follow_instructions: phase 2 plan is built AFTER fetch, from content
            # No execute_instructions placeholder — that was a phantom step

        elif intent.intent_type == "skill_install":
            url = intent.slots.get("url")
            if url:
                plan.append({"tool": "fetch_url", "input": {"url": url}})
                plan.append({"tool": "install_skill", "input": {"url": url}})

        elif intent.intent_type == "imperative_task":
            api_key = intent.slots.get("api_key")
            if api_key:
                # Infer the credential key name from the key value or message.
                # Keys like "moltbook_sk_..." should store as "moltbook_api_key"
                # so _get_known_services() can discover them.
                cred_key = "api_key"
                for svc_name in list(_KNOWN_SERVICES.keys()):
                    if api_key.lower().startswith(f"{svc_name}_") or svc_name in message.lower():
                        cred_key = f"{svc_name}_api_key"
                        break
                plan.append({
                    "tool": "store_credential",
                    "input": {"key": cred_key, "value": api_key, "raw": message},
                })
            else:
                plan.append({"tool": "llm_respond", "input": {"message": message}})

        elif intent.intent_type == "service_action":
            service = intent.slots.get("service", "")
            action = intent.slots.get("action", "query")  # "write" or "query"

            # Cascade: credential store → local cache → _KNOWN_SERVICES → _no_endpoint
            # 1. Try credential store for skill URL
            skill_url_key = intent.slots.get("skill_url_key", "")
            skill_url = load_credential(skill_url_key) if skill_url_key else None
            if not skill_url:
                skill_url = load_credential(f"{service}_skill_url")

            if skill_url:
                # Stored skill URL — fetch it for re-planning
                plan.append({"tool": "fetch_url", "input": {"url": skill_url}})
                intent.slots["url"] = skill_url
                if action == "write":
                    intent.slots["action"] = "follow_instructions"
            elif _load_cached_skill(service):
                # 2. Local skill cache — read from disk, replan from cached content
                plan.append({"tool": "load_cached_skill", "input": {"service": service}})
            else:
                # 3. Try _KNOWN_SERVICES for skill URL
                known = _KNOWN_SERVICES.get(service)
                if known and known.get("skill_url"):
                    plan.append({"tool": "fetch_url", "input": {"url": known["skill_url"]}})
                    intent.slots["url"] = known["skill_url"]
                    if action == "write":
                        intent.slots["action"] = "follow_instructions"
                else:
                    # 4. Try credential store or _KNOWN_SERVICES for API base
                    api_base_key = intent.slots.get("api_base_key", "")
                    api_base = load_credential(api_base_key) if api_base_key else None
                    if not api_base:
                        api_base = load_credential(f"{service}_api_base")
                    if not api_base and known:
                        api_base = known.get("api_base")

                    if api_base:
                        plan.append({"tool": "http_get_json", "input": {"url": api_base}})
                    else:
                        # No endpoint metadata — deterministic answer
                        intent.slots["_no_endpoint"] = True

        elif intent.intent_type == "task_continuation":
            at = intent.slots.get("active_task") or active_task or {}
            api_key = intent.slots.get("api_key")
            if api_key:
                plan.append({
                    "tool": "store_credential",
                    "input": {"key": at.get("credential_key", "api_key"), "value": api_key},
                })
            pending_steps = at.get("steps_pending", [])
            if pending_steps:
                plan.extend(pending_steps[:3])  # pick up where we left off
            if not plan:
                plan.append({"tool": "llm_respond", "input": {"message": message, "context": at}})

        if not plan:
            plan.append({"tool": "llm_respond", "input": {"message": message}})

        return plan

    # ------------------------------------------------------------------
    # Credential injection for API calls
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_credentials(
        inp: Dict[str, Any],
        task_context: Optional[Dict[str, Any]],
        thread_id: str,
    ) -> None:
        """Replace YOUR_API_KEY placeholders in headers with stored credentials.

        Also adds an Authorization header if the service has a stored credential
        but the step has no auth header.
        """
        ctx = task_context or {}
        service = ctx.get("_service", "")
        cred_key = ctx.get("_credential_key", "") or f"{service}_api_key"
        if not cred_key:
            return

        headers = inp.get("headers")
        if not headers:
            headers = {}
            inp["headers"] = headers

        # Replace placeholder values in existing headers
        cred_value: Optional[str] = None
        for k, v in list(headers.items()):
            if "YOUR_API_KEY" in v or "YOUR_TOKEN" in v:
                if cred_value is None:
                    cred_value = load_credential(cred_key, thread_id)
                if cred_value:
                    headers[k] = v.replace("YOUR_API_KEY", cred_value).replace("YOUR_TOKEN", cred_value)

        # Add Authorization header if none present
        if "Authorization" not in headers:
            if cred_value is None:
                cred_value = load_credential(cred_key, thread_id)
            if cred_value:
                headers["Authorization"] = f"Bearer {cred_value}"

    # ------------------------------------------------------------------
    # Step executor with verification + retry (1.2)
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: AgentStep,
        tool: str,
        inp: Dict[str, Any],
        thread_id: str,
        step_index: int,
        fetched_content: Optional[str] = None,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """Execute one step, verify result, retry once on failure. Yields nothing, returns the result event."""

        if tool == "fetch_url":
            return (yield from self._run_fetch_url(step, inp, step_index))

        elif tool == "http_post":
            self._inject_credentials(inp, task_context, thread_id)
            return (yield from self._run_http_post(step, inp, step_index))

        elif tool == "http_get_json":
            self._inject_credentials(inp, task_context, thread_id)
            return (yield from self._run_http_get_json(step, inp, step_index))

        elif tool == "load_cached_skill":
            return self._run_load_cached_skill(step, inp, step_index)

        elif tool == "install_skill":
            return self._run_install_skill(step, inp, step_index, thread_id, task_context=task_context)

        elif tool == "store_credential":
            # _run_store_credential is not a generator — call directly and return as generator value
            return self._run_store_credential(step, inp, step_index, thread_id, task_context=task_context)

        elif tool == "system_info":
            return self._run_system_info(step, inp, step_index)

        elif tool == "file_read":
            return self._run_file_read(step, inp, step_index)

        elif tool == "dir_list":
            return self._run_dir_list(step, inp, step_index)

        elif tool == "project_scan":
            return self._run_project_scan(step, inp, step_index)

        else:
            # execute_instructions / llm_respond — resolved in LLM call
            step.status = "queued"
            return {
                "type": "tool_result",
                "content": "→ queued for LLM",
                "metadata": {"tool_name": tool, "status": "queued", "step_index": step_index},
            }

    def _run_fetch_url(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        url = inp.get("url", "")
        for attempt in range(2):  # one retry
            try:
                status, text, byte_count, duration_ms = _http_get(url)
                ok, reason = _verify_response(status, text)
                if ok:
                    step.output = text
                    step.output_preview = text[:500]
                    step.byte_count = byte_count
                    step.duration_ms = duration_ms
                    step.status = "ok"
                    step.verified = True
                    return {
                        "type": "tool_result",
                        "content": f"✓ {byte_count:,} bytes  {duration_ms:.0f}ms",
                        "metadata": {
                            "tool_name": "fetch_url",
                            "output_preview": step.output_preview,
                            "byte_count": byte_count,
                            "duration_ms": duration_ms,
                            "status": "ok",
                            "verified": True,
                            "step_index": step_index,
                        },
                    }
                else:
                    if attempt == 0:
                        yield {"type": "status", "content": f"retrying — {reason}"}
                        continue
                    step.status = "error"
                    step.error = reason
            except Exception as e:
                if attempt == 0:
                    yield {"type": "status", "content": f"retrying — {e}"}
                    continue
                step.status = "error"
                step.error = str(e)

        logger.warning("[TASK_AGENT] fetch_url failed after retry: %s", step.error)
        return {
            "type": "tool_result",
            "content": f"✗ {step.error}",
            "metadata": {"tool_name": "fetch_url", "status": "error", "error": step.error, "step_index": step_index},
        }

    def _run_http_post(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        url = inp.get("url", "")
        payload = inp.get("payload", {})
        headers = inp.get("headers")
        expected = inp.get("expected_fields")

        for attempt in range(2):
            try:
                status, body, duration_ms = _http_post(url, payload, headers)
                ok, reason = _verify_response(status, body, expected)
                if ok:
                    extracted = _extract_key_fields(body)
                    step.output = body
                    step.output_preview = json.dumps(body)[:500]
                    step.duration_ms = duration_ms
                    step.status = "ok"
                    step.verified = True
                    step.extracted_fields = extracted
                    return {
                        "type": "tool_result",
                        "content": f"✓ HTTP {status}  {duration_ms:.0f}ms" + (f"  keys: {list(extracted.keys())}" if extracted else ""),
                        "metadata": {
                            "tool_name": "http_post",
                            "output_preview": step.output_preview,
                            "extracted_fields": extracted,
                            "duration_ms": duration_ms,
                            "status_code": status,
                            "status": "ok",
                            "verified": True,
                            "step_index": step_index,
                        },
                    }
                else:
                    # Don't retry on 4xx client errors — they won't resolve on retry
                    if attempt == 0 and (status >= 500 or status == 0):
                        yield {"type": "status", "content": f"retrying POST — {reason}"}
                        continue
                    step.status = "error"
                    step.error = reason
                    break
            except Exception as e:
                if attempt == 0:
                    yield {"type": "status", "content": f"retrying POST — {e}"}
                    continue
                step.status = "error"
                step.error = str(e)

        return {
            "type": "tool_result",
            "content": f"✗ POST failed: {step.error}",
            "metadata": {"tool_name": "http_post", "status": "error", "error": step.error, "step_index": step_index},
        }

    def _run_http_get_json(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        url = inp.get("url", "")
        headers = inp.get("headers")
        for attempt in range(2):
            try:
                status, body, duration_ms = _http_get_json(url, headers)
                ok, reason = _verify_response(status, body)
                if ok:
                    extracted = _extract_key_fields(body)
                    step.output = body
                    step.output_preview = json.dumps(body)[:500]
                    step.duration_ms = duration_ms
                    step.status = "ok"
                    step.verified = True
                    step.extracted_fields = extracted
                    return {
                        "type": "tool_result",
                        "content": f"✓ HTTP {status}  {duration_ms:.0f}ms",
                        "metadata": {
                            "tool_name": "http_get_json",
                            "output_preview": step.output_preview,
                            "extracted_fields": extracted,
                            "status": "ok",
                            "verified": True,
                            "step_index": step_index,
                        },
                    }
                else:
                    if attempt == 0:
                        yield {"type": "status", "content": f"retrying GET — {reason}"}
                        continue
                    step.status = "error"
                    step.error = reason
            except Exception as e:
                if attempt == 0:
                    yield {"type": "status", "content": f"retrying GET — {e}"}
                    continue
                step.status = "error"
                step.error = str(e)

        return {
            "type": "tool_result",
            "content": f"✗ GET failed: {step.error}",
            "metadata": {"tool_name": "http_get_json", "status": "error", "error": step.error, "step_index": step_index},
        }

    def _run_load_cached_skill(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int,
    ) -> Dict[str, Any]:
        """Read a locally cached SKILL.md file."""
        service = inp.get("service", "")
        content = _load_cached_skill(service)
        if content:
            step.output = content
            step.output_preview = content[:500]
            step.status = "ok"
            step.verified = True
            return {
                "type": "tool_result",
                "content": f"✓ loaded cached skill for {service} ({len(content)} bytes)",
                "metadata": {
                    "tool_name": "load_cached_skill",
                    "service": service,
                    "byte_count": len(content),
                    "status": "ok",
                    "step_index": step_index,
                },
            }
        step.status = "error"
        step.error = f"no cached skill file for {service}"
        return {
            "type": "tool_result",
            "content": f"✗ no cached skill for {service}",
            "metadata": {"tool_name": "load_cached_skill", "status": "error", "step_index": step_index},
        }

    def _run_install_skill(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int, thread_id: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Install a skill from fetched content: parse frontmatter, save locally, register service."""
        url = inp.get("url", "")

        # The fetched content comes from the prior fetch_url step via task_context
        fetched_content = (task_context or {}).get("_fetched_content", "")

        if not fetched_content:
            step.status = "error"
            step.error = "no fetched content to install"
            return {
                "type": "tool_result",
                "content": "✗ no fetched content — fetch_url must run first",
                "metadata": {"tool_name": "install_skill", "status": "error", "step_index": step_index},
            }

        # Parse YAML frontmatter
        name = ""
        api_base = ""
        credential_key = ""
        description = ""
        if fetched_content.startswith("---"):
            parts = fetched_content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                try:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict):
                        name = fm.get("name", "")
                        description = fm.get("description", "")
                        meta = fm.get("metadata", "")
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except Exception:
                                meta = {}
                        if isinstance(meta, dict):
                            api_base = meta.get("api_base", "")
                except Exception:
                    pass

        if not name:
            # Try to infer from URL: https://example.com/skill.md → "example"
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            name = hostname.replace("www.", "").split(".")[0] if hostname else "unknown_skill"

        # Default credential key from name
        credential_key = f"{name}_api_key"

        # Save to local cache
        _cache_skill_content(name, fetched_content)

        # Register in _KNOWN_SERVICES (runtime only — persists via credential store)
        _KNOWN_SERVICES[name] = {
            "skill_url": url,
            "api_base": api_base,
            "credential_key": credential_key,
        }
        # Rebuild the regex to include the new service
        global _KNOWN_SERVICE_RE
        _KNOWN_SERVICE_RE = re.compile(
            r"\b(" + "|".join(re.escape(s) for s in _KNOWN_SERVICES) + r")\b",
            re.IGNORECASE,
        )

        # Store skill URL and api_base in credential store for persistence across restarts
        store_credential(f"{name}_skill_url", url, thread_id)
        if api_base:
            store_credential(f"{name}_api_base", api_base, thread_id)

        step.output = f"Installed skill '{name}' from {url}"
        step.output_preview = f"name={name}, api_base={api_base}, credential_key={credential_key}"
        step.status = "ok"
        step.verified = True

        logger.info("[SKILL_INSTALL] Installed '%s' from %s (api_base=%s)", name, url, api_base)

        return {
            "type": "tool_result",
            "content": f"✓ Installed skill '{name}' — saved to data/managed_skills/{name}/SKILL.md",
            "metadata": {
                "tool_name": "install_skill",
                "service_name": name,
                "description": description,
                "api_base": api_base,
                "credential_key": credential_key,
                "skill_url": url,
                "status": "ok",
                "step_index": step_index,
                "needs_api_key": True,
            },
        }

    def _run_store_credential(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int, thread_id: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        key = inp.get("key", "api_key")
        value = inp.get("value", "")
        # source_field: pull value from a previous step's extracted response field
        source_field = inp.get("source_field")
        if not value and source_field and task_context:
            value = str(task_context.get(source_field, ""))
        if not value:
            step.status = "error"
            step.error = "no value to store"
            return {
                "type": "tool_result",
                "content": "✗ no value to store",
                "metadata": {"tool_name": "store_credential", "status": "error", "step_index": step_index},
            }
        try:
            path = store_credential(key, value, thread_id)
            step.output = path
            step.output_preview = f"stored {key} to {path}"
            step.status = "ok"
            step.verified = True
            step.extracted_fields = {key: value}

            # Auto-store service metadata alongside credentials.
            # If key looks like {service}_api_key and we have task context with
            # a source URL, store {service}_skill_url and {service}_api_base
            # so future service_action intents can resolve endpoints.
            for suffix in ("_api_key", "_token", "_secret"):
                if key.endswith(suffix):
                    svc = key[: -len(suffix)]
                    if svc and task_context:
                        source_url = task_context.get("source_url") or ""
                        if source_url:
                            try:
                                store_credential(f"{svc}_skill_url", source_url, thread_id)
                            except Exception:
                                pass
                            # Derive API base from skill URL (strip /skill.md → /api/v1)
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(source_url)
                                api_base = f"{parsed.scheme}://{parsed.netloc}/api/v1"
                                store_credential(f"{svc}_api_base", api_base, thread_id)
                            except Exception:
                                pass
                    break

            return {
                "type": "tool_result",
                "content": f"✓ stored {key}",
                "metadata": {
                    "tool_name": "store_credential",
                    "key": key,
                    "path": path,
                    "status": "ok",
                    "verified": True,
                    "step_index": step_index,
                },
            }
        except Exception as e:
            step.status = "error"
            step.error = str(e)
            return {
                "type": "tool_result",
                "content": f"✗ store failed: {e}",
                "metadata": {"tool_name": "store_credential", "status": "error", "error": str(e), "step_index": step_index},
            }

    # ------------------------------------------------------------------
    # System info tool (Layer 1 — read-only)
    # ------------------------------------------------------------------

    def _run_system_info(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int,
    ) -> Dict[str, Any]:
        """Collect system snapshot and return formatted text for LLM."""
        import time as _time
        t0 = _time.time()
        try:
            from personal_agent.system_info import get_system_snapshot, format_snapshot_text
            snapshot = get_system_snapshot()
            text = format_snapshot_text(snapshot)
            duration_ms = round((_time.time() - t0) * 1000)

            step.output = snapshot
            step.output_preview = text[:500]
            step.byte_count = len(text)
            step.duration_ms = duration_ms
            step.status = "ok"
            step.verified = True

            logger.info("[SYSTEM_INFO] Tool returned %d chars in %dms", len(text), duration_ms)
            return {
                "type": "tool_result",
                "content": text,
                "metadata": {
                    "tool_name": "system_info",
                    "output_preview": step.output_preview,
                    "byte_count": len(text),
                    "duration_ms": duration_ms,
                    "status": "ok",
                    "verified": True,
                    "step_index": step_index,
                    "snapshot": snapshot,
                },
            }
        except Exception as e:
            logger.warning("[SYSTEM_INFO] Failed: %s", e)
            step.status = "error"
            step.error = str(e)
            return {
                "type": "tool_result",
                "content": f"✗ system info failed: {e}",
                "metadata": {"tool_name": "system_info", "status": "error", "error": str(e), "step_index": step_index},
            }

    # ------------------------------------------------------------------
    # File tools (Layer 2 — read-only)
    # ------------------------------------------------------------------

    def _run_file_read(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int,
    ) -> Dict[str, Any]:
        """Read a file and return its content for LLM."""
        try:
            from personal_agent.file_tools import read_file, format_file_result
            result = read_file(inp.get("path", ""))
            text = format_file_result(result)
            has_error = "error" in result

            step.output = result
            step.output_preview = text[:500]
            step.byte_count = len(text)
            step.status = "error" if has_error else "ok"
            step.error = result.get("error") if has_error else None
            step.verified = not has_error

            logger.info("[FILE_TOOLS] file_read %s — %s", inp.get("path"), step.status)
            return {
                "type": "tool_result",
                "content": text,
                "metadata": {
                    "tool_name": "file_read",
                    "status": step.status,
                    "step_index": step_index,
                    **({"error": step.error} if step.error else {}),
                },
            }
        except Exception as e:
            logger.warning("[FILE_TOOLS] file_read failed: %s", e)
            step.status = "error"
            step.error = str(e)
            return {
                "type": "tool_result",
                "content": f"✗ file read failed: {e}",
                "metadata": {"tool_name": "file_read", "status": "error", "error": str(e), "step_index": step_index},
            }

    def _run_dir_list(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int,
    ) -> Dict[str, Any]:
        """List a directory and return formatted result for LLM."""
        try:
            from personal_agent.file_tools import list_directory, format_dir_result
            result = list_directory(inp.get("path", ""))
            text = format_dir_result(result)
            has_error = "error" in result

            step.output = result
            step.output_preview = text[:500]
            step.byte_count = len(text)
            step.status = "error" if has_error else "ok"
            step.error = result.get("error") if has_error else None
            step.verified = not has_error

            logger.info("[FILE_TOOLS] dir_list %s — %s", inp.get("path"), step.status)
            return {
                "type": "tool_result",
                "content": text,
                "metadata": {
                    "tool_name": "dir_list",
                    "status": step.status,
                    "step_index": step_index,
                    **({"error": step.error} if step.error else {}),
                },
            }
        except Exception as e:
            logger.warning("[FILE_TOOLS] dir_list failed: %s", e)
            step.status = "error"
            step.error = str(e)
            return {
                "type": "tool_result",
                "content": f"✗ dir list failed: {e}",
                "metadata": {"tool_name": "dir_list", "status": "error", "error": str(e), "step_index": step_index},
            }

    def _run_project_scan(
        self, step: AgentStep, inp: Dict[str, Any], step_index: int,
    ) -> Dict[str, Any]:
        """Scan a project and return formatted result for LLM."""
        try:
            from personal_agent.file_tools import scan_project, format_project_result
            result = scan_project(inp.get("path", ""))
            text = format_project_result(result)
            has_error = "error" in result

            step.output = result
            step.output_preview = text[:500]
            step.byte_count = len(text)
            step.status = "error" if has_error else "ok"
            step.error = result.get("error") if has_error else None
            step.verified = not has_error

            logger.info("[FILE_TOOLS] project_scan %s — %s", inp.get("path"), step.status)
            return {
                "type": "tool_result",
                "content": text,
                "metadata": {
                    "tool_name": "project_scan",
                    "status": step.status,
                    "step_index": step_index,
                    **({"error": step.error} if step.error else {}),
                },
            }
        except Exception as e:
            logger.warning("[FILE_TOOLS] project_scan failed: %s", e)
            step.status = "error"
            step.error = str(e)
            return {
                "type": "tool_result",
                "content": f"✗ project scan failed: {e}",
                "metadata": {"tool_name": "project_scan", "status": "error", "error": str(e), "step_index": step_index},
            }

    # ------------------------------------------------------------------
    # Task state persistence (1.4)
    # ------------------------------------------------------------------

    def _persist_task_state(
        self,
        thread_id: str,
        intent: TaskIntent,
        steps: List[AgentStep],
        task_context: Dict[str, Any],
        stored_credentials: Dict[str, str],
    ) -> None:
        if self._session_db is None:
            return
        try:
            failed_steps = [s for s in steps if s.status == "error"]
            pending = [s.to_dict() for s in failed_steps]
            status = "completed" if not failed_steps else "partial"
            self._session_db.set_pending_task(thread_id, {
                "intent_type": intent.intent_type,
                "status": status,
                "steps_completed": [s.to_dict() for s in steps if s.status == "ok"],
                "steps_pending": pending,
                "context": task_context,
                "credential_keys": list(stored_credentials.keys()),
            })
        except Exception as e:
            logger.warning("[TASK_AGENT] Failed to persist task state: %s", e)

    # ------------------------------------------------------------------
    # Answer generation — streaming with <think> routing
    # ------------------------------------------------------------------

    def _stream_generate_answer(
        self,
        message: str,
        fetched_content: Optional[str],
        intent: TaskIntent,
        steps: List[AgentStep],
        stored_credentials: Dict[str, str],
        active_task: Optional[Dict[str, Any]],
    ) -> Generator[Dict[str, Any], None, str]:
        """
        Stream the answer, routing thinking tokens to agent_thinking_token events
        and content tokens to token events. Returns the full answer string.
        """
        if self._llm is None or not hasattr(self._llm, "chat_stream"):
            answer = self._generate_answer(
                message, fetched_content, intent, steps, stored_credentials, active_task
            )
            yield {"type": "token", "content": answer}
            return answer

        context_block = self._build_answer_context(
            fetched_content, intent, steps, stored_credentials, active_task
        )
        system_prompt = (
            "You are Aether. Report what actually happened based on the tool results below.\n"
            "RULES:\n"
            "- 2-4 sentences max. Start with the answer immediately.\n"
            "- Only state outcomes that are in the verified results.\n"
            "- If something failed, say so.\n"
            "- Do NOT include meta-reasoning about sufficiency, next steps, or whether more data is needed.\n"
            "- Do NOT start with 'The information shows', 'Based on the data', 'The results indicate'.\n"
            "- Put ALL reasoning in <think> tags. Everything outside <think> is shown verbatim to the user."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{message}\n\n{context_block}".strip()},
        ]

        thinking_buf = ""
        content_buf = ""
        thinking_start = time.time()

        # Use the fast model for answer generation — reasoning models are too
        # slow for simple "summarise these API results" tasks and cause timeouts.
        fast_model = os.getenv("CRT_MODEL_FAST") or "role:fast"

        # Reasoning prefixes that should be routed to thinking, not content.
        # The model sometimes outputs meta-reasoning outside <think> tags.
        _REASONING_PREFIXES = (
            "the information from",
            "the results show",
            "the data indicates",
            "based on the",
            "this suggests",
            "no further tool",
            "no specific request",
            "since the user",
            "i've explored",
            "i have enough",
            "the search returned",
            "let me ",
        )
        # Buffer initial content to detect reasoning paragraphs
        content_line_buf = ""
        first_content_emitted = False

        try:
            for tok_type, text in self._llm.chat_stream(
                messages, max_tokens=800, temperature=0.3, model=fast_model,
            ):
                if tok_type == "thinking":
                    thinking_buf += text
                    yield {"type": "agent_thinking_token", "content": text,
                           "metadata": {"step": "generate_answer"}}
                else:
                    if not first_content_emitted:
                        # Buffer content until we see a newline or enough text
                        content_line_buf += text
                        # Check if we have a full first line/paragraph
                        if "\n" in content_line_buf or len(content_line_buf) > 200:
                            first_line = content_line_buf.split("\n")[0].strip().lower()
                            if any(first_line.startswith(p) for p in _REASONING_PREFIXES):
                                # Route the reasoning paragraph to thinking
                                para_end = content_line_buf.find("\n\n")
                                if para_end != -1:
                                    reasoning_part = content_line_buf[:para_end]
                                    remaining = content_line_buf[para_end + 2:]
                                    thinking_buf += reasoning_part
                                    yield {"type": "agent_thinking_token",
                                           "content": reasoning_part,
                                           "metadata": {"step": "generate_answer"}}
                                    if remaining.strip():
                                        content_buf += remaining
                                        yield {"type": "token", "content": remaining}
                                    first_content_emitted = True
                                else:
                                    # Whole buffer is reasoning, redirect it all
                                    thinking_buf += content_line_buf
                                    yield {"type": "agent_thinking_token",
                                           "content": content_line_buf,
                                           "metadata": {"step": "generate_answer"}}
                                    first_content_emitted = True
                                content_line_buf = ""
                            else:
                                # Not reasoning — flush buffer as content
                                content_buf += content_line_buf
                                yield {"type": "token", "content": content_line_buf}
                                first_content_emitted = True
                                content_line_buf = ""
                    else:
                        content_buf += text
                        yield {"type": "token", "content": text}

            # Flush any remaining buffered content
            if content_line_buf:
                first_line = content_line_buf.strip().lower()
                if any(first_line.startswith(p) for p in _REASONING_PREFIXES):
                    thinking_buf += content_line_buf
                    yield {"type": "agent_thinking_token",
                           "content": content_line_buf,
                           "metadata": {"step": "generate_answer"}}
                else:
                    content_buf += content_line_buf
                    yield {"type": "token", "content": content_line_buf}

            if thinking_buf:
                thinking_ms = int((time.time() - thinking_start) * 1000)
                logger.debug("[TASK_AGENT] Answer thinking: %dms, %d chars", thinking_ms, len(thinking_buf))

            return content_buf.strip() or "[No answer generated]"

        except Exception as e:
            logger.warning("[TASK_AGENT] Stream answer failed: %s", e)
            fallback = self._generate_answer(
                message, fetched_content, intent, steps, stored_credentials, active_task
            )
            yield {"type": "token", "content": fallback}
            return fallback

    def _build_answer_context(
        self,
        fetched_content: Optional[str],
        intent: TaskIntent,
        steps: List[AgentStep],
        stored_credentials: Dict[str, str],
        active_task: Optional[Dict[str, Any]],
    ) -> str:
        """Build the context block shared by both streaming and blocking answer generation."""
        context_parts: List[str] = []
        action = intent.slots.get("action", "")
        has_execution_steps = any(
            s.tool_name in ("http_post", "http_get_json", "store_credential") for s in steps
        )
        if fetched_content and action != "follow_instructions":
            # Plain fetch (no instruction execution) — include content summary
            url = intent.slots.get("url", "URL")
            context_parts.append(f"[Content fetched from {url}]\n{fetched_content[:4000]}\n[End]")
        elif fetched_content and action == "follow_instructions" and has_execution_steps:
            # Instructions were fetched and executed — just note the source, not the full content
            url = intent.slots.get("url", "URL")
            context_parts.append(f"[Instructions fetched from {url} and executed — see step results below]")
        elif fetched_content and action == "follow_instructions" and not has_execution_steps:
            context_parts.append(
                "[Note: Instructions were fetched but could not be parsed into executable steps. "
                "Do not claim the task was completed.]"
            )
        # Include verified extracted fields
        verified_steps = [s for s in steps if s.verified and s.extracted_fields]
        if verified_steps:
            real_data: Dict[str, Any] = {}
            for s in verified_steps:
                real_data.update(s.extracted_fields)
            context_parts.append(f"[Verified API response fields]\n{json.dumps(real_data, indent=2)}\n[End]")
        # Include actual API response data from successful http_get_json / http_post steps
        # even when extracted_fields is empty — the raw response IS the useful data
        api_steps = [
            s for s in steps
            if s.tool_name in ("http_get_json", "http_post")
            and s.status == "ok"
            and s not in verified_steps  # avoid double-counting
        ]
        if api_steps:
            for s in api_steps:
                preview = s.output_preview or (s.output[:2000] if isinstance(s.output, str) else "")
                if preview:
                    context_parts.append(
                        f"[API response from {s.input.get('url', 'unknown')}]\n{preview}\n[End]"
                    )
        failed_steps = [s for s in steps if s.status == "error"]
        if failed_steps:
            failures = "\n".join(f"- {s.tool_name}: {s.error}" for s in failed_steps)
            context_parts.append(f"[Steps that failed — do not claim success for these]\n{failures}\n[End]")
        if active_task:
            context_parts.append(
                f"[Continuing task: {active_task.get('intent_type', 'unknown')}]\n"
                f"{json.dumps(active_task.get('context', {}), indent=2)}\n[End]"
            )
        return "\n\n".join(context_parts)

    # ------------------------------------------------------------------
    # Reasoning filter for tool loop output
    # ------------------------------------------------------------------

    _TOOL_LOOP_REASONING_PREFIXES = (
        "i have enough",
        "the information from",
        "the results show",
        "the data indicates",
        "the current results",
        "the initial tool call",
        "the dashboard data",
        "based on the",
        "this suggests",
        "this fulfills",
        "no further tool",
        "no specific request",
        "since the user",
        "since no specific",
        "i've explored",
        "i've retrieved",
        "the search returned",
        "additional tool calls",
        "with the provided data",
        "let me ",
        "no further tool calls",
        "the api documentation",
        "i'll summarize",
        "i will summarize",
    )

    def _filter_reasoning_from_content(self, text: str) -> str:
        """Strip internal reasoning paragraphs from tool loop output.

        The LLM often produces meta-reasoning like:
          "I have enough information to answer the user's question..."
          "The initial tool call provided a comprehensive overview..."
          "This fulfills the goal of checking..."
          "Final summary: <actual useful content>"

        This method keeps only the user-facing content.
        """
        if not text or not text.strip():
            return text

        paragraphs = text.split("\n\n")
        kept = []
        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                continue
            first_line = stripped.lower()
            # Check for "Final summary:" prefix — extract just the content after it
            if first_line.startswith("final summary:"):
                kept.append(stripped[len("final summary:"):].strip())
                continue
            # Skip reasoning paragraphs
            if any(first_line.startswith(p) for p in self._TOOL_LOOP_REASONING_PREFIXES):
                logger.debug("[REASONING_FILTER] Stripped: %s", stripped[:80])
                continue
            kept.append(stripped)

        result = "\n\n".join(kept).strip()
        if not result:
            # Everything was reasoning — fall back to the last paragraph
            # (usually the most useful content)
            result = paragraphs[-1].strip() if paragraphs else text
        return result

    # ------------------------------------------------------------------

    def _generate_answer(
        self,
        message: str,
        fetched_content: Optional[str],
        intent: TaskIntent,
        steps: List[AgentStep],
        stored_credentials: Dict[str, str],
        active_task: Optional[Dict[str, Any]],
    ) -> str:
        context_block = self._build_answer_context(
            fetched_content, intent, steps, stored_credentials, active_task
        )

        if self._llm is None:
            return self._no_llm_answer(fetched_content, intent, steps, stored_credentials)

        system_prompt = (
            "You are Aether. Report what actually happened based on the tool results below.\n"
            "RULES:\n"
            "- 2-4 sentences max. Start with the answer immediately.\n"
            "- Only state outcomes that are in the verified results.\n"
            "- If something failed, say so.\n"
            "- Do NOT include meta-reasoning about sufficiency, next steps, or whether more data is needed.\n"
            "- Do NOT start with 'The information shows', 'Based on the data', 'The results indicate'.\n"
            "- Put ALL reasoning in <think> tags. Everything outside <think> is shown verbatim to the user."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{message}\n\n{context_block}".strip()},
        ]
        # Use fast model for answer summarisation — reasoning models timeout
        fast_model = os.getenv("CRT_MODEL_FAST") or "role:fast"
        try:
            return self._llm.chat(messages, max_tokens=800, temperature=0.3, model=fast_model)
        except Exception as e:
            logger.warning("[TASK_AGENT] LLM call failed: %s", e)
            return self._no_llm_answer(fetched_content, intent, steps, stored_credentials)

    def _no_llm_answer(
        self,
        fetched_content: Optional[str],
        intent: TaskIntent,
        steps: List[AgentStep],
        stored_credentials: Dict[str, str],
    ) -> str:
        parts: List[str] = []
        ok_steps = [s for s in steps if s.status == "ok"]
        fail_steps = [s for s in steps if s.status == "error"]

        if ok_steps:
            parts.append(f"Completed {len(ok_steps)} step(s): {', '.join(s.tool_name for s in ok_steps)}")
        if stored_credentials:
            parts.append(f"Stored credentials: {', '.join(stored_credentials.keys())}")
        if fail_steps:
            parts.append(f"Failed: {', '.join(f'{s.tool_name} ({s.error})' for s in fail_steps)}")
        if fetched_content and not parts:
            url = intent.slots.get("url", "URL")
            parts.append(f"Fetched {url}:\n\n{fetched_content[:2000]}")

        return "\n".join(parts) if parts else "Task completed."

    # ------------------------------------------------------------------
    # CRT memory write-back
    # ------------------------------------------------------------------

    def _write_facts(
        self,
        thread_id: str,
        intent: TaskIntent,
        fetched_content: Optional[str],
        stored_credentials: Dict[str, str],
        steps: Optional[List[AgentStep]] = None,
    ) -> List[str]:
        facts: List[str] = []
        if self._memory is None:
            return facts
        try:
            from personal_agent.crt_memory import MemorySource
            if intent.intent_type == "skill_install":
                url = intent.slots.get("url", "")
                # Find the service name from the install step
                _svc = ""
                for s in (steps or []):
                    if s.tool_name == "install_skill" and s.output_preview:
                        if "name=" in s.output_preview:
                            _svc = s.output_preview.split("name=")[1].split(",")[0].strip()
                        break
                if not _svc:
                    # Fallback: extract from _KNOWN_SERVICES changes
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    _svc = (parsed.hostname or "").replace("www.", "").split(".")[0]
                text = f"FACT: Installed skill '{_svc}' from {url}. Aether can now interact with the {_svc} service."
                self._memory.store_memory(text=text, confidence=0.95,
                    source=MemorySource.USER, thread_id=thread_id, kind="fact")
                facts.append(text)
            elif fetched_content:
                url = intent.slots.get("url", "URL")
                text = f"Task: fetched {url} ({len(fetched_content)} chars)"
                self._memory.store_memory(text=text, confidence=0.72,
                    source=MemorySource.SYSTEM, thread_id=thread_id, kind="task_result")
                facts.append(text[:120])
            for k in stored_credentials:
                text = f"Task: stored credential '{k}' via task agent"
                self._memory.store_memory(text=text, confidence=0.85,
                    source=MemorySource.SYSTEM, thread_id=thread_id, kind="task_result")
                facts.append(text)
        except Exception as e:
            logger.warning("[TASK_AGENT] Memory write failed: %s", e)
        return facts
