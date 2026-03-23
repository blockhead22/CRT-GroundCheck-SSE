"""Export contradiction data from live CRT databases and generate synthetic pairs."""

from __future__ import annotations

import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .labeler import AutoLabeler
from .types import BeliefType, ContradictionPair, PolicyAction


class LedgerExporter:
    """Read contradiction data from CRT SQLite databases and produce
    ContradictionPair instances suitable for training.
    """

    def __init__(self, db_paths: List[str]) -> None:
        self.db_paths = [str(p) for p in db_paths]
        self._labeler = AutoLabeler()

    # ── Public API ───────────────────────────────────────────────────────

    def export_pairs(self) -> List[ContradictionPair]:
        """Export all contradiction pairs found across the configured DBs."""
        pairs: List[ContradictionPair] = []
        for db_path in self.db_paths:
            path = Path(db_path)
            if not path.exists():
                continue
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                pairs.extend(self._extract_from_db(conn, db_path))
                conn.close()
            except Exception:
                continue
        return pairs

    def export_labeled(
        self,
    ) -> List[Tuple[ContradictionPair, BeliefType, PolicyAction]]:
        """Export pairs with auto-labels applied."""
        results: List[Tuple[ContradictionPair, BeliefType, PolicyAction]] = []
        for pair in self.export_pairs():
            belief, _ = self._labeler.label_belief(pair)
            policy, _ = self._labeler.label_policy(pair, belief)
            results.append((pair, belief, policy))
        return results

    # ── Synthetic data ───────────────────────────────────────────────────

    def generate_synthetic_pairs(
        self, n: int = 200
    ) -> List[Tuple[ContradictionPair, BeliefType, PolicyAction]]:
        """Generate *n* realistic synthetic contradiction pairs covering all
        four BeliefTypes and three PolicyActions.
        """
        rng = random.Random(42)
        results: List[Tuple[ContradictionPair, BeliefType, PolicyAction]] = []

        templates = _build_templates()

        # Target distribution: roughly balanced across belief types
        per_type = max(n // len(BeliefType), 1)

        for belief_type in BeliefType:
            type_templates = templates[belief_type]
            for i in range(per_type):
                tmpl = type_templates[i % len(type_templates)]
                pair = _template_to_pair(tmpl, belief_type, rng)
                # Use labeler for policy (but we already know the belief type)
                policy, _ = self._labeler.label_policy(pair, belief_type)

                # Force some policy diversity for CONFLICT type
                if belief_type == BeliefType.CONFLICT:
                    if i % 3 == 0:
                        # High-trust both sides -> ASK_USER
                        pair.old_trust = rng.uniform(0.82, 0.95)
                        pair.new_trust = rng.uniform(0.82, 0.95)
                        policy = PolicyAction.ASK_USER
                    elif i % 3 == 1:
                        # Big trust delta -> OVERRIDE
                        pair.old_trust = rng.uniform(0.3, 0.5)
                        pair.new_trust = rng.uniform(0.8, 0.95)
                        policy = PolicyAction.OVERRIDE
                    else:
                        # Low stakes -> PRESERVE
                        pair.old_trust = rng.uniform(0.5, 0.65)
                        pair.new_trust = rng.uniform(0.5, 0.65)
                        policy = PolicyAction.PRESERVE

                results.append((pair, belief_type, policy))

        # Trim or pad to exactly n
        rng.shuffle(results)
        return results[:n]

    # ── Internal: DB extraction ──────────────────────────────────────────

    def _extract_from_db(
        self, conn: sqlite3.Connection, db_path: str
    ) -> List[ContradictionPair]:
        """Try multiple strategies to pull contradiction data from a DB."""
        pairs: List[ContradictionPair] = []

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        # Strategy 1: contradictions + memories (crt_memory.db style)
        if "contradictions" in tables and "memories" in tables:
            pairs.extend(self._from_contradictions_table(conn))

        # Strategy 2: conflict_resolutions + old_fact/new_fact columns
        if "conflict_resolutions" in tables:
            pairs.extend(self._from_conflict_resolutions(conn))

        # Strategy 3: corrections table (active_learning.db)
        if "corrections" in tables:
            pairs.extend(self._from_corrections(conn))

        return pairs

    def _from_contradictions_table(
        self, conn: sqlite3.Connection
    ) -> List[ContradictionPair]:
        """Extract from contradictions joined with memories."""
        query = """
            SELECT
                c.ledger_id,
                c.timestamp AS c_ts,
                c.old_memory_id,
                c.new_memory_id,
                c.contradiction_type,
                c.affects_slots,
                c.drift_mean,
                m_old.text AS old_text,
                m_old.trust AS old_trust,
                m_old.timestamp AS old_ts,
                m_old.thread_id AS old_thread,
                m_new.text AS new_text,
                m_new.trust AS new_trust,
                m_new.timestamp AS new_ts,
                m_new.thread_id AS new_thread
            FROM contradictions c
            LEFT JOIN memories m_old ON c.old_memory_id = m_old.memory_id
            LEFT JOIN memories m_new ON c.new_memory_id = m_new.memory_id
            WHERE m_old.text IS NOT NULL AND m_new.text IS NOT NULL
        """
        pairs: List[ContradictionPair] = []
        try:
            for row in conn.execute(query).fetchall():
                slot = row["affects_slots"]
                # affects_slots may be JSON list — take first element
                if slot:
                    try:
                        parsed = json.loads(slot)
                        slot = parsed[0] if isinstance(parsed, list) and parsed else slot
                    except (json.JSONDecodeError, IndexError):
                        pass

                pairs.append(
                    ContradictionPair(
                        old_text=row["old_text"],
                        new_text=row["new_text"],
                        old_trust=float(row["old_trust"]),
                        new_trust=float(row["new_trust"]),
                        old_timestamp=float(row["old_ts"]),
                        new_timestamp=float(row["new_ts"]),
                        slot_name=slot,
                        is_exclusive_slot=bool(slot),
                        similarity_score=max(0.0, 1.0 - abs(float(row["drift_mean"]))),
                        thread_id=row["new_thread"] or row["old_thread"],
                    )
                )
        except Exception:
            pass
        return pairs

    def _from_conflict_resolutions(
        self, conn: sqlite3.Connection
    ) -> List[ContradictionPair]:
        """Extract from conflict_resolutions with old_fact/new_fact columns
        (active_learning.db style).
        """
        # Check which columns exist
        try:
            cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(conflict_resolutions)"
                ).fetchall()
            }
        except Exception:
            return []

        if "old_fact" not in cols or "new_fact" not in cols:
            return []

        pairs: List[ContradictionPair] = []
        query = """
            SELECT old_fact, new_fact, timestamp, thread_id
            FROM conflict_resolutions
        """
        try:
            for row in conn.execute(query).fetchall():
                pairs.append(
                    ContradictionPair(
                        old_text=row["old_fact"],
                        new_text=row["new_fact"],
                        old_trust=0.7,
                        new_trust=0.8,
                        old_timestamp=float(row["timestamp"]) - 86400,
                        new_timestamp=float(row["timestamp"]),
                        thread_id=row["thread_id"],
                    )
                )
        except Exception:
            pass
        return pairs

    def _from_corrections(
        self, conn: sqlite3.Connection
    ) -> List[ContradictionPair]:
        """Extract from corrections table (active_learning.db)."""
        pairs: List[ContradictionPair] = []
        query = """
            SELECT incorrect_value, correct_value, timestamp,
                   thread_id, field_name, correction_type
            FROM corrections
            WHERE incorrect_value IS NOT NULL AND correct_value IS NOT NULL
        """
        try:
            for row in conn.execute(query).fetchall():
                pairs.append(
                    ContradictionPair(
                        old_text=row["incorrect_value"],
                        new_text=row["correct_value"],
                        old_trust=0.6,
                        new_trust=0.9,
                        old_timestamp=float(row["timestamp"]) - 3600,
                        new_timestamp=float(row["timestamp"]),
                        slot_name=row["field_name"],
                        is_exclusive_slot=row["correction_type"] in ("fact", "slot"),
                        thread_id=row["thread_id"],
                    )
                )
        except Exception:
            pass
        return pairs


# ── Synthetic template helpers ───────────────────────────────────────────────

_SyntheticTemplate = Dict[str, object]


def _build_templates() -> Dict[BeliefType, List[_SyntheticTemplate]]:
    """Return template dicts keyed by BeliefType."""
    return {
        BeliefType.REFINEMENT: [
            {"old": "My favorite color is blue", "new": "My favorite color is dark blue", "slot": "favorite_color", "excl": True, "sim": 0.92},
            {"old": "I like Italian food", "new": "I like Northern Italian food especially", "slot": "food_preference", "excl": False, "sim": 0.88},
            {"old": "I usually wake up early", "new": "I wake up around 6am most days", "slot": None, "excl": False, "sim": 0.87},
            {"old": "I enjoy running", "new": "I enjoy trail running in particular", "slot": "exercise", "excl": False, "sim": 0.90},
            {"old": "I have two cats", "new": "I have two tabby cats", "slot": "pets", "excl": False, "sim": 0.93},
            {"old": "I prefer tea", "new": "I prefer green tea", "slot": "beverage", "excl": True, "sim": 0.91},
            {"old": "I drive a Honda", "new": "I drive a Honda Civic", "slot": "car", "excl": True, "sim": 0.89},
            {"old": "I work in tech", "new": "I work in tech, specifically backend engineering", "slot": "industry", "excl": False, "sim": 0.86},
            {"old": "I live on the east coast", "new": "I live in Boston on the east coast", "slot": "location", "excl": False, "sim": 0.88},
            {"old": "I play guitar", "new": "I play acoustic guitar", "slot": "instrument", "excl": True, "sim": 0.91},
        ],
        BeliefType.REVISION: [
            {"old": "I work at Google", "new": "Actually I work at Microsoft now", "slot": "employer", "excl": True, "sim": 0.45},
            {"old": "My favorite language is Python", "new": "No, I switched to Rust actually", "slot": "favorite_language", "excl": True, "sim": 0.35},
            {"old": "I'm single", "new": "Actually I got married last year", "slot": "relationship_status", "excl": True, "sim": 0.30},
            {"old": "I don't have any pets", "new": "Wait, I adopted a dog recently", "slot": "pets", "excl": True, "sim": 0.25},
            {"old": "I'm a vegetarian", "new": "I meant to say I'm vegan actually", "slot": "diet", "excl": True, "sim": 0.55},
            {"old": "My name is Mike", "new": "Let me correct that, my name is Michael", "slot": "name", "excl": True, "sim": 0.65},
            {"old": "I use Windows", "new": "Actually I switched to Linux", "slot": "os", "excl": True, "sim": 0.40},
            {"old": "I'm 28 years old", "new": "No, I'm actually 32", "slot": "age", "excl": True, "sim": 0.50},
            {"old": "I live in an apartment", "new": "Actually we bought a house", "slot": "housing", "excl": True, "sim": 0.35},
            {"old": "I'm studying biology", "new": "Wait, I changed my major to CS", "slot": "field_of_study", "excl": True, "sim": 0.30},
        ],
        BeliefType.TEMPORAL: [
            {"old": "I live in Seattle", "new": "I moved to Denver last month", "slot": "city", "excl": True, "sim": 0.40},
            {"old": "I work at Amazon", "new": "I left Amazon, now at a startup", "slot": "employer", "excl": True, "sim": 0.35},
            {"old": "I'm learning Spanish", "new": "I used to learn Spanish, now studying Japanese", "slot": "language_study", "excl": True, "sim": 0.45},
            {"old": "I drive a Toyota", "new": "I changed cars, now drive a Tesla", "slot": "car", "excl": True, "sim": 0.30},
            {"old": "I'm in college", "new": "I graduated last spring, currently job hunting", "slot": "education_status", "excl": True, "sim": 0.25},
            {"old": "I live with roommates", "new": "I moved out and live alone now", "slot": "living_situation", "excl": True, "sim": 0.30},
            {"old": "I was a manager at Costco", "new": "I quit Costco and started freelancing", "slot": "employer", "excl": True, "sim": 0.25},
            {"old": "I'm dating someone", "new": "We broke up, I'm single currently", "slot": "relationship_status", "excl": True, "sim": 0.20},
            {"old": "I have a beard", "new": "I shaved it off, was getting too hot", "slot": "appearance", "excl": True, "sim": 0.30},
            {"old": "I subscribe to Netflix", "new": "I cancelled Netflix, started using Hulu now", "slot": "streaming", "excl": False, "sim": 0.35},
        ],
        BeliefType.CONFLICT: [
            {"old": "I never worked at Google", "new": "FACT: employer = Google", "slot": "employer", "excl": True, "sim": 0.20},
            {"old": "I don't have siblings", "new": "My sister is visiting this weekend", "slot": "siblings", "excl": True, "sim": 0.15},
            {"old": "I'm allergic to cats", "new": "I adopted a cat yesterday", "slot": "pets", "excl": False, "sim": 0.20},
            {"old": "I've never been to Europe", "new": "When I was in Paris last summer", "slot": None, "excl": False, "sim": 0.15},
            {"old": "I don't drink coffee", "new": "I need my morning espresso", "slot": "beverage", "excl": False, "sim": 0.25},
            {"old": "I'm a morning person", "new": "I never wake up before noon", "slot": "schedule", "excl": True, "sim": 0.10},
            {"old": "I'm 25 years old", "new": "I'm turning 40 this year", "slot": "age", "excl": True, "sim": 0.45},
            {"old": "I live alone", "new": "My wife and kids are home", "slot": "living_situation", "excl": True, "sim": 0.15},
            {"old": "I don't own a car", "new": "I drove my car to work today", "slot": "car", "excl": True, "sim": 0.20},
            {"old": "I've never smoked", "new": "I've been smoking for 10 years", "slot": "smoking", "excl": True, "sim": 0.15},
        ],
    }


def _template_to_pair(
    tmpl: _SyntheticTemplate,
    belief_type: BeliefType,
    rng: random.Random,
) -> ContradictionPair:
    """Convert a template dict into a ContradictionPair with jittered values."""
    now = time.time()

    # Time gap varies by type
    if belief_type == BeliefType.TEMPORAL:
        gap = rng.uniform(48 * 3600, 720 * 3600)  # 2 days - 30 days
    elif belief_type == BeliefType.REFINEMENT:
        gap = rng.uniform(60, 48 * 3600)  # minutes to 2 days
    elif belief_type == BeliefType.REVISION:
        gap = rng.uniform(300, 168 * 3600)  # 5 min to 1 week
    else:  # CONFLICT
        gap = rng.uniform(60, 720 * 3600)  # any range

    old_ts = now - gap
    new_ts = now

    # Trust levels vary by type
    if belief_type == BeliefType.REFINEMENT:
        old_trust = rng.uniform(0.6, 0.9)
        new_trust = rng.uniform(0.6, 0.9)
    elif belief_type == BeliefType.REVISION:
        old_trust = rng.uniform(0.5, 0.8)
        new_trust = rng.uniform(0.7, 0.95)
    elif belief_type == BeliefType.TEMPORAL:
        old_trust = rng.uniform(0.6, 0.85)
        new_trust = rng.uniform(0.7, 0.9)
    else:  # CONFLICT
        old_trust = rng.uniform(0.4, 0.95)
        new_trust = rng.uniform(0.4, 0.95)

    sim_base = float(tmpl["sim"])  # type: ignore[arg-type]
    sim = max(0.0, min(1.0, sim_base + rng.uniform(-0.05, 0.05)))

    return ContradictionPair(
        old_text=str(tmpl["old"]),
        new_text=str(tmpl["new"]),
        old_trust=round(old_trust, 3),
        new_trust=round(new_trust, 3),
        old_timestamp=old_ts,
        new_timestamp=new_ts,
        slot_name=tmpl.get("slot"),  # type: ignore[arg-type]
        is_exclusive_slot=bool(tmpl.get("excl", False)),
        similarity_score=round(sim, 3),
        thread_id=f"synthetic-{rng.randint(1000, 9999)}",
    )
