"""
Verified Self-Audit Mode
========================

Unified self-audit combining all governance, execution, and belief checks
into a single coherent report. Detects cross-system anomalies that individual
checks miss.

Run independently:
    python -m personal_agent.verified_self_audit

Or via heartbeat:
    auditor = VerifiedSelfAuditor()
    report = auditor.audit(thread_id)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

@dataclass
class AuditAnomaly:
    """A detected cross-system inconsistency."""
    source: str          # which subsystem detected it
    severity: str        # "info" | "warning" | "critical"
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedAuditReport:
    """Comprehensive self-audit result."""
    timestamp: float = field(default_factory=time.time)
    thread_id: str = ""

    # Subsystem results
    execution_state: Dict[str, str] = field(default_factory=dict)
    self_model_slots: Dict[str, Any] = field(default_factory=dict)
    execution_beliefs: List[Dict[str, Any]] = field(default_factory=list)
    governance_status: Dict[str, str] = field(default_factory=dict)
    memory_health: Dict[str, Any] = field(default_factory=dict)

    # Cross-system findings
    anomalies: List[AuditAnomaly] = field(default_factory=list)

    # Summary
    overall_health: float = 1.0  # 0.0-1.0
    checks_run: int = 0
    checks_passed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "overall_health": round(self.overall_health, 3),
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "anomaly_count": len(self.anomalies),
            "anomalies": [
                {"source": a.source, "severity": a.severity,
                 "description": a.description, "evidence": a.evidence}
                for a in self.anomalies
            ],
            "execution_state": self.execution_state,
            "self_model_slots": self.self_model_slots,
            "execution_beliefs_count": len(self.execution_beliefs),
            "governance_status": self.governance_status,
            "memory_health": self.memory_health,
        }


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

class VerifiedSelfAuditor:
    """
    Unified self-audit across all governance layers.

    Checks:
    1. Execution state (models reachable, agent loop status)
    2. Self-model slot health (evidence-backed vs stale)
    3. Execution beliefs vs actual run data
    4. Governance agent availability
    5. Memory system health (deprecated ratio, contradiction load)
    6. Cross-system anomalies (beliefs contradict execution data)
    """

    def audit(self, thread_id: str = "default") -> VerifiedAuditReport:
        report = VerifiedAuditReport(thread_id=thread_id)

        self._check_execution_state(report)
        self._check_self_model(report)
        self._check_execution_beliefs(report)
        self._check_governance(report)
        self._check_memory_health(report)
        self._cross_validate(report)

        # Compute overall health
        if report.checks_run > 0:
            base = report.checks_passed / report.checks_run
            # Penalize for anomalies
            critical = sum(1 for a in report.anomalies if a.severity == "critical")
            warnings = sum(1 for a in report.anomalies if a.severity == "warning")
            penalty = critical * 0.15 + warnings * 0.05
            report.overall_health = round(max(0.0, min(1.0, base - penalty)), 3)

        return report

    # ----- 1. Execution State -----

    def _check_execution_state(self, report: VerifiedAuditReport):
        """Verify runtime systems are reachable."""
        try:
            from personal_agent.self_model import verify_execution_state
            state = verify_execution_state()
            report.execution_state = state
            report.checks_run += 1

            # Check for problems
            if state.get("agent_loop") == "disabled":
                report.anomalies.append(AuditAnomaly(
                    source="execution_state",
                    severity="warning",
                    description="Agent loop reports disabled",
                    evidence=state,
                ))
            else:
                report.checks_passed += 1

            if state.get("claude_cli", "").startswith("unavailable"):
                report.anomalies.append(AuditAnomaly(
                    source="execution_state",
                    severity="info",
                    description="Claude CLI not available (dispatch won't work)",
                ))
        except Exception as e:
            report.checks_run += 1
            report.anomalies.append(AuditAnomaly(
                source="execution_state",
                severity="critical",
                description=f"verify_execution_state() failed: {e}",
            ))

    # ----- 2. Self-Model Slots -----

    def _check_self_model(self, report: VerifiedAuditReport):
        """Check self-model slot health."""
        try:
            from personal_agent.self_model import get_self_model
            sm = get_self_model()
            slots = sm.get_all_slots() if hasattr(sm, 'get_all_slots') else {}

            report.self_model_slots = {
                k: {"value": str(v)[:100], "set": bool(v and v != "(not yet set)")}
                for k, v in slots.items()
            } if slots else {}

            report.checks_run += 1
            populated = sum(1 for v in report.self_model_slots.values() if v["set"])
            total = len(report.self_model_slots)

            if populated == 0 and total > 0:
                report.anomalies.append(AuditAnomaly(
                    source="self_model",
                    severity="warning",
                    description=f"No self-model slots populated (0/{total})",
                ))
            else:
                report.checks_passed += 1
                if populated < total * 0.5:
                    report.anomalies.append(AuditAnomaly(
                        source="self_model",
                        severity="info",
                        description=f"Only {populated}/{total} self-model slots populated",
                    ))
        except Exception as e:
            report.checks_run += 1
            logger.debug(f"[SELF_AUDIT] self_model check failed: {e}")

    # ----- 3. Execution Beliefs vs Reality -----

    def _check_execution_beliefs(self, report: VerifiedAuditReport):
        """Validate execution beliefs against actual run data."""
        try:
            from personal_agent.execution_beliefs import get_execution_model
            em = get_execution_model()
            beliefs = em.get_beliefs() if hasattr(em, 'get_beliefs') else []
            report.execution_beliefs = [
                {"category": b.category, "description": b.description,
                 "confidence": b.confidence, "direction": b.direction}
                for b in beliefs
            ] if beliefs else []

            report.checks_run += 1

            # Cross-check: if we claim "I verify writes" but verification_gap > 0.5
            for b in beliefs:
                if b.category == "verification" and b.confidence > 0.5:
                    # Check actual verification rate from runs
                    try:
                        from personal_agent.agent_run_log import get_run_log_db
                        db = get_run_log_db()
                        recent = db.get_recent_runs(limit=20)
                        verified_count = sum(
                            1 for r in recent
                            if int(r.get("verification_steps", 0) or 0) > 0
                        )
                        total_runs = len(recent)
                        actual_rate = verified_count / max(1, total_runs)
                        claimed = b.confidence

                        if abs(actual_rate - claimed) > 0.3:
                            report.anomalies.append(AuditAnomaly(
                                source="execution_beliefs",
                                severity="warning",
                                description=(
                                    f"Verification belief ({claimed:.2f}) doesn't match "
                                    f"actual rate ({actual_rate:.2f}, {verified_count}/{total_runs} runs)"
                                ),
                                evidence={"claimed": claimed, "actual": actual_rate},
                            ))
                    except Exception:
                        pass

            report.checks_passed += 1
        except Exception as e:
            report.checks_run += 1
            logger.debug(f"[SELF_AUDIT] execution_beliefs check failed: {e}")

    # ----- 4. Governance Agent Availability -----

    def _check_governance(self, report: VerifiedAuditReport):
        """Verify all 6 governance agents are loadable."""
        agent_names = [
            "TemplateDetector", "SpeechLeakDetector", "GapAuditor",
            "PrematureResolutionGuard", "MemoryCorruptionGuard", "ContinuityAuditor",
        ]
        report.checks_run += 1
        loaded = []
        failed = []

        for name in agent_names:
            try:
                from personal_agent import immune_agents
                cls = getattr(immune_agents, name, None)
                if cls is not None:
                    loaded.append(name)
                else:
                    failed.append(name)
            except Exception:
                failed.append(name)

        report.governance_status = {
            "loaded": loaded,
            "failed": failed,
            "total": len(agent_names),
        }

        if failed:
            report.anomalies.append(AuditAnomaly(
                source="governance",
                severity="warning" if len(failed) <= 2 else "critical",
                description=f"{len(failed)}/{len(agent_names)} governance agents failed to load: {failed}",
            ))
        else:
            report.checks_passed += 1

    # ----- 5. Memory System Health -----

    def _check_memory_health(self, report: VerifiedAuditReport):
        """Check memory store health metrics."""
        try:
            from personal_agent.crt_memory import CRTMemorySystem
            mem = CRTMemorySystem(db_path="personal_agent/crt_memory_shared.db")
            all_mems = mem._load_all_memories()

            total = len(all_mems)
            deprecated = sum(1 for m in all_mems if getattr(m, "deprecated", False))
            low_trust = sum(1 for m in all_mems if not getattr(m, "deprecated", False)
                          and getattr(m, "trust", 1.0) < 0.2)
            active = total - deprecated

            report.memory_health = {
                "total": total,
                "active": active,
                "deprecated": deprecated,
                "deprecated_ratio": round(deprecated / max(1, total), 3),
                "low_trust_count": low_trust,
            }

            report.checks_run += 1

            if deprecated / max(1, total) > 0.5:
                report.anomalies.append(AuditAnomaly(
                    source="memory_health",
                    severity="warning",
                    description=f"High deprecation ratio: {deprecated}/{total} ({deprecated/total:.0%})",
                ))
            else:
                report.checks_passed += 1

            if low_trust > active * 0.3 and active > 10:
                report.anomalies.append(AuditAnomaly(
                    source="memory_health",
                    severity="info",
                    description=f"{low_trust} active memories have trust < 0.2",
                ))
        except Exception as e:
            report.checks_run += 1
            logger.debug(f"[SELF_AUDIT] memory_health check failed: {e}")

    # ----- 6. Cross-System Validation -----

    def _cross_validate(self, report: VerifiedAuditReport):
        """Detect contradictions between subsystems."""
        report.checks_run += 1

        # Cross-check: agent_loop says enabled but no recent runs
        if report.execution_state.get("agent_loop") == "enabled":
            try:
                from personal_agent.agent_run_log import get_run_log_db
                db = get_run_log_db()
                recent = db.get_recent_runs(limit=5)
                if not recent:
                    report.anomalies.append(AuditAnomaly(
                        source="cross_validation",
                        severity="info",
                        description="Agent loop claims enabled but no recent runs logged",
                    ))
            except Exception:
                pass

        # Cross-check: execution beliefs say "worsening" but self-model says "growing_confidence"
        worsening = [b for b in report.execution_beliefs
                     if b.get("direction") == "worsening" and b.get("confidence", 0) > 0.5]
        growing = report.self_model_slots.get("growing_confidence", {})
        if worsening and growing.get("set"):
            report.anomalies.append(AuditAnomaly(
                source="cross_validation",
                severity="warning",
                description=(
                    f"Execution beliefs show {len(worsening)} worsening patterns "
                    f"but self-model claims growing confidence"
                ),
                evidence={
                    "worsening_beliefs": [b["description"][:80] for b in worsening],
                    "growing_confidence": str(growing.get("value", ""))[:80],
                },
            ))

        report.checks_passed += 1


# ---------------------------------------------------------------------------
# API endpoint helper
# ---------------------------------------------------------------------------

def run_verified_self_audit(thread_id: str = "default") -> VerifiedAuditReport:
    """Convenience function for running audit from anywhere."""
    auditor = VerifiedSelfAuditor()
    report = auditor.audit(thread_id)
    logger.info(
        "[SELF_AUDIT] health=%.2f checks=%d/%d anomalies=%d",
        report.overall_health,
        report.checks_passed,
        report.checks_run,
        len(report.anomalies),
    )
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    auditor = VerifiedSelfAuditor()
    report = auditor.audit()

    print(f"\n{'='*60}")
    print(f"VERIFIED SELF-AUDIT REPORT")
    print(f"{'='*60}")
    print(f"Health: {report.overall_health:.1%}")
    print(f"Checks: {report.checks_passed}/{report.checks_run} passed")
    print(f"Anomalies: {len(report.anomalies)}")

    if report.execution_state:
        print(f"\nExecution State:")
        for k, v in report.execution_state.items():
            print(f"  {k}: {v}")

    if report.governance_status:
        gs = report.governance_status
        print(f"\nGovernance: {len(gs.get('loaded', []))}/{gs.get('total', 0)} agents loaded")
        if gs.get("failed"):
            print(f"  Failed: {gs['failed']}")

    if report.memory_health:
        mh = report.memory_health
        print(f"\nMemory: {mh['active']} active, {mh['deprecated']} deprecated ({mh['deprecated_ratio']:.0%})")

    if report.anomalies:
        print(f"\nAnomalies:")
        for a in report.anomalies:
            icon = {"critical": "!!!", "warning": " ! ", "info": " i "}[a.severity]
            print(f"  [{icon}] [{a.source}] {a.description}")

    print(f"\n{'='*60}")
    sys.exit(0 if report.overall_health >= 0.6 else 1)
