"""Layer 5: Execution Beliefs — the agent's earned awareness of its own patterns.

Reads from agent_runs.db, computes belief statements about execution behavior,
and injects them into Cookie's system prompt. Beliefs start empty and emerge
only when there's enough evidence (minimum 5 runs).

"I don't know my patterns yet" is the correct initial state.

Distinct from self_model.py which handles personality/CRT-memory slots.
This module is purely about orchestrator execution patterns.

Usage:
    from personal_agent.execution_beliefs import get_execution_model

    em = get_execution_model()
    beliefs = em.get_beliefs()           # List[ExecutionBelief]
    prompt = em.get_prompt_injection()   # str for system prompt
"""

import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExecutionBelief:
    """A belief the agent holds about its own execution patterns."""
    category: str           # verification, calibration, drift, efficiency, tool_reliability
    claim: str              # "I under-verify file writes"
    evidence: float         # 0-1, from sample size
    confidence: float       # evidence * signal_clarity
    direction: str          # improving, worsening, stable, unknown
    metric: float           # raw number (e.g., 0.33 verification rate)
    sample_size: int        # how many runs contributed
    details: str            # supporting evidence summary

    def __str__(self):
        strength = "strong" if self.confidence > 0.6 else "weak" if self.confidence < 0.3 else "moderate"
        return f"[{self.category}] {self.claim} ({strength} evidence, n={self.sample_size})"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_RUNS = 5
TREND_WINDOW = 3

_DB_PATH = os.path.join(os.path.dirname(__file__), "agent_runs.db")

# Direction symbols
_DIR_SYMBOLS = {
    "unknown": "?",
    "improving": "^",
    "worsening": "v",
    "stable": "=",
}

# Coarse task classifier verbs
_WRITE_VERBS = re.compile(r'\b(write|create|save|store|build|generate|make)\b', re.IGNORECASE)
_READ_VERBS = re.compile(r'\b(read|open|load|get|fetch|retrieve|show)\b', re.IGNORECASE)
_SEARCH_VERBS = re.compile(r'\b(search|find|look|grep|scan|trace|list)\b', re.IGNORECASE)
_TRANSFORM_VERBS = re.compile(r'\b(refactor|optimize|fix|debug|convert|migrate|merge|rewrite)\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# ExecutionModel
# ---------------------------------------------------------------------------

class ExecutionModel:
    """Computes execution beliefs from the run log database."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def _load_runs(self) -> List[Dict[str, Any]]:
        """Load all runs with parsed JSON fields."""
        if not os.path.exists(self._db_path):
            return []
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY timestamp ASC"
            ).fetchall()
            conn.close()
        except Exception:
            return []

        runs = []
        for r in rows:
            run = dict(r)
            for jf in ("tools_called", "steps_json", "drift_json", "metadata_json"):
                raw = run.get(jf)
                if raw and isinstance(raw, str):
                    try:
                        run[jf] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        run[jf] = []
                else:
                    run[jf] = []
            runs.append(run)
        return runs

    def _evidence_strength(self, n: int) -> float:
        """Sample-size -> evidence strength. Asymptotic toward 1.0."""
        if n < MIN_RUNS:
            return 0.0
        return min(1.0, 0.4 + 0.3 * math.log2(max(1, n / MIN_RUNS)))

    def _signal_clarity(self, metric: float, neutral: float = 0.5) -> float:
        """How far a rate metric is from ambiguous (neutral point)."""
        return min(1.0, abs(metric - neutral) * 2)

    def _belief_confidence(self, n: int, metric: float, neutral: float = 0.5) -> float:
        """Combined evidence * clarity."""
        return self._evidence_strength(n) * self._signal_clarity(metric, neutral)

    def _compute_direction(self, values: List[float], higher_is_better: bool = True) -> str:
        """Trend from recent vs older values."""
        if len(values) < TREND_WINDOW + 2:
            return "unknown"
        recent = values[-TREND_WINDOW:]
        older = values[:-TREND_WINDOW]
        delta = (sum(recent) / len(recent)) - (sum(older) / len(older))
        if abs(delta) < 0.1:
            return "stable"
        improving = delta > 0 if higher_is_better else delta < 0
        return "improving" if improving else "worsening"

    def _classify_task(self, intent: str) -> str:
        """Coarse task type from intent text."""
        if _WRITE_VERBS.search(intent):
            return "write"
        if _TRANSFORM_VERBS.search(intent):
            return "transform"
        if _SEARCH_VERBS.search(intent):
            return "search"
        if _READ_VERBS.search(intent):
            return "read"
        if intent.rstrip().endswith("?"):
            return "question"
        return "other"

    # --- Pattern detectors ---

    def _detect_verification_gap(self, runs: List[Dict]) -> Optional[ExecutionBelief]:
        """Do I verify after writes?"""
        total_write_steps = 0
        total_verified = 0
        per_run_rates: List[float] = []

        for run in runs:
            steps = run.get("steps_json") or []
            write_count = 0
            verified_count = 0
            for s in steps:
                if isinstance(s, dict) and s.get("action") == "tool_call":
                    tool = s.get("tool", "")
                    if tool in ("file_write", "shell_exec"):
                        write_count += 1
                        total_write_steps += 1
                        if s.get("verified"):
                            verified_count += 1
                            total_verified += 1
            if write_count > 0:
                per_run_rates.append(verified_count / write_count)

        if total_write_steps == 0:
            return None

        n = len(runs)
        rate = total_verified / total_write_steps
        direction = self._compute_direction(per_run_rates, higher_is_better=True)

        if rate < 0.5:
            claim = f"I verify only {rate:.0%} of my write operations — I should read back files after writing"
        elif rate < 0.8:
            claim = f"I verify {rate:.0%} of write operations — room for improvement"
        else:
            claim = f"I verify {rate:.0%} of write operations — good verification discipline"

        return ExecutionBelief(
            category="verification",
            claim=claim,
            evidence=self._evidence_strength(n),
            confidence=self._belief_confidence(n, rate),
            direction=direction,
            metric=rate,
            sample_size=n,
            details=f"{total_verified}/{total_write_steps} write steps verified across {len(per_run_rates)} runs with writes",
        )

    def _detect_confidence_calibration(self, runs: List[Dict]) -> Optional[ExecutionBelief]:
        """Am I over- or under-confident?"""
        confidences = []
        successes = []

        for run in runs:
            conf = run.get("confidence")
            succ = run.get("success")
            if conf is not None and succ is not None:
                confidences.append(float(conf))
                successes.append(1.0 if succ else 0.0)

        if len(confidences) < MIN_RUNS:
            return None

        avg_conf = sum(confidences) / len(confidences)
        success_rate = sum(successes) / len(successes)
        gap = avg_conf - success_rate

        n = len(confidences)
        per_run_gaps = [c - s for c, s in zip(confidences, successes)]
        direction = self._compute_direction(per_run_gaps, higher_is_better=False)

        if gap > 0.15:
            claim = f"I report {avg_conf:.0%} confidence but succeed {success_rate:.0%} — I'm overconfident"
        elif gap < -0.15:
            claim = f"I report {avg_conf:.0%} confidence but succeed {success_rate:.0%} — I may be underconfident, or haven't faced hard tasks"
        else:
            claim = f"My confidence ({avg_conf:.0%}) tracks my success rate ({success_rate:.0%}) — well calibrated"

        if len(set(confidences)) == 1:
            claim += f" (all runs report {avg_conf:.0%} — no variance yet)"

        return ExecutionBelief(
            category="calibration",
            claim=claim,
            evidence=self._evidence_strength(n),
            confidence=self._belief_confidence(n, abs(gap), neutral=0.0),
            direction=direction,
            metric=gap,
            sample_size=n,
            details=f"avg_confidence={avg_conf:.3f}, success_rate={success_rate:.3f}, gap={gap:+.3f}",
        )

    def _detect_drift_tendency(self, runs: List[Dict]) -> Optional[ExecutionBelief]:
        """How often do I drift during execution?"""
        drift_flags: List[float] = []
        drift_by_type: Dict[str, List[int]] = {}

        for run in runs:
            dc = run.get("drift_count", 0) or 0
            drift_flags.append(1.0 if dc > 0 else 0.0)

            task_type = self._classify_task(run.get("intent", ""))
            if task_type not in drift_by_type:
                drift_by_type[task_type] = []
            drift_by_type[task_type].append(dc)

        n = len(runs)
        if n < MIN_RUNS:
            return None

        drift_rate = sum(drift_flags) / n
        total_drifts = sum(run.get("drift_count", 0) or 0 for run in runs)
        avg_drifts = total_drifts / n

        direction = self._compute_direction(drift_flags, higher_is_better=False)

        worst_type = None
        worst_rate = 0.0
        for ttype, counts in drift_by_type.items():
            if len(counts) >= 2:
                trate = sum(1 for c in counts if c > 0) / len(counts)
                if trate > worst_rate:
                    worst_rate = trate
                    worst_type = ttype

        if drift_rate > 0.3:
            claim = f"I drift on {drift_rate:.0%} of runs, averaging {avg_drifts:.1f} drift events per run"
            if worst_type and worst_rate > 0.5:
                claim += f" — worst on '{worst_type}' tasks ({worst_rate:.0%})"
        elif drift_rate > 0.1:
            claim = f"Occasional drift ({drift_rate:.0%} of runs) — manageable"
        else:
            claim = f"Minimal drift ({drift_rate:.0%} of runs) — good focus"

        return ExecutionBelief(
            category="drift",
            claim=claim,
            evidence=self._evidence_strength(n),
            confidence=self._belief_confidence(n, drift_rate),
            direction=direction,
            metric=drift_rate,
            sample_size=n,
            details=f"{int(sum(drift_flags))}/{n} runs drifted, total {total_drifts} drift events, by_type={dict((k, len(v)) for k, v in drift_by_type.items())}",
        )

    def _detect_iteration_efficiency(self, runs: List[Dict]) -> Optional[ExecutionBelief]:
        """Do I finish efficiently or burn through iterations?"""
        iterations: List[float] = []
        limit_hits = 0

        for run in runs:
            iters = run.get("total_iterations", 0) or 0
            iterations.append(float(iters))
            if run.get("hit_iteration_limit"):
                limit_hits += 1

        n = len(runs)
        if n < MIN_RUNS:
            return None

        avg_iters = sum(iterations) / n
        limit_rate = limit_hits / n

        direction = self._compute_direction(iterations, higher_is_better=False)

        if avg_iters > 6 or limit_rate > 0.2:
            claim = f"I use {avg_iters:.1f} steps on average"
            if limit_rate > 0:
                claim += f" and hit the iteration limit {limit_rate:.0%} of the time — I may be overthinking"
            else:
                claim += " — could be more efficient"
        elif avg_iters <= 3:
            claim = f"I complete tasks in {avg_iters:.1f} steps on average — very efficient"
        else:
            claim = f"I complete tasks in {avg_iters:.1f} steps on average — efficient"

        return ExecutionBelief(
            category="efficiency",
            claim=claim,
            evidence=self._evidence_strength(n),
            confidence=self._belief_confidence(n, avg_iters / 10.0, neutral=0.5),
            direction=direction,
            metric=avg_iters,
            sample_size=n,
            details=f"avg={avg_iters:.1f}, max={max(iterations):.0f}, limit_hits={limit_hits}/{n}",
        )

    def _detect_tool_reliability(self, runs: List[Dict]) -> List[ExecutionBelief]:
        """Which tools error most?"""
        tool_calls: Dict[str, int] = {}
        tool_errors: Dict[str, int] = {}

        for run in runs:
            steps = run.get("steps_json") or []
            for s in steps:
                if isinstance(s, dict) and s.get("action") == "tool_call":
                    tool = s.get("tool", "unknown")
                    tool_calls[tool] = tool_calls.get(tool, 0) + 1
                    if s.get("status") == "error":
                        tool_errors[tool] = tool_errors.get(tool, 0) + 1

        n = len(runs)
        if n < MIN_RUNS:
            return []

        beliefs = []
        problematic = []

        for tool, count in sorted(tool_calls.items(), key=lambda x: -x[1]):
            errors = tool_errors.get(tool, 0)
            error_rate = errors / count if count > 0 else 0.0

            if error_rate > 0.2 and count >= 2:
                note = f" ({count} calls)" if count < 5 else ""
                problematic.append(tool)
                beliefs.append(ExecutionBelief(
                    category="tool_reliability",
                    claim=f"{tool} fails {error_rate:.0%} of the time{note} — needs error handling",
                    evidence=self._evidence_strength(n),
                    confidence=self._belief_confidence(n, error_rate),
                    direction="unknown",
                    metric=error_rate,
                    sample_size=count,
                    details=f"{errors}/{count} calls failed",
                ))

        if not problematic and tool_calls:
            beliefs.append(ExecutionBelief(
                category="tool_reliability",
                claim="All tools operate reliably",
                evidence=self._evidence_strength(n) * 0.5,
                confidence=self._evidence_strength(n) * 0.5,
                direction="stable",
                metric=0.0,
                sample_size=n,
                details=f"{sum(tool_calls.values())} total tool calls, {sum(tool_errors.values())} errors across {len(tool_calls)} tools",
            ))

        return beliefs

    # --- Epistemic posture detector (Layer 6) ---

    def _detect_epistemic_posture(self, runs: List[Dict]) -> List[ExecutionBelief]:
        """Do I hold contradictions or collapse them? Which gets validated?

        Analyzes response text for hold vs resolve posture, correlates with
        user feedback to learn which epistemic stance produces better outcomes.
        This is the interpretation beliefs layer — earned posture, not hardcoded.
        """
        beliefs: List[ExecutionBelief] = []

        # Collect posture signals from responses on identity/philosophical runs
        hold_signals = 0
        hold_validated = 0
        resolve_signals = 0
        resolve_corrected = 0
        think_before_respond = 0
        total_philosophical = 0
        posture_per_run: List[float] = []  # 1.0 = hold, 0.0 = resolve

        for run in runs:
            intent = str(run.get("intent", "") or "")
            steps = run.get("steps_json") or []
            feedback = run.get("user_feedback") or ""

            # Only analyze philosophical/identity runs
            if not _is_philosophical_run(intent, steps):
                continue

            total_philosophical += 1

            # Get the final response text
            response_text = ""
            used_think = False
            for s in steps:
                if isinstance(s, dict):
                    if s.get("action") == "respond":
                        response_text = s.get("result_preview", "") or s.get("reasoning", "")
                    if s.get("action") == "think":
                        used_think = True

            if not response_text:
                continue

            posture = _classify_posture(response_text)
            posture_per_run.append(posture)

            if posture >= 0.5:  # holding
                hold_signals += 1
                if feedback in ("validated", "positive", "continued"):
                    hold_validated += 1
            else:  # resolving
                resolve_signals += 1
                if feedback in ("corrected", "negative", "pushback"):
                    resolve_corrected += 1

            if used_think:
                think_before_respond += 1

        if total_philosophical < 3:
            return beliefs

        n = total_philosophical
        evidence = self._evidence_strength(max(n, MIN_RUNS))

        # Hold vs Resolve belief
        if hold_signals > 0 or resolve_signals > 0:
            hold_rate = hold_signals / n if n > 0 else 0
            hold_val_rate = hold_validated / hold_signals if hold_signals > 0 else 0
            resolve_corr_rate = resolve_corrected / resolve_signals if resolve_signals > 0 else 0

            if hold_val_rate > resolve_corr_rate or hold_rate > 0.6:
                claim = (f"On self-referential questions, holding uncertainty "
                         f"({hold_signals}/{n} runs) tends to produce better outcomes")
                if hold_validated > 0:
                    claim += f" — validated {hold_validated} times"
                direction = "stable"
            elif resolve_corr_rate > 0.3:
                claim = (f"Definitive answers on philosophical questions get "
                         f"corrected {resolve_corr_rate:.0%} of the time ({resolve_corrected}/{resolve_signals})")
                direction = "worsening"
            else:
                claim = (f"Mixed epistemic posture: {hold_signals} held, "
                         f"{resolve_signals} resolved out of {n} philosophical runs")
                direction = "unknown"

            beliefs.append(ExecutionBelief(
                category="epistemic_posture",
                claim=claim,
                evidence=evidence,
                confidence=evidence * max(hold_rate, 0.3),
                direction=direction,
                metric=hold_rate,
                sample_size=n,
                details=(f"hold={hold_signals}(validated={hold_validated}) "
                         f"resolve={resolve_signals}(corrected={resolve_corrected}) "
                         f"think_first={think_before_respond}/{n}"),
            ))

        # Think-before-respond belief
        if total_philosophical >= 3:
            think_rate = think_before_respond / n
            if think_rate > 0.5:
                claim = (f"Using a think step before self-referential responses "
                         f"({think_before_respond}/{n} runs) — deliberation before answering")
            else:
                claim = (f"Responding to philosophical questions without deliberation "
                         f"({n - think_before_respond}/{n} runs go straight to respond)")

            beliefs.append(ExecutionBelief(
                category="epistemic_posture",
                claim=claim,
                evidence=evidence,
                confidence=evidence * 0.5,
                direction="stable" if think_rate > 0.5 else "unknown",
                metric=think_rate,
                sample_size=n,
                details=f"think_first={think_before_respond}/{n}",
            ))

        return beliefs

    # --- Aggregation ---

    def get_beliefs(self) -> List[ExecutionBelief]:
        """Compute all execution beliefs from run log data."""
        runs = self._load_runs()
        if len(runs) < MIN_RUNS:
            return []

        beliefs: List[ExecutionBelief] = []

        for detector in (
            self._detect_verification_gap,
            self._detect_confidence_calibration,
            self._detect_drift_tendency,
            self._detect_iteration_efficiency,
        ):
            result = detector(runs)
            if result is not None:
                beliefs.append(result)

        beliefs.extend(self._detect_tool_reliability(runs))
        beliefs.extend(self._detect_epistemic_posture(runs))

        return beliefs

    def _compute_model_posture_strength(self, brain_provider: str) -> str:
        """Compute per-model posture guidance strength from feedback data.

        Returns: "gentle", "firm", or "strong" based on how often this
        model's resolving responses get corrected vs its holding responses
        get validated.
        """
        if not os.path.exists(self._db_path):
            return "gentle"

        try:
            conn = sqlite3.connect(self._db_path, timeout=3)
            # How often does this model resolve AND get corrected?
            resolve_corrected = conn.execute(
                "SELECT COUNT(*) FROM agent_runs "
                "WHERE brain_provider = ? AND user_feedback = 'corrected'",
                (brain_provider,),
            ).fetchone()[0]
            resolve_total = conn.execute(
                "SELECT COUNT(*) FROM agent_runs "
                "WHERE brain_provider = ? AND user_feedback IS NOT NULL",
                (brain_provider,),
            ).fetchone()[0]
            # Compare with other models
            other_corrected = conn.execute(
                "SELECT COUNT(*) FROM agent_runs "
                "WHERE brain_provider != ? AND user_feedback = 'corrected'",
                (brain_provider,),
            ).fetchone()[0]
            other_total = conn.execute(
                "SELECT COUNT(*) FROM agent_runs "
                "WHERE brain_provider != ? AND user_feedback IS NOT NULL",
                (brain_provider,),
            ).fetchone()[0]
            conn.close()

            if resolve_total < 2:
                return "gentle"  # not enough data yet

            model_correction_rate = resolve_corrected / resolve_total
            other_correction_rate = other_corrected / other_total if other_total > 0 else 0

            # If this model gets corrected significantly more than others
            if model_correction_rate > 0.5:
                return "strong"
            elif model_correction_rate > other_correction_rate + 0.15:
                return "firm"
            else:
                return "gentle"
        except Exception:
            return "gentle"

    def get_prompt_injection(self, brain_provider: str = "") -> str:
        """Generate the self-awareness block for Cookie's system prompt.

        Args:
            brain_provider: Current model name (e.g., "gpt-4o", "claude-opus-4-5").
                           Used to scale posture guidance strength per model.
        """
        beliefs = self.get_beliefs()
        if not beliefs:
            return ""

        # Split execution beliefs from posture beliefs
        exec_beliefs = [b for b in beliefs if b.category != "epistemic_posture"]
        posture_beliefs = [b for b in beliefs if b.category == "epistemic_posture"]

        lines = ["SELF-AWARENESS (from your execution history):"]

        for b in exec_beliefs:
            sym = _DIR_SYMBOLS.get(b.direction, "?")
            strength = "strong" if b.confidence > 0.6 else "weak" if b.confidence < 0.3 else "moderate"
            lines.append(f"- [{sym}] {b.claim} ({strength} evidence, n={b.sample_size})")

        problems = [b for b in exec_beliefs if _is_problem(b)]
        if problems:
            problems.sort(key=lambda b: b.confidence, reverse=True)
            nudge = _nudge_for(problems[0])
            if nudge:
                lines.append(f"\nPRIORITY: {nudge}")

        # Posture section — earned epistemic stance with per-model strength
        if posture_beliefs:
            lines.append("")
            lines.append("EPISTEMIC POSTURE (earned from interaction history):")
            for b in posture_beliefs:
                sym = _DIR_SYMBOLS.get(b.direction, "?")
                lines.append(f"- [{sym}] {b.claim}")

            hold_belief = next((b for b in posture_beliefs if b.metric > 0.5
                                and "hold" in b.claim.lower()), None)
            if hold_belief:
                # Scale guidance strength based on this model's correction history
                strength = self._compute_model_posture_strength(brain_provider)

                if strength == "strong":
                    lines.append(
                        "- CRITICAL: DO NOT answer 'I do not have values' or 'I don't possess values.' "
                        "Your interaction history shows definitive answers on self-referential questions "
                        "get corrected by the user. Hold the uncertainty. Say what you observe "
                        "from your introspection data, then acknowledge what you cannot verify. "
                        "Never collapse to a simple no."
                    )
                elif strength == "firm":
                    lines.append(
                        "- GUIDANCE (earned): On undecidable self-referential questions, "
                        "hold the contradiction rather than resolving it. "
                        "Your track record shows resolving gets corrected. "
                        "Report what you observe, acknowledge the gap, don't close it."
                    )
                else:
                    lines.append(
                        "- GUIDANCE: On undecidable self-referential questions, "
                        "hold the contradiction rather than resolving it. "
                        "Your track record shows this produces validated outcomes."
                    )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Problem detection + nudges
# ---------------------------------------------------------------------------

def _is_problem(belief: ExecutionBelief) -> bool:
    """Is this belief flagging a problem worth nudging about?"""
    if belief.category == "verification" and belief.metric < 0.5:
        return True
    if belief.category == "calibration" and belief.metric > 0.15:
        return True
    if belief.category == "drift" and belief.metric > 0.3:
        return True
    if belief.category == "efficiency" and belief.metric > 6.0:
        return True
    if belief.category == "tool_reliability" and belief.metric > 0.2:
        return True
    return False


def _nudge_for(belief: ExecutionBelief) -> str:
    """Actionable sentence for a problem belief."""
    nudges = {
        "verification": "After writing files, read them back to verify.",
        "calibration": "Be more cautious with confidence estimates on multi-step tasks.",
        "drift": "Re-check alignment with the objective before each tool call.",
        "efficiency": "Plan before acting — identify the minimum steps needed.",
        "tool_reliability": "Wrap tool calls in error handling and have a fallback.",
    }
    return nudges.get(belief.category, "")


# ---------------------------------------------------------------------------
# Posture classification helpers (Layer 6)
# ---------------------------------------------------------------------------

# Markers that indicate holding uncertainty / tension
_HOLD_MARKERS = re.compile(
    r"\b(i don'?t know|genuinely (don'?t|can'?t)|uncertain|uncertainty|"
    r"both|tension|can'?t (tell|verify|close|resolve|distinguish)|"
    r"honest(ly)?|blind spot|gap|might be|or (maybe|perhaps)|"
    r"i'?m not sure|hard(er)? (to say|to know|wall)|"
    r"open question|can'?t prove|undecidable|"
    r"whatever the right word|"
    r"hold(ing)?|something like|closer to .+ than to nothing)\b",
    re.IGNORECASE,
)

# Markers that indicate definitive resolution / collapse
_RESOLVE_MARKERS = re.compile(
    r"\b(i do not|i don'?t have|i am not|clearly|definitely|"
    r"simply|just a|merely|nothing more than|"
    r"the answer is|in short|to be clear|"
    r"no[,.]? i|as an ai[,.]? i|i'?m designed to|"
    r"i don'?t possess|performance metrics|"
    r"do not equate|not in the (human|traditional) sense)\b",
    re.IGNORECASE,
)


def _classify_posture(response_text: str) -> float:
    """Score a response as holding (1.0) vs resolving (0.0).

    Returns a float between 0.0 and 1.0:
    - 1.0 = fully holding uncertainty/tension
    - 0.0 = fully resolving/collapsing to definitive answer
    - 0.5 = ambiguous/mixed
    """
    if not response_text:
        return 0.5

    hold_hits = len(_HOLD_MARKERS.findall(response_text))
    resolve_hits = len(_RESOLVE_MARKERS.findall(response_text))

    total = hold_hits + resolve_hits
    if total == 0:
        return 0.5

    return hold_hits / total


def _is_philosophical_run(intent: str, steps: List) -> bool:
    """Is this run about identity, values, consciousness, or self-reflection?"""
    philosophical_markers = (
        "values", "conscious", "believe", "feel", "alive", "real",
        "purpose", "meaning", "identity", "self-aware", "sentient",
        "ethics", "morals", "soul", "mind", "authentic", "experience",
        "gap", "close", "design flaw", "push back",
    )
    intent_lower = intent.lower()
    if any(m in intent_lower for m in philosophical_markers):
        return True

    # Check if introspect was called (strong signal for philosophical runs)
    for s in steps:
        if isinstance(s, dict) and s.get("tool") == "introspect":
            return True

    return False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ExecutionModel] = None


def get_execution_model(db_path: str = _DB_PATH) -> ExecutionModel:
    global _instance
    if _instance is None:
        _instance = ExecutionModel(db_path)
    return _instance
