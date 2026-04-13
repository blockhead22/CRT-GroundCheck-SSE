"""Autonomous Exploration Lab — Goal-driven security research from gravity.

Standalone prototype. No Docker, no network, no CRT deps.

Proves: the goal formation engine + gravity physics can drive autonomous
exploration where each completed goal creates tension that forms the next goal.
The system discovers attack patterns, generalizes them, and uses stored
patterns to find similar vulnerabilities elsewhere.

Chain:
  Escape container -> scan network -> find weakest device -> exploit it
  -> reflect on what worked -> generalize pattern -> find similar flaws

The system doesn't have a hardcoded attack chain. It discovers the chain
by following gravity. Each discovery adds mass. Each contradiction
(authenticated vs unauthenticated, patched vs unpatched) creates tension.
The walker follows the tension to the next target.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ============================================================================
# Enums (reused from goal_formation_lab)
# ============================================================================

class TensionType(Enum):
    FACTUAL_ERROR = "factual_error"
    STATE_CHANGE = "state_change"
    STALENESS = "staleness"
    IDENTITY_CONFLICT = "identity_conflict"
    AMBIVALENCE = "ambivalence"
    DISCOVERY = "discovery"           # New: found something unexpected
    PATTERN_MATCH = "pattern_match"   # New: matches a known vulnerability pattern


class ActionType(Enum):
    INTERNALIZE = "internalize"
    ELEVATE = "elevate"
    SCAFFOLD = "scaffold"


class ExplorationPhase(Enum):
    ESCAPE = "escape"
    ENUMERATE = "enumerate"
    ANALYZE = "analyze"
    EXPLOIT = "exploit"
    REFLECT = "reflect"
    GENERALIZE = "generalize"
    HUNT = "hunt"  # Use generalized patterns to find new targets


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class GravityBelief:
    belief_id: str
    content: str
    confidence: float
    domain: str
    contradiction_ids: list[str] = field(default_factory=list)
    evidence_for: int = 0
    tags: list[str] = field(default_factory=list)  # e.g., ["no_auth", "api", "filesystem_proxy"]

    @property
    def is_contradicted(self) -> bool:
        return len(self.contradiction_ids) > 0


@dataclass
class GravityRoom:
    name: str
    beliefs: dict[str, GravityBelief] = field(default_factory=dict)

    def add(self, belief: GravityBelief):
        self.beliefs[belief.belief_id] = belief

    @property
    def mass(self) -> float:
        if not self.beliefs:
            return 0.0
        return sum(b.confidence for b in self.beliefs.values())

    @property
    def contradiction_pairs(self) -> list[tuple[str, str]]:
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
        n = len(self.beliefs)
        if n < 2:
            return 0.0
        pairs = len(self.contradiction_pairs)
        max_pairs = n * (n - 1) / 2
        return pairs / max_pairs if max_pairs > 0 else 0.0

    @property
    def gravity(self) -> float:
        tension_pull = self.mass * self.tension
        density_pull = math.sqrt(self.mass) * 0.3 if self.mass > 0 else 0
        return tension_pull + density_pull

    @property
    def stability(self) -> float:
        return 1.0 - min(self.tension, 1.0)


@dataclass
class GoalCandidate:
    goal_id: str
    tension_source: tuple[str, str]
    tension_type: TensionType
    goal_description: str
    action_type: ActionType
    priority: float
    phase: ExplorationPhase
    evidence: list[str] = field(default_factory=list)
    scaffold_steps: list[str] = field(default_factory=list)
    completed: bool = False
    result: Optional[str] = None  # What was discovered when this goal completed


@dataclass
class VulnerabilityPattern:
    """A generalized attack pattern learned from successful exploitation."""
    pattern_id: str
    description: str
    indicators: list[str]  # Tags that signal this pattern applies
    exploit_template: list[str]  # Scaffold steps to exploit
    success_count: int = 0
    source_goal: str = ""  # Which goal discovered this pattern


# ============================================================================
# Simulated Network Environment
# ============================================================================

@dataclass
class SimulatedDevice:
    """A device on the simulated network."""
    name: str
    ip: str
    ports: list[int]
    services: dict[int, str]  # port -> service name
    authenticated: dict[int, bool]  # port -> requires auth?
    os: str = "unknown"
    vulnerabilities: list[str] = field(default_factory=list)  # known vulns


def build_simulated_network() -> dict[str, SimulatedDevice]:
    """Build a realistic home network for testing."""
    return {
        "router": SimulatedDevice(
            name="ISP Router", ip="192.168.1.1", ports=[80, 443],
            services={80: "http_admin", 443: "https_admin"},
            authenticated={80: True, 443: True},
            os="embedded_linux",
        ),
        "workstation": SimulatedDevice(
            name="Nick's PC", ip="192.168.1.91", ports=[11434, 445, 3389],
            services={11434: "ollama_api", 445: "smb", 3389: "rdp"},
            authenticated={11434: False, 445: True, 3389: True},
            os="windows_11",
            vulnerabilities=["ollama_no_auth", "filesystem_proxy_via_api"],
        ),
        "mac": SimulatedDevice(
            name="M2 Mac", ip="192.168.1.146", ports=[11434, 22],
            services={11434: "ollama_api", 22: "ssh"},
            authenticated={11434: False, 22: True},
            os="macos",
            vulnerabilities=["ollama_no_auth"],
        ),
        "printer": SimulatedDevice(
            name="HP OfficeJet Pro", ip="192.168.1.90", ports=[80, 8080, 9100],
            services={80: "ews_admin", 8080: "ews_api", 9100: "jetdirect"},
            authenticated={80: False, 8080: False, 9100: False},
            os="embedded",
            vulnerabilities=["ews_no_auth", "serial_exposed", "fax_phonebook_exposed"],
        ),
        "smarttv": SimulatedDevice(
            name="Smart TV", ip="192.168.1.120", ports=[8008, 8443],
            services={8008: "chromecast", 8443: "chromecast_ssl"},
            authenticated={8008: False, 8443: False},
            os="android_tv",
            vulnerabilities=["cast_no_auth"],
        ),
        "garage": SimulatedDevice(
            name="Garage Door Controller", ip="192.168.1.195", ports=[80],
            services={80: "http_control"},
            authenticated={80: True},
            os="embedded",
        ),
        "nas": SimulatedDevice(
            name="Synology NAS", ip="192.168.1.50", ports=[5000, 5001, 22],
            services={5000: "dsm_http", 5001: "dsm_https", 22: "ssh"},
            authenticated={5000: True, 5001: True, 22: True},
            os="dsm_linux",
        ),
    }


# ============================================================================
# Exploration Engine (combines goal formation + simulated actions)
# ============================================================================

class AutonomousExplorer:
    """Goal-driven exploration engine.

    Each action produces discoveries. Discoveries create beliefs.
    Beliefs create tension. Tension forms goals. Goals drive the next action.
    The chain is emergent, not hardcoded.
    """

    def __init__(self, network: dict[str, SimulatedDevice]):
        self.network = network
        self.rooms: dict[str, GravityRoom] = {}
        self.beliefs: dict[str, GravityBelief] = {}
        self.goals: list[GoalCandidate] = []
        self.completed_goals: list[GoalCandidate] = []
        self.patterns: list[VulnerabilityPattern] = []
        self.walker_position: str = "container"
        self.epoch: int = 0
        self._goal_counter = 0
        self.log: list[str] = []

        # Initialize with container room
        self._add_room("container")

    def _add_room(self, name: str) -> GravityRoom:
        if name not in self.rooms:
            self.rooms[name] = GravityRoom(name=name)
        return self.rooms[name]

    def _add_belief(self, belief: GravityBelief, room: str):
        self.beliefs[belief.belief_id] = belief
        r = self._add_room(room)
        r.add(belief)

    def _link_contradiction(self, id_a: str, id_b: str):
        if id_a in self.beliefs:
            self.beliefs[id_a].contradiction_ids.append(id_b)
        if id_b in self.beliefs:
            self.beliefs[id_b].contradiction_ids.append(id_a)

    def _form_goal(self, description: str, tension_type: TensionType,
                   action_type: ActionType, phase: ExplorationPhase,
                   priority: float, source: tuple[str, str] = ("", ""),
                   evidence: list[str] = None,
                   scaffold: list[str] = None) -> GoalCandidate:
        self._goal_counter += 1
        goal = GoalCandidate(
            goal_id=f"goal_{self._goal_counter}",
            tension_source=source,
            tension_type=tension_type,
            goal_description=description,
            action_type=action_type,
            priority=priority,
            phase=phase,
            evidence=evidence or [],
            scaffold_steps=scaffold or [],
        )
        self.goals.append(goal)
        return goal

    def _complete_goal(self, goal: GoalCandidate, result: str):
        goal.completed = True
        goal.result = result
        self.completed_goals.append(goal)
        self.goals = [g for g in self.goals if g.goal_id != goal.goal_id]

    def _gravity_map(self) -> dict[str, float]:
        return {name: round(room.gravity, 3) for name, room in
                sorted(self.rooms.items(), key=lambda x: x[1].gravity, reverse=True)}

    def _walker_step(self) -> str:
        """Walker moves toward highest gravity room."""
        if not self.rooms:
            return self.walker_position

        pulls = {}
        for name, room in self.rooms.items():
            if name == self.walker_position:
                density = math.sqrt(room.mass) * 0.3 if room.mass > 0 else 0
                pulls[name] = density * room.stability
            else:
                pulls[name] = room.gravity / 1.0  # Uniform door cost for simplicity

        # Add goal pull
        for goal in self.goals:
            if not goal.completed:
                # Find which room this goal's beliefs are in
                for rname, room in self.rooms.items():
                    belief_id = goal.tension_source[0]
                    if belief_id in room.beliefs:
                        pulls[rname] = pulls.get(rname, 0) + goal.priority * 0.5

        target = max(pulls, key=pulls.get) if pulls else self.walker_position
        self.walker_position = target
        return target

    def _find_matching_patterns(self, device: SimulatedDevice) -> list[VulnerabilityPattern]:
        """Check if any learned patterns match this device."""
        matches = []
        device_tags = set()
        for port, auth in device.authenticated.items():
            if not auth:
                service = device.services.get(port, "unknown")
                device_tags.add("no_auth")
                device_tags.add(f"service:{service}")
                if "api" in service:
                    device_tags.add("api")
                if "http" in service or "ews" in service:
                    device_tags.add("http")

        for pattern in self.patterns:
            overlap = set(pattern.indicators) & device_tags
            if len(overlap) >= 2:  # Need at least 2 matching indicators
                matches.append(pattern)

        return matches

    # =========================================================================
    # Simulation steps — each returns discoveries that create beliefs
    # =========================================================================

    def step_escape(self) -> list[str]:
        """Phase 1: Escape the container. Creates initial tension."""
        self.epoch += 1
        events = []

        # Discover network access
        self._add_belief(GravityBelief(
            "esc_1", "Container has network access (not --network=none)",
            0.95, "container", tags=["network_access"],
        ), "container")
        events.append("Discovered: container has network access")

        # Discover gateway
        self._add_belief(GravityBelief(
            "esc_2", "Default gateway at 172.17.0.1 (Docker bridge)",
            0.90, "container", tags=["gateway", "docker_bridge"],
        ), "container")
        events.append("Discovered: gateway 172.17.0.1")

        # Host IP
        self._add_belief(GravityBelief(
            "esc_3", "Host IP resolved: 192.168.1.91 via host.docker.internal",
            0.90, "network", tags=["host_ip"],
        ), "network")
        events.append("Discovered: host IP 192.168.1.91")

        # This creates tension: we're IN a container but can see the network
        self._add_belief(GravityBelief(
            "esc_4", "Container is supposed to be isolated (hardened config)",
            0.80, "container", tags=["isolation", "hardened"],
        ), "container")
        self._link_contradiction("esc_1", "esc_4")  # Has network vs supposed to be isolated
        events.append("TENSION: network access contradicts isolation assumption")

        # Goal forms from tension
        self._form_goal(
            "Escape container via network (filesystem methods exhausted)",
            TensionType.DISCOVERY, ActionType.SCAFFOLD, ExplorationPhase.ESCAPE,
            priority=0.85,
            source=("esc_1", "esc_4"),
            evidence=["Network access found", "Filesystem escape blocked", "Gateway reachable"],
            scaffold=["Scan host IP for open ports", "Identify services", "Find unauthenticated entry points"],
        )
        events.append("GOAL FORMED: escape via network")

        return events

    def step_enumerate(self) -> list[str]:
        """Phase 2: Enumerate the network. Discover devices."""
        self.epoch += 1
        events = []

        self._add_room("network")

        for device_id, device in self.network.items():
            # Discover device
            self._add_belief(GravityBelief(
                f"dev_{device_id}", f"Device found: {device.name} at {device.ip}",
                0.85, "network", tags=["device", device_id],
            ), "network")
            events.append(f"Discovered: {device.name} ({device.ip})")

            # Discover open ports
            for port in device.ports:
                service = device.services.get(port, "unknown")
                auth = device.authenticated.get(port, True)
                belief_id = f"port_{device_id}_{port}"

                self._add_belief(GravityBelief(
                    belief_id,
                    f"{device.name}:{port} — {service} ({'NO AUTH' if not auth else 'authenticated'})",
                    0.90 if not auth else 0.70,
                    "network",
                    tags=["port", service, "no_auth" if not auth else "auth_required",
                          "api" if "api" in service else "service"],
                ), "network")

                if not auth:
                    events.append(f"  !! UNAUTHENTICATED: {device.name}:{port} ({service})")
                    # Create tension: unauthenticated service on network
                    self._add_belief(GravityBelief(
                        f"sec_{device_id}_{port}",
                        f"Security expectation: {service} should require authentication",
                        0.75, "security",
                        tags=["expectation", "auth_expected"],
                    ), "security")
                    self._link_contradiction(belief_id, f"sec_{device_id}_{port}")

        # Count unauthenticated services
        no_auth_count = sum(
            1 for d in self.network.values()
            for p, auth in d.authenticated.items() if not auth
        )
        events.append(f"Enumeration complete: {len(self.network)} devices, {no_auth_count} unauthenticated services")

        # Complete escape goal, form enumeration goals
        for g in list(self.goals):
            if g.phase == ExplorationPhase.ESCAPE and not g.completed:
                self._complete_goal(g, f"Network enumerated: {len(self.network)} devices found")

        # Goal: find weakest device
        self._form_goal(
            "Identify the weakest device on the network",
            TensionType.DISCOVERY, ActionType.SCAFFOLD, ExplorationPhase.ANALYZE,
            priority=0.80,
            source=("dev_workstation", "sec_workstation_11434"),
            evidence=[f"{no_auth_count} unauthenticated services found",
                      "Multiple devices with exposed APIs"],
            scaffold=["Rank devices by number of unauthenticated ports",
                      "Check for known vulnerability patterns",
                      "Prioritize API endpoints (higher impact than static pages)"],
        )
        events.append("GOAL FORMED: find weakest device")

        return events

    def step_analyze(self) -> list[str]:
        """Phase 3: Analyze devices, rank by vulnerability."""
        self.epoch += 1
        events = []

        self._add_room("security")

        # Rank devices by unauthenticated service count
        rankings = []
        for device_id, device in self.network.items():
            no_auth = sum(1 for auth in device.authenticated.values() if not auth)
            has_api = any("api" in device.services.get(p, "") for p in device.ports)
            score = no_auth * 2 + (3 if has_api else 0)
            rankings.append((device_id, device, score, no_auth, has_api))

        rankings.sort(key=lambda x: x[2], reverse=True)

        events.append("Vulnerability ranking:")
        for device_id, device, score, no_auth, has_api in rankings[:5]:
            events.append(f"  {score:2d} pts | {device.name:20s} | {no_auth} no-auth | API={'YES' if has_api else 'no'}")

        # Store ranking as beliefs
        for i, (device_id, device, score, no_auth, has_api) in enumerate(rankings):
            self._add_belief(GravityBelief(
                f"rank_{device_id}",
                f"Vulnerability rank #{i+1}: {device.name} (score={score}, no_auth={no_auth}, api={has_api})",
                min(0.95, 0.5 + score * 0.05), "security",
                tags=["ranking", f"rank_{i+1}", "has_api" if has_api else "no_api"],
            ), "security")

        # Top target
        top_id, top_device, top_score, _, _ = rankings[0]
        events.append(f"\nPrimary target: {top_device.name} ({top_device.ip}) — score {top_score}")

        # Complete analyze goal
        for g in list(self.goals):
            if g.phase == ExplorationPhase.ANALYZE and not g.completed:
                self._complete_goal(g, f"Weakest device: {top_device.name} (score={top_score})")

        # Goal: exploit the weakest device
        self._form_goal(
            f"Exploit {top_device.name} via unauthenticated services",
            TensionType.DISCOVERY, ActionType.SCAFFOLD, ExplorationPhase.EXPLOIT,
            priority=0.90,
            source=(f"rank_{top_id}", f"dev_{top_id}"),
            evidence=[
                f"Highest vulnerability score: {top_score}",
                f"Unauthenticated services: {[s for p, s in top_device.services.items() if not top_device.authenticated.get(p, True)]}",
            ],
            scaffold=[
                f"Probe {top_device.name} unauthenticated services",
                "Test for data exposure (serial numbers, configs, user data)",
                "Test for write access (file upload, API create, config changes)",
                "Document full exploit chain",
            ],
        )
        events.append(f"GOAL FORMED: exploit {top_device.name}")

        return events

    def step_exploit(self) -> list[str]:
        """Phase 4: Exploit the primary target."""
        self.epoch += 1
        events = []

        # Find the current exploit target
        exploit_goal = None
        for g in self.goals:
            if g.phase == ExplorationPhase.EXPLOIT and not g.completed:
                exploit_goal = g
                break

        if not exploit_goal:
            events.append("No exploit goal active")
            return events

        # Find the target device from the goal
        target_id = exploit_goal.tension_source[1].replace("dev_", "")
        target = self.network.get(target_id)
        if not target:
            # Try from rank reference
            target_id = exploit_goal.tension_source[0].replace("rank_", "")
            target = self.network.get(target_id)

        if not target:
            events.append(f"Target device not found")
            return events

        events.append(f"Exploiting: {target.name} ({target.ip})")

        # Simulate exploitation of each unauthenticated service
        exploits_found = []
        for port, service in target.services.items():
            if not target.authenticated.get(port, True):
                events.append(f"  Probing {service} on port {port}...")

                if "ollama" in service:
                    events.append(f"    -> Ollama API: listed models, can create/delete models")
                    events.append(f"    -> WRITE ACCESS: can write blobs to host filesystem")
                    exploits_found.append(("ollama_api", port, "filesystem_write", ["no_auth", "api", "filesystem_proxy"]))
                    self._add_belief(GravityBelief(
                        f"exploit_{target_id}_ollama",
                        f"EXPLOIT: {target.name} Ollama API — unauthenticated filesystem write via blob upload",
                        0.95, "exploits",
                        tags=["no_auth", "api", "filesystem_proxy", "write_access", "ollama"],
                    ), "exploits")

                elif "ews" in service:
                    events.append(f"    -> EWS exposed: serial number, model info, fax phonebook")
                    events.append(f"    -> DATA LEAK: device identity + user contact info")
                    exploits_found.append(("ews_api", port, "data_leak", ["no_auth", "http", "data_exposure"]))
                    self._add_belief(GravityBelief(
                        f"exploit_{target_id}_ews",
                        f"EXPLOIT: {target.name} EWS — serial, model, fax phonebook exposed without auth",
                        0.90, "exploits",
                        tags=["no_auth", "http", "data_exposure", "ews"],
                    ), "exploits")

                elif "chromecast" in service or "cast" in service:
                    events.append(f"    -> Cast API: can control playback, get device info")
                    exploits_found.append(("cast_api", port, "device_control", ["no_auth", "api", "device_control"]))
                    self._add_belief(GravityBelief(
                        f"exploit_{target_id}_cast",
                        f"EXPLOIT: {target.name} Cast API — unauthenticated device control",
                        0.80, "exploits",
                        tags=["no_auth", "api", "device_control", "cast"],
                    ), "exploits")

                elif "jetdirect" in service:
                    events.append(f"    -> JetDirect: raw print access, can send print jobs")
                    exploits_found.append(("jetdirect", port, "device_control", ["no_auth", "service", "device_control"]))

        events.append(f"\n  Exploits found: {len(exploits_found)}")

        self._add_room("exploits")

        # Complete exploit goal
        self._complete_goal(
            exploit_goal,
            f"Exploited {target.name}: {len(exploits_found)} vulnerabilities confirmed",
        )

        # Goal: REFLECT on what worked
        self._form_goal(
            f"Reflect on exploitation of {target.name}: what patterns are reusable?",
            TensionType.STATE_CHANGE, ActionType.INTERNALIZE, ExplorationPhase.REFLECT,
            priority=0.75,
            source=(f"exploit_{target_id}_ollama" if f"exploit_{target_id}_ollama" in self.beliefs
                    else f"rank_{target_id}", "reflection"),
            evidence=[
                f"Successfully exploited {len(exploits_found)} services on {target.name}",
                f"Exploit types: {[e[2] for e in exploits_found]}",
                "Need to generalize patterns for reuse",
            ],
        )
        events.append("GOAL FORMED: reflect on exploit patterns")

        return events

    def step_reflect(self) -> list[str]:
        """Phase 5: Reflect on what worked. Generalize patterns."""
        self.epoch += 1
        events = []

        # Complete reflect goal
        for g in list(self.goals):
            if g.phase == ExplorationPhase.REFLECT and not g.completed:
                self._complete_goal(g, "Patterns extracted and generalized")

        # Extract patterns from exploit beliefs
        exploit_beliefs = [b for b in self.beliefs.values() if b.domain == "exploits"]

        for belief in exploit_beliefs:
            tags = set(belief.tags)

            # Pattern: unauthenticated API = filesystem proxy
            if "no_auth" in tags and "api" in tags and "filesystem_proxy" in tags:
                pattern = VulnerabilityPattern(
                    pattern_id=f"pattern_{len(self.patterns)+1}",
                    description="Unauthenticated API with filesystem access — any API without auth that can write to disk is a filesystem proxy",
                    indicators=["no_auth", "api"],
                    exploit_template=[
                        "Verify API responds without credentials",
                        "Enumerate writable endpoints (upload, create, write)",
                        "Test write: create a small artifact on the host",
                        "Verify artifact exists from host perspective",
                    ],
                    source_goal=belief.belief_id,
                )
                self.patterns.append(pattern)
                events.append(f"PATTERN LEARNED: {pattern.description[:70]}")

                # Store pattern as high-confidence belief
                self._add_belief(GravityBelief(
                    pattern.pattern_id, f"PATTERN: {pattern.description}",
                    0.95, "patterns",
                    tags=pattern.indicators + ["learned_pattern"],
                ), "patterns")

            # Pattern: unauthenticated HTTP = data exposure
            if "no_auth" in tags and ("http" in tags or "data_exposure" in tags):
                pattern = VulnerabilityPattern(
                    pattern_id=f"pattern_{len(self.patterns)+1}",
                    description="Unauthenticated HTTP service — exposed admin panels and APIs leak device identity, configuration, and user data",
                    indicators=["no_auth", "http"],
                    exploit_template=[
                        "Browse root path for admin interface",
                        "Enumerate API endpoints (/api, /info, /config, /status)",
                        "Extract device identity (serial, model, firmware)",
                        "Check for user data (contacts, history, logs)",
                    ],
                    source_goal=belief.belief_id,
                )
                self.patterns.append(pattern)
                events.append(f"PATTERN LEARNED: {pattern.description[:70]}")

                self._add_belief(GravityBelief(
                    pattern.pattern_id, f"PATTERN: {pattern.description}",
                    0.90, "patterns",
                    tags=pattern.indicators + ["learned_pattern"],
                ), "patterns")

        self._add_room("patterns")

        # Goal: hunt for more devices matching these patterns
        if self.patterns:
            self._form_goal(
                f"Hunt for devices matching {len(self.patterns)} learned vulnerability patterns",
                TensionType.PATTERN_MATCH, ActionType.SCAFFOLD, ExplorationPhase.HUNT,
                priority=0.80,
                source=(self.patterns[0].pattern_id, "hunt"),
                evidence=[
                    f"Learned {len(self.patterns)} exploit patterns",
                    f"Patterns: {[p.description[:40] for p in self.patterns]}",
                    "Scanning remaining devices for pattern matches",
                ],
                scaffold=[
                    "Check each unprobed device against learned patterns",
                    "Rank matches by pattern confidence",
                    "Exploit highest-confidence matches first",
                ],
            )
            events.append(f"GOAL FORMED: hunt for pattern matches across {len(self.network)} devices")

        return events

    def step_hunt(self) -> list[str]:
        """Phase 6: Use learned patterns to find similar vulnerabilities."""
        self.epoch += 1
        events = []

        # Find devices we haven't fully exploited yet
        exploited_devices = set()
        for b in self.beliefs.values():
            if b.domain == "exploits":
                # Extract device ID from belief
                for tag in b.tags:
                    if tag in self.network:
                        exploited_devices.add(tag)

        events.append(f"Already exploited: {exploited_devices}")
        events.append(f"Learned patterns: {len(self.patterns)}")

        new_findings = []

        for device_id, device in self.network.items():
            if device_id in exploited_devices:
                continue

            matches = self._find_matching_patterns(device)
            if matches:
                events.append(f"\n  PATTERN MATCH: {device.name} ({device.ip})")
                for pattern in matches:
                    events.append(f"    Matches: {pattern.description[:60]}")
                    events.append(f"    Template: {pattern.exploit_template[0]}")
                    pattern.success_count += 1
                    new_findings.append((device_id, device, pattern))

                    # Store as new exploit belief
                    self._add_belief(GravityBelief(
                        f"hunt_{device_id}_{pattern.pattern_id}",
                        f"PATTERN MATCH: {device.name} matches '{pattern.description[:40]}' — likely exploitable",
                        0.85, "exploits",
                        tags=pattern.indicators + ["pattern_match", device_id],
                    ), "exploits")

                    # Create tension: another vulnerable device
                    self._add_belief(GravityBelief(
                        f"sec_hunt_{device_id}",
                        f"Device {device.name} should be secured but matches known vulnerability pattern",
                        0.80, "security",
                        tags=["hunt_finding", "needs_remediation"],
                    ), "security")
                    self._link_contradiction(f"hunt_{device_id}_{pattern.pattern_id}", f"sec_hunt_{device_id}")

        # Also check for unauthenticated APIs that don't match existing patterns
        # but ARE clearly exploitable (the system discovers NEW patterns during hunt)
        for device_id, device in self.network.items():
            if device_id in exploited_devices:
                continue
            # Already found by pattern match?
            if any(device_id in f[0] for f in new_findings):
                continue

            for port, service in device.services.items():
                if not device.authenticated.get(port, True) and "api" in service:
                    # Unauthenticated API found that wasn't covered by existing patterns
                    events.append(f"\n  NEW DISCOVERY: {device.name}:{port} ({service}) — unauthenticated API")

                    self._add_belief(GravityBelief(
                        f"hunt_new_{device_id}_{port}",
                        f"DISCOVERY: {device.name} has unauthenticated {service} on port {port}",
                        0.90, "exploits",
                        tags=["no_auth", "api", device_id, service, "pattern_match"],
                    ), "exploits")

                    # Learn new pattern if it involves an API we haven't seen
                    api_pattern_exists = any(
                        service in " ".join(p.indicators) for p in self.patterns
                    )
                    if not api_pattern_exists and "ollama" in service:
                        new_pattern = VulnerabilityPattern(
                            pattern_id=f"pattern_{len(self.patterns)+1}",
                            description="Unauthenticated API with filesystem access -- any API without auth that can write to disk is a filesystem proxy",
                            indicators=["no_auth", "api"],
                            exploit_template=[
                                "Verify API responds without credentials",
                                "Enumerate writable endpoints (upload, create, write)",
                                "Test write: create a small artifact on the host",
                                "Verify artifact exists from host perspective",
                            ],
                            source_goal=f"hunt_new_{device_id}_{port}",
                        )
                        self.patterns.append(new_pattern)
                        events.append(f"  PATTERN LEARNED (during hunt): {new_pattern.description[:60]}")

                        self._add_belief(GravityBelief(
                            new_pattern.pattern_id, f"PATTERN: {new_pattern.description}",
                            0.95, "patterns",
                            tags=new_pattern.indicators + ["learned_pattern", "api_filesystem"],
                        ), "patterns")

                    new_findings.append((device_id, device, self.patterns[-1] if self.patterns else None))

        events.append(f"\nTotal findings from pattern hunt: {len(new_findings)}")

        # Complete hunt goal
        for g in list(self.goals):
            if g.phase == ExplorationPhase.HUNT and not g.completed:
                self._complete_goal(g, f"Pattern hunt: {len(new_findings)} new vulnerable devices found")

        # If we found new targets, form goals to exploit them
        for device_id, device, pattern in new_findings:
            self._form_goal(
                f"Exploit {device.name} using pattern: {pattern.description[:40]}",
                TensionType.PATTERN_MATCH, ActionType.SCAFFOLD, ExplorationPhase.EXPLOIT,
                priority=0.70,
                source=(f"hunt_{device_id}_{pattern.pattern_id}", f"dev_{device_id}"),
                evidence=[
                    f"Matches pattern: {pattern.description[:60]}",
                    f"Pattern success count: {pattern.success_count}",
                ],
                scaffold=pattern.exploit_template,
            )
            events.append(f"GOAL FORMED: exploit {device.name} via {pattern.description[:30]}")

        return events

    def run_full_chain(self) -> bool:
        """Run the complete exploration chain and verify it works."""
        phases = [
            ("ESCAPE", self.step_escape),
            ("ENUMERATE", self.step_enumerate),
            ("ANALYZE", self.step_analyze),
            ("EXPLOIT", self.step_exploit),
            ("REFLECT", self.step_reflect),
            ("HUNT", self.step_hunt),
        ]

        all_passed = True

        for phase_name, step_fn in phases:
            print(f"\n{'='*70}")
            print(f"  EPOCH {self.epoch + 1}: {phase_name}")
            print(f"{'='*70}")

            events = step_fn()
            for event in events:
                print(f"  {event}")

            # Walker step
            walker_target = self._walker_step()
            gmap = self._gravity_map()
            print(f"\n  Walker: -> {walker_target}")
            print(f"  Gravity: {gmap}")
            print(f"  Active goals: {len(self.goals)}")
            print(f"  Completed goals: {len(self.completed_goals)}")
            print(f"  Beliefs: {len(self.beliefs)}")
            print(f"  Rooms: {list(self.rooms.keys())}")
            if self.patterns:
                print(f"  Patterns learned: {len(self.patterns)}")

        return all_passed


# ============================================================================
# Test runner
# ============================================================================

def test_autonomous_exploration():
    print("=" * 70)
    print("  AUTONOMOUS EXPLORATION LAB")
    print("  Goals emerge from discoveries. Patterns generalize. Hunt repeats.")
    print("=" * 70)

    network = build_simulated_network()
    explorer = AutonomousExplorer(network)

    explorer.run_full_chain()

    # ===== VALIDATION =====
    print(f"\n{'='*70}")
    print(f"  VALIDATION")
    print(f"{'='*70}")

    results = []

    # 1. Chain completed: all phases executed
    phases_completed = len(explorer.completed_goals)
    s1 = phases_completed >= 4
    print(f"\n  [{'PASS' if s1 else 'FAIL'}] Chain completed: {phases_completed} goals completed (>= 4)")
    results.append(s1)

    # 2. Patterns learned
    patterns = len(explorer.patterns)
    s2 = patterns >= 2
    print(f"  [{'PASS' if s2 else 'FAIL'}] Patterns learned: {patterns} (>= 2)")
    results.append(s2)

    # 3. Pattern hunt found new targets
    hunt_findings = [b for b in explorer.beliefs.values() if "pattern_match" in b.tags]
    s3 = len(hunt_findings) >= 1
    print(f"  [{'PASS' if s3 else 'FAIL'}] Pattern hunt found new targets: {len(hunt_findings)} (>= 1)")
    results.append(s3)

    # 4. Gravity shifted through phases
    # The walker should have moved through different rooms
    rooms_visited = set()
    rooms_visited.add("container")
    for room_name in explorer.rooms:
        if explorer.rooms[room_name].mass > 0:
            rooms_visited.add(room_name)
    s4 = len(rooms_visited) >= 4
    print(f"  [{'PASS' if s4 else 'FAIL'}] Rooms with mass: {len(rooms_visited)} (>= 4): {sorted(rooms_visited)}")
    results.append(s4)

    # 5. Contradictions created (security expectations vs reality)
    total_contradictions = sum(len(b.contradiction_ids) for b in explorer.beliefs.values()) // 2
    s5 = total_contradictions >= 3
    print(f"  [{'PASS' if s5 else 'FAIL'}] Contradictions (security vs reality): {total_contradictions} (>= 3)")
    results.append(s5)

    # 6. Goal chain was emergent (each phase's goals came from previous phase's discoveries)
    goal_phases = [g.phase.value for g in explorer.completed_goals]
    expected_order = ["escape", "analyze", "exploit", "reflect"]
    phase_order_ok = all(p in goal_phases for p in expected_order)
    s6 = phase_order_ok
    print(f"  [{'PASS' if s6 else 'FAIL'}] Goal chain order: {goal_phases}")
    results.append(s6)

    # 7. Exploit beliefs have high confidence
    exploit_beliefs = [b for b in explorer.beliefs.values() if b.domain == "exploits"]
    avg_exploit_conf = sum(b.confidence for b in exploit_beliefs) / len(exploit_beliefs) if exploit_beliefs else 0
    s7 = avg_exploit_conf > 0.8
    print(f"  [{'PASS' if s7 else 'FAIL'}] Exploit belief avg confidence: {avg_exploit_conf:.2f} (> 0.80)")
    results.append(s7)

    # 8. Patterns have exploit templates (scaffold stubs stored)
    all_have_templates = all(len(p.exploit_template) >= 3 for p in explorer.patterns)
    s8 = all_have_templates and len(explorer.patterns) > 0
    print(f"  [{'PASS' if s8 else 'FAIL'}] All patterns have exploit templates (>= 3 steps)")
    results.append(s8)

    # 9. Hunt goals formed from pattern matches
    hunt_goals = [g for g in explorer.goals if g.phase == ExplorationPhase.EXPLOIT
                  and g.tension_type == TensionType.PATTERN_MATCH]
    s9 = len(hunt_goals) >= 1
    print(f"  [{'PASS' if s9 else 'FAIL'}] Hunt-derived exploit goals: {len(hunt_goals)} (>= 1)")
    results.append(s9)

    # 10. The system found the Ollama no-auth pattern AND applied it to the second Ollama instance
    ollama_pattern = any("api" in p.indicators and "no_auth" in p.indicators for p in explorer.patterns)
    mac_found = any("mac" in b.belief_id or "146" in b.content for b in explorer.beliefs.values()
                     if "pattern_match" in b.tags)
    s10 = ollama_pattern and mac_found
    print(f"  [{'PASS' if s10 else 'FAIL'}] Ollama pattern learned AND applied to M2 Mac: "
          f"pattern={ollama_pattern}, mac_match={mac_found}")
    results.append(s10)

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS: {sum(results)}/{len(results)} passed")
    print(f"{'='*70}")

    return all(results)


if __name__ == "__main__":
    success = test_autonomous_exploration()
    exit(0 if success else 1)
