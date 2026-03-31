"""
Belief-Aware Context Compaction — CRT Epistemic Compression

Compaction is a belief event, not a summarization event. When context is
compressed, the system makes epistemic claims about what matters. This module
preserves trust scores, contradiction topology, and provenance through
compression — producing a BeliefSnapshot instead of a content summary.

Key differences from naive compaction:
- High-trust memories preserved verbatim (trust > 0.8 or authority=locked)
- Active contradictions preserved as pairs (both sides kept)
- Provenance tracked: "direct observation" vs "survived compaction"
- Token budget enforced with epistemic priority ordering
- No LLM calls — rule-based compression from existing fact_tuples

Philosophy:
- Compaction is lossy. The system should know what it lost.
- Locked beliefs are immutable through compression.
- Contradictions are structure, not noise — preserve the topology.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trust tiers for compaction representation
VERBATIM_TRUST_THRESHOLD = 0.80
SUMMARY_TRUST_THRESHOLD = 0.50
# Below SUMMARY_TRUST_THRESHOLD → slot_only or dropped

# Token budget defaults
DEFAULT_TOKEN_BUDGET = 4000
MIN_TOKENS_PER_BELIEF = 20  # minimum tokens to represent even a slot_only belief

# Priority weights for budget allocation
PRIORITY_LOCKED = 100
PRIORITY_HIGH_TRUST = 80
PRIORITY_CONTRADICTION = 70  # both sides of active contradictions
PRIORITY_MEDIUM_TRUST = 40
PRIORITY_LOW_TRUST = 10
PRIORITY_SESSION_HOT = 15    # boost for memories active in current session


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CompactedBelief:
    """A single memory's representation after compaction."""
    memory_id: str
    text: str                              # verbatim, summary, or slot representation
    original_text: str                     # always the full original
    representation: str                    # "verbatim" | "summary" | "slot_only" | "dropped"
    trust: float
    confidence: float
    authority: str
    source_kind: str
    compaction_generation: int             # how many compactions this belief has survived
    observation_type: str                  # "direct" | "survived_compaction"
    contradiction_pair_id: Optional[str]   # paired memory_id if in active contradiction
    original_text_hash: str                # SHA-256 for re-verification tracking
    kind: str = "observation"
    tokens_estimated: int = 0


@dataclass
class BeliefSnapshot:
    """Complete compacted context — a belief state, not a content summary."""
    snapshot_id: str
    timestamp: float
    generation: int                        # increments each compaction pass
    beliefs: List[CompactedBelief]
    active_contradictions: List[Tuple[str, str]]  # (memory_id_a, memory_id_b)
    dropped_count: int
    token_budget: int
    tokens_used: int
    trigger: str = "manual"                # "token_overflow" | "scheduled" | "manual"

    @property
    def verbatim_count(self) -> int:
        return sum(1 for b in self.beliefs if b.representation == "verbatim")

    @property
    def summary_count(self) -> int:
        return sum(1 for b in self.beliefs if b.representation == "summary")

    @property
    def slot_only_count(self) -> int:
        return sum(1 for b in self.beliefs if b.representation == "slot_only")


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Fast token count estimate. chars/4 heuristic, conservative."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Memory representation helpers (no LLM calls)
# ---------------------------------------------------------------------------

def _extract_fact_tuples(memory: Any) -> Optional[str]:
    """Extract fact_tuples from a memory item if available."""
    ft = getattr(memory, "fact_tuples", None)
    if ft and isinstance(ft, str) and ft.strip():
        return ft.strip()
    ctx = getattr(memory, "context_json", None) or getattr(memory, "context", None)
    if isinstance(ctx, dict):
        ft = ctx.get("fact_tuples")
        if ft and isinstance(ft, str) and ft.strip():
            return ft.strip()
    return None


def _summarize_memory(memory: Any) -> str:
    """Rule-based summary: slot=value pairs + truncated text. No LLM call."""
    fact_tuples = _extract_fact_tuples(memory)
    text = getattr(memory, "text", str(memory))
    trust = getattr(memory, "trust", 0.5)

    if fact_tuples:
        # Use structured facts as summary
        return f"{fact_tuples} (trust={trust:.2f})"

    # Truncate to first sentence or 120 chars
    text = text.strip()
    period_idx = text.find(".")
    if 0 < period_idx < 120:
        return f"{text[:period_idx + 1]} (trust={trust:.2f})"
    if len(text) > 120:
        return f"{text[:117]}... (trust={trust:.2f})"
    return f"{text} (trust={trust:.2f})"


def _slot_only_memory(memory: Any) -> str:
    """Bare slot=value representation. Minimal tokens."""
    fact_tuples = _extract_fact_tuples(memory)
    if fact_tuples:
        return fact_tuples

    # Fall back to first 60 chars
    text = getattr(memory, "text", str(memory)).strip()
    if len(text) > 60:
        return text[:57] + "..."
    return text


def _text_hash(text: str) -> str:
    """SHA-256 of text for re-verification tracking."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core compaction
# ---------------------------------------------------------------------------

def compact_context(
    memories: list,
    active_contradictions: Optional[list] = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    previous_snapshot: Optional[BeliefSnapshot] = None,
    trigger: str = "manual",
    session_hot_ids: Optional[Set[str]] = None,
) -> BeliefSnapshot:
    """Produce a belief snapshot from memories under a token budget.

    Trust tiers:
    - authority == "locked": ALWAYS verbatim (never summarized)
    - trust > 0.8: verbatim
    - 0.5 <= trust <= 0.8: summary representation
    - trust < 0.5: slot_only or dropped (budget permitting)

    Active contradictions: both sides preserved as pairs regardless of trust.

    If previous_snapshot is provided, inherits and increments compaction_generation
    for surviving beliefs, and marks observation_type as "survived_compaction".
    """
    active_contradictions = active_contradictions or []

    # Build set of memory_ids involved in active contradictions
    contradiction_memory_ids: Set[str] = set()
    contradiction_pairs: List[Tuple[str, str]] = []
    for entry in active_contradictions:
        old_id = getattr(entry, "old_memory_id", None) or (entry.get("old_memory_id") if isinstance(entry, dict) else None)
        new_id = getattr(entry, "new_memory_id", None) or (entry.get("new_memory_id") if isinstance(entry, dict) else None)
        if old_id and new_id:
            contradiction_memory_ids.add(old_id)
            contradiction_memory_ids.add(new_id)
            contradiction_pairs.append((old_id, new_id))

    # Build previous generation lookup
    prev_gen: Dict[str, int] = {}
    if previous_snapshot:
        for b in previous_snapshot.beliefs:
            prev_gen[b.memory_id] = b.compaction_generation

    generation = (previous_snapshot.generation + 1) if previous_snapshot else 1

    # Classify each memory into representation tier and assign priority
    classified: List[Tuple[float, str, Any]] = []  # (priority, representation, memory)
    for mem in memories:
        mem_id = getattr(mem, "memory_id", None) or getattr(mem, "id", str(id(mem)))
        trust = getattr(mem, "trust", 0.5)
        authority = getattr(mem, "authority", "confirmed")
        in_contradiction = mem_id in contradiction_memory_ids

        # Session hot boost — memories active in current session get priority
        hot_boost = PRIORITY_SESSION_HOT if (session_hot_ids and mem_id in session_hot_ids) else 0

        if authority == "locked":
            classified.append((PRIORITY_LOCKED + hot_boost, "verbatim", mem))
        elif in_contradiction:
            rep = "verbatim" if trust >= SUMMARY_TRUST_THRESHOLD else "summary"
            classified.append((PRIORITY_CONTRADICTION + hot_boost, rep, mem))
        elif trust >= VERBATIM_TRUST_THRESHOLD:
            classified.append((PRIORITY_HIGH_TRUST + hot_boost, "verbatim", mem))
        elif trust >= SUMMARY_TRUST_THRESHOLD:
            classified.append((PRIORITY_MEDIUM_TRUST + hot_boost, "summary", mem))
        else:
            classified.append((PRIORITY_LOW_TRUST + hot_boost, "slot_only", mem))

    # Sort by priority descending (highest priority = first to get budget)
    classified.sort(key=lambda x: -x[0])

    # Allocate within token budget
    beliefs: List[CompactedBelief] = []
    tokens_used = 0
    dropped_count = 0
    metadata_line_tokens = estimate_tokens(
        f"## Belief Snapshot (gen {generation}, {len(classified)} beliefs)"
    )
    tokens_used += metadata_line_tokens

    for priority, representation, mem in classified:
        mem_id = getattr(mem, "memory_id", None) or getattr(mem, "id", str(id(mem)))
        trust = getattr(mem, "trust", 0.5)
        confidence = getattr(mem, "confidence", 0.5)
        authority = getattr(mem, "authority", "confirmed")
        source_kind = getattr(mem, "source_kind", "principal")
        kind = getattr(mem, "kind", "observation")
        original_text = getattr(mem, "text", str(mem))
        in_contradiction = mem_id in contradiction_memory_ids

        # Determine compaction generation for this memory
        mem_gen = prev_gen.get(mem_id, 0) + 1 if previous_snapshot else (
            getattr(mem, "compaction_count", 0)
        )
        obs_type = "survived_compaction" if previous_snapshot or getattr(mem, "compaction_count", 0) > 0 else "direct"

        # Get text representation
        if representation == "verbatim":
            display_text = f"- {original_text} [trust={trust:.2f}, {authority}]"
        elif representation == "summary":
            display_text = f"- {_summarize_memory(mem)}"
        else:
            display_text = f"- {_slot_only_memory(mem)}"

        tokens_needed = estimate_tokens(display_text)

        # Check budget
        if tokens_used + tokens_needed > token_budget:
            # Try to downgrade representation
            if representation == "verbatim" and authority != "locked":
                display_text = f"- {_summarize_memory(mem)}"
                tokens_needed = estimate_tokens(display_text)
                representation = "summary"

            if tokens_used + tokens_needed > token_budget and representation == "summary":
                display_text = f"- {_slot_only_memory(mem)}"
                tokens_needed = estimate_tokens(display_text)
                representation = "slot_only"

            if tokens_used + tokens_needed > token_budget:
                # Still doesn't fit — drop unless it's locked or in contradiction
                if authority == "locked" or in_contradiction:
                    # Force include locked/contradiction at slot_only minimum
                    display_text = f"- {_slot_only_memory(mem)}"
                    tokens_needed = estimate_tokens(display_text)
                    representation = "slot_only"
                else:
                    representation = "dropped"
                    display_text = ""
                    tokens_needed = 0
                    dropped_count += 1

        # Find contradiction pair id
        pair_id = None
        if in_contradiction:
            for old_id, new_id in contradiction_pairs:
                if mem_id == old_id:
                    pair_id = new_id
                    break
                elif mem_id == new_id:
                    pair_id = old_id
                    break

        belief = CompactedBelief(
            memory_id=mem_id,
            text=display_text,
            original_text=original_text,
            representation=representation,
            trust=trust,
            confidence=confidence,
            authority=authority,
            source_kind=source_kind,
            compaction_generation=mem_gen,
            observation_type=obs_type,
            contradiction_pair_id=pair_id,
            original_text_hash=_text_hash(original_text),
            kind=kind,
            tokens_estimated=tokens_needed,
        )
        beliefs.append(belief)
        tokens_used += tokens_needed

    snapshot = BeliefSnapshot(
        snapshot_id=str(uuid.uuid4())[:12],
        timestamp=time.time(),
        generation=generation,
        beliefs=beliefs,
        active_contradictions=contradiction_pairs,
        dropped_count=dropped_count,
        token_budget=token_budget,
        tokens_used=tokens_used,
        trigger=trigger,
    )

    logger.info(
        f"[COMPACTION] gen={generation} beliefs={len(beliefs)} "
        f"verbatim={snapshot.verbatim_count} summary={snapshot.summary_count} "
        f"slot_only={snapshot.slot_only_count} dropped={dropped_count} "
        f"tokens={tokens_used}/{token_budget}"
    )

    return snapshot


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_belief_snapshot(snapshot: BeliefSnapshot) -> str:
    """Render snapshot to text for system prompt injection.

    Sections:
    - Metadata line (generation, counts)
    - High-confidence beliefs (verbatim)
    - Active tensions (contradiction pairs)
    - Summary beliefs
    - Slot-only beliefs
    """
    lines: List[str] = []

    lines.append(
        f"## Belief Snapshot (gen {snapshot.generation}, "
        f"{len(snapshot.beliefs)} beliefs, {snapshot.dropped_count} dropped)"
    )

    # High-confidence (verbatim)
    verbatim = [b for b in snapshot.beliefs if b.representation == "verbatim"]
    if verbatim:
        lines.append("")
        lines.append("### High-confidence beliefs:")
        for b in verbatim:
            obs_marker = " [compacted]" if b.observation_type == "survived_compaction" else ""
            lines.append(b.text + obs_marker)

    # Active tensions
    rendered_pairs: Set[str] = set()
    tensions = [b for b in snapshot.beliefs if b.contradiction_pair_id]
    if tensions:
        lines.append("")
        lines.append("### Active tensions:")
        for b in tensions:
            pair_key = tuple(sorted([b.memory_id, b.contradiction_pair_id or ""]))
            if str(pair_key) in rendered_pairs:
                continue
            rendered_pairs.add(str(pair_key))
            # Find the other side
            other = next(
                (ob for ob in snapshot.beliefs if ob.memory_id == b.contradiction_pair_id),
                None
            )
            if other:
                lines.append(
                    f"- HELD: \"{b.original_text[:60]}\" vs "
                    f"\"{other.original_text[:60]}\" (under review)"
                )
            else:
                lines.append(f"- TENSION: \"{b.original_text[:80]}\" (pair not in snapshot)")

    # Summary beliefs
    summaries = [b for b in snapshot.beliefs if b.representation == "summary" and not b.contradiction_pair_id]
    if summaries:
        lines.append("")
        lines.append("### Summary beliefs:")
        for b in summaries:
            gen_note = f", survived {b.compaction_generation} compactions" if b.compaction_generation > 0 else ""
            lines.append(f"{b.text}{gen_note}")

    # Slot-only beliefs
    slots = [b for b in snapshot.beliefs if b.representation == "slot_only" and not b.contradiction_pair_id]
    if slots:
        lines.append("")
        lines.append("### Compressed beliefs:")
        for b in slots:
            lines.append(b.text)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def record_compaction_event(
    conn,
    snapshot: BeliefSnapshot,
) -> None:
    """Write compaction event and per-memory provenance to the database."""
    import json

    cursor = conn.cursor()

    # Write the compaction event
    cursor.execute("""
        INSERT INTO compaction_events
            (snapshot_id, timestamp, generation, total_beliefs,
             verbatim_count, summary_count, slot_only_count, dropped_count,
             token_budget, tokens_used, trigger, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot.snapshot_id,
        snapshot.timestamp,
        snapshot.generation,
        len(snapshot.beliefs),
        snapshot.verbatim_count,
        snapshot.summary_count,
        snapshot.slot_only_count,
        snapshot.dropped_count,
        snapshot.token_budget,
        snapshot.tokens_used,
        snapshot.trigger,
        json.dumps({
            "active_contradictions": snapshot.active_contradictions,
        }),
    ))

    # Write per-memory provenance (skip dropped for storage efficiency)
    for belief in snapshot.beliefs:
        cursor.execute("""
            INSERT INTO compaction_provenance
                (memory_id, snapshot_id, timestamp, representation,
                 generation, trust_before, trust_after, flagged_reverification)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            belief.memory_id,
            snapshot.snapshot_id,
            snapshot.timestamp,
            belief.representation,
            belief.compaction_generation,
            belief.trust,
            belief.trust,  # trust_after updated by compaction_decay
            0,
        ))

    conn.commit()
    logger.info(f"[COMPACTION] Recorded event {snapshot.snapshot_id} with {len(snapshot.beliefs)} provenance entries")
