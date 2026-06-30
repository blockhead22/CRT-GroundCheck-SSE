"""Attach generated RAG evidence review metadata to a Workbench trace row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from labs.meaning_compression_lab.workbench_trace_fixture import (
    attach_rag_evidence_review_to_trace_fixture,
)


LIVE_DB_CONFIRMATION = "ATTACH_REVIEW_ONLY_TRACE_EVIDENCE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True, help="Workbench DB path.")
    parser.add_argument("--turn-id", required=True, help="Existing Workbench turn_id to update.")
    parser.add_argument("--rag-result-path", type=Path, required=True, help="RAG-suite result JSON.")
    parser.add_argument("--output", type=Path, help="Optional receipt output JSON path. Defaults to stdout.")
    parser.add_argument(
        "--allow-live-db",
        action="store_true",
        help="Allow attaching to ~/.aether/workbench.db. Requires --confirm-live-db.",
    )
    parser.add_argument(
        "--confirm-live-db",
        default="",
        help=f"Required with --allow-live-db. Must equal {LIVE_DB_CONFIRMATION}.",
    )
    args = parser.parse_args(argv)

    _validate_live_db_confirmation(args.db_path, args.allow_live_db, args.confirm_live_db)
    receipt = attach_rag_evidence_review_to_trace_fixture(
        db_path=args.db_path,
        turn_id=args.turn_id,
        rag_result_path=args.rag_result_path,
        allow_live_db=args.allow_live_db,
    )
    text = json.dumps(receipt, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def _validate_live_db_confirmation(db_path: Path, allow_live_db: bool, confirmation: str) -> None:
    live = (Path.home() / ".aether" / "workbench.db").resolve()
    target = Path(db_path).expanduser().resolve()
    if target != live:
        return
    if not allow_live_db:
        return
    if confirmation != LIVE_DB_CONFIRMATION:
        raise ValueError(
            "Live Workbench DB attachment requires "
            f"--confirm-live-db {LIVE_DB_CONFIRMATION}."
        )


if __name__ == "__main__":
    raise SystemExit(main())
