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
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


def _now() -> str:
    return time.strftime("%H:%M:%S")


def _http_get_json(url: str, timeout: float = 2.0) -> tuple[Optional[Any], Optional[str]]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        return json.loads(payload or "{}"), None
    except urllib.error.HTTPError as e:
        return None, f"http_{e.code}"
    except Exception as e:
        return None, str(e)


def _http_post_json(url: str, payload: Optional[dict] = None, timeout: float = 3.0) -> tuple[Optional[Any], Optional[str]]:
    body = b""
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data or "{}"), None
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
            args = parts[1:]
            arg = args[0].lower() if args else ""

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
            if cmd in {"system", "copilot"}:
                self._handle_system_command(args)
                continue
            if cmd == "hmr":
                self._handle_hmr_command(arg or "status")
                continue
            self.log(f"[portal] unknown command: {raw}")

    def _print_help(self) -> None:
        self.log(
            "commands: status | "
            "start <api|telegram|all|heartbeat|dnnt> | "
            "stop <api|telegram|all|heartbeat|dnnt> | "
            "restart <api|telegram|all|heartbeat|dnnt> | "
            "system <status|decay|tick|checks [limit]|resolve <check_id>|reinforce <memory_id>|retrain> | "
            "copilot <...> (alias) | "
            "hmr <on|off|status> | quit"
        )

    def _print_status(self) -> None:
        if self.api_external:
            self.log("[status] api: external process (reachable via health check)")
        for proc in self.processes.values():
            self.log(f"[status] {proc.status_line()}")
        up, err = self._is_api_up()
        self.log(f"[status] api_health={'up' if up else f'down ({err})'}")

    def _handle_process_command(self, action: str, target: str) -> None:
        if target in {"heartbeat", "dnnt"}:
            self._handle_api_background_command(action, target)
            return
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

    def _handle_api_background_command(self, action: str, target: str) -> None:
        endpoint_map = {
            "heartbeat": ("/api/heartbeat/start", "/api/heartbeat/stop"),
            "dnnt": ("/api/dnnt/retraining/start", "/api/dnnt/retraining/stop"),
        }
        endpoints = endpoint_map.get(target)
        if endpoints is None:
            self.log(f"[portal] unsupported background target: {target}")
            return
        start_ep, stop_ep = endpoints

        if action == "start":
            _, err = _http_post_json(f"{self.api_url}{start_ep}")
            self.log(
                f"[portal] {target} start {'ok' if not err else f'failed ({err})'}"
            )
            return
        if action == "stop":
            _, err = _http_post_json(f"{self.api_url}{stop_ep}")
            self.log(
                f"[portal] {target} stop {'ok' if not err else f'failed ({err})'}"
            )
            return
        if action == "restart":
            _, err1 = _http_post_json(f"{self.api_url}{stop_ep}")
            _, err2 = _http_post_json(f"{self.api_url}{start_ep}")
            if not err1 and not err2:
                self.log(f"[portal] {target} restart ok")
            else:
                self.log(f"[portal] {target} restart failed (stop={err1}, start={err2})")
            return

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

    def _handle_system_command(self, args: list[str]) -> None:
        sub = args[0].lower() if args else "status"

        if sub == "status":
            self._print_system_status()
            return

        if sub == "decay":
            payload, err = _http_post_json(f"{self.api_url}/api/copilot/trust-decay/run")
            self._log_system_result("decay", payload, err)
            return

        if sub == "tick":
            payload, err = _http_post_json(f"{self.api_url}/api/copilot/scheduler/tick")
            self._log_system_result("tick", payload, err)
            return

        if sub == "retrain":
            payload, err = _http_post_json(f"{self.api_url}/api/copilot/learning/retrain")
            self._log_system_result("retrain", payload, err)
            return

        if sub == "checks":
            limit = 10
            if len(args) > 1:
                try:
                    limit = int(args[1])
                except ValueError:
                    self.log(f"[system] invalid checks limit: {args[1]}")
                    return
            limit = max(1, min(limit, 100))
            payload, err = _http_get_json(f"{self.api_url}/api/copilot/fact-checks?limit={limit}")
            if err:
                self.log(f"[system] checks failed ({err})")
                return
            if not isinstance(payload, list):
                self.log(f"[system] checks unexpected payload={self._compact_preview(payload)}")
                return
            self.log(f"[system] pending fact checks={len(payload)}")
            for row in payload:
                if not isinstance(row, dict):
                    continue
                check_id = str(row.get("id", "?"))
                severity = str(row.get("severity", "?"))
                status = str(row.get("status", "?"))
                finding = self._truncate(str(row.get("finding", "")))
                self.log(
                    f"[system] - id={check_id} severity={severity} status={status} finding={finding}"
                )
            return

        if sub == "resolve":
            if len(args) < 2:
                self.log("[system] usage: system resolve <check_id>")
                return
            check_id = urllib.parse.quote(args[1], safe="")
            payload, err = _http_post_json(
                f"{self.api_url}/api/copilot/fact-checks/{check_id}/resolve"
            )
            self._log_system_result("resolve", payload, err)
            return

        if sub == "reinforce":
            if len(args) < 2:
                self.log("[system] usage: system reinforce <memory_id>")
                return
            memory_id = urllib.parse.quote(args[1], safe="")
            payload, err = _http_post_json(
                f"{self.api_url}/api/copilot/memory/{memory_id}/reinforce"
            )
            self._log_system_result("reinforce", payload, err)
            return

        self.log(
            "[system] usage: system <status|decay|tick|checks [limit]|resolve <check_id>|reinforce <memory_id>|retrain>"
        )

    def _print_system_status(self) -> None:
        scheduler, scheduler_err = _http_get_json(
            f"{self.api_url}/api/copilot/scheduler/status", timeout=1.5
        )
        if scheduler_err:
            self.log(f"[system] scheduler status failed ({scheduler_err})")
        elif isinstance(scheduler, dict):
            self.log(
                "[system] scheduler "
                f"enabled={bool(scheduler.get('enabled', False))} "
                f"auto_learning={bool(scheduler.get('auto_learning_enabled', False))} "
                f"idle_seconds={scheduler.get('idle_seconds')} "
                f"interval_seconds={scheduler.get('interval_seconds')}"
            )
        else:
            self.log(f"[system] scheduler payload={self._compact_preview(scheduler)}")

        checks, checks_err = _http_get_json(
            f"{self.api_url}/api/copilot/fact-checks?limit=50", timeout=1.5
        )
        if checks_err:
            self.log(f"[system] fact checks failed ({checks_err})")
        elif isinstance(checks, list):
            self.log(f"[system] pending_fact_checks={len(checks)}")
        else:
            self.log(f"[system] fact checks payload={self._compact_preview(checks)}")

        learning, learning_err = _http_get_json(
            f"{self.api_url}/api/copilot/learning/stats", timeout=1.5
        )
        if learning_err:
            self.log(f"[system] learning stats failed ({learning_err})")
        elif isinstance(learning, dict):
            self.log(
                "[system] learning "
                f"total_events={learning.get('total_events')} "
                f"total_corrections={learning.get('total_corrections')} "
                f"pending_training={learning.get('pending_training')}"
            )
        else:
            self.log(f"[system] learning payload={self._compact_preview(learning)}")

        training, training_err = _http_get_json(
            f"{self.api_url}/api/copilot/training-data/stats", timeout=1.5
        )
        if training_err:
            self.log(f"[system] training-data stats failed ({training_err})")
        elif isinstance(training, dict):
            self.log(
                "[system] training-data "
                f"total_reflections={training.get('total_reflections')} "
                f"total_requeries={training.get('total_requeries')} "
                f"total_preferences={training.get('total_preferences')}"
            )
        else:
            self.log(f"[system] training-data payload={self._compact_preview(training)}")

    def _log_system_result(self, action: str, payload: Optional[Any], err: Optional[str]) -> None:
        if err:
            self.log(f"[system] {action} failed ({err})")
            return
        self.log(f"[system] {action} ok payload={self._compact_preview(payload)}")

    @staticmethod
    def _truncate(text: str, max_len: int = 120) -> str:
        one_line = " ".join(text.split())
        if len(one_line) <= max_len:
            return one_line
        return f"{one_line[:max_len - 3]}..."

    @staticmethod
    def _compact_preview(payload: Optional[Any], max_len: int = 220) -> str:
        if payload is None:
            return "null"
        try:
            text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        except Exception:
            text = str(payload)
        if len(text) <= max_len:
            return text
        return f"{text[:max_len - 3]}..."

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
        dnnt, dnnt_err = _http_get_json(f"{self.api_url}/api/dnnt/retraining/status", timeout=1.5)
        system_bg, system_bg_err = _http_get_json(
            f"{self.api_url}/api/copilot/scheduler/status", timeout=1.5
        )

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

        dnnt_state = "unknown"
        if isinstance(dnnt, dict):
            dnnt_state = "running" if dnnt.get("running") else "idle"
        elif dnnt_err:
            dnnt_state = f"err:{dnnt_err}"

        system_state = "unknown"
        if isinstance(system_bg, dict):
            sched = "on" if system_bg.get("enabled") else "off"
            auto = "on" if system_bg.get("auto_learning_enabled") else "off"
            system_state = f"sched:{sched},al:{auto}"
        elif system_bg_err:
            system_state = f"err:{system_bg_err}"

        return (
            f"[health] api=up heartbeat={hb_state} jobs={jobs_state} "
            f"dnnt={dnnt_state} system={system_state}"
        )

    def _watchdog_loop(self) -> None:
        while not self._stop.is_set():
            for name, proc in self.processes.items():
                if proc.process is not None and proc.process.poll() is not None:
                    # Process exited; keep portal alive and expose manual restart path.
                    # Auto-restart only for managed API when not external.
                    if name == "api" and not self.api_external:
                        # If API is already reachable, another process owns it.
                        # Treat it as external and stop restart loops on bind errors.
                        up, _err = self._is_api_up()
                        if up:
                            self.api_external = True
                            self.log("[portal] API became externally managed; disabling managed API restarts")
                            continue
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
