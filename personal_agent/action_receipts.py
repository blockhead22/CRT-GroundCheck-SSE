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

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_receipts.db")

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
    checkpoint_approved INTEGER
)
"""


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


def _get_db() -> sqlite3.Connection:
    """Get or create the receipts database."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def log_receipt(receipt: ActionReceipt, thread_id: str) -> None:
    """Persist an action receipt to SQLite."""
    try:
        conn = _get_db()
        conn.execute(
            """INSERT OR REPLACE INTO action_receipts
               (id, thread_id, timestamp, tool_name, action, target, result,
                reversible, reverse_action, details, checkpoint_approved)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                      reversible, reverse_action, details, checkpoint_approved
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
