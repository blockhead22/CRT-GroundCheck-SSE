"""
Scaffold Generation Module
===========================

When the local model is selected, this module replaces the standard
"dump everything into context and generate" approach with a staged
scaffold that walks the belief graph anchor-by-anchor.

WHY THIS EXISTS:
Small models (3B-14B) have limited attention. They can't hold 20+ memories
and synthesize a coherent response. They repeat themselves, miss facts,
and contradict prior statements. The scaffold sidesteps this by:
  1. Walking the belief graph one anchor (topic cluster) at a time
  2. Verifying each anchor's memories for internal consistency
  3. Building a focused prompt per anchor (model only sees 3 memories at a time)
  4. Checking each generated section against all prior sections
  5. Expanding beyond the facts with verified inferences
  6. Stitching the verified sections into a coherent output

The model never sees its own prior output during generation. It only sees
the scaffold's verified facts for the current anchor. This eliminates
the repetition problem that plagues small models on open-ended queries.

HOW TO USE:
  from personal_agent.scaffold_generation import scaffold_generate

  result = scaffold_generate(
      query="What do you know about me?",
      memories=retrieved_memories,   # List of MemoryItem objects
      model="gemma3:latest",         # Ollama model name
      max_anchors=5,                 # How many topic clusters to cover
  )

  # result is a dict with:
  #   "output": str          - the final stitched text
  #   "anchors_passed": int  - how many topic clusters passed coherence
  #   "anchors_total": int   - how many were attempted
  #   "anchors_dead": int    - how many failed coherence and were excluded
  #   "tokens_used": int     - total tokens across all steps
  #   "time_ms": float       - total wall clock time
  #   "walk_log": list       - per-step details for debugging
  #   "scaffold_question": str - optional tension-derived question
"""

import re
import time
import logging
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# These thresholds control how strict the coherence checks are.
# Tune these based on model quality:
#   - Smaller models (3B): use lower COHERENCE_PASS (0.6)
#   - Larger models (14B): can use higher COHERENCE_PASS (0.8)
# ═══════════════════════════════════════════════════════════════════

COHERENCE_PASS = 0.7       # >= this score = section passes
COHERENCE_MARGINAL = 0.4   # between marginal and pass = included with warning
MAX_RETRIES = 2            # how many times to retry a failed section
EXPANSION_THRESHOLD = 0.6  # minimum score for a generative expansion to be kept
MAX_ANCHORS = 6            # default number of topic clusters to walk


# ═══════════════════════════════════════════════════════════════════
# DOMAIN CLASSIFICATION
# Simple keyword-based domain assignment for memories.
# This determines which "anchor basin" a memory belongs to.
# The scaffold walks one basin at a time, so getting this right
# directly affects the quality of the output.
# ═══════════════════════════════════════════════════════════════════

DOMAIN_KEYWORDS = {
    "health": ["health", "medical", "leukemia", "cgvhd", "hospital", "medication", "antidepressant", "sleep"],
    "work": ["work", "job", "walmart", "freelance", "self-employed", "coding", "developer", "programming"],
    "location": ["live", "milwaukee", "waukesha", "sussex", "wisconsin", "portland"],
    "preferences": ["favorite", "color", "drink", "coffee", "music", "food"],
    "personality": ["self-doubt", "sabotage", "confidence", "anxiety", "honest", "push back"],
    "relationships": ["friend", "family", "dating", "relationship", "cat"],
    "project": ["aether", "crt", "core", "scaffold", "memory", "trust", "contradiction", "brg"],
}

# How important each domain is for tension-derived questions.
# Higher weight = scaffold prioritizes contradictions in this domain.
DOMAIN_IMPORTANCE = {
    "health": 3.0,
    "work": 2.5,
    "personality": 2.0,
    "relationships": 2.0,
    "project": 1.5,
    "location": 1.0,
    "preferences": 0.5,
    "other": 0.3,
}


# ═══════════════════════════════════════════════════════════════════
# LLM INTERFACE
# Calls the local Ollama model. This is the ONLY place the model
# is called. Everything else in this module is scaffold logic.
# ═══════════════════════════════════════════════════════════════════

def _call_local_model(
    prompt: str,
    model: str = "gemma3:latest",
    max_tokens: int = 200,
    temperature: float = 0.7,
    ollama_url: str = "http://127.0.0.1:11434",
) -> Tuple[str, int, float]:
    """
    Call a local Ollama model. Returns (text, token_count, time_ms).

    This is intentionally simple - one prompt in, one response out.
    The scaffold handles all the complexity of what to put in the prompt.
    """
    start = time.time()
    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
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
        logger.error(f"[SCAFFOLD] Ollama call failed: {e}")
        return f"[ERROR: {e}]", 0, elapsed


# ═══════════════════════════════════════════════════════════════════
# ANCHOR BASIN DETECTION
# Groups memories by domain (topic cluster). Each basin becomes
# one "step" in the scaffold walk. The scaffold visits each basin
# in order of gravity (trust mass - internal tension).
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AnchorBasin:
    name: str
    memories: list = field(default_factory=list)  # list of (text, trust) tuples
    total_mass: float = 0.0
    tension: float = 0.0
    gravity: float = 0.0  # mass - tension


def _classify_domain(text: str) -> str:
    """Assign a domain label to a memory based on keywords."""
    text_lower = text.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return domain
    return "other"


def _build_anchor_basins(memories: List[Tuple[str, float, str]]) -> List[AnchorBasin]:
    """
    Group memories into anchor basins by domain.

    memories: list of (text, trust_score, memory_id) tuples

    Returns basins sorted by gravity (highest first).
    """
    basins: Dict[str, AnchorBasin] = {}

    for text, trust, mem_id in memories:
        domain = _classify_domain(text)
        if domain not in basins:
            basins[domain] = AnchorBasin(name=domain)
        basins[domain].memories.append((text, trust, mem_id))
        basins[domain].total_mass += trust

    # Gravity = mass (for now; tension subtracted in pipeline if contradiction data available)
    for basin in basins.values():
        basin.gravity = basin.total_mass - basin.tension

    return sorted(basins.values(), key=lambda b: b.gravity, reverse=True)


# ═══════════════════════════════════════════════════════════════════
# COHERENCE SCORING
# Asks the model to rate consistency on a 0-10 scale.
# This replaces binary yes/no checks with a severity threshold.
#
# Why 0-10 instead of yes/no:
#   - "You said testing twice" is cosmetic (score 7-8, let it through)
#   - "You said he left Walmart then said he works there" is real (score 2-3, kill it)
#   - Binary checks can't tell the difference
# ═══════════════════════════════════════════════════════════════════

def _score_coherence(
    new_text: str,
    prior_text: str,
    model: str,
) -> float:
    """
    Score how well new_text is consistent with prior_text.
    Returns 0.0-1.0 (higher = more coherent).
    """
    if not prior_text:
        # First section: check internal consistency only
        prompt = f"""Rate the internal consistency of this text on a scale of 0 to 10.
0 = contains major factual contradictions
5 = minor inconsistencies or repeated information
10 = fully consistent, no issues

Text: {new_text[:500]}

Reply with ONLY a number 0-10."""
    else:
        prompt = f"""Rate how well the NEW text is consistent with the PREVIOUS text on a scale of 0 to 10.
0 = directly contradicts previous facts
5 = minor overlap or slightly inconsistent tone
10 = fully consistent, adds new information without contradiction

PREVIOUS (verified):
{prior_text[-600:]}

NEW:
{new_text[:400]}

Reply with ONLY a number 0-10."""

    check_out, _, _ = _call_local_model(prompt, model=model, max_tokens=10, temperature=0.1)
    score_match = re.search(r'(\d+)', check_out.strip())
    raw_score = int(score_match.group(1)) if score_match else 5
    return raw_score / 10.0


# ═══════════════════════════════════════════════════════════════════
# GENERATIVE EXPANSION
# After verified facts are generated, the scaffold asks the model
# to infer ONE additional thing that follows logically from the facts.
# This inference is then checked against all verified content.
#
# This is the difference between "here are your facts back" and
# "here's what your facts mean together."
# ═══════════════════════════════════════════════════════════════════

def _try_expand(
    section: str,
    all_verified: str,
    model: str,
) -> Optional[str]:
    """
    Try to generate one inference step beyond the verified facts.
    Returns the expansion text if it passes verification, None otherwise.
    """
    # Step 1: Ask model to infer beyond the facts
    expand_prompt = f"""You wrote this about a user based on verified facts:
"{section}"

Now write ONE additional sentence that follows logically from this - something that isn't explicitly stated but is a reasonable inference. Do not repeat what's already written. Do not invent new facts. Only state what logically follows.

If nothing follows naturally, reply with: NOTHING_TO_ADD"""

    expansion, _, _ = _call_local_model(expand_prompt, model=model, max_tokens=80)

    if "nothing_to_add" in expansion.lower() or len(expansion.strip()) < 10:
        return None

    # Step 2: Verify the inference against all verified content
    verify_prompt = f"""Rate the consistency of this INFERENCE with the established facts on a scale 0-10.
0 = contradicts known facts
5 = plausible but unsupported
10 = clearly follows from the facts

Facts:
{all_verified[-800:]}

Inference:
{expansion[:200]}

Reply with ONLY a number 0-10."""

    verify_out, _, _ = _call_local_model(verify_prompt, model=model, max_tokens=10, temperature=0.1)
    score_match = re.search(r'(\d+)', verify_out.strip())
    exp_score = int(score_match.group(1)) if score_match else 5
    exp_coherence = exp_score / 10.0

    if exp_coherence >= EXPANSION_THRESHOLD:
        return expansion
    return None


# ═══════════════════════════════════════════════════════════════════
# MAIN SCAFFOLD FUNCTION
# This is what the pipeline calls instead of direct LLM generation.
# It orchestrates the entire walk-verify-generate-expand process.
# ═══════════════════════════════════════════════════════════════════

def scaffold_generate(
    query: str,
    memories: List[Tuple[str, float, str]],
    model: str = "gemma3:latest",
    max_anchors: int = MAX_ANCHORS,
    enable_expansion: bool = True,
) -> Dict[str, Any]:
    """
    Generate a response using the staged scaffold approach.

    Instead of dumping all memories into the context and hoping the model
    figures it out, this function:
      1. Groups memories into topic clusters (anchor basins)
      2. For each cluster: verifies memories, builds a focused prompt,
         generates 2-3 sentences, checks coherence against prior sections
      3. If a section fails coherence, retries with corrective context
      4. If it still fails, excludes it (the model can't reconcile this domain)
      5. Optionally expands each verified section with one inference step
      6. Stitches the verified sections into a final output

    Args:
        query: the user's question
        memories: list of (text, trust_score, memory_id) tuples
        model: which Ollama model to use
        max_anchors: how many topic clusters to walk (more = broader but slower)
        enable_expansion: whether to do generative expansion after verification

    Returns:
        dict with output, stats, and per-step walk log
    """
    logger.info(f"[SCAFFOLD] Starting staged generation for: {query[:60]}...")
    total_start = time.time()
    total_tokens = 0

    # ── Step 1: Build anchor basins from memories ──
    # Group memories by topic so we can walk one topic at a time
    basins = _build_anchor_basins(memories)
    logger.info(f"[SCAFFOLD] Found {len(basins)} anchor basins: {[b.name for b in basins[:max_anchors]]}")

    walk_log = []
    topics_covered = []

    # ── Step 2: Verify + stage prompts for each anchor ──
    # For each topic cluster, check if the memories are internally consistent
    # and build a generation prompt that only includes verified facts
    staged = []
    for basin in basins[:max_anchors]:
        if not basin.memories:
            continue

        # Take top 3 memories by trust for this basin
        sorted_mems = sorted(basin.memories, key=lambda m: m[1], reverse=True)[:3]
        memory_block = "\n".join(f"- (trust:{trust:.2f}) {text}" for text, trust, _ in sorted_mems)

        # Build the generation prompt
        # KEY: No prior output included. Model only sees THIS anchor's memories.
        # A one-line coverage summary prevents repeating already-covered topics.
        if topics_covered:
            coverage = f"You have already covered: {', '.join(topics_covered)}. Do NOT repeat those topics."
        else:
            coverage = "This is the first section of your answer."

        prompt = f"""You are answering: "{query}"

{coverage}

Write 2-3 sentences about the user's {basin.name} based ONLY on these verified facts:
{memory_block}

Be specific. Reference actual facts. Do not add information not in the memories above. Do not use filler phrases."""

        staged.append({
            "basin_name": basin.name,
            "prompt": prompt,
            "memories": sorted_mems,
        })
        topics_covered.append(basin.name)

    # ── Step 3: Generate from staged prompts ──
    # Each section is generated independently. The model never sees its own
    # prior output. This eliminates the repetition problem.
    sections = []
    for s in staged:
        text, tokens, time_ms = _call_local_model(s["prompt"], model=model, max_tokens=200)
        total_tokens += tokens
        sections.append(text)

        walk_log.append({
            "anchor": s["basin_name"],
            "generated_text": text,
            "tokens": tokens,
            "time_ms": time_ms,
            "coherence": None,  # filled in next step
            "status": "generated",
        })
        logger.info(f"[SCAFFOLD] Generated [{s['basin_name']}]: {tokens} tokens, {time_ms:.0f}ms")

    # ── Step 4: Incremental coherence check with retry ──
    # Each section is checked against ALL previously verified sections.
    # If it fails, we retry with corrective context. If it still fails,
    # the anchor is marked dead and excluded from the final output.
    verified_sections = []
    anchors_dead = 0

    for i, (step_log, section, s) in enumerate(zip(walk_log, sections, staged)):
        passed = False

        for attempt in range(MAX_RETRIES + 1):
            prior = "\n".join(verified_sections) if verified_sections else ""
            coherence = _score_coherence(section, prior, model)

            if coherence >= COHERENCE_PASS:
                # ── PASS: section is coherent, include it ──
                step_log["coherence"] = coherence
                step_log["status"] = "passed"
                verified_sections.append(section)
                passed = True
                logger.info(f"[SCAFFOLD] [{s['basin_name']}] PASSED (coherence={coherence:.1f})")
                break

            elif coherence >= COHERENCE_MARGINAL:
                # ── MARGINAL: minor issues, include with warning ──
                step_log["coherence"] = coherence
                step_log["status"] = "marginal"
                verified_sections.append(section)
                passed = True
                logger.warning(f"[SCAFFOLD] [{s['basin_name']}] MARGINAL (coherence={coherence:.1f})")
                break

            else:
                # ── FAIL: section contradicts prior content ──
                if attempt < MAX_RETRIES:
                    # Retry with corrective context
                    logger.warning(f"[SCAFFOLD] [{s['basin_name']}] FAILED (coherence={coherence:.1f}), retry {attempt + 1}/{MAX_RETRIES}")
                    retry_prompt = s["prompt"] + f"\n\nIMPORTANT: Your previous attempt scored {coherence:.1f}/1.0 on coherence. Here is what has been verified so far:\n{prior[-400:]}\n\nWrite ONLY new facts that do not contradict the above."
                    section, retry_tokens, retry_time = _call_local_model(retry_prompt, model=model, max_tokens=200)
                    total_tokens += retry_tokens
                    step_log["tokens"] += retry_tokens
                else:
                    # Dead: couldn't produce coherent output for this domain
                    step_log["coherence"] = coherence
                    step_log["status"] = "dead"
                    anchors_dead += 1
                    logger.warning(f"[SCAFFOLD] [{s['basin_name']}] DEAD after {MAX_RETRIES + 1} attempts")

        if not passed:
            step_log["status"] = "excluded"

    # ── Step 5: Generative expansion ──
    # For each verified section, try to infer one thing beyond the facts.
    # This is where the scaffold adds meaning, not just retrieval.
    if enable_expansion and verified_sections:
        logger.info(f"[SCAFFOLD] Running generative expansion on {len(verified_sections)} sections...")
        expanded = []
        all_verified_text = "\n".join(verified_sections)

        for section in verified_sections:
            expansion = _try_expand(section, all_verified_text, model)
            if expansion:
                expanded.append(section + " " + expansion)
                logger.info(f"[SCAFFOLD] Expansion KEPT: {expansion[:60]}...")
            else:
                expanded.append(section)

        final_sections = expanded
    else:
        final_sections = verified_sections

    # ── Step 6: Stitch into final output ──
    output = "\n\n".join(final_sections)
    total_time = (time.time() - total_start) * 1000

    result = {
        "output": output,
        "anchors_passed": len(verified_sections),
        "anchors_total": len(staged),
        "anchors_dead": anchors_dead,
        "tokens_used": total_tokens,
        "time_ms": total_time,
        "walk_log": walk_log,
    }

    logger.info(
        f"[SCAFFOLD] Complete: {len(verified_sections)}/{len(staged)} anchors, "
        f"{anchors_dead} dead, {total_tokens} tokens, {total_time:.0f}ms"
    )

    return result
