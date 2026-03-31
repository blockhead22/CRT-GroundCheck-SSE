"""
Execution Belief Verification — Empirical, Not Adversarial

CRT's alternative to "spawn a second model to check the first."
Instead of model-checking-model, we check reality against prediction.

Before a tool runs, the model's reasoning contains an implicit expectation
about what will happen. After the tool runs, we check if reality matched:

- Did the file write succeed? (status == "ok")
- Does the result contain expected content? (keyword matching)
- Did the tool error when success was expected? (status mismatch)
- Did the tool succeed when failure was expected? (surprise success)

Results feed back into execution beliefs: this tool, with this intent,
in this context, succeeded or failed. Over time, the system learns which
patterns need extra verification.

Not adversarial — empirical. Not another model call — structural.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keywords in reasoning that indicate expectation of success
SUCCESS_EXPECTATIONS = re.compile(
    r'\b(should\s+(?:return|show|contain|create|work|succeed|pass|fix|find))'
    r'|(?:this\s+will\s+(?:create|fix|return|show|produce))'
    r'|(?:expecting\s+(?:to\s+see|success|output|result))'
    r'|(?:let\s+me\s+(?:verify|check|confirm|read\s+back))',
    re.IGNORECASE,
)

# Keywords indicating expectation of potential failure
FAILURE_EXPECTATIONS = re.compile(
    r'\b(might\s+(?:fail|error|not\s+exist|not\s+work))'
    r'|(?:could\s+(?:fail|error|timeout))'
    r'|(?:may\s+not\s+(?:exist|work|be\s+there))'
    r'|(?:if\s+(?:it\s+fails|this\s+errors|not\s+found))',
    re.IGNORECASE,
)

# Content keywords to extract from reasoning for result matching
CONTENT_EXPECTATIONS = re.compile(
    r'(?:should\s+(?:contain|show|return|output|include)\s+["\']?)([\w\s./-]+)',
    re.IGNORECASE,
)

# Tools that produce verifiable results
VERIFIABLE_TOOLS = {
    "file_write", "file_read", "shell_exec", "search_code",
    "dir_list", "memory_recall", "web_search", "git_exec",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolExpectation:
    """What we expect before a tool runs."""
    tool: str
    args: Dict[str, Any]
    expects_success: bool           # True if reasoning implies success
    expects_failure: bool           # True if reasoning implies potential failure
    expected_content: List[str]     # keywords expected in result
    reasoning_excerpt: str          # the model's reasoning that generated this expectation
    timestamp: float = field(default_factory=time.time)


@dataclass
class VerificationResult:
    """What happened vs what was expected."""
    tool: str
    expected_success: bool
    actual_success: bool
    status_match: bool              # did success/failure match expectation?
    content_match: Optional[bool]   # did result contain expected content?
    content_matches: int            # how many expected keywords found
    content_misses: int             # how many expected keywords missing
    surprise: str                   # "none" | "unexpected_success" | "unexpected_failure" | "content_mismatch"
    verification_ms: float
    details: str


# ---------------------------------------------------------------------------
# Expectation extraction
# ---------------------------------------------------------------------------

def extract_expectation(
    tool: str,
    args: Dict[str, Any],
    reasoning: str,
) -> ToolExpectation:
    """Extract the implicit expectation from the model's reasoning.

    No LLM call — pattern matching on reasoning text.
    """
    expects_success = bool(SUCCESS_EXPECTATIONS.search(reasoning))
    expects_failure = bool(FAILURE_EXPECTATIONS.search(reasoning))

    # If neither detected, default to expecting success (optimism bias)
    if not expects_success and not expects_failure:
        expects_success = True

    # Extract expected content keywords
    expected_content = []
    for match in CONTENT_EXPECTATIONS.finditer(reasoning):
        kw = match.group(1).strip()
        if kw and len(kw) > 2:
            expected_content.append(kw)

    return ToolExpectation(
        tool=tool,
        args=args,
        expects_success=expects_success,
        expects_failure=expects_failure,
        expected_content=expected_content,
        reasoning_excerpt=reasoning[:200],
    )


# ---------------------------------------------------------------------------
# Result verification
# ---------------------------------------------------------------------------

def verify_tool_result(
    expectation: ToolExpectation,
    result_content: str,
    result_status: str,
) -> VerificationResult:
    """Check if tool result matches expectation. Empirical, not adversarial.

    Checks:
    1. Status match: did success/failure match what was expected?
    2. Content match: does result contain expected keywords?
    3. Surprise detection: flag unexpected outcomes
    """
    t0 = time.perf_counter()

    actual_success = result_status == "ok"
    status_match = (
        (expectation.expects_success and actual_success)
        or (expectation.expects_failure and not actual_success)
    )

    # Content matching
    content_match = None
    content_matches = 0
    content_misses = 0

    if expectation.expected_content and result_content:
        result_lower = result_content.lower()
        for kw in expectation.expected_content:
            if kw.lower() in result_lower:
                content_matches += 1
            else:
                content_misses += 1
        content_match = content_misses == 0

    # Surprise classification
    surprise = "none"
    if expectation.expects_success and not actual_success:
        surprise = "unexpected_failure"
    elif expectation.expects_failure and actual_success:
        surprise = "unexpected_success"
    elif content_match is False:
        surprise = "content_mismatch"

    elapsed = (time.perf_counter() - t0) * 1000

    # Build details string
    details_parts = [f"tool={expectation.tool}"]
    if surprise != "none":
        details_parts.append(f"surprise={surprise}")
    if expectation.expected_content:
        details_parts.append(f"content_match={content_matches}/{content_matches + content_misses}")
    if not status_match:
        details_parts.append(f"expected={'success' if expectation.expects_success else 'failure'} got={'success' if actual_success else 'failure'}")

    result = VerificationResult(
        tool=expectation.tool,
        expected_success=expectation.expects_success,
        actual_success=actual_success,
        status_match=status_match,
        content_match=content_match,
        content_matches=content_matches,
        content_misses=content_misses,
        surprise=surprise,
        verification_ms=elapsed,
        details=", ".join(details_parts),
    )

    if surprise != "none":
        logger.info(
            f"[VERIFY] {surprise}: {expectation.tool} "
            f"(expected={'ok' if expectation.expects_success else 'fail'}, "
            f"got={result_status})"
        )

    return result


# ---------------------------------------------------------------------------
# Aggregation for execution beliefs
# ---------------------------------------------------------------------------

@dataclass
class VerificationStats:
    """Aggregate verification statistics for a session."""
    total_verified: int = 0
    status_matches: int = 0
    status_mismatches: int = 0
    content_matches: int = 0
    content_mismatches: int = 0
    unexpected_failures: int = 0
    unexpected_successes: int = 0
    by_tool: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def match_rate(self) -> float:
        if self.total_verified == 0:
            return 0.0
        return self.status_matches / self.total_verified

    @property
    def surprise_rate(self) -> float:
        if self.total_verified == 0:
            return 0.0
        return (self.unexpected_failures + self.unexpected_successes) / self.total_verified

    def record(self, result: VerificationResult) -> None:
        """Record a verification result into running stats."""
        self.total_verified += 1
        if result.status_match:
            self.status_matches += 1
        else:
            self.status_mismatches += 1
        if result.content_match is True:
            self.content_matches += 1
        elif result.content_match is False:
            self.content_mismatches += 1
        if result.surprise == "unexpected_failure":
            self.unexpected_failures += 1
        elif result.surprise == "unexpected_success":
            self.unexpected_successes += 1

        # Per-tool tracking
        tool = result.tool
        if tool not in self.by_tool:
            self.by_tool[tool] = {"total": 0, "matches": 0, "surprises": 0}
        self.by_tool[tool]["total"] += 1
        if result.status_match:
            self.by_tool[tool]["matches"] += 1
        if result.surprise != "none":
            self.by_tool[tool]["surprises"] += 1

    def summary(self) -> str:
        """Human-readable summary for logging."""
        if self.total_verified == 0:
            return "No tool calls verified yet."
        return (
            f"Verified {self.total_verified} tool calls: "
            f"{self.match_rate:.0%} match rate, "
            f"{self.surprise_rate:.0%} surprise rate "
            f"({self.unexpected_failures} unexpected failures, "
            f"{self.unexpected_successes} unexpected successes)"
        )


# Module-level session stats (reset per orchestrator run)
_session_stats = VerificationStats()


def get_session_stats() -> VerificationStats:
    return _session_stats


def reset_session_stats() -> None:
    global _session_stats
    _session_stats = VerificationStats()
