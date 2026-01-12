#!/usr/bin/env python3
"""Train a small NN (MLP) to produce suggestion-only CRT recommendations.

This is NOT a model that changes beliefs. It learns a policy like:
- "prefer_latest" vs "ask_clarify" for slot-style questions.

Training data source (self-supervised / weak labels):
- Contradiction ledger entries + associated old/new memories
- Slot extraction over those texts

Usage example:
  D:/AI_round2/.venv/Scripts/python.exe crt_learn_train.py \
    --memory-db artifacts/crt_stress_memory.<runid>.db \
    --ledger-db artifacts/crt_stress_ledger.<runid>.db \
    --out artifacts/learned_suggestions.joblib

Then enable at runtime:
  set CRT_LEARNED_MODEL_PATH=artifacts/learned_suggestions.joblib

"""

from __future__ import annotations

import argparse
import sqlite3
import re
import json
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
    cur.execute("SELECT ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, confidence_delta, status, contradiction_type, query, summary FROM contradictions")
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
    return (
        s.endswith("_preference")
        or s.startswith("favorite_")
        or "preference" in s
        or "favorite" in s
    )


def _has_preference_language(text: str) -> int:
    t = (text or "").lower()
    for kw in ("i prefer", "i hate", "i love", "rather than", "instead of", "favorite"):
        if kw in t:
            return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Train CRT learned suggestion model (MLP, suggestion-only)")
    ap.add_argument("--memory-db", required=False, help="Path to memory sqlite db")
    ap.add_argument("--ledger-db", required=False, help="Path to ledger sqlite db")
    ap.add_argument("--artifacts-dir", required=False, default=None, help="Directory containing crt_stress_memory.*.db and crt_stress_ledger.*.db")
    ap.add_argument("--max-runs", type=int, default=0, help="If >0, use only the most recent N runs from artifacts-dir")
    ap.add_argument("--out", required=True, help="Output joblib path")
    ap.add_argument("--min-examples", type=int, default=20, help="Minimum examples required to train")
    args = ap.parse_args(argv)

    from personal_agent.fact_slots import extract_fact_slots

    runs: List[Tuple[str, str]] = []

    if args.artifacts_dir:
        art = Path(args.artifacts_dir)
        if not art.exists():
            raise SystemExit(f"artifacts-dir not found: {art}")

        mem_re = re.compile(r"^crt_stress_memory\.(?P<runid>\d{8}_\d{6})\.db$")
        led_re = re.compile(r"^crt_stress_ledger\.(?P<runid>\d{8}_\d{6})\.db$")

        mem_map_paths: Dict[str, str] = {}
        led_map_paths: Dict[str, str] = {}
        for p in art.glob("*.db"):
            m = mem_re.match(p.name)
            if m:
                mem_map_paths[m.group("runid")] = str(p)
                continue
            m = led_re.match(p.name)
            if m:
                led_map_paths[m.group("runid")] = str(p)

        run_ids = sorted(set(mem_map_paths.keys()) & set(led_map_paths.keys()))
        if args.max_runs and args.max_runs > 0:
            run_ids = run_ids[-args.max_runs :]
        if not run_ids:
            raise SystemExit("No paired memory/ledger DBs found in artifacts-dir")

        for rid in run_ids:
            runs.append((mem_map_paths[rid], led_map_paths[rid]))
    else:
        if not args.memory_db or not args.ledger_db:
            raise SystemExit("Provide either --artifacts-dir or both --memory-db and --ledger-db")
        runs.append((args.memory_db, args.ledger_db))

    X: List[Dict[str, Any]] = []
    y: List[str] = []

    total_contras = 0
    for mem_db_path, led_db_path in runs:
        contras = _fetch_all_contradictions(led_db_path)
        if not contras:
            continue
        total_contras += len(contras)

        memory_ids: List[str] = []
        for c in contras:
            memory_ids.append(c["old_memory_id"])
            memory_ids.append(c["new_memory_id"])
        mem_map = _fetch_memory_text_and_scores(mem_db_path, list(dict.fromkeys(memory_ids)))

        # Per-run slot stats to match runtime inference (conversation-local).
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

    if len(X) < args.min_examples:
        raise SystemExit(
            f"Not enough examples to train: {len(X)} < {args.min_examples}. "
            "Run more stress tests first, or lower --min-examples."
        )

    from sklearn.feature_extraction import DictVectorizer
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    import joblib

    model = Pipeline(
        steps=[
            ("vec", DictVectorizer(sparse=True)),
            ("scale", StandardScaler(with_mean=False)),
            (
                "clf",
                MLPClassifier(
                    hidden_layer_sizes=(32, 16),
                    activation="relu",
                    solver="adam",
                    max_iter=400,
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(X, y)

    joblib.dump(model, args.out)

    # Write a small, human-readable metadata sidecar for tracking evolution over time.
    # This intentionally avoids a strict schema so it can grow without breaking older runs.
    try:
        out_path = Path(args.out)
        meta_path = out_path.with_suffix(".meta.json")

        label_counts: Dict[str, int] = {}
        for lbl in y:
            label_counts[lbl] = int(label_counts.get(lbl, 0) + 1)

        try:
            classes = list(getattr(model, "classes_", []))
            if not classes and hasattr(model, "named_steps"):
                clf = model.named_steps.get("clf")
                classes = list(getattr(clf, "classes_", [])) if clf is not None else []
        except Exception:
            classes = []

        try:
            train_accuracy = float(model.score(X, y))
        except Exception:
            train_accuracy = None

        try:
            from personal_agent.artifact_store import sha256_file, now_iso_utc

            out_sha256 = sha256_file(out_path)
            trained_at = now_iso_utc()
        except Exception:
            out_sha256 = None
            trained_at = None

        try:
            import sklearn  # type: ignore

            sklearn_version = getattr(sklearn, "__version__", None)
        except Exception:
            sklearn_version = None

        meta = {
            "type": "crt_learned_suggestions_model",
            "version": "v1",
            "trained_at": trained_at,
            "out_path": str(out_path),
            "out_sha256": out_sha256,
            "python_version": sys.version.split()[0],
            "sklearn_version": sklearn_version,
            "examples": {
                "count": len(X),
                "label_counts": label_counts,
                "train_accuracy": train_accuracy,
                "classes": classes,
            },
            "data": {
                "artifacts_dir": str(args.artifacts_dir) if args.artifacts_dir else None,
                "runs_used": len(runs),
                "total_contradictions_scanned": int(total_contras),
                "memory_db": str(args.memory_db) if args.memory_db else None,
                "ledger_db": str(args.ledger_db) if args.ledger_db else None,
                "max_runs": int(args.max_runs),
                "min_examples": int(args.min_examples),
            },
        }

        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote metadata: {meta_path}")
    except Exception:
        # Metadata is best-effort; training output is the joblib.
        pass

    print(f"Trained learned-suggestions model on {len(X)} examples")
    if args.artifacts_dir:
        print(f"Runs used: {len(runs)} (total contradictions scanned: {total_contras})")
    print(f"Saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
