"""Agent Run Log — CRT measurement layer for orchestrator execution.

Captures every orchestrator run: intent, steps, drift events,
verification gaps, completion status. Pure observation — no behavior changes.

This is Layer 1 of CRT-governed agent execution.
Layer 2: pre-step alignment checking
Layer 3: post-step contradiction detection
Layer 4: self-model beliefs from aggregated patterns

Usage:
    from personal_agent.agent_run_log import RunLog, RunStep, get_run_log_db

    log = RunLog(intent="Write a RAG system", thread_id="t_123")
    log.add_step(RunStep(action="tool_call", tool="file_read", ...))
    log.complete(success=True, confidence=0.8, user_feedback="works")

    db = get_run_log_db()
    db.store_run(log)
    analytics = db.get_analytics()
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .runtime_paths import resolve_agent_runs_db_path

# ---------------------------------------------------------------------------
# Alignment scoring — cosine similarity between intent and step reasoning
# ---------------------------------------------------------------------------

_encoder = None

def _get_encoder():
    """Lazy-load the sentence encoder (same one CRT uses)."""
    global _encoder
    if _encoder is None:
        try:
            from personal_agent.crt_core import encode_vector
            _encoder = encode_vector
        except ImportError:
            _encoder = False  # mark as unavailable
    return _encoder if _encoder is not False else None


_MAX_ALIGN_CHARS = 400  # ~250 tokens — semantic similarity stabilises in first few sentences


def score_alignment(intent: str, reasoning: str) -> Optional[float]:
    """Score how aligned a step's reasoning is with the original intent.

    Returns cosine similarity (0-1), or None if encoder unavailable.
    Higher = more aligned. Below 0.15 is suspicious drift.

    The reasoning is prefixed with a task-bridging phrase to improve alignment
    scoring for indirect tool use. Without this, "what matters to me?" vs
    "search memory for values/priorities" scores ~0.04 because the surface
    words don't overlap, even though the task is perfectly on-track.
    """
    encoder = _get_encoder()
    if encoder is None or not intent.strip() or not reasoning.strip():
        return None

    # Truncate before encoding to stay within model_max_length (512 tokens).
    intent_t = intent[:_MAX_ALIGN_CHARS]

    # Bridge the semantic gap: prepend a compressed intent echo to the reasoning
    # so the encoder sees "To answer [intent], I will [reasoning]" instead of
    # just "[reasoning]". This gives tool-mediated steps a fair alignment score.
    _intent_echo = intent[:80].strip()
    reasoning_bridged = f"To address '{_intent_echo}': {reasoning}"
    reasoning_t = reasoning_bridged[:_MAX_ALIGN_CHARS]

    try:
        import numpy as np
        intent_vec = np.array(encoder(intent_t), dtype=np.float32)
        reason_vec = np.array(encoder(reasoning_t), dtype=np.float32)

        norm_i = np.linalg.norm(intent_vec)
        norm_r = np.linalg.norm(reason_vec)
        if norm_i < 1e-8 or norm_r < 1e-8:
            return None

        sim = float(np.dot(intent_vec, reason_vec) / (norm_i * norm_r))
        return round(max(0.0, min(1.0, sim)), 4)
    except Exception:
        return None


def detect_step_contradictions(steps: List['RunStep'],
                              similarity_threshold: float = 0.6) -> List[tuple]:
    """Detect contradictions between steps.

    Looks for:
    1. Two steps operating on the same target with conflicting outcomes
    2. A think step asserting X, then a later step assuming not-X
    3. Sequential tool calls where the second undoes the first

    Returns list of (step_i, step_j, description) tuples.
    """
    contradictions = []
    encoder = _get_encoder()

    # Strategy 1: Same tool + same target + different outcomes
    tool_steps = [s for s in steps if s.action == "tool_call" and s.tool]
    for i, a in enumerate(tool_steps):
        for j, b in enumerate(tool_steps):
            if j <= i:
                continue
            # Same tool, same path/args but different status
            if (a.tool == b.tool
                    and a.status != b.status
                    and str(a.args) == str(b.args)):
                contradictions.append((
                    a.iteration, b.iteration,
                    f"Same tool call ({a.tool}) with same args: step {a.iteration} "
                    f"was {a.status}, step {b.iteration} was {b.status}"
                ))

    # Strategy 2: Think/reasoning contradictions via embedding similarity
    # Compare reasoning that mentions similar topics but with opposing conclusions
    if encoder:
        reasoning_steps = [(s, s.reasoning) for s in steps if s.reasoning.strip()]
        for i, (step_a, reason_a) in enumerate(reasoning_steps):
            for j, (step_b, reason_b) in enumerate(reasoning_steps):
                if j <= i:
                    continue
                try:
                    import numpy as np
                    vec_a = np.array(encoder(reason_a[:_MAX_ALIGN_CHARS]), dtype=np.float32)
                    vec_b = np.array(encoder(reason_b[:_MAX_ALIGN_CHARS]), dtype=np.float32)
                    norm_a = np.linalg.norm(vec_a)
                    norm_b = np.linalg.norm(vec_b)
                    if norm_a < 1e-8 or norm_b < 1e-8:
                        continue
                    sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

                    # High similarity in reasoning but conflicting outcomes
                    if sim > similarity_threshold:
                        # Only flag conflicting outcomes (not different tools —
                        # write→read→write is normal, not contradictory)
                        if step_a.status != step_b.status:
                            contradictions.append((
                                step_a.iteration, step_b.iteration,
                                f"Similar reasoning (sim={sim:.3f}) but conflicting outcomes: "
                                f"{step_a.status} vs {step_b.status}"
                            ))
                except Exception:
                    continue

    # Strategy 3: File write then different file write to same path (overwrite without reason)
    writes = [(s.iteration, (s.args or {}).get("path", ""))
              for s in steps if s.action == "tool_call" and s.tool == "file_write"]
    seen_paths = {}
    for iteration, path in writes:
        if path in seen_paths:
            contradictions.append((
                seen_paths[path], iteration,
                f"File '{path}' written twice — step {seen_paths[path]} then step {iteration}"
            ))
        seen_paths[path] = iteration

    return contradictions


def detect_drift(intent: str, steps: List['RunStep'],
                 threshold: float = 0.12) -> List['DriftEvent']:
    """Detect drift events by comparing step reasoning against intent.

    Flags steps where alignment drops significantly from the running average.
    Also flags steps where alignment is below absolute threshold.

    Note: threshold lowered from 0.15 to 0.12 because score_alignment now
    bridges intent→reasoning with "To address [intent]: [reasoning]", which
    raises legitimate tool-step scores from ~0.04 to ~0.3+. The 0.12 threshold
    now catches genuinely off-topic steps, not routine tool use.
    """
    drifts = []
    if not steps:
        return drifts

    scores = []
    for step in steps:
        if step.intent_alignment is not None:
            scores.append(step.intent_alignment)

            # Absolute threshold check
            if step.intent_alignment < threshold and step.action == "tool_call":
                drifts.append(DriftEvent(
                    at_step=step.iteration,
                    description=f"Low alignment ({step.intent_alignment:.3f}) for {step.tool or step.action}",
                    from_belief=intent[:100],
                    to_belief=step.reasoning[:100],
                    had_reasoning=bool(step.reasoning.strip()),
                ))

            # Relative drop check (>0.2 drop from running average)
            if len(scores) >= 3:
                avg = sum(scores[-3:]) / len(scores[-3:])
                if step.intent_alignment < avg - 0.2:
                    drifts.append(DriftEvent(
                        at_step=step.iteration,
                        description=f"Alignment dropped ({step.intent_alignment:.3f} vs avg {avg:.3f})",
                        from_belief=f"Running avg alignment: {avg:.3f}",
                        to_belief=step.reasoning[:100],
                        had_reasoning=bool(step.reasoning.strip()),
                    ))

    return drifts


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RunStep:
    """One step in an orchestrator run."""
    iteration: int
    action: str                      # tool_call, think, respond, ask_user
    tool: Optional[str] = None
    args: Optional[Dict] = None
    reasoning: str = ""
    result_preview: str = ""         # first 500 chars of result
    status: str = "ok"               # ok, error
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    # CRT measurements (Layer 1: just capture, don't act)
    intent_alignment: Optional[float] = None   # 0-1, how aligned with original intent
    contradicts_prior: Optional[str] = None    # step ID if contradicts a prior step
    verified: bool = False                      # did this step verify its own output?


@dataclass
class DriftEvent:
    """When the agent changes direction without explicit reasoning."""
    at_step: int
    description: str
    from_belief: str     # what the agent was doing/assuming before
    to_belief: str       # what it switched to
    had_reasoning: bool  # did Cookie explain why it changed direction?
    timestamp: float = field(default_factory=time.time)


@dataclass
class RunLog:
    """Complete log of one orchestrator run."""
    # Identity
    run_id: str = field(default_factory=lambda: f"run_{int(time.time()*1000)}_{os.getpid()}")
    thread_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Intent
    intent: str = ""                 # original user message / objective
    intent_type: str = ""            # inferred: code_gen, analysis, question, file_op, etc.

    # Execution
    steps: List[RunStep] = field(default_factory=list)
    drift_events: List[DriftEvent] = field(default_factory=list)
    total_iterations: int = 0
    hit_iteration_limit: bool = False

    # Tools used
    tools_called: List[str] = field(default_factory=list)
    unique_tools: int = 0
    tool_errors: int = 0

    # Timing
    brain_ms: float = 0.0
    tool_ms: float = 0.0
    total_ms: float = 0.0

    # Completion
    completed: bool = False
    success: Optional[bool] = None   # None = unknown, True/False = assessed
    confidence: float = 0.0          # agent's self-assessed confidence
    final_response_length: int = 0

    # Verification
    verification_steps: int = 0      # how many steps verified their output
    unverified_claims: int = 0       # assertions without evidence

    # User feedback (filled later if available)
    user_feedback: Optional[str] = None
    user_rating: Optional[float] = None  # 0-1

    # Provider
    brain_provider: str = ""

    def add_step(self, step: RunStep):
        self.steps.append(step)
        if step.tool:
            self.tools_called.append(step.tool)
        if step.status == "error":
            self.tool_errors += 1
        if step.verified:
            self.verification_steps += 1

    def add_drift(self, drift: DriftEvent):
        self.drift_events.append(drift)

    def complete(self, success: bool = True, confidence: float = 0.5,
                 response_length: int = 0):
        self.completed = True
        self.success = success
        self.confidence = confidence
        self.final_response_length = response_length
        self.total_iterations = len(self.steps)
        self.unique_tools = len(set(self.tools_called))
        self.total_ms = self.brain_ms + self.tool_ms

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Serialize complex fields
        d["steps"] = [asdict(s) for s in self.steps]
        d["drift_events"] = [asdict(de) for de in self.drift_events]
        return d


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

_DB_PATH = str(resolve_agent_runs_db_path())
_db_instance = None


class RunLogDB:
    """SQLite storage for agent run logs."""

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                thread_id TEXT,
                timestamp REAL NOT NULL,
                intent TEXT NOT NULL,
                intent_type TEXT,
                total_iterations INTEGER,
                hit_iteration_limit INTEGER DEFAULT 0,
                tools_called TEXT,
                unique_tools INTEGER,
                tool_errors INTEGER DEFAULT 0,
                brain_ms REAL,
                tool_ms REAL,
                total_ms REAL,
                completed INTEGER DEFAULT 0,
                success INTEGER,
                confidence REAL,
                final_response_length INTEGER,
                verification_steps INTEGER DEFAULT 0,
                unverified_claims INTEGER DEFAULT 0,
                drift_count INTEGER DEFAULT 0,
                user_feedback TEXT,
                user_rating REAL,
                brain_provider TEXT,
                steps_json TEXT,
                drift_json TEXT,
                metadata_json TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_thread ON agent_runs(thread_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON agent_runs(timestamp DESC)
        """)
        conn.commit()
        conn.close()

    def store_run(self, log: RunLog):
        """Store a completed run log."""
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO agent_runs (
                run_id, thread_id, timestamp, intent, intent_type,
                total_iterations, hit_iteration_limit,
                tools_called, unique_tools, tool_errors,
                brain_ms, tool_ms, total_ms,
                completed, success, confidence, final_response_length,
                verification_steps, unverified_claims, drift_count,
                user_feedback, user_rating, brain_provider,
                steps_json, drift_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log.run_id, log.thread_id, log.timestamp,
            log.intent, log.intent_type,
            log.total_iterations, int(log.hit_iteration_limit),
            json.dumps(log.tools_called), log.unique_tools, log.tool_errors,
            log.brain_ms, log.tool_ms, log.total_ms,
            int(log.completed), int(log.success) if log.success is not None else None,
            log.confidence, log.final_response_length,
            log.verification_steps, log.unverified_claims, len(log.drift_events),
            log.user_feedback, log.user_rating, log.brain_provider,
            json.dumps([asdict(s) for s in log.steps]),
            json.dumps([asdict(d) for d in log.drift_events]),
        ))
        conn.commit()
        conn.close()
        print(f"[RUN_LOG] Stored run {log.run_id}: {log.total_iterations} steps, "
              f"{'success' if log.success else 'incomplete'}, "
              f"{len(log.drift_events)} drifts, "
              f"{log.verification_steps}/{log.total_iterations} verified")

    def get_recent_runs(self, limit: int = 20) -> List[Dict]:
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_analytics(self) -> Dict[str, Any]:
        """Compute aggregate analytics across all runs."""
        conn = self._get_connection()
        cur = conn.cursor()

        stats = {}

        # Total runs
        cur.execute("SELECT COUNT(*) FROM agent_runs")
        stats["total_runs"] = cur.fetchone()[0]

        if stats["total_runs"] == 0:
            conn.close()
            return stats

        # Success rate
        cur.execute("SELECT AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) FROM agent_runs WHERE success IS NOT NULL")
        row = cur.fetchone()
        stats["success_rate"] = round(row[0], 3) if row[0] is not None else None

        # Average iterations
        cur.execute("SELECT AVG(total_iterations), MAX(total_iterations) FROM agent_runs")
        row = cur.fetchone()
        stats["avg_iterations"] = round(row[0], 1) if row[0] else 0
        stats["max_iterations"] = row[1] or 0

        # Hit iteration limit rate
        cur.execute("SELECT AVG(CAST(hit_iteration_limit AS REAL)) FROM agent_runs")
        row = cur.fetchone()
        stats["iteration_limit_rate"] = round(row[0], 3) if row[0] is not None else 0

        # Drift rate
        cur.execute("SELECT AVG(drift_count), SUM(drift_count) FROM agent_runs")
        row = cur.fetchone()
        stats["avg_drifts"] = round(row[0], 2) if row[0] else 0
        stats["total_drifts"] = row[1] or 0

        # Verification gap
        cur.execute("""
            SELECT AVG(CASE WHEN total_iterations > 0
                THEN CAST(verification_steps AS REAL) / total_iterations
                ELSE 0 END)
            FROM agent_runs
        """)
        row = cur.fetchone()
        stats["verification_rate"] = round(row[0], 3) if row[0] is not None else 0

        # Tool error rate
        cur.execute("SELECT AVG(CASE WHEN total_iterations > 0 THEN CAST(tool_errors AS REAL) / total_iterations ELSE 0 END) FROM agent_runs")
        row = cur.fetchone()
        stats["tool_error_rate"] = round(row[0], 3) if row[0] is not None else 0

        # Timing
        cur.execute("SELECT AVG(total_ms), AVG(brain_ms), AVG(tool_ms) FROM agent_runs")
        row = cur.fetchone()
        stats["avg_total_ms"] = round(row[0], 0) if row[0] else 0
        stats["avg_brain_ms"] = round(row[1], 0) if row[1] else 0
        stats["avg_tool_ms"] = round(row[2], 0) if row[2] else 0

        # Most used tools
        cur.execute("SELECT tools_called FROM agent_runs")
        tool_counts: Dict[str, int] = {}
        for row in cur.fetchall():
            try:
                tools = json.loads(row[0] or "[]")
                for t in tools:
                    tool_counts[t] = tool_counts.get(t, 0) + 1
            except json.JSONDecodeError:
                pass
        stats["tool_frequency"] = dict(sorted(tool_counts.items(), key=lambda x: -x[1])[:10])

        # Confidence calibration (agent confidence vs success)
        cur.execute("""
            SELECT confidence, success FROM agent_runs
            WHERE success IS NOT NULL AND confidence > 0
        """)
        calibration_data = [(r[0], r[1]) for r in cur.fetchall()]
        if calibration_data:
            high_conf = [s for c, s in calibration_data if c >= 0.7]
            low_conf = [s for c, s in calibration_data if c < 0.5]
            stats["calibration"] = {
                "high_confidence_success_rate": round(sum(high_conf) / len(high_conf), 3) if high_conf else None,
                "low_confidence_success_rate": round(sum(low_conf) / len(low_conf), 3) if low_conf else None,
                "samples": len(calibration_data),
            }

        conn.close()
        return stats

    def print_analytics(self):
        """Pretty-print analytics to console."""
        stats = self.get_analytics()
        print(f"\n{'='*60}")
        print("AGENT RUN ANALYTICS")
        print(f"{'='*60}")
        print(f"  Total runs: {stats.get('total_runs', 0)}")
        print(f"  Success rate: {stats.get('success_rate', 'N/A')}")
        print(f"  Avg iterations: {stats.get('avg_iterations', 0)} (max: {stats.get('max_iterations', 0)})")
        print(f"  Hit limit rate: {stats.get('iteration_limit_rate', 0):.1%}")
        print(f"  Drift rate: {stats.get('avg_drifts', 0)} avg per run ({stats.get('total_drifts', 0)} total)")
        print(f"  Verification rate: {stats.get('verification_rate', 0):.1%}")
        print(f"  Tool error rate: {stats.get('tool_error_rate', 0):.1%}")
        print(f"  Avg time: {stats.get('avg_total_ms', 0):.0f}ms (brain: {stats.get('avg_brain_ms', 0):.0f}ms, tools: {stats.get('avg_tool_ms', 0):.0f}ms)")
        if stats.get("tool_frequency"):
            print(f"  Top tools: {stats['tool_frequency']}")
        if stats.get("calibration"):
            cal = stats["calibration"]
            print(f"  Calibration ({cal['samples']} samples):")
            if cal.get("high_confidence_success_rate") is not None:
                print(f"    High conf (>=0.7): {cal['high_confidence_success_rate']:.1%} success")
            if cal.get("low_confidence_success_rate") is not None:
                print(f"    Low conf (<0.5): {cal['low_confidence_success_rate']:.1%} success")
        print(f"{'='*60}")


def get_run_log_db() -> RunLogDB:
    """Get or create the singleton RunLogDB."""
    global _db_instance
    if _db_instance is None:
        _db_instance = RunLogDB()
    return _db_instance
