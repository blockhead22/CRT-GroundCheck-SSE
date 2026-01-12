#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
from pathlib import Path

from personal_agent.artifact_store import now_iso_utc, write_promotion_apply_result
from personal_agent.promotion_apply import apply_promotions


def _resolve_maybe_glob(path_or_pattern: str) -> Path:
    s = str(path_or_pattern or "").strip()
    if not s:
        raise ValueError("empty path")

    if any(ch in s for ch in ("*", "?", "[")):
        matches = [Path(p) for p in glob.glob(s)]
        matches = [p for p in matches if p.exists() and p.is_file()]
        if not matches:
            raise FileNotFoundError(f"No files matched: {s}")
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0].resolve()

    return Path(s).resolve()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply approved promotion proposals into a CRT memory DB")
    ap.add_argument("--memory-db", required=True, help="Path to target memory sqlite db")
    ap.add_argument("--proposals", required=True, help="Path to proposals.*.json artifact")
    ap.add_argument("--decisions", required=True, help="Path to decisions.*.json artifact")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Base directory to write apply result artifacts")
    ap.add_argument("--dry-run", action="store_true", help="Compute actions but do not write to the DB")
    ap.add_argument("--notes", default=None, help="Optional note stored in the apply result artifact")

    args = ap.parse_args(argv)

    proposals_path = _resolve_maybe_glob(args.proposals)
    decisions_path = _resolve_maybe_glob(args.decisions)
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    payload, _ = apply_promotions(
        memory_db=str(Path(args.memory_db).resolve()),
        proposals_path=proposals_path,
        decisions_path=decisions_path,
        dry_run=bool(args.dry_run),
    )
    if args.notes is not None:
        payload["metadata"]["notes"] = str(args.notes)

    out_dir = artifacts_dir / "promotion_apply"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = now_iso_utc().replace(":", "").replace("+", "").replace("-", "")
    out_path = out_dir / f"apply_result.{ts}.json"
    write_promotion_apply_result(out_path, payload)

    applied = sum(
        1
        for r in payload.get("results", [])
        if r.get("action") == "applied" and r.get("new_memory_id") not in (None, "dry_run")
    )
    would_apply = sum(
        1
        for r in payload.get("results", [])
        if r.get("action") == "applied" and r.get("new_memory_id") == "dry_run"
    )
    skipped = sum(1 for r in payload.get("results", []) if r.get("action") == "skipped")
    errors = sum(1 for r in payload.get("results", []) if r.get("action") == "error")

    print(f"Wrote apply result: {out_path}")
    if args.dry_run:
        print(f"Would apply: {would_apply} | Skipped: {skipped} | Errors: {errors} | Dry-run: True")
    else:
        print(f"Applied: {applied} | Skipped: {skipped} | Errors: {errors} | Dry-run: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
