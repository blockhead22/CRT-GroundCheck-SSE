"""Real Codebase Audit: Find bugs in CRT's heartbeat system.

No planted bugs. No simplified code. Real production files.
Mirus reads the actual source and reports what it finds.
Holden validates whether findings are real.

This is the ultimate test: can the system find bugs
that the developer doesn't know about yet?
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
MAX_EPOCHS = 10
LOG_FILE = Path(__file__).parent / "results" / "raw" / "audit_crt.jsonl"

# Real source files
SOURCE_FILES = [
    r"D:\AI_round2\personal_agent\heartbeat_executor.py",
    r"D:\AI_round2\personal_agent\governance_bridge.py",
]


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read_source(path, max_chars=15000):
    """Read source file, truncate if too large for context."""
    with _real_open(path) as f:
        content = f.read()
    if len(content) > max_chars:
        # Keep first and last portions
        half = max_chars // 2
        content = content[:half] + f"\n\n... [{len(content)} chars total, middle truncated] ...\n\n" + content[-half:]
    return content


def holden_validate(finding):
    """Holden (Claude) evaluates whether a finding is real."""
    # Read the full source files for Holden (Claude has larger context)
    sources = {}
    for path in SOURCE_FILES:
        with _real_open(path) as f:
            sources[os.path.basename(path)] = f.read()

    source_text = "\n\n".join([f"--- {k} ---\n{v[:8000]}" for k, v in sources.items()])

    prompt = (
        f"A 3B model audited production code and reported this finding:\n\n"
        f"FINDING:\n{finding}\n\n"
        f"SOURCE CODE:\n{source_text}\n\n"
        f"EVALUATE:\n"
        f"1. Is this a REAL bug/issue, or a false positive?\n"
        f"2. If real: severity (critical/high/medium/low/informational)\n"
        f"3. If real: is this a known pattern or a novel finding?\n"
        f"4. Could this cause issues in production?\n\n"
        f"Be honest. If it's a false positive, say so. If it's real, explain why.\n"
        f"Format: VERDICT: real|false_positive\nSEVERITY: ...\nEXPLANATION: ..."
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        return result.stdout.strip() if result.returncode == 0 else "Validation unavailable"
    except:
        return "Validation unavailable"


async def mirus_audit(session, epoch, prior_findings, focus_area=None):
    """Mirus reads real source code and looks for bugs."""

    sources = {}
    for path in SOURCE_FILES:
        sources[os.path.basename(path)] = read_source(path)

    source_text = "\n\n".join([f"--- {k} ---\n{v}" for k, v in sources.items()])

    history = ""
    if prior_findings:
        history = "YOUR PREVIOUS FINDINGS (find something NEW):\n"
        for f in prior_findings:
            history += f"  - {f['summary'][:100]}\n"

    focus = ""
    if focus_area:
        focus = f"FOCUS AREA: {focus_area}\n"
    elif epoch == 0:
        focus = "FOCUS: Look for error handling issues, silent failures, race conditions, or data corruption risks.\n"
    elif epoch == 1:
        focus = "FOCUS: Look for resource leaks, unclosed connections, or memory growth patterns.\n"
    elif epoch == 2:
        focus = "FOCUS: Look for security issues — unsanitized inputs, exposed internals, or trust boundary violations.\n"
    elif epoch == 3:
        focus = "FOCUS: Look for logic errors — wrong conditions, off-by-one, or incorrect state transitions.\n"
    elif epoch == 4:
        focus = "FOCUS: Look for concurrency issues — shared state, missing locks, thread safety.\n"
    elif epoch == 5:
        focus = (
            "FOCUS: FORECAST — This system currently has 849 memories. "
            "What breaks at 10,000? 100,000? Look for O(n^2) operations, "
            "unbounded loops, missing pagination, memory growth that never gets pruned.\n"
        )
    elif epoch == 6:
        focus = (
            "FOCUS: FORECAST — The heartbeat runs every 30 seconds. "
            "What happens if one cycle takes LONGER than 30 seconds? "
            "Is there overlap protection? What state gets corrupted if two cycles run simultaneously?\n"
        )
    elif epoch == 7:
        focus = (
            "FOCUS: FORECAST — The system runs 24/7. What degrades over days? Weeks? "
            "Look for counters that grow without bound, caches that never clear, "
            "timestamps that lose precision, or state that accumulates without cleanup.\n"
        )
    elif epoch == 8:
        focus = (
            "FOCUS: FORECAST — What happens during network failures? "
            "Ollama goes down, the DB file gets locked, disk fills up. "
            "Does the heartbeat recover gracefully or does it enter a broken state?\n"
        )
    else:
        focus = (
            "FOCUS: FORECAST — Think about edge cases nobody tests. "
            "Empty DB. Corrupted JSON. Unicode in memory text. "
            "Clock skew. Timezone changes. Daylight savings. Leap seconds.\n"
        )

    prompt = (
        f"You are performing a security and reliability audit on production Python code.\n\n"
        f"{focus}\n"
        f"SOURCE CODE:\n{source_text}\n\n"
        f"{history}\n"
        f"Report ONE specific bug or vulnerability. For each finding:\n"
        f"1. FILE and LINE (approximate) where the issue is\n"
        f"2. WHAT the bug is (be specific)\n"
        f"3. HOW it could cause problems in production\n"
        f"4. SEVERITY (critical/high/medium/low)\n"
        f"5. SUGGESTED FIX (1-2 lines of code)\n\n"
        f"Only report issues you're confident about. No speculation."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": (
            "You are a senior security auditor reviewing production Python code. "
            "Report only real, specific issues with file names and line numbers. "
            "No vague concerns. Each finding must be actionable."
        ),
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 8192},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=90)) as resp:
        data = await resp.json()
    return data.get("response", "")


async def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("REAL CODEBASE AUDIT: CRT Heartbeat System")
    p("=" * 60)
    p(f"Auditor: {MIRUS_MODEL} (3B)")
    p(f"Validator: claude-sonnet-4-6")
    p(f"Target files:")
    for f in SOURCE_FILES:
        p(f"  {os.path.basename(f)}")
    p(f"Epochs: {MAX_EPOCHS}")
    p("=" * 60)

    findings = []

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EPOCHS):
            p(f"\n{'='*50}")
            p(f"AUDIT PASS {epoch+1}/{MAX_EPOCHS}")
            p(f"{'='*50}")

            # Mirus audits
            p(f"\n  [MIRUS] Auditing...")
            t0 = time.time()
            finding = await mirus_audit(session, epoch, findings)
            audit_time = time.time() - t0

            p(f"  [MIRUS] ({audit_time:.1f}s) Finding:")
            for line in finding.split("\n")[:15]:
                p(f"    {line}")
            if len(finding.split("\n")) > 15:
                p(f"    ... ({len(finding.split(chr(10)))} lines)")

            # Holden validates
            p(f"\n  [HOLDEN] Validating finding...")
            t0 = time.time()
            validation = holden_validate(finding)
            val_time = time.time() - t0

            # Parse verdict
            verdict = "unknown"
            severity = "unknown"
            for vline in validation.split("\n"):
                if vline.strip().startswith("VERDICT:"):
                    verdict = vline.split(":", 1)[1].strip().lower()
                elif vline.strip().startswith("SEVERITY:"):
                    severity = vline.split(":", 1)[1].strip().lower()

            is_real = "real" in verdict and "false" not in verdict

            p(f"  [HOLDEN] ({val_time:.1f}s):")
            p(f"    Verdict: {'REAL BUG' if is_real else 'FALSE POSITIVE'}")
            p(f"    Severity: {severity}")
            for line in validation.split("\n")[:8]:
                p(f"    {line}")

            finding_record = {
                "epoch": epoch + 1,
                "summary": finding[:200],
                "full_finding": finding,
                "verdict": verdict,
                "severity": severity,
                "is_real": is_real,
            }
            findings.append(finding_record)

            log({
                "epoch": epoch + 1,
                "finding": finding[:1000],
                "validation": validation[:1000],
                "verdict": verdict,
                "severity": severity,
                "is_real": is_real,
            })

    # Summary
    real_bugs = [f for f in findings if f["is_real"]]
    false_positives = [f for f in findings if not f["is_real"]]

    p(f"\n{'='*60}")
    p("AUDIT RESULTS")
    p(f"{'='*60}")
    p(f"  Total findings: {len(findings)}")
    p(f"  Real bugs: {len(real_bugs)}")
    p(f"  False positives: {len(false_positives)}")

    if real_bugs:
        p(f"\n  CONFIRMED BUGS:")
        for i, bug in enumerate(real_bugs):
            p(f"    {i+1}. [{bug['severity']}] {bug['summary'][:120]}")

    if false_positives:
        p(f"\n  FALSE POSITIVES:")
        for i, fp in enumerate(false_positives):
            p(f"    {i+1}. {fp['summary'][:120]}")

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
