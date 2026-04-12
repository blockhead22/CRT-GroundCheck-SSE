"""Gravity Bridge Singleton — lazy-initialized, shared across the app.

Usage:
    from personal_agent._gravity_singleton import get_gravity_bridge
    bridge = get_gravity_bridge()  # Returns None if not available
    if bridge:
        result = bridge.on_memory_stored(memory_dict)
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

_bridge = None
_init_attempted = False


def get_gravity_bridge():
    """Get or lazily initialize the gravity bridge.
    Returns None if initialization fails (non-blocking)."""
    global _bridge, _init_attempted

    if _bridge is not None:
        return _bridge

    if _init_attempted:
        return None  # Already tried, failed — don't retry every call

    _init_attempted = True

    # Only initialize if gravity is enabled
    if os.environ.get("CRT_GRAVITY_ENABLED", "1") != "1":
        logger.info("[GRAVITY] Disabled via CRT_GRAVITY_ENABLED=0")
        return None

    try:
        # Add labs/gravity to path for import
        gravity_path = os.path.join(os.path.dirname(__file__), "..", "labs", "gravity")
        if gravity_path not in sys.path:
            sys.path.insert(0, os.path.abspath(gravity_path))

        from gravity_bridge import GravityBridge

        # Resolve DB paths relative to project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        memory_db = os.path.join(project_root, "personal_agent", "crt_memory_shared.db")
        ledger_db = os.path.join(project_root, "personal_agent", "crt_ledger_shared.db")

        _bridge = GravityBridge(
            memory_db=memory_db,
            ledger_db=ledger_db,
            max_memories=1000,
        )
        _bridge.initialize()
        logger.info("[GRAVITY] Bridge initialized successfully")
        return _bridge

    except Exception as e:
        logger.warning("[GRAVITY] Bridge initialization failed (non-blocking): %s", e)
        return None


def reset_gravity_bridge():
    """Force re-initialization on next access. For testing."""
    global _bridge, _init_attempted
    _bridge = None
    _init_attempted = False
