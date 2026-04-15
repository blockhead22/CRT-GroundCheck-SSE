"""Seed Aether substrate with task references before the Warm arm.

Reads tasks.json, writes each task's `reference` (and any `seed_facts`) into
Aether under thread_id=aether_bench. This is the fair setup for Claim 1:
Warm gets a pre-loaded substrate; Cold has only the prompt.

Usage:
    python -m labs.aether_bench.seed           # seed all tasks
    python -m labs.aether_bench.seed --wipe    # (future) clear first
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import aether_client

LAB_DIR = Path(__file__).resolve().parent
TASKS_PATH = LAB_DIR / "tasks.json"


def seed() -> int:
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]
    n = 0
    for t in tasks:
        ref = t.get("reference") or ""
        if ref:
            text = f"[{t['id']}] {ref}"
            try:
                aether_client.store(text=text, confidence=0.85, kind="fact")
                n += 1
                print(f"  + {t['id']}: {ref[:70]}")
            except Exception as e:
                print(f"  ! {t['id']}: {e}")
        for extra in t.get("seed_facts", []) or []:
            try:
                aether_client.store(text=f"[{t['id']}] {extra}",
                                    confidence=0.85, kind="fact")
                n += 1
            except Exception as e:
                print(f"  ! {t['id']} extra: {e}")
    print(f"\nseeded {n} facts into thread_id={aether_client.THREAD_ID}")
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.parse_args()
    seed()


if __name__ == "__main__":
    main()
