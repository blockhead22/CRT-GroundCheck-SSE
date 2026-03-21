from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


_DEFAULT_HANDOFF_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "agent_id": "main",
    "session_prefix": "crt",
    "timeout_seconds": 120,
    "allowed_channels": ["telegram", "webchat"],
    "denied_channels": [],
    "inject_crt_context": True,
    "include_api_guide": True,
    "max_fact_items": 8,
    "auto_keywords": [
        "moltbook",
        "join moltbook",
        "openclaw",
        "research",
        "investigate",
        "look up",
        "search for",
        "find latest",
        "browse",
        "compare",
        "summarize",
        "github",
        "git hub",
        "repo",
        "repository",
        "pull request",
        "issue",
        "documentation",
        "docs for",
        "check website",
        "visit",
        "weather",
        "price of",
        "what changed",
    ],
}


def get_openclaw_handoff_config(runtime_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = dict(_DEFAULT_HANDOFF_CONFIG)
    raw = {}
    if isinstance(runtime_config, dict):
        raw = runtime_config.get("openclaw_handoff") or {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            cfg[key] = value
    return cfg


def openclaw_session_id(thread_id: str, session_prefix: str = "crt") -> str:
    prefix = str(session_prefix or "crt").strip() or "crt"
    safe_thread = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(thread_id or "default")).strip("._-")
    safe_thread = safe_thread or "default"
    return f"{prefix}-{safe_thread}"


def resolve_openclaw_executable() -> str:
    """Resolve the OpenClaw CLI path in a way that works from Python on Windows."""
    explicit = str(os.getenv("OPENCLAW_BIN", "") or "").strip()
    if explicit:
        return explicit

    for candidate in ("openclaw", "openclaw.cmd", "openclaw.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    appdata = str(os.getenv("APPDATA", "") or "").strip()
    if appdata:
        npm_bin = Path(appdata) / "npm"
        for name in ("openclaw.cmd", "openclaw.exe", "openclaw"):
            candidate = npm_bin / name
            if candidate.exists():
                return str(candidate)

    return "openclaw"


def should_delegate_to_openclaw(
    *,
    message: str,
    channel: Optional[str],
    meta_scope: Optional[str],
    mode: Optional[str],
    runtime_config: Optional[Dict[str, Any]],
) -> tuple[bool, Optional[str]]:
    cfg = get_openclaw_handoff_config(runtime_config)
    if not bool(cfg.get("enabled")):
        return False, None

    chan = str(channel or "").strip().lower()
    allowed = [str(x).strip().lower() for x in (cfg.get("allowed_channels") or []) if str(x).strip()]
    denied = [str(x).strip().lower() for x in (cfg.get("denied_channels") or []) if str(x).strip()]

    if chan and denied and chan in denied:
        return False, None
    if allowed and chan not in allowed:
        return False, None

    scope = str(meta_scope or "").strip().lower()
    if scope in {"openclaw", "openclaw_auto", "openclaw_force"}:
        return True, "meta_scope"

    mode_name = str(mode or "").strip().lower()
    if mode_name == "tasking":
        return True, "tasking_mode"

    text = str(message or "").strip().lower()
    if not text:
        return False, None

    url_action_re = re.compile(
        r"\b(read|fetch|visit|check|open|go to|follow|access|look at|get|load)\b.{0,60}https?://\S+",
        re.IGNORECASE,
    )
    bare_url_re = re.compile(r"^https?://\S+$", re.IGNORECASE)
    if url_action_re.search(text) or bare_url_re.match(text):
        return True, "url_action"

    for keyword in cfg.get("auto_keywords") or []:
        probe = str(keyword or "").strip().lower()
        if probe and probe in text:
            return True, f"keyword:{probe}"

    return False, None


def build_openclaw_prompt(
    *,
    user_command: str,
    thread_id: str,
    crt_api_url: str,
    channel: Optional[str] = None,
    origin: Optional[str] = None,
    actor_id: Optional[str] = None,
    structured_facts: Optional[Dict[str, Any]] = None,
    include_api_guide: bool = True,
    max_fact_items: int = 8,
) -> str:
    lines = [
        "This task was delegated by CRT.",
        f"CRT thread_id: {thread_id}",
    ]

    helper_path = os.getenv(
        "OPENCLAW_CRT_CLIENT",
        r"C:\Users\block\AppData\Roaming\npm\node_modules\openclaw\skills\crt-memory\scripts\crt_client.py",
    ).strip()
    helper_exists = bool(helper_path) and Path(helper_path).exists()

    if channel:
        lines.append(f"Inbound channel: {channel}")
    if origin:
        lines.append(f"Origin: {origin}")
    if actor_id:
        lines.append(f"Actor ID: {actor_id}")

    if include_api_guide:
        base = str(crt_api_url or "http://127.0.0.1:8123").rstrip("/")
        lines.extend(
            [
                f"CRT API base: {base}",
                "You have direct local access to CRT. Query it when you need grounded personal context.",
                f"- GET {base}/api/profile?thread_id={thread_id}",
                f"- GET {base}/api/facts/structured?thread_id={thread_id}&scope=effective",
                f"- GET {base}/api/facts/search?thread_id={thread_id}&scope=effective&q=<query>",
                f"- GET {base}/api/memory/recent?thread_id={thread_id}&limit=50",
                f"- GET {base}/api/contradictions?thread_id={thread_id}",
                f"- GET {base}/api/memory/usage/summary?thread_id={thread_id}&limit=25",
                f"- POST {base}/api/memory/store (include thread_id, channel, origin, kind, authority/source_kind where relevant)",
            ]
        )
        if helper_exists:
            lines.extend(
                [
                    "Preferred CRT helper:",
                    f'- `python "{helper_path}" --thread {thread_id} facts`',
                    f'- `python "{helper_path}" --thread {thread_id} facts-search --query "favorite color"`',
                    f'- `python "{helper_path}" --thread {thread_id} recent --limit 20`',
                    f'- `python "{helper_path}" --thread {thread_id} contradictions`',
                ]
            )

    if isinstance(structured_facts, dict) and structured_facts:
        compact: Dict[str, Any] = {}
        for idx, (key, value) in enumerate(structured_facts.items()):
            if idx >= max(1, int(max_fact_items or 8)):
                break
            if value is None or value == "":
                continue
            compact[str(key)] = value
        if compact:
            lines.append(f"Compact CRT facts: {json.dumps(compact, ensure_ascii=True)}")

    lines.extend(
        [
            "",
            "User task:",
            str(user_command or "").strip(),
        ]
    )
    return "\n".join(lines).strip()


def _extract_openclaw_answer(raw: Dict[str, Any]) -> str:
    """Extract the user-facing answer from OpenClaw JSON output."""
    for key in ("output", "response", "text", "content"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    payloads = raw.get("payloads")
    if isinstance(payloads, list):
        texts = []
        for item in payloads:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if text:
                texts.append(text)
        if texts:
            return "\n\n".join(texts).strip()

    result = raw.get("result")
    if isinstance(result, dict):
        nested = _extract_openclaw_answer(result)
        if nested:
            return nested

    return ""


def _parse_openclaw_json(stdout: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse for OpenClaw --json output."""
    text = str(stdout or "").strip()
    if not text:
        return None

    candidates = [text]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        candidates.extend(reversed(lines))

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            raw = json.loads(candidate)
        except Exception:
            continue
        if isinstance(raw, dict):
            return raw
    return None


def run_openclaw_agent(
    *,
    user_command: str,
    thread_id: str,
    crt_api_url: str = "http://127.0.0.1:8123",
    channel: Optional[str] = None,
    origin: Optional[str] = None,
    actor_id: Optional[str] = None,
    structured_facts: Optional[Dict[str, Any]] = None,
    runtime_config: Optional[Dict[str, Any]] = None,
    workdir: Optional[Path] = None,
) -> Dict[str, Any]:
    cfg = get_openclaw_handoff_config(runtime_config)
    agent_id = str(cfg.get("agent_id") or "main").strip() or "main"
    session_prefix = str(cfg.get("session_prefix") or "crt").strip() or "crt"
    timeout_seconds = int(cfg.get("timeout_seconds") or 120)
    include_api_guide = bool(cfg.get("include_api_guide", True))
    inject_crt_context = bool(cfg.get("inject_crt_context", True))
    max_fact_items = int(cfg.get("max_fact_items") or 8)
    session_id = openclaw_session_id(thread_id, session_prefix=session_prefix)

    prompt = build_openclaw_prompt(
        user_command=user_command,
        thread_id=thread_id,
        crt_api_url=crt_api_url,
        channel=channel,
        origin=origin,
        actor_id=actor_id,
        structured_facts=structured_facts if inject_crt_context else None,
        include_api_guide=include_api_guide,
        max_fact_items=max_fact_items,
    )

    cmd = [
        resolve_openclaw_executable(),
        "agent",
        "--local",
        "--agent",
        agent_id,
        "--session-id",
        session_id,
        "--message",
        prompt,
        "--json",
    ]
    logger.info("[OPENCLAW] Delegating thread=%s session=%s agent=%s", thread_id, session_id, agent_id)

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(10, timeout_seconds),
        cwd=str(workdir or Path.cwd()),
        env={
            **os.environ,
            "CRT_API_URL": str(crt_api_url or "http://127.0.0.1:8123").rstrip("/"),
            "CRT_THREAD_ID": str(thread_id or "openclaw"),
            "CRT_CHANNEL": str(channel or ""),
            "CRT_ORIGIN": str(origin or ""),
            "CRT_ACTOR_ID": str(actor_id or ""),
            "PYTHONIOENCODING": "utf-8",
            "OPENCLAW_CRT_CLIENT": os.getenv(
                "OPENCLAW_CRT_CLIENT",
                r"C:\Users\block\AppData\Roaming\npm\node_modules\openclaw\skills\crt-memory\scripts\crt_client.py",
            ),
        },
    )

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    parsed: Optional[Dict[str, Any]] = None
    answer = ""

    if stdout:
        parsed = _parse_openclaw_json(stdout)
        if parsed is not None:
            answer = _extract_openclaw_answer(parsed)
        else:
            answer = stdout

    if not answer and stderr:
        answer = stderr

    return {
        "ok": bool(completed.returncode == 0 and answer),
        "answer": answer or "OpenClaw returned an empty response.",
        "session_id": session_id,
        "agent_id": agent_id,
        "returncode": int(completed.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed,
        "command": cmd,
    }
