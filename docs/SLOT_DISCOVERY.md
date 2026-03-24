# Dynamic Slot Discovery

**Version:** v2.1 (March 25, 2026)
**Sprint:** 6
**Design Law:** 3 — "Structure should emerge, not be hardcoded"
**File:** `personal_agent/slot_discovery.py`, `routes/slot_discovery.py`

---

## Overview

Slot discovery replaces the hardcoded `EXCLUSIVE_SLOTS` list with a learned model that discovers slot behavior from contradiction and fact patterns. Instead of the developer deciding which facts are exclusive (only one value at a time) vs additive (multiple values coexist), the system observes how contradictions are resolved and infers the slot type automatically.

---

## Slot Types

| Type | Behavior | Example | Resolution |
|------|----------|---------|------------|
| **EXCLUSIVE** | Only one value true at a time | favorite_color, name, employer | Override old with new |
| **ADDITIVE** | Multiple values coexist | hobbies, skills, friends | Preserve both |
| **TEMPORAL** | Value changes over time, history matters | location, job | Archive old, accept new |
| **HIERARCHICAL** | Parent/child containment | role: developer > frontend dev | Merge if containment, else override |
| **UNKNOWN** | Not enough data to classify | — | Ask user |

---

## Classification Logic

The classifier is rule-based (no ML) and uses contradiction resolution history:

1. **< 2 facts and 0 contradictions** → UNKNOWN (not enough data)
2. **HIERARCHICAL**: 2+ distinct values with substring/containment relationships
3. **ADDITIVE**: 2+ high-trust (>= 0.7) values coexisting with <= 1 contradiction, OR more preserve resolutions than overrides
4. **TEMPORAL**: 4+ distinct values AND 3+ override resolutions AND 4+ timestamped facts
5. **EXCLUSIVE**: 1+ contradictions with overrides > preserves, OR single high-trust value with 2+ distinct values
6. **Default ADDITIVE**: 0 contradictions, 2+ distinct values, 2+ high-trust values
7. Otherwise **UNKNOWN**

### Confidence Scoring

| Evidence | Confidence |
|----------|------------|
| 0 contradictions, < 2 distinct values | 0.0 |
| 1 contradiction | 0.30 |
| 2+ contradictions | 0.60 |
| 4+ consistent contradictions | 0.85 |
| 10+ consistent contradictions | 0.95 |
| No contradictions but multi-fact | 0.50 |

Consistency penalty applied when 2+ resolution types exist (mixed override/preserve signals reduce confidence by up to 50%).

---

## Bootstrap: Seed Lists

Before enough contradiction data accumulates, seed lists provide defaults:

**Seed EXCLUSIVE (14):** favorite_color, name, first_name, last_name, birthday, birth_date, legal_name, primary_city, city, employer, job_title, nickname, age, email

**Seed ADDITIVE (5):** hobby, skill, interest, project, friend

### Lookup Fallback Chain

```
get_slot_type(slot_name):
  1. Learned profile with confidence >= 0.5 → use it
  2. Seed exclusive list → EXCLUSIVE
  3. Seed additive list → ADDITIVE
  4. → UNKNOWN
```

---

## Event Hooks (Real-Time Learning)

The system updates slot profiles incrementally via event hooks:

### on_contradiction_recorded(slot_name, old_value, new_value, resolution)
Fired when a new contradiction is recorded. Updates the slot's values_seen set and resolution_history (last 20 entries), reclassifies, and logs any type change.

### on_fact_stored(slot_name, value, trust_score)
Fired when a fact is stored. Tracks unique values and high-trust values (>= 0.7). Triggers reclassification when 2+ unique values exist.

### on_contradiction_resolved(slot_name, resolution, was_suggested)
Counter-evidence hook. When user resolves differently than the system suggested (e.g. clicks "Keep Both" on an EXCLUSIVE slot), the classification confidence decreases. This is how the system learns from user disagreement.

---

## Resolution Policy Engine

```python
suggest_resolution_policy(slot_name, new_value, existing_value)
```

| Slot Type | Suggested Policy |
|-----------|-----------------|
| EXCLUSIVE | `override` — replace old value |
| ADDITIVE | `preserve` — keep both values |
| TEMPORAL | `archive` — mark old as historical, accept new |
| HIERARCHICAL | `merge` (if containment) or `override` |
| UNKNOWN | `ask_user` — defer to human |

### CRT Memory Integration

TEMPORAL slots get lighter trust demotion on the old value (0.6x) compared to EXCLUSIVE slots (0.4x). The reasoning: temporal values were true at the time, they're just no longer current.

---

## Full Discovery Pass

`run_discovery_pass()` performs batch analysis across all slots:

1. Queries all facts from `memory_facts` joined with `memories` (non-deprecated)
2. Queries all contradictions with `affects_slots`
3. Classifies every slot with 2+ facts or any contradictions
4. Compares with existing profiles, saves updates, logs reclassifications

This runs periodically via the heartbeat system and can be triggered manually.

---

## Persistence

### SQLite Tables

**`slot_profiles`** — one row per slot:
- slot_name (PK), discovered_type, confidence, evidence_count, resolution_pattern, unique_values_seen, contradiction_count, avg_resolution_time, last_updated, metadata (JSON)

**`slot_discovery_log`** — audit trail:
- id, slot_name, old_type, new_type, confidence, trigger, evidence_summary (JSON), timestamp

Database co-located next to the memory DB.

---

## API Endpoints

**Router:** `/api/slots`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/slots/profiles` | List all learned slot profiles |
| GET | `/api/slots/profiles/{slot_name}` | Get specific profile (404 if not found) |
| POST | `/api/slots/analyze` | Trigger full discovery pass manually |
| PUT | `/api/slots/profiles/{slot_name}/override` | Manual override — sets confidence to 1.0 |
| GET | `/api/slots/stats` | Summary statistics |

### GET /api/slots/stats

Returns:
```json
{
  "total_slots": 42,
  "typed": 35,
  "untyped": 7,
  "type_breakdown": {"EXCLUSIVE": 14, "ADDITIVE": 12, "TEMPORAL": 6, "HIERARCHICAL": 3},
  "confidence_distribution": {"high": 20, "medium": 10, "low": 5, "none": 7},
  "seed_exclusive_count": 14,
  "seed_additive_count": 5
}
```

---

## Heartbeat Integration

Every heartbeat cycle includes a slot discovery pass (`run_discovery_pass()`) that reclassifies slots from the full ledger. This means slot types continuously improve as more data accumulates.
