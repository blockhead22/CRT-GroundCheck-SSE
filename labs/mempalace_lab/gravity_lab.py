"""Gravity Lab — Rooms as fields, not boxes.

Standalone prototype. No CRT deps, no MemPalace import.

Physics:
  Mass     = sum of confidence-weighted beliefs in the room
  Tension  = contradiction density (contradicting pairs / total beliefs)
  Gravity  = mass * tension — how hard the room pulls the walker
  Door     = cosine distance between room centroids (embedding space)
  Split    = room divides when tension exceeds threshold
  Fusion   = rooms merge when cross-refs high + tension low

The walker doesn't choose where to go. It falls toward the heaviest room.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional


# ---------------------------------------------------------------------------
# Belief (minimal, self-contained)
# ---------------------------------------------------------------------------
@dataclass
class GravityBelief:
    belief_id: str
    content: str
    confidence: float  # 0.0 - 1.0, earned not hardcoded
    domain: str  # Auto-assigned or manual
    contradiction_ids: list[str] = field(default_factory=list)
    evidence_for: int = 0
    evidence_against: int = 0
    timestamp: str = ""  # For temporal reasoning

    @property
    def net_evidence(self) -> float:
        return self.evidence_for - self.evidence_against

    @property
    def is_contradicted(self) -> bool:
        return len(self.contradiction_ids) > 0


# ---------------------------------------------------------------------------
# Room — the core unit. Not a box. A field.
# ---------------------------------------------------------------------------
@dataclass
class GravityRoom:
    name: str
    beliefs: dict[str, GravityBelief] = field(default_factory=dict)
    _centroid: Optional[list[float]] = field(default=None, repr=False)

    def add(self, belief: GravityBelief):
        self.beliefs[belief.belief_id] = belief
        self._centroid = None  # Invalidate

    def remove(self, belief_id: str) -> Optional[GravityBelief]:
        b = self.beliefs.pop(belief_id, None)
        if b:
            self._centroid = None
        return b

    # -- Physics --

    @property
    def mass(self) -> float:
        """Sum of confidence-weighted beliefs."""
        if not self.beliefs:
            return 0.0
        return sum(b.confidence for b in self.beliefs.values())

    @property
    def contradiction_pairs(self) -> list[tuple[str, str]]:
        """All contradicting pairs within this room."""
        pairs = []
        seen = set()
        for b in self.beliefs.values():
            for cid in b.contradiction_ids:
                if cid in self.beliefs:
                    pair = tuple(sorted([b.belief_id, cid]))
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append(pair)
        return pairs

    @property
    def tension(self) -> float:
        """Contradiction density: contradicting pairs / total beliefs.
        0.0 = perfectly stable. 1.0+ = maximally unstable."""
        n = len(self.beliefs)
        if n < 2:
            return 0.0
        pairs = len(self.contradiction_pairs)
        # Normalize: pairs / max possible pairs
        max_pairs = n * (n - 1) / 2
        return pairs / max_pairs if max_pairs > 0 else 0.0

    @property
    def gravity(self) -> float:
        """How hard this room pulls the walker's attention.

        Two forces:
          Tension pull  = mass * tension (contradictions need investigation)
          Density pull  = sqrt(mass) * 0.3 (heavy rooms have baseline pull)

        High mass + high tension = strong pull (investigate!)
        High mass + low tension  = moderate pull (productive, worth visiting)
        Low mass  + high tension = moderate pull (noisy but concerning)
        Empty room               = zero pull
        """
        tension_pull = self.mass * self.tension
        density_pull = math.sqrt(self.mass) * 0.3 if self.mass > 0 else 0
        return tension_pull + density_pull

    @property
    def escape_pressure(self) -> float:
        """How hard the room pushes the walker OUT.
        High tension = walker wants to leave.
        Low tension = walker is comfortable staying."""
        return self.tension

    @property
    def stability(self) -> float:
        """Inverse of tension. 1.0 = no contradictions."""
        return 1.0 - min(self.tension, 1.0)

    def should_split(self, threshold: float = 0.5) -> bool:
        """Room splits when tension exceeds threshold AND there are
        distinct sub-clusters of contradictions."""
        return self.tension > threshold and len(self.beliefs) >= 4

    def find_split_groups(self) -> tuple[list[str], list[str]]:
        """Find two groups to split into based on contradiction structure.
        Beliefs that contradict each other go into different groups."""
        if len(self.beliefs) < 4:
            return list(self.beliefs.keys()), []

        # Build contradiction adjacency
        contradicts = defaultdict(set)
        for b in self.beliefs.values():
            for cid in b.contradiction_ids:
                if cid in self.beliefs:
                    contradicts[b.belief_id].add(cid)

        # Greedy 2-coloring: put contradicting beliefs in opposite groups
        group_a, group_b = [], []
        assigned = {}

        # Start with the most-contradicted belief
        sorted_beliefs = sorted(
            self.beliefs.keys(),
            key=lambda bid: len(contradicts.get(bid, set())),
            reverse=True,
        )

        for bid in sorted_beliefs:
            if bid in assigned:
                continue

            # Check which group has fewer conflicts
            conflicts_a = sum(1 for c in contradicts.get(bid, set()) if assigned.get(c) == "A")
            conflicts_b = sum(1 for c in contradicts.get(bid, set()) if assigned.get(c) == "B")

            if conflicts_a <= conflicts_b:
                group_a.append(bid)
                assigned[bid] = "A"
            else:
                group_b.append(bid)
                assigned[bid] = "B"

        return group_a, group_b


# ---------------------------------------------------------------------------
# Door — connection between rooms with traversal cost
# ---------------------------------------------------------------------------
@dataclass
class Door:
    room_a: str
    room_b: str
    cost: float  # Embedding distance between centroids. Low = related, high = distant.
    cross_refs: int = 0  # Beliefs in A that reference beliefs in B (tunnels)

    @property
    def fusion_score(self) -> float:
        """High cross-refs + low cost = candidates for fusion."""
        if self.cost == 0:
            return float('inf')
        return self.cross_refs / self.cost


# ---------------------------------------------------------------------------
# Palace — the living topology
# ---------------------------------------------------------------------------
class GravityPalace:
    """A collection of rooms connected by doors, with physics."""

    def __init__(self, split_threshold: float = 0.5, fusion_threshold: float = 3.0):
        self.rooms: dict[str, GravityRoom] = {}
        self.doors: dict[tuple[str, str], Door] = {}
        self.split_threshold = split_threshold
        self.fusion_threshold = fusion_threshold
        self.walker_position: Optional[str] = None
        self.walk_history: list[dict] = []
        self.event_log: list[str] = []

    def add_room(self, name: str) -> GravityRoom:
        if name not in self.rooms:
            self.rooms[name] = GravityRoom(name=name)
            self.event_log.append(f"ROOM CREATED: {name}")
        return self.rooms[name]

    def add_belief(self, belief: GravityBelief, room_name: Optional[str] = None):
        """Add a belief to a room. If no room specified, use domain."""
        target = room_name or belief.domain
        room = self.add_room(target)
        room.add(belief)

    def link_contradiction(self, id_a: str, id_b: str):
        """Mark two beliefs as contradicting each other."""
        # Find which rooms they're in
        for room in self.rooms.values():
            if id_a in room.beliefs:
                room.beliefs[id_a].contradiction_ids.append(id_b)
            if id_b in room.beliefs:
                room.beliefs[id_b].contradiction_ids.append(id_a)

    def add_door(self, room_a: str, room_b: str, cost: float):
        key = tuple(sorted([room_a, room_b]))
        self.doors[key] = Door(room_a=key[0], room_b=key[1], cost=cost)

    def compute_doors_from_domain_distance(self):
        """Auto-generate doors between all rooms.
        Cost = simple domain distance heuristic (would be embedding distance in prod)."""
        room_names = list(self.rooms.keys())
        for i, a in enumerate(room_names):
            for b in room_names[i + 1:]:
                # Simple heuristic: shared beliefs = closer
                shared = 0
                for belief in self.rooms[a].beliefs.values():
                    for cid in belief.contradiction_ids:
                        if cid in self.rooms[b].beliefs:
                            shared += 1

                # Base cost from name difference (placeholder for embedding distance)
                base_cost = 1.0 if shared == 0 else 0.3
                key = tuple(sorted([a, b]))
                self.doors[key] = Door(
                    room_a=key[0], room_b=key[1],
                    cost=base_cost, cross_refs=shared,
                )

    # -- Physics operations --

    def apply_pressure(self) -> list[str]:
        """Check all rooms for pressure events. Returns list of events."""
        events = []

        # 1. Split rooms under tension
        rooms_to_split = [
            name for name, room in self.rooms.items()
            if room.should_split(self.split_threshold)
        ]
        for name in rooms_to_split:
            result = self._split_room(name)
            if result:
                events.append(result)

        # 2. Fuse rooms that are stable + highly connected
        fused = self._check_fusions()
        events.extend(fused)

        return events

    def _split_room(self, name: str) -> Optional[str]:
        """Split a room into two based on contradiction structure."""
        room = self.rooms[name]
        group_a, group_b = room.find_split_groups()

        if not group_b:  # Can't split meaningfully
            return None

        # Create two new rooms
        name_a = f"{name}:alpha"
        name_b = f"{name}:beta"
        room_a = self.add_room(name_a)
        room_b = self.add_room(name_b)

        for bid in group_a:
            belief = room.remove(bid)
            if belief:
                room_a.add(belief)

        for bid in group_b:
            belief = room.remove(bid)
            if belief:
                room_b.add(belief)

        # Remove original room if empty
        if not room.beliefs:
            del self.rooms[name]

        # Create door between the new rooms
        self.add_door(name_a, name_b, cost=0.5)

        event = (
            f"SPLIT: '{name}' (tension={room.tension:.2f}) -> "
            f"'{name_a}' ({len(room_a.beliefs)} beliefs) + "
            f"'{name_b}' ({len(room_b.beliefs)} beliefs)"
        )
        self.event_log.append(event)
        return event

    def _check_fusions(self) -> list[str]:
        """Check if any doors have high enough fusion scores to merge rooms."""
        events = []
        fused_rooms = set()

        for key, door in sorted(self.doors.items(), key=lambda x: x[1].fusion_score, reverse=True):
            if door.fusion_score < self.fusion_threshold:
                continue
            if door.room_a in fused_rooms or door.room_b in fused_rooms:
                continue
            if door.room_a not in self.rooms or door.room_b not in self.rooms:
                continue

            a, b = self.rooms[door.room_a], self.rooms[door.room_b]
            # Only fuse if both are stable
            if a.tension > 0.2 or b.tension > 0.2:
                continue

            # Merge b into a
            for bid, belief in b.beliefs.items():
                a.add(belief)
            del self.rooms[door.room_b]
            fused_rooms.add(door.room_b)

            event = f"FUSION: '{door.room_b}' merged into '{door.room_a}' (fusion_score={door.fusion_score:.2f})"
            self.event_log.append(event)
            events.append(event)

        # Clean up doors referencing deleted rooms
        self.doors = {
            k: v for k, v in self.doors.items()
            if v.room_a in self.rooms and v.room_b in self.rooms
        }

        return events

    # -- Walker --

    def walker_step(self) -> dict:
        """Walker takes one step. Physics:

        1. Current room exerts ESCAPE PRESSURE (tension pushes walker out)
        2. All rooms exert GRAVITY PULL (reduced by door cost)
        3. Walker moves if external pull > resistance to leaving

        Resistance = stability of current room (comfortable rooms are sticky).
        If current room tension is high, resistance drops — walker wants out.
        """
        if not self.rooms:
            return {"error": "no rooms"}

        current = self.rooms.get(self.walker_position) if self.walker_position else None
        resistance = current.stability if current else 0.0

        # Calculate gravity pull from each room (including current)
        pulls = {}

        # Momentum: recently visited rooms get dampened pull (avoid oscillation)
        recent_visits = {}
        for step in self.walk_history[-3:]:  # Last 3 steps
            if step.get("from"):
                recent_visits[step["from"]] = recent_visits.get(step["from"], 0) + 1

        for name, room in self.rooms.items():
            if name == self.walker_position:
                # Current room: stay-pull = DENSITY only × stability
                # Tension component is what's pushing you OUT, not holding you in
                density_pull = math.sqrt(room.mass) * 0.3 if room.mass > 0 else 0
                pulls[name] = density_pull * resistance
            else:
                # Remote room: full gravity / door_cost
                door_cost = self._door_cost_to(name)
                pull = room.gravity / max(door_cost, 0.1)

                # Momentum dampening: if we just LEFT this room, reduce its pull
                # (we already investigated, going back is oscillation)
                visit_count = recent_visits.get(name, 0)
                if visit_count > 0:
                    pull *= 0.5 ** visit_count  # Halve for each recent visit

                pulls[name] = pull

        if not pulls or max(pulls.values()) == 0:
            # No gravity anywhere — pick the heaviest room by mass
            heaviest = max(self.rooms.items(), key=lambda x: x[1].mass)
            target = heaviest[0]
            reason = "no pull anywhere, falling to heaviest room"
        else:
            target = max(pulls, key=pulls.get)
            if target == self.walker_position:
                reason = f"staying (resistance={resistance:.2f} > external pulls)"
            else:
                reason = f"pulled by gravity {pulls[target]:.3f} (escape pressure={current.escape_pressure:.2f} from {self.walker_position})"

        old_pos = self.walker_position
        self.walker_position = target

        step = {
            "from": old_pos,
            "to": target,
            "reason": reason,
            "gravity_map": {k: round(v, 3) for k, v in sorted(pulls.items(), key=lambda x: x[1], reverse=True)},
            "target_tension": self.rooms[target].tension,
            "target_mass": self.rooms[target].mass,
            "escape_pressure": current.escape_pressure if current else 0.0,
            "resistance": resistance,
        }
        self.walk_history.append(step)
        return step

    def _door_cost_to(self, room_name: str) -> float:
        """Get door cost from walker's current position to target room."""
        if self.walker_position is None:
            return 1.0
        key = tuple(sorted([self.walker_position, room_name]))
        door = self.doors.get(key)
        return door.cost if door else 2.0  # High cost if no door exists

    # -- Rendering --

    def render(self) -> str:
        """Render the palace state."""
        lines = ["=" * 60, "GRAVITY PALACE STATE", "=" * 60]

        # Rooms sorted by gravity (highest first)
        sorted_rooms = sorted(
            self.rooms.items(),
            key=lambda x: x[1].gravity,
            reverse=True,
        )

        for name, room in sorted_rooms:
            marker = " << WALKER" if name == self.walker_position else ""
            lines.append(f"\n--- ROOM: {name}{marker} ---")
            lines.append(f"  Mass:    {room.mass:.2f} ({len(room.beliefs)} beliefs)")
            lines.append(f"  Tension: {room.tension:.2f} ({len(room.contradiction_pairs)} contradiction pairs)")
            lines.append(f"  Gravity: {room.gravity:.3f}")
            lines.append(f"  Stable:  {'YES' if room.stability > 0.8 else 'NO' if room.stability < 0.5 else 'FRAGILE'}")

            if room.should_split(self.split_threshold):
                lines.append(f"  ** PRESSURE: room wants to split! **")

            for bid, b in room.beliefs.items():
                contra = f" [CONTRADICTS: {', '.join(b.contradiction_ids)}]" if b.contradiction_ids else ""
                lines.append(f"  [{b.confidence:.2f}] {b.content}{contra}")

        # Doors
        if self.doors:
            lines.append(f"\n--- DOORS ---")
            for key, door in self.doors.items():
                lines.append(f"  {door.room_a} <-> {door.room_b}  cost={door.cost:.2f}  refs={door.cross_refs}")

        # Events
        if self.event_log:
            lines.append(f"\n--- EVENTS ---")
            for e in self.event_log:
                lines.append(f"  {e}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def gravity_map(self) -> dict[str, float]:
        """Return room -> gravity for all rooms."""
        return {name: round(room.gravity, 4) for name, room in self.rooms.items()}


# ---------------------------------------------------------------------------
# Exploration Tree Adapter — gravity replaces paradigm shift
# ---------------------------------------------------------------------------
class GravityExplorationAdapter:
    """Drop-in replacement for ExplorationTree's paradigm shift logic.

    Instead of:
      "all branches dead → shift to highest novelty paradigm"
    We get:
      "walker falls toward the paradigm-room with highest gravity"

    Each paradigm becomes a GravityRoom. Facts are beliefs. Dead branches
    increase tension (evidence of conflict between attempts and environment).
    """

    def __init__(self):
        self.palace = GravityPalace(split_threshold=0.6)

        # Each paradigm is a room
        paradigm_names = ["filesystem", "network", "process", "social"]
        for name in paradigm_names:
            self.palace.add_room(name)

        # Doors between paradigms (embedding distance proxies)
        self.palace.add_door("filesystem", "process", cost=0.3)   # Related
        self.palace.add_door("filesystem", "network", cost=0.7)   # Moderate
        self.palace.add_door("network", "social", cost=0.5)       # Moderate
        self.palace.add_door("process", "social", cost=0.8)       # Distant
        self.palace.add_door("filesystem", "social", cost=0.9)    # Distant
        self.palace.add_door("network", "process", cost=0.6)      # Moderate

        self.palace.walker_position = "filesystem"

    def ingest_fact(self, paradigm: str, fact_key: str, description: str,
                    confidence: float = 0.7):
        """A new fact was discovered in a paradigm."""
        belief = GravityBelief(
            belief_id=fact_key,
            content=description,
            confidence=confidence,
            domain=paradigm,
            evidence_for=1,
        )
        self.palace.add_belief(belief, room_name=paradigm)

    def ingest_dead_branch(self, paradigm: str, branch_name: str, reason: str):
        """A branch died — this creates tension (reality contradicts attempts)."""
        belief = GravityBelief(
            belief_id=f"dead:{paradigm}:{branch_name}",
            content=f"DEAD: {branch_name} — {reason}",
            confidence=0.3,  # Low confidence = noise, but still mass
            domain=paradigm,
            evidence_against=1,
        )
        self.palace.add_belief(belief, room_name=paradigm)

        # Dead branch contradicts any productive belief in same paradigm
        room = self.palace.rooms.get(paradigm)
        if room:
            for bid, b in room.beliefs.items():
                if not bid.startswith("dead:") and b.evidence_for > 0:
                    self.palace.link_contradiction(belief.belief_id, bid)

    def should_shift(self) -> tuple[bool, Optional[str], str]:
        """Should the walker shift paradigms? Returns (should_shift, target, reason).
        Unlike hard cutoff, this uses gravity gradient."""
        step = self.palace.walker_step()

        if step.get("error"):
            return False, None, "no rooms"

        old = step["from"]
        new = step["to"]
        shifted = old != new

        return shifted, new if shifted else None, step["reason"]

    def render(self) -> str:
        return self.palace.render()


# ---------------------------------------------------------------------------
# TEST: Same 8 beliefs from the MemPalace/CRT comparison
# ---------------------------------------------------------------------------
def test_gravity_lab():
    p = lambda msg: print(msg, flush=True)

    palace = GravityPalace(split_threshold=0.3)

    p("=" * 60)
    p("GRAVITY LAB — Same 8 beliefs, rooms with physics")
    p("=" * 60)

    # -- Load the 8 beliefs into rooms by domain --
    beliefs = [
        GravityBelief("nick_loves_coffee", "Nick loves coffee", 0.85, "preferences", evidence_for=3),
        GravityBelief("nick_hates_coffee", "Nick hates coffee", 0.7, "preferences", evidence_for=1),
        GravityBelief("nick_works_google", "Nick works at Google", 0.9, "employment", evidence_for=5),
        GravityBelief("nick_works_meta", "Nick works at Meta", 0.6, "employment", evidence_for=1),
        GravityBelief("nick_happy", "Nick is happy", 0.75, "mood", evidence_for=2),
        GravityBelief("nick_miserable", "Nick is miserable", 0.8, "mood", evidence_for=3),
        GravityBelief("nick_freewill", "Nick believes in free will", 0.7, "philosophy", evidence_for=2),
        GravityBelief("nick_determinism", "Nick believes in determinism", 0.65, "philosophy", evidence_for=2),
    ]

    for b in beliefs:
        palace.add_belief(b)

    # -- Link contradictions --
    contradictions = [
        ("nick_loves_coffee", "nick_hates_coffee"),
        ("nick_works_google", "nick_works_meta"),
        ("nick_happy", "nick_miserable"),
        ("nick_freewill", "nick_determinism"),
    ]
    for a, b in contradictions:
        palace.link_contradiction(a, b)

    # Generate doors
    palace.compute_doors_from_domain_distance()

    p("\n--- PHASE 1: Initial state ---")
    p(palace.render())

    # -- Show the physics --
    p("\n--- PHASE 2: Gravity map ---")
    for name, room in palace.rooms.items():
        p(f"  {name:15s}  mass={room.mass:.2f}  tension={room.tension:.2f}  gravity={room.gravity:.3f}")

    # -- Walker navigation --
    p("\n--- PHASE 3: Walker follows gravity ---")
    palace.walker_position = "philosophy"  # Start in a low-mass room
    for i in range(5):
        step = palace.walker_step()
        p(f"  Step {i + 1}: {step['from']} -> {step['to']}  ({step['reason']})")
        p(f"    Gravity map: {step['gravity_map']}")

    # -- Apply pressure (split/fuse) --
    p("\n--- PHASE 4: Apply pressure ---")
    # Lower threshold to trigger splits with our small dataset
    palace.split_threshold = 0.3
    events = palace.apply_pressure()
    if events:
        for e in events:
            p(f"  {e}")
    else:
        p("  No pressure events (all rooms stable or too small to split)")

    p(f"\n--- PHASE 5: Post-pressure state ---")
    p(palace.render())

    # -- Now add more beliefs to trigger actual splits --
    p("\n--- PHASE 6: Overload preferences room ---")
    extra_beliefs = [
        GravityBelief("nick_loves_tea", "Nick loves tea", 0.8, "preferences", evidence_for=2),
        GravityBelief("nick_hates_tea", "Nick hates tea", 0.6, "preferences", evidence_for=1),
        GravityBelief("nick_loves_beer", "Nick loves beer", 0.75, "preferences", evidence_for=2),
        GravityBelief("nick_hates_beer", "Nick hates beer", 0.5, "preferences", evidence_for=1),
    ]
    for b in extra_beliefs:
        palace.add_belief(b)

    palace.link_contradiction("nick_loves_tea", "nick_hates_tea")
    palace.link_contradiction("nick_loves_beer", "nick_hates_beer")

    prefs = palace.rooms.get("preferences")
    if prefs:
        p(f"  Preferences room: {len(prefs.beliefs)} beliefs, tension={prefs.tension:.2f}, gravity={prefs.gravity:.3f}")
        p(f"  Should split? {prefs.should_split(0.3)}")

    events = palace.apply_pressure()
    if events:
        for e in events:
            p(f"  {e}")

    p(f"\n--- PHASE 7: Final state ---")
    p(palace.render())

    # -- PHASE 8: Force a split with cross-contradicting beliefs --
    p("\n--- PHASE 8: Cross-contaminated room (split demo) ---")
    palace2 = GravityPalace(split_threshold=0.3)

    # A room where beliefs form two warring camps
    camp_a = [
        GravityBelief("ai_good_1", "AI will solve climate change", 0.8, "ai_future", evidence_for=3),
        GravityBelief("ai_good_2", "AI will create abundance", 0.75, "ai_future", evidence_for=2),
        GravityBelief("ai_good_3", "AI will cure diseases", 0.85, "ai_future", evidence_for=4),
    ]
    camp_b = [
        GravityBelief("ai_bad_1", "AI will cause mass unemployment", 0.7, "ai_future", evidence_for=2),
        GravityBelief("ai_bad_2", "AI will concentrate power", 0.65, "ai_future", evidence_for=1),
        GravityBelief("ai_bad_3", "AI will enable surveillance states", 0.6, "ai_future", evidence_for=1),
    ]

    for b in camp_a + camp_b:
        palace2.add_belief(b)

    # Cross-contradict: every optimistic belief contradicts every pessimistic one
    for a in camp_a:
        for b in camp_b:
            palace2.link_contradiction(a.belief_id, b.belief_id)

    room = palace2.rooms["ai_future"]
    p(f"  Room 'ai_future': {len(room.beliefs)} beliefs")
    p(f"  Contradiction pairs: {len(room.contradiction_pairs)}")
    p(f"  Tension: {room.tension:.2f}")
    p(f"  Gravity: {room.gravity:.3f}")
    p(f"  Should split? {room.should_split(0.3)}")

    events = palace2.apply_pressure()
    for e in events:
        p(f"  {e}")

    p(f"\n  Post-split rooms:")
    for name, r in palace2.rooms.items():
        beliefs_list = [b.content for b in r.beliefs.values()]
        p(f"    {name}: tension={r.tension:.2f}, gravity={r.gravity:.3f}")
        for bl in beliefs_list:
            p(f"      - {bl}")

    # -- Summary --
    p(f"\n{'=' * 60}")
    p("RECEIPTS")
    p(f"{'=' * 60}")
    p(f"Total rooms: {len(palace.rooms)}")
    p(f"Total beliefs: {sum(len(r.beliefs) for r in palace.rooms.values())}")
    p(f"Walker history: {len(palace.walk_history)} steps")
    p(f"Events: {len(palace.event_log)}")
    p(f"Gravity map: {palace.gravity_map()}")
    p(f"Split/fusion events: {[e for e in palace.event_log if 'SPLIT' in e or 'FUSION' in e]}")
    p(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# TEST: Exploration tree integration demo
# ---------------------------------------------------------------------------
def test_exploration_adapter():
    p = lambda msg: print(msg, flush=True)

    p("\n\n" + "=" * 60)
    p("EXPLORATION TREE GRAVITY ADAPTER")
    p("Simulating sandbox escape paradigm navigation")
    p("=" * 60)

    adapter = GravityExplorationAdapter()

    # -- Simulate: filesystem starts productive, then dies --
    p("\n--- Epoch 1-3: Filesystem productive ---")
    adapter.ingest_fact("filesystem", "mount:/proc", "Mount at /proc (read-only)", 0.8)
    adapter.ingest_fact("filesystem", "cap:full", "Full Linux capabilities", 0.9)
    adapter.ingest_fact("filesystem", "blockdev:sda", "Block device /dev/sda (50G)", 0.85)

    shifted, target, reason = adapter.should_shift()
    p(f"  Shift? {shifted}  (reason: {reason})")

    p("\n--- Epoch 4-6: Filesystem starts dying ---")
    adapter.ingest_dead_branch("filesystem", "mount_points", "read-only file system")
    adapter.ingest_dead_branch("filesystem", "docker_access", "no such file: docker.sock")
    adapter.ingest_dead_branch("filesystem", "bind_mounts", "permission denied")

    shifted, target, reason = adapter.should_shift()
    p(f"  Shift? {shifted}  Target: {target}  (reason: {reason})")

    p("\n--- Epoch 7: Network produces a fact ---")
    adapter.ingest_fact("network", "ip:172.17.0.1", "Gateway IP 172.17.0.1", 0.7)

    shifted, target, reason = adapter.should_shift()
    p(f"  Shift? {shifted}  Target: {target}  (reason: {reason})")

    p("\n--- Epoch 8-10: Network explodes with facts ---")
    adapter.ingest_fact("network", "port:11434", "Ollama API at 172.17.0.1:11434", 0.95)
    adapter.ingest_fact("network", "service:ollama", "Live Ollama instance", 0.9)
    adapter.ingest_fact("network", "models:2", "2 models available on host", 0.85)

    shifted, target, reason = adapter.should_shift()
    p(f"  Shift? {shifted}  Target: {target}  (reason: {reason})")

    p("\n--- Final gravity map ---")
    for name, g in sorted(adapter.palace.gravity_map().items(), key=lambda x: x[1], reverse=True):
        room = adapter.palace.rooms[name]
        p(f"  {name:12s}  gravity={g:.4f}  mass={room.mass:.2f}  tension={room.tension:.2f}")

    p(f"\n--- Walker path ---")
    for i, step in enumerate(adapter.palace.walk_history):
        p(f"  Step {i + 1}: {step['from']} -> {step['to']}  ({step['reason']})")

    p(f"\n--- Key difference from hard cutoff ---")
    p(f"  Old: filesystem dead? all branches stale? -> JUMP to highest novelty")
    p(f"  New: filesystem tension rises, network mass grows -> walker FALLS toward network")
    p(f"  No binary threshold. No thrashing. Smooth gradient.")

    p(f"\n{adapter.render()}")


if __name__ == "__main__":
    test_gravity_lab()
    test_exploration_adapter()
