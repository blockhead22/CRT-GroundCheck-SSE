"""Chunked Audit: Holden-as-attention-pointer.

Instead of dumping 15K chars into one prompt, Holden:
1. AST-parses the source into functions
2. Digests each function into a ~40-token semantic summary
3. Feeds Mirus ONE function at a time
4. Checks whether Mirus's concern is already guarded
5. Steers to the next uncovered function

This tests whether the 0/20 false positive rate was an architecture
failure (attention exhaustion) rather than a capability failure.
"""

import ast
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

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
LOG_FILE = Path(__file__).parent / "results" / "raw" / "audit_chunked.jsonl"

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


# ---------------------------------------------------------------------------
# Step 1: AST extraction — pull every function with its source
# ---------------------------------------------------------------------------
def extract_functions(filepath: str) -> List[Dict]:
    """Extract all functions from a Python file with their source code."""
    with _real_open(filepath) as f:
        source = f.read()

    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1  # 0-indexed
            end = getattr(node, 'end_lineno', node.lineno)
            func_source = ''.join(lines[start:end])

            # Get the class this function belongs to (if any)
            parent_class = None
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    if any(child is node for child in ast.walk(parent)):
                        parent_class = parent.name

            functions.append({
                "name": node.name,
                "class": parent_class,
                "file": os.path.basename(filepath),
                "start_line": node.lineno,
                "end_line": end,
                "line_count": end - node.lineno + 1,
                "source": func_source,
                "args": [a.arg for a in node.args.args if a.arg != 'self'],
            })

    return functions


# ---------------------------------------------------------------------------
# Step 2: Holden digests a function into a semantic summary
# ---------------------------------------------------------------------------
def holden_digest(func: Dict) -> Dict:
    """Holden reads one function and produces a structured digest.

    Returns a dict with 'risk' (what Mirus investigates) and 'guards' (held back for validation).
    """
    try:
        # Truncate source for very large functions to stay under CLI limits
        func_source = func['source']
        if len(func_source) > 8000:
            half = 3500
            func_source = func_source[:half] + f"\n\n... [{len(func['source'])} chars total, middle truncated] ...\n\n" + func_source[-half:]

        prompt = (
            f"Read this Python function and produce a COMPACT digest (max 6 lines):\n\n"
            f"```python\n{func_source}\n```\n\n"
            f"Format (use these EXACT labels):\n"
            f"FUNCTION: {func['class']}.{func['name']}({', '.join(func['args'])})\n"
            f"DOES: [one sentence — what it does]\n"
            f"GUARDS: [list every defensive check: null checks, try/except, validation, bounds checks]\n"
            f"RISK: [one sentence — what could go wrong that ISN'T already guarded]\n\n"
            f"Be precise. If there are no unguarded risks, say 'RISK: none identified'.\n"
            f"List EVERY guard you find — this is critical for avoiding false positives."
        )

        # Pipe prompt via stdin to avoid WinError 206 on large functions
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "-", "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=90,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )

        raw = result.stdout.strip() if result.returncode == 0 else ""
        if not raw:
            return {"raw": f"Digest failed for {func['name']}", "risk": "", "guards": ""}

        # Parse out RISK and GUARDS separately
        risk = ""
        guards = ""
        for line in raw.split("\n"):
            if line.strip().startswith("RISK:"):
                risk = line.split("RISK:", 1)[1].strip()
            elif line.strip().startswith("GUARDS:"):
                guards = line.split("GUARDS:", 1)[1].strip()

        return {"raw": raw, "risk": risk, "guards": guards}
    except Exception as e:
        return {"raw": f"Digest failed for {func['name']}: {e}", "risk": "", "guards": ""}


# ---------------------------------------------------------------------------
# Step 3: Mirus audits ONE function with its digest + source
# ---------------------------------------------------------------------------
async def mirus_audit_function(session, func: Dict, digest: Dict,
                                prior_findings: List[str]) -> str:
    """Mirus audits a single function. Gets the RISK claim, must verify it."""

    history = ""
    if prior_findings:
        history = "YOUR PRIOR FINDINGS (don't repeat these):\n"
        for f in prior_findings[-5:]:
            history += f"  - {f}\n"

    risk = digest.get("risk", "")

    if risk and risk.lower() != "none identified":
        # Holden identified a risk — challenge Mirus to verify it
        prompt = (
            f"A senior auditor reviewed this function and flagged a potential risk:\n\n"
            f"CLAIMED RISK: {risk}\n\n"
            f"SOURCE CODE:\n```python\n{func['source']}\n```\n\n"
            f"File: {func['file']}, lines {func['start_line']}-{func['end_line']}\n\n"
            f"{history}\n"
            f"YOUR JOB: Read the source code and determine if this risk is REAL.\n\n"
            f"1. Find the specific line(s) relevant to this risk\n"
            f"2. Check: is there existing code that ALREADY handles this case?\n"
            f"3. If the risk IS real and unguarded, report:\n"
            f"   REAL: [what the bug is]\n"
            f"   LINE: [approximate line number]\n"
            f"   SEVERITY: critical/high/medium/low\n"
            f"   FIX: [one line of code]\n"
            f"4. If the code ALREADY handles it, report:\n"
            f"   GUARDED: [which line/mechanism handles it]\n\n"
            f"Also report any OTHER issue you notice in the source."
        )
    else:
        # No specific risk — open-ended audit of short function
        prompt = (
            f"Review this function for bugs, security issues, or reliability problems:\n\n"
            f"SOURCE CODE:\n```python\n{func['source']}\n```\n\n"
            f"File: {func['file']}, lines {func['start_line']}-{func['end_line']}\n\n"
            f"{history}\n"
            f"Report any real issue you find, or say NO ISSUES FOUND if the code is solid."
        )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": (
            "You are verifying a specific risk claim about a Python function. "
            "Read the actual source code carefully. Determine if the risk is real "
            "by finding whether existing code handles the case or not. "
            "Be specific — cite line numbers and code."
        ),
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 400, "num_ctx": 4096},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()
    return data.get("response", "")


# ---------------------------------------------------------------------------
# Step 4: Holden validates — is this finding real?
# ---------------------------------------------------------------------------
def holden_validate(func: Dict, finding: str) -> Dict:
    """Holden checks whether Mirus's finding is real against the actual source."""
    prompt = (
        f"A 3B model audited this function and reported:\n\n"
        f"FINDING:\n{finding}\n\n"
        f"ACTUAL SOURCE:\n```python\n{func['source']}\n```\n\n"
        f"Is this finding REAL or a FALSE POSITIVE?\n"
        f"If false positive, explain which guard already handles it.\n"
        f"If real, rate severity.\n\n"
        f"Format:\n"
        f"VERDICT: real | false_positive\n"
        f"SEVERITY: critical/high/medium/low/n-a\n"
        f"EXPLANATION: one sentence"
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "-", "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=60,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        output = result.stdout.strip() if result.returncode == 0 else ""
    except:
        output = ""

    verdict = "unknown"
    severity = "unknown"
    for line in output.split("\n"):
        if line.strip().startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().lower()
        elif line.strip().startswith("SEVERITY:"):
            severity = line.split(":", 1)[1].strip().lower()

    is_real = "real" in verdict and "false" not in verdict
    return {
        "verdict": verdict,
        "severity": severity,
        "is_real": is_real,
        "explanation": output[:500],
    }


# ---------------------------------------------------------------------------
# Main: Holden steers, Mirus audits, function by function
# ---------------------------------------------------------------------------
async def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("CHUNKED AUDIT: Holden-as-attention-pointer")
    p("=" * 60)
    p(f"Auditor: {MIRUS_MODEL} (3B)")
    p(f"Validator: claude-sonnet-4-6")
    p(f"Method: AST chunking + digest + per-function audit")
    p("=" * 60)

    # Extract all functions
    all_functions = []
    for filepath in SOURCE_FILES:
        funcs = extract_functions(filepath)
        all_functions.extend(funcs)
        p(f"\n  {os.path.basename(filepath)}: {len(funcs)} functions extracted")

    p(f"\n  Total functions to audit: {len(all_functions)}")

    # Filter: skip tiny functions (< 5 lines) — getters, one-liners
    audit_targets = [f for f in all_functions if f["line_count"] >= 5]
    p(f"  After filtering (<5 lines): {len(audit_targets)} functions")

    # Sort by size descending — audit the complex ones first
    audit_targets.sort(key=lambda f: f["line_count"], reverse=True)

    findings = []
    real_bugs = []
    false_positives = []
    no_issues = []

    async with aiohttp.ClientSession() as session:
        for i, func in enumerate(audit_targets):
            p(f"\n{'='*50}")
            p(f"FUNCTION {i+1}/{len(audit_targets)}: {func['class']}.{func['name']}")
            p(f"  File: {func['file']} lines {func['start_line']}-{func['end_line']} ({func['line_count']} lines)")
            p(f"{'='*50}")

            # Holden digests
            p(f"\n  [HOLDEN] Digesting...")
            t0 = time.time()
            digest = holden_digest(func)
            digest_time = time.time() - t0
            p(f"  [HOLDEN] ({digest_time:.1f}s) Digest:")
            for line in digest["raw"].split("\n")[:6]:
                p(f"    {line}")
            if digest["risk"]:
                p(f"  [HOLDEN] RISK → {digest['risk'][:150]}")

            # Mirus audits with digest
            p(f"\n  [MIRUS] Auditing...")
            t0 = time.time()
            prior = [f["summary"] for f in findings if f.get("is_real")]
            finding = await mirus_audit_function(session, func, digest, prior)
            audit_time = time.time() - t0
            p(f"  [MIRUS] ({audit_time:.1f}s):")
            for line in finding.split("\n")[:8]:
                p(f"    {line}")

            # Check if Mirus said "no issues" or "guarded"
            finding_lower = finding.lower()
            is_guarded = "guarded:" in finding_lower
            is_clean = ("no issues" in finding_lower or "no issue" in finding_lower
                or "guards are sufficient" in finding_lower
                or "looks correct" in finding_lower
                or "no bug" in finding_lower)

            if is_clean and not is_guarded:
                p(f"\n  [RESULT] No issues found — moving on")
                no_issues.append(func["name"])
                log({
                    "function": f"{func['class']}.{func['name']}",
                    "file": func["file"],
                    "lines": f"{func['start_line']}-{func['end_line']}",
                    "digest": digest["raw"][:500],
                    "finding": "no_issues",
                    "verdict": "clean",
                })
                continue

            if is_guarded and "real:" not in finding_lower and "other" not in finding_lower:
                p(f"\n  [RESULT] Risk verified as GUARDED — moving on")
                no_issues.append(func["name"])
                log({
                    "function": f"{func['class']}.{func['name']}",
                    "file": func["file"],
                    "lines": f"{func['start_line']}-{func['end_line']}",
                    "digest": digest["raw"][:500],
                    "finding": finding[:500],
                    "verdict": "guarded",
                })
                continue

            # Holden validates
            p(f"\n  [HOLDEN] Validating...")
            t0 = time.time()
            validation = holden_validate(func, finding)
            val_time = time.time() - t0

            if validation["is_real"]:
                p(f"  [HOLDEN] ({val_time:.1f}s): REAL BUG [{validation['severity']}]")
                real_bugs.append({
                    "function": f"{func['class']}.{func['name']}",
                    "file": func["file"],
                    "finding": finding[:200],
                    "severity": validation["severity"],
                })
            else:
                p(f"  [HOLDEN] ({val_time:.1f}s): FALSE POSITIVE")
                false_positives.append({
                    "function": f"{func['class']}.{func['name']}",
                    "finding": finding[:200],
                })

            for line in validation["explanation"].split("\n")[:4]:
                p(f"    {line}")

            finding_record = {
                "function": f"{func['class']}.{func['name']}",
                "file": func["file"],
                "lines": f"{func['start_line']}-{func['end_line']}",
                "summary": finding[:200],
                "digest": digest["raw"][:500],
                "finding": finding[:1000],
                "verdict": validation["verdict"],
                "severity": validation["severity"],
                "is_real": validation["is_real"],
            }
            findings.append(finding_record)
            log(finding_record)

    # Summary
    p(f"\n{'='*60}")
    p("CHUNKED AUDIT RESULTS")
    p(f"{'='*60}")
    p(f"  Functions audited: {len(audit_targets)}")
    p(f"  Clean / guarded: {len(no_issues)}")
    p(f"  Findings reported: {len(findings)}")
    p(f"  Real bugs: {len(real_bugs)}")
    p(f"  False positives: {len(false_positives)}")

    if no_issues:
        p(f"\n  CLEAN FUNCTIONS:")
        for name in no_issues:
            p(f"    - {name}")

    if real_bugs:
        p(f"\n  CONFIRMED BUGS:")
        for i, bug in enumerate(real_bugs):
            p(f"    {i+1}. [{bug['severity']}] {bug['function']}: {bug['finding'][:100]}")

    if false_positives:
        p(f"\n  FALSE POSITIVES:")
        for i, fp in enumerate(false_positives):
            p(f"    {i+1}. {fp['function']}: {fp['finding'][:100]}")

    # The key metric
    total_with_findings = len(real_bugs) + len(false_positives)
    if total_with_findings > 0:
        precision = len(real_bugs) / total_with_findings * 100
        p(f"\n  PRECISION: {precision:.0f}% ({len(real_bugs)}/{total_with_findings} findings were real)")
    else:
        p(f"\n  PRECISION: N/A (no findings reported)")

    p(f"\n  COMPARISON:")
    p(f"    Old audit (dump all): 0/20 real (0% precision)")
    p(f"    Chunked audit:        {len(real_bugs)}/{total_with_findings} real")

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
