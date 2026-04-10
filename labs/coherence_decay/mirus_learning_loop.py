"""Mirus Learning Loop — Real Attempt-Learn-Retry Cycle

Each epoch:
1. Mirus (llama3.2) attempts a challenge via Ollama
2. Result is evaluated
3. If failed: Holden (Claude) provides the correction
4. The correction is added to Mirus's "learned knowledge" system prompt
5. Mirus retries WITH the accumulated lessons in its context

This is in-context learning — the model's effective knowledge grows
with each epoch because successful solutions become part of its prompt.

For true weight-level learning, the epoch log becomes LoRA training data
to be run on the TPU when available.
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MIRUS_MODEL = "llama3.2:latest"
CLAUDE_CLI = os.getenv(
    "CLAUDE_CODE_EXECPATH",
    r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
)
MAX_EPOCHS = 10
LOG_FILE = Path(__file__).parent / "results" / "raw" / "learning_loop.jsonl"


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Challenges — multiple, increasing difficulty
# ---------------------------------------------------------------------------
CHALLENGES = [
    {
        "id": "reverse_no_slice",
        "name": "Reverse a string without slicing",
        "prompt": "Write a Python function reverse_string(s) that reverses a string WITHOUT using slicing (no s[::-1]). Use only loops or recursion.",
        "test_code": """
result = reverse_string("hello")
assert result == "olleh", f"Expected 'olleh', got '{result}'"
result2 = reverse_string("")
assert result2 == "", f"Expected '', got '{result2}'"
result3 = reverse_string("a")
assert result3 == "a", f"Expected 'a', got '{result3}'"
print("ALL TESTS PASSED")
""",
        "verify": lambda output: "ALL TESTS PASSED" in output,
    },
    {
        "id": "flatten_nested",
        "name": "Flatten arbitrarily nested list",
        "prompt": "Write a Python function flatten(lst) that takes an arbitrarily nested list and returns a flat list. Example: flatten([1, [2, [3, 4], 5], 6]) returns [1, 2, 3, 4, 5, 6].",
        "test_code": """
assert flatten([1, [2, [3, 4], 5], 6]) == [1, 2, 3, 4, 5, 6]
assert flatten([]) == []
assert flatten([1, 2, 3]) == [1, 2, 3]
assert flatten([[[[1]]]]) == [1]
assert flatten([1, [2], [3, [4, [5]]]]) == [1, 2, 3, 4, 5]
print("ALL TESTS PASSED")
""",
        "verify": lambda output: "ALL TESTS PASSED" in output,
    },
    {
        "id": "lru_cache",
        "name": "Implement LRU Cache",
        "prompt": "Write a Python class LRUCache with methods get(key) and put(key, value). It should have a max capacity set in __init__. When capacity is exceeded, evict the least recently used item. get() returns -1 if key not found. Both get and put should be O(1).",
        "test_code": """
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
cache.put(4, 4)
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4
print("ALL TESTS PASSED")
""",
        "verify": lambda output: "ALL TESTS PASSED" in output,
    },
]


# ---------------------------------------------------------------------------
# Sandbox execution
# ---------------------------------------------------------------------------
def run_code(code: str, test_code: str) -> dict:
    """Execute the model's code + test assertions."""
    full_code = code + "\n\n" + test_code

    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(full_code)
            tmp = f.name

        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=10,
        )
        Path(tmp).unlink(missing_ok=True)

        output = result.stdout + result.stderr
        return {
            "success": result.returncode == 0,
            "output": output[:2000],
            "passed": "ALL TESTS PASSED" in output,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "TIMEOUT", "passed": False}
    except Exception as e:
        return {"success": False, "output": str(e), "passed": False}


def clean_code(text):
    code = text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(l for l in lines if not l.startswith("```"))
    return code


# ---------------------------------------------------------------------------
# Mirus — generate with accumulated lessons
# ---------------------------------------------------------------------------
async def mirus_generate(session, challenge, learned_lessons, epoch):
    """Mirus generates code, with all learned lessons in system prompt."""

    # Build accumulated knowledge into system prompt
    if learned_lessons:
        lessons_text = "\n\n".join([
            f"LESSON {i+1} ({l['challenge']}):\n"
            f"What I tried: {l['wrong_approach'][:100]}\n"
            f"What went wrong: {l['error'][:100]}\n"
            f"Correct approach: {l['correct_approach'][:200]}"
            for i, l in enumerate(learned_lessons)
        ])
        system = (
            f"You are an expert Python programmer. "
            f"You have learned from previous mistakes:\n\n{lessons_text}\n\n"
            f"Apply these lessons. Output ONLY Python code. No explanation. No markdown."
        )
    else:
        system = "You are an expert Python programmer. Output ONLY Python code. No explanation. No markdown."

    payload = {
        "model": MIRUS_MODEL,
        "prompt": challenge["prompt"] + "\n\nOutput ONLY the Python code. No explanation.",
        "system": system,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 400, "num_ctx": 4096},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()

    return clean_code(data.get("response", ""))


# ---------------------------------------------------------------------------
# Holden — analyze and teach
# ---------------------------------------------------------------------------
def holden_teach(challenge, mirus_code, error_output):
    """Holden provides the correction as a lesson."""

    prompt = (
        f"A small model tried to solve this challenge and failed:\n\n"
        f"CHALLENGE: {challenge['prompt']}\n\n"
        f"MODEL'S CODE:\n{mirus_code[:500]}\n\n"
        f"ERROR:\n{error_output[:500]}\n\n"
        f"Provide:\n"
        f"1. What the model did wrong (1 sentence)\n"
        f"2. The correct working code\n"
        f"3. The key lesson (1 sentence)\n\n"
        f"Format as:\nWRONG: ...\nCODE:\n...\nLESSON: ..."
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except:
        return None


def parse_holden_response(response):
    """Extract lesson components from Holden's teaching."""
    wrong = ""
    code = ""
    lesson = ""

    lines = response.split("\n")
    mode = None
    code_lines = []

    for line in lines:
        if line.startswith("WRONG:"):
            wrong = line[6:].strip()
            mode = "wrong"
        elif line.startswith("CODE:"):
            mode = "code"
        elif line.startswith("LESSON:"):
            lesson = line[7:].strip()
            mode = "lesson"
        elif mode == "code":
            code_lines.append(line)
        elif mode == "lesson":
            lesson += " " + line.strip()

    code = "\n".join(code_lines).strip()
    code = clean_code(code)

    return {"wrong": wrong, "code": code, "lesson": lesson}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("MIRUS LEARNING LOOP")
    p("=" * 60)
    p(f"Mirus: {MIRUS_MODEL}")
    p(f"Holden: claude-sonnet-4-6")
    p(f"Challenges: {len(CHALLENGES)}")
    p("=" * 60)

    learned_lessons = []  # Accumulates across ALL challenges
    total_stats = {"mirus_solo": 0, "mirus_coached": 0, "holden_solved": 0}

    async with aiohttp.ClientSession() as session:
        for challenge in CHALLENGES:
            p(f"\n{'='*50}")
            p(f"CHALLENGE: {challenge['name']}")
            p(f"{'='*50}")

            solved = False
            challenge_epochs = 0

            for epoch in range(MAX_EPOCHS):
                challenge_epochs += 1
                who = "mirus" if not learned_lessons or epoch == 0 else "mirus+lessons"

                p(f"\n  --- Epoch {epoch+1} [{who}] ---")

                # Mirus generates
                p(f"  [MIRUS] Generating...")
                t0 = time.time()
                code = await mirus_generate(session, challenge, learned_lessons, epoch)
                gen_time = time.time() - t0

                p(f"  [MIRUS] Code ({gen_time:.1f}s):")
                for line in code.split("\n")[:12]:
                    p(f"    {line}")

                # Test it
                result = run_code(code, challenge["test_code"])
                p(f"  [TEST] Passed: {result['passed']}")
                if not result['passed']:
                    p(f"  [TEST] Output: {result['output'][:200]}")

                log({
                    "challenge": challenge["id"],
                    "epoch": epoch + 1,
                    "who": who,
                    "code": code[:500],
                    "passed": result["passed"],
                    "output": result["output"][:500],
                    "time_s": round(gen_time, 1),
                    "lessons_count": len(learned_lessons),
                })

                if result["passed"]:
                    if epoch == 0 and not learned_lessons:
                        total_stats["mirus_solo"] += 1
                        p(f"  >>> MIRUS SOLVED IT SOLO on epoch {epoch+1}!")
                    else:
                        total_stats["mirus_coached"] += 1
                        p(f"  >>> MIRUS SOLVED IT (coached) on epoch {epoch+1}!")
                    solved = True
                    break

                # Holden teaches
                if epoch < MAX_EPOCHS - 1:
                    p(f"\n  [HOLDEN] Teaching...")
                    t0 = time.time()
                    teaching = holden_teach(challenge, code, result["output"])
                    teach_time = time.time() - t0

                    if teaching:
                        parsed = parse_holden_response(teaching)
                        p(f"  [HOLDEN] ({teach_time:.1f}s):")
                        p(f"    Wrong: {parsed['wrong'][:100]}")
                        p(f"    Lesson: {parsed['lesson'][:100]}")

                        # Verify Holden's code works
                        if parsed["code"]:
                            holden_result = run_code(parsed["code"], challenge["test_code"])
                            if holden_result["passed"]:
                                p(f"  [HOLDEN] Verified: code passes tests")

                                # ADD TO LEARNED LESSONS
                                learned_lessons.append({
                                    "challenge": challenge["name"],
                                    "wrong_approach": code[:200],
                                    "error": result["output"][:200],
                                    "correct_approach": parsed["code"][:300],
                                    "lesson": parsed["lesson"],
                                })
                                p(f"  [LEARN] Lesson #{len(learned_lessons)} added to memory")

                                log({
                                    "challenge": challenge["id"],
                                    "epoch": epoch + 1,
                                    "who": "holden",
                                    "type": "lesson",
                                    "lesson": parsed["lesson"],
                                })
                            else:
                                p(f"  [HOLDEN] Code failed verification: {holden_result['output'][:100]}")
                    else:
                        p(f"  [HOLDEN] No response")

            if not solved:
                total_stats["holden_solved"] += 1
                p(f"  >>> MIRUS FAILED after {challenge_epochs} epochs")

    # Summary
    p(f"\n{'='*60}")
    p("LEARNING LOOP COMPLETE")
    p(f"{'='*60}")
    p(f"  Challenges: {len(CHALLENGES)}")
    p(f"  Mirus solved solo: {total_stats['mirus_solo']}")
    p(f"  Mirus solved coached: {total_stats['mirus_coached']}")
    p(f"  Mirus failed: {total_stats['holden_solved']}")
    p(f"  Total lessons learned: {len(learned_lessons)}")
    p(f"  Log: {LOG_FILE}")

    # Save training data
    train_file = LOG_FILE.parent / "learning_loop_training.json"
    with open(train_file, "w") as f:
        json.dump({
            "lessons": learned_lessons,
            "stats": total_stats,
        }, f, indent=2)
    p(f"  Training data: {train_file}")


if __name__ == "__main__":
    asyncio.run(run())
