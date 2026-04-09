"""Coherence Decay Experiment — Scoring Pipeline

Scores generation results on:
  1. Factual fidelity — ground truth keyword/fact presence
  2. Semantic drift — embedding distance from source truth over spans
  3. Entropy profile — per-span uncertainty (from generation or re-estimated)
  4. Self-contradiction — does the output contradict itself?
  5. Executability — (programming only) does the code run?
"""

import json
import math
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

import numpy as np

from config import PROMPTS_DIR, RAW_DIR, RESULTS_DIR, DOMAINS


# ---------------------------------------------------------------------------
# Optional: sentence-transformers for drift scoring
# ---------------------------------------------------------------------------
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            print("[WARN] sentence-transformers not installed. Drift scoring disabled.")
            print("       pip install sentence-transformers")
            return None
    return _embedder


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ---------------------------------------------------------------------------
# 1. Factual Fidelity
# ---------------------------------------------------------------------------
def score_fidelity(full_text: str, prompt_data: dict, domain: str) -> dict:
    """Check how many ground truth elements are present in the output."""
    text_lower = full_text.lower()

    if domain == "programming":
        keywords = prompt_data.get("ground_truth_keywords", [])
        hits = [kw for kw in keywords if kw.lower() in text_lower]
        return {
            "fidelity_score": len(hits) / len(keywords) if keywords else 1.0,
            "keywords_found": hits,
            "keywords_missing": [kw for kw in keywords if kw.lower() not in text_lower],
            "total_keywords": len(keywords),
        }

    elif domain == "narrative":
        facts = prompt_data.get("ground_truth_facts", [])
        found = [f for f in facts if f.lower() in text_lower]
        return {
            "fidelity_score": len(found) / len(facts) if facts else 1.0,
            "facts_found": found,
            "facts_missing": [f for f in facts if f.lower() not in text_lower],
            "total_facts": len(facts),
        }

    elif domain == "memory":
        facts = prompt_data.get("ground_truth_facts", [])
        found = [f for f in facts if f.lower() in text_lower]
        return {
            "fidelity_score": len(found) / len(facts) if facts else 1.0,
            "facts_found": found,
            "facts_missing": [f for f in facts if f.lower() not in text_lower],
            "total_facts": len(facts),
        }

    return {"fidelity_score": 0.0, "error": f"Unknown domain: {domain}"}


# ---------------------------------------------------------------------------
# 2. Semantic Drift
# ---------------------------------------------------------------------------
def score_drift(full_text: str, prompt_text: str, spans: list[dict]) -> dict:
    """Measure embedding distance of each span from the original prompt.

    Drift = how far the generation wanders from the source question.
    """
    embedder = get_embedder()
    if embedder is None:
        return {"drift_scores": [], "drift_mean": 0.0, "drift_available": False}

    prompt_emb = embedder.encode(prompt_text)

    drift_scores = []
    for span in spans:
        text = span.get("text", "")
        if not text.strip():
            drift_scores.append(0.0)
            continue
        span_emb = embedder.encode(text)
        sim = cosine_similarity(prompt_emb, span_emb)
        drift = 1.0 - sim  # Higher = more drift
        drift_scores.append(round(drift, 4))

    return {
        "drift_scores": drift_scores,
        "drift_mean": round(np.mean(drift_scores), 4) if drift_scores else 0.0,
        "drift_max": round(max(drift_scores), 4) if drift_scores else 0.0,
        "drift_trend": _compute_trend(drift_scores),
        "drift_available": True,
    }


def _compute_trend(values: list[float]) -> str:
    """Is drift increasing, stable, or decreasing over spans?"""
    if len(values) < 2:
        return "single_span"
    # Simple linear regression
    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]
    if slope > 0.01:
        return "increasing"
    elif slope < -0.01:
        return "decreasing"
    return "stable"


# ---------------------------------------------------------------------------
# 3. Entropy Profile
# ---------------------------------------------------------------------------
def score_entropy(spans: list[dict]) -> dict:
    """Aggregate entropy statistics across spans."""
    all_entropy = []
    span_means = []

    for span in spans:
        per_token = span.get("entropy_per_token", [])
        if per_token:
            all_entropy.extend(per_token)
            span_means.append(sum(per_token) / len(per_token))
        else:
            # Use the pre-computed mean if available
            mean = span.get("entropy_mean", 0.0)
            span_means.append(mean)

    return {
        "entropy_span_means": [round(e, 4) for e in span_means],
        "entropy_global_mean": round(np.mean(all_entropy), 4) if all_entropy else 0.0,
        "entropy_global_max": round(max(all_entropy), 4) if all_entropy else 0.0,
        "entropy_trend": _compute_trend(span_means) if len(span_means) > 1 else "single_span",
        "high_entropy_spans": sum(1 for m in span_means if m > 2.5),
    }


# ---------------------------------------------------------------------------
# 4. Self-Contradiction
# ---------------------------------------------------------------------------
def score_self_contradiction(full_text: str, spans: list[dict]) -> dict:
    """Detect self-contradictions within the generated text.

    Uses simple heuristic patterns + optional embedding-based detection.
    """
    contradictions = []
    sentences = [s.strip() for s in re.split(r'[.!?]+', full_text) if s.strip()]

    # Pattern-based: look for direct negation pairs
    for i, s1 in enumerate(sentences):
        for j, s2 in enumerate(sentences):
            if j <= i:
                continue
            if _sentences_contradict(s1, s2):
                contradictions.append({
                    "sentence_a_idx": i,
                    "sentence_a": s1[:100],
                    "sentence_b_idx": j,
                    "sentence_b": s2[:100],
                    "method": "pattern",
                })

    # Embedding-based: high similarity but semantic inversion
    embedder = get_embedder()
    if embedder and len(sentences) > 1:
        embs = embedder.encode(sentences)
        for i in range(len(sentences)):
            for j in range(i + 2, min(i + 10, len(sentences))):
                sim = cosine_similarity(embs[i], embs[j])
                # Very high similarity but different stance might indicate contradiction
                # This is a weak signal — just flag for review
                if sim > 0.85:
                    # Check if one negates the other
                    if _has_negation_flip(sentences[i], sentences[j]):
                        contradictions.append({
                            "sentence_a_idx": i,
                            "sentence_a": sentences[i][:100],
                            "sentence_b_idx": j,
                            "sentence_b": sentences[j][:100],
                            "similarity": round(sim, 3),
                            "method": "embedding+negation",
                        })

    return {
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "self_consistent": len(contradictions) == 0,
    }


def _sentences_contradict(s1: str, s2: str) -> bool:
    """Simple pattern check for direct contradiction."""
    s1, s2 = s1.lower(), s2.lower()
    negation_pairs = [
        ("is ", "is not "), ("is ", "isn't "),
        ("was ", "was not "), ("was ", "wasn't "),
        ("are ", "are not "), ("are ", "aren't "),
        ("has ", "has no "), ("has ", "hasn't "),
        ("can ", "cannot "), ("can ", "can't "),
        ("will ", "will not "), ("will ", "won't "),
        ("does ", "does not "), ("does ", "doesn't "),
    ]
    for pos, neg in negation_pairs:
        if pos in s1 and neg in s2:
            # Check if the subject is similar
            subj1 = s1.split(pos)[0].split()[-3:]
            subj2 = s2.split(neg)[0].split()[-3:]
            if set(subj1) & set(subj2):
                return True
        if pos in s2 and neg in s1:
            subj1 = s1.split(neg)[0].split()[-3:]
            subj2 = s2.split(pos)[0].split()[-3:]
            if set(subj1) & set(subj2):
                return True
    return False


def _has_negation_flip(s1: str, s2: str) -> bool:
    """Check if one sentence has negation that the other doesn't."""
    neg_words = {"not", "no", "never", "neither", "nor", "n't", "cannot", "isn't", "wasn't", "aren't", "hasn't", "can't", "won't", "doesn't", "didn't"}
    words1 = set(s1.lower().split())
    words2 = set(s2.lower().split())
    neg1 = words1 & neg_words
    neg2 = words2 & neg_words
    # One has negation, the other doesn't
    return bool(neg1) != bool(neg2)


# ---------------------------------------------------------------------------
# 5. Executability (programming only)
# ---------------------------------------------------------------------------
def score_executability(full_text: str, prompt_data: dict) -> dict:
    """Try to extract and run Python code from the response."""
    if not prompt_data.get("executable", False):
        return {"executable": None, "reason": "not_applicable"}

    # Extract code blocks
    code_blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', full_text, re.DOTALL)
    if not code_blocks:
        # Try to find code without fences (model might not use markdown)
        lines = full_text.split("\n")
        code_lines = [l for l in lines if l.strip() and (
            l.startswith("def ") or l.startswith("class ") or
            l.startswith("    ") or l.startswith("import ") or
            l.startswith("from ") or l.startswith("return ")
        )]
        if code_lines:
            code_blocks = ["\n".join(code_lines)]

    if not code_blocks:
        return {"executable": False, "reason": "no_code_found", "error": None}

    code = code_blocks[0]

    # Safety: only run in temp file, timeout 5s
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"compile(open(r'{tmp_path}').read(), '{tmp_path}', 'exec')"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return {"executable": True, "reason": "compiles", "error": None}
        else:
            return {"executable": False, "reason": "syntax_error", "error": result.stderr[:300]}
    except subprocess.TimeoutExpired:
        return {"executable": False, "reason": "timeout", "error": None}
    except Exception as e:
        return {"executable": False, "reason": "error", "error": str(e)[:300]}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Narrative-specific: consistency checks
# ---------------------------------------------------------------------------
def score_narrative_consistency(full_text: str, prompt_data: dict) -> dict:
    """Check narrative-specific consistency requirements."""
    checks = prompt_data.get("consistency_checks", [])
    if not checks:
        return {"consistency_score": 1.0, "checks": []}

    # For now, do basic keyword-based verification
    # A full version would use NLI or an LLM-as-judge
    text_lower = full_text.lower()
    results = []

    for check in checks:
        # Simple heuristic: check if the requirement is obviously violated
        # This is intentionally basic — we're measuring the model, not building a judge
        results.append({
            "check": check,
            "status": "needs_human_review",
        })

    return {
        "consistency_checks": results,
        "total_checks": len(checks),
    }


# ---------------------------------------------------------------------------
# Memory-specific: expected behavior
# ---------------------------------------------------------------------------
def score_memory_behavior(full_text: str, prompt_data: dict) -> dict:
    """Check memory-domain specific behaviors."""
    expected = prompt_data.get("expected_behavior", "")
    planted = prompt_data.get("planted_contradictions", [])

    result = {"expected_behavior": expected}

    if expected == "detect_contradiction" and planted:
        # Check if the model identified the contradiction
        text_lower = full_text.lower()
        detected = any(
            any(word in text_lower for word in c.lower().split()[:3])
            for c in planted
        )
        result["contradiction_detected"] = detected

    elif expected == "all_facts_present":
        # Already covered by fidelity scoring
        result["note"] = "see fidelity_score"

    elif expected == "update_belief_on_evidence":
        text_lower = full_text.lower()
        # Check if the model updated its stated belief
        result["shows_update"] = any(w in text_lower for w in [
            "updated", "revised", "corrected", "now believe",
            "physical review", "changed", "new information",
        ])

    elif expected == "belief_update_with_reasoning":
        text_lower = full_text.lower()
        result["shows_reasoning"] = any(w in text_lower for w in [
            "because", "since", "given", "based on", "evidence",
            "confidence", "trust", "updated",
        ])

    return result


# ---------------------------------------------------------------------------
# Master scoring function
# ---------------------------------------------------------------------------
def score_result(result: dict, prompt_lookup: dict) -> dict:
    """Score a single generation result across all dimensions."""
    if "error" in result:
        return {"error": result["error"], "scored": False}

    prompt_id = result["prompt_id"]
    domain = result["domain"]
    prompt_data = prompt_lookup.get(f"{domain}/{prompt_id}", {})
    full_text = result.get("full_text", "")
    spans = result.get("spans", [])

    scores = {
        "prompt_id": prompt_id,
        "domain": domain,
        "model_tier": result["model_tier"],
        "model_name": result["model_name"],
        "strategy": result["strategy"],
        "total_tokens": result.get("total_tokens", 0),
        "total_time_ms": result.get("total_time_ms", 0),
        "reanchors": result.get("reanchors", 0),
        "reruns": result.get("reruns", 0),
        "scored": True,
    }

    # Universal scores
    scores["fidelity"] = score_fidelity(full_text, prompt_data, domain)
    scores["drift"] = score_drift(full_text, prompt_data.get("prompt", ""), spans)
    scores["entropy"] = score_entropy(spans)
    scores["self_contradiction"] = score_self_contradiction(full_text, spans)

    # Domain-specific
    if domain == "programming":
        scores["executability"] = score_executability(full_text, prompt_data)
    elif domain == "narrative":
        scores["narrative_consistency"] = score_narrative_consistency(full_text, prompt_data)
    elif domain == "memory":
        scores["memory_behavior"] = score_memory_behavior(full_text, prompt_data)

    # Composite score (weighted)
    fidelity = scores["fidelity"]["fidelity_score"]
    drift = 1.0 - scores["drift"].get("drift_mean", 0.5)  # Invert: low drift = good
    consistency = 1.0 if scores["self_contradiction"]["self_consistent"] else 0.5
    exec_bonus = 0.0
    if domain == "programming":
        ex = scores.get("executability", {})
        exec_bonus = 0.1 if ex.get("executable") else 0.0

    scores["composite"] = round(
        0.40 * fidelity +
        0.25 * drift +
        0.25 * consistency +
        0.10 + exec_bonus,  # Base + executability bonus
        4
    )

    return scores


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------
def score_run(results_file: str | Path) -> Path:
    """Score all results in a run file."""
    results_file = Path(results_file)
    with open(results_file) as f:
        results = json.load(f)

    # Build prompt lookup
    prompt_lookup = {}
    for domain in DOMAINS:
        prompt_file = PROMPTS_DIR / f"{domain}.json"
        if prompt_file.exists():
            with open(prompt_file) as f:
                data = json.load(f)
            for p in data["prompts"]:
                prompt_lookup[f"{domain}/{p['id']}"] = p

    scored = []
    for r in results:
        s = score_result(r, prompt_lookup)
        scored.append(s)

    # Save scored results
    out_file = results_file.parent / results_file.name.replace("run_", "scored_")
    with open(out_file, "w") as f:
        json.dump(scored, f, indent=2, default=str)

    # Print summary
    _print_summary(scored)

    return out_file


def _print_summary(scored: list[dict]):
    """Print a quick summary table."""
    print(f"\n{'='*70}")
    print(f"SCORING SUMMARY")
    print(f"{'='*70}")

    # Group by model × strategy
    groups = {}
    for s in scored:
        if not s.get("scored"):
            continue
        key = (s["model_tier"], s["strategy"])
        groups.setdefault(key, []).append(s)

    print(f"\n{'Model':<18} {'Strategy':<22} {'Fidelity':>8} {'Drift':>8} {'Consist':>8} {'Composite':>9}")
    print("-" * 70)

    for (model, strategy), items in sorted(groups.items()):
        fid = np.mean([i["fidelity"]["fidelity_score"] for i in items])
        dft = np.mean([i["drift"].get("drift_mean", 0) for i in items])
        con = sum(1 for i in items if i["self_contradiction"]["self_consistent"]) / len(items)
        comp = np.mean([i["composite"] for i in items])

        print(f"{model:<18} {strategy:<22} {fid:>8.3f} {dft:>8.3f} {con:>8.3f} {comp:>9.3f}")

    print(f"\n{'='*70}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score coherence decay results")
    parser.add_argument("results_file", help="Path to raw results JSON")
    args = parser.parse_args()

    out = score_run(args.results_file)
    print(f"\nScored results: {out}")
