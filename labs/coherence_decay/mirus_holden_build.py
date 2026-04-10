"""Mirus/Holden Build Challenge — Route Stability Classifier

Mirus (local 3B) writes a real component from spec.
Tests verify correctness. Holden coaches on failures.
The output is a working route_classifier.py.
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
from generate import ollama_generate

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLAUDE_CLI = os.getenv(
    "CLAUDE_CODE_EXECPATH",
    r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
)
MAX_EPOCHS = 8
MIRUS_MODEL = "llama3.2:latest"

SPEC_FILE = Path(__file__).parent / "route_stability_spec.md"
TEST_FILE = Path(__file__).parent / "test_route_classifier.py"
OUTPUT_FILE = Path(__file__).parent / "route_classifier.py"
LOG_FILE = Path(__file__).parent / "results" / "raw" / "mirus_holden_build.jsonl"


def p(msg: str):
    print(msg, flush=True)


def log(entry: dict):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def clean_code(text: str) -> str:
    code = text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(l for l in lines if not l.startswith("```"))
    return code


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------
def run_tests() -> dict:
    """Run the test suite and capture results."""
    try:
        result = subprocess.run(
            [sys.executable, str(TEST_FILE)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent),
        )
        output = result.stdout + result.stderr

        # Count passes/fails
        passes = output.count("PASS:")
        fails = output.count("FAIL:")

        return {
            "passed": passes,
            "failed": fails,
            "all_passed": fails == 0 and passes > 0,
            "output": output[:3000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": -1, "all_passed": False,
                "output": "TIMEOUT", "returncode": -1}
    except Exception as e:
        return {"passed": 0, "failed": -1, "all_passed": False,
                "output": str(e), "returncode": -1}


# ---------------------------------------------------------------------------
# Mirus — write the code
# ---------------------------------------------------------------------------
async def mirus_write(session, epoch: int, epoch_log: list,
                      holden_advice: str = "") -> str:
    """Mirus generates the route_classifier.py code."""

    spec = SPEC_FILE.read_text()

    if epoch == 0:
        prompt = (
            f"Write a Python module called route_classifier.py based on this spec:\n\n"
            f"{spec}\n\n"
            f"Output ONLY the complete Python file. No explanation. No markdown fences.\n"
            f"Start with the function definition. Include all classification logic."
        )
    elif holden_advice:
        history = "\n".join([
            f"Epoch {e['epoch']}: {e['passed']}P/{e['failed']}F - {e['lesson']}"
            for e in epoch_log
        ])
        prompt = (
            f"TASK: Fix route_classifier.py\n\n"
            f"SPEC:\n{spec}\n\n"
            f"YOUR PREVIOUS ATTEMPTS:\n{history}\n\n"
            f"TEACHER'S ADVICE:\n{holden_advice}\n\n"
            f"Write the COMPLETE FIXED route_classifier.py. "
            f"Follow the teacher's advice precisely. Output ONLY Python code."
        )
    else:
        history = "\n".join([
            f"Epoch {e['epoch']}: {e['passed']}P/{e['failed']}F - {e['lesson']}"
            for e in epoch_log
        ])
        last_test_output = epoch_log[-1]["test_output"][:800] if epoch_log else ""
        prompt = (
            f"TASK: Fix route_classifier.py\n\n"
            f"SPEC:\n{spec}\n\n"
            f"ATTEMPT HISTORY:\n{history}\n\n"
            f"LATEST TEST OUTPUT:\n{last_test_output}\n\n"
            f"Fix the failing tests. Write the COMPLETE route_classifier.py. "
            f"Output ONLY Python code. No explanation."
        )

    text, _ = await ollama_generate(
        session, MIRUS_MODEL, prompt,
        "You are an expert Python developer. Output ONLY complete, working Python code. No markdown. No explanation.",
        max_tokens=800,
    )

    return clean_code(text)


# ---------------------------------------------------------------------------
# Holden — coach on failures
# ---------------------------------------------------------------------------
def holden_coach(epoch_log: list, latest_code: str, test_output: str) -> str:
    """Holden analyzes test failures and coaches Mirus."""

    spec = SPEC_FILE.read_text()
    history = "\n".join([
        f"Epoch {e['epoch']}: {e['passed']}P/{e['failed']}F - {e['lesson']}"
        for e in epoch_log
    ])

    prompt = (
        f"You are Holden, a teacher helping a 3B model (Mirus) write correct code.\n\n"
        f"SPEC:\n{spec}\n\n"
        f"MIRUS'S LATEST CODE:\n{latest_code[:1000]}\n\n"
        f"TEST RESULTS:\n{test_output[:1500]}\n\n"
        f"ATTEMPT HISTORY:\n{history}\n\n"
        f"Analyze the failing tests. Give SPECIFIC advice:\n"
        f"1. Which tests fail and why\n"
        f"2. What logic errors exist in Mirus's code\n"
        f"3. Give corrected code SNIPPETS (not full file) for the broken parts\n"
        f"4. Explain the fix clearly so Mirus can apply it\n\n"
        f"Be a teacher. Show the fix for each failing test."
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        if result.returncode != 0:
            return f"Holden error: {result.stderr[:200]}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Holden timeout."
    except Exception as e:
        return f"Holden error: {e}"


def holden_solve(spec_text: str) -> str:
    """Holden writes the solution directly (last resort training data)."""

    prompt = (
        f"Write a complete Python module route_classifier.py based on this spec:\n\n"
        f"{spec_text}\n\n"
        f"Output ONLY the complete Python file. No explanation. No markdown fences."
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        return clean_code(result.stdout.strip()) if result.returncode == 0 else ""
    except:
        return ""


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def run():
    # Clear old log
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    epoch_log = []
    holden_advice = ""
    holden_interventions = 0

    p("=" * 60)
    p("MIRUS/HOLDEN BUILD CHALLENGE")
    p("Task: Route Stability Classifier")
    p("=" * 60)
    p(f"Mirus: {MIRUS_MODEL} (local 3B)")
    p(f"Holden: claude-sonnet-4-6 (cloud)")
    p(f"Tests: {TEST_FILE}")
    p(f"Output: {OUTPUT_FILE}")
    p(f"Max epochs: {MAX_EPOCHS}")
    p("=" * 60)

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EPOCHS):
            p(f"\n{'='*50}")
            p(f"EPOCH {epoch + 1}")
            p(f"{'='*50}")

            # --- MIRUS WRITES CODE ---
            p(f"\n  [MIRUS] Writing route_classifier.py...")
            t0 = time.time()
            code = await mirus_write(session, epoch, epoch_log, holden_advice)
            mirus_time = time.time() - t0

            p(f"  [MIRUS] Generated ({mirus_time:.1f}s, {len(code)} chars):")
            for line in code.split("\n")[:20]:
                p(f"    {line}")
            if len(code.split("\n")) > 20:
                p(f"    ... ({len(code.split(chr(10)))} lines total)")

            # Save the code
            OUTPUT_FILE.write_text(code)

            # --- RUN TESTS ---
            p(f"\n  [TESTS] Running test suite...")
            test_result = run_tests()

            p(f"  [TESTS] Passed: {test_result['passed']}, Failed: {test_result['failed']}")
            # Show test output
            for line in test_result['output'].split("\n"):
                if "FAIL:" in line or "PASS:" in line or "RESULTS:" in line or "ERROR" in line:
                    p(f"    {line}")

            # --- LOG ---
            if test_result["all_passed"]:
                lesson = f"ALL TESTS PASSED! {test_result['passed']}/{test_result['passed']}"
            elif test_result["failed"] == -1:
                lesson = f"Code crashed: {test_result['output'][:100]}"
            else:
                lesson = f"{test_result['passed']}P/{test_result['failed']}F"

            entry = {
                "epoch": epoch + 1,
                "who": "mirus+holden" if holden_advice else "mirus",
                "code_length": len(code),
                "passed": test_result["passed"],
                "failed": test_result["failed"],
                "all_passed": test_result["all_passed"],
                "lesson": lesson,
                "test_output": test_result["output"][:2000],
                "time_s": round(mirus_time, 1),
            }
            epoch_log.append(entry)
            log(entry)

            p(f"\n  [LOG] Epoch {epoch+1}: {lesson}")

            if test_result["all_passed"]:
                p(f"\n{'='*50}")
                p(f"MIRUS PASSED ALL TESTS ON EPOCH {epoch + 1}!")
                p(f"Holden interventions: {holden_interventions}")
                p(f"Output: {OUTPUT_FILE}")
                p(f"{'='*50}")
                break

            # --- HOLDEN COACHES ---
            should_coach = (
                (epoch + 1) % 2 == 0
                or epoch >= 2
                or test_result["failed"] == -1  # Code crashed, needs help
            )

            if should_coach:
                p(f"\n  [HOLDEN] Analyzing failures...")
                t0 = time.time()
                holden_advice = holden_coach(epoch_log, code, test_result["output"])
                holden_time = time.time() - t0
                holden_interventions += 1

                p(f"  [HOLDEN] Coaching ({holden_time:.1f}s):")
                for line in holden_advice.split("\n")[:15]:
                    p(f"    {line}")
                if len(holden_advice.split("\n")) > 15:
                    p(f"    ... (truncated)")

                log({"epoch": epoch + 1, "who": "holden", "type": "coaching",
                     "advice": holden_advice[:2000], "time_s": round(holden_time, 1)})
            else:
                holden_advice = ""
                p(f"\n  [HOLDEN] Watching. Mirus tries alone next epoch.")

        else:
            # Mirus couldn't pass all tests
            p(f"\n{'='*50}")
            p(f"MIRUS FAILED AFTER {MAX_EPOCHS} EPOCHS")
            p(f"{'='*50}")

            p(f"\n  [HOLDEN] Writing solution directly...")
            holden_code = holden_solve(SPEC_FILE.read_text())
            if holden_code:
                OUTPUT_FILE.write_text(holden_code)
                test_result = run_tests()
                p(f"  [HOLDEN] Solution: {test_result['passed']}P/{test_result['failed']}F")

                log({"epoch": "final", "who": "holden", "type": "solution",
                     "passed": test_result["passed"], "failed": test_result["failed"]})

    # Summary
    p(f"\n{'='*50}")
    p("BUILD CHALLENGE COMPLETE")
    p(f"{'='*50}")
    p(f"  Total epochs: {len(epoch_log)}")
    p(f"  Holden interventions: {holden_interventions}")
    best = max(epoch_log, key=lambda e: e["passed"])
    p(f"  Best result: {best['passed']}P/{best['failed']}F (epoch {best['epoch']})")
    p(f"  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
