"""Background learner for trust-gated DNNT distillation."""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import torch

from .data_extractor import TrainingExample
from .model import DNNTConfig, DNNTMicroTransformer, SimpleTokenizer
from .trainer import ReasoningTrainer, TrainingConfig

logger = logging.getLogger(__name__)


@dataclass
class BackgroundLearningConfig:
    output_dir: str = "models/dnnt"
    collected_examples_path: str = "data/dnnt_collected_training_data.jsonl"
    collapse_trails_db_path: str = "personal_agent/crt_collapse_trails.db"
    active_learning_db_path: str = "personal_agent/active_learning.db"
    state_path: str = "data/dnnt_background_state.json"
    min_new_examples: int = 24
    max_examples_per_cycle: int = 512
    max_steps_per_cycle: int = 200
    batch_size: int = 16
    learning_rate: float = 1e-4
    device: str = "auto"
    include_collapse_trails: bool = True
    include_active_learning: bool = True
    include_thumbs_up_interactions: bool = True
    poll_interval_sec: int = 180


@dataclass
class BackgroundLearningState:
    collected_offset: int = 0
    collapse_last_ts: float = 0.0
    corrections_last_ts: float = 0.0
    interactions_last_ts: float = 0.0
    cycles_completed: int = 0
    last_cycle_ts: float = 0.0
    last_cycle_examples: int = 0
    last_cycle_status: str = "never_ran"


def _json_load(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _truncate(text: Any, limit: int) -> str:
    out = str(text or "").strip()
    if len(out) <= limit:
        return out
    return out[: max(1, limit - 1)].rstrip() + "."


class DNNTBackgroundLearner:
    """Periodically fine-tunes DNNT on trust-gated lineage data."""

    def __init__(self, config: Optional[BackgroundLearningConfig] = None):
        self.config = config or BackgroundLearningConfig()
        self.state_path = Path(self.config.state_path)
        self.state = self._load_state()

    def _load_state(self) -> BackgroundLearningState:
        data = _json_load(self.state_path, asdict(BackgroundLearningState()))
        try:
            return BackgroundLearningState(**data)
        except Exception:
            return BackgroundLearningState()

    def _save_state(self) -> None:
        _json_dump(self.state_path, asdict(self.state))

    @staticmethod
    def _safe_json(value: Any) -> Any:
        try:
            return json.loads(value) if isinstance(value, str) and value.strip() else value
        except Exception:
            return None

    def _extract_facts_from_payload(self, payload: Dict[str, Any]) -> List[str]:
        facts: List[str] = []
        for item in payload.get("facts") or []:
            text = str(item or "").strip()
            if text:
                facts.append(_truncate(text, 260))

        for key in ("retrieved_memories", "prompt_memories"):
            for mem in payload.get(key) or []:
                if not isinstance(mem, dict):
                    continue
                text = _truncate(mem.get("text"), 220)
                if not text:
                    continue
                trust = mem.get("trust")
                if isinstance(trust, (int, float)):
                    facts.append(f"{text} (trust={float(trust):.2f})")
                else:
                    facts.append(text)

        deduped: List[str] = []
        seen: set[str] = set()
        for item in facts:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
            if len(deduped) >= 12:
                break
        return deduped

    def _extract_thinking_from_payload(self, payload: Dict[str, Any]) -> str:
        direct = str(payload.get("thinking") or payload.get("analysis") or "").strip()
        if direct:
            return _truncate(direct, 1200)

        trace = payload.get("reasoning_trace")
        if isinstance(trace, dict):
            steps = trace.get("thinking_steps") or []
            if isinstance(steps, list):
                chunks: List[str] = []
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    content = str(step.get("content") or "").strip()
                    if content:
                        chunks.append(content)
                if chunks:
                    return _truncate("\n".join(chunks), 1200)

        return "Derived from gate-cleared lineage."

    @staticmethod
    def _as_example(
        *,
        query: str,
        response: str,
        facts: Optional[Iterable[str]] = None,
        thinking: str = "",
        confidence: float = 0.7,
        thread_id: str = "",
    ) -> Optional[TrainingExample]:
        q = str(query or "").strip()
        r = str(response or "").strip()
        if not q or not r:
            return None
        fact_lines = [str(f).strip() for f in (facts or []) if str(f).strip()]
        return TrainingExample(
            query=_truncate(q, 500),
            response=_truncate(r, 1500),
            thinking=_truncate(thinking or "Reasoning unavailable.", 1500),
            facts=fact_lines[:12],
            confidence=float(confidence),
            thread_id=str(thread_id or ""),
        )

    def _load_collected_examples(self, limit: int) -> Tuple[List[TrainingExample], int]:
        path = Path(self.config.collected_examples_path)
        if not path.exists():
            return [], self.state.collected_offset

        items: List[TrainingExample] = []
        offset = self.state.collected_offset
        with open(path, "r", encoding="utf-8") as f:
            try:
                f.seek(offset)
            except Exception:
                f.seek(0)
            while len(items) < limit:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ex = TrainingExample(
                        query=str(data.get("query") or "").strip(),
                        facts=list(data.get("facts") or []),
                        thinking=str(data.get("thinking") or "").strip(),
                        response=str(data.get("response") or "").strip(),
                        confidence=float(data.get("confidence") or 0.7),
                        thread_id=str(data.get("thread_id") or ""),
                    )
                    if ex.query and ex.response:
                        items.append(ex)
                except Exception:
                    continue
            next_offset = int(f.tell())
        return items, next_offset

    def _load_collapse_trails(self, limit: int) -> Tuple[List[TrainingExample], float]:
        if not self.config.include_collapse_trails:
            return [], self.state.collapse_last_ts

        db = Path(self.config.collapse_trails_db_path)
        if not db.exists():
            return [], self.state.collapse_last_ts

        out: List[TrainingExample] = []
        newest_ts = self.state.collapse_last_ts
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT timestamp, thread_id, query_text, answer_text, payload_json,
                       gates_passed, unresolved_contradictions_total
                FROM collapse_trails
                WHERE timestamp > ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (float(self.state.collapse_last_ts), int(limit)),
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            ts = float(row["timestamp"] or 0.0)
            newest_ts = max(newest_ts, ts)
            gates_passed = int(row["gates_passed"] or 0) == 1
            unresolved = int(row["unresolved_contradictions_total"] or 0)
            if not gates_passed:
                continue
            if unresolved > 0:
                continue
            payload = self._safe_json(row["payload_json"]) or {}
            if not isinstance(payload, dict):
                payload = {}
            ex = self._as_example(
                query=row["query_text"],
                response=row["answer_text"],
                facts=self._extract_facts_from_payload(payload),
                thinking=self._extract_thinking_from_payload(payload),
                confidence=float(payload.get("confidence") or 0.7),
                thread_id=row["thread_id"],
            )
            if ex is not None:
                out.append(ex)
        return out, newest_ts

    def _load_active_learning_examples(
        self, limit: int
    ) -> Tuple[List[TrainingExample], float, float]:
        if not self.config.include_active_learning:
            return [], self.state.corrections_last_ts, self.state.interactions_last_ts

        db = Path(self.config.active_learning_db_path)
        if not db.exists():
            return [], self.state.corrections_last_ts, self.state.interactions_last_ts

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        corrections_newest = self.state.corrections_last_ts
        interactions_newest = self.state.interactions_last_ts
        out: List[TrainingExample] = []

        try:
            correction_rows = conn.execute(
                """
                SELECT c.timestamp AS ts,
                       c.correction_type AS correction_type,
                       c.field_name AS field_name,
                       c.correct_value AS correct_value,
                       c.user_comment AS user_comment,
                       i.thread_id AS thread_id,
                       i.query AS query,
                       i.facts_injected AS facts_injected
                FROM corrections c
                JOIN interaction_logs i ON i.interaction_id = c.interaction_id
                WHERE c.timestamp > ?
                ORDER BY c.timestamp ASC
                LIMIT ?
                """,
                (float(self.state.corrections_last_ts), int(limit)),
            ).fetchall()

            for row in correction_rows:
                ts = float(row["ts"] or 0.0)
                corrections_newest = max(corrections_newest, ts)
                target = str(row["correct_value"] or row["user_comment"] or "").strip()
                if not target:
                    continue
                facts_raw = self._safe_json(row["facts_injected"]) or []
                facts: List[str] = []
                if isinstance(facts_raw, list):
                    for item in facts_raw:
                        if isinstance(item, dict):
                            txt = _truncate(item.get("text"), 220)
                            if txt:
                                facts.append(txt)
                thinking = (
                    f"User correction ({row['correction_type']})"
                    + (f" on {row['field_name']}" if row["field_name"] else "")
                    + "."
                )
                ex = self._as_example(
                    query=row["query"],
                    response=target,
                    facts=facts,
                    thinking=thinking,
                    confidence=0.95,
                    thread_id=row["thread_id"],
                )
                if ex is not None:
                    out.append(ex)

            if self.config.include_thumbs_up_interactions:
                thumbs_rows = conn.execute(
                    """
                    SELECT timestamp, thread_id, query, response, facts_injected
                    FROM interaction_logs
                    WHERE timestamp > ?
                      AND user_reaction = 'thumbs_up'
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (float(self.state.interactions_last_ts), int(limit)),
                ).fetchall()

                for row in thumbs_rows:
                    ts = float(row["timestamp"] or 0.0)
                    interactions_newest = max(interactions_newest, ts)
                    facts_raw = self._safe_json(row["facts_injected"]) or []
                    facts: List[str] = []
                    if isinstance(facts_raw, list):
                        for item in facts_raw:
                            if isinstance(item, dict):
                                txt = _truncate(item.get("text"), 220)
                                if txt:
                                    facts.append(txt)
                    ex = self._as_example(
                        query=row["query"],
                        response=row["response"],
                        facts=facts,
                        thinking="User gave explicit positive feedback.",
                        confidence=0.9,
                        thread_id=row["thread_id"],
                    )
                    if ex is not None:
                        out.append(ex)
        finally:
            conn.close()

        return out, corrections_newest, interactions_newest

    @staticmethod
    def _dedupe_examples(examples: Iterable[TrainingExample]) -> List[TrainingExample]:
        out: List[TrainingExample] = []
        seen: set[Tuple[str, str]] = set()
        for ex in examples:
            key = (ex.query.strip().lower(), ex.response.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(ex)
        return out

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _load_or_init_model(self, device: str) -> Tuple[DNNTMicroTransformer, SimpleTokenizer]:
        model_dir = Path(self.config.output_dir) / "model"
        model_pt = model_dir / "model.pt"
        if model_pt.exists():
            model = DNNTMicroTransformer.load(str(model_dir), device=device)
            tok_path = model_dir / "tokenizer.json"
            tokenizer = SimpleTokenizer.load(str(tok_path)) if tok_path.exists() else SimpleTokenizer()
            return model, tokenizer
        config = DNNTConfig(vocab_size=8000)
        return DNNTMicroTransformer(config).to(device), SimpleTokenizer()

    def run_once(self) -> Dict[str, Any]:
        """Run one training cycle and return cycle summary."""
        start = time.time()
        limit = int(self.config.max_examples_per_cycle)

        collected, next_offset = self._load_collected_examples(limit=limit)
        remaining = max(0, limit - len(collected))
        trails, next_trail_ts = self._load_collapse_trails(limit=remaining)
        remaining = max(0, remaining - len(trails))
        active, next_corr_ts, next_int_ts = self._load_active_learning_examples(limit=remaining)

        combined = self._dedupe_examples([*collected, *trails, *active])
        random.shuffle(combined)
        examples = combined[:limit]

        summary: Dict[str, Any] = {
            "new_collected": len(collected),
            "new_collapse_trails": len(trails),
            "new_active_learning": len(active),
            "candidate_examples": len(examples),
            "trained": False,
            "duration_sec": 0.0,
        }

        if len(examples) < int(self.config.min_new_examples):
            self.state.collected_offset = next_offset
            self.state.collapse_last_ts = next_trail_ts
            self.state.corrections_last_ts = next_corr_ts
            self.state.interactions_last_ts = next_int_ts
            self.state.last_cycle_ts = time.time()
            self.state.last_cycle_examples = len(examples)
            self.state.last_cycle_status = (
                f"skipped_insufficient_examples({len(examples)}/{self.config.min_new_examples})"
            )
            self._save_state()
            summary["duration_sec"] = round(time.time() - start, 3)
            summary["status"] = self.state.last_cycle_status
            return summary

        split = max(1, int(len(examples) * 0.9))
        train_examples = examples[:split]
        val_examples = examples[split:] if split < len(examples) else []

        device = self._resolve_device(self.config.device)
        model, tokenizer = self._load_or_init_model(device)
        steps_per_epoch = max(1, len(train_examples) // max(1, int(self.config.batch_size)))
        max_steps = max(steps_per_epoch, int(self.config.max_steps_per_cycle))

        train_config = TrainingConfig(
            batch_size=int(self.config.batch_size),
            learning_rate=float(self.config.learning_rate),
            max_steps=max_steps,
            save_every=max(50, max_steps // 2),
            eval_every=max(25, max_steps // 4),
            log_every=max(10, max_steps // 10),
            device=device,
            mixed_precision=(device == "cuda"),
            output_dir=str(self.config.output_dir),
        )

        trainer = ReasoningTrainer(
            config=train_config,
            tokenizer=tokenizer,
            train_examples=train_examples,
            val_examples=val_examples,
            model=model,
        )
        trainer.train()

        self.state.collected_offset = next_offset
        self.state.collapse_last_ts = next_trail_ts
        self.state.corrections_last_ts = next_corr_ts
        self.state.interactions_last_ts = next_int_ts
        self.state.cycles_completed += 1
        self.state.last_cycle_ts = time.time()
        self.state.last_cycle_examples = len(examples)
        self.state.last_cycle_status = "trained"
        self._save_state()

        summary["trained"] = True
        summary["train_examples"] = len(train_examples)
        summary["val_examples"] = len(val_examples)
        summary["max_steps"] = max_steps
        summary["duration_sec"] = round(time.time() - start, 3)
        summary["status"] = "trained"
        return summary

    def run_forever(self) -> None:
        logger.info(
            "[DNNTBackgroundLearner] starting loop (poll_interval=%ss, min_new_examples=%s)",
            self.config.poll_interval_sec,
            self.config.min_new_examples,
        )
        while True:
            try:
                summary = self.run_once()
                logger.info("[DNNTBackgroundLearner] cycle summary: %s", summary)
            except Exception as e:
                logger.exception("[DNNTBackgroundLearner] cycle failed: %s", e)
            time.sleep(max(1, int(self.config.poll_interval_sec)))


def run_background_learning_once(config: Optional[BackgroundLearningConfig] = None) -> Dict[str, Any]:
    learner = DNNTBackgroundLearner(config=config)
    return learner.run_once()


def run_background_learning_forever(config: Optional[BackgroundLearningConfig] = None) -> None:
    learner = DNNTBackgroundLearner(config=config)
    learner.run_forever()

