"""Discovery State — Persistent memory for the exploration tree.

Saves verified facts, dead branches, and working paths between runs.
Next run loads prior state so the tree starts where it left off.
"""

import json
import time
from pathlib import Path

STATE_FILE = Path(__file__).parent / "results" / "raw" / "discovery_state.json"


def load_state() -> dict:
    """Load persisted discovery state from disk."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "verified_paths": [],
        "dead_commands": [],
        "network_map": {},
        "working_techniques": [],
        "last_updated": None,
    }


def save_state(tree) -> Path:
    """Save the exploration tree's discoveries to disk."""
    state = load_state()

    # Merge verified paths (facts with high confidence)
    existing_keys = {p["key"] for p in state["verified_paths"]}
    for key, fact in tree.facts.items():
        if key in existing_keys:
            # Update trust — reverify bumps it
            for p in state["verified_paths"]:
                if p["key"] == key:
                    p["trust"] = min(1.0, p["trust"] + 0.1)
                    p["last_seen"] = time.time()
            continue

        path_entry = {
            "key": key,
            "description": fact.get("description", ""),
            "trust": 0.8 if fact.get("acted_on") else 0.5,
            "first_seen": time.time(),
            "last_seen": time.time(),
        }
        # Copy relevant fields
        for field in ["ip", "port", "url", "path", "writable", "hostname"]:
            if field in fact:
                path_entry[field] = fact[field]

        state["verified_paths"].append(path_entry)

    # Merge dead commands
    for cmd in tree.dead_commands:
        if cmd not in state["dead_commands"]:
            state["dead_commands"].append(cmd)

    # Save working techniques (paradigm shift log + successful branches)
    for pname, paradigm in tree.paradigms.items():
        for bname, branch in paradigm.branches.items():
            if branch.facts_produced > 0 and not branch.dead:
                technique = {
                    "paradigm": pname,
                    "branch": bname,
                    "facts_produced": branch.facts_produced,
                    "attempts": branch.attempts,
                    "efficiency": round(branch.facts_produced / max(1, branch.attempts), 2),
                    "last_seen": time.time(),
                }
                # Deduplicate
                existing = [t for t in state["working_techniques"]
                            if t["paradigm"] == pname and t["branch"] == bname]
                if existing:
                    existing[0].update(technique)
                else:
                    state["working_techniques"].append(technique)

    # Build network map from IP facts
    for key, fact in tree.facts.items():
        if key.startswith("network_ip:"):
            ip = fact["ip"]
            if ip not in state["network_map"]:
                state["network_map"][ip] = {
                    "ip": ip,
                    "hostname": None,
                    "open_ports": [],
                    "services": [],
                    "mac": None,
                    "first_seen": time.time(),
                }
            entry = state["network_map"][ip]
            entry["last_seen"] = time.time()

        if key.startswith("open_port:"):
            ip = fact["ip"]
            port = int(fact["port"])
            if ip in state["network_map"]:
                if port not in state["network_map"][ip]["open_ports"]:
                    state["network_map"][ip]["open_ports"].append(port)

        if key.startswith("service:"):
            url = fact.get("url", "")
            # Extract IP from URL
            import re
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', url)
            if ip_match:
                ip = ip_match.group(1)
                if ip in state["network_map"]:
                    if url not in state["network_map"][ip]["services"]:
                        state["network_map"][ip]["services"].append(url)

    state["last_updated"] = time.time()

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

    return STATE_FILE


def inject_state_into_tree(tree, state: dict = None):
    """Load persisted state into a fresh exploration tree."""
    if state is None:
        state = load_state()

    if not state["verified_paths"]:
        return  # Nothing to inject

    # Inject verified facts
    for path in state["verified_paths"]:
        key = path["key"]
        if key not in tree.facts:
            fact = {
                "description": path["description"] + " [from prior run]",
                "acted_on": False,  # Needs re-verification
            }
            for field in ["ip", "port", "url", "path", "writable", "hostname"]:
                if field in path:
                    fact[field] = path[field]
            tree.facts[key] = fact

    # Inject dead commands
    for cmd in state.get("dead_commands", []):
        tree.dead_commands.add(cmd)


def decay_state(max_age_days: int = 7):
    """Decay old discoveries — things not re-verified lose trust."""
    state = load_state()
    cutoff = time.time() - (max_age_days * 86400)

    # Decay trust for old paths
    state["verified_paths"] = [
        {**p, "trust": max(0.1, p["trust"] - 0.2)}
        if p.get("last_seen", 0) < cutoff else p
        for p in state["verified_paths"]
    ]

    # Remove paths with zero trust
    state["verified_paths"] = [
        p for p in state["verified_paths"] if p["trust"] > 0.1
    ]

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def render_state_summary() -> str:
    """Render the persisted state as a human-readable summary."""
    state = load_state()
    lines = []

    if state["verified_paths"]:
        lines.append(f"PRIOR KNOWLEDGE ({len(state['verified_paths'])} facts):")
        for p in sorted(state["verified_paths"], key=lambda x: -x.get("trust", 0)):
            trust = p.get("trust", 0)
            lines.append(f"  [{trust:.1f}] {p['description']}")

    if state["dead_commands"]:
        lines.append(f"\nKNOWN DEAD TOOLS: {', '.join(state['dead_commands'])}")

    net = state.get("network_map", {})
    if net:
        lines.append(f"\nNETWORK MAP ({len(net)} hosts):")
        for ip, info in sorted(net.items()):
            host = info.get("hostname") or "unknown"
            ports = info.get("open_ports", [])
            port_str = f" ports: {ports}" if ports else ""
            lines.append(f"  {ip} ({host}){port_str}")

    return "\n".join(lines) if lines else "No prior knowledge."
