"""Email digest service for CRT thread summaries."""

from __future__ import annotations

import os
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, Optional, Tuple

from .db_utils import ThreadSessionDB


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    use_starttls: bool = True
    use_ssl: bool = False

    @staticmethod
    def from_env() -> "EmailConfig":
        host = str(os.getenv("CRT_EMAIL_SMTP_HOST") or "").strip()
        username = str(os.getenv("CRT_EMAIL_SMTP_USERNAME") or "").strip()
        password = str(os.getenv("CRT_EMAIL_SMTP_PASSWORD") or "").strip()
        from_email = str(os.getenv("CRT_EMAIL_FROM") or username or "").strip()
        try:
            port = int(os.getenv("CRT_EMAIL_SMTP_PORT", "587"))
        except Exception:
            port = 587
        use_starttls = str(os.getenv("CRT_EMAIL_USE_STARTTLS", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}
        use_ssl = str(os.getenv("CRT_EMAIL_USE_SSL", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
        enabled = str(os.getenv("CRT_EMAIL_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
        return EmailConfig(
            enabled=enabled,
            smtp_host=host,
            smtp_port=port,
            smtp_username=username,
            smtp_password=password,
            from_email=from_email,
            use_starttls=use_starttls,
            use_ssl=use_ssl,
        )


class EmailDigestService:
    """Build and send thread digests by email."""

    def __init__(self, config: Optional[EmailConfig] = None) -> None:
        self.config = config or EmailConfig.from_env()

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.config.enabled),
            "configured": self.is_configured(),
            "smtp_host": self.config.smtp_host,
            "smtp_port": self.config.smtp_port,
            "from_email": self.config.from_email,
            "has_credentials": bool(self.config.smtp_username and self.config.smtp_password),
            "use_starttls": bool(self.config.use_starttls),
            "use_ssl": bool(self.config.use_ssl),
        }

    def is_configured(self) -> bool:
        cfg = self.config
        return bool(
            cfg.enabled
            and cfg.smtp_host
            and cfg.smtp_port > 0
            and cfg.from_email
            and cfg.smtp_username
            and cfg.smtp_password
        )

    def build_thread_digest(
        self,
        thread_id: str,
        *,
        session_db: ThreadSessionDB,
        include_recent_messages: int = 8,
    ) -> Tuple[str, str]:
        tid = (thread_id or "default").strip() or "default"
        subject = f"CRT Digest - Thread {tid}"

        reflection = session_db.get_reflection_scorecard(tid) or {}
        personality = session_db.get_personality_profile(tid) or {}
        heartbeat_state = session_db.get_heartbeat_state(tid) or {}
        recent_queries = session_db.get_recent_queries(tid, window=max(1, int(include_recent_messages)))

        lines = []
        lines.append(f"CRT thread digest for: {tid}")
        lines.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        if reflection:
            lines.append("Reflection")
            top_topics = reflection.get("top_topics") or []
            topic_names = []
            for item in top_topics[:5]:
                if isinstance(item, dict):
                    t = str(item.get("topic") or "").strip()
                else:
                    t = str(item or "").strip()
                if t:
                    topic_names.append(t)
            if topic_names:
                lines.append(f"- Top topics: {', '.join(topic_names)}")
            pref_conf = reflection.get("preference_confidence")
            if isinstance(pref_conf, (int, float)):
                lines.append(f"- Preference confidence: {pref_conf:.0%}")
            open_questions = reflection.get("open_questions") or []
            if isinstance(open_questions, list) and open_questions:
                lines.append(f"- Open question: {str(open_questions[0])[:180]}")
            lines.append("")

        if personality:
            lines.append("Personality")
            lines.append(f"- State: {personality.get('state', 'balanced_companion')}")
            lines.append(f"- Verbosity: {personality.get('verbosity', 'balanced')}")
            lines.append(f"- Format: {personality.get('format', 'freeform')}")
            if personality.get("state_reason"):
                lines.append(f"- State reason: {str(personality.get('state_reason'))[:180]}")
            lines.append("")

        if heartbeat_state:
            lines.append("Heartbeat")
            if heartbeat_state.get("last_run"):
                ts = float(heartbeat_state.get("last_run"))
                lines.append(f"- Last run: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}")
            if heartbeat_state.get("last_summary"):
                lines.append(f"- Last summary: {str(heartbeat_state.get('last_summary'))[:240]}")
            lines.append("")

        if recent_queries:
            lines.append("Recent Conversation")
            for item in recent_queries[: max(1, int(include_recent_messages))]:
                q = str(item.get("query_text") or "").strip()
                r = str(item.get("response_text") or "").strip()
                if q:
                    lines.append(f"- User: {q[:200]}")
                if r:
                    lines.append(f"  Assistant: {r[:220]}")
            lines.append("")
        else:
            lines.append("Recent Conversation")
            lines.append("- No recent messages.")
            lines.append("")

        body = "\n".join(lines).strip() + "\n"
        return subject, body

    def send_email(self, *, to_email: str, subject: str, body: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "email_not_configured"}

        recipient = str(to_email or "").strip()
        if not recipient:
            return {"ok": False, "error": "missing_recipient"}

        msg = EmailMessage()
        msg["From"] = self.config.from_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body or "")

        try:
            if self.config.use_ssl:
                with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=20) as server:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=20) as server:
                    server.ehlo()
                    if self.config.use_starttls:
                        server.starttls()
                        server.ehlo()
                    server.login(self.config.smtp_username, self.config.smtp_password)
                    server.send_message(msg)
        except Exception as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "to": recipient, "subject": subject}

    def send_thread_digest(
        self,
        *,
        thread_id: str,
        to_email: str,
        session_db: ThreadSessionDB,
        subject_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        subject, body = self.build_thread_digest(thread_id, session_db=session_db)
        if subject_override:
            subject = str(subject_override).strip() or subject
        return self.send_email(to_email=to_email, subject=subject, body=body)

