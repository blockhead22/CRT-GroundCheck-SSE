"""
Personal rate limiter for cloud LLM providers.

Tracks requests-per-minute (RPM) and tokens-per-day (TPD) using sliding windows.
When limits are hit, HybridLLMClient falls back to local Ollama automatically.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PersonalRateLimiter:
    """Thread-safe sliding-window rate limiter for a single provider."""

    def __init__(
        self,
        *,
        provider: str = "anthropic",
        rpm_limit: int = 50,
        tpd_limit: int = 1_000_000,
    ) -> None:
        self.provider = provider
        self.rpm_limit = rpm_limit
        self.tpd_limit = tpd_limit

        self._lock = threading.Lock()
        self._request_times: Deque[float] = deque()          # timestamps
        self._token_log: Deque[Tuple[float, int]] = deque()   # (timestamp, token_count)
        self._total_requests: int = 0
        self._total_tokens: int = 0
        self._fallback_count: int = 0

    def can_request(self) -> bool:
        """Check if a request can be made within rate limits."""
        with self._lock:
            now = time.time()
            self._prune(now)

            if len(self._request_times) >= self.rpm_limit:
                return False

            day_tokens = sum(count for _, count in self._token_log)
            if day_tokens >= self.tpd_limit:
                return False

            return True

    def record_request(self, tokens_used: int = 0) -> None:
        """Record a completed request and its token usage."""
        with self._lock:
            now = time.time()
            self._request_times.append(now)
            if tokens_used > 0:
                self._token_log.append((now, tokens_used))
            self._total_requests += 1
            self._total_tokens += tokens_used

    def record_fallback(self) -> None:
        """Record that a fallback to local was triggered."""
        with self._lock:
            self._fallback_count += 1

    def time_until_available(self) -> float:
        """Seconds until the next request can be made (0 if available now)."""
        with self._lock:
            now = time.time()
            self._prune(now)

            if len(self._request_times) < self.rpm_limit:
                day_tokens = sum(count for _, count in self._token_log)
                if day_tokens < self.tpd_limit:
                    return 0.0

                # Token limit hit — find when oldest day entry expires
                if self._token_log:
                    oldest = self._token_log[0][0]
                    return max(0.0, oldest + 86400 - now)
                return 0.0

            # RPM limit hit — find when oldest minute entry expires
            oldest = self._request_times[0]
            return max(0.0, oldest + 60 - now)

    def usage_summary(self) -> Dict:
        """Return current usage stats for telemetry/dashboard."""
        with self._lock:
            now = time.time()
            self._prune(now)

            rpm_used = len(self._request_times)
            tpd_used = sum(count for _, count in self._token_log)

            return {
                "provider": self.provider,
                "rpm_used": rpm_used,
                "rpm_limit": self.rpm_limit,
                "rpm_pct": round(rpm_used / max(self.rpm_limit, 1) * 100, 1),
                "tpd_used": tpd_used,
                "tpd_limit": self.tpd_limit,
                "tpd_pct": round(tpd_used / max(self.tpd_limit, 1) * 100, 1),
                "total_requests": self._total_requests,
                "total_tokens": self._total_tokens,
                "fallback_count": self._fallback_count,
                "available": rpm_used < self.rpm_limit and tpd_used < self.tpd_limit,
                "seconds_until_available": self.time_until_available(),
            }

    def _prune(self, now: float) -> None:
        """Remove expired entries from sliding windows (must hold lock)."""
        # Prune RPM window (60 seconds)
        cutoff_rpm = now - 60
        while self._request_times and self._request_times[0] < cutoff_rpm:
            self._request_times.popleft()

        # Prune TPD window (24 hours)
        cutoff_tpd = now - 86400
        while self._token_log and self._token_log[0][0] < cutoff_tpd:
            self._token_log.popleft()


class RateLimiterRegistry:
    """Registry of rate limiters, one per provider."""

    def __init__(self) -> None:
        self._limiters: Dict[str, PersonalRateLimiter] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        provider: str,
        rpm_limit: int = 50,
        tpd_limit: int = 1_000_000,
    ) -> PersonalRateLimiter:
        with self._lock:
            if provider not in self._limiters:
                self._limiters[provider] = PersonalRateLimiter(
                    provider=provider,
                    rpm_limit=rpm_limit,
                    tpd_limit=tpd_limit,
                )
                logger.info(
                    "[RATE_LIMITER] Created limiter for %s: %d RPM, %d TPD",
                    provider, rpm_limit, tpd_limit,
                )
            return self._limiters[provider]

    def get(self, provider: str) -> Optional[PersonalRateLimiter]:
        with self._lock:
            return self._limiters.get(provider)

    def all_summaries(self) -> Dict[str, Dict]:
        with self._lock:
            return {name: limiter.usage_summary() for name, limiter in self._limiters.items()}
