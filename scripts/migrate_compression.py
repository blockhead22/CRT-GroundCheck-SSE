#!/usr/bin/env python3
"""Migrate existing compressed memories from fold format to MemQuant format.

Idempotent — skips memories that already have method=memquant.
Re-compresses from the original full vector (always preserved in vector_json).

Usage:
    python scripts/migrate_compression.py [--db PATH] [--dry-run]
"""

import argparse
import json
import sqlite3
import sys
import os

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_agent.memory_compression import quantize_vector, TIER_BITS


def migrate(db_path: str, dry_run: bool = False):
    conn = sqlite3.connect(db_path)

    # Check columns exist
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
    if "compression_tier" not in cols:
        print("No compression columns found. Nothing to migrate.")
        return

    rows = conn.execute(
        """SELECT memory_id, vector_json, compression_tier, cogni_seed_json
           FROM memories
           WHERE compression_tier < 2
             AND compressed_vector_json IS NOT NULL
             AND (deprecated IS NULL OR deprecated = 0)"""
    ).fetchall()

    print(f"Found {len(rows)} compressed memories to check.")

    migrated = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        mem_id, vector_json, tier, seed_json = row

        # Skip if already memquant
        if seed_json:
            try:
                seed = json.loads(seed_json)
                if isinstance(seed, dict) and seed.get("method") == "memquant":
                    skipped += 1
                    continue
            except Exception:
                pass

        # Load original vector
        try:
            original = np.array(json.loads(vector_json), dtype=np.float32)
        except Exception as e:
            print(f"  ERROR loading vector for {mem_id}: {e}")
            errors += 1
            continue

        # Re-compress with MemQuant
        bits = TIER_BITS.get(tier, 3)
        if bits == 0:
            skipped += 1
            continue

        indices, metadata = quantize_vector(original, bits)

        if not dry_run:
            conn.execute(
                """UPDATE memories SET
                        compressed_vector_json = ?,
                        cogni_seed_json = ?
                    WHERE memory_id = ?""",
                (json.dumps(indices.tolist()), json.dumps(metadata), mem_id),
            )

        migrated += 1
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(rows)} checked, {migrated} migrated")

    if not dry_run:
        conn.commit()

    conn.close()
    print(f"\nDone. Migrated: {migrated}, Skipped (already memquant): {skipped}, Errors: {errors}")
    if dry_run:
        print("(dry run — no changes written)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate compression format to MemQuant")
    parser.add_argument("--db", default="crt_memory.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}")
        sys.exit(1)

    migrate(args.db, dry_run=args.dry_run)
