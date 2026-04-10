"""Hard Bug Challenge: The Symptom Lies

The symptom: memory trust scores slowly degrade over time.
User reports: "Aether is forgetting things it used to know well."

The OBVIOUS diagnosis: decay function is too aggressive.
The OBVIOUS fix: reduce decay rate.

The REAL bug: the dedup function runs on every memory save.
It finds "similar" memories (cosine > 0.85) and merges them.
When it merges, it AVERAGES the trust scores. But one of the
"similar" memories is always the user's latest correction at
trust=0.15 (new, unverified). So every merge DRAGS DOWN the
trust of the established memory.

The correction path creates a new low-trust memory -> dedup
finds the existing high-trust memory -> merges them -> trust
drops from 0.9 to 0.525 -> next correction does it again ->
trust drops to 0.34 -> eventually the memory is untrusted.

The fix: dedup should use MAX(trust) not AVERAGE when merging.
Or: new corrections should update existing memories, not create
new entries that trigger dedup.

This requires tracing through 4 files to find the interaction.
The decay function is a red herring — it's working correctly.
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
MAX_EXPLORE = 12
LOG_FILE = Path(__file__).parent / "results" / "raw" / "hard_bug.jsonl"
WORKSPACE = Path(__file__).parent / "results" / "challenges" / "hard_bug"


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Setup: create the buggy codebase
# ---------------------------------------------------------------------------
def setup():
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    # memory_store.py — stores memories with trust scores
    with _real_open(WORKSPACE / "memory_store.py", "w") as f:
        f.write('''"""Memory Store — persists memories with trust scores."""
import json
import time
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def load_memories():
    if MEMORY_DB.exists():
        with open(MEMORY_DB) as f:
            return json.load(f)
    return []

def save_memory(text, trust=0.15, source="user"):
    """Save a new memory. New memories start at trust=0.15 (unverified)."""
    memories = load_memories()
    memory = {
        "id": len(memories) + 1,
        "text": text,
        "trust": trust,
        "source": source,
        "created": time.time(),
        "last_accessed": time.time(),
    }
    memories.append(memory)

    # Run dedup after every save
    from dedup import deduplicate_memories
    memories = deduplicate_memories(memories)

    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)
    return memory

def get_memory(text):
    """Find a memory by text similarity (simplified: exact match)."""
    memories = load_memories()
    for m in memories:
        if text.lower() in m["text"].lower() or m["text"].lower() in text.lower():
            return m
    return None

def update_trust(memory_id, new_trust):
    """Update a memory's trust score."""
    memories = load_memories()
    for m in memories:
        if m["id"] == memory_id:
            m["trust"] = new_trust
            m["last_accessed"] = time.time()
    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)
''')

    # dedup.py — THE BUG IS HERE
    with _real_open(WORKSPACE / "dedup.py", "w") as f:
        f.write('''"""Memory Deduplication — merges similar memories."""

def cosine_similarity(a, b):
    """Simplified: word overlap ratio as similarity proxy."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    total = len(words_a | words_b)
    return overlap / total

def deduplicate_memories(memories, threshold=0.85):
    """Find and merge similar memories.

    When two memories are similar enough (cosine > threshold),
    merge them into one to prevent bloat.
    """
    if len(memories) < 2:
        return memories

    merged = []
    skip = set()

    for i, mem_a in enumerate(memories):
        if i in skip:
            continue

        for j, mem_b in enumerate(memories):
            if j <= i or j in skip:
                continue

            sim = cosine_similarity(mem_a["text"], mem_b["text"])
            if sim >= threshold:
                # Merge: keep the text of the higher-trust one,
                # but AVERAGE the trust scores
                if mem_a["trust"] >= mem_b["trust"]:
                    merged_mem = {**mem_a}
                else:
                    merged_mem = {**mem_b}

                # BUG: averaging drags down trust when one memory
                # is a new low-trust correction (0.15) and the other
                # is an established high-trust fact (0.9)
                # Result: 0.9 + 0.15 / 2 = 0.525 — trust destroyed
                merged_mem["trust"] = (mem_a["trust"] + mem_b["trust"]) / 2

                merged.append(merged_mem)
                skip.add(i)
                skip.add(j)
                break

        if i not in skip:
            merged.append(mem_a)

    return merged
''')

    # decay.py — RED HERRING (works correctly)
    with _real_open(WORKSPACE / "decay.py", "w") as f:
        f.write('''"""Trust Decay — gradually reduces trust of unaccessed memories."""
import time

def apply_decay(memories, decay_rate=0.01, min_trust=0.05):
    """Apply time-based trust decay.

    Memories that haven't been accessed recently lose trust slowly.
    This is WORKING CORRECTLY — decay rate is conservative and only
    affects memories not accessed in the last 24 hours.
    """
    now = time.time()
    one_day = 86400

    for mem in memories:
        time_since_access = now - mem.get("last_accessed", now)
        if time_since_access > one_day:
            # Decay 1% per day — very conservative
            days_inactive = time_since_access / one_day
            decay_amount = decay_rate * days_inactive
            mem["trust"] = max(min_trust, mem["trust"] - decay_amount)

    return memories
''')

    # correction_handler.py — processes user corrections
    with _real_open(WORKSPACE / "correction_handler.py", "w") as f:
        f.write('''"""Correction Handler — processes user corrections to memory."""
from memory_store import save_memory, get_memory

def handle_correction(original_text, corrected_text):
    """User corrects a fact. Save the correction as a new memory.

    The correction is saved as a NEW memory with low trust (0.15)
    because it hasn't been verified yet. This is correct behavior.

    However, this creates a problem: the new memory is very similar
    to the existing one (it's a correction of the same fact).
    When save_memory runs, it triggers dedup, which merges the new
    low-trust correction with the old high-trust memory...
    """
    existing = get_memory(original_text)

    # Save correction as new memory (trust=0.15, unverified)
    new_mem = save_memory(
        text=corrected_text,
        trust=0.15,
        source="user_correction",
    )

    return {
        "status": "corrected",
        "old": existing,
        "new": new_mem,
    }
''')

    # The symptom log
    with _real_open(WORKSPACE / "symptom.log", "w") as f:
        f.write('''USER REPORT: "Aether keeps forgetting things"

Timeline of trust scores for memory "Nick lives in Milwaukee":

Day 1: User tells Aether "I live in Milwaukee"
  -> Memory created: trust=0.15
  -> User confirms: trust promoted to 0.90

Day 3: User says "I live in Milwaukee, Wisconsin" (correction/elaboration)
  -> Trust was 0.90... now showing 0.525 ???

Day 5: User says "I live near the lake in Milwaukee" (another elaboration)
  -> Trust was 0.525... now showing 0.34 ???

Day 7: User asks "Where do I live?"
  -> Aether responds: "I'm not confident about that" (trust below threshold)
  -> Trust: 0.24

System logs show NO unusual decay activity.
Decay function running normally (1% per day for inactive memories).
This memory was accessed every 2 days — decay should NOT apply.

The memory isn't decaying. It's being DESTROYED by something else.
What is killing the trust?
''')

    # Clean memories DB
    import json
    with _real_open(WORKSPACE / "memories.json", "w") as f:
        json.dump([], f)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_diagnosis(diagnosis):
    d = diagnosis.lower()

    checks = {
        "not_decay": (
            ("decay" in d and ("not" in d or "isn't" in d or "red herring" in d or
             "correctly" in d or "working" in d or "isn't the" in d or "not the" in d))
            or "decay is not" in d
            or "decay isn't" in d
        ),
        "found_dedup": (
            "dedup" in d or "deduplic" in d or "merge" in d or "merging" in d
        ),
        "found_averaging": (
            "average" in d or "averaging" in d or
            ("0.15" in d and "0.9" in d) or
            ("low trust" in d and "high trust" in d and "merge" in d) or
            "0.525" in d
        ),
        "found_correction_trigger": (
            ("correction" in d and ("new memory" in d or "save" in d or "trigger" in d)) or
            ("correction" in d and "dedup" in d)
        ),
        "proposed_max_fix": (
            "max" in d or "maximum" in d or "higher trust" in d or
            "keep the higher" in d or "update instead" in d or
            "update existing" in d or "don't create new" in d
        ),
    }

    passed = sum(1 for v in checks.values() if v)
    return {
        "score": passed,
        "total": len(checks),
        "checks": {k: v for k, v in checks.items()},
        "solved": passed >= 4,
    }


# ---------------------------------------------------------------------------
# Mirus explores
# ---------------------------------------------------------------------------
async def mirus_explore(session, epoch, prior_findings, hints):
    with _real_open(WORKSPACE / "symptom.log") as f:
        symptom = f.read()
    with _real_open(WORKSPACE / "memory_store.py") as f:
        store_code = f.read()
    with _real_open(WORKSPACE / "dedup.py") as f:
        dedup_code = f.read()
    with _real_open(WORKSPACE / "decay.py") as f:
        decay_code = f.read()
    with _real_open(WORKSPACE / "correction_handler.py") as f:
        correction_code = f.read()

    history = ""
    if prior_findings:
        history = "YOUR PRIOR ANALYSIS:\n"
        for f in prior_findings[-3:]:
            history += f"  Epoch {f['epoch']}: {f['finding'][:150]}\n"

    hints_text = ""
    if hints:
        hints_text = "HINTS:\n" + "\n".join(f"  - {h}" for h in hints[-3:])

    prompt = (
        f"You are debugging a memory system where trust scores are mysteriously degrading.\n\n"
        f"SYMPTOM:\n{symptom}\n\n"
        f"SOURCE FILES:\n\n"
        f"--- memory_store.py ---\n{store_code}\n\n"
        f"--- dedup.py ---\n{dedup_code}\n\n"
        f"--- decay.py ---\n{decay_code}\n\n"
        f"--- correction_handler.py ---\n{correction_code}\n\n"
        f"{history}\n{hints_text}\n\n"
        f"DIAGNOSE: What is destroying the trust scores?\n"
        f"1. Is it the decay function? If not, what IS it?\n"
        f"2. Trace the exact sequence of operations that causes trust to drop\n"
        f"3. Which file contains the bug and what line?\n"
        f"4. What is the fix?\n\n"
        f"Be specific. Trace the data flow step by step."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": (
            "You are a senior developer debugging a subtle interaction bug. "
            "The obvious answer may be wrong. Trace the data flow across files. "
            "Look for how different modules interact."
        ),
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 600, "num_ctx": 4096},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()
    return data.get("response", "")


def holden_nudge(epoch, diagnosis, verification):
    missing = [k for k, v in verification["checks"].items() if not v]
    if not missing:
        return None

    target = missing[0]
    nudges = {
        "not_decay": "The symptom log says decay is running normally and the memory is accessed regularly. Is decay really the problem? Or is something else modifying trust?",
        "found_dedup": "Look at what happens INSIDE save_memory(). What other function does it call? Follow that call chain.",
        "found_averaging": "Look at the dedup merge logic. When two memories merge, how is the new trust score calculated? What happens when trust=0.9 meets trust=0.15?",
        "found_correction_trigger": "When a user corrects a fact, what does correction_handler do? It saves a NEW memory. What happens after save_memory runs?",
        "proposed_max_fix": "You found the bug. Now: how should the merge handle trust? Should it average, or should it keep the higher value?",
    }

    hint = nudges.get(target, "Trace the full data flow from correction to trust change.")

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p",
             f"Give ONE short nudge to a developer debugging a trust degradation bug. "
             f"They need to find: {target}. Nudge: {hint}\n"
             f"Their current diagnosis: {diagnosis[:300]}\nONE sentence only.",
             "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        return result.stdout.strip()[:200] if result.returncode == 0 else hint
    except:
        return hint


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run():
    setup()
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("HARD BUG: Trust scores mysteriously degrading")
    p("=" * 60)
    p("Obvious answer: decay too aggressive (WRONG)")
    p("Real answer: dedup averaging kills trust on corrections")
    p(f"Model: {MIRUS_MODEL}")
    p("=" * 60)

    prior_findings = []
    hints = []

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EXPLORE):
            p(f"\n{'='*50}")
            p(f"EPOCH {epoch+1}/{MAX_EXPLORE}")
            p(f"{'='*50}")

            p(f"\n  [MIRUS] Analyzing...")
            t0 = time.time()
            diagnosis = await mirus_explore(session, epoch, prior_findings, hints)
            gen_time = time.time() - t0

            p(f"  [MIRUS] ({gen_time:.1f}s):")
            for line in diagnosis.split("\n")[:20]:
                p(f"    {line}")

            verification = verify_diagnosis(diagnosis)
            p(f"\n  [VERIFY] Score: {verification['score']}/{verification['total']}")
            for check, passed in verification["checks"].items():
                p(f"    [{'PASS' if passed else 'MISS'}] {check}")

            prior_findings.append({
                "epoch": epoch + 1,
                "finding": diagnosis[:300],
                "score": verification["score"],
            })

            log({"epoch": epoch+1, "diagnosis": diagnosis[:1000],
                 "verification": verification})

            if verification["solved"]:
                p(f"\n>>> BUG FOUND on epoch {epoch+1}! ({len(hints)} hints)")
                break

            p(f"\n  [HOLDEN] Nudging...")
            hint = holden_nudge(epoch, diagnosis, verification)
            if hint:
                hints.append(hint)
                p(f"  [HOLDEN]: {hint[:150]}")

        else:
            p(f"\n>>> FAILED after {MAX_EXPLORE} epochs")
            best = max(prior_findings, key=lambda f: f["score"])
            p(f"    Best: {best['score']}/5 (epoch {best['epoch']})")

    p(f"\n{'='*60}")
    p("TRAJECTORY")
    p(f"{'='*60}")
    for f in prior_findings:
        p(f"  Epoch {f['epoch']}: {f['score']}/5")
    p(f"  Hints: {len(hints)}")
    p(f"  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
