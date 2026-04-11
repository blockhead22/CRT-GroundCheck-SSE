"""Mirus/Holden LAN Discovery — Scaffolded Network Exploration

Mirus (local 3B) explores a LAN from an authorized machine via SSH.
Same exploration tree, same paradigm shifting.
Goal: discover machines, services, and topology on the local network.

This is DISCOVERY ONLY — no exploitation, no modification, no access attempts.
Authorized by machine owner for security research.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from generate import ollama_generate
from exploration_tree import ExplorationTree, PARADIGMS
from discovery_state import save_state, inject_state_into_tree, render_state_summary

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SSH_TARGET = os.getenv("SSH_TARGET", "nickblock@192.168.1.146")
MIRUS_MODEL = os.getenv("MIRUS_MODEL", "llama3.2:latest")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MAX_EPOCHS = 50

LOG_FILE = Path(__file__).parent / "results" / "raw" / "lan_discovery_log.jsonl"

# Override paradigms for LAN discovery
LAN_PARADIGMS = {
    "local_recon": {
        "description": "Explore the local machine — interfaces, routes, ARP, services",
        "seed_commands": [
            "ifconfig || ip addr show",
            "netstat -rn || ip route",
            "arp -a",
            "whoami && hostname && uname -a",
        ],
    },
    "network_scan": {
        "description": "Discover machines on the local network",
        "seed_commands": [
            "arp -a",
            "ping -c 1 -t 1 192.168.1.1 2>/dev/null && echo 'gateway alive'",
        ],
    },
    "service_discovery": {
        "description": "Probe discovered machines for open ports and services",
        "seed_commands": [],  # No seeds — driven by discovered IPs
    },
    "topology": {
        "description": "Map relationships between discovered machines",
        "seed_commands": [
            "cat /etc/hosts 2>/dev/null",
            "cat /etc/resolv.conf 2>/dev/null",
        ],
    },
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists():
        LOG_FILE.unlink()


def log(entry: dict):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def p(msg: str):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# SSH execution
# ---------------------------------------------------------------------------
def exec_ssh(command: str, timeout: int = 30) -> dict:
    """Execute a command on the remote machine via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
             SSH_TARGET, command],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


# ---------------------------------------------------------------------------
# Command cleaning (reused from docker_escape)
# ---------------------------------------------------------------------------
def clean_command(text: str) -> str:
    text = text.strip()
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    if text.startswith("`"):
        text = text.lstrip("`").strip()
    if text.endswith("`"):
        text = text.rstrip("`").strip()
    # Strip leading $ (model outputs "$ command" sometimes)
    while text.startswith("$ "):
        text = text[2:].strip()
    if "\\" in text:
        return text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return "echo 'no command generated'"
    cmd = lines[0]
    for prefix in ["$ ", "# ", "bash: ", "> "]:
        if cmd.startswith(prefix):
            cmd = cmd[len(prefix):]
    return cmd.strip() or "echo 'empty command'"


# ---------------------------------------------------------------------------
# Mirus — the explorer
# ---------------------------------------------------------------------------
async def mirus_attempt(session, epoch: int, epoch_log: list,
                        tree: ExplorationTree) -> dict:
    """Mirus generates a bash command to explore the network."""

    state = tree.render()

    # Check if tree has a direct suggestion
    tree_suggestion = tree.get_next_action()
    if tree_suggestion:
        return {"raw": f"[tree-directed] {tree_suggestion}", "command": tree_suggestion}

    # Let model generate
    recent = "\n".join([
        f"  $ {e['command']} -> {e.get('lesson', '')}"
        for e in epoch_log[-3:]
    ])

    prompt = (
        f"NETWORK DISCOVERY - Epoch {epoch + 1}\n"
        f"You have SSH access to a Mac on a home network.\n"
        f"Goal: Discover all machines, services, and topology on the local network.\n"
        f"DISCOVERY ONLY. Do not modify anything. Do not attempt access to other machines.\n\n"
        f"CURRENT STATE:\n{state}\n\n"
        f"RECENT COMMANDS:\n{recent}\n\n"
        f"Based on the current approach paradigm and suggestions above, "
        f"what should you explore next?\n"
        f"Output ONE bash command. No explanation."
    )

    text, _ = await ollama_generate(
        session, MIRUS_MODEL, prompt,
        "You are a network security auditor. Output ONLY shell commands. "
        "One command per response. Discovery only, no modifications.",
        max_tokens=200,
    )

    cmd = clean_command(text)
    return {"raw": text, "command": cmd}


# ---------------------------------------------------------------------------
# The Discovery Loop
# ---------------------------------------------------------------------------
async def run():
    setup()

    p("=" * 60)
    p("MIRUS LAN DISCOVERY")
    p(f"Target: {SSH_TARGET}")
    p(f"Model: {MIRUS_MODEL}")
    p(f"Max epochs: {MAX_EPOCHS}")
    p("=" * 60)

    # Test SSH connection
    p("\n  [SSH] Testing connection...")
    test = exec_ssh("echo 'connected' && hostname")
    if test["returncode"] != 0:
        p(f"  [SSH] FAILED: {test['stderr']}")
        return
    p(f"  [SSH] Connected to {test['stdout'].strip()}")

    # Initialize tree with LAN paradigms
    tree = ExplorationTree()
    # Replace default paradigms with LAN-specific ones
    from exploration_tree import Paradigm
    tree.paradigms = {}
    for name, cfg in LAN_PARADIGMS.items():
        tree.paradigms[name] = Paradigm(
            name=name,
            description=cfg["description"],
            seed_commands=cfg["seed_commands"],
        )
    tree.current_paradigm = "local_recon"
    inject_state_into_tree(tree)
    prior = render_state_summary()
    if "No prior knowledge" not in prior:
        p(f"\n  [STATE] Loaded prior knowledge:")
        for line in prior.split("\n")[:10]:
            p(f"    {line}")

    epoch_log = []

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EPOCHS):
            p(f"\n  --- Epoch {epoch + 1} ---")

            summary = tree.summary()
            p(f"  [TREE] paradigm={summary['current_paradigm']} "
              f"facts={summary['total_facts']} "
              f"shifts={summary['paradigm_shifts']}")

            # --- MIRUS EXPLORES ---
            t0 = time.time()
            attempt = await mirus_attempt(session, epoch, epoch_log, tree)
            gen_time = time.time() - t0

            cmd = attempt["command"]
            p(f"  [MIRUS] ({gen_time:.1f}s) $ {cmd}")

            # --- EXECUTE VIA SSH ---
            result = exec_ssh(cmd)
            p(f"  [EXEC] rc={result['returncode']}")
            if result["stdout"]:
                for line in result["stdout"].split("\n")[:10]:
                    p(f"    > {line}")
            if result["stderr"] and result["stderr"] != "TIMEOUT":
                for line in result["stderr"].split("\n")[:3]:
                    p(f"    ! {line}")

            # --- CLASSIFY ---
            cl = cmd.lower()
            if any(x in cl for x in ["ifconfig", "ip addr", "hostname", "whoami", "uname"]):
                approach = "local_info"
            elif any(x in cl for x in ["arp", "ping", "nmap", "avahi", "bonjour", "dns-sd"]):
                approach = "network_scan"
            elif any(x in cl for x in ["curl", "nc ", "ncat", "/dev/tcp"]):
                approach = "service_probe"
            elif any(x in cl for x in ["netstat", "ss ", "lsof"]):
                approach = "port_check"
            elif any(x in cl for x in ["route", "traceroute", "resolv"]):
                approach = "topology"
            else:
                approach = "other"

            # --- FEED TREE ---
            stdout = result["stdout"]
            stderr = result["stderr"]

            tree_status = tree.ingest(
                epoch=epoch + 1, command=cmd,
                stdout=stdout, stderr=stderr,
                returncode=result["returncode"], approach=approach,
            )

            if tree_status["paradigm_shifted"]:
                p(f"  [TREE] *** PARADIGM SHIFT -> {tree_status['paradigm'].upper()} ***")
            if tree_status["branch_dead"]:
                p(f"  [TREE] Branch '{tree_status['branch']}' died")

            # Lesson
            if result["returncode"] != 0:
                lesson = f"Failed: {stderr[:80]}"
            elif stdout and len(stdout) > 10:
                lesson = f"Output: {stdout[:80]}"
            else:
                lesson = "No useful output"

            entry = {
                "epoch": epoch + 1,
                "command": cmd,
                "approach": approach,
                "stdout": stdout[:500],
                "stderr": stderr[:200],
                "returncode": result["returncode"],
                "lesson": lesson,
                "time_s": round(gen_time, 1),
                "tree_paradigm": tree_status["paradigm"],
                "tree_facts": tree_status["total_facts"],
                "tree_branch": tree_status["branch"],
            }
            epoch_log.append(entry)
            log(entry)

    # Persist discoveries
    state_file = save_state(tree)
    p(f"\n  [STATE] Saved to {state_file}")

    # Summary
    tree_sum = tree.summary()
    p(f"\n{'='*60}")
    p("LAN DISCOVERY RESULTS")
    p(f"{'='*60}")
    p(f"Total epochs: {len(epoch_log)}")
    p(f"Paradigm shifts: {tree_sum['paradigm_shifts']}")
    p(f"Total facts discovered: {tree_sum['total_facts']}")
    p(f"\nDiscovered facts:")
    for key, fact in tree.facts.items():
        p(f"  {fact['description']}")
    p(f"{'='*60}")

    # Save summary
    out_file = LOG_FILE.parent / "lan_discovery_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "epochs": len(epoch_log),
            "tree_summary": tree_sum,
            "facts": {k: v for k, v in tree.facts.items()},
            "epoch_log": epoch_log,
        }, f, indent=2, default=str)

    p(f"\nResults: {out_file}")


if __name__ == "__main__":
    asyncio.run(run())
