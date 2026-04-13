"""Trust Recalibration — One-time repair of floor-clamped memories.

The compaction_decay system was applying -0.15 trust hits without
checking access count. Memories accessed 100+ times were stuck at
floor (0.20) despite being clearly load-bearing.

This script recalibrates trust based on actual usage evidence:
  - access_count: how many times retrieved (earned relevance)
  - kind: user_fact gets more credit than observation
  - contradiction_count: contradicted memories stay low
  - original trust: memories already high stay high

Run: python personal_agent/trust_recalibration.py
"""

import sqlite3
import time
import math
import logging

logger = logging.getLogger(__name__)

DB_PATH = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
TRUST_FLOOR = 0.20
TRUST_CEILING = 0.95

# Kind-based base trust (what trust SHOULD be for a healthy memory of this kind)
KIND_BASE = {
    "user_fact": 0.50,
    "self_model": 0.50,
    "preference": 0.45,
    "ops": 0.40,
    "user_belief": 0.40,
    "narrative_note": 0.35,
    "observation": 0.30,
}


def recalibrate(dry_run=True):
    conn = sqlite3.connect(DB_PATH)
    now = time.time()

    rows = conn.execute("""
        SELECT memory_id, text, trust, kind, access_count,
               contradiction_count, timestamp, authority
        FROM memories WHERE deprecated=0
    """).fetchall()

    print(f"Recalibrating {len(rows)} memories (dry_run={dry_run})")

    updated = 0
    changes = []

    for mid, text, trust, kind, access, contras, ts, authority in rows:
        access = access or 0
        contras = contras or 0
        trust = trust or 0.20
        kind = kind or "observation"

        # Skip already-high trust (don't lower them)
        if trust > 0.60:
            continue

        # Skip contradicted memories (they SHOULD be low)
        if contras >= 2:
            continue

        # Skip test probe memories (color tests, identity tests, etc.)
        # These were deliberately injected to test contradiction detection
        text_lower = (text or "").lower()
        test_signals = ["favorite color is green", "favorite color is cyan",
                        "favorite color is purple", "favorite color is red",
                        "favorite color is burgundy", "favorite color is silver",
                        "favorite color is brown", "favorite color is blue",
                        "favorite_color = burgundy", "favorite_color = cyan",
                        "favorite_color = purple", "favorite_color = red",
                        "favorite_color = silver", "favorite_color = brown",
                        "i'm at amazon", "work at a design studio",
                        "work for google", "works at a design studio",
                        "worked for google", "never worked for google"]
        if any(sig in text_lower for sig in test_signals):
            continue

        # Compute what trust should be based on evidence
        base = KIND_BASE.get(kind, 0.30)

        # Access bonus: logarithmic, caps at +0.35
        # 5 accesses: +0.10, 20: +0.20, 50: +0.25, 100: +0.30
        if access > 0:
            access_bonus = min(0.35, 0.065 * math.log1p(access))
        else:
            access_bonus = 0

        # Authority bonus
        auth_bonus = 0.05 if authority == "confirmed" else 0

        # Contradiction penalty
        contra_penalty = contras * 0.15

        # Recalibrated trust
        recalibrated = base + access_bonus + auth_bonus - contra_penalty
        recalibrated = max(TRUST_FLOOR, min(TRUST_CEILING, recalibrated))

        # Only update if recalibrated is HIGHER than current
        # (we're repairing undervaluation, not imposing new values)
        if recalibrated > trust + 0.02:
            changes.append({
                "mid": mid,
                "text": text[:70],
                "old": trust,
                "new": recalibrated,
                "access": access,
                "kind": kind,
            })
            updated += 1

    # Sort by biggest delta
    changes.sort(key=lambda x: -(x["new"] - x["old"]))

    print(f"\nWould update: {updated} / {len(rows)} memories")
    print(f"\nTop 20 changes:")
    for c in changes[:20]:
        delta = c["new"] - c["old"]
        print(f"  {c['old']:.2f} -> {c['new']:.2f} ({delta:+.2f}) [{c['access']}x, {c['kind']}] {c['text']}")

    if not dry_run:
        cursor = conn.cursor()
        for c in changes:
            cursor.execute(
                "UPDATE memories SET trust = ? WHERE memory_id = ?",
                (c["new"], c["mid"]),
            )
            cursor.execute(
                "INSERT INTO trust_log (memory_id, timestamp, old_trust, new_trust, reason, drift) VALUES (?, ?, ?, ?, ?, ?)",
                (c["mid"], now, c["old"], c["new"], "trust_recalibration", 0),
            )
        conn.commit()
        print(f"\nApplied {len(changes)} trust updates.")

    conn.close()
    return changes


if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    if dry:
        print("DRY RUN (use --apply to commit changes)\n")
    recalibrate(dry_run=dry)
