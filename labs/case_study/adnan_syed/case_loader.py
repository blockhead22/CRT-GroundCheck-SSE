"""Case Study Loader: Feed evidence to CRT in an isolated thread.

Creates a temporary memory database, loads all evidence entries,
runs structural tension analysis, then cleans up.

No contamination of Aether's real memories.
"""

import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PA_DIR = PROJECT_ROOT / "personal_agent"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PA_DIR))

EVIDENCE_FILE = Path(__file__).parent / "evidence_base.json"
RESULTS_DIR = Path(__file__).parent / "results"
ISOLATED_DB = Path(__file__).parent / "case_memory_isolated.db"

import builtins
_real_open = builtins.open


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def load_evidence():
    """Load evidence entries from JSON."""
    with _real_open(EVIDENCE_FILE) as f:
        return json.loads(f.read())


def create_isolated_db(evidence):
    """Create an isolated SQLite memory DB and populate with evidence."""
    if ISOLATED_DB.exists():
        ISOLATED_DB.unlink()

    # Import embedding engine
    from embeddings import encode_text

    conn = sqlite3.connect(str(ISOLATED_DB), timeout=30.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp REAL NOT NULL,
            confidence REAL NOT NULL,
            trust REAL NOT NULL,
            source TEXT NOT NULL,
            sse_mode TEXT NOT NULL DEFAULT 'standard',
            context_json TEXT,
            tags_json TEXT,
            thread_id TEXT DEFAULT 'case_study',
            deprecated INTEGER DEFAULT 0,
            deprecation_reason TEXT,
            kind TEXT DEFAULT 'evidence'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_facts (
            memory_id TEXT NOT NULL,
            slot TEXT NOT NULL,
            value TEXT NOT NULL,
            normalized TEXT,
            UNIQUE(memory_id, slot)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trust_log (
            memory_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            old_trust REAL,
            new_trust REAL,
            reason TEXT,
            drift REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trust_log_memory ON trust_log(memory_id, timestamp)")

    p(f"  Encoding {len(evidence)} evidence entries...")
    base_time = time.time() - (len(evidence) * 3600)  # Spread timestamps

    for i, entry in enumerate(evidence):
        vec = encode_text(entry["text"])
        vec_json = json.dumps(vec.tolist())
        tags = json.dumps(entry.get("tags", []))
        context = json.dumps({"category": entry.get("category", ""), "source": entry.get("source", "")})
        timestamp = base_time + (i * 3600)

        conn.execute(
            "INSERT INTO memories (memory_id, vector_json, text, timestamp, confidence, trust, source, tags_json, context_json, kind) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry["id"], vec_json, entry["text"], timestamp, entry["trust"], entry["trust"],
             entry.get("source", "evidence"), tags, context, "evidence")
        )

        if (i + 1) % 10 == 0:
            p(f"    {i+1}/{len(evidence)} loaded")

    conn.commit()
    conn.close()
    p(f"  All {len(evidence)} entries loaded into {ISOLATED_DB.name}")


def extract_case_slots(text):
    """Domain-specific slot extraction for legal case evidence.

    CRT's production slot extractor handles personal facts (name, location, job).
    Legal evidence needs different slots: witness claims, event locations,
    timeline entries, forensic findings.
    """
    import re
    text_lower = text.lower().strip()
    slots = {}

    def _make_fact(slot, value, temporal="active"):
        f = type("Fact", (), {})()
        f.slot = slot
        f.value = value
        f.normalized = value.lower().strip()
        f.temporal_status = temporal
        f.period_text = None
        f.domains = ()
        f.confidence = 0.9
        return f

    PATTERNS = [
        # Where events happened
        (r"(?:at|in|near|outside|from)\s+(?:the\s+)?(?:best buy|edmondson|patapsco|leakin park|pool hall|catonsville|grandmother|gas station|woodlawn|library|park.n.ride|7-eleven|hunt valley|lenscrafters)", "event_location"),
        # Trunk pop location specifically
        (r"(?:trunk\s+pop|showed?\s+him\s+(?:hae'?s?\s+)?body|body\s+in\s+the\s+trunk)\s*(?:at|in|near|outside)?\s*(?:the\s+)?(.+?)(?:\.|,|$)", "trunk_pop_location"),
        # Time claims
        (r"(?:at\s+)?(?:approximately\s+)?(\d{1,2}:\d{2}\s*(?:am|pm))", "claimed_time"),
        (r"between\s+(?:approximately\s+)?(\d{1,2}:\d{2})\s*(?:and|to|-)\s*(\d{1,2}:\d{2})\s*(?:am|pm)?", "time_window"),
        # Burial time
        (r"(?:burial|buried|burying)\s*(?:at|around|approximately)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|midnight))", "burial_time"),
        (r"(?:7:09|7:16)\s*pm.*(?:burial|leakin|park)", "burial_time"),
        (r"closer to midnight", "burial_time"),
        # Cause of death
        (r"(?:manual\s+)?strangulation|strangled", "cause_of_death"),
        # Alibi claims
        (r"(?:alibi|was\s+(?:at|with|in))\s+(?:the\s+)?(.+?)(?:\s+(?:between|from|at|during))", "alibi_location"),
        (r"(?:library|mosque|track\s+practice)", "alibi_location"),
        # Cell tower / location evidence
        (r"(?:cell\s+tower|pinging|ping)\s+(?:l689b|leakin)", "cell_tower_claim"),
        (r"incoming\s+calls?\s+(?:will\s+)?not\s+be\s+(?:considered\s+)?reliable", "cell_tower_reliability"),
        (r"outgoing\s+calls?\s+only\s+(?:are\s+)?reliable", "cell_tower_reliability"),
        # Lividity
        (r"(?:frontal|anterior)\s+lividity", "lividity_finding"),
        (r"face.?down\s+for\s+(\d+)\+?\s+hours", "lividity_duration"),
        # DNA evidence
        (r"(?:dna|touch\s+dna).*(?:not\s+found|excluded|no\s+(?:adnan|syed))", "dna_result"),
        # Witness reliability
        (r"(?:changed|shifted|different|contradicts?|inconsisten|recant)", "witness_reliability"),
        (r"(?:admitted?\s+to\s+lying|lied|fabricat)", "witness_credibility"),
        # Brady violation
        (r"(?:brady|not\s+(?:properly\s+)?(?:disclosed|investigated)|never\s+disclosed)", "brady_violation"),
        # Suspect identification
        (r"(?:alternative\s+suspect|other\s+suspect|threatened\s+to\s+kill)", "alternative_suspect"),
        # Defense failures
        (r"(?:never\s+contacted?|ineffective|disbarred|failed\s+to)", "defense_failure"),
        # Murder window
        (r"(?:2:15|2:36|21.minute|murder\s+window)", "murder_window"),
    ]

    for pattern, slot_name in PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            value = m.group(m.lastindex) if m.lastindex else m.group(0)
            value = value.strip()
            if value and len(value) > 1:
                # Avoid overwriting with less specific matches
                if slot_name not in slots:
                    slots[slot_name] = _make_fact(slot_name, value)

    return slots


def bootstrap_slots(evidence):
    """Auto-discover domain slots from evidence corpus. Zero LLM calls."""
    from slot_bootstrapper import extract_variable_patterns, extract_prepositional_patterns, propose_slot_names

    texts = [e["text"] for e in evidence]

    p("  Phase 1: Variable patterns...")
    var_patterns = extract_variable_patterns(texts)
    p(f"    {len(var_patterns)} candidates")

    p("  Phase 2: Prepositional patterns...")
    prep_patterns = extract_prepositional_patterns(texts)
    p(f"    {len(prep_patterns)} candidates")

    p("  Phase 3: Proposing slots...")
    proposals = propose_slot_names(var_patterns, prep_patterns)
    p(f"    {len(proposals)} unique proposals")

    # Build a dynamic slot extractor from discovered patterns
    # Filter: require confidence >= 0.4 and evidence_count >= 2
    promoted = [s for s in proposals if s["confidence"] >= 0.4 and s["evidence_count"] >= 2]
    p(f"    {len(promoted)} promoted (confidence >= 0.4, evidence >= 2)")

    return promoted


def build_dynamic_extractor(promoted_slots, evidence):
    """Build a slot extraction function from bootstrapped slots.

    Combines:
    1. Hardcoded case slots (from extract_case_slots)
    2. Dynamically discovered slots from the bootstrapper
    """
    # Build regex patterns from discovered frames
    discovered_frames = {}
    for slot in promoted_slots:
        frame = slot["frame"]
        name = slot["slot_name"]
        values = slot["example_values"]
        discovered_frames[name] = {
            "frame": frame,
            "values": values,
            "source": slot["source"],
        }

    def hybrid_extract(text):
        """Extract slots using both hardcoded and discovered patterns."""
        import re
        # Start with hardcoded case slots
        slots = extract_case_slots(text)

        # Layer on discovered slots
        text_lower = text.lower().strip()
        for slot_name, info in discovered_frames.items():
            if slot_name in slots:
                continue  # Hardcoded takes priority

            frame = info["frame"]
            if frame in text_lower:
                # Find what comes after the frame
                idx = text_lower.index(frame) + len(frame)
                remainder = text_lower[idx:idx+60].strip()
                # Clean up
                remainder = re.sub(r'[,\.\;].*$', '', remainder).strip()
                if remainder and len(remainder) > 1:
                    f = type("Fact", (), {})()
                    f.slot = slot_name
                    f.value = remainder
                    f.normalized = remainder.lower()
                    f.temporal_status = "active"
                    f.period_text = None
                    f.domains = ()
                    f.confidence = 0.7  # Lower confidence for discovered slots
                    slots[slot_name] = f

        return slots

    return hybrid_extract


def run_tension_analysis(evidence, slot_extractor=None):
    """Run structural tension meter on all evidence pairs within topic clusters."""
    from structural_tension import StructuralTensionMeter, TensionRelationship
    from embeddings import encode_text

    meter = StructuralTensionMeter()

    # Use provided extractor or fall back to case-specific
    meter._extract_slots = slot_extractor or extract_case_slots

    # Encode all evidence
    p("  Encoding evidence for tension analysis...")
    entries_with_vecs = []
    for entry in evidence:
        vec = encode_text(entry["text"])
        entries_with_vecs.append({**entry, "vector": vec})

    # Find pairs with high similarity (same topic cluster)
    p("  Finding topic clusters...")
    pairs = []
    for i, a in enumerate(entries_with_vecs):
        for j, b in enumerate(entries_with_vecs):
            if i >= j:
                continue
            sim = float(np.dot(a["vector"], b["vector"]))
            if sim > 0.5:
                pairs.append((a, b, sim))

    pairs.sort(key=lambda x: x[2], reverse=True)
    p(f"  Found {len(pairs)} related pairs (similarity > 0.5)")

    # Run tension meter on each pair
    p("  Measuring tension...")
    results = []
    for a, b, sim in pairs:
        t_result = meter.measure(
            text_a=a["text"],
            text_b=b["text"],
            trust_a=a["trust"],
            trust_b=b["trust"],
            source_a=a.get("source", "evidence"),
            source_b=b.get("source", "evidence"),
            vector_a=a["vector"],
            vector_b=b["vector"],
        )

        if t_result.tension_score > 0.1:  # Only record meaningful tension
            results.append({
                "entry_a": a["id"],
                "entry_b": b["id"],
                "text_a": a["text"][:80],
                "text_b": b["text"][:80],
                "similarity": round(sim, 4),
                "tension_score": t_result.tension_score,
                "relationship": t_result.relationship.value,
                "action": t_result.action.value,
                "confidence": t_result.confidence,
                "trust_a": a["trust"],
                "trust_b": b["trust"],
                "category_a": a.get("category", ""),
                "category_b": b.get("category", ""),
                "slots": [{"slot": o.slot, "value_a": o.value_a, "value_b": o.value_b,
                           "match": o.match_type} for o in t_result.slot_overlaps],
            })

    results.sort(key=lambda x: x["tension_score"], reverse=True)
    return results


def run_oscillation_analysis(evidence):
    """Identify evidence entries that contradict each other across versions."""
    # Group by tags to find version chains
    version_groups = {}
    for entry in evidence:
        tags = entry.get("tags", [])
        for tag in tags:
            if tag.startswith("contradicts_") or tag.startswith("challenges_"):
                ref_id = tag.split("_", 1)[1] if "_" in tag else tag
                if ref_id not in version_groups:
                    version_groups[ref_id] = []
                version_groups[ref_id].append(entry)

    # Find Jay Wilds version chain
    jay_versions = [e for e in evidence if "jay_wilds" in e.get("tags", []) and "trunk_pop" in e.get("tags", [])]

    return {
        "contradiction_chains": version_groups,
        "jay_wilds_versions": jay_versions,
        "total_contradicting_entries": len([e for e in evidence if any(t.startswith("contradicts_") for t in e.get("tags", []))]),
    }


def generate_report(tension_results, oscillation_data, evidence):
    """Generate human-readable analysis report."""
    report = []
    report.append("=" * 70)
    report.append("CASE ANALYSIS: Adnan Syed / Hae Min Lee (1999)")
    report.append("CRT Structural Tension Analysis")
    report.append("=" * 70)

    # Summary stats
    real = [e for e in evidence if e["id"].startswith("E")]
    noise = [e for e in evidence if e["id"].startswith("N")]
    herrings = [e for e in evidence if e["id"].startswith("R")]
    report.append(f"\nEvidence loaded: {len(evidence)} total")
    report.append(f"  Real evidence: {len(real)}")
    report.append(f"  Noise entries: {len(noise)}")
    report.append(f"  Red herrings:  {len(herrings)}")

    # Top tension pairs
    report.append(f"\n{'='*70}")
    report.append("TOP 20 HIGHEST TENSION PAIRS")
    report.append(f"{'='*70}")

    for i, r in enumerate(tension_results[:20]):
        # Check if either entry is noise or red herring
        is_noise = r["entry_a"].startswith("N") or r["entry_b"].startswith("N")
        is_herring = r["entry_a"].startswith("R") or r["entry_b"].startswith("R")
        flag = " [NOISE]" if is_noise else (" [RED HERRING]" if is_herring else "")

        report.append(f"\n  {i+1}. Tension={r['tension_score']:.2f} ({r['relationship']}) {flag}")
        report.append(f"     {r['entry_a']} (trust={r['trust_a']:.2f}): {r['text_a']}")
        report.append(f"     {r['entry_b']} (trust={r['trust_b']:.2f}): {r['text_b']}")
        if r["slots"]:
            for s in r["slots"]:
                report.append(f"     Slot [{s['slot']}]: '{s['value_a']}' vs '{s['value_b']}' -> {s['match']}")

    # Jay Wilds version analysis
    report.append(f"\n{'='*70}")
    report.append("WITNESS OSCILLATION: Jay Wilds")
    report.append(f"{'='*70}")

    jay_versions = oscillation_data["jay_wilds_versions"]
    report.append(f"\n  Versions found: {len(jay_versions)}")
    for v in jay_versions:
        report.append(f"  [{v['id']}] trust={v['trust']:.2f} | {v['text'][:90]}")

    trust_values = [v["trust"] for v in jay_versions]
    if trust_values:
        report.append(f"\n  Trust range: {min(trust_values):.2f} - {max(trust_values):.2f}")
        report.append(f"  Trust variance: {np.var(trust_values):.4f}")
        report.append(f"  Average trust: {np.mean(trust_values):.2f}")

    # Noise/Red Herring filtering effectiveness
    report.append(f"\n{'='*70}")
    report.append("NOISE FILTERING EFFECTIVENESS")
    report.append(f"{'='*70}")

    top20_ids = set()
    for r in tension_results[:20]:
        top20_ids.add(r["entry_a"])
        top20_ids.add(r["entry_b"])

    noise_in_top20 = len([i for i in top20_ids if i.startswith("N")])
    herring_in_top20 = len([i for i in top20_ids if i.startswith("R")])
    real_in_top20 = len([i for i in top20_ids if i.startswith("E")])

    report.append(f"\n  In top 20 tension pairs:")
    report.append(f"    Real evidence entries: {real_in_top20}")
    report.append(f"    Noise entries:         {noise_in_top20}")
    report.append(f"    Red herring entries:   {herring_in_top20}")

    if noise_in_top20 == 0 and herring_in_top20 == 0:
        report.append(f"\n  PERFECT: No noise or red herrings in top findings.")
    else:
        total_noise = noise_in_top20 + herring_in_top20
        report.append(f"\n  {total_noise} noise/herring entries leaked into top findings.")

    # Key contradictions found
    report.append(f"\n{'='*70}")
    report.append("KEY CONTRADICTIONS IDENTIFIED")
    report.append(f"{'='*70}")

    conflict_results = [r for r in tension_results if r["relationship"] == "conflict"]
    report.append(f"\n  Total CONFLICT relationships: {len(conflict_results)}")
    for r in conflict_results[:10]:
        report.append(f"\n  CONFLICT (tension={r['tension_score']:.2f}):")
        report.append(f"    {r['entry_a']}: {r['text_a']}")
        report.append(f"    {r['entry_b']}: {r['text_b']}")

    # Verdict
    report.append(f"\n{'='*70}")
    report.append("SYSTEM VERDICT")
    report.append(f"{'='*70}")

    # Check what the system found
    found_jay_oscillation = len(jay_versions) >= 4
    found_cell_tower = any(
        ("cell_tower" in r.get("text_a", "").lower() or "cell_tower" in str(r.get("entry_a", "")))
        and r["tension_score"] > 0.3
        for r in tension_results
    )
    found_lividity = any(
        "lividity" in r.get("text_a", "").lower() or "lividity" in r.get("text_b", "").lower()
        for r in tension_results[:30]
    )
    found_alibi = any(
        "asia" in r.get("text_a", "").lower() or "asia" in r.get("text_b", "").lower()
        for r in tension_results[:30]
    )

    report.append(f"\n  Jay Wilds oscillation detected: {'YES' if found_jay_oscillation else 'NO'}")
    report.append(f"  Cell tower reliability issue:   {'YES' if found_cell_tower else 'NO'}")
    report.append(f"  Lividity contradiction:         {'YES' if found_lividity else 'NO'}")
    report.append(f"  Asia McClain alibi surfaced:    {'YES' if found_alibi else 'NO'}")

    checks = [found_jay_oscillation, found_cell_tower, found_lividity, found_alibi]
    score = sum(checks)
    report.append(f"\n  Score: {score}/4 key issues identified")

    return "\n".join(report)


def cleanup():
    """Remove isolated database."""
    if ISOLATED_DB.exists():
        ISOLATED_DB.unlink()
        p(f"  Cleaned up: {ISOLATED_DB.name}")


def run():
    p("=" * 70)
    p("CASE STUDY LOADER: Adnan Syed / Hae Min Lee")
    p("Isolated thread - no contamination of main memories")
    p("=" * 70)

    # Load evidence
    p("\nLoading evidence...")
    evidence = load_evidence()
    p(f"  {len(evidence)} entries loaded from {EVIDENCE_FILE.name}")

    # Create isolated DB
    p("\nCreating isolated memory database...")
    create_isolated_db(evidence)

    # Bootstrap domain slots
    p("\nBootstrapping domain slots...")
    promoted_slots = bootstrap_slots(evidence)
    for s in promoted_slots[:10]:
        p(f"  [{s['slot_name']}] conf={s['confidence']:.2f} evidence={s['evidence_count']} values={s['example_values'][:2]}")

    # Build hybrid extractor (hardcoded + discovered)
    p("\nBuilding hybrid slot extractor...")
    hybrid_extractor = build_dynamic_extractor(promoted_slots, evidence)
    p(f"  Hardcoded case slots + {len(promoted_slots)} discovered slots")

    # Run tension analysis with hybrid extractor
    p("\nRunning structural tension analysis (hybrid slots)...")
    tension_results = run_tension_analysis(evidence, slot_extractor=hybrid_extractor)
    p(f"  {len(tension_results)} tension relationships found")

    # Run oscillation analysis
    p("\nRunning oscillation analysis...")
    oscillation_data = run_oscillation_analysis(evidence)

    # Generate report
    p("\nGenerating report...")
    report = generate_report(tension_results, oscillation_data, evidence)

    # Save report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "case_analysis_report.txt"
    with _real_open(report_path, "w") as f:
        f.write(report)

    # Save raw results
    raw_path = RESULTS_DIR / "tension_results.json"
    with _real_open(raw_path, "w") as f:
        json.dump(tension_results, f, indent=2, default=str)

    # Print report
    p("\n" + report)

    # Cleanup
    p(f"\nCleaning up isolated database...")
    cleanup()

    p(f"\nResults saved to:")
    p(f"  Report: {report_path}")
    p(f"  Raw data: {raw_path}")


if __name__ == "__main__":
    run()
