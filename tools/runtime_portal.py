#!/usr/bin/env python
"""
Runtime supervisor portal for Aether.

Features:
- One command to launch API + Telegram bot
- Unified prefixed log stream
- Interactive process controls (status/start/stop/restart)
- Health polling
- Process-level hot reload on file changes (HMR-like dev loop)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional


def _now() -> str:
    return time.strftime("%H:%M:%S")


def _http_get_json(url: str, timeout: float = 2.0) -> tuple[Optional[dict], Optional[str]]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        return json.loads(payload or "{}"), None
    except urllib.error.HTTPError as e:
        return None, f"http_{e.code}"
    except Exception as e:
        return None, str(e)


@dataclass
class ManagedProcess:
    name: str
    command: list[str]
    cwd: Path
    env: Dict[str, str]
    logger: Callable[[str], None]
    process: Optional[subprocess.Popen] = None
    restart_count: int = 0
    started_at: float = 0.0
    _stdout_thread: Optional[threading.Thread] = None
    _stderr_thread: Optional[threading.Thread] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return False
            try:
                self.process = subprocess.Popen(
                    self.command,
                    cwd=str(self.cwd),
                    env=self.env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except Exception as e:
                self.logger(f"[portal] failed to start {self.name}: {e}")
                self.process = None
                return False

            self.started_at = time.time()
            self.logger(f"[portal] started {self.name} (pid={self.process.pid})")
            self._stdout_thread = threading.Thread(
                target=self._pump_stream,
                args=(self.process.stdout, "out"),
                daemon=True,
                name=f"{self.name}-stdout",
            )
            self._stderr_thread = threading.Thread(
                target=self._pump_stream,
                args=(self.process.stderr, "err"),
                daemon=True,
                name=f"{self.name}-stderr",
            )
            self._stdout_thread.start()
            self._stderr_thread.start()
            return True

    def stop(self, *, timeout: float = 8.0) -> bool:
        with self._lock:
            if not self.is_running():
                return False
            assert self.process is not None
            proc = self.process
            self.logger(f"[portal] stopping {self.name} (pid={proc.pid})")
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.logger(f"[portal] force-killing {self.name} (pid={proc.pid})")
                proc.kill()
            return True

    def restart(self, *, reason: str = "manual") -> None:
        self.stop()
        self.restart_count += 1
        self.logger(f"[portal] restarting {self.name} (reason={reason})")
        self.start()

    def status_line(self) -> str:
        if self.is_running():
            uptime = int(max(0.0, time.time() - self.started_at))
            assert self.process is not None
            return (
                f"{self.name}: running pid={self.process.pid} "
                f"uptime={uptime}s restarts={self.restart_count}"
            )
        return f"{self.name}: stopped restarts={self.restart_count}"

    def _pump_stream(self, stream, label: str) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                text = line.rstrip()
                if text:
                    self.logger(f"[{self.name}:{label}] {text}")
        except Exception as e:
            self.logger(f"[portal] stream error ({self.name}:{label}): {e}")
        finally:
            try:
                stream.close()
            except Exception:
                pass
            proc = self.process
            if proc is not None and proc.poll() is not None:
                self.logger(f"[portal] {self.name} exited with code {proc.returncode}")


class RuntimePortal:
    def __init__(
        self,
        *,
        root: Path,
        python_bin: Path,
        api_url: str,
        start_api: bool = True,
        start_telegram: bool = True,
        force_api: bool = False,
        hmr_enabled: bool = True,
        watch_interval: float = 1.0,
        health_interval: float = 5.0,
    ) -> None:
        self.root = root
        self.python_bin = python_bin
        self.api_url = api_url.rstrip("/")
        self.hmr_enabled = hmr_enabled
        self.watch_interval = max(0.5, watch_interval)
        self.health_interval = max(2.0, health_interval)
        self._print_lock = threading.Lock()
        self._stop = threading.Event()
        self._hmr_snapshot: Dict[str, float] = {}
        self._last_health_line = ""
        self._last_restart_at: Dict[str, float] = {"api": 0.0, "telegram": 0.0}

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env.setdefault("CRT_API_URL", self.api_url)
        self.env = env

        self.processes: Dict[str, ManagedProcess] = {
            "api": ManagedProcess(
                name="api",
                command=[str(self.python_bin), "crt_api.py"],
                cwd=self.root,
                env=self.env,
                logger=self.log,
            ),
            "telegram": ManagedProcess(
                name="telegram",
                command=[str(self.python_bin), "-m", "channels.telegram_bot"],
                cwd=self.root,
                env=self.env,
                logger=self.log,
            ),
        }

        self.api_external = False
        if start_api:
            up, _ = self._is_api_up()
            if up and not force_api:
                self.api_external = True
                self.log("[portal] API already reachable; not launching managed API process")
            else:
                self.processes["api"].start()
        if start_telegram:
            self.processes["telegram"].start()

        self._health_thread = threading.Thread(
            target=self._health_loop,
            daemon=True,
            name="portal-health",
        )
        self._hmr_thread = threading.Thread(
            target=self._hmr_loop,
            daemon=True,
            name="portal-hmr",
        )
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="portal-watchdog",
        )

    def log(self, message: str) -> None:
        with self._print_lock:
            print(f"{_now()} {message}", flush=True)

    def run(self) -> None:
        self.log("[portal] runtime portal ready. Type 'help' for commands.")
        self._health_thread.start()
        self._watchdog_thread.start()
        if self.hmr_enabled:
            self._hmr_snapshot = self._snapshot_files()
            self._hmr_thread.start()
            self.log("[portal] HMR watch is ON")
        else:
            self.log("[portal] HMR watch is OFF")

        try:
            self._command_loop()
        except KeyboardInterrupt:
            self.log("[portal] keyboard interrupt")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._stop.set()
        for proc in self.processes.values():
            proc.stop(timeout=5.0)
        self.log("[portal] shutdown complete")

    def _command_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = input("portal> ").strip()
            except EOFError:
                break
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()
            arg = parts[1].lower() if len(parts) > 1 else ""

            if cmd in {"quit", "exit"}:
                break
            if cmd == "help":
                self._print_help()
                continue
            if cmd == "status":
                self._print_status()
                continue
            if cmd in {"start", "stop", "restart"}:
                self._handle_process_command(cmd, arg or "all")
                continue
            if cmd == "hmr":
                self._handle_hmr_command(arg or "status")
                continue
            self.log(f"[portal] unknown command: {raw}")

    def _print_help(self) -> None:
        self.log("commands: status | start <api|telegram|all> | stop <...> | restart <...> | hmr <on|off|status> | quit")

    def _print_status(self) -> None:
        if self.api_external:
            self.log("[status] api: external process (reachable via health check)")
        for proc in self.processes.values():
            self.log(f"[status] {proc.status_line()}")
        up, err = self._is_api_up()
        self.log(f"[status] api_health={'up' if up else f'down ({err})'}")

    def _handle_process_command(self, action: str, target: str) -> None:
        names = ["api", "telegram"] if target == "all" else [target]
        for name in names:
            proc = self.processes.get(name)
            if proc is None:
                self.log(f"[portal] unknown process: {name}")
                continue
            if action == "start":
                proc.start()
            elif action == "stop":
                proc.stop()
            elif action == "restart":
                if name == "api" and self.api_external:
                    self.log("[portal] API is external; cannot restart unmanaged process")
                else:
                    proc.restart(reason="manual")

    def _handle_hmr_command(self, arg: str) -> None:
        if arg == "status":
            self.log(f"[portal] HMR is {'ON' if self.hmr_enabled else 'OFF'}")
            return
        if arg == "on":
            if self.hmr_enabled:
                self.log("[portal] HMR already ON")
                return
            self.hmr_enabled = True
            self._hmr_snapshot = self._snapshot_files()
            self._hmr_thread = threading.Thread(
                target=self._hmr_loop,
                daemon=True,
                name="portal-hmr",
            )
            self._hmr_thread.start()
            self.log("[portal] HMR enabled")
            return
        if arg == "off":
            self.hmr_enabled = False
            self.log("[portal] HMR disabled")
            return
        self.log(f"[portal] invalid hmr command: {arg}")

    def _is_api_up(self) -> tuple[bool, Optional[str]]:
        payload, err = _http_get_json(f"{self.api_url}/health", timeout=1.5)
        if err:
            return False, err
        if isinstance(payload, dict) and str(payload.get("status", "")).lower() == "ok":
            return True, None
        return False, "bad_health_payload"

    def _health_loop(self) -> None:
        while not self._stop.is_set():
            line = self._build_health_line()
            if line and line != self._last_health_line:
                self._last_health_line = line
                self.log(line)
            self._stop.wait(self.health_interval)

    def _build_health_line(self) -> str:
        up, err = self._is_api_up()
        if not up:
            return f"[health] api=down ({err})"

        hb, hb_err = _http_get_json(f"{self.api_url}/api/heartbeat/status", timeout=1.5)
        jobs, jobs_err = _http_get_json(f"{self.api_url}/api/jobs/status", timeout=1.5)

        hb_state = "unknown"
        if isinstance(hb, dict):
            hb_state = "running" if hb.get("running") else "idle"
        elif hb_err:
            hb_state = f"err:{hb_err}"

        jobs_state = "unknown"
        if isinstance(jobs, dict):
            worker = jobs.get("worker") or {}
            jobs_state = "running" if worker.get("running") else "idle"
        elif jobs_err:
            jobs_state = f"err:{jobs_err}"

        return f"[health] api=up heartbeat={hb_state} jobs={jobs_state}"

    def _watchdog_loop(self) -> None:
        while not self._stop.is_set():
            for name, proc in self.processes.items():
                if proc.process is not None and proc.process.poll() is not None:
                    # Process exited; keep portal alive and expose manual restart path.
                    # Auto-restart only for managed API when not external.
                    if name == "api" and not self.api_external:
                        self._restart_with_cooldown(name, "watchdog_exit")
            self._stop.wait(1.5)

    def _hmr_loop(self) -> None:
        while not self._stop.is_set():
            if not self.hmr_enabled:
                self._stop.wait(0.5)
                continue

            new_snapshot = self._snapshot_files()
            changed = self._diff_snapshot(self._hmr_snapshot, new_snapshot)
            self._hmr_snapshot = new_snapshot
            if changed:
                rel_preview = ", ".join(changed[:3])
                if len(changed) > 3:
                    rel_preview += f" (+{len(changed) - 3} more)"
                self.log(f"[hmr] change detected: {rel_preview}")
                self._apply_hmr(changed)
            self._stop.wait(self.watch_interval)

    def _apply_hmr(self, changed_rel_paths: Iterable[str]) -> None:
        restart_api = False
        restart_telegram = False
        for rel in changed_rel_paths:
            norm = rel.replace("\\", "/")
            if norm.startswith("personal_agent/") or norm.startswith("routes/"):
                restart_api = True
            if norm == "crt_api.py":
                restart_api = True
            if norm.startswith("channels/"):
                restart_telegram = True
                if norm in {"channels/base.py", "channels/__init__.py"}:
                    restart_api = True
            if norm.endswith(".json") and norm.startswith("crt_runtime_config"):
                restart_api = True

        if restart_api and not self.api_external:
            self._restart_with_cooldown("api", "hmr_change")
        if restart_telegram:
            self._restart_with_cooldown("telegram", "hmr_change")

    def _restart_with_cooldown(self, name: str, reason: str) -> None:
        now = time.time()
        if (now - self._last_restart_at.get(name, 0.0)) < 1.5:
            return
        self._last_restart_at[name] = now
        proc = self.processes.get(name)
        if proc is None:
            return
        if name == "api" and self.api_external:
            return
        proc.restart(reason=reason)

    def _snapshot_files(self) -> Dict[str, float]:
        include_roots = (
            self.root / "personal_agent",
            self.root / "routes",
            self.root / "channels",
            self.root / "crt_api.py",
            self.root / "crt_runtime_config.json",
        )
        snapshot: Dict[str, float] = {}
        for root in include_roots:
            if root.is_file():
                rel = str(root.relative_to(self.root))
                snapshot[rel] = float(root.stat().st_mtime)
                continue
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in {".py", ".json", ".yaml", ".yml"}:
                    continue
                rel = str(p.relative_to(self.root))
                try:
                    snapshot[rel] = float(p.stat().st_mtime)
                except FileNotFoundError:
                    continue
        return snapshot

    @staticmethod
    def _diff_snapshot(old: Dict[str, float], new: Dict[str, float]) -> list[str]:
        changed = []
        all_keys = set(old) | set(new)
        for key in sorted(all_keys):
            if key not in old or key not in new:
                changed.append(key)
                continue
            if abs(float(old[key]) - float(new[key])) > 1e-6:
                changed.append(key)
        return changed


def _resolve_python_bin(root: Path) -> Path:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path(sys.executable)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aether runtime supervisor portal")
    parser.add_argument("--api-url", default=os.getenv("CRT_API_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--force-api", action="store_true")
    parser.add_argument("--no-hmr", action="store_true")
    parser.add_argument("--watch-interval", type=float, default=1.0)
    parser.add_argument("--health-interval", type=float, default=5.0)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    python_bin = _resolve_python_bin(root)

    portal = RuntimePortal(
        root=root,
        python_bin=python_bin,
        api_url=args.api_url,
        start_api=not args.skip_api,
        start_telegram=not args.skip_telegram,
        force_api=args.force_api,
        hmr_enabled=not args.no_hmr,
        watch_interval=args.watch_interval,
        health_interval=args.health_interval,
    )
    portal.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
