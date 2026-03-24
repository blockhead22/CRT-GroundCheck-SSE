"""
Layer 1 — Read-only system awareness.

Provides get_system_snapshot() which returns CPU, RAM, GPU, disk,
top processes, and active window info as a plain dict.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPU helpers (pynvml — optional)
# ---------------------------------------------------------------------------

def _gpu_info() -> Optional[Dict[str, Any]]:
    """Return GPU usage dict or None if unavailable."""
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode()
        result = {
            "name": name,
            "gpu_percent": util.gpu,
            "memory_used_mb": round(mem.used / (1024 ** 2)),
            "memory_total_mb": round(mem.total / (1024 ** 2)),
            "memory_percent": round(mem.used / mem.total * 100, 1) if mem.total else 0,
        }
        pynvml.nvmlShutdown()
        return result
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Active window helper (pygetwindow — optional, Windows only)
# ---------------------------------------------------------------------------

def _active_window() -> Optional[str]:
    """Return the title of the foreground window, or None."""
    try:
        import pygetwindow as gw  # type: ignore
        win = gw.getActiveWindow()
        return win.title if win else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Top processes
# ---------------------------------------------------------------------------

_GAME_EXECUTABLES = frozenset([
    "steam.exe", "steamwebhelper.exe",
    "csgo.exe", "cs2.exe", "valorant.exe", "riotclientservices.exe",
    "fortnite.exe", "fortniteclient-win64-shipping.exe",
    "gta5.exe", "gtavlauncher.exe", "rdr2.exe",
    "overwatch.exe", "overwatchlauncher.exe",
    "minecraft.exe", "javaw.exe",
    "eldenring.exe", "darksoulsiii.exe",
    "baldursgate3.exe", "bg3.exe", "bg3_dx11.exe",
    "cyberpunk2077.exe", "witcher3.exe",
    "destiny2.exe", "apex_legends.exe", "r5apex.exe",
    "leagueclient.exe", "league of legends.exe",
    "dota2.exe", "cod.exe", "modernwarfare.exe",
    "helldivers2.exe", "palworld.exe", "enshrouded.exe",
    "starfield.exe", "hogwartslegacy.exe",
    "epicgameslauncher.exe", "easyanticheat.exe",
    "battleye.exe", "vanguard.exe",
])


def _top_processes(n: int = 5) -> List[Dict[str, Any]]:
    """Return top *n* processes by CPU + memory, with a gaming flag."""
    procs: List[Dict[str, Any]] = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info  # type: ignore[attr-defined]
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_percent": round(info["memory_percent"] or 0.0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Sort by combined CPU + memory weight
    procs.sort(key=lambda p: p["cpu_percent"] + p["memory_percent"] * 2, reverse=True)
    top = procs[:n]
    for p in top:
        p["is_game"] = (p["name"] or "").lower() in _GAME_EXECUTABLES
    return top


# ---------------------------------------------------------------------------
# Main snapshot
# ---------------------------------------------------------------------------

def get_system_snapshot() -> Dict[str, Any]:
    """Collect a point-in-time system snapshot. All read-only, no side effects."""
    t0 = time.time()

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)
    cpu_count = psutil.cpu_count(logical=True)

    # RAM
    vmem = psutil.virtual_memory()
    ram = {
        "total_gb": round(vmem.total / (1024 ** 3), 1),
        "available_gb": round(vmem.available / (1024 ** 3), 1),
        "used_gb": round(vmem.used / (1024 ** 3), 1),
        "percent": vmem.percent,
    }

    # Disk (main drive)
    try:
        disk = psutil.disk_usage("/")
        disk_info = {
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "percent": disk.percent,
        }
    except Exception:
        disk_info = None

    # GPU
    gpu = _gpu_info()

    # Processes
    top_procs = _top_processes(5)

    # Active window
    active_win = _active_window()

    # Derived flags
    gaming = False
    idle = False
    if gpu and gpu.get("gpu_percent", 0) > 85:
        gaming = any(p.get("is_game") for p in top_procs)
    if cpu_percent < 10 and (not gpu or gpu.get("gpu_percent", 0) < 15):
        idle = True

    elapsed_ms = round((time.time() - t0) * 1000)

    snapshot: Dict[str, Any] = {
        "cpu": {
            "percent": cpu_percent,
            "per_core": cpu_per_core,
            "logical_cores": cpu_count,
        },
        "ram": ram,
        "disk": disk_info,
        "gpu": gpu,
        "top_processes": top_procs,
        "active_window": active_win,
        "flags": {
            "gaming": gaming,
            "idle": idle,
        },
        "snapshot_ms": elapsed_ms,
    }

    logger.info("[SYSTEM_INFO] Snapshot captured in %dms (cpu=%.0f%% ram=%.0f%% gpu=%s gaming=%s idle=%s)",
                elapsed_ms, cpu_percent, vmem.percent,
                f"{gpu['gpu_percent']}%" if gpu else "n/a",
                gaming, idle)

    return snapshot


def format_snapshot_text(snap: Dict[str, Any]) -> str:
    """Format a snapshot dict as human-readable text for LLM consumption."""
    lines = []

    # CPU
    cpu = snap.get("cpu", {})
    lines.append(f"CPU: {cpu.get('percent', '?')}% across {cpu.get('logical_cores', '?')} cores")

    # RAM
    ram = snap.get("ram", {})
    lines.append(f"RAM: {ram.get('used_gb', '?')} / {ram.get('total_gb', '?')} GB ({ram.get('percent', '?')}%)")

    # GPU
    gpu = snap.get("gpu")
    if gpu:
        lines.append(f"GPU: {gpu.get('name', 'Unknown')} — {gpu.get('gpu_percent', '?')}% utilization, "
                      f"VRAM {gpu.get('memory_used_mb', '?')} / {gpu.get('memory_total_mb', '?')} MB ({gpu.get('memory_percent', '?')}%)")
    else:
        lines.append("GPU: not detected / no driver")

    # Disk
    disk = snap.get("disk")
    if disk:
        lines.append(f"Disk: {disk.get('free_gb', '?')} GB free of {disk.get('total_gb', '?')} GB ({disk.get('percent', '?')}% used)")

    # Active window
    win = snap.get("active_window")
    if win:
        lines.append(f"Active window: {win}")

    # Top processes
    procs = snap.get("top_processes", [])
    if procs:
        lines.append("Top processes:")
        for p in procs:
            game_tag = " [GAME]" if p.get("is_game") else ""
            lines.append(f"  - {p['name']} (PID {p['pid']}): CPU {p['cpu_percent']:.0f}%, RAM {p['memory_percent']:.1f}%{game_tag}")

    # Flags
    flags = snap.get("flags", {})
    if flags.get("gaming"):
        lines.append(">> GAMING detected")
    if flags.get("idle"):
        lines.append(">> System is IDLE")

    return "\n".join(lines)
