"""Score the live CRT system from production databases.

Pure data analysis -- no LLM calls. Reads crt_memory_shared.db,
agent_runs.db, and retrieval_activations to compute health metrics
across six dimensions: retrieval, trust evolution, gate accuracy,
drift, governance bridge, and agent performance.

Each scoring function returns::

    {
        "score": float 0-1,
        "details": { ... },
        "recommendations": [str, ...],
    }
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import time
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _safe_json(raw: Optional[str], fallback=None):
    """Parse a JSON string, returning *fallback* on failure."""
    if not raw:
        return fallback if fallback is not None else []
    try:
        return json.loads(raw)
    except Exception:
        return fallback if fallback is not None else []


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# ProductionScorer
# ---------------------------------------------------------------------------

class ProductionScorer:
    """Score the live system from production databases."""

    def __init__(
        self,
        memory_db_path: str,
        agent_runs_db_path: str,
        activation_db_path: Optional[str] = None,
    ):
        self.memory_db_path = memory_db_path
        self.agent_runs_db_path = agent_runs_db_path
        # activation data lives in crt_memory_shared.db (retrieval_activations table)
        self.activation_db_path = activation_db_path or memory_db_path

    # -- helpers ---------------------------------------------------------------

    def _mem_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _agent_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.agent_runs_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _act_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.activation_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- public API ------------------------------------------------------------

    def score_all(self) -> Dict[str, Any]:
        """Run all production metrics and return a comprehensive report."""
        t0 = time.perf_counter()
        results: Dict[str, Any] = {}

        scorers = [
            ("retrieval", self.score_retrieval),
            ("trust_evolution", self.score_trust_evolution),
            ("gate_accuracy", self.score_gates),
            ("drift_health", self.score_drift),
            ("governance_bridge", self.score_governance_bridge),
            ("agent_performance", self.score_agent_runs),
        ]

        for name, fn in scorers:
            try:
                results[name] = fn()
            except Exception as exc:
                logger.warning("[production_scorer] %s failed: %s", name, exc)
                results[name] = {
                    "score": float("nan"),
                    "details": {"error": str(exc)},
                    "recommendations": [f"Fix {name} scorer: {exc}"],
                }

        elapsed = time.perf_counter() - t0
        results["_meta"] = {
            "scored_at": time.time(),
            "elapsed_s": round(elapsed, 3),
            "memory_db": self.memory_db_path,
            "agent_runs_db": self.agent_runs_db_path,
        }
        return results

    # -----------------------------------------------------------------------
    # 1. Retrieval health
    # -----------------------------------------------------------------------

    def score_retrieval(self) -> Dict[str, Any]:
        """Score retrieval quality from activation log data.

        Metrics:
        - avg_memories_per_query: mean memory count per retrieval
        - dead_memory_ratio: high-trust memories that never activate
        - co_activation_density: mean pairwise co-activation across queries
        - retrieval_gap_count: trust > 0.7 memories never seen in activations
        """
        conn_act = self._act_conn()
        conn_mem = self._mem_conn()

        try:
            # -- activations ---------------------------------------------------
            rows = conn_act.execute(
                "SELECT memory_ids_json, scores_json, trusts_json, memory_count "
                "FROM retrieval_activations"
            ).fetchall()

            n_queries = len(rows)
            if n_queries == 0:
                return {
                    "score": 0.5,
                    "details": {"n_queries": 0, "note": "No activation data yet"},
                    "recommendations": ["Generate retrieval activations by using the system"],
                }

            total_memories = sum(r["memory_count"] or 0 for r in rows)
            avg_per_query = total_memories / n_queries

            # Build set of all activated memory IDs
            activated_ids: set = set()
            for r in rows:
                ids = _safe_json(r["memory_ids_json"])
                activated_ids.update(ids)

            # -- dead memories -------------------------------------------------
            high_trust = conn_mem.execute(
                "SELECT memory_id FROM memories "
                "WHERE trust > 0.7 AND deprecated = 0"
            ).fetchall()
            high_trust_ids = {r["memory_id"] for r in high_trust}
            total_high_trust = len(high_trust_ids)
            dead_ids = high_trust_ids - activated_ids
            dead_ratio = len(dead_ids) / total_high_trust if total_high_trust else 0.0

            # -- co-activation density -----------------------------------------
            # How many memories appear together across queries (mean pair count)
            pair_counts: List[int] = []
            for r in rows:
                ids = _safe_json(r["memory_ids_json"])
                n = len(ids)
                pair_counts.append(n * (n - 1) // 2 if n > 1 else 0)
            co_activation = mean(pair_counts) if pair_counts else 0.0

            # -- composite score -----------------------------------------------
            # Good retrieval: high avg memories, low dead ratio
            # avg_per_query score: 5+ memories per query = 1.0, 0 = 0.0
            avg_score = _clamp(avg_per_query / 5.0)
            # dead ratio score: 0% dead = 1.0, 100% dead = 0.0
            dead_score = 1.0 - _clamp(dead_ratio)
            # Weighted composite
            score = 0.5 * avg_score + 0.5 * dead_score

            recommendations = []
            if dead_ratio > 0.5:
                recommendations.append(
                    f"{len(dead_ids)} high-trust memories never activate -- "
                    "review embedding quality or memory relevance"
                )
            if avg_per_query < 2.0:
                recommendations.append(
                    "Low memories per query -- consider lowering retrieval threshold"
                )

            return {
                "score": round(score, 3),
                "details": {
                    "n_queries": n_queries,
                    "avg_memories_per_query": round(avg_per_query, 2),
                    "dead_memory_ratio": round(dead_ratio, 3),
                    "dead_memory_count": len(dead_ids),
                    "total_high_trust": total_high_trust,
                    "co_activation_density": round(co_activation, 2),
                    "total_activated_unique": len(activated_ids),
                },
                "recommendations": recommendations,
            }
        finally:
            conn_act.close()
            conn_mem.close()

    # -----------------------------------------------------------------------
    # 2. Trust evolution
    # -----------------------------------------------------------------------

    def score_trust_evolution(self) -> Dict[str, Any]:
        """Score trust evolution health from trust_log.

        Metrics:
        - trust_volatility: per-memory std dev of deltas (high = unstable)
        - governance_penalty_count: governance_bridge drift penalties applied
        - mean_trust_trajectory: avg direction of trust changes (+up, -down)
        - oscillating_memory_count: memories with std_dev > 0.15
        """
        conn = self._mem_conn()

        try:
            rows = conn.execute(
                "SELECT memory_id, old_trust, new_trust, reason "
                "FROM trust_log ORDER BY timestamp"
            ).fetchall()

            if not rows:
                return {
                    "score": 0.5,
                    "details": {"n_log_entries": 0, "note": "No trust log data"},
                    "recommendations": ["Trust log empty -- system may be freshly initialized"],
                }

            # Per-memory deltas
            deltas_by_mem: Dict[str, List[float]] = {}
            governance_penalties = 0
            contested_caps = 0

            for r in rows:
                mid = r["memory_id"]
                delta = (r["new_trust"] or 0) - (r["old_trust"] or 0)
                deltas_by_mem.setdefault(mid, []).append(delta)

                reason = r["reason"] or ""
                if "governance_bridge:drift_penalty" in reason:
                    governance_penalties += 1
                if "contested_cap_applied" in reason:
                    contested_caps += 1

            # Volatility per memory
            volatilities: List[float] = []
            for mid, deltas in deltas_by_mem.items():
                if len(deltas) >= 2:
                    volatilities.append(stdev(deltas))

            mean_volatility = mean(volatilities) if volatilities else 0.0
            oscillating = sum(1 for v in volatilities if v > 0.15)

            # Mean trajectory
            all_deltas = [d for ds in deltas_by_mem.values() for d in ds]
            mean_trajectory = mean(all_deltas) if all_deltas else 0.0

            # Score: low volatility + positive trajectory = good
            # Volatility score: 0 vol = 1.0, 0.3+ vol = 0.0
            vol_score = _clamp(1.0 - mean_volatility / 0.3)
            # Trajectory score: slightly positive is ideal
            traj_score = _clamp(0.5 + mean_trajectory * 5)  # center at 0.5
            # Oscillation penalty
            osc_ratio = oscillating / len(volatilities) if volatilities else 0.0
            osc_score = 1.0 - _clamp(osc_ratio)

            score = 0.4 * vol_score + 0.3 * traj_score + 0.3 * osc_score

            recommendations = []
            if mean_volatility > 0.2:
                recommendations.append(
                    f"High trust volatility ({mean_volatility:.3f}) -- "
                    "memories are flip-flopping, check drift governance"
                )
            if oscillating > 10:
                recommendations.append(
                    f"{oscillating} memories oscillating (std > 0.15) -- "
                    "review compaction_decay and alignment update rates"
                )
            if governance_penalties > 50:
                recommendations.append(
                    f"High governance penalty count ({governance_penalties}) -- "
                    "many topics triggering drift penalties"
                )

            return {
                "score": round(score, 3),
                "details": {
                    "n_log_entries": len(rows),
                    "n_memories_tracked": len(deltas_by_mem),
                    "mean_trust_volatility": round(mean_volatility, 4),
                    "oscillating_memory_count": oscillating,
                    "oscillating_ratio": round(osc_ratio, 3),
                    "mean_trust_trajectory": round(mean_trajectory, 5),
                    "governance_penalty_count": governance_penalties,
                    "contested_cap_count": contested_caps,
                },
                "recommendations": recommendations,
            }
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 3. Gate accuracy
    # -----------------------------------------------------------------------

    def score_gates(self) -> Dict[str, Any]:
        """Score gate accuracy from agent_runs.db.

        Uses the belief_speech table to approximate gate pass/fail,
        and agent_runs for explicit gate data if available.
        """
        conn_agent = self._agent_conn()
        conn_mem = self._mem_conn()

        try:
            # From agent_runs: runs with success/completed flags
            runs = conn_agent.execute(
                "SELECT success, completed, confidence, verification_steps, "
                "unverified_claims, transformation_verified "
                "FROM agent_runs"
            ).fetchall()

            n_runs = len(runs)
            if n_runs == 0:
                return {
                    "score": 0.5,
                    "details": {"n_runs": 0, "note": "No agent runs recorded"},
                    "recommendations": ["No agent runs -- use the system to generate data"],
                }

            completed = sum(1 for r in runs if r["completed"])
            successful = sum(1 for r in runs if r["success"])
            verified = sum(1 for r in runs if r["verification_steps"] and r["verification_steps"] > 0)
            unverified_total = sum(r["unverified_claims"] or 0 for r in runs)
            transform_verified = sum(1 for r in runs if r["transformation_verified"])

            # From belief_speech: belief vs speech ratio as proxy for gate behavior
            bs_rows = conn_mem.execute(
                "SELECT is_belief, trust_avg FROM belief_speech"
            ).fetchall()

            n_belief = sum(1 for r in bs_rows if r["is_belief"])
            n_speech = sum(1 for r in bs_rows if not r["is_belief"])
            total_bs = len(bs_rows)

            # Gate utilization: belief ratio (beliefs passing the gate)
            belief_ratio = n_belief / total_bs if total_bs else 0.0

            # Gate precision proxy: success rate among completed runs
            success_rate = successful / completed if completed else 0.0

            # Always-pass detection: if belief ratio > 0.95, gate may be too permissive
            # Always-fail detection: if belief ratio < 0.05, gate may be too strict
            gate_balance_score = 1.0
            if belief_ratio > 0.95:
                gate_balance_score = 0.5  # too permissive
            elif belief_ratio < 0.05 and total_bs > 10:
                gate_balance_score = 0.3  # too strict

            # Verification quality
            verification_rate = verified / n_runs if n_runs else 0.0

            score = (
                0.35 * success_rate
                + 0.25 * gate_balance_score
                + 0.20 * _clamp(verification_rate)
                + 0.20 * _clamp(1.0 - unverified_total / max(n_runs, 1))
            )

            recommendations = []
            if success_rate < 0.7:
                recommendations.append(
                    f"Low success rate ({success_rate:.1%}) -- "
                    "agent runs are frequently failing"
                )
            if belief_ratio > 0.95:
                recommendations.append(
                    "Gate almost always passes (belief ratio > 95%) -- "
                    "gate may be too permissive"
                )
            if belief_ratio < 0.05 and total_bs > 10:
                recommendations.append(
                    "Gate almost never passes (belief ratio < 5%) -- "
                    "gate may be too strict, most responses are speech"
                )
            if unverified_total > n_runs * 0.3:
                recommendations.append(
                    f"High unverified claims ({unverified_total}) -- "
                    "verification pipeline may need attention"
                )

            return {
                "score": round(_clamp(score), 3),
                "details": {
                    "n_agent_runs": n_runs,
                    "completed": completed,
                    "successful": successful,
                    "success_rate": round(success_rate, 3),
                    "verification_rate": round(verification_rate, 3),
                    "unverified_claims_total": unverified_total,
                    "transformation_verified_count": transform_verified,
                    "belief_speech_total": total_bs,
                    "belief_count": n_belief,
                    "speech_count": n_speech,
                    "belief_ratio": round(belief_ratio, 3),
                    "gate_balance_score": round(gate_balance_score, 3),
                },
                "recommendations": recommendations,
            }
        finally:
            conn_agent.close()
            conn_mem.close()

    # -----------------------------------------------------------------------
    # 4. Drift health
    # -----------------------------------------------------------------------

    def score_drift(self) -> Dict[str, Any]:
        """Score drift health from agent_runs.db drift data.

        Metrics:
        - drift_rate: fraction of runs with any drift
        - avg_drifts_per_run: mean drift_count across runs
        - execution_drift_events: total drift events from drift_json
        """
        conn = self._agent_conn()

        try:
            rows = conn.execute(
                "SELECT drift_count, drift_json, total_iterations, success "
                "FROM agent_runs"
            ).fetchall()

            n_runs = len(rows)
            if n_runs == 0:
                return {
                    "score": 0.5,
                    "details": {"n_runs": 0, "note": "No agent run data"},
                    "recommendations": ["No data -- use the system to generate runs"],
                }

            total_drifts = sum(r["drift_count"] or 0 for r in rows)
            runs_with_drift = sum(1 for r in rows if (r["drift_count"] or 0) > 0)
            drift_rate = runs_with_drift / n_runs

            avg_drifts = total_drifts / n_runs

            # Parse drift_json for richer detail
            drift_events: List[Dict] = []
            for r in rows:
                events = _safe_json(r["drift_json"])
                if isinstance(events, list):
                    drift_events.extend(events)

            # Drift-success correlation
            drift_successes = sum(
                1 for r in rows
                if (r["drift_count"] or 0) > 0 and r["success"]
            )
            drift_success_rate = (
                drift_successes / runs_with_drift if runs_with_drift else 1.0
            )

            # Score: low drift = healthy. Some drift is tolerable.
            # drift_rate < 0.1 = great, > 0.5 = concerning
            rate_score = _clamp(1.0 - drift_rate / 0.5)
            # avg drifts < 0.5 = great, > 3 = bad
            avg_score = _clamp(1.0 - avg_drifts / 3.0)

            score = 0.6 * rate_score + 0.4 * avg_score

            recommendations = []
            if drift_rate > 0.3:
                recommendations.append(
                    f"High drift rate ({drift_rate:.1%}) -- "
                    "over 30% of runs experience drift, check intent alignment"
                )
            if avg_drifts > 2.0:
                recommendations.append(
                    f"High avg drifts per run ({avg_drifts:.1f}) -- "
                    "runs are drifting multiple times"
                )
            if drift_success_rate < 0.5 and runs_with_drift > 5:
                recommendations.append(
                    f"Drift-success rate only {drift_success_rate:.1%} -- "
                    "drifted runs often fail, drift recovery is weak"
                )

            return {
                "score": round(_clamp(score), 3),
                "details": {
                    "n_runs": n_runs,
                    "runs_with_drift": runs_with_drift,
                    "drift_rate": round(drift_rate, 3),
                    "total_drift_events": total_drifts,
                    "avg_drifts_per_run": round(avg_drifts, 3),
                    "drift_event_details_count": len(drift_events),
                    "drift_success_rate": round(drift_success_rate, 3),
                },
                "recommendations": recommendations,
            }
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 5. Governance bridge
    # -----------------------------------------------------------------------

    def score_governance_bridge(self) -> Dict[str, Any]:
        """Score governance bridge health from trust_log entries.

        Looks for governance_bridge:drift_penalty and contested_cap_applied
        entries which indicate active governance enforcement.
        """
        conn = self._mem_conn()

        try:
            # Governance bridge penalties
            penalty_rows = conn.execute(
                "SELECT reason, old_trust, new_trust, timestamp "
                "FROM trust_log "
                "WHERE reason LIKE '%governance_bridge%'"
            ).fetchall()

            # Contested cap entries
            contested_rows = conn.execute(
                "SELECT reason, old_trust, new_trust "
                "FROM trust_log "
                "WHERE reason LIKE 'contested_cap_applied%'"
            ).fetchall()

            # Total trust log size for context
            total_log = conn.execute("SELECT COUNT(*) FROM trust_log").fetchone()[0]

            n_penalties = len(penalty_rows)
            n_contested = len(contested_rows)

            # Parse topic info from penalty reasons
            topics_flagged: set = set()
            for r in penalty_rows:
                reason = r["reason"] or ""
                match = re.search(r"topic=(\d+)", reason)
                if match:
                    topics_flagged.add(int(match.group(1)))

            # Trust impact of governance actions
            penalty_deltas = [
                (r["new_trust"] or 0) - (r["old_trust"] or 0)
                for r in penalty_rows
            ]
            contested_deltas = [
                (r["new_trust"] or 0) - (r["old_trust"] or 0)
                for r in contested_rows
            ]

            avg_penalty_delta = mean(penalty_deltas) if penalty_deltas else 0.0
            avg_contested_delta = mean(contested_deltas) if contested_deltas else 0.0

            # Score interpretation:
            # Some governance activity = healthy (the bridge is working)
            # No activity at all = either perfect system or bridge not wired
            # Excessive activity = too much instability
            governance_ratio = (n_penalties + n_contested) / max(total_log, 1)

            if total_log < 10:
                score = 0.5
                note = "Too little data to assess governance bridge"
            elif governance_ratio == 0:
                score = 0.4
                note = "No governance actions detected -- bridge may be inactive"
            elif governance_ratio < 0.05:
                score = 0.9
                note = "Healthy governance -- active but not excessive"
            elif governance_ratio < 0.15:
                score = 0.7
                note = "Moderate governance activity -- within normal range"
            else:
                score = 0.4
                note = "Excessive governance activity -- system may be unstable"

            recommendations = []
            if governance_ratio == 0 and total_log > 100:
                recommendations.append(
                    "No governance bridge penalties in trust log -- "
                    "verify drift governance is wired and running"
                )
            if governance_ratio > 0.15:
                recommendations.append(
                    f"Governance ratio {governance_ratio:.1%} is high -- "
                    "too many topics triggering drift penalties"
                )
            if n_contested > n_penalties * 2 and n_contested > 10:
                recommendations.append(
                    f"Contested caps ({n_contested}) outnumber penalties ({n_penalties}) -- "
                    "many memories hitting contested trust ceiling"
                )

            return {
                "score": round(_clamp(score), 3),
                "details": {
                    "total_trust_log_entries": total_log,
                    "governance_penalty_count": n_penalties,
                    "contested_cap_count": n_contested,
                    "governance_ratio": round(governance_ratio, 4),
                    "topics_flagged": len(topics_flagged),
                    "avg_penalty_trust_delta": round(avg_penalty_delta, 4),
                    "avg_contested_trust_delta": round(avg_contested_delta, 4),
                    "note": note,
                },
                "recommendations": recommendations,
            }
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 6. Agent performance
    # -----------------------------------------------------------------------

    def score_agent_runs(self) -> Dict[str, Any]:
        """Score agent execution quality from agent_runs.db.

        Metrics:
        - success_rate: fraction completed and successful
        - avg_iterations: mean iterations per run (lower = more efficient)
        - tool_error_rate: tool_errors / total tool calls
        - verification_rate: fraction of runs with verification steps
        - transformation_verification_rate: fraction with transform verified
        """
        conn = self._agent_conn()

        try:
            rows = conn.execute(
                "SELECT success, completed, total_iterations, hit_iteration_limit, "
                "tools_called, unique_tools, tool_errors, brain_ms, tool_ms, total_ms, "
                "confidence, verification_steps, unverified_claims, "
                "transformation_verified, brain_provider, steps_json "
                "FROM agent_runs"
            ).fetchall()

            n_runs = len(rows)
            if n_runs == 0:
                return {
                    "score": 0.5,
                    "details": {"n_runs": 0, "note": "No agent runs recorded"},
                    "recommendations": ["No data available"],
                }

            completed = sum(1 for r in rows if r["completed"])
            successful = sum(1 for r in rows if r["success"])
            hit_limit = sum(1 for r in rows if r["hit_iteration_limit"])

            success_rate = successful / n_runs
            completion_rate = completed / n_runs

            # Iterations
            iterations = [r["total_iterations"] or 0 for r in rows]
            avg_iterations = mean(iterations)

            # Tool errors
            total_tool_calls = 0
            total_tool_errors = sum(r["tool_errors"] or 0 for r in rows)
            for r in rows:
                tools = _safe_json(r["tools_called"])
                if isinstance(tools, list):
                    total_tool_calls += len(tools)
            tool_error_rate = (
                total_tool_errors / total_tool_calls if total_tool_calls else 0.0
            )

            # Timing
            total_ms_vals = [r["total_ms"] or 0 for r in rows if r["total_ms"]]
            avg_total_ms = mean(total_ms_vals) if total_ms_vals else 0.0
            brain_ms_vals = [r["brain_ms"] or 0 for r in rows if r["brain_ms"]]
            avg_brain_ms = mean(brain_ms_vals) if brain_ms_vals else 0.0

            # Verification
            verified = sum(
                1 for r in rows
                if r["verification_steps"] and r["verification_steps"] > 0
            )
            verification_rate = verified / n_runs
            transform_verified = sum(1 for r in rows if r["transformation_verified"])
            transform_rate = transform_verified / n_runs

            # Confidence
            confidences = [r["confidence"] for r in rows if r["confidence"] is not None]
            avg_confidence = mean(confidences) if confidences else 0.0

            # Providers used
            providers: Dict[str, int] = {}
            for r in rows:
                p = r["brain_provider"] or "unknown"
                providers[p] = providers.get(p, 0) + 1

            # Composite score
            success_score = success_rate
            efficiency_score = _clamp(1.0 - (avg_iterations - 1) / 9)  # 1 iter = 1.0, 10 = 0.0
            error_score = 1.0 - _clamp(tool_error_rate / 0.2)  # 0% = 1.0, 20%+ = 0.0
            limit_penalty = 1.0 - _clamp(hit_limit / max(n_runs, 1) / 0.2)

            score = (
                0.35 * success_score
                + 0.25 * efficiency_score
                + 0.20 * error_score
                + 0.20 * limit_penalty
            )

            recommendations = []
            if success_rate < 0.7:
                recommendations.append(
                    f"Low success rate ({success_rate:.1%}) -- "
                    "investigate common failure patterns in steps_json"
                )
            if avg_iterations > 5:
                recommendations.append(
                    f"High avg iterations ({avg_iterations:.1f}) -- "
                    "agent may be looping or inefficient"
                )
            if tool_error_rate > 0.1:
                recommendations.append(
                    f"Tool error rate {tool_error_rate:.1%} -- "
                    "check tool implementations for reliability"
                )
            if hit_limit > n_runs * 0.1:
                recommendations.append(
                    f"{hit_limit} runs hit iteration limit -- "
                    "consider raising limit or improving convergence"
                )
            if verification_rate < 0.3 and n_runs > 10:
                recommendations.append(
                    f"Low verification rate ({verification_rate:.1%}) -- "
                    "most runs skip verification steps"
                )

            return {
                "score": round(_clamp(score), 3),
                "details": {
                    "n_runs": n_runs,
                    "completed": completed,
                    "successful": successful,
                    "success_rate": round(success_rate, 3),
                    "completion_rate": round(completion_rate, 3),
                    "hit_iteration_limit": hit_limit,
                    "avg_iterations": round(avg_iterations, 2),
                    "total_tool_calls": total_tool_calls,
                    "total_tool_errors": total_tool_errors,
                    "tool_error_rate": round(tool_error_rate, 4),
                    "avg_total_ms": round(avg_total_ms, 1),
                    "avg_brain_ms": round(avg_brain_ms, 1),
                    "verification_rate": round(verification_rate, 3),
                    "transformation_verification_rate": round(transform_rate, 3),
                    "avg_confidence": round(avg_confidence, 3),
                    "providers": providers,
                },
                "recommendations": recommendations,
            }
        finally:
            conn.close()
