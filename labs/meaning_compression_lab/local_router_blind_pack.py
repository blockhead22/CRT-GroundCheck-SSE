"""Build blind local-router replay packs outside a source evidence pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.local_router_cli import build_case
from labs.meaning_compression_lab.replay_pack_builder import (
    EXPORT_DIR,
    Candidate,
    _dedupe_key,
    collect_candidates,
    select_balanced,
)


DEFAULT_SOURCE = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_curated_v1.json")
DEFAULT_OUT = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_blind_v1.json")
BLIND_REJECT_FLAGS = {
    "low_keyword_specificity",
    "starts_with_quote",
    "artifact_like",
    "transcript_fragment",
    "weak_request_shape",
}


def build_blind_pack(
    *,
    source_pack: dict[str, Any],
    candidates: list[Candidate],
    limit_per_type: int = 3,
    min_quality: int = 4,
    pack_name: str = "local_router_replay_blind_v1",
) -> dict[str, Any]:
    """Select fresh candidate prompts not present in the source pack.

    Blind here means excluded by both source conversation id and prompt dedupe
    key. It does not guarantee the broader project has never discussed the
    topic; it only prevents reusing cases from the tuning/evidence pack.
    """
    source_cases = list(source_pack.get("cases") or [])
    source_conversations = {
        str((case.get("source") or {}).get("conversation_id") or "")
        for case in source_cases
        if (case.get("source") or {}).get("conversation_id")
    }
    source_prompt_keys = {
        _dedupe_key(str(case.get("prompt") or ""))
        for case in source_cases
        if case.get("prompt")
    }
    blind_candidates = [
        candidate for candidate in candidates
        if candidate.conversation_id not in source_conversations
        and _dedupe_key(candidate.prompt) not in source_prompt_keys
        and not (set(candidate.quality_flags) & BLIND_REJECT_FLAGS)
    ]
    selected = _select_balanced_unique_conversations(
        blind_candidates,
        limit_per_type=limit_per_type,
        min_quality=min_quality,
    )
    cases = [_case_payload(candidate, idx) for idx, candidate in enumerate(selected, start=1)]
    return {
        "pack": pack_name,
        "source_pack": source_pack.get("pack"),
        "case_count": len(cases),
        "selection": {
            "blind_exclusion": "conversation_id_and_prompt_dedupe_key",
            "excluded_conversation_count": len(source_conversations),
            "excluded_prompt_count": len(source_prompt_keys),
            "candidate_count_before_exclusion": len(candidates),
            "candidate_count_after_exclusion": len(blind_candidates),
            "rejected_quality_flags": sorted(BLIND_REJECT_FLAGS),
            "limit_per_type": limit_per_type,
            "min_quality": min_quality,
            "task_types": sorted({case["task_type"] for case in cases}),
        },
        "cases": cases,
    }


def _select_balanced_unique_conversations(
    candidates: list[Candidate],
    *,
    limit_per_type: int,
    min_quality: int,
) -> list[Candidate]:
    selected: list[Candidate] = []
    remaining = list(candidates)
    while remaining:
        batch = select_balanced(remaining, limit_per_type=limit_per_type, min_quality=min_quality)
        if not batch:
            break
        changed = False
        used_conversations = {item.conversation_id for item in selected}
        for candidate in batch:
            if candidate.conversation_id in used_conversations:
                continue
            if sum(1 for item in selected if item.task_type == candidate.task_type) >= limit_per_type:
                continue
            selected.append(candidate)
            used_conversations.add(candidate.conversation_id)
            changed = True
        if all(sum(1 for item in selected if item.task_type == task_type) >= limit_per_type for task_type in {item.task_type for item in remaining}):
            break
        selected_keys = {_dedupe_key(item.prompt) for item in selected}
        selected_conversations = {item.conversation_id for item in selected}
        remaining = [
            item for item in remaining
            if item.conversation_id not in selected_conversations
            and _dedupe_key(item.prompt) not in selected_keys
        ]
        if not changed:
            break
    return selected


def _case_payload(candidate: Candidate, idx: int) -> dict[str, Any]:
    case = build_case(candidate.prompt, task_type=candidate.task_type)
    return {
        "id": f"blind_{idx:03d}_{candidate.task_type}",
        "source": {
            "title": candidate.title,
            "file": candidate.source_file,
            "conversation_id": candidate.conversation_id,
        },
        "task_type": candidate.task_type,
        "prompt": candidate.prompt,
        "reference_response_excerpt": candidate.reference_response[:1200],
        "curation": {
            "keyword_score": candidate.score,
            "quality_score": candidate.quality_score,
            "quality_flags": list(candidate.quality_flags),
            "blind_selection": True,
        },
        "expected_receipts": list(case.expected_receipts),
        "required_concepts": list(case.required_concepts),
        "forbidden_claims": list(case.forbidden_claims),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a blind replay pack excluding source-pack cases.")
    parser.add_argument("--source-pack", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--export-dir", type=Path, default=EXPORT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit-per-type", type=int, default=3)
    parser.add_argument("--min-quality", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_pack = json.loads(args.source_pack.read_text(encoding="utf-8-sig"))
    candidates = collect_candidates(args.export_dir)
    pack = build_blind_pack(
        source_pack=source_pack,
        candidates=candidates,
        limit_per_type=max(1, args.limit_per_type),
        min_quality=max(0, args.min_quality),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["result_path"] = str(args.out)
    if args.json:
        print(json.dumps(pack, indent=2))
    else:
        print(f"Built {pack['pack']} with {pack['case_count']} cases")
        print(f"Candidates after exclusion: {pack['selection']['candidate_count_after_exclusion']}")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
