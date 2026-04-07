"""
Layer 3-4 — Action receipt system.

Every write/exec action creates an ActionReceipt, persisted to SQLite.
Receipts track what happened, whether it's reversible, and how to undo.
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .runtime_paths import resolve_action_receipts_db_path

logger = logging.getLogger(__name__)

_DB_PATH = str(resolve_action_receipts_db_path())

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS action_receipts (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    timestamp REAL,
    tool_name TEXT,
    action TEXT,
    target TEXT,
    result TEXT,
    reversible INTEGER,
    reverse_action TEXT,
    details TEXT,
    checkpoint_approved INTEGER,
    agent_name TEXT,
    orchestration_id TEXT
)
"""

_MIGRATE_AGENT_COLS_SQL = [
    "ALTER TABLE action_receipts ADD COLUMN agent_name TEXT DEFAULT NULL",
    "ALTER TABLE action_receipts ADD COLUMN orchestration_id TEXT DEFAULT NULL",
]

_MIGRATE_VERIFICATION_COLS_SQL = [
    "ALTER TABLE action_receipts ADD COLUMN verification_passed INTEGER DEFAULT NULL",
    "ALTER TABLE action_receipts ADD COLUMN verification_reason TEXT DEFAULT NULL",
    "ALTER TABLE action_receipts ADD COLUMN expectation_keywords TEXT DEFAULT NULL",
    "ALTER TABLE action_receipts ADD COLUMN run_step_id TEXT DEFAULT NULL",
    "ALTER TABLE action_receipts ADD COLUMN model_attribution TEXT DEFAULT NULL",
]


@dataclass
class ActionReceipt:
    receipt_id: str
    timestamp: float
    tool_name: str           # "file_write", "shell_exec", "git", etc.
    action: str              # human-readable: "wrote 45 lines to src/App.tsx"
    target: str              # path, URL, or command
    result: str              # "success", "error", "partial"
    reversible: bool         # can this be undone?
    reverse_action: Optional[str] = None  # how to undo
    details: Dict[str, Any] = field(default_factory=dict)
    checkpoint_approved: bool = True
    # --- Verification fields (Sprint 15) ---
    verification_passed: Optional[bool] = None
    verification_reason: Optional[str] = None
    expectation_keywords: Optional[List[str]] = None
    run_step_id: Optional[str] = None        # links to RunStep iteration
    model_attribution: Optional[str] = None  # which LLM model planned this action


def _get_db() -> sqlite3.Connection:
    """Get or create the receipts database."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    # Migrate: add Sprint 8 columns if missing
    for sql in _MIGRATE_AGENT_COLS_SQL:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    # Migrate: add Sprint 15 verification columns if missing
    for sql in _MIGRATE_VERIFICATION_COLS_SQL:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    return conn


def log_receipt(receipt: ActionReceipt, thread_id: str) -> None:
    """Persist an action receipt to SQLite."""
    try:
        conn = _get_db()
        conn.execute(
            """INSERT OR REPLACE INTO action_receipts
               (id, thread_id, timestamp, tool_name, action, target, result,
                reversible, reverse_action, details, checkpoint_approved,
                verification_passed, verification_reason, expectation_keywords,
                run_step_id, model_attribution)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                receipt.receipt_id,
                thread_id,
                receipt.timestamp,
                receipt.tool_name,
                receipt.action,
                receipt.target,
                receipt.result,
                1 if receipt.reversible else 0,
                receipt.reverse_action,
                json.dumps(receipt.details, default=str),
                1 if receipt.checkpoint_approved else 0,
                (1 if receipt.verification_passed else 0) if receipt.verification_passed is not None else None,
                receipt.verification_reason,
                json.dumps(receipt.expectation_keywords) if receipt.expectation_keywords else None,
                receipt.run_step_id,
                receipt.model_attribution,
            ),
        )
        conn.commit()
        conn.close()
        logger.info("[RECEIPTS] Logged receipt %s: %s", receipt.receipt_id[:8], receipt.action)
    except Exception as e:
        logger.warning("[RECEIPTS] Failed to log receipt: %s", e)


def get_receipts(thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Read recent receipts for a thread."""
    try:
        conn = _get_db()
        cursor = conn.execute(
            """SELECT id, thread_id, timestamp, tool_name, action, target, result,
                      reversible, reverse_action, details, checkpoint_approved,
                      verification_passed, verification_reason, expectation_keywords,
                      run_step_id, model_attribution
               FROM action_receipts
               WHERE thread_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (thread_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "receipt_id": r[0],
                "thread_id": r[1],
                "timestamp": r[2],
                "tool_name": r[3],
                "action": r[4],
                "target": r[5],
                "result": r[6],
                "reversible": bool(r[7]),
                "reverse_action": r[8],
                "details": json.loads(r[9]) if r[9] else {},
                "checkpoint_approved": bool(r[10]),
                "verification_passed": bool(r[11]) if r[11] is not None else None,
                "verification_reason": r[12],
                "expectation_keywords": json.loads(r[13]) if r[13] else None,
                "run_step_id": r[14],
                "model_attribution": r[15],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("[RECEIPTS] Failed to get receipts: %s", e)
        return []


def create_receipt(
    tool_name: str,
    action: str,
    target: str,
    result: str,
    reversible: bool = False,
    reverse_action: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    checkpoint_approved: bool = True,
) -> ActionReceipt:
    """Factory to create an ActionReceipt with auto-generated ID and timestamp."""
    return ActionReceipt(
        receipt_id=str(uuid.uuid4()),
        timestamp=time.time(),
        tool_name=tool_name,
        action=action,
        target=target,
        result=result,
        reversible=reversible,
        reverse_action=reverse_action,
        details=details or {},
        checkpoint_approved=checkpoint_approved,
    )


def update_receipt_verification(
    receipt_id: str,
    verification_passed: bool,
    verification_reason: str,
    expectation_keywords: Optional[List[str]] = None,
    run_step_id: Optional[str] = None,
    model_attribution: Optional[str] = None,
) -> None:
    """Update an existing receipt with verification and attribution data."""
    try:
        conn = _get_db()
        conn.execute(
            """UPDATE action_receipts
               SET verification_passed = ?,
                   verification_reason = ?,
                   expectation_keywords = ?,
                   run_step_id = ?,
                   model_attribution = ?
               WHERE id = ?""",
            (
                1 if verification_passed else 0,
                verification_reason,
                json.dumps(expectation_keywords) if expectation_keywords else None,
                run_step_id,
                model_attribution,
                receipt_id,
            ),
        )
        conn.commit()
        conn.close()
        logger.debug("[RECEIPTS] Updated verification for %s: passed=%s", receipt_id[:8], verification_passed)
    except Exception as e:
        logger.warning("[RECEIPTS] Failed to update verification: %s", e)


def get_receipt_summary(thread_id: str) -> Dict[str, Any]:
    """Return aggregate receipt stats: total actions, pass rate, tools used."""
    try:
        conn = _get_db()
        # Total count
        total = conn.execute(
            "SELECT COUNT(*) FROM action_receipts WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()[0]

        # Per-tool counts
        tool_rows = conn.execute(
            "SELECT tool_name, COUNT(*) FROM action_receipts WHERE thread_id = ? GROUP BY tool_name",
            (thread_id,),
        ).fetchall()
        tools_used = {r[0]: r[1] for r in tool_rows}

        # Verification stats
        verified = conn.execute(
            "SELECT COUNT(*) FROM action_receipts WHERE thread_id = ? AND verification_passed IS NOT NULL",
            (thread_id,),
        ).fetchone()[0]
        passed = conn.execute(
            "SELECT COUNT(*) FROM action_receipts WHERE thread_id = ? AND verification_passed = 1",
            (thread_id,),
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM action_receipts WHERE thread_id = ? AND verification_passed = 0",
            (thread_id,),
        ).fetchone()[0]

        # Result breakdown
        result_rows = conn.execute(
            "SELECT result, COUNT(*) FROM action_receipts WHERE thread_id = ? GROUP BY result",
            (thread_id,),
        ).fetchall()
        results = {r[0]: r[1] for r in result_rows}

        # Model attribution breakdown
        model_rows = conn.execute(
            "SELECT model_attribution, COUNT(*) FROM action_receipts WHERE thread_id = ? AND model_attribution IS NOT NULL GROUP BY model_attribution",
            (thread_id,),
        ).fetchall()
        models_used = {r[0]: r[1] for r in model_rows}

        conn.close()
        return {
            "thread_id": thread_id,
            "total_actions": total,
            "tools_used": tools_used,
            "verification": {
                "total_verified": verified,
                "passed": passed,
                "failed": failed,
                "pass_rate": round(passed / verified, 3) if verified > 0 else None,
            },
            "results": results,
            "models_used": models_used,
        }
    except Exception as e:
        logger.warning("[RECEIPTS] Failed to get summary: %s", e)
        return {"thread_id": thread_id, "total_actions": 0, "error": str(e)}


def log_orchestration_receipt(
    orchestration_id: str,
    thread_id: str,
    subtask_count: int,
    parallel_count: int,
    total_duration_ms: float,
    merged_trust: float,
    all_ok: bool,
) -> str:
    """Log an orchestration-level receipt that ties sub-agent receipts together."""
    receipt = ActionReceipt(
        receipt_id=orchestration_id,
        timestamp=time.time(),
        tool_name="orchestration",
        action=f"{subtask_count} subtasks ({parallel_count} parallel)",
        target="TaskOrchestrator",
        result="ok" if all_ok else "partial_failure",
        reversible=False,
        details={
            "subtask_count": subtask_count,
            "parallel_count": parallel_count,
            "merged_trust": merged_trust,
            "total_duration_ms": total_duration_ms,
        },
    )
    log_receipt(receipt, thread_id)
    return orchestration_id
