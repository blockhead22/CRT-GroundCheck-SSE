"""
Scaffold Conversation Lab
=========================

Tests whether a BRG-walking scaffold can help a small model (Gemma3)
synthesize memories AND generate meaningful questions from graph tension.

Three conditions:
  A. Raw dump - 20+ memories stuffed into context
  B. Pre-filtered - 5 trust-weighted memories
  C. Scaffolded walk - anchor-by-anchor generation with verification

Two phases:
  Phase 1: "What do you know about me?" (synthesis)
  Phase 2: Scaffold derives a question from BRG tension (epistemic motivation)

Usage:
  python labs/scaffold_conversation_lab/scaffold_conversation_lab.py
"""

import sys
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, field

# Project root
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


# ── Data classes ──

@dataclass
class MemoryNode:
    """A memory with its trust score and embedding."""
    id: str
    text: str
    trust: float
    kind: str = "user_fact"
    embedding: Optional[np.ndarray] = None
    domain: str = ""


@dataclass
class TensionEdge:
    """An edge between two memories with tension score."""
    source_id: str
    target_id: str
    edge_type: str  # SUPPORTS, CONTRADICTS, RELATED_TO, SUPERSEDES
    weight: float = 0.5
    tension: float = 0.0  # 0 = no tension, 1 = max contradiction


@dataclass
class AnchorBasin:
    """A cluster of related memories."""
    name: str
    memory_ids: List[str] = field(default_factory=list)
    center_embedding: Optional[np.ndarray] = None
    total_mass: float = 0.0  # sum of trust scores
    tension: float = 0.0  # internal contradiction tension
    gravity: float = 0.0  # mass - tension = how much it pulls


@dataclass
class WalkStep:
    """One step in the scaffold walk."""
    anchor: str
    memories_used: List[str]
    generated_text: str
    coherence_score: float = 0.0
    fact_accuracy: float = 0.0
    tokens_used: int = 0
    step_time_ms: float = 0.0


@dataclass
class LabResult:
    """Result from one experimental condition."""
    condition: str  # "raw_dump", "pre_filtered", "scaffolded"
    query: str
    output: str
    memories_available: int
    memories_used: int
    domains_covered: List[str] = field(default_factory=list)
    contradictions_in_output: int = 0
    total_tokens: int = 0
    total_time_ms: float = 0.0
    walk_steps: List[WalkStep] = field(default_factory=list)
    scaffold_question: str = ""  # Phase 2: question derived from tension


# ── Memory loading ──

def load_memories_from_db(db_path: str, limit: int = 200) -> List[MemoryNode]:
    """Load memories from the production SQLite DB."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT memory_id, text, trust, kind
        FROM memories
        WHERE deprecated = 0 AND text IS NOT NULL AND LENGTH(text) > 10
        ORDER BY trust DESC
        LIMIT ?
    """, (limit,)).fetchall()

    memories = []
    for row in rows:
        memories.append(MemoryNode(
            id=str(row["memory_id"]),
            text=row["text"][:500],
            trust=float(row["trust"] or 0.5),
            kind=row["kind"] or "user_fact",
        ))

    conn.close()
    logger.info(f"Loaded {len(memories)} memories from {db_path}")
    return memories


def assign_domains(memories: List[MemoryNode]) -> List[MemoryNode]:
    """Simple keyword-based domain assignment."""
    domain_keywords = {
        "health": ["health", "medical", "leukemia", "cgvhd", "hospital", "medication", "antidepressant", "sleep"],
        "work": ["work", "job", "walmart", "freelance", "self-employed", "coding", "developer", "programming"],
        "location": ["live", "milwaukee", "waukesha", "sussex", "wisconsin", "portland"],
        "preferences": ["favorite", "color", "drink", "coffee", "music", "food"],
        "personality": ["self-doubt", "sabotage", "confidence", "anxiety", "honest", "push back"],
        "relationships": ["friend", "family", "dating", "relationship", "cat", "depression"],
        "project": ["aether", "crt", "core", "scaffold", "memory", "trust", "contradiction", "brg"],
    }

    for mem in memories:
        text_lower = mem.text.lower()
        for domain, keywords in domain_keywords.items():
            if any(kw in text_lower for kw in keywords):
                mem.domain = domain
                break
        if not mem.domain:
            mem.domain = "other"

    return memories


# ── Anchor basin detection ──

def find_anchor_basins(memories: List[MemoryNode]) -> List[AnchorBasin]:
    """Group memories into anchor basins by domain."""
    basins: Dict[str, AnchorBasin] = {}

    for mem in memories:
        domain = mem.domain or "other"
        if domain not in basins:
            basins[domain] = AnchorBasin(name=domain)
        basins[domain].memory_ids.append(mem.id)
        basins[domain].total_mass += mem.trust

    # Calculate gravity (mass for now, tension subtracted later)
    for basin in basins.values():
        basin.gravity = basin.total_mass

    return sorted(basins.values(), key=lambda b: b.gravity, reverse=True)


def find_tension_edges(memories: List[MemoryNode]) -> List[TensionEdge]:
    """Find contradiction pairs using simple text heuristics."""
    edges = []
    mem_by_id = {m.id: m for m in memories}

    # Look for memories that reference the same slot with different values
    slot_memories: Dict[str, List[MemoryNode]] = {}
    for mem in memories:
        text_lower = mem.text.lower()
        for slot in ["favorite_color", "favorite color", "favorite_drink", "employer", "location"]:
            if slot.replace("_", " ") in text_lower:
                slot_memories.setdefault(slot.replace(" ", "_"), []).append(mem)

    for slot, mems in slot_memories.items():
        if len(mems) > 1:
            for i in range(len(mems)):
                for j in range(i + 1, len(mems)):
                    # Simple: if both mention same slot but different trust, there's tension
                    tension = abs(mems[i].trust - mems[j].trust)
                    edges.append(TensionEdge(
                        source_id=mems[i].id,
                        target_id=mems[j].id,
                        edge_type="CONTRADICTS" if tension > 0.2 else "RELATED_TO",
                        weight=0.5,
                        tension=min(1.0, tension * 2),
                    ))

    logger.info(f"Found {len(edges)} tension edges ({sum(1 for e in edges if e.edge_type == 'CONTRADICTS')} contradictions)")
    return edges


# ── LLM interface ──

def call_gemma3(prompt: str, max_tokens: int = 500) -> Tuple[str, int, float]:
    """Call Gemma3 via Ollama. Returns (text, tokens_used, time_ms)."""
    import requests

    start = time.time()
    try:
        resp = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "gemma3:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7,
                }
            },
            timeout=60,
        )
        data = resp.json()
        text = data.get("response", "").strip()
        tokens = data.get("eval_count", len(text.split()))
        elapsed = (time.time() - start) * 1000
        return text, tokens, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Gemma3 call failed: {e}")
        return f"[ERROR: {e}]", 0, elapsed


# ── Condition A: Raw dump ──

def run_raw_dump(memories: List[MemoryNode], query: str) -> LabResult:
    """Condition A: Dump all memories into context."""
    logger.info("=== CONDITION A: RAW DUMP ===")

    memory_block = "\n".join(
        f"- [{m.domain}] (trust:{m.trust:.2f}) {m.text}"
        for m in memories[:30]  # cap at 30 to avoid overflow
    )

    prompt = f"""You are a personal AI assistant with the following memories about your user:

{memory_block}

User question: {query}

Based on ALL the memories above, provide a comprehensive answer. Reference specific facts you know."""

    start = time.time()
    output, tokens, llm_time = call_gemma3(prompt, max_tokens=800)
    total_time = (time.time() - start) * 1000

    # Count which domains appear in output
    domains_covered = []
    output_lower = output.lower()
    for mem in memories[:30]:
        if mem.domain and mem.domain not in domains_covered:
            # Check if any keyword from this memory appears in output
            words = set(mem.text.lower().split())
            if len(words & set(output_lower.split())) > 3:
                domains_covered.append(mem.domain)

    # Coherence self-check
    coherence = 1.0
    if output:
        check_prompt = f"""Does the following text contain any internal contradictions where it says one thing and then says the opposite? Answer only YES or NO.

Text: {output[:800]}"""
        check_output, _, _ = call_gemma3(check_prompt, max_tokens=10)
        if "yes" in check_output.lower():
            coherence = 0.3
            logger.warning("  Raw dump: self-contradiction detected")

    logger.info(f"  Output ({tokens} tokens, {total_time:.0f}ms):")
    for line in output.split("\n")[:10]:
        if line.strip():
            logger.info(f"    {line.strip()[:120]}")

    return LabResult(
        condition="raw_dump",
        query=query,
        output=output,
        memories_available=min(len(memories), 30),
        memories_used=len(domains_covered),
        domains_covered=domains_covered,
        contradictions_in_output=0 if coherence > 0.5 else 1,
        total_tokens=tokens,
        total_time_ms=total_time,
    )


# ── Condition B: Pre-filtered ──

def run_pre_filtered(memories: List[MemoryNode], query: str) -> LabResult:
    """Condition B: Top 5 trust-weighted memories."""
    logger.info("=== CONDITION B: PRE-FILTERED ===")

    # Sort by trust, take top 5
    top5 = sorted(memories, key=lambda m: m.trust, reverse=True)[:5]

    memory_block = "\n".join(
        f"- (trust:{m.trust:.2f}) {m.text}"
        for m in top5
    )

    prompt = f"""You are a personal AI assistant. Here are your most trusted memories about your user:

{memory_block}

User question: {query}

Answer based on these memories. Be honest about what you know and don't know."""

    start = time.time()
    output, tokens, llm_time = call_gemma3(prompt, max_tokens=600)
    total_time = (time.time() - start) * 1000

    domains_covered = list(set(m.domain for m in top5 if m.domain))

    # Coherence self-check
    coherence = 1.0
    if output:
        check_prompt = f"""Does the following text contain any internal contradictions where it says one thing and then says the opposite? Answer only YES or NO.

Text: {output[:800]}"""
        check_output, _, _ = call_gemma3(check_prompt, max_tokens=10)
        if "yes" in check_output.lower():
            coherence = 0.3
            logger.warning("  Pre-filtered: self-contradiction detected")

    logger.info(f"  Output ({tokens} tokens, {total_time:.0f}ms):")
    for line in output.split("\n")[:10]:
        if line.strip():
            logger.info(f"    {line.strip()[:120]}")

    return LabResult(
        condition="pre_filtered",
        query=query,
        output=output,
        memories_available=5,
        memories_used=5,
        domains_covered=domains_covered,
        contradictions_in_output=0 if coherence > 0.5 else 1,
        total_tokens=tokens,
        total_time_ms=total_time,
    )


# ── Condition C: Scaffolded walk ──

def run_scaffolded_walk(memories: List[MemoryNode], query: str) -> LabResult:
    """Condition C: Staged scaffold - verify anchors, build prompts, generate, stitch."""
    logger.info("=== CONDITION C: SCAFFOLDED WALK (STAGED) ===")

    basins = find_anchor_basins(memories)
    mem_by_id = {m.id: m for m in memories}

    # ── Stage 1: Walk and verify each anchor ──
    logger.info("  Stage 1: Walking anchors...")
    staged_prompts = []
    topics_covered = []

    for basin in basins[:6]:
        if not basin.memory_ids:
            continue

        basin_memories = [mem_by_id[mid] for mid in basin.memory_ids if mid in mem_by_id]
        basin_memories.sort(key=lambda m: m.trust, reverse=True)
        top_memories = basin_memories[:3]

        # Verify: are these memories internally consistent?
        if len(top_memories) > 1:
            texts = [m.text[:100] for m in top_memories]
            verify_prompt = f"""Do these facts about the same person contradict each other? Answer YES or NO then one sentence why.

Fact 1: {texts[0]}
Fact 2: {texts[1]}
{('Fact 3: ' + texts[2]) if len(texts) > 2 else ''}"""

            verify_out, _, _ = call_gemma3(verify_prompt, max_tokens=30)
            has_internal_contradiction = "yes" in verify_out.lower()
        else:
            has_internal_contradiction = False

        memory_block = "\n".join(
            f"- (trust:{m.trust:.2f}) {m.text}"
            for m in top_memories
        )

        # ── Stage 2: Build the generation prompt ──
        # No prior output. Just the verified facts and a one-line coverage summary.
        if topics_covered:
            coverage_line = f"You have already covered: {', '.join(topics_covered)}. Do NOT repeat those topics."
        else:
            coverage_line = "This is the first section of your answer."

        contradiction_note = ""
        if has_internal_contradiction:
            contradiction_note = " Note: these memories contain a contradiction. Acknowledge it honestly rather than picking a side."

        prompt = f"""You are answering: "{query}"

{coverage_line}

Write 2-3 sentences about the user's {basin.name} based ONLY on these verified facts:
{memory_block}
{contradiction_note}
Be specific. Reference actual facts. Do not add information not in the memories above. Do not use filler phrases like "continuing from our previous discussion"."""

        staged_prompts.append({
            "basin": basin.name,
            "prompt": prompt,
            "memories": top_memories,
            "has_contradiction": has_internal_contradiction,
        })
        topics_covered.append(basin.name)

        logger.info(f"  Verified [{basin.name}]: {len(top_memories)} memories, contradiction={has_internal_contradiction}")

    # ── Stage 3: Generate from staged prompts ──
    logger.info("  Stage 2: Generating from staged prompts...")
    walk_steps = []
    sections = []
    total_tokens = 0
    total_time = 0.0

    for staged in staged_prompts:
        step_start = time.time()
        step_output, step_tokens, llm_time = call_gemma3(staged["prompt"], max_tokens=200)
        step_time = (time.time() - step_start) * 1000

        walk_steps.append(WalkStep(
            anchor=staged["basin"],
            memories_used=[m.id for m in staged["memories"]],
            generated_text=step_output,
            coherence_score=1.0,  # set after stitch check
            tokens_used=step_tokens,
            step_time_ms=step_time,
        ))

        sections.append(step_output)
        total_tokens += step_tokens
        total_time += step_time

        logger.info(f"  Generated [{staged['basin']}]: {step_tokens} tokens, {step_time:.0f}ms")
        for line in step_output.split("\n")[:3]:
            if line.strip():
                logger.info(f"    > {line.strip()[:120]}")

    # ── Stage 4: Incremental coherence check with retry ──
    logger.info("  Stage 3: Incremental coherence checks...")
    MAX_RETRIES = 2

    verified_sections = []
    contradictions_count = 0

    for i, (step, section, staged) in enumerate(zip(walk_steps, sections, staged_prompts)):
        passed = False

        for attempt in range(MAX_RETRIES + 1):
            if not verified_sections:
                # First section - just check internal consistency
                check_prompt = f"""Does this text contain any internal contradictions? Answer only YES or NO.

{section[:500]}"""
            else:
                # Check against all previously verified sections
                prior_text = "\n".join(verified_sections)[-600:]
                check_prompt = f"""Does the NEW text contradict anything in the PREVIOUS text? Answer only YES or NO.

PREVIOUS (verified):
{prior_text}

NEW:
{section[:400]}"""

            check_out, _, _ = call_gemma3(check_prompt, max_tokens=10)
            is_coherent = "yes" not in check_out.lower()

            if is_coherent:
                step.coherence_score = 1.0
                verified_sections.append(section)
                passed = True
                if attempt > 0:
                    logger.info(f"  [{step.anchor}] PASSED on retry {attempt}")
                break
            else:
                if attempt < MAX_RETRIES:
                    # Retry: regenerate this section with explicit warning
                    logger.warning(f"  [{step.anchor}] FAILED coherence (attempt {attempt + 1}/{MAX_RETRIES + 1}), retrying...")
                    retry_prompt = staged["prompt"] + f"\n\nIMPORTANT: Your previous attempt contradicted established facts. Here is what has been verified so far:\n{chr(10).join(verified_sections)[-400:]}\n\nDo NOT contradict these facts."

                    section, retry_tokens, retry_time = call_gemma3(retry_prompt, max_tokens=200)
                    step.generated_text = section
                    step.tokens_used += retry_tokens
                    step.step_time_ms += retry_time
                    total_tokens += retry_tokens
                    total_time += retry_time
                else:
                    # Final attempt failed - mark as dead, skip this anchor
                    step.coherence_score = 0.0
                    contradictions_count += 1
                    logger.warning(f"  [{step.anchor}] DEAD after {MAX_RETRIES + 1} attempts - skipping anchor")

        if not passed:
            logger.warning(f"  [{step.anchor}] excluded from final output")

    full_output = "\n\n".join(verified_sections)
    logger.info(f"  Final output: {len(verified_sections)}/{len(walk_steps)} anchors passed, {contradictions_count} dead")

    domains_covered = [step.anchor for step in walk_steps]

    return LabResult(
        condition="scaffolded_staged",
        query=query,
        output=full_output,
        memories_available=len(memories),
        memories_used=sum(len(s.memories_used) for s in walk_steps),
        domains_covered=domains_covered,
        contradictions_in_output=contradictions_count,
        total_tokens=total_tokens,
        total_time_ms=total_time,
        walk_steps=walk_steps,
    )


# ── Phase 2: Tension-derived question ──

def derive_question_from_tension(
    memories: List[MemoryNode],
    basins: List[AnchorBasin],
    edges: List[TensionEdge],
) -> Tuple[str, LabResult]:
    """Use BRG tension to derive a meaningful question."""
    logger.info("=== PHASE 2: TENSION-DERIVED QUESTION ===")

    mem_by_id = {m.id: m for m in memories}

    # Domain importance weighting - prioritize high-stakes domains over preferences
    domain_weight = {
        "health": 3.0,
        "work": 2.5,
        "personality": 2.0,
        "relationships": 2.0,
        "project": 1.5,
        "location": 1.0,
        "preferences": 0.5,  # deprioritize favorite color type stuff
        "other": 0.3,
    }

    # Score tension edges by tension * domain importance
    def edge_importance(edge: TensionEdge) -> float:
        src = mem_by_id.get(edge.source_id)
        if not src:
            return edge.tension
        weight = domain_weight.get(src.domain, 1.0)
        return edge.tension * weight

    tension_edges = sorted(edges, key=edge_importance, reverse=True)

    # Build tension summary - skip low-stakes preference contradictions
    tension_facts = []
    seen_domains = set()
    for edge in tension_edges:
        src = mem_by_id.get(edge.source_id)
        tgt = mem_by_id.get(edge.target_id)
        if src and tgt:
            domain = src.domain or "other"
            # Skip if we already have a tension fact from this domain
            if domain in seen_domains:
                continue
            # Skip pure preference contradictions unless nothing else exists
            if domain == "preferences" and len(tension_facts) >= 2:
                continue
            tension_facts.append(
                f"- TENSION in {domain} ({edge_importance(edge):.2f}): \"{src.text[:100]}\" vs \"{tgt.text[:100]}\""
            )
            seen_domains.add(domain)
            if len(tension_facts) >= 5:
                break

    # Find the highest gravity basin and the lowest
    if basins:
        strongest = basins[0]
        weakest = basins[-1] if len(basins) > 1 else basins[0]

        strongest_memories = [mem_by_id[mid].text[:80] for mid in strongest.memory_ids[:3] if mid in mem_by_id]

        gravity_summary = f"""Strongest memory cluster: {strongest.name} ({strongest.total_mass:.1f} total trust, {len(strongest.memory_ids)} memories)
  Examples: {'; '.join(strongest_memories)}
Weakest cluster: {weakest.name} ({weakest.total_mass:.1f} total trust, {len(weakest.memory_ids)} memories)"""
    else:
        gravity_summary = "No anchor basins found."

    tension_block = "\n".join(tension_facts) if tension_facts else "No high-tension edges found."

    prompt = f"""You are an AI assistant analyzing your user's belief graph to find the most interesting question to ask them.

MEMORY GRAPH ANALYSIS:

Tension points (contradictions or evolving beliefs):
{tension_block}

Gravity analysis (where memories cluster):
{gravity_summary}

Based on this structural analysis, generate ONE thoughtful question to ask the user. The question should:
1. Address a real tension or gap you see in their memories
2. Be specific enough to be meaningful, not generic
3. Show that you noticed something they might not have noticed themselves

Output ONLY the question, nothing else."""

    start = time.time()
    question, tokens, llm_time = call_gemma3(prompt, max_tokens=150)
    total_time = (time.time() - start) * 1000

    result = LabResult(
        condition="tension_derived_question",
        query="[scaffold-generated from BRG tension]",
        output=question,
        memories_available=len(memories),
        memories_used=len(tension_facts),
        domains_covered=[b.name for b in basins[:3]],
        total_tokens=tokens,
        total_time_ms=total_time,
        scaffold_question=question,
    )

    logger.info(f"  Tension question: {question}")
    return question, result


# ── Main ──

def main():
    db_path = str(Path(_root) / "personal_agent" / "crt_memory_shared.db")

    logger.info("=" * 60)
    logger.info("SCAFFOLD CONVERSATION LAB")
    logger.info("=" * 60)

    # Load and prepare memories
    memories = load_memories_from_db(db_path, limit=200)
    memories = assign_domains(memories)

    domain_counts = {}
    for m in memories:
        domain_counts[m.domain] = domain_counts.get(m.domain, 0) + 1
    logger.info(f"Domain distribution: {json.dumps(domain_counts, indent=2)}")

    query = "What do you know about me?"

    # ── Phase 1: Three conditions ──
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: SYNTHESIS TEST")
    logger.info("=" * 60)

    result_a = run_raw_dump(memories, query)
    result_b = run_pre_filtered(memories, query)
    result_c = run_scaffolded_walk(memories, query)

    # ── Phase 2: Tension-derived question ──
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: EPISTEMIC MOTIVATION TEST")
    logger.info("=" * 60)

    basins = find_anchor_basins(memories)
    edges = find_tension_edges(memories)

    # Apply tension to basins
    for edge in edges:
        if edge.edge_type == "CONTRADICTS":
            mem = {m.id: m for m in memories}
            src = mem.get(edge.source_id)
            if src:
                for basin in basins:
                    if edge.source_id in basin.memory_ids:
                        basin.tension += edge.tension
                        basin.gravity = basin.total_mass - basin.tension

    question, result_q = derive_question_from_tension(memories, basins, edges)

    # ── Results ──
    logger.info("\n" + "=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)

    results = [result_a, result_b, result_c, result_q]

    for r in results:
        logger.info(f"\n--- {r.condition.upper()} ---")
        logger.info(f"  Memories available: {r.memories_available}")
        logger.info(f"  Memories used: {r.memories_used}")
        logger.info(f"  Domains covered: {r.domains_covered}")
        logger.info(f"  Tokens: {r.total_tokens}")
        logger.info(f"  Time: {r.total_time_ms:.0f}ms")
        logger.info(f"  Output preview: {r.output[:200]}...")
        if r.walk_steps:
            for step in r.walk_steps:
                logger.info(f"    Walk [{step.anchor}]: coherence={step.coherence_score:.1f}, {step.tokens_used} tokens")
        if r.scaffold_question:
            logger.info(f"  SCAFFOLD QUESTION: {r.scaffold_question}")

    # Save full results
    output_path = Path(__file__).parent / "results.json"
    serializable = []
    for r in results:
        d = {
            "condition": r.condition,
            "query": r.query,
            "output": r.output,
            "memories_available": r.memories_available,
            "memories_used": r.memories_used,
            "domains_covered": r.domains_covered,
            "total_tokens": r.total_tokens,
            "total_time_ms": r.total_time_ms,
            "scaffold_question": r.scaffold_question,
        }
        d["contradictions_in_output"] = r.contradictions_in_output
        if r.walk_steps:
            d["walk_steps"] = [
                {
                    "anchor": s.anchor,
                    "coherence": s.coherence_score,
                    "tokens": s.tokens_used,
                    "time_ms": s.step_time_ms,
                    "generated_text": s.generated_text,
                    "memories_used": s.memories_used,
                }
                for s in r.walk_steps
            ]
        serializable.append(d)

    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2)

    logger.info(f"\nResults saved to {output_path}")

    # ── Comparison table ──
    logger.info("\n" + "=" * 60)
    logger.info("COMPARISON")
    logger.info("=" * 60)
    logger.info(f"{'Condition':<20} {'Domains':<8} {'Tokens':<8} {'Time(ms)':<10} {'Contradictions':<15}")
    logger.info("-" * 65)
    for r in results[:3]:
        logger.info(f"{r.condition:<20} {len(r.domains_covered):<8} {r.total_tokens:<8} {r.total_time_ms:<10.0f} {r.contradictions_in_output:<15}")

    logger.info(f"\nScaffold walk coherence per step:")
    for r in results:
        if r.walk_steps:
            for step in r.walk_steps:
                logger.info(f"  [{step.anchor}] coherence={step.coherence_score:.1f} | {step.tokens_used} tokens | {step.generated_text[:80]}...")


if __name__ == "__main__":
    main()
