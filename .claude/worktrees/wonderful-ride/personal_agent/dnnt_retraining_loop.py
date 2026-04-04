"""Managed background loop for periodic DNNT retraining."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .dnnt.background_learning import (
    BackgroundLearningConfig,
    run_background_learning_once,
)

logger = logging.getLogger(__name__)


@dataclass
class DNNTBackgroundLoopStatus:
    enabled: bool
    running: bool
    poll_interval_seconds: float
    last_run_at: Optional[float]
    last_summary: Optional[Dict[str, Any]]
    last_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "running": bool(self.running),
            "poll_interval_seconds": float(self.poll_interval_seconds),
            "last_run_at": self.last_run_at,
            "last_summary": self.last_summary,
            "last_error": self.last_error,
        }


class DNNTBackgroundLoop:
    """Runs DNNT background learning on a fixed interval."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        poll_interval_seconds: float = 1800.0,
        config: Optional[BackgroundLearningConfig] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.poll_interval_seconds = max(30.0, float(poll_interval_seconds))
        self.config = config or BackgroundLearningConfig()

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._running = False
        self._last_run_at: Optional[float] = None
        self._last_summary: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None

    def status(self) -> DNNTBackgroundLoopStatus:
        return DNNTBackgroundLoopStatus(
            enabled=self.enabled,
            running=self._running,
            poll_interval_seconds=self.poll_interval_seconds,
            last_run_at=self._last_run_at,
            last_summary=self._last_summary,
            last_error=self._last_error,
        )

    def run_once(self) -> Dict[str, Any]:
        """Run one background learning cycle immediately."""
        with self._lock:
            self._last_error = None
            try:
                summary = run_background_learning_once(config=self.config)
                self._last_run_at = time.time()
                self._last_summary = summary if isinstance(summary, dict) else {"summary": str(summary)}
                return self._last_summary
            except Exception as e:
                self._last_run_at = time.time()
                self._last_error = str(e)
                logger.exception("[DNNT_LOOP] run_once failed: %s", e)
                return {"ok": False, "error": str(e)}

    def start(self) -> None:
        if not self.enabled:
            logger.info("[DNNT_LOOP] Disabled; not starting")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_forever, name="dnnt-background-loop", daemon=True)
        self._thread.start()
        logger.info("[DNNT_LOOP] Started (poll_interval=%ss)", self.poll_interval_seconds)

    def stop(self) -> None:
        self._stop.set()
        logger.info("[DNNT_LOOP] Stop requested")

    def _run_forever(self) -> None:
        self._running = True
        try:
            while not self._stop.is_set():
                self.run_once()
                self._stop.wait(self.poll_interval_seconds)
        finally:
            self._running = False

