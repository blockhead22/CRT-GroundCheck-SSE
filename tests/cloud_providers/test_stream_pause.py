#!/usr/bin/env python3
"""
Streaming pause/resume test with mid-generation verification.

Phase 1: Can we pause qwen mid-story and resume?
Phase 2: Can we inject CRT-like checks at checkpoints?
Phase 3: Can we course-correct mid-stream?

Watch it happen in real time.
"""
from __future__ import annotations

import json
import re
import sys
import time
import requests
from typing import Generator, Tuple

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3:14b"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def stream_tokens(prompt: str, system: str = "", max_tokens: int = 500) -> Generator[Tuple[str, str], None, None]:
    """Stream tokens from Ollama. Yields (token_type, text) tuples.

    Handles qwen3's <think>...</think> blocks by buffering them
    and only yielding visible content after the think block closes.
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": True,
        "options": {"num_predict": max_tokens, "temperature": 0.7},
    }
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=120)

    think_buffer = ""
    thinking_done = False

    for line in resp.iter_lines():
        if not line:
            continue
        data = json.loads(line)
        thinking_token = data.get("thinking", "")
        response_token = data.get("response", "")
        done = data.get("done", False)

        # Ollama qwen3 uses separate "thinking" and "response" fields
        if thinking_token:
            think_buffer += thinking_token
            continue

        if response_token:
            if not thinking_done and think_buffer:
                # First visible token after thinking — yield thinking summary
                yield ("thinking", think_buffer)
                thinking_done = True
            yield ("token", response_token)

        if done:
            if think_buffer and not thinking_done:
                yield ("thinking", think_buffer)
            yield ("done", data.get("done_reason", ""))
            break


def strip_think_content(text: str) -> str:
    """Remove <think>...</think> blocks."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# =====================================================================
# PHASE 1: Stream, pause at checkpoint, resume from where we left off
# =====================================================================

def phase1_pause_resume():
    print(f"\n{BOLD}{CYAN}=== PHASE 1: Stream, Pause, Resume ==={RESET}")
    print(f"{DIM}Ask qwen to tell a story. Stop at ~200 tokens. Resume with context.{RESET}\n")

    system = "You are a storyteller. Tell vivid, engaging stories. Be concise and direct."
    prompt = "Tell me a short story about a robot who learns to dream. Keep it under 300 words."

    buffer = ""
    token_count = 0
    checkpoint = 100  # pause after this many VISIBLE tokens
    paused = False

    print(f"{BOLD}--- PART 1 (streaming until checkpoint) ---{RESET}")

    thinking_shown = False
    for token_type, text in stream_tokens(prompt, system, max_tokens=2000):
        if token_type == "done":
            break
        if token_type == "thinking":
            if not thinking_shown:
                print(f"{DIM}  [thinking: {text[:80]}...]{RESET}")
                thinking_shown = True
            continue
        # Visible token
        if token_count == 0:
            print(f"{GREEN}", end="", flush=True)
        buffer += text
        token_count += 1
        print(text, end="", flush=True)

        if token_count >= checkpoint and not paused:
            paused = True
            print(f"{RESET}")
            print(f"\n{YELLOW}--- PAUSED at {token_count} tokens ---{RESET}")
            print(f"{DIM}Buffer length: {len(buffer)} chars{RESET}")
            break

    if not paused:
        print(f"{RESET}")
        print(f"{YELLOW}Story completed before checkpoint ({token_count} tokens){RESET}")
        return buffer

    # Now resume with the buffer as context
    time.sleep(1)
    print(f"\n{BOLD}--- PART 2 (resuming from checkpoint) ---{RESET}")

    resume_prompt = f"""Continue this story EXACTLY from where it left off. Do not restart or summarize. Just continue the next sentence:

{buffer}"""

    part2_buffer = ""
    part2_count = 0
    for token_type, text in stream_tokens(resume_prompt, system, max_tokens=1500):
        if token_type == "done":
            break
        if token_type == "thinking":
            continue
        if part2_count == 0:
            print(f"{CYAN}", end="", flush=True)
        part2_buffer += text
        part2_count += 1
        print(text, end="", flush=True)

    print(f"{RESET}")
    full_story = buffer + part2_buffer
    print(f"\n{DIM}Total: {len(full_story)} chars across 2 generations ({token_count} + {part2_count} tokens){RESET}")
    return full_story


# =====================================================================
# PHASE 2: Mid-stream CRT checkpoint (toy version)
# =====================================================================

def phase2_crt_checkpoint():
    print(f"\n{BOLD}{CYAN}=== PHASE 2: Mid-Stream CRT Verification ==={RESET}")
    print(f"{DIM}Stream a factual response. Every 150 tokens, run a fake CRT check.{RESET}\n")

    # Simulated "known facts" — what CRT would have in memory
    known_facts = {
        "name": "Nick Block",
        "favorite_color": "orange",
        "occupation": "freelance developer",
        "health": "chronic graft vs host disease",
    }

    system = "You are Aether, a personal AI assistant. Answer questions about the user based on what you know."
    prompt = f"""Here are facts about the user:
- Name: {known_facts['name']}
- Favorite color: {known_facts['favorite_color']}
- Occupation: {known_facts['occupation']}
- Health: {known_facts['health']}

Now tell the user about themselves in a warm, personal way. Include all the facts naturally."""

    buffer = ""
    token_count = 0
    checkpoint_interval = 150
    next_checkpoint = checkpoint_interval
    checks_passed = 0
    checks_failed = 0

    print(f"{GREEN}", end="", flush=True)

    for token_type, text in stream_tokens(prompt, system, max_tokens=2000):
        if token_type == "done":
            break
        if token_type == "thinking":
            continue
        buffer += text
        token_count += 1
        print(text, end="", flush=True)

        # CRT checkpoint
        if token_count >= next_checkpoint:
            print(f"{RESET}")
            print(f"\n{MAGENTA}  [CRT CHECKPOINT @ {token_count} tokens]{RESET}")

            # Check 1: Think tag leak
            if "<think>" in buffer.lower():
                print(f"  {RED}  FAIL: Think tags leaking into response{RESET}")
                checks_failed += 1
            else:
                print(f"  {GREEN}  PASS: No think tag leak{RESET}")
                checks_passed += 1

            # Check 2: Fact contradiction (toy version)
            lower_buf = buffer.lower()
            if "yellow" in lower_buf and "favorite color" in lower_buf:
                print(f"  {RED}  FAIL: Said yellow instead of orange{RESET}")
                checks_failed += 1
            elif "orange" in lower_buf:
                print(f"  {GREEN}  PASS: Favorite color correct (orange){RESET}")
                checks_passed += 1

            # Check 3: Name check
            if "nick" in lower_buf:
                print(f"  {GREEN}  PASS: User name present{RESET}")
                checks_passed += 1
            else:
                print(f"  {YELLOW}  WARN: User name not yet mentioned{RESET}")

            # Check 4: Repetition detection
            sentences = [s.strip() for s in buffer.split(".") if len(s.strip()) > 20]
            if len(sentences) != len(set(sentences)):
                print(f"  {RED}  FAIL: Repetition detected{RESET}")
                checks_failed += 1
            else:
                print(f"  {GREEN}  PASS: No repetition{RESET}")
                checks_passed += 1

            next_checkpoint += checkpoint_interval
            print(f"{GREEN}", end="", flush=True)

    print(f"{RESET}")
    print(f"\n{BOLD}CRT Results: {checks_passed} passed, {checks_failed} failed{RESET}")
    return buffer


# =====================================================================
# PHASE 3: Course correction mid-stream
# =====================================================================

def phase3_course_correct():
    print(f"\n{BOLD}{CYAN}=== PHASE 3: Mid-Stream Course Correction ==={RESET}")
    print(f"{DIM}Intentionally trigger a contradiction. Detect it. Stop. Regenerate.{RESET}\n")

    known_color = "orange"

    # Deliberately feed a wrong fact to trigger contradiction
    system = """You are a personal AI. You have these facts about the user:
- Name: Nick Block
- Favorite color: blue
- Occupation: freelance developer
Answer warmly and reference these facts."""
    prompt = "Tell me about myself and my preferences!"

    buffer = ""
    token_count = 0
    contradiction_detected = False

    print(f"{BOLD}--- Attempt 1 (monitoring for contradiction) ---{RESET}")
    print(f"{GREEN}", end="", flush=True)

    for token_type, text in stream_tokens(prompt, system, max_tokens=2000):
        if token_type == "done":
            break
        if token_type == "thinking":
            continue
        buffer += text
        token_count += 1
        print(text, end="", flush=True)

        # Check for color contradiction every few tokens
        if token_count % 10 == 0:
            lower = buffer.lower()
            # Check if it mentioned a wrong color as favorite
            wrong_colors = ["blue", "red", "green", "yellow", "purple"]
            for wrong in wrong_colors:
                if f"favorite color" in lower and wrong in lower and known_color not in lower:
                    contradiction_detected = True
                    print(f"{RESET}")
                    print(f"\n{RED}  !!! CONTRADICTION DETECTED at token {token_count} !!!{RESET}")
                    print(f"{RED}  Said '{wrong}' but known fact is '{known_color}'{RESET}")
                    break
            if contradiction_detected:
                break

    if not contradiction_detected:
        print(f"{RESET}")
        lower = buffer.lower()
        if known_color in lower:
            print(f"\n{GREEN}No contradiction — model got it right or didn't mention color.{RESET}")
        else:
            print(f"\n{YELLOW}No contradiction detected, but also didn't mention the correct color.{RESET}")
        return

    # Course correct: regenerate with the known fact injected
    print(f"\n{BOLD}--- Attempt 2 (with fact injection) ---{RESET}")
    print(f"{GREEN}", end="", flush=True)

    corrected_system = f"""You are a personal AI. You have these facts about the user:
- Name: Nick Block
- Favorite color: {known_color}
- Occupation: freelance developer
Answer warmly and reference these facts."""
    corrected_prompt = "Tell me about myself and my preferences!"

    corrected_buffer = ""
    for token_type, text in stream_tokens(corrected_prompt, corrected_system, max_tokens=1500):
        if token_type == "done":
            break
        clean = strip_think_content(text) if "<think>" in text or "</think>" in text else text
        if not clean:
            continue
        corrected_buffer += clean
        print(text, end="", flush=True)

    print(f"{RESET}")

    if known_color in corrected_buffer.lower():
        print(f"\n{GREEN}Course correction successful — correct color in regenerated response.{RESET}")
    else:
        print(f"\n{YELLOW}Regenerated but still didn't mention {known_color}.{RESET}")


# =====================================================================
# Main
# =====================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Streaming pause/resume + CRT checkpoint test")
    parser.add_argument("--phase", "-p", type=int, default=0, help="Run specific phase (1/2/3) or 0 for all")
    args = parser.parse_args()

    if args.phase == 0 or args.phase == 1:
        phase1_pause_resume()
    if args.phase == 0 or args.phase == 2:
        phase2_crt_checkpoint()
    if args.phase == 0 or args.phase == 3:
        phase3_course_correct()

    print(f"\n{BOLD}Done.{RESET}")


if __name__ == "__main__":
    main()
