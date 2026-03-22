"""OpenClaw-style 24/7 heartbeat system for proactive Ledger engagement.

This module implements a local-only heartbeat scheduler that:
1. Runs periodically per thread (configurable interval, e.g., 30m, 1h)
2. Reads HEARTBEAT.md instructions from the workspace
3. Gathers recent chat context and memory
4. Uses LLM to decide proactive Ledger actions (posts, comments, votes)
5. Records results in thread state DB
6. Emits SSE updates and logs for transparency

Design principles:
- No external URLs (local Ledger API only)
- Users control via config + HEARTBEAT.md edits
- Full audit trail of decisions + actions
- Dry-run mode for testing
- Per-thread state tracking (last_run, interval, enabled flag)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Will be imported lazily
HeartbeatLLMExecutor = None


@dataclass
class HeartbeatConfig:
    """Configuration for per-thread heartbeat behavior."""
    enabled: bool = True
    every_seconds: int = 1800  # 30 minutes
    target: str = "none"  # "none" (silent), "last" (last channel), or specific channel
    active_hours_start: Optional[int] = None  # Hour of day (0-23), None = all hours
    active_hours_end: Optional[int] = None
    timezone: str = "UTC"
    model: Optional[str] = None  # Override model for heartbeat (e.g., "claude-3-haiku")
    max_tokens: int = 500
    temperature: float = 0.7
    dry_run: bool = False  # If True, simulate without writing to Ledger
    news_monitoring_enabled: bool = False
    news_topics: List[str] = field(default_factory=list)  # User-defined topics for proactive updates
    news_query_suffix: str = "latest news"
    news_max_results: int = 5
    news_cooldown_seconds: int = 21600  # 6 hours per topic
    news_post_submolt: str = "news"
    curiosity_enabled: bool = True
    curiosity_threshold: float = 0.42
    curiosity_cooldown_seconds: int = 7200
    curiosity_post_enabled: bool = True
    curiosity_post_submolt: str = "reflections"
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> HeartbeatConfig:
        """Parse config from dict."""
        if not data:
            return HeartbeatConfig()
        return HeartbeatConfig(
            enabled=data.get("enabled", True),
            every_seconds=int(data.get("every", data.get("every_seconds", 1800))),
            target=data.get("target", "none"),
            active_hours_start=data.get("active_hours_start"),
            active_hours_end=data.get("active_hours_end"),
            timezone=data.get("timezone", "UTC"),
            model=data.get("model"),
            max_tokens=int(data.get("max_tokens", 500)),
            temperature=float(data.get("temperature", 0.7)),
            dry_run=bool(data.get("dry_run", False)),
            news_monitoring_enabled=bool(data.get("news_monitoring_enabled", False)),
            news_topics=list(data.get("news_topics") or []),
            news_query_suffix=str(data.get("news_query_suffix") or "latest news").strip() or "latest news",
            news_max_results=max(1, int(data.get("news_max_results", 5))),
            news_cooldown_seconds=max(900, int(data.get("news_cooldown_seconds", 21600))),
            news_post_submolt=str(data.get("news_post_submolt") or "news").strip() or "news",
            curiosity_enabled=bool(data.get("curiosity_enabled", True)),
            curiosity_threshold=min(0.95, max(0.1, float(data.get("curiosity_threshold", 0.42)))),
            curiosity_cooldown_seconds=max(900, int(data.get("curiosity_cooldown_seconds", 7200))),
            curiosity_post_enabled=bool(data.get("curiosity_post_enabled", True)),
            curiosity_post_submolt=str(data.get("curiosity_post_submolt") or "reflections").strip() or "reflections",
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "enabled": self.enabled,
            "every": self.every_seconds,
            "target": self.target,
            "active_hours_start": self.active_hours_start,
            "active_hours_end": self.active_hours_end,
            "timezone": self.timezone,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "dry_run": self.dry_run,
            "news_monitoring_enabled": bool(self.news_monitoring_enabled),
            "news_topics": list(self.news_topics or []),
            "news_query_suffix": self.news_query_suffix,
            "news_max_results": int(self.news_max_results),
            "news_cooldown_seconds": int(self.news_cooldown_seconds),
            "news_post_submolt": self.news_post_submolt,
            "curiosity_enabled": bool(self.curiosity_enabled),
            "curiosity_threshold": float(self.curiosity_threshold),
            "curiosity_cooldown_seconds": int(self.curiosity_cooldown_seconds),
            "curiosity_post_enabled": bool(self.curiosity_post_enabled),
            "curiosity_post_submolt": self.curiosity_post_submolt,
        }


@dataclass
class HeartbeatAction:
    """A single action taken by heartbeat (post, comment, vote, or none)."""
    action_type: str  # "post", "comment", "vote", "none"
    target_id: Optional[str] = None  # Post ID for comment/vote
    content: Optional[str] = None  # Post/comment text
    vote_direction: Optional[str] = None  # "up", "down", or None
    reason: str = ""  # Why this action was chosen
    executed: bool = False  # Whether it was actually written to Ledger
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeartbeatResult:
    """Result of a heartbeat run."""
    timestamp: float
    thread_id: str
    ran_successfully: bool
    decision_summary: str  # What the agent decided to do
    actions: List[HeartbeatAction]
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "ran_successfully": self.ran_successfully,
            "decision_summary": self.decision_summary,
            "actions": [a.to_dict() for a in self.actions],
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
        }


class HeartbeatMDParser:
    """Parse HEARTBEAT.md and extract instructions for the agent."""
    
    @staticmethod
    def read_heartbeat_md(workspace_path: Path) -> Optional[str]:
        """Read HEARTBEAT.md from workspace, if it exists."""
        hb_path = workspace_path / "HEARTBEAT.md"
        if not hb_path.exists():
            return None
        try:
            return hb_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read HEARTBEAT.md: {e}")
            return None
    
    @staticmethod
    def extract_instructions(heartbeat_md: str) -> Dict[str, Any]:
        """
        Extract structured instructions from HEARTBEAT.md.
        
        Expected format:
        ```
        ## Checklist
        - [ ] Check for urgent items
        - [ ] Scan Ledger for new submissions
        
        ## Rules
        If no urgent items → reply HEARTBEAT_OK only.
        If high-activity submolt → post summary comment.
        
        ## Proactive Behaviors
        - Monitor for posts from [user1, user2]
        - If consensus question detected → vote up
        ```
        """
        result = {
            "checklist": [],
            "rules": [],
            "proactive_behaviors": [],
            "raw": heartbeat_md,
        }
        
        lines = heartbeat_md.split("\n")
        current_section = None
        
        for line in lines:
            if line.startswith("## "):
                section = line[3:].strip().lower()
                if "checklist" in section:
                    current_section = "checklist"
                elif "rules" in section or "rule" in section:
                    current_section = "rules"
                elif "proactive" in section or "behavior" in section:
                    current_section = "proactive_behaviors"
                else:
                    current_section = None
            elif current_section and line.strip():
                text = line.strip().lstrip("-[] ").strip()
                if text:
                    if current_section == "checklist":
                        result["checklist"].append(text)
                    elif current_section == "rules":
                        result["rules"].append(text)
                    elif current_section == "proactive_behaviors":
                        result["proactive_behaviors"].append(text)
        
        return result


class HeartbeatScheduler:
    """
    Background scheduler that runs heartbeats for each active thread at configured intervals.
    
    This is separate from the reflection/personality loop (continuous_loops.py).
    It runs as a daemon thread and checks which threads are due for a heartbeat.
    """
    
    def __init__(
        self,
        *,
        workspace_path: Path,
        thread_session_db_path: str,
        ledger_db_path: Optional[str] = None,
        memory_db_path: Optional[str] = None,
        interval_seconds: int = 10,  # How often to check for due heartbeats
        enabled: bool = True,
    ):
        self.workspace_path = Path(workspace_path)
        self.thread_session_db_path = str(thread_session_db_path)
        self.ledger_db_path = ledger_db_path
        self.memory_db_path = memory_db_path
        self.check_interval = max(5, int(interval_seconds))
        self.enabled = bool(enabled)
        
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_heartbeat_by_thread: Dict[str, float] = {}
        
        # For SSE notifications
        self._callbacks: List[callable] = []
    
    def register_callback(self, callback: callable) -> None:
        """Register a callback to be called when heartbeat completes."""
        if callback and callable(callback):
            self._callbacks.append(callback)
    
    def _notify_callbacks(self, result: HeartbeatResult) -> None:
        """Notify all registered callbacks."""
        for cb in self._callbacks:
            try:
                cb(result)
            except Exception as e:
                logger.warning(f"Callback error: {e}")
    
    def start(self) -> None:
        """Start the scheduler daemon thread."""
        if not self.enabled:
            logger.debug("[HEARTBEAT] Scheduler is disabled, not starting")
            return
        
        if self._thread and self._thread.is_alive():
            logger.debug("[HEARTBEAT] Scheduler already running")
            return
        
        self._stop.clear()
        self._running = True
        t = threading.Thread(
            target=self._run,
            name="crt-heartbeat-scheduler",
            daemon=True,
        )
        t.start()
        self._thread = t
        logger.info("[HEARTBEAT] Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._stop.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("[HEARTBEAT] Scheduler stopped")
    
    def _run(self) -> None:
        """Main scheduler loop."""
        logger.info(f"[HEARTBEAT] Scheduler loop running (check every {self.check_interval}s)")
        
        while not self._stop.is_set():
            try:
                # Get list of active threads from session DB
                threads = self._get_active_threads()
                
                for thread_id in threads:
                    if self._stop.is_set():
                        break
                    
                    # Check if this thread is due for heartbeat
                    if self._is_heartbeat_due(thread_id):
                        self._run_heartbeat_for_thread(thread_id)
                
                # Sleep before next check
                self._stop.wait(self.check_interval)
            
            except Exception as e:
                logger.error(f"[HEARTBEAT] Scheduler error: {e}", exc_info=True)
                self._stop.wait(5)  # Back off on error
    
    def _get_active_threads(self) -> List[str]:
        """Get list of active thread IDs from session DB."""
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT thread_id FROM thread_sessions ORDER BY last_active DESC")
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows if row[0]]
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting active threads: {e}")
            return []
    
    def _is_heartbeat_due(self, thread_id: str) -> bool:
        """Check if a thread's heartbeat is due."""
        try:
            # Get config and last run time
            config = self._get_heartbeat_config(thread_id)
            if not config.enabled:
                return False
            
            last_run = self._last_heartbeat_by_thread.get(thread_id, 0.0)
            if last_run == 0:
                # Try to get from DB
                last_run = self._get_last_heartbeat_run(thread_id)
                self._last_heartbeat_by_thread[thread_id] = last_run
            
            now = time.time()
            elapsed = now - last_run
            
            # Check if due
            if elapsed >= config.every_seconds:
                # Also check active hours if configured
                if config.active_hours_start is not None:
                    hour = time.localtime().tm_hour
                    end = config.active_hours_end or config.active_hours_start
                    if config.active_hours_start <= config.active_hours_end:
                        # Normal case (e.g., 9-17)
                        if not (config.active_hours_start <= hour < config.active_hours_end):
                            return False
                    else:
                        # Wrap case (e.g., 22-6)
                        if not (hour >= config.active_hours_start or hour < config.active_hours_end):
                            return False
                
                return True
        
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error checking if due for {thread_id}: {e}")
        
        return False
    
    def _get_heartbeat_config(self, thread_id: str) -> HeartbeatConfig:
        """Get heartbeat config for thread (override or default)."""
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT heartbeat_config_json FROM thread_sessions WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                try:
                    data = json.loads(row[0])
                    return HeartbeatConfig.from_dict(data)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting config for {thread_id}: {e}")
        
        return HeartbeatConfig()
    
    def _get_last_heartbeat_run(self, thread_id: str) -> float:
        """Get timestamp of last heartbeat run from DB."""
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT heartbeat_last_run FROM thread_sessions WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                return float(row[0])
        except Exception as e:
            logger.debug(f"[HEARTBEAT] Error getting last run for {thread_id}: {e}")
        
        return 0.0
    
    def _run_heartbeat_for_thread(self, thread_id: str) -> None:
        """Execute heartbeat for a single thread."""
        start_time = time.time()
        result = HeartbeatResult(
            timestamp=start_time,
            thread_id=thread_id,
            ran_successfully=False,
            decision_summary="",
            actions=[],
        )
        
        try:
            logger.info(f"[HEARTBEAT] Starting heartbeat for thread {thread_id}")
            
            # Lazy import the executor
            from .heartbeat_executor import HeartbeatLLMExecutor
            
            config = self._get_heartbeat_config(thread_id)
            heartbeat_md = HeartbeatMDParser.read_heartbeat_md(self.workspace_path)
            instructions = {}
            
            if heartbeat_md:
                instructions = HeartbeatMDParser.extract_instructions(heartbeat_md)
            
            # Initialize executor
            executor = HeartbeatLLMExecutor(
                thread_session_db_path=self.thread_session_db_path,
                ledger_db_path=self.ledger_db_path,
                memory_db_path=self.memory_db_path,
            )
            
            # Gather context
            context = executor.gather_context(thread_id)
            
            # Create decision prompt
            prompt = executor.create_decision_prompt(
                context=context,
                heartbeat_md_text=heartbeat_md or "",
                config=config.to_dict(),
            )
            
            # Call LLM to decide action
            llm_response = self._call_llm(
                prompt=prompt,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )
            
            if llm_response:
                # Parse response
                action_data = executor.parse_llm_response(llm_response)
                
                # Validate action
                is_valid, validation_error = executor.validate_action(action_data)
                if not is_valid:
                    logger.warning(f"[HEARTBEAT] Validation failed: {validation_error}")
                    result.ran_successfully = False
                    result.error = f"Validation: {validation_error}"
                else:
                    # Sanitize action data (truncate, escape, etc)
                    action_data = executor.sanitize_action(action_data)
                    
                    # Execute action
                    exec_result = executor.execute_action(
                        action_data=action_data,
                        thread_id=thread_id,
                        dry_run=config.dry_run,
                    )
                    
                    # Record result
                    action_type = action_data.get("action", "none")
                    action = HeartbeatAction(
                        action_type=action_type,
                        target_id=action_data.get("post_id"),
                        content=action_data.get("content", "")[:500],
                        vote_direction=action_data.get("vote_direction"),
                        reason=action_data.get("reasoning", ""),
                        executed=exec_result.get("success", False),
                    )
                    result.actions = [action]
                    result.decision_summary = f"Action: {action_type}. {action_data.get('reasoning', '')}"
                    result.ran_successfully = True
            
                    result.ran_successfully = True
            else:
                result.ran_successfully = True
                result.decision_summary = "No LLM response; taking no action"
            
        except Exception as e:
            logger.error(f"[HEARTBEAT] Error running heartbeat for {thread_id}: {e}", exc_info=True)
            result.ran_successfully = False
            result.error = str(e)
        
        finally:
            result.execution_time_seconds = time.time() - start_time
            self._last_heartbeat_by_thread[thread_id] = result.timestamp
            self._record_heartbeat_run(thread_id, result)
            self._notify_callbacks(result)

        # Self-reflection pass — runs after the main action regardless of its success.
        # Failures here are fully isolated from the main heartbeat result.
        try:
            self._run_self_reflection(thread_id)
        except Exception as sr_exc:
            logger.debug("[HEARTBEAT] self-reflection pass failed: %s", sr_exc)

    # ------------------------------------------------------------------
    # Self-reflection pass (personality / self-awareness)
    # ------------------------------------------------------------------

    _SELF_REFLECTION_PROMPT = """You are Aether performing a private self-assessment.

Evidence from recent interactions:

Gate failures (things you tried to say but were blocked): {gate_fails}
Negative feedback from user (what you got wrong): {negative_feedback}
Open unresolved contradictions: {open_contradictions}
Recent trust movements (memories that changed): {trust_deltas}
Current self-model:
{current_self_model}

Based on this evidence, produce a JSON object with ONLY these keys:
{{
  "uncertainty_domains": "<topics where you frequently make errors>",
  "correction_pattern": "<pattern in your mistakes — e.g. over-stating recency, confusing similar names>",
  "trust_trajectory": "<one sentence on whether trust is rising, stable, or eroding and why>",
  "known_blindspots": "<structural weaknesses you've noticed — be specific>",
  "growing_confidence": "<areas where you've been consistently accurate and reinforced>",
  "user_relationship": "<one sentence on the interaction style and what the user values>",
  "response_style": "<current calibration — verbosity, tone, hedging level>",
  "summary": "<2-sentence honest self-assessment>",
  "notable_events": ["<event1>", "<event2>"]
}}

Be honest and specific. If you have no evidence for a field, say so briefly.
Output ONLY valid JSON, nothing else."""

    def _run_self_reflection(self, thread_id: str) -> None:
        """Run a self-reflection LLM pass and update the self-model."""
        from personal_agent.self_model import get_self_model
        from personal_agent.db_utils import get_db_connection

        self_model = get_self_model()

        # ── gather evidence signals ──────────────────────────────────────────
        gate_fails_lines: List[str] = []
        negative_feedback_lines: List[str] = []
        trust_delta_lines: List[str] = []
        open_contradictions = 0

        al_db = Path("personal_agent/active_learning.db")
        if al_db.exists():
            try:
                with get_db_connection(str(al_db)) as conn:
                    since = time.time() - 86400  # last 24h

                    rows = conn.execute(
                        """SELECT payload_json FROM turn_telemetry
                           WHERE event_type = 'gate_fail' AND ts > ?
                           ORDER BY ts DESC LIMIT 5""",
                        (since,),
                    ).fetchall()
                    for r in rows:
                        try:
                            p = json.loads(r[0] or "{}")
                            gate_fails_lines.append(
                                f"- {p.get('gate_reason', 'unknown')}"
                            )
                        except Exception:
                            pass

                    rows = conn.execute(
                        """SELECT payload_json, severity FROM turn_telemetry
                           WHERE event_type = 'feedback_down' AND ts > ?
                           ORDER BY severity DESC, ts DESC LIMIT 8""",
                        (since,),
                    ).fetchall()
                    for r in rows:
                        try:
                            p = json.loads(r[0] or "{}")
                            cat = p.get("category", "general")
                            negative_feedback_lines.append(
                                f"- {cat} (severity {float(r[1] or 0):.2f})"
                            )
                        except Exception:
                            pass

                    rows = conn.execute(
                        """SELECT memory_ids_json, payload_json FROM turn_telemetry
                           WHERE event_type = 'trust_delta_batch' AND ts > ?
                           ORDER BY ts DESC LIMIT 3""",
                        (since,),
                    ).fetchall()
                    for r in rows:
                        try:
                            p = json.loads(r[1] or "{}")
                            trust_delta_lines.append(
                                f"- delta {p.get('mean_delta', '?'):.3f} across {p.get('count', '?')} memories"
                            )
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug("[SELF_REFLECTION] signal read failed: %s", exc)

        # open contradictions from ledger
        for ledger_cand in [
            Path("personal_agent/crt_ledger_shared.db"),
            Path("data/crt_memory.db"),
        ]:
            if ledger_cand.exists():
                try:
                    with get_db_connection(str(ledger_cand)) as conn:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM contradictions "
                            "WHERE status IN ('OPEN','REFLECTING')"
                        ).fetchone()
                        open_contradictions = int(row[0]) if row else 0
                    break
                except Exception:
                    pass

        # ── call LLM ─────────────────────────────────────────────────────────
        current_model = self_model.read_model()
        current_model_text = "\n".join(
            f"  {k}: {v or '(not yet set)'}"
            for k, v in current_model.items()
        )

        prompt = self._SELF_REFLECTION_PROMPT.format(
            gate_fails="\n".join(gate_fails_lines) or "(none in last 24h)",
            negative_feedback="\n".join(negative_feedback_lines) or "(none in last 24h)",
            open_contradictions=str(open_contradictions),
            trust_deltas="\n".join(trust_delta_lines) or "(none recorded)",
            current_self_model=current_model_text,
        )

        llm_response = self._call_llm(
            prompt=prompt,
            max_tokens=600,
            temperature=0.4,
        )

        if not llm_response:
            logger.debug("[SELF_REFLECTION] no LLM response, skipping")
            return

        # ── parse JSON ───────────────────────────────────────────────────────
        import re as _re
        raw = llm_response.strip()
        # Extract JSON block if wrapped in markdown fences
        m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, _re.DOTALL)
        if m:
            raw = m.group(1)
        elif raw.startswith("{"):
            pass
        else:
            brace = raw.find("{")
            if brace >= 0:
                raw = raw[brace:]

        try:
            data = json.loads(raw)
        except Exception as parse_exc:
            logger.debug("[SELF_REFLECTION] JSON parse failed: %s | raw=%s", parse_exc, raw[:200])
            return

        # ── cloud reflection validation (optional) ─────────────────────────
        _cloud_reflection_skip = False
        try:
            import auth as _auth_mod_refl
            # Use user_id=1 (single-user default) for heartbeat context
            _cloud_refl_enabled = str(
                _auth_mod_refl.get_user_setting(1, "cloud_reflection_validation", "false")
            ).lower() in ("true", "1", "yes")
            if _cloud_refl_enabled:
                from personal_agent.cloud_features import get_cloud_feature_service
                _cloud_svc_refl = get_cloud_feature_service()
                if _cloud_svc_refl is not None:
                    # Build evidence list from the signals gathered above
                    _evidence_for_cloud = []
                    for gf in gate_fails_lines:
                        _evidence_for_cloud.append({"type": "gate_fail", "detail": gf})
                    for nf in negative_feedback_lines:
                        _evidence_for_cloud.append({"type": "negative_feedback", "detail": nf})
                    for td in trust_delta_lines:
                        _evidence_for_cloud.append({"type": "trust_delta", "detail": td})
                    if open_contradictions:
                        _evidence_for_cloud.append({"type": "open_contradictions", "count": open_contradictions})

                    _proposed = {k: str(v) for k, v in data.items() if k != "notable_events" and v}
                    _validation = _cloud_svc_refl.validate_reflection(
                        evidence=_evidence_for_cloud,
                        proposed_update=_proposed,
                    )
                    if _validation and not _validation.get("valid", True):
                        _cloud_reflection_skip = True
                        logger.info(
                            "[CLOUD_REFLECTION] Cloud rejected self-model update: %s",
                            _validation.get("concerns", "unspecified"),
                        )
        except Exception as _cloud_refl_err:
            logger.debug("[CLOUD_REFLECTION] Cloud validation failed (non-fatal): %s", _cloud_refl_err)

        # ── update self-model slots ──────────────────────────────────────────
        last_snapshot = self_model.get_last_snapshot()
        new_snapshot: Dict[str, Any] = {}
        delta: Dict[str, str] = {}

        from personal_agent.self_model import SELF_MODEL_SLOTS
        if _cloud_reflection_skip:
            logger.info("[SELF_REFLECTION] Skipping self-model update (cloud validation rejected)")
        else:
            for slot in SELF_MODEL_SLOTS:
                value = str(data.get(slot) or "").strip()
                if not value or value == "(not yet set)":
                    continue
                # Compute delta from last snapshot
                old_val = last_snapshot.get(slot, "")
                if old_val and old_val != value:
                    delta[slot] = f"{old_val[:60]} → {value[:60]}"
                new_snapshot[slot] = value
                # Severity-weighted trust: use negative feedback density as evidence quality
                trust = max(0.35, min(0.80, 0.55 + len(negative_feedback_lines) * 0.03))
                self_model.update_slot(slot, value, trust=trust, thread_id=thread_id)

        # ── write checkpoint ─────────────────────────────────────────────────
        notable = data.get("notable_events") or []
        if isinstance(notable, str):
            notable = [notable]
        new_snapshot["summary"] = data.get("summary", "")

        self_model.checkpoint(
            snapshot=new_snapshot,
            delta=delta or None,
            notable_events=[str(e) for e in notable[:5]],
            period_days=1.0,
        )

        logger.info(
            "[SELF_REFLECTION] updated %d slots, %d deltas, %d notable events",
            len(new_snapshot),
            len(delta),
            len(notable),
        )

    def _record_heartbeat_run(self, thread_id: str, result: HeartbeatResult) -> None:
        """Record heartbeat run result in thread_sessions DB."""
        try:
            conn = sqlite3.connect(self.thread_session_db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            actions_json = json.dumps([a.to_dict() for a in result.actions])
            
            cursor.execute(
                """
                UPDATE thread_sessions 
                SET heartbeat_last_run = ?, 
                    heartbeat_last_summary = ?,
                    heartbeat_last_actions_json = ?
                WHERE thread_id = ?
                """,
                (result.timestamp, result.decision_summary, actions_json, thread_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[HEARTBEAT] Failed to record heartbeat for {thread_id}: {e}")
    
    def _call_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """Call LLM to get heartbeat decision."""
        try:
            # Try Ollama first (local)
            from .ollama_client import OllamaClient
            
            llm_model = model or os.getenv("CRT_OLLAMA_MODEL") or "llama3.2:latest"
            client = OllamaClient(model=llm_model)
            
            response = client.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response
        
        except Exception as e:
            logger.warning(f"[HEARTBEAT] LLM call failed: {e}")
            return None
    
    def run_heartbeat_now(self, thread_id: str) -> HeartbeatResult:
        """
        Manually trigger a heartbeat for a thread.
        Returns the result immediately (blocking).
        """
        self._run_heartbeat_for_thread(thread_id)
        # The result is cached in memory, but we don't have access to it here
        # For now, return a basic result
        return HeartbeatResult(
            timestamp=time.time(),
            thread_id=thread_id,
            ran_successfully=True,
            decision_summary="Manual heartbeat triggered",
            actions=[],
        )


def get_heartbeat_scheduler(
    workspace_path: Path,
    thread_session_db_path: str,
    enabled: bool = True,
) -> HeartbeatScheduler:
    """Factory to create and initialize the heartbeat scheduler."""
    return HeartbeatScheduler(
        workspace_path=workspace_path,
        thread_session_db_path=thread_session_db_path,
        enabled=enabled,
    )


def run_self_reflection_now(thread_id: str = "default") -> Dict[str, Optional[str]]:
    """Standalone self-reflection trigger — runs the LLM self-awareness pass for
    a given thread and returns the updated self-model slots.  Can be called from
    any context without needing a running HeartbeatScheduler instance.

    This is the primary entry point used by HeartbeatLLMExecutor.run_heartbeat_for_thread()
    to execute self-reflection as part of the active heartbeat loop.
    """
    _dummy = HeartbeatScheduler.__new__(HeartbeatScheduler)
    _dummy._run_self_reflection(thread_id)
    from personal_agent.self_model import get_self_model
    return get_self_model().read_model()
