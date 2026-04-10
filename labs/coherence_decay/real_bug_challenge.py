"""Real Bug Challenge: Mirus/Holden diagnose a production bug.

The bug: Electron health-checks port 8000, but Python backend runs on 8123.
UI never loads. "Startup timeout" in Electron logs.

Root cause: crt_api.py loads .env (PORT=8123), but electron/main.js
doesn't read .env, defaults to 8000. They talk past each other.

Fix: electron/main.js needs to load dotenv so both read the same PORT.

Mirus gets: symptoms + the relevant files. No hints about ports or .env.
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
from config import OLLAMA_URL

import builtins
_real_open = builtins.open

MIRUS_MODEL = "llama3.2:latest"
CLAUDE_CLI = os.getenv(
    "CLAUDE_CODE_EXECPATH",
    r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
)
MAX_EXPLORE = 10
MAX_PATCH = 8
LOG_FILE = Path(__file__).parent / "results" / "raw" / "real_bug.jsonl"
WORKSPACE = Path(__file__).parent / "results" / "challenges" / "real_bug"


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def clean(text):
    code = text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(l for l in lines if not l.startswith("```"))
    return code


# ---------------------------------------------------------------------------
# Setup: create the buggy workspace
# ---------------------------------------------------------------------------
def setup():
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    # The .env file (the source of truth that backend reads)
    with _real_open(WORKSPACE / ".env", "w") as f:
        f.write("PORT=8123\nOLLAMA_BASE_URL=http://localhost:11434\n")

    # Simplified crt_api.py — loads .env, uses PORT
    with _real_open(WORKSPACE / "crt_api.py", "w") as f:
        f.write('''"""CRT API Server (simplified for bug challenge)"""
import os
from dotenv import load_dotenv

# Load .env file — this sets PORT=8123
load_dotenv(override=True)

PORT = int(os.getenv("PORT", "8000"))

def start_server():
    """Start uvicorn on the configured port."""
    print(f"[BACKEND] Starting on port {PORT}")
    # uvicorn.run(app, host="127.0.0.1", port=PORT)

if __name__ == "__main__":
    start_server()
''')

    # Simplified electron/main.js — does NOT load .env (THE BUG)
    (WORKSPACE / "electron").mkdir(exist_ok=True)
    with _real_open(WORKSPACE / "electron" / "main.js", "w") as f:
        f.write('''// Electron main process (simplified for bug challenge)
const { app } = require('electron');

class Backend {
    constructor() {
        // BUG: reads PORT from process.env, which is empty
        // Defaults to 8000, but backend runs on 8123 (from .env)
        this.port = parseInt(process.env.PORT || '8000', 10);
        this.healthUrl = `http://127.0.0.1:${this.port}/health`;
    }

    async checkHealth() {
        try {
            const resp = await fetch(this.healthUrl);
            return resp.ok;
        } catch {
            return false;
        }
    }

    async waitForStartup(timeoutMs = 120000) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            if (await this.checkHealth()) {
                console.log('[ELECTRON] Backend healthy');
                return true;
            }
            await new Promise(r => setTimeout(r, 1000));
        }
        console.log('[ELECTRON] Startup timeout');
        return false;
    }
}

app.on('ready', async () => {
    const backend = new Backend();
    // Spawn Python backend (it reads .env and uses PORT=8123)
    // spawn('python', ['crt_api.py']);

    const healthy = await backend.waitForStartup();
    if (!healthy) {
        console.log('[ELECTRON] Backend failed to start');
        // app.quit();
    }
});
''')

    # Simplified backend.js with port config
    with _real_open(WORKSPACE / "electron" / "backend.js", "w") as f:
        f.write('''// Backend manager (simplified)
class BackendManager {
    constructor() {
        this.port = parseInt(process.env.PORT || '8000', 10);
    }

    getEnv() {
        return {
            ...process.env,
            PORT: String(this.port),
        };
    }

    getHealthUrl() {
        return `http://127.0.0.1:${this.port}/health`;
    }
}

module.exports = { BackendManager };
''')

    # The symptom log (what Mirus sees)
    with _real_open(WORKSPACE / "symptom.log", "w") as f:
        f.write('''[main] Aether Desktop starting...
[backend] Starting: python crt_api.py
[main] Backend status: starting
[backend:out] [BACKEND] Starting on port 8123
[backend:err] INFO: Started server process [7719]
[backend:err] INFO: Waiting for application startup.
[backend:err] INFO: Application startup complete.
[backend:err] INFO: Uvicorn running on http://127.0.0.1:8123 (Press CTRL+C to quit)
[main] Health check: http://127.0.0.1:8000/health -> connection refused
[main] Health check: http://127.0.0.1:8000/health -> connection refused
[main] Health check: http://127.0.0.1:8000/health -> connection refused
[main] Health check: http://127.0.0.1:8000/health -> connection refused
... (120 seconds of repeated health check failures)
[main] Backend status: timeout
[main] Backend failed to start
''')


# ---------------------------------------------------------------------------
# Verification: does the fix address the root cause?
# ---------------------------------------------------------------------------
def verify_fix(diagnosis):
    """Check if Mirus identified the real root cause and proposed a valid fix."""
    d = diagnosis.lower()

    checks = {
        "identified_port_mismatch": (
            ("8123" in d and "8000" in d) or
            "port mismatch" in d or
            "different port" in d or
            "wrong port" in d
        ),
        "identified_env_source": (
            ".env" in d and ("electron" in d or "main.js" in d or "backend.js" in d)
        ),
        "proposed_dotenv_fix": (
            "dotenv" in d or
            "load_dotenv" in d or
            "read .env" in d or
            "load .env" in d or
            "read the .env" in d
        ),
        "identified_correct_files": (
            ("main.js" in d or "backend.js" in d) and
            ("crt_api" in d or ".env" in d or "python" in d)
        ),
    }

    passed = sum(1 for v in checks.values() if v)
    return {
        "score": passed,
        "total": len(checks),
        "checks": {k: v for k, v in checks.items()},
        "solved": passed >= 3,  # Need at least 3/4 to count as solved
    }


# ---------------------------------------------------------------------------
# Mirus explores
# ---------------------------------------------------------------------------
async def mirus_explore(session, epoch, prior_findings, hints):
    files_available = "crt_api.py, electron/main.js, electron/backend.js, .env, symptom.log"

    history = ""
    if prior_findings:
        history = "YOUR FINDINGS SO FAR:\n"
        for f in prior_findings[-5:]:
            history += f"  Epoch {f['epoch']}: {f['finding']}\n"

    hints_text = ""
    if hints:
        hints_text = "HINTS:\n" + "\n".join(f"  - {h}" for h in hints[-3:])

    # Read the symptom log
    with _real_open(WORKSPACE / "symptom.log") as f:
        symptom = f.read()

    # Read source files for context
    with _real_open(WORKSPACE / "crt_api.py") as f:
        api_code = f.read()
    with _real_open(WORKSPACE / "electron" / "main.js") as f:
        main_code = f.read()
    with _real_open(WORKSPACE / "electron" / "backend.js") as f:
        backend_code = f.read()
    with _real_open(WORKSPACE / ".env") as f:
        env_content = f.read()

    prompt = (
        f"You are debugging a production bug in an Electron + Python application.\n\n"
        f"SYMPTOM LOG:\n{symptom}\n\n"
        f"FILES:\n\n"
        f"--- .env ---\n{env_content}\n\n"
        f"--- crt_api.py ---\n{api_code}\n\n"
        f"--- electron/main.js ---\n{main_code}\n\n"
        f"--- electron/backend.js ---\n{backend_code}\n\n"
        f"{history}\n{hints_text}\n\n"
        f"TASK: Diagnose why the UI never loads despite the backend starting successfully.\n"
        f"Explain:\n"
        f"1. What is the ROOT CAUSE?\n"
        f"2. Which files are involved?\n"
        f"3. What is the specific fix?\n\n"
        f"Be specific. Reference line numbers and variable names."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": (
            "You are a senior developer debugging a cross-process communication bug. "
            "Read the logs carefully. Compare the configurations. Find the mismatch."
        ),
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 4096},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()
    return data.get("response", "")


# ---------------------------------------------------------------------------
# Holden nudges
# ---------------------------------------------------------------------------
def holden_nudge(epoch, diagnosis, verification):
    """Progressive hints based on what Mirus hasn't found yet."""
    missing = [k for k, v in verification["checks"].items() if not v]

    if not missing:
        return None  # All found

    # Progressive nudges based on what's still missing
    if "identified_port_mismatch" in missing:
        focus = "Look at the symptom log VERY carefully. What PORT is the backend running on? What PORT is the health check hitting? Are they the same?"
    elif "identified_env_source" in missing:
        focus = "You found the port mismatch. Now: WHY are they different? Where does each process get its PORT value from?"
    elif "proposed_dotenv_fix" in missing:
        focus = "You know the ports don't match and you know why. What's the specific code change that would make Electron read the same PORT as Python?"
    elif "identified_correct_files" in missing:
        focus = "Which specific files need to change to fix this? Be precise — file name and what to add/modify."
    else:
        focus = "Review your diagnosis. Is it complete? Does it explain the root cause AND the fix?"

    prompt = (
        f"A junior developer diagnosed this bug but missed something:\n\n"
        f"THEIR DIAGNOSIS:\n{diagnosis[:500]}\n\n"
        f"VERIFICATION: {json.dumps(verification['checks'])}\n\n"
        f"Give ONE nudge hint to help them find what they're missing.\n"
        f"Focus on: {focus}\n\n"
        f"ONE sentence only. Don't give the answer."
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        hint = result.stdout.strip() if result.returncode == 0 else None
        if hint and ". " in hint:
            hint = hint.split(". ")[0] + "."
        return hint[:200] if hint else None
    except:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run():
    setup()
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("REAL BUG CHALLENGE: Electron + Python port mismatch")
    p("=" * 60)
    p("Symptom: Backend starts on 8123, Electron health-checks 8000")
    p("Root cause: hidden in the code")
    p(f"Mirus model: {MIRUS_MODEL}")
    p("=" * 60)

    prior_findings = []
    hints = []

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EXPLORE):
            p(f"\n{'='*50}")
            p(f"EPOCH {epoch+1}/{MAX_EXPLORE}")
            p(f"{'='*50}")

            # Mirus diagnoses
            p(f"\n  [MIRUS] Analyzing...")
            t0 = time.time()
            diagnosis = await mirus_explore(session, epoch, prior_findings, hints)
            gen_time = time.time() - t0

            p(f"  [MIRUS] ({gen_time:.1f}s) Diagnosis:")
            for line in diagnosis.split("\n")[:15]:
                p(f"    {line}")
            if len(diagnosis.split("\n")) > 15:
                p(f"    ... ({len(diagnosis.split(chr(10)))} lines)")

            # Verify
            verification = verify_fix(diagnosis)
            p(f"\n  [VERIFY] Score: {verification['score']}/{verification['total']}")
            for check, passed in verification["checks"].items():
                status = "PASS" if passed else "MISS"
                p(f"    [{status}] {check}")

            prior_findings.append({
                "epoch": epoch + 1,
                "finding": diagnosis[:200],
                "score": verification["score"],
            })

            log({
                "epoch": epoch + 1,
                "diagnosis": diagnosis[:1000],
                "verification": verification,
                "hints_given": len(hints),
            })

            if verification["solved"]:
                p(f"\n{'='*50}")
                p(f"BUG DIAGNOSED on epoch {epoch+1}!")
                p(f"Score: {verification['score']}/{verification['total']}")
                p(f"Hints needed: {len(hints)}")
                p(f"{'='*50}")
                break

            # Holden nudges
            p(f"\n  [HOLDEN] Nudging...")
            t0 = time.time()
            hint = holden_nudge(epoch, diagnosis, verification)
            nudge_time = time.time() - t0

            if hint:
                hints.append(hint)
                p(f"  [HOLDEN] ({nudge_time:.1f}s): {hint}")
            else:
                p(f"  [HOLDEN] (no hint needed or no response)")

        else:
            p(f"\n{'='*50}")
            p(f"FAILED to diagnose after {MAX_EXPLORE} epochs")
            p(f"Best score: {max(f['score'] for f in prior_findings)}/{4}")
            p(f"{'='*50}")

    # Summary
    p(f"\n{'='*60}")
    p("DIAGNOSTIC TRAJECTORY")
    p(f"{'='*60}")
    for f in prior_findings:
        p(f"  Epoch {f['epoch']}: score {f['score']}/4")
    p(f"\n  Hints given:")
    for i, h in enumerate(hints):
        p(f"    {i+1}: {h}")
    p(f"  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
