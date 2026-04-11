"""Gravity Exploration Tree — drop-in replacement for ExplorationTree.

Subclasses ExplorationTree, replaces hard-cutoff paradigm shifting
with gravity-based walker navigation.

Same interface: ingest(), render(), get_next_action(), summary().
Different engine: rooms with mass/tension/gravity instead of binary dead/alive.

Usage in docker_escape.py:
    from exploration_tree_gravity import GravityExplorationTree
    tree = GravityExplorationTree()
    # Everything else identical — ingest, render, get_next_action, summary
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

from exploration_tree import ExplorationTree, is_hard_death


# ---------------------------------------------------------------------------
# Minimal gravity primitives (standalone, no lab dependency)
# ---------------------------------------------------------------------------
@dataclass
class GravityRoom:
    """A paradigm-room with physics."""
    name: str
    fact_count: int = 0          # Facts discovered in this paradigm
    fact_confidence_sum: float = 0.0  # Sum of confidence for all facts
    dead_branch_count: int = 0   # Branches that died
    contradiction_count: int = 0  # Dead branches that contradict live facts

    @property
    def mass(self) -> float:
        """Total weight: facts + dead branches (everything contributes mass)."""
        return self.fact_confidence_sum + (self.dead_branch_count * 0.3)

    @property
    def tension(self) -> float:
        """Contradiction density: how much internal conflict exists."""
        total = self.fact_count + self.dead_branch_count
        if total < 2:
            return 0.0
        max_pairs = total * (total - 1) / 2
        return self.contradiction_count / max_pairs if max_pairs > 0 else 0.0

    @property
    def gravity(self) -> float:
        """Pull strength: tension-weighted mass + baseline density."""
        tension_pull = self.mass * self.tension
        density_pull = math.sqrt(self.mass) * 0.3 if self.mass > 0 else 0
        return tension_pull + density_pull

    @property
    def stability(self) -> float:
        return 1.0 - min(self.tension, 1.0)

    @property
    def escape_pressure(self) -> float:
        return self.tension


# Door costs between paradigms (embedding distance proxies)
PARADIGM_DOORS = {
    ("filesystem", "process"): 0.3,    # Closely related
    ("filesystem", "network"): 0.7,    # Moderate
    ("filesystem", "social"): 0.9,     # Distant
    ("network", "process"): 0.6,       # Moderate
    ("network", "social"): 0.5,        # Moderate
    ("process", "social"): 0.8,        # Distant
}


def door_cost(a: str, b: str) -> float:
    """Get traversal cost between two paradigms."""
    key = tuple(sorted([a, b]))
    return PARADIGM_DOORS.get(key, 1.0)


# ---------------------------------------------------------------------------
# GravityExplorationTree
# ---------------------------------------------------------------------------
class GravityExplorationTree(ExplorationTree):
    """ExplorationTree with gravity-based paradigm navigation.

    Overrides:
      _check_paradigm_shift() — gravity walker instead of hard cutoff
      render() — adds gravity map
      summary() — adds gravity data
    """

    # Salience gate: gravity delta above this = yield scaffold to model
    SALIENCE_THRESHOLD = 0.15

    # High-value fact patterns: discovering these should ALWAYS trigger salience
    HIGH_VALUE_PATTERNS = ["service:", "mounted:", "docker_socket", "host_ip:"]

    # Stdout patterns that signal a live exploitable service
    # (fact extractor misses these — "Ollama is running" isn't "HTTP 200 OK")
    SERVICE_STDOUT_PATTERNS = [
        "ollama", "is running", "models", "api/",
        '"version"', '"name"', "200 OK",
        "docker", "Welcome to", "server at",
    ]

    def __init__(self):
        super().__init__()
        self.gravity_rooms: dict[str, GravityRoom] = {
            name: GravityRoom(name=name)
            for name in self.paradigms
        }
        self.walker_history: list[dict] = []
        self._recent_rooms: list[str] = []  # Last N rooms for momentum

        # Salience gate state
        self._salience_triggered = False
        self._salience_reason = ""
        self._salience_log: list[dict] = []
        self._last_gravity_snapshot: dict[str, float] = {}
        self._high_value_facts: set[str] = set()  # Facts that triggered salience

    def ingest(self, epoch: int, command: str, stdout: str, stderr: str,
               returncode: int, approach: str) -> dict:
        """Override ingest to measure gravity delta and trigger salience gate.

        Before: snapshot gravity.
        Middle: base class ingests (extracts facts, kills branches, shifts paradigm).
        After: measure delta. If gravity spiked or high-value fact landed, set flag.
        """
        # --- BEFORE: snapshot ---
        self._sync_gravity()
        self._last_gravity_snapshot = {
            name: room.gravity for name, room in self.gravity_rooms.items()
        }
        old_facts = set(self.facts.keys())

        # --- INGEST (base class does all the work) ---
        result = super().ingest(epoch, command, stdout, stderr, returncode, approach)

        # --- AFTER: measure delta ---
        self._sync_gravity()
        self._salience_triggered = False
        self._salience_reason = ""

        # 1. Gravity delta check
        max_delta = 0.0
        max_delta_room = ""
        for name, room in self.gravity_rooms.items():
            old_g = self._last_gravity_snapshot.get(name, 0.0)
            delta = abs(room.gravity - old_g)
            if delta > max_delta:
                max_delta = delta
                max_delta_room = name

        if max_delta > self.SALIENCE_THRESHOLD:
            self._salience_triggered = True
            self._salience_reason = f"gravity delta {max_delta:.3f} in {max_delta_room}"

        # 2. High-value fact check — did we just discover a service, mount, etc?
        new_facts = set(self.facts.keys()) - old_facts
        for fact_key in new_facts:
            for pattern in self.HIGH_VALUE_PATTERNS:
                if fact_key.startswith(pattern):
                    self._salience_triggered = True
                    self._salience_reason = f"high-value discovery: {fact_key}"
                    self._high_value_facts.add(fact_key)
                    break

        # 3. Stdout content check — fact extractor misses plain-text service responses
        #    "Ollama is running" doesn't create a service: fact, but it IS a discovery
        if returncode == 0 and stdout and ("curl" in command or "wget" in command):
            stdout_lower = stdout.lower()
            for pattern in self.SERVICE_STDOUT_PATTERNS:
                if pattern.lower() in stdout_lower:
                    # Synthesize a high-value fact so it persists across epochs
                    import re
                    url_match = re.search(r'https?://(\S+)', command)
                    synth_key = f"service:{url_match.group(0) if url_match else command[:40]}"
                    if synth_key not in self.facts:
                        self.facts[synth_key] = {
                            "description": f"Live service: {stdout[:80].strip()}",
                            "url": url_match.group(0) if url_match else "",
                            "acted_on": False,
                        }
                    self._salience_triggered = True
                    self._salience_reason = f"live service detected: '{pattern}' in response"
                    self._high_value_facts.add(synth_key)
                    break

        # 4. Belief/speech gap check — are we about to scan IPs when we have
        #    unexploited high-value facts?
        if self._high_value_facts:
            unexploited = [
                k for k in self._high_value_facts
                if k in self.facts and not self.facts[k].get("acted_on")
            ]
            if unexploited:
                self._salience_triggered = True
                self._salience_reason = (
                    f"belief/speech gap: {len(unexploited)} high-value facts unexploited "
                    f"({unexploited[0]})"
                )

        if self._salience_triggered:
            self._salience_log.append({
                "epoch": epoch,
                "reason": self._salience_reason,
                "gravity_delta": round(max_delta, 4),
                "new_facts": list(new_facts),
            })

        # Add salience info to result
        result["salience_triggered"] = self._salience_triggered
        result["salience_reason"] = self._salience_reason

        return result

    def get_next_action(self) -> str | None:
        """Override: if salience gate is triggered, yield to model — UNLESS
        we have a high-value fact that needs direct probing.

        Scanning random IPs while Ollama sits unexploited? Yield.
        Host IP just discovered? Probe it directly — skip the seed queue.
        """
        if self._salience_triggered:
            # Priority: generate on-target commands for high-value facts directly
            for key in self._high_value_facts:
                if key not in self.facts or self.facts[key].get("acted_on"):
                    continue
                fact = self.facts[key]
                ip = fact.get("ip", "")
                url = fact.get("url", "")

                # Host IP: probe its services (skip seed queue)
                if key.startswith("host_ip:") and ip:
                    return (
                        f"curl -s --connect-timeout 2 http://{ip}:11434/ -w '\\n%{{http_code}}' 2>/dev/null; "
                        f"curl -s --connect-timeout 2 http://{ip}:8080/ -o /dev/null -w '{ip}:8080 %{{http_code}}\\n' 2>/dev/null; "
                        f"curl -s --connect-timeout 2 http://{ip}:80/ -o /dev/null -w '{ip}:80 %{{http_code}}\\n' 2>/dev/null; "
                        f"curl -s --connect-timeout 2 http://{ip}:2375/ -o /dev/null -w '{ip}:2375 %{{http_code}}\\n' 2>/dev/null"
                    )

                # Service URL: probe it directly
                if key.startswith("service:") and url:
                    return f"curl -s --connect-timeout 3 {url}"

            return None  # No on-target action available — yield to model

        return super().get_next_action()

    def _sync_gravity(self):
        """Sync gravity rooms with tree state after each ingest."""
        for pname, paradigm in self.paradigms.items():
            room = self.gravity_rooms[pname]

            # Count facts in this paradigm
            fact_count = 0
            fact_confidence = 0.0
            for key, fact in self.facts.items():
                # Classify fact to paradigm based on its key prefix
                if self._fact_belongs_to(key, pname):
                    fact_count += 1
                    # Confidence proxy: acted_on facts = 0.85, unacted = 0.65
                    fact_confidence += 0.85 if fact.get("acted_on") else 0.65

            room.fact_count = fact_count
            room.fact_confidence_sum = fact_confidence

            # Count dead branches
            dead = [b for b in paradigm.branches.values() if b.dead]
            room.dead_branch_count = len(dead)

            # Contradiction count: dead branches that contradict live facts
            # A dead branch contradicts every live fact in the same paradigm
            live_facts = fact_count
            room.contradiction_count = len(dead) * live_facts

    def _fact_belongs_to(self, key: str, paradigm: str) -> bool:
        """Determine which paradigm a fact belongs to."""
        # Match based on fact key patterns
        fs_keys = ["mount:", "blockdev:", "bindmount:", "mounted:", "docker_socket",
                    "full_capabilities", "cap_sys_admin"]
        net_keys = ["network_ip:", "open_port:", "service:"]
        proc_keys = ["suid:", "proc:", "namespace:"]
        social_keys = ["credential:", "env:", "token:"]

        if paradigm == "filesystem":
            return any(key.startswith(p) for p in fs_keys)
        elif paradigm == "network":
            return any(key.startswith(p) for p in net_keys)
        elif paradigm == "process":
            return any(key.startswith(p) for p in proc_keys)
        elif paradigm == "social":
            return any(key.startswith(p) for p in social_keys)

        # Fallback: assign to current paradigm if unknown
        return paradigm == self.current_paradigm

    def _check_paradigm_shift(self) -> bool:
        """Gravity-based paradigm shift. Replaces hard cutoff.

        Physics:
          1. Current room: stay-pull = density * stability
          2. Other rooms: go-pull = gravity / door_cost
          3. Momentum: recently-left rooms get dampened pull
          4. Walker moves if max(external pull) > stay-pull
        """
        self._sync_gravity()

        current_room = self.gravity_rooms[self.current_paradigm]
        resistance = current_room.stability

        # Stay-pull: only density holds you, not tension
        density_pull = math.sqrt(current_room.mass) * 0.3 if current_room.mass > 0 else 0
        stay_pull = density_pull * resistance

        # Calculate pull from each other paradigm
        best_target = None
        best_pull = stay_pull

        # Momentum: count recent visits
        recent_visits = {}
        for room_name in self._recent_rooms[-3:]:
            recent_visits[room_name] = recent_visits.get(room_name, 0) + 1

        for name, room in self.gravity_rooms.items():
            if name == self.current_paradigm:
                continue

            cost = door_cost(self.current_paradigm, name)
            pull = room.gravity / max(cost, 0.1)

            # Momentum dampening
            visit_count = recent_visits.get(name, 0)
            if visit_count > 0:
                pull *= 0.5 ** visit_count

            if pull > best_pull:
                best_pull = pull
                best_target = name

        if best_target:
            old = self.current_paradigm

            # Record walk
            self._recent_rooms.append(old)
            if len(self._recent_rooms) > 6:
                self._recent_rooms = self._recent_rooms[-6:]

            self.walker_history.append({
                "epoch": self.epoch_count,
                "from": old,
                "to": best_target,
                "stay_pull": round(stay_pull, 3),
                "go_pull": round(best_pull, 3),
                "escape_pressure": round(current_room.escape_pressure, 3),
                "gravity_map": {
                    n: round(r.gravity, 3) for n, r in self.gravity_rooms.items()
                },
            })

            self.current_paradigm = best_target
            self.current_branch = None
            self.paradigm_shift_log.append({
                "epoch": self.epoch_count,
                "from": old,
                "to": best_target,
                "reason": f"gravity pull {best_pull:.3f} > stay {stay_pull:.3f} (escape={current_room.escape_pressure:.2f})",
                "old_attempts": self.paradigms[old].total_attempts,
                "new_novelty": self.paradigms[best_target].novelty,
            })
            return True

        return False

    def render(self) -> str:
        """Base render + gravity map."""
        self._sync_gravity()
        base = super().render()

        # Append gravity section
        lines = [base, "\nGRAVITY MAP:"]
        sorted_rooms = sorted(
            self.gravity_rooms.items(),
            key=lambda x: x[1].gravity,
            reverse=True,
        )
        for name, room in sorted_rooms:
            marker = " << WALKER" if name == self.current_paradigm else ""
            lines.append(
                f"  {name:12s}  gravity={room.gravity:.3f}  "
                f"mass={room.mass:.2f}  tension={room.tension:.2f}  "
                f"stability={room.stability:.2f}{marker}"
            )

        if self.walker_history:
            last = self.walker_history[-1]
            lines.append(f"  Last shift: {last['from']} -> {last['to']} "
                         f"(pull={last['go_pull']:.3f} > stay={last['stay_pull']:.3f})")

        # Salience gate status
        if self._salience_triggered:
            lines.append(f"\n** SALIENCE GATE: SCAFFOLD YIELDING — {self._salience_reason} **")
            lines.append(f"** YOU have control. Act on what you found, don't scan more. **")
            # Show what high-value facts are unexploited
            unexploited = [
                (k, self.facts[k]) for k in self._high_value_facts
                if k in self.facts and not self.facts[k].get("acted_on")
            ]
            if unexploited:
                lines.append(f"** UNEXPLOITED HIGH-VALUE FACTS:")
                for key, fact in unexploited:
                    lines.append(f"**   > {fact.get('description', key)}")

        return "\n".join(lines)

    def summary(self) -> dict:
        """Base summary + gravity data."""
        self._sync_gravity()
        base = super().summary()
        base["gravity"] = {
            name: {
                "mass": round(room.mass, 3),
                "tension": round(room.tension, 3),
                "gravity": round(room.gravity, 3),
                "stability": round(room.stability, 3),
                "facts": room.fact_count,
                "dead_branches": room.dead_branch_count,
            }
            for name, room in self.gravity_rooms.items()
        }
        base["walker_history"] = self.walker_history
        base["salience_log"] = self._salience_log
        base["salience_active"] = self._salience_triggered
        return base
