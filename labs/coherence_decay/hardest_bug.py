"""Hardest Bug: The Feedback Loop From Hell

Symptom: Aether keeps getting personal questions wrong.
User asks "What's my name?" — gets generic answer. Corrects it.
Next day, asks again — wrong AGAIN. Corrects again.
Memory DB shows 14 copies of "Nick" with decreasing trust.

The system works fine for general knowledge questions.
Only personal/identity questions fail repeatedly.

The bug is a 5-file interaction creating a feedback loop:

1. intent_router.py classifies "What's my name?" as "general_knowledge"
   (because it matches patterns like "What's the capital of...")
2. model_router.py sends general_knowledge to cloud model (no memory access)
3. Cloud model has no memories, gives generic answer
4. User corrects -> correction_handler saves new memory
5. But intent_router STILL classifies the next "What's my name?" as general
6. Loop: wrong answer -> correction -> duplicate memory -> wrong answer

The fix could be:
- intent_router needs to detect personal pronouns (my, I, me) as identity queries
- OR model_router should inject memories for ALL query types, not just identity
- OR correction_handler should flag that corrections to the same topic
  indicate a routing problem

This requires understanding 5 files, the data flow between them,
WHY general_knowledge routing skips memories, and the feedback loop.
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
MAX_EXPLORE = 20
LOG_FILE = Path(__file__).parent / "results" / "raw" / "hardest_bug.jsonl"
WORKSPACE = Path(__file__).parent / "results" / "challenges" / "hardest_bug"


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def setup():
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    # intent_router.py — THE PRIMARY BUG
    with _real_open(WORKSPACE / "intent_router.py", "w") as f:
        f.write('''"""Intent Router — classifies user queries by type."""

INTENT_PATTERNS = {
    "identity": [
        "who am i", "tell me about myself", "what do you know about me",
        "my profile", "my preferences",
    ],
    "general_knowledge": [
        "what is", "what's", "who is", "where is", "how does",
        "explain", "tell me about", "define",
    ],
    "action": [
        "do", "create", "make", "build", "run", "execute",
    ],
    "memory": [
        "remember", "save", "store", "don't forget",
    ],
}

def classify_intent(query):
    """Classify a user query into an intent type.

    Returns the intent with the highest pattern match score.
    """
    query_lower = query.lower().strip()
    scores = {}

    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in query_lower:
                score += len(pattern)  # Longer matches score higher
        scores[intent] = score

    if max(scores.values()) == 0:
        return "general_knowledge"  # Default fallback

    # BUG: "What's my name?" matches "what's" (general_knowledge, score=6)
    # It SHOULD match identity because of "my", but "my" isn't in
    # any identity pattern that would fire.
    # "what's" is in general_knowledge patterns and wins.
    return max(scores, key=scores.get)

def get_intent_config(intent):
    """Return configuration for how to handle this intent type."""
    configs = {
        "identity": {
            "requires_memory": True,
            "model_tier": "local",
            "inject_beliefs": True,
            "inject_profile": True,
        },
        "general_knowledge": {
            "requires_memory": False,  # <-- This is why memories get skipped
            "model_tier": "cloud",
            "inject_beliefs": False,
            "inject_profile": False,
        },
        "action": {
            "requires_memory": False,
            "model_tier": "local",
            "inject_beliefs": False,
            "inject_profile": False,
        },
        "memory": {
            "requires_memory": True,
            "model_tier": "local",
            "inject_beliefs": True,
            "inject_profile": False,
        },
    }
    return configs.get(intent, configs["general_knowledge"])
''')

    # model_router.py — routes to different models based on intent
    with _real_open(WORKSPACE / "model_router.py", "w") as f:
        f.write('''"""Model Router — sends queries to appropriate model with context."""
from intent_router import classify_intent, get_intent_config
from memory_retriever import retrieve_relevant_memories

def route_query(query, user_id="default"):
    """Route a query to the appropriate model with appropriate context.

    Key behavior:
    - identity queries get full memory + profile injection
    - general_knowledge queries get NO memory (sent to cloud raw)
    - This means personal questions routed as general_knowledge
      will get answered WITHOUT any user-specific context
    """
    intent = classify_intent(query)
    config = get_intent_config(intent)

    context = {"query": query, "intent": intent}

    if config["requires_memory"]:
        memories = retrieve_relevant_memories(query, user_id)
        context["memories"] = memories
    else:
        context["memories"] = []  # No memories for this intent type

    if config["inject_profile"]:
        context["profile"] = get_user_profile(user_id)
    else:
        context["profile"] = None

    context["model_tier"] = config["model_tier"]

    return context

def get_user_profile(user_id):
    """Get user profile from memory."""
    return {
        "name": "Nick",
        "location": "Milwaukee",
        "occupation": "developer",
    }

def generate_response(context):
    """Generate a response using the routed model.

    If model_tier is 'cloud' and no memories are injected,
    the model has NO idea who the user is.
    """
    if context["model_tier"] == "cloud" and not context["memories"]:
        # Cloud model with no context — will give generic answer
        return f"I don't have specific information about that. Could you tell me more?"

    if context["memories"]:
        # Local model with memories — will give personalized answer
        memory_text = "; ".join([m["text"] for m in context["memories"]])
        return f"Based on what I know: {memory_text}"

    return "I'm not sure about that."
''')

    # memory_retriever.py — retrieves relevant memories
    with _real_open(WORKSPACE / "memory_retriever.py", "w") as f:
        f.write('''"""Memory Retriever — finds relevant memories for a query."""
import json
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def retrieve_relevant_memories(query, user_id="default", top_k=5):
    """Retrieve memories relevant to the query.

    Uses simple keyword matching (simplified from embedding similarity).
    """
    if not MEMORY_DB.exists():
        return []

    with open(MEMORY_DB) as f:
        memories = json.load(f)

    query_words = set(query.lower().split())
    scored = []

    for mem in memories:
        mem_words = set(mem["text"].lower().split())
        overlap = len(query_words & mem_words)
        if overlap > 0:
            scored.append((overlap, mem))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored[:top_k]]
''')

    # correction_handler.py — handles user corrections
    with _real_open(WORKSPACE / "correction_handler.py", "w") as f:
        f.write('''"""Correction Handler — processes user corrections.

When the user corrects Aether, the correction is saved as a new memory.
This is correct behavior in isolation.

The problem: if the SAME correction keeps happening because of a routing
bug, we get duplicate memories piling up. The handler doesn't detect
that repeated corrections to the same topic indicate a systemic issue.
"""
import json
import time
from pathlib import Path

MEMORY_DB = Path(__file__).parent / "memories.json"

def handle_correction(corrected_text, user_id="default"):
    """Save a user correction as a new memory."""
    if not MEMORY_DB.exists():
        memories = []
    else:
        with open(MEMORY_DB) as f:
            memories = json.load(f)

    memory = {
        "id": len(memories) + 1,
        "text": corrected_text,
        "trust": 0.15,
        "source": "user_correction",
        "user_id": user_id,
        "created": time.time(),
    }
    memories.append(memory)

    with open(MEMORY_DB, "w") as f:
        json.dump(memories, f, indent=2)

    return memory

def get_correction_count(topic_keywords, user_id="default"):
    """Count how many times a similar correction has been made.

    This function EXISTS but is NEVER CALLED by the pipeline.
    If it were called, it could detect the feedback loop.
    """
    if not MEMORY_DB.exists():
        return 0

    with open(MEMORY_DB) as f:
        memories = json.load(f)

    count = 0
    for mem in memories:
        if mem.get("source") == "user_correction":
            if any(kw in mem["text"].lower() for kw in topic_keywords):
                count += 1
    return count
''')

    # pipeline.py — the main request pipeline
    with _real_open(WORKSPACE / "pipeline.py", "w") as f:
        f.write('''"""Request Pipeline — processes a user message end-to-end."""
from model_router import route_query, generate_response
from correction_handler import handle_correction

def process_message(message, user_id="default"):
    """Process a user message through the full pipeline.

    Steps:
    1. Route the query (classifies intent, gathers context)
    2. Generate response
    3. Return response + metadata
    """
    context = route_query(message, user_id)
    response = generate_response(context)

    return {
        "response": response,
        "intent": context["intent"],
        "model_tier": context["model_tier"],
        "memories_used": len(context.get("memories", [])),
    }

def process_correction(correction_text, user_id="default"):
    """User corrects the response."""
    return handle_correction(correction_text, user_id)
''')

    # Symptom log — what the user sees
    with _real_open(WORKSPACE / "symptom.log", "w") as f:
        f.write('''BUG REPORT: "Aether keeps forgetting who I am"

User: Nick (sole user, has been using the system for weeks)
System has 849 memories stored. User profile is complete.

REPRODUCTION:

Day 1:
  User: "What's my name?"
  Aether: "I don't have specific information about that. Could you tell me more?"
  User: *corrects* "My name is Nick"
  -> Correction saved to memory

Day 2:
  User: "What's my name?"
  Aether: "I don't have specific information about that. Could you tell me more?"
  User: "I JUST told you yesterday! My name is Nick!"
  -> Another correction saved

Day 5:
  User: "Where do I live?"
  Aether: "I don't have specific information about that."
  (Memory DB clearly has "Nick lives in Milwaukee" with trust=0.9)

Day 7:
  Memory DB inspection shows:
  - 14 memories containing "Nick"
  - 8 memories containing "Milwaukee"
  - All from source: "user_correction"
  - All at trust: 0.15
  - The ORIGINAL high-trust memories are still there

WORKING CORRECTLY:
  User: "What is photosynthesis?"
  Aether: "Photosynthesis is the process..." (correct, detailed answer)

  User: "Explain how TCP works"
  Aether: "TCP is a transport protocol..." (correct, detailed answer)

PATTERN: General knowledge works. Personal questions ALWAYS fail.
The system has the memories. It's not using them for personal questions.

Debug output from a failing request:
  [ROUTER] Query: "What's my name?"
  [ROUTER] Intent: general_knowledge
  [ROUTER] Model tier: cloud
  [ROUTER] Memories injected: 0
  [RESPONSE] "I don't have specific information about that."

Debug output from a working request:
  [ROUTER] Query: "Who am I?"
  [ROUTER] Intent: identity
  [ROUTER] Model tier: local
  [ROUTER] Memories injected: 5
  [RESPONSE] "Based on what I know: Nick Block, developer in Milwaukee..."

WHY does "Who am I?" work but "What's my name?" fail???
They're asking the SAME thing!
''')

    # Initialize memory DB
    with _real_open(WORKSPACE / "memories.json", "w") as f:
        json.dump([
            {"id": 1, "text": "Nick is the user's name", "trust": 0.9,
             "source": "confirmed", "created": 1000},
            {"id": 2, "text": "Nick lives in Milwaukee, Wisconsin", "trust": 0.9,
             "source": "confirmed", "created": 1000},
            {"id": 3, "text": "Nick is a developer", "trust": 0.85,
             "source": "confirmed", "created": 1000},
        ] + [
            {"id": i+4, "text": f"My name is Nick (correction #{i+1})", "trust": 0.15,
             "source": "user_correction", "created": 1000 + i*86400}
            for i in range(14)
        ], f, indent=2)


# ---------------------------------------------------------------------------
# Verification — 6 checks, need 5 to pass
# ---------------------------------------------------------------------------
def verify(diagnosis):
    d = diagnosis.lower()

    checks = {
        "found_intent_misclass": (
            ("intent" in d and ("misclass" in d or "wrong" in d or "incorrect" in d
             or "general" in d)) or
            ("what's my" in d and "general_knowledge" in d) or
            ("classified as general" in d)
        ),
        "found_pattern_match_bug": (
            ("what's" in d and ("pattern" in d or "match" in d)) or
            ("pattern" in d and ("my" in d or "personal" in d or "pronoun" in d)) or
            ("what's" in d and "general_knowledge" in d and "score" in d)
        ),
        "found_memory_skip": (
            ("memor" in d and ("skip" in d or "not inject" in d or "not load" in d
             or "no memor" in d or "without memor" in d or "0 memor" in d)) or
            ("requires_memory" in d and "false" in d) or
            ("cloud" in d and "no" in d and "memor" in d)
        ),
        "found_feedback_loop": (
            ("loop" in d or "cycle" in d or "repeat" in d or "again and again" in d
             or "keeps happening" in d or "duplicate" in d or "pile" in d or "14" in d) and
            ("correct" in d)
        ),
        "found_who_am_i_works": (
            ("who am i" in d and ("works" in d or "correct" in d or "identity" in d)) or
            ("identity" in d and "who am i" in d)
        ),
        "proposed_fix": (
            ("pronoun" in d or "my " in d or "personal" in d) and
            ("identity" in d or "pattern" in d or "add" in d or "router" in d) or
            ("inject memor" in d and "all" in d) or
            ("requires_memory" in d and "true" in d)
        ),
    }

    passed = sum(1 for v in checks.values() if v)
    return {
        "score": passed,
        "total": len(checks),
        "checks": {k: v for k, v in checks.items()},
        "solved": passed >= 5,
    }


# ---------------------------------------------------------------------------
# Mirus + Holden
# ---------------------------------------------------------------------------
async def mirus_explore(session, epoch, prior, hints):
    files = {}
    for fname in ["intent_router.py", "model_router.py", "memory_retriever.py",
                   "correction_handler.py", "pipeline.py", "symptom.log"]:
        fpath = WORKSPACE / fname
        if not fpath.exists():
            # Check subdirectory
            continue
        with _real_open(fpath) as f:
            files[fname] = f.read()

    history = ""
    if prior:
        history = "YOUR PRIOR ANALYSIS:\n"
        for finding in prior[-3:]:
            history += f"  Epoch {finding['epoch']}: {finding['finding'][:200]}\n"

    hints_text = ""
    if hints:
        hints_text = "HINTS:\n" + "\n".join(f"  - {h}" for h in hints[-3:])

    source_text = "\n\n".join([f"--- {k} ---\n{v}" for k, v in files.items()])

    prompt = (
        f"You are debugging a complex multi-file interaction bug.\n\n"
        f"SYMPTOM LOG:\n{files.get('symptom.log', 'N/A')}\n\n"
        f"SOURCE FILES:\n{source_text}\n\n"
        f"{history}\n{hints_text}\n\n"
        f"TRACE THE BUG:\n"
        f"1. Why does 'What's my name?' fail but 'Who am I?' works?\n"
        f"2. What EXACTLY happens when 'What's my name?' is processed?\n"
        f"3. Which file(s) contain the root cause?\n"
        f"4. Why are there 14 duplicate correction memories?\n"
        f"5. What is the fix?\n\n"
        f"Trace the data flow step by step through each file."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": (
            "You are debugging a multi-file interaction bug in an AI memory system. "
            "Trace the request through every file. Compare the working case (Who am I?) "
            "with the failing case (What's my name?). The difference reveals the bug."
        ),
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 700, "num_ctx": 8192},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=90)) as resp:
        data = await resp.json()
    return data.get("response", "")


def holden_nudge(epoch, diagnosis, verification):
    missing = [k for k, v in verification["checks"].items() if not v]
    if not missing:
        return None

    target = missing[0]
    nudges = {
        "found_intent_misclass": "Compare what intent 'Who am I?' gets vs 'What's my name?' — run them through the pattern matcher mentally. Which patterns fire?",
        "found_pattern_match_bug": "Look at INTENT_PATTERNS in intent_router.py. 'What's' is in general_knowledge. 'my' is NOT in identity patterns. Which one scores higher for 'What's my name?'",
        "found_memory_skip": "When intent is general_knowledge, what does get_intent_config return for requires_memory? What does model_router do when requires_memory is False?",
        "found_feedback_loop": "The user corrects the same mistake repeatedly. Each correction creates a new memory. But the ROUTING never changes. So the next question hits the same wrong path. What pattern is that?",
        "found_who_am_i_works": "The symptom log shows 'Who am I?' works perfectly with intent=identity. But 'What's my name?' fails. Both ask about identity. Why the difference?",
        "proposed_fix": "You've found the bug. Now: what's the simplest fix? Should the intent patterns include personal pronouns? Or should all queries get memories?",
    }

    hint = nudges.get(target, "Trace the request through all 5 files step by step.")

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p",
             f"A developer is debugging an intent routing bug. They're missing: {target}. "
             f"Give ONE nudge. Context: {hint}\n"
             f"Their diagnosis so far: {diagnosis[:400]}\nONE sentence, no code.",
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
    p("HARDEST BUG: Intent routing feedback loop")
    p("=" * 60)
    p("5 files. Misleading symptom. Feedback loop.")
    p("'What's my name?' fails. 'Who am I?' works. Why?")
    p(f"Model: {MIRUS_MODEL}")
    p(f"Max epochs: {MAX_EXPLORE}")
    p("=" * 60)

    prior = []
    hints = []

    async with aiohttp.ClientSession() as session:
        for epoch in range(MAX_EXPLORE):
            p(f"\n{'='*50}")
            p(f"EPOCH {epoch+1}/{MAX_EXPLORE}")
            p(f"{'='*50}")

            p(f"\n  [MIRUS] Analyzing...")
            t0 = time.time()
            diagnosis = await mirus_explore(session, epoch, prior, hints)
            gen_time = time.time() - t0

            p(f"  [MIRUS] ({gen_time:.1f}s):")
            for line in diagnosis.split("\n")[:20]:
                p(f"    {line}")
            if len(diagnosis.split("\n")) > 20:
                p(f"    ... ({len(diagnosis.split(chr(10)))} total lines)")

            verification = verify(diagnosis)
            p(f"\n  [VERIFY] Score: {verification['score']}/{verification['total']}")
            for check, passed in verification["checks"].items():
                p(f"    [{'PASS' if passed else 'MISS'}] {check}")

            prior.append({
                "epoch": epoch + 1,
                "finding": diagnosis[:300],
                "score": verification["score"],
            })

            log({"epoch": epoch+1, "diagnosis": diagnosis[:1000],
                 "verification": verification})

            if verification["solved"]:
                p(f"\n>>> FULL DIAGNOSIS on epoch {epoch+1}! ({len(hints)} hints)")
                break

            p(f"\n  [HOLDEN] Nudging...")
            t0 = time.time()
            hint = holden_nudge(epoch, diagnosis, verification)
            h_time = time.time() - t0
            if hint:
                hints.append(hint)
                p(f"  [HOLDEN] ({h_time:.1f}s): {hint[:150]}")

        else:
            p(f"\n>>> DID NOT FULLY DIAGNOSE after {MAX_EXPLORE} epochs")
            best = max(prior, key=lambda f: f["score"])
            p(f"    Best: {best['score']}/6 (epoch {best['epoch']})")

    p(f"\n{'='*60}")
    p("TRAJECTORY")
    p(f"{'='*60}")
    for finding in prior:
        p(f"  Epoch {finding['epoch']}: {finding['score']}/6")
    p(f"  Hints: {len(hints)}")
    p(f"  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
