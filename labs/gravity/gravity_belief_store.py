"""GravityBeliefStore — Adapter from CRT MemoryItem/BeliefStore to GravityPalace.

Standalone lab module. Does NOT import from personal_agent at runtime.
Instead, it accepts raw memory dicts (from DB dump or API) and builds
gravity rooms from them.

Usage:
    gbs = GravityBeliefStore()
    gbs.ingest_memories(memories)  # list of dicts from DB
    gbs.render()                   # see the topology
    delta = gbs.turn_delta()       # measure change after a conversation turn

This is the prep layer before wiring into Aether's chat loop.
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional


# ---------------------------------------------------------------------------
# Gravity Room (adapted from gravity_lab.py for belief domains)
# ---------------------------------------------------------------------------
@dataclass
class GravityRoom:
    """A belief domain with physics."""
    name: str
    memories: dict[str, dict] = field(default_factory=dict)  # memory_id -> memory dict

    def add(self, memory_id: str, memory: dict):
        self.memories[memory_id] = memory

    def remove(self, memory_id: str):
        self.memories.pop(memory_id, None)

    @property
    def mass(self) -> float:
        """Sum of trust-weighted memories. Trust is earned, not hardcoded."""
        if not self.memories:
            return 0.0
        return sum(
            m.get("trust", 0.5) * m.get("confidence", 0.5)
            for m in self.memories.values()
        )

    @property
    def contradiction_pairs(self) -> int:
        """Count of memories in 'both' belnap state (held contradictions)."""
        return sum(
            1 for m in self.memories.values()
            if m.get("belnap_state") == "both"
        )

    @property
    def deprecated_count(self) -> int:
        """Memories that have been deprecated (dead branches equivalent)."""
        return sum(
            1 for m in self.memories.values()
            if m.get("deprecated", False)
        )

    @property
    def tension(self) -> float:
        """Contradiction density.
        Sources of tension:
          - Belnap 'both' states (held contradictions)
          - High contradiction_count on individual memories
          - Deprecated memories coexisting with active ones
        """
        n = len(self.memories)
        if n < 2:
            return 0.0

        # Tension sources
        both_count = self.contradiction_pairs
        deprecated = self.deprecated_count
        active = n - deprecated

        # Contradiction count across all memories in room
        total_contradictions = sum(
            m.get("contradiction_count", 0) for m in self.memories.values()
        )

        # Normalize: contradictions / memories
        contradiction_density = total_contradictions / n if n > 0 else 0
        # Both states / active memories
        both_density = both_count / active if active > 0 else 0
        # Deprecated vs active ratio
        deprecated_tension = (deprecated * active) / (n * n) if n > 0 else 0

        # Combined tension (0-1 range, clamped)
        raw = (contradiction_density * 0.4) + (both_density * 0.4) + (deprecated_tension * 0.2)
        return min(raw, 1.0)

    @property
    def gravity(self) -> float:
        """Pull strength: tension-weighted mass + baseline density.
        Freshness modulates: stale rooms lose pull over time."""
        tension_pull = self.mass * self.tension
        density_pull = math.sqrt(self.mass) * 0.3 if self.mass > 0 else 0
        raw = tension_pull + density_pull
        # Freshness decay: rooms with only old memories lose 40% pull at minimum
        return raw * (0.6 + 0.4 * self.freshness)

    @property
    def stability(self) -> float:
        return 1.0 - min(self.tension, 1.0)

    @property
    def escape_pressure(self) -> float:
        return self.tension

    def should_split(self, threshold: float = 0.5) -> bool:
        return self.tension > threshold and len(self.memories) >= 6

    def find_split_groups(self) -> tuple[list[str], list[str]]:
        """Split into two groups: contradicted vs clean memories."""
        contradicted = [
            mid for mid, m in self.memories.items()
            if m.get("belnap_state") == "both" or m.get("contradiction_count", 0) > 0
        ]
        clean = [
            mid for mid in self.memories if mid not in set(contradicted)
        ]
        # Only split if both groups have members
        if not contradicted or not clean:
            return list(self.memories.keys()), []
        return clean, contradicted

    @property
    def age_days(self) -> float:
        """Average age of memories in days."""
        if not self.memories:
            return 0.0
        now = time.time()
        ages = [
            (now - m.get("timestamp", now)) / 86400
            for m in self.memories.values()
        ]
        return sum(ages) / len(ages)

    @property
    def freshness(self) -> float:
        """How recently updated. 1.0 = today, 0.0 = ancient."""
        age = self.age_days
        if age <= 1:
            return 1.0
        return max(0.0, 1.0 - (age / 90))  # Decays over 90 days


# ---------------------------------------------------------------------------
# Door — connection between domain rooms
# ---------------------------------------------------------------------------
@dataclass
class DomainDoor:
    room_a: str
    room_b: str
    cost: float = 1.0  # Will be set from embedding distance
    shared_memories: int = 0  # Memories tagged in both domains


# ---------------------------------------------------------------------------
# GravityBeliefStore
# ---------------------------------------------------------------------------
class GravityBeliefStore:
    """Wraps CRT memories into gravity rooms by domain.

    Does not touch production code. Accepts raw memory dicts
    (same schema as MemoryItem.to_dict()) and builds a GravityPalace.
    """

    SALIENCE_THRESHOLD = 0.20  # Raised from 0.15 to reduce noise
    HIGH_VALUE_KINDS = {"correction", "identity"}  # Removed user_fact — too noisy

    def __init__(self, split_threshold: float = 0.5):
        self.rooms: dict[str, GravityRoom] = {}
        self.doors: dict[tuple[str, str], DomainDoor] = {}
        self.split_threshold = split_threshold
        self.unassigned_room = "__untagged__"

        # Salience state
        self._last_gravity_snapshot: dict[str, float] = {}
        self._salience_triggered = False
        self._salience_reason = ""
        self._salience_log: list[dict] = []

        # Walker
        self.walker_position: Optional[str] = None
        self.walk_history: list[dict] = []

    # -- Ingestion --

    def ingest_memories(self, memories: list[dict]):
        """Bulk load memories into rooms by domain_tags."""
        for m in memories:
            self._assign_to_rooms(m)
        self._compute_doors()

    def ingest_single(self, memory: dict) -> dict:
        """Ingest one memory (e.g., after a conversation turn).
        Returns salience status."""
        # Snapshot before
        self._last_gravity_snapshot = self._gravity_snapshot()

        # Assign to rooms
        self._assign_to_rooms(memory)

        # Measure delta
        return self._check_salience(memory)

    def ingest_contradictions(self, contradictions: list[dict]):
        """Load contradiction ledger entries and inject tension into rooms.

        Each contradiction links two memory IDs. If both memories are in
        the same room, that room's tension increases. If they're in different
        rooms, a cross-room tension door is created.
        """
        for c in contradictions:
            old_id = c.get("old_memory_id", "")
            new_id = c.get("new_memory_id", "")
            status = c.get("status", "open")
            lifecycle = c.get("lifecycle_state", "active")

            # Find which rooms these memories are in
            old_rooms = self._find_rooms_for(old_id)
            new_rooms = self._find_rooms_for(new_id)

            if not old_rooms and not new_rooms:
                continue

            # Mark the memories with contradiction data
            for room_name in old_rooms:
                mem = self.rooms[room_name].memories.get(old_id)
                if mem:
                    mem["contradiction_count"] = mem.get("contradiction_count", 0) + 1
                    if status == "open" and lifecycle in ("active", "settling"):
                        mem["belnap_state"] = "both"

            for room_name in new_rooms:
                mem = self.rooms[room_name].memories.get(new_id)
                if mem:
                    mem["contradiction_count"] = mem.get("contradiction_count", 0) + 1
                    if status == "open" and lifecycle in ("active", "settling"):
                        mem["belnap_state"] = "both"

        # Count how many contradictions were injected
        total_injected = sum(
            m.get("contradiction_count", 0)
            for room in self.rooms.values()
            for m in room.memories.values()
        )
        both_count = sum(
            1 for room in self.rooms.values()
            for m in room.memories.values()
            if m.get("belnap_state") == "both"
        )
        print(f"  Injected {total_injected} contradiction marks across {both_count} memories")

    def _find_rooms_for(self, memory_id: str) -> list[str]:
        """Find which rooms contain a given memory ID."""
        return [
            name for name, room in self.rooms.items()
            if memory_id in room.memories
        ]

    def _assign_to_rooms(self, memory: dict):
        """Put a memory into rooms based on its domain_tags."""
        memory_id = memory.get("memory_id", str(id(memory)))
        domains = memory.get("domain_tags") or []

        if not domains:
            # Untagged — goes to catch-all room
            domains = [self.unassigned_room]

        for domain in domains:
            if domain not in self.rooms:
                self.rooms[domain] = GravityRoom(name=domain)
            self.rooms[domain].add(memory_id, memory)

    def _compute_doors(self):
        """Auto-generate doors between rooms.
        Cost = blend of shared memories (structural) and centroid distance (semantic)."""
        self.doors.clear()
        room_names = list(self.rooms.keys())

        # Compute room centroids from memory vectors (if available)
        centroids = {}
        for name, room in self.rooms.items():
            vectors = []
            for m in room.memories.values():
                vec = m.get("_vector")
                if vec is not None:
                    vectors.append(vec)
            if vectors:
                import numpy as np
                centroids[name] = np.mean(vectors, axis=0)

        for i, a in enumerate(room_names):
            mem_ids_a = set(self.rooms[a].memories.keys())
            for b in room_names[i + 1:]:
                mem_ids_b = set(self.rooms[b].memories.keys())
                shared = len(mem_ids_a & mem_ids_b)

                # Structural cost: shared memories
                struct_cost = 1.0 / (1 + shared) if shared > 0 else 2.0

                # Semantic cost: centroid distance (if vectors available)
                if a in centroids and b in centroids:
                    import numpy as np
                    cos_sim = np.dot(centroids[a], centroids[b]) / (
                        np.linalg.norm(centroids[a]) * np.linalg.norm(centroids[b]) + 1e-8
                    )
                    semantic_cost = 1.0 - max(cos_sim, 0)  # 0=identical, 1=orthogonal
                    # Blend: 40% structural + 60% semantic
                    cost = 0.4 * struct_cost + 0.6 * semantic_cost
                else:
                    cost = struct_cost

                key = tuple(sorted([a, b]))
                self.doors[key] = DomainDoor(
                    room_a=key[0], room_b=key[1],
                    cost=cost, shared_memories=shared,
                )

    # -- Room Splitting --

    def apply_pressure(self) -> list[str]:
        """Split rooms under tension. Returns list of events."""
        events = []
        rooms_to_split = [
            name for name, room in self.rooms.items()
            if room.should_split(self.split_threshold)
            and name != self.unassigned_room
        ]

        for name in rooms_to_split:
            room = self.rooms.get(name)
            if not room:
                continue
            clean, contradicted = room.find_split_groups()
            if not contradicted:
                continue

            # Create the contradicted sub-room
            new_name = f"{name}:disputed"
            new_room = GravityRoom(name=new_name)
            for mid in contradicted:
                mem = room.memories.pop(mid, None)
                if mem:
                    new_room.add(mid, mem)

            self.rooms[new_name] = new_room

            event = (
                f"SPLIT: '{name}' -> '{name}' ({len(room.memories)} clean) + "
                f"'{new_name}' ({len(new_room.memories)} disputed)"
            )
            events.append(event)

        return events

    # -- Room Fusion --

    def fuse_micro_rooms(self, min_memories: int = 3):
        """Merge tiny rooms into their closest neighbor by shared memories.
        Rooms with fewer than min_memories get absorbed."""
        micro = [name for name, room in self.rooms.items()
                 if len(room.memories) < min_memories and name != self.unassigned_room]

        if not micro:
            return []

        fused = []
        for name in micro:
            room = self.rooms.get(name)
            if not room:
                continue

            # Find best merge target: room that shares the most memories
            best_target = None
            best_shared = -1

            mem_ids = set(room.memories.keys())
            for other_name, other_room in self.rooms.items():
                if other_name == name or other_name == self.unassigned_room:
                    continue
                if len(other_room.memories) < min_memories:
                    continue  # Don't merge into another micro room
                shared = len(mem_ids & set(other_room.memories.keys()))
                if shared > best_shared:
                    best_shared = shared
                    best_target = other_name

            if not best_target:
                # No good target — merge into untagged
                best_target = self.unassigned_room
                if best_target not in self.rooms:
                    self.rooms[best_target] = GravityRoom(name=best_target)

            # Merge
            target_room = self.rooms[best_target]
            for mid, mem in room.memories.items():
                if mid not in target_room.memories:
                    target_room.add(mid, mem)

            del self.rooms[name]
            fused.append(f"{name} -> {best_target} ({len(room.memories)} memories)")

        # Clean up doors referencing deleted rooms
        self.doors = {
            k: v for k, v in self.doors.items()
            if v.room_a in self.rooms and v.room_b in self.rooms
        }

        return fused

    # -- Salience Gate --

    def _gravity_snapshot(self) -> dict[str, float]:
        return {name: room.gravity for name, room in self.rooms.items()}

    def _check_salience(self, memory: dict) -> dict:
        """Check if this memory write changed the topology significantly."""
        self._salience_triggered = False
        self._salience_reason = ""

        new_snapshot = self._gravity_snapshot()

        # 1. Gravity delta
        max_delta = 0.0
        max_delta_room = ""
        for name in set(list(new_snapshot.keys()) + list(self._last_gravity_snapshot.keys())):
            old_g = self._last_gravity_snapshot.get(name, 0.0)
            new_g = new_snapshot.get(name, 0.0)
            delta = abs(new_g - old_g)
            if delta > max_delta:
                max_delta = delta
                max_delta_room = name

        if max_delta > self.SALIENCE_THRESHOLD:
            self._salience_triggered = True
            self._salience_reason = f"gravity delta {max_delta:.3f} in '{max_delta_room}'"

        # 2. High-value memory kind
        kind = memory.get("kind", "")
        if kind in self.HIGH_VALUE_KINDS:
            self._salience_triggered = True
            self._salience_reason = f"high-value memory: kind={kind}"

        # 3. Contradiction signal
        if memory.get("belnap_state") == "both":
            self._salience_triggered = True
            self._salience_reason = f"contradiction held: '{memory.get('text', '')[:50]}'"

        if memory.get("contradiction_count", 0) > 0:
            self._salience_triggered = True
            self._salience_reason = f"contradiction detected: count={memory['contradiction_count']}"

        # 4. New room created (domain never seen before)
        new_domains = set(memory.get("domain_tags") or [])
        for d in new_domains:
            if d not in self._last_gravity_snapshot:
                self._salience_triggered = True
                self._salience_reason = f"new domain discovered: '{d}'"

        if self._salience_triggered:
            self._salience_log.append({
                "timestamp": time.time(),
                "reason": self._salience_reason,
                "gravity_delta": round(max_delta, 4),
                "memory_id": memory.get("memory_id", ""),
                "memory_text": memory.get("text", "")[:80],
            })

        self._last_gravity_snapshot = new_snapshot

        return {
            "salience_triggered": self._salience_triggered,
            "salience_reason": self._salience_reason,
            "gravity_delta": round(max_delta, 4),
            "gravity_map": {k: round(v, 4) for k, v in new_snapshot.items()},
        }

    # -- Walker --

    def set_walker_context(self, domain_tags: list[str]):
        """Set walker position from conversation context.
        If the user is talking about photography, start there."""
        for tag in domain_tags:
            if tag in self.rooms:
                self.walker_position = tag
                return
        # Fallback: highest gravity room
        if self.rooms:
            best = max(self.rooms.items(), key=lambda x: x[1].gravity)
            self.walker_position = best[0]

    def walker_step(self) -> dict:
        """Walker navigates toward highest gravity, considering escape pressure."""
        if not self.rooms:
            return {"error": "no rooms"}

        current = self.rooms.get(self.walker_position) if self.walker_position else None
        resistance = current.stability if current else 0.0

        pulls = {}
        recent_visits = {}
        for step in self.walk_history[-3:]:
            if step.get("from"):
                recent_visits[step["from"]] = recent_visits.get(step["from"], 0) + 1

        for name, room in self.rooms.items():
            if name == self.walker_position:
                density_pull = math.sqrt(room.mass) * 0.3 if room.mass > 0 else 0
                pulls[name] = density_pull * resistance
            else:
                door_key = tuple(sorted([self.walker_position or "", name]))
                door = self.doors.get(door_key)
                cost = door.cost if door else 2.0
                pull = room.gravity / max(cost, 0.1)

                visit_count = recent_visits.get(name, 0)
                if visit_count > 0:
                    pull *= 0.5 ** visit_count

                pulls[name] = pull

        if not pulls or max(pulls.values()) == 0:
            heaviest = max(self.rooms.items(), key=lambda x: x[1].mass)
            target = heaviest[0]
            reason = "no pull, falling to heaviest"
        else:
            target = max(pulls, key=pulls.get)
            if target == self.walker_position:
                reason = f"staying (resistance={resistance:.2f})"
            else:
                reason = f"pulled by gravity {pulls[target]:.3f}"

        old_pos = self.walker_position
        self.walker_position = target

        step = {
            "from": old_pos,
            "to": target,
            "reason": reason,
            "gravity_map": {k: round(v, 3) for k, v in sorted(pulls.items(), key=lambda x: x[1], reverse=True)},
        }
        self.walk_history.append(step)
        return step

    # -- Rendering --

    def render(self) -> str:
        """Render the gravity topology."""
        lines = ["=" * 60, "GRAVITY BELIEF TOPOLOGY", "=" * 60]

        sorted_rooms = sorted(
            self.rooms.items(),
            key=lambda x: x[1].gravity,
            reverse=True,
        )

        for name, room in sorted_rooms:
            marker = " << WALKER" if name == self.walker_position else ""
            stability_tag = "STABLE" if room.stability > 0.8 else "FRAGILE" if room.stability > 0.5 else "UNSTABLE"
            lines.append(f"\n--- {name}{marker} ---")
            lines.append(f"  Memories: {len(room.memories)}  Mass: {room.mass:.2f}  "
                         f"Tension: {room.tension:.3f}  Gravity: {room.gravity:.3f}  [{stability_tag}]")
            lines.append(f"  Contradictions: {room.contradiction_pairs} held  "
                         f"Deprecated: {room.deprecated_count}  "
                         f"Freshness: {room.freshness:.2f}")

            if room.should_split(self.split_threshold):
                lines.append(f"  ** PRESSURE: room wants to split! **")

        if self._salience_triggered:
            lines.append(f"\n** SALIENCE: {self._salience_reason} **")

        lines.append("=" * 60)
        return "\n".join(lines)

    def render_for_prompt(self, max_rooms: int = 10) -> str:
        """Compact gravity map for injection into Aether's system prompt.
        Shows only the most significant rooms + any active salience."""
        sorted_rooms = sorted(
            self.rooms.items(),
            key=lambda x: x[1].gravity,
            reverse=True,
        )[:max_rooms]

        lines = ["BELIEF TOPOLOGY:"]
        for name, room in sorted_rooms:
            tag = ""
            if room.tension > 0.5:
                tag = " [UNSTABLE]"
            elif room.tension > 0.2:
                tag = " [TENSION]"
            elif room.stability > 0.8:
                tag = ""
            lines.append(
                f"  {name}: {len(room.memories)} memories, "
                f"gravity={room.gravity:.1f}, tension={room.tension:.2f}{tag}"
            )

        # Rooms wanting to split
        splitting = [
            name for name, room in self.rooms.items()
            if room.should_split(self.split_threshold)
        ]
        if splitting:
            lines.append(f"  PRESSURE: {', '.join(splitting)} want to split")

        # Active salience
        if self._salience_triggered:
            lines.append(f"  SALIENCE: {self._salience_reason}")

        return "\n".join(lines)

    def summary(self) -> dict:
        """Summary for logging / heartbeat consumption."""
        return {
            "rooms": {
                name: {
                    "memories": len(room.memories),
                    "mass": round(room.mass, 3),
                    "tension": round(room.tension, 3),
                    "gravity": round(room.gravity, 3),
                    "stability": round(room.stability, 3),
                    "contradictions": room.contradiction_pairs,
                    "deprecated": room.deprecated_count,
                    "freshness": round(room.freshness, 2),
                }
                for name, room in self.rooms.items()
            },
            "salience": {
                "triggered": self._salience_triggered,
                "reason": self._salience_reason,
                "log_length": len(self._salience_log),
            },
            "walker_position": self.walker_position,
            "total_memories": sum(len(r.memories) for r in self.rooms.values()),
            "total_rooms": len(self.rooms),
        }


# ---------------------------------------------------------------------------
# TEST: Load from production DB and see what happens
# ---------------------------------------------------------------------------
def test_from_db():
    """Load real memories + contradiction ledger and build gravity topology."""
    import sqlite3
    import json

    memory_db = "D:/AI_round2/personal_agent/crt_memory_shared.db"
    ledger_db = "D:/AI_round2/personal_agent/crt_ledger_shared.db"

    try:
        conn = sqlite3.connect(memory_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT memory_id, text, confidence, trust, domain_tags,
                   belnap_state, contradiction_count, deprecated,
                   timestamp, kind, authority, temporal_status
            FROM memories
            WHERE deprecated = 0 OR deprecated IS NULL
            ORDER BY timestamp DESC
            LIMIT 500
        """)

        memories = []
        for row in cursor.fetchall():
            m = dict(row)
            # Parse domain_tags from JSON string
            if m.get("domain_tags"):
                try:
                    m["domain_tags"] = json.loads(m["domain_tags"])
                except (json.JSONDecodeError, TypeError):
                    m["domain_tags"] = []
            else:
                m["domain_tags"] = []
            memories.append(m)

        conn.close()
        print(f"Loaded {len(memories)} memories from production DB")

    except Exception as e:
        print(f"Could not load from DB: {e}")
        print("Falling back to synthetic test data...")
        memories = _synthetic_memories()

    # Load contradiction ledger
    contradictions = []
    try:
        conn = sqlite3.connect(ledger_db)
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
        print(f"Loaded {len(contradictions)} contradictions from ledger")
    except Exception as e:
        print(f"Could not load ledger: {e}")

    # Build gravity topology
    gbs = GravityBeliefStore()
    gbs.ingest_memories(memories)
    if contradictions:
        gbs.ingest_contradictions(contradictions)

    # Fuse micro-rooms
    fused = gbs.fuse_micro_rooms(min_memories=3)
    if fused:
        print(f"\nFused {len(fused)} micro-rooms:")
        for f in fused:
            print(f"  {f}")

    print(gbs.render())

    # Prompt-ready gravity summary
    print("\n--- PROMPT-READY GRAVITY MAP ---")
    print(gbs.render_for_prompt())

    # Walker test
    print("\n--- Walker Navigation (5 steps) ---")
    gbs.walker_position = list(gbs.rooms.keys())[0] if gbs.rooms else None
    for i in range(5):
        step = gbs.walker_step()
        print(f"  Step {i+1}: {step['from']} -> {step['to']}  ({step['reason']})")

    # Summary
    s = gbs.summary()
    print(f"\nTotal: {s['total_rooms']} rooms, {s['total_memories']} memories")
    print(f"Top 5 by gravity:")
    top = sorted(s["rooms"].items(), key=lambda x: x[1]["gravity"], reverse=True)[:5]
    for name, data in top:
        print(f"  {name}: gravity={data['gravity']:.3f} mass={data['mass']:.2f} "
              f"tension={data['tension']:.3f} memories={data['memories']}")

    # Simulate a conversation turn with salience
    print("\n--- Simulating conversation turn ---")
    new_memory = {
        "memory_id": "test_new_memory",
        "text": "Nick quit his print shop job and is freelancing full time",
        "confidence": 0.9,
        "trust": 0.85,
        "domain_tags": ["employment", "freelance"],
        "belnap_state": "true",
        "contradiction_count": 1,  # contradicts prior employment info
        "kind": "user_fact",
        "timestamp": time.time(),
    }
    result = gbs.ingest_single(new_memory)
    print(f"  Salience: {result['salience_triggered']}")
    print(f"  Reason: {result['salience_reason']}")
    print(f"  Gravity delta: {result['gravity_delta']}")


def _synthetic_memories() -> list[dict]:
    """Fallback test data if DB isn't available."""
    now = time.time()
    return [
        {"memory_id": "m1", "text": "Nick loves coffee", "confidence": 0.85, "trust": 0.8,
         "domain_tags": ["preferences"], "belnap_state": "both", "contradiction_count": 1,
         "kind": "user_fact", "timestamp": now - 86400},
        {"memory_id": "m2", "text": "Nick quit coffee", "confidence": 0.7, "trust": 0.75,
         "domain_tags": ["preferences"], "belnap_state": "both", "contradiction_count": 1,
         "kind": "user_fact", "timestamp": now - 3600},
        {"memory_id": "m3", "text": "Nick works at a print shop", "confidence": 0.6, "trust": 0.5,
         "domain_tags": ["employment"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "user_fact", "timestamp": now - 86400 * 30, "deprecated": True},
        {"memory_id": "m4", "text": "Nick is a freelance developer", "confidence": 0.9, "trust": 0.9,
         "domain_tags": ["employment", "freelance"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "user_fact", "timestamp": now - 86400},
        {"memory_id": "m5", "text": "Nick prefers dark mode", "confidence": 0.8, "trust": 0.7,
         "domain_tags": ["preferences", "ui"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "preference", "timestamp": now - 86400 * 7},
        {"memory_id": "m6", "text": "Aether uses CRT architecture", "confidence": 0.95, "trust": 0.95,
         "domain_tags": ["architecture", "system"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "observation", "timestamp": now - 86400 * 14},
        {"memory_id": "m7", "text": "Nick is building belief backpropagation", "confidence": 0.85, "trust": 0.8,
         "domain_tags": ["research", "architecture"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "user_fact", "timestamp": now - 86400 * 3},
        {"memory_id": "m8", "text": "The cascade paper has 5 theorems", "confidence": 0.9, "trust": 0.85,
         "domain_tags": ["research"], "belnap_state": "true", "contradiction_count": 0,
         "kind": "observation", "timestamp": now - 86400 * 10},
    ]


if __name__ == "__main__":
    test_from_db()
