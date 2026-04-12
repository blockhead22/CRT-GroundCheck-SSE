"""Gravity Bridge — Connects GravityBeliefStore to Aether's chat pipeline.

This module is the wire-in point. It:
1. Initializes the gravity store from production DBs on startup
2. Hooks into store_memory() to update gravity after each write
3. Provides the prompt-ready gravity map for injection
4. Fires salience events that the heartbeat can consume

Integration into Aether:
  In routes/chat.py or the orchestrator, add:
    from labs.gravity.gravity_bridge import GravityBridge
    gravity = GravityBridge()  # loads from DB on init

  After each store_memory() call:
    salience = gravity.on_memory_stored(memory_dict)
    if salience["salience_triggered"]:
        # Include gravity context in next response

  In prompt construction:
    gravity_section = gravity.prompt_section()
"""

from __future__ import annotations
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Optional

from gravity_belief_store import GravityBeliefStore

logger = logging.getLogger(__name__)


class GravityBridge:
    """Bridge between Aether's memory system and the gravity topology."""

    def __init__(
        self,
        memory_db: str = "personal_agent/crt_memory_shared.db",
        ledger_db: str = "personal_agent/crt_ledger_shared.db",
        max_memories: int = 1000,
        min_room_size: int = 3,
    ):
        self.memory_db = memory_db
        self.ledger_db = ledger_db
        self.max_memories = max_memories
        self.min_room_size = min_room_size
        self.store = GravityBeliefStore()
        self._initialized = False
        self._last_rebuild = 0.0
        self._rebuild_interval = 300  # Rebuild from DB every 5 minutes max

    def initialize(self):
        """Load memories + contradictions from production DBs."""
        memories = self._load_memories()
        contradictions = self._load_contradictions()

        self.store = GravityBeliefStore()
        self.store.ingest_memories(memories)
        if contradictions:
            self.store.ingest_contradictions(contradictions)
        self.store.fuse_micro_rooms(self.min_room_size)
        self.store._compute_doors()

        self._initialized = True
        self._last_rebuild = time.time()
        logger.info(
            f"[GRAVITY] Initialized: {len(self.store.rooms)} rooms, "
            f"{sum(len(r.memories) for r in self.store.rooms.values())} memories"
        )

    def on_memory_stored(self, memory_dict: dict) -> dict:
        """Called after store_memory(). Updates gravity and checks salience.

        Args:
            memory_dict: Dict with keys matching MemoryItem fields:
                memory_id, text, confidence, trust, domain_tags,
                belnap_state, contradiction_count, kind, timestamp

        Returns:
            Dict with salience_triggered, salience_reason, gravity_delta, gravity_map
        """
        if not self._initialized:
            self.initialize()

        result = self.store.ingest_single(memory_dict)

        # Apply pressure: split rooms under tension
        splits = self.store.apply_pressure()
        if splits:
            for s in splits:
                logger.info(f"[GRAVITY SPLIT] {s}")
            result["splits"] = splits

        # Set walker context from the memory's domains
        domains = memory_dict.get("domain_tags") or []
        if domains:
            self.store.set_walker_context(domains)

        if result["salience_triggered"]:
            logger.info(
                f"[GRAVITY SALIENCE] {result['salience_reason']} "
                f"(delta={result['gravity_delta']:.3f})"
            )

        return result

    def on_contradiction_detected(self, old_memory_id: str, new_memory_id: str,
                                   summary: str = ""):
        """Called when the contradiction pipeline detects a new contradiction.
        Updates tension in the affected rooms."""
        contradiction = {
            "old_memory_id": old_memory_id,
            "new_memory_id": new_memory_id,
            "status": "open",
            "lifecycle_state": "active",
            "summary": summary,
        }
        self.store.ingest_contradictions([contradiction])

    def prompt_section(self, max_rooms: int = 8) -> str:
        """Return the gravity map formatted for system prompt injection.
        Compact, informative, no noise."""
        if not self._initialized:
            return ""
        return self.store.render_for_prompt(max_rooms=max_rooms)

    def full_render(self) -> str:
        """Full gravity topology for debugging."""
        if not self._initialized:
            return "Gravity not initialized"
        return self.store.render()

    def summary(self) -> dict:
        """Summary dict for heartbeat consumption."""
        if not self._initialized:
            return {"initialized": False}
        s = self.store.summary()
        s["initialized"] = True
        return s

    def should_rebuild(self) -> bool:
        """Check if we should reload from DB (periodic refresh)."""
        return time.time() - self._last_rebuild > self._rebuild_interval

    def walker_attention(self) -> Optional[str]:
        """Where should attention go right now? Returns the room name
        the walker would navigate to, or None if stable."""
        if not self._initialized:
            return None

        step = self.store.walker_step()
        if step.get("to") != step.get("from"):
            return step["to"]
        return None

    # -- Private: DB loading --

    def _load_memories(self) -> list[dict]:
        try:
            conn = sqlite3.connect(self.memory_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT memory_id, text, confidence, trust, domain_tags,
                       belnap_state, contradiction_count, deprecated,
                       timestamp, kind, authority, temporal_status
                FROM memories
                WHERE deprecated = 0 OR deprecated IS NULL
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.max_memories,))

            memories = []
            for row in cursor.fetchall():
                m = dict(row)
                if m.get("domain_tags"):
                    try:
                        m["domain_tags"] = json.loads(m["domain_tags"])
                    except (json.JSONDecodeError, TypeError):
                        m["domain_tags"] = []
                else:
                    m["domain_tags"] = []
                memories.append(m)

            conn.close()
            return memories
        except Exception as e:
            logger.error(f"[GRAVITY] Failed to load memories: {e}")
            return []

    def _load_contradictions(self) -> list[dict]:
        try:
            conn = sqlite3.connect(self.ledger_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ledger_id, old_memory_id, new_memory_id, status,
                       lifecycle_state, summary, contradiction_type
                FROM contradictions
                WHERE old_memory_id NOT LIKE 'profile%'
            """)
            contradictions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return contradictions
        except Exception as e:
            logger.error(f"[GRAVITY] Failed to load contradictions: {e}")
            return []


# ---------------------------------------------------------------------------
# TEST: Simulate a chat session with gravity bridge
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    os.chdir("D:/AI_round2")

    bridge = GravityBridge()
    bridge.initialize()

    print(bridge.full_render())
    print("\n--- PROMPT SECTION ---")
    print(bridge.prompt_section())

    # Simulate conversation turns
    print("\n--- SIMULATED CONVERSATION ---")

    turns = [
        {
            "memory_id": "sim_1",
            "text": "I'm thinking about going back to the print shop",
            "confidence": 0.7,
            "trust": 0.6,
            "domain_tags": ["career", "print_shop"],
            "belnap_state": "true",
            "contradiction_count": 0,
            "kind": "user_fact",
            "timestamp": time.time(),
        },
        {
            "memory_id": "sim_2",
            "text": "Actually no, I want to focus on freelance dev work",
            "confidence": 0.85,
            "trust": 0.75,
            "domain_tags": ["career", "programming"],
            "belnap_state": "both",
            "contradiction_count": 1,
            "kind": "user_fact",
            "timestamp": time.time() + 1,
        },
        {
            "memory_id": "sim_3",
            "text": "I sold my camera gear",
            "confidence": 0.9,
            "trust": 0.85,
            "domain_tags": ["photography"],
            "belnap_state": "true",
            "contradiction_count": 0,
            "kind": "user_fact",
            "timestamp": time.time() + 2,
        },
    ]

    for i, turn in enumerate(turns):
        result = bridge.on_memory_stored(turn)
        print(f"\n  Turn {i+1}: \"{turn['text'][:50]}\"")
        print(f"    Salience: {result['salience_triggered']}")
        if result["salience_triggered"]:
            print(f"    Reason: {result['salience_reason']}")
        print(f"    Delta: {result['gravity_delta']}")

    # Final state
    print("\n--- POST-CONVERSATION PROMPT SECTION ---")
    print(bridge.prompt_section())

    # Walker attention
    attention = bridge.walker_attention()
    print(f"\n--- ATTENTION: {attention or 'stable, no shift needed'} ---")
