"""Build a small router replay pack from exported ChatGPT conversations."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.local_router_cli import build_case
from labs.meaning_compression_lab.local_router_eval import classify_request


EXPORT_DIR = Path("data/chatgpt_export")
DEFAULT_OUT = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_v0.json")


@dataclass(frozen=True)
class Candidate:
    title: str
    source_file: str
    conversation_id: str
    task_type: str
    prompt: str
    reference_response: str
    score: int


TASK_KEYWORDS = {
    "grant_business": (
        "grant",
        "business",
        "roadmap",
        "fundable",
        "small-business",
        "small business",
    ),
    "architecture_synthesis": (
        "crt",
        "aether",
        "mirus",
        "holden",
        "sse",
        "local model",
        "semantic",
        "architecture",
        "scaffold",
    ),
    "personal_synthesis": (
        "pattern",
        "who am i",
        "what do you see",
        "vibe",
        "spiral",
        "road america",
        "body",
        "rebuilding",
    ),
    "code_reasoning": (
        "code",
        "implement",
        "debug",
        "repo",
        "test",
        "python",
    ),
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(password|passwd|api[_-]?key|token|secret)\s*[:=]\s*\S+"),
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
)


def build_replay_pack(
    *,
    export_dir: Path = EXPORT_DIR,
    limit_per_type: int = 4,
    out_path: Path = DEFAULT_OUT,
) -> dict[str, Any]:
    candidates = collect_candidates(export_dir)
    selected = select_balanced(candidates, limit_per_type=limit_per_type)
    cases = []
    for idx, candidate in enumerate(selected, start=1):
        case = build_case(candidate.prompt, task_type=candidate.task_type)
        cases.append(
            {
                "id": f"gptlog_{idx:03d}_{candidate.task_type}",
                "source": {
                    "title": candidate.title,
                    "file": candidate.source_file,
                    "conversation_id": candidate.conversation_id,
                },
                "task_type": candidate.task_type,
                "prompt": candidate.prompt,
                "reference_response_excerpt": candidate.reference_response[:1200],
                "expected_receipts": list(case.expected_receipts),
                "required_concepts": list(case.required_concepts),
                "forbidden_claims": list(case.forbidden_claims),
            }
        )
    out = {
        "pack": "local_router_replay_v0",
        "source": str(export_dir),
        "case_count": len(cases),
        "selection": {
            "limit_per_type": limit_per_type,
            "task_types": sorted({case["task_type"] for case in cases}),
        },
        "cases": cases,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    out["result_path"] = str(out_path)
    return out


def collect_candidates(export_dir: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in sorted(export_dir.glob("conversations-*.json")):
        try:
            conversations = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for conversation in conversations:
            title = str(conversation.get("title") or "")
            conversation_id = str(conversation.get("conversation_id") or conversation.get("id") or "")
            turns = _linear_turns(conversation.get("mapping") or {})
            for i, turn in enumerate(turns[:-1]):
                if turn["role"] != "user":
                    continue
                assistant = _next_assistant(turns, i + 1)
                if not assistant:
                    continue
                prompt = sanitize_text(turn["text"])
                response = sanitize_text(assistant["text"])
                if not _usable(prompt, response):
                    continue
                task_type, score = classify_prompt_for_pack(prompt, title)
                if score <= 0:
                    continue
                candidates.append(
                    Candidate(
                        title=sanitize_text(title)[:160],
                        source_file=str(path),
                        conversation_id=conversation_id,
                        task_type=task_type,
                        prompt=prompt,
                        reference_response=response,
                        score=score,
                    )
                )
    candidates.sort(key=lambda item: (item.score, len(item.prompt)), reverse=True)
    return candidates


def select_balanced(candidates: list[Candidate], *, limit_per_type: int) -> list[Candidate]:
    selected = []
    counts: dict[str, int] = {}
    seen_prompts: set[str] = set()
    priority = ("architecture_synthesis", "personal_synthesis", "grant_business", "code_reasoning")
    for task_type in priority:
        for candidate in candidates:
            if candidate.task_type != task_type:
                continue
            key = _dedupe_key(candidate.prompt)
            if key in seen_prompts:
                continue
            if counts.get(task_type, 0) >= limit_per_type:
                break
            selected.append(candidate)
            seen_prompts.add(key)
            counts[task_type] = counts.get(task_type, 0) + 1
    return selected


def classify_prompt_for_pack(prompt: str, title: str = "") -> tuple[str, int]:
    text = f"{title} {prompt}".lower()
    best_type = classify_request(prompt)
    best_score = 0
    for task_type, keywords in TASK_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_type = task_type
            best_score = score
    return best_type, best_score


def sanitize_text(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text)).strip()
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _linear_turns(mapping: dict[str, Any]) -> list[dict[str, str]]:
    turns = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        role = ((message.get("author") or {}).get("role") or "").lower()
        if role not in {"user", "assistant"}:
            continue
        content = message.get("content") or {}
        if content.get("content_type") != "text":
            continue
        parts = content.get("parts") or []
        text = "\n".join(str(part) for part in parts if isinstance(part, str)).strip()
        if text:
            turns.append(
                {
                    "role": role,
                    "text": text,
                    "time": str(message.get("create_time") or ""),
                }
            )
    return turns


def _next_assistant(turns: list[dict[str, str]], start: int) -> dict[str, str] | None:
    for turn in turns[start : start + 4]:
        if turn["role"] == "assistant":
            return turn
    return None


def _usable(prompt: str, response: str) -> bool:
    if len(prompt) < 30 or len(response) < 120:
        return False
    if len(prompt) > 1100:
        return False
    if _looks_like_dump(prompt):
        return False
    if _looks_like_assistant_quote(prompt):
        return False
    if not _has_user_request_shape(prompt):
        return False
    if any(pattern.search(prompt) for pattern in SECRET_PATTERNS):
        return False
    return True


def _dedupe_key(prompt: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", prompt.lower()).strip()[:180]


def _looks_like_dump(prompt: str) -> bool:
    lowered = prompt.lower()
    stripped = lowered.lstrip(" \"'“”")
    dump_markers = (
        "traceback (most recent call last)",
        "invoke-restmethod",
        "ps c:",
        "ps h:",
        "```",
        "file \"<stdin>\"",
        "npm ",
        "pip install",
        "curl ",
        "git ",
        "core update queue",
        "file purpose reason",
    )
    if any(marker in lowered for marker in dump_markers):
        return True
    if stripped.startswith(("def ", "class ", "import ", "from ")):
        return True
    if re.search(r"\b(def|class)\s+\w+\s*\(", prompt) and not _has_user_request_shape(prompt):
        return True
    # Reject prompts that are mostly a pasted report/list instead of a request.
    questionish = any(token in lowered for token in ("?", "can you", "what", "why", "how", "help", "think", "should", "let's"))
    punctuation_density = sum(1 for ch in prompt if ch in "{}[]@$=<>") / max(1, len(prompt))
    if punctuation_density > 0.025 and not questionish:
        return True
    if prompt.count("\n") > 8:
        return True
    return False


def _looks_like_assistant_quote(prompt: str) -> bool:
    lowered = prompt.lower().lstrip(" \"'“”")
    assistant_starts = (
        "got it.",
        "affirmative.",
        "it looks like",
        "conclusion",
        "baseline locked",
        "core update queue",
        "here's what i need",
        "if you recognize your failure",
        "in the email body",
        "captain",
    )
    if lowered.startswith(assistant_starts):
        return True
    if "agent says" in lowered:
        return True
    return False


def _has_user_request_shape(prompt: str) -> bool:
    lowered = prompt.lower()
    cues = (
        "?",
        "can you",
        "could you",
        "what",
        "why",
        "how",
        "help",
        "think",
        "should",
        "let's",
        "lets",
        "go ahead",
        "i need",
        "i want",
        "i'm",
        "im ",
        "nova",
        "okay",
        "so ",
    )
    return any(cue in lowered for cue in cues)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local-router replay pack from ChatGPT export.")
    parser.add_argument("--export-dir", type=Path, default=EXPORT_DIR)
    parser.add_argument("--limit-per-type", type=int, default=4)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = build_replay_pack(
        export_dir=args.export_dir,
        limit_per_type=args.limit_per_type,
        out_path=args.out,
    )
    _safe_print(json.dumps({k: v for k, v in out.items() if k != "cases"}, indent=2))
    for case in out["cases"]:
        _safe_print(f"- {case['id']}: {case['source']['title'][:80]} :: {case['prompt'][:120]}")


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
