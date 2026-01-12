#!/usr/bin/env python3
"""Evaluate a CRT learned-suggestions model and write an eval artifact.

This evaluates the suggestion-only learned model (joblib sklearn Pipeline) against
examples derived from contradiction ledger entries.

It produces a JSON artifact that can be plotted over time to track model evolution.

Usage examples:
  D:/AI_round2/.venv/Scripts/python.exe crt_learn_eval.py \
    --artifacts-dir artifacts/adaptive_all_3x200_seed1337_postgates_20260111 \
    --model artifacts/learned_suggestions.latest.joblib \
    --out artifacts/learned_suggestions.latest.eval.json

  # Evaluate a timestamped model
  D:/AI_round2/.venv/Scripts/python.exe crt_learn_eval.py \
    --memory-db artifacts/crt_stress_memory.20260111_120000.db \
    --ledger-db artifacts/crt_stress_ledger.20260111_120000.db \
    --model artifacts/learned_suggestions.20260110_081530.joblib \
    --out artifacts/learned_suggestions.20260110_081530.eval.json

Notes:
- This is not a "belief model"; it only predicts actions like prefer_latest vs ask_clarify.
- Data is weakly-labeled from contradictions; this eval is mainly to track drift and regressions.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _fetch_all_contradictions(db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, confidence_delta, status, contradiction_type, query, summary FROM contradictions"
    )
    rows = cur.fetchall()
    conn.close()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "ledger_id": r[0],
                "timestamp": float(r[1]),
                "old_memory_id": r[2],
                "new_memory_id": r[3],
                "drift_mean": float(r[4]),
                "confidence_delta": float(r[5] or 0.0),
                "status": r[6],
                "contradiction_type": r[7] or "conflict",
                "query": r[8],
                "summary": r[9],
            }
        )
    return out


def _fetch_memory_text_and_scores(db_path: str, memory_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not memory_ids:
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    qmarks = ",".join(["?"] * len(memory_ids))
    cur.execute(
        f"SELECT memory_id, text, timestamp, trust, confidence, source FROM memories WHERE memory_id IN ({qmarks})",
        memory_ids,
    )
    rows = cur.fetchall()
    conn.close()

    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        out[r[0]] = {
            "text": r[1],
            "timestamp": float(r[2]),
            "trust": float(r[3]),
            "confidence": float(r[4]),
            "source": str(r[5]),
        }
    return out


def _fetch_all_memories(db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT memory_id, text, timestamp, trust, confidence, source FROM memories")
    rows = cur.fetchall()
    conn.close()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "memory_id": r[0],
                "text": r[1],
                "timestamp": float(r[2]),
                "trust": float(r[3]),
                "confidence": float(r[4]),
                "source": str(r[5]),
            }
        )
    return out


def _count_open_contradictions(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM contradictions WHERE status = ?", ("open",))
        n = int(cur.fetchone()[0])
    except Exception:
        n = 0
    conn.close()
    return n


def _has_revision_keyword(text: str) -> int:
    t = (text or "").lower()
    for kw in ("actually", "correction", "i meant", "not ", "wrong", "mistake"):
        if kw in t:
            return 1
    return 0


def _is_preference_slot(slot: str) -> bool:
    s = (slot or "").lower()
    return s.endswith("_preference") or s.startswith("favorite_") or "preference" in s or "favorite" in s


def _has_preference_language(text: str) -> int:
    t = (text or "").lower()
    for kw in ("i prefer", "i hate", "i love", "rather than", "instead of", "favorite"):
        if kw in t:
            return 1
    return 0


def _collect_labeled_examples(
    *,
    mem_db_path: str,
    led_db_path: str,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    from personal_agent.fact_slots import extract_fact_slots

    X: List[Dict[str, Any]] = []
    y: List[str] = []

    contras = _fetch_all_contradictions(led_db_path)
    total_contras = len(contras)

    memory_ids: List[str] = []
    for c in contras:
        memory_ids.append(c["old_memory_id"])
        memory_ids.append(c["new_memory_id"])
    mem_map = _fetch_memory_text_and_scores(mem_db_path, list(dict.fromkeys(memory_ids)))

    all_mems = _fetch_all_memories(mem_db_path)
    slot_norm_values: Dict[str, set] = {}
    slot_trust_values: Dict[str, List[float]] = {}
    slot_has_value: Dict[str, int] = {}
    for m in all_mems:
        facts = extract_fact_slots(m.get("text", ""))
        if not facts:
            continue
        trust = _safe_float(m.get("trust"), 0.0)
        for slot, fact in facts.items():
            slot_has_value[slot] = 1
            slot_norm_values.setdefault(slot, set()).add(fact.normalized)
            slot_trust_values.setdefault(slot, []).append(trust)

    open_contras_count = _count_open_contradictions(led_db_path)

    for c in contras:
        old = mem_map.get(c["old_memory_id"], {})
        new = mem_map.get(c["new_memory_id"], {})
        old_text = old.get("text", "")
        new_text = new.get("text", "")
        if not old_text or not new_text:
            continue

        old_facts = extract_fact_slots(old_text)
        new_facts = extract_fact_slots(new_text)
        overlapping = set(old_facts.keys()) & set(new_facts.keys())
        if not overlapping:
            continue

        for slot in overlapping:
            if old_facts[slot].normalized == new_facts[slot].normalized:
                continue

            ctype = (c.get("contradiction_type") or "conflict").lower()
            rev_kw = _has_revision_keyword(new_text)
            pref_kw = _has_preference_language(new_text)
            if ctype in ("revision", "temporal", "refinement") or rev_kw or _is_preference_slot(slot) or pref_kw:
                label = "prefer_latest"
            else:
                label = "ask_clarify"

            trust_list = slot_trust_values.get(slot, [])
            trust_max = max(trust_list) if trust_list else 0.0
            trust_min = min(trust_list) if trust_list else 0.0
            features = {
                "slot": slot,
                "distinct_values": len({v for v in slot_norm_values.get(slot, set()) if v}),
                "open_contradictions_count": open_contras_count,
                "trust_max": trust_max,
                "trust_min": trust_min,
                "trust_gap": trust_max - trust_min,
                "has_value": slot_has_value.get(slot, 0),
            }

            X.append(features)
            y.append(label)

    meta = {
        "contradictions_scanned": int(total_contras),
        "examples": int(len(X)),
    }
    return X, y, meta


def _choose_runs_from_artifacts_dir(artifacts_dir: Path, max_runs: int) -> List[Tuple[str, str]]:
    mem_re = re.compile(r"^crt_stress_memory\.(?P<runid>\d{8}_\d{6})\.db$")
    led_re = re.compile(r"^crt_stress_ledger\.(?P<runid>\d{8}_\d{6})\.db$")

    mem_map_paths: Dict[str, str] = {}
    led_map_paths: Dict[str, str] = {}
    for p in artifacts_dir.glob("*.db"):
        m = mem_re.match(p.name)
        if m:
            mem_map_paths[m.group("runid")] = str(p)
            continue
        m = led_re.match(p.name)
        if m:
            led_map_paths[m.group("runid")] = str(p)

    run_ids = sorted(set(mem_map_paths.keys()) & set(led_map_paths.keys()))
    if max_runs and max_runs > 0:
        run_ids = run_ids[-max_runs:]
    runs: List[Tuple[str, str]] = []
    for rid in run_ids:
        runs.append((mem_map_paths[rid], led_map_paths[rid]))
    return runs


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate CRT learned suggestion model")
    ap.add_argument("--model", required=True, help="Path to joblib model")
    ap.add_argument("--out", required=True, help="Output eval JSON path")
    ap.add_argument("--memory-db", required=False, help="Path to memory sqlite db")
    ap.add_argument("--ledger-db", required=False, help="Path to ledger sqlite db")
    ap.add_argument("--artifacts-dir", required=False, default=None, help="Directory containing crt_stress_memory.*.db and crt_stress_ledger.*.db")
    ap.add_argument("--max-runs", type=int, default=0, help="If >0, use only the most recent N runs from artifacts-dir")
    ap.add_argument("--min-examples", type=int, default=20, help="Minimum examples required to evaluate")
    args = ap.parse_args(argv)

    model_path = Path(args.model)
    if not model_path.exists():
        raise SystemExit(f"model not found: {model_path}")

    runs: List[Tuple[str, str]] = []
    if args.artifacts_dir:
        art = Path(args.artifacts_dir)
        if not art.exists():
            raise SystemExit(f"artifacts-dir not found: {art}")
        runs = _choose_runs_from_artifacts_dir(art, int(args.max_runs))
        if not runs:
            raise SystemExit("No paired memory/ledger DBs found in artifacts-dir")
    else:
        if not args.memory_db or not args.ledger_db:
            raise SystemExit("Provide either --artifacts-dir or both --memory-db and --ledger-db")
        runs = [(args.memory_db, args.ledger_db)]

    try:
        import joblib  # type: ignore

        model = joblib.load(str(model_path))
    except Exception as e:
        raise SystemExit(f"Failed to load model: {e}")

    X_all: List[Dict[str, Any]] = []
    y_all: List[str] = []
    scanned = 0
    for mem_db, led_db in runs:
        X, y, meta = _collect_labeled_examples(mem_db_path=mem_db, led_db_path=led_db)
        scanned += int(meta.get("contradictions_scanned") or 0)
        X_all.extend(X)
        y_all.extend(y)

    if len(X_all) < int(args.min_examples):
        raise SystemExit(
            f"Not enough examples to evaluate: {len(X_all)} < {int(args.min_examples)}. "
            "Run more stress tests first, or lower --min-examples."
        )

    # Predict
    try:
        y_pred = list(model.predict(X_all))
    except Exception as e:
        raise SystemExit(f"Prediction failed: {e}")

    true_label_counts: Dict[str, int] = {}
    pred_label_counts: Dict[str, int] = {}
    for yt, yp in zip(y_all, y_pred):
        true_label_counts[str(yt)] = int(true_label_counts.get(str(yt), 0) + 1)
        pred_label_counts[str(yp)] = int(pred_label_counts.get(str(yp), 0) + 1)

    total_preds = int(sum(pred_label_counts.values()) or 0)
    prefer_latest_rate_pred = (
        float(pred_label_counts.get("prefer_latest", 0)) / total_preds if total_preds else None
    )

    # Metrics (keep lightweight)
    try:
        from sklearn.metrics import accuracy_score, confusion_matrix  # type: ignore

        acc = float(accuracy_score(y_all, y_pred))
        labels = sorted(list({str(x) for x in (y_all + y_pred)}))
        cm = confusion_matrix(y_all, y_pred, labels=labels)
        cm_list = [[int(v) for v in row] for row in cm.tolist()]
    except Exception:
        acc = None
        labels = sorted(list({str(x) for x in (y_all + y_pred)}))
        cm_list = []

    # By-slot metrics
    by_slot: Dict[str, Dict[str, Any]] = {}
    for features, y_true, y_hat in zip(X_all, y_all, y_pred):
        slot = str(features.get("slot") or "unknown")
        ent = by_slot.setdefault(slot, {"count": 0, "correct": 0, "accuracy": None, "label_counts": {}, "pred_counts": {}})
        ent["count"] += 1
        if str(y_true) == str(y_hat):
            ent["correct"] += 1
        ent["label_counts"][str(y_true)] = int(ent["label_counts"].get(str(y_true), 0) + 1)
        ent["pred_counts"][str(y_hat)] = int(ent["pred_counts"].get(str(y_hat), 0) + 1)

    for slot, ent in by_slot.items():
        c = int(ent.get("count") or 0)
        ent["accuracy"] = (float(ent.get("correct") or 0) / c) if c else None

    # Artifact
    try:
        from personal_agent.artifact_store import sha256_file, now_iso_utc

        model_sha = sha256_file(model_path)
        evaluated_at = now_iso_utc()
    except Exception:
        model_sha = None
        evaluated_at = None

    payload = {
        "type": "crt_learned_suggestions_eval",
        "version": "v1",
        "evaluated_at": evaluated_at,
        "model": {
            "path": str(model_path),
            "sha256": model_sha,
        },
        "data": {
            "artifacts_dir": str(args.artifacts_dir) if args.artifacts_dir else None,
            "runs_used": int(len(runs)),
            "total_contradictions_scanned": int(scanned),
            "min_examples": int(args.min_examples),
        },
        "metrics": {
            "examples": int(len(X_all)),
            "accuracy": acc,
            "true_label_counts": true_label_counts,
            "pred_label_counts": pred_label_counts,
            "prefer_latest_rate_pred": prefer_latest_rate_pred,
            "labels": labels,
            "confusion_matrix": cm_list,
            "by_slot": by_slot,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote eval: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
