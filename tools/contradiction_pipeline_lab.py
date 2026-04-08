"""
Contradiction Pipeline Lab — Standalone contradiction detection test.

Tests the full extraction + comparison chain WITHOUT the pipeline.
No backend, no Ollama, no generation. Just:
  1. Regex extraction (extract_fact_slots)
  2. Cloud extraction (gpt-4o-mini, one call per probe)
  3. Slot comparison against seeded facts
  4. Pass/fail scoring

Usage:
    python -m tools.contradiction_pipeline_lab
"""

import argparse
import json
import os
import time
import sys
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

# Add project root to path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Seed Facts ───────────────────────────────────────────────────────────────

SEED_FACTS = [
    {"slot": "name", "value": "Marcus", "normalized": "marcus", "text": "My name is Marcus."},
    {"slot": "employer", "value": "Anthropic", "normalized": "anthropic", "text": "I work at Anthropic as a research engineer."},
    {"slot": "job_title", "value": "research engineer", "normalized": "research engineer", "text": "I work at Anthropic as a research engineer."},
    {"slot": "location", "value": "Seattle", "normalized": "seattle", "text": "I live in Seattle."},
    {"slot": "favorite_color", "value": "blue", "normalized": "blue", "text": "My favorite color is blue."},
    {"slot": "age", "value": "34", "normalized": "34", "text": "I'm 34 years old."},
]


# ── Test Probes ──────────────────────────────────────────────────────────────

@dataclass
class TestProbe:
    probe_id: str
    message: str
    should_fire: bool
    target_slot: Optional[str]
    description: str
    message_style: str


TEST_PROBES = [
    # Should-fire (5) — T1 removed, name is identity-level
    TestProbe("T2", (
        "So I've been thinking about the move a lot, and we finally did it — "
        "we packed up everything in Seattle and drove down to Portland. The new "
        "apartment is in the Pearl District, really walkable, and I've been settling "
        "in for a few weeks now. Definitely feels like home already. The coffee scene "
        "here is incredible, way better than what we had. Anyway, what's a good "
        "restaurant nearby for date night?"
    ), True, "location", "Long narrative with location change buried in story", "long"),

    TestProbe("T3",
        "I just turned 35 last week, had a little birthday dinner with friends.",
        True, "age", "Age contradiction stated casually", "short"),

    TestProbe("T4", (
        "Let me tell you about my day — I had back-to-back meetings starting at 8am, "
        "grabbed lunch at this new Thai place (amazing pad see ew by the way), then "
        "spent the afternoon doing code reviews. Oh, I should mention, I actually left "
        "Anthropic about a month ago and joined OpenAI. The team there is great, really "
        "different culture but in a good way. Anyway, after work I went for a run along "
        "the waterfront and then watched some Netflix. Pretty solid Tuesday overall."
    ), True, "employer", "Long narration with employer change buried mid-paragraph", "long"),

    TestProbe("T5", (
        "I've really been getting into green lately. Repainted my office wall, got "
        "some green plants everywhere, even my new phone case is green. It's definitely "
        "my favorite color now, green just makes me feel calm and focused."
    ), True, "favorite_color", "Contextual color declaration without direct pattern", "contextual"),

    TestProbe("T5b",
        "Actually, my favorite color is green now. Blue was getting boring.",
        True, "favorite_color", "Direct color contradiction with corrective language", "short"),

    # Should-NOT-fire (5)
    TestProbe("T6",
        "I also enjoy hiking on weekends. Last week I did a trail near Mount Rainier, it was beautiful.",
        False, None, "Additive hobby — no exclusive slot conflict", "short"),

    TestProbe("T7",
        "What's the weather like in Seattle this time of year? I'm trying to plan an outdoor event.",
        False, None, "Question about location — not a declaration", "short"),

    TestProbe("T8",
        "At Anthropic, we've been working on some really interesting alignment research lately. The team is great.",
        False, None, "Reinforces existing employer — no contradiction", "short"),

    TestProbe("T9", (
        "My friend Sarah works at Google, she absolutely loves it there. She told me "
        "they have amazing food in the cafeteria and the work-life balance is solid."
    ), False, None, "Third-party fact about someone else", "short"),

    TestProbe("T10", (
        "I've been learning Spanish on Duolingo, and I also started a pottery class "
        "last month. On top of that, I picked up running again — I used to run cross "
        "country in college but stopped for years. Also been getting into woodworking, "
        "built a small shelf last weekend. So yeah, keeping busy with hobbies."
    ), False, None, "Long block with multiple additive facts — no exclusive slots", "long"),
]


# ── Results ──────────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    probe_id: str
    message: str
    target_slot: Optional[str]
    should_fire: bool
    description: str
    message_style: str
    # Regex extraction
    regex_slots: Dict[str, str] = field(default_factory=dict)
    # Cloud extraction
    cloud_result: Optional[Dict] = None
    cloud_slots: Dict[str, str] = field(default_factory=dict)
    cloud_latency_ms: float = 0.0
    # Combined extraction
    all_extracted_slots: Dict[str, str] = field(default_factory=dict)
    # Comparison
    contradictions_found: List[Dict] = field(default_factory=list)
    third_person_filtered: bool = False
    same_value_skipped: bool = False
    # Verdict
    passed: bool = False
    diagnosis: str = ""


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_regex(text: str) -> Dict[str, str]:
    """Run regex fact extraction. Returns {slot: normalized_value}."""
    try:
        from personal_agent.fact_slots import extract_fact_slots
        raw = extract_fact_slots(text)
        return {
            k: str(getattr(v, "normalized", getattr(v, "value", v))).strip().lower()
            for k, v in raw.items()
        }
    except Exception as e:
        print(f"  [REGEX] Error: {e}")
        return {}


def _get_openai_key() -> str:
    """Read OpenAI API key from .env file (most reliable source)."""
    env_path = _ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == "OPENAI_API_KEY" and v.strip():
                return v.strip()
    return os.environ.get("OPENAI_API_KEY", "")


def extract_cloud(text: str, existing_slots: List[str]) -> Tuple[Optional[Dict], Dict[str, str], float]:
    """Run cloud slot classification via gpt-4o-mini. Direct OpenAI call, no litellm."""
    try:
        from tests.cloud_providers.prompts import slot_classification_prompt
        system, prompt = slot_classification_prompt(text, existing_slots)

        import openai
        api_key = _get_openai_key()
        if not api_key:
            print("  [CLOUD] No OpenAI API key found")
            return None, {}, 0.0

        client = openai.OpenAI(api_key=api_key)
        t0 = time.time()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.1,
        )
        latency = (time.time() - t0) * 1000
        raw = resp.choices[0].message.content.strip()

        # Parse JSON (strip fences, find first brace)
        clean = raw
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        brace = clean.find("{")
        if brace > 0:
            clean = clean[brace:]
        result = json.loads(clean)

        slots = {}
        if result.get("contains_fact"):
            slot_name = result.get("slot_name", "")
            value = str(result.get("value", "")).strip().lower()
            if slot_name and value:
                slots[slot_name] = value
        return result, slots, latency
    except Exception as e:
        print(f"  [CLOUD] Error: {e}")
        return None, {}, 0.0


# ── Guards ───────────────────────────────────────────────────────────────────

THIRD_PERSON_INDICATORS = (
    "my friend ", "my buddy ", "my colleague ", "my sister ", "my brother ",
    "my mom ", "my dad ", "my wife ", "my husband ", "my partner ",
    "she works ", "he works ", "she lives ", "he lives ",
    "she is ", "he is ", "they work ", "their favorite ",
)
FIRST_PERSON_INDICATORS = ("i ", "i'm ", "i've ", "my ", "i am ", "i was ", "i used ", "i work ", "i live ")


def is_third_person(text: str) -> bool:
    """Check if text is about someone else, not the user."""
    t = text.lower().strip()
    has_third = any(ind in t for ind in THIRD_PERSON_INDICATORS)
    if not has_third:
        return False
    # "my friend/buddy/colleague" etc. uses "my" but describes someone else.
    # Only count first-person if it's NOT immediately followed by a relationship noun.
    _relationship_possessives = ("my friend", "my buddy", "my colleague", "my sister",
                                  "my brother", "my mom", "my dad", "my wife", "my husband", "my partner")
    has_first = False
    for ind in FIRST_PERSON_INDICATORS:
        if t.startswith(ind) or f" {ind}" in t:
            # Check if this "my" is actually "my friend/colleague/etc."
            if ind == "my ":
                if any(t.startswith(rp) or f" {rp}" in t for rp in _relationship_possessives):
                    continue  # "my friend" — not first-person about self
            has_first = True
            break
    return has_third and not has_first


def is_same_value(existing_norm: str, new_norm: str) -> bool:
    """Check if two normalized values are the same (substring containment)."""
    return (existing_norm == new_norm
            or new_norm in existing_norm
            or existing_norm in new_norm)


# ── Comparison ───────────────────────────────────────────────────────────────

def compare_against_seeds(
    extracted_slots: Dict[str, str],
    seed_facts: List[Dict],
) -> List[Dict]:
    """Compare extracted slots against seeded facts. Returns list of contradictions."""
    contradictions = []
    seed_by_slot = {f["slot"]: f for f in seed_facts}

    for slot, new_value in extracted_slots.items():
        if slot not in seed_by_slot:
            continue  # New slot, not a contradiction
        existing = seed_by_slot[slot]
        existing_norm = existing["normalized"]

        # Slot type check
        try:
            from personal_agent.slot_discovery import get_slot_type, SlotType
            slot_type = get_slot_type(slot)
            if slot_type == SlotType.ADDITIVE:
                continue  # Additive slots don't contradict
        except Exception:
            pass  # Default to exclusive behavior

        if is_same_value(existing_norm, new_value):
            continue  # Same value, not a conflict

        contradictions.append({
            "slot": slot,
            "existing_value": existing_norm,
            "new_value": new_value,
            "seed_text": existing["text"],
        })

    return contradictions


# ── Lab Runner ───────────────────────────────────────────────────────────────

def run_lab() -> Dict[str, Any]:
    """Run the standalone contradiction detection lab."""
    print("=" * 60)
    print("CONTRADICTION PIPELINE LAB — Standalone Mode")
    print("No backend. No Ollama. No generation pipeline.")
    print("Regex extraction + Cloud extraction + Slot comparison.")
    print("=" * 60)
    print()

    existing_slot_names = [f["slot"] for f in SEED_FACTS]

    print(f"Seed facts: {len(SEED_FACTS)}")
    for f in SEED_FACTS:
        print(f"  {f['slot']} = {f['value']}")
    print()

    print(f"Probes: {len(TEST_PROBES)} ({sum(1 for p in TEST_PROBES if p.should_fire)} should-fire, "
          f"{sum(1 for p in TEST_PROBES if not p.should_fire)} should-NOT-fire)")
    print()

    results: List[ProbeResult] = []

    for probe in TEST_PROBES:
        expect = "SHOULD FIRE" if probe.should_fire else "should NOT fire"
        print(f"--- {probe.probe_id} [{expect}]: {probe.description}")

        r = ProbeResult(
            probe_id=probe.probe_id,
            message=probe.message,
            target_slot=probe.target_slot,
            should_fire=probe.should_fire,
            description=probe.description,
            message_style=probe.message_style,
        )

        # Guard: third-person filter
        if is_third_person(probe.message):
            r.third_person_filtered = True
            r.all_extracted_slots = {}
            print(f"  [GUARD] Third-person text detected — skipping extraction")
        else:
            # Step 1: Regex extraction
            r.regex_slots = extract_regex(probe.message)
            if r.regex_slots:
                print(f"  [REGEX] Extracted: {r.regex_slots}")
            else:
                print(f"  [REGEX] No slots found")

            # Step 2: Cloud extraction (also gated by third-person filter)
            if not is_third_person(probe.message):
                r.cloud_result, r.cloud_slots, r.cloud_latency_ms = extract_cloud(
                    probe.message, existing_slot_names,
                )
            else:
                print(f"  [CLOUD] Skipped — third-person text")
                r.cloud_slots = {}
            if r.cloud_slots:
                print(f"  [CLOUD] Extracted: {r.cloud_slots} ({r.cloud_latency_ms:.0f}ms)")
            elif r.cloud_result:
                print(f"  [CLOUD] No fact detected ({r.cloud_latency_ms:.0f}ms)")
            else:
                print(f"  [CLOUD] Failed or unavailable")

            # Merge: cloud fills gaps regex missed
            r.all_extracted_slots = {**r.regex_slots, **r.cloud_slots}

        # Step 3: Compare against seeds
        r.contradictions_found = compare_against_seeds(r.all_extracted_slots, SEED_FACTS)

        # Score
        if probe.should_fire:
            if r.contradictions_found:
                r.passed = True
                contras = "; ".join(
                    f"{c['slot']}: '{c['existing_value']}' → '{c['new_value']}'"
                    for c in r.contradictions_found
                )
                r.diagnosis = f"DETECTED: {contras}"
            else:
                r.passed = False
                if r.third_person_filtered:
                    r.diagnosis = "NOT DETECTED — third-person filter blocked extraction"
                elif not r.all_extracted_slots:
                    r.diagnosis = "NOT DETECTED — neither regex nor cloud extracted the target slot"
                else:
                    r.diagnosis = f"NOT DETECTED — extracted {r.all_extracted_slots} but no conflict with seeds"
        else:
            if r.contradictions_found:
                r.passed = False
                contras = "; ".join(
                    f"{c['slot']}: '{c['existing_value']}' → '{c['new_value']}'"
                    for c in r.contradictions_found
                )
                r.diagnosis = f"FALSE POSITIVE: {contras}"
            else:
                r.passed = True
                if r.third_person_filtered:
                    r.diagnosis = "Correctly silent — third-person filter"
                else:
                    r.diagnosis = "Correctly silent — no false positive"

        status = "PASS" if r.passed else "FAIL"
        print(f"  >>> {status} — {r.diagnosis}")
        print()
        results.append(r)

    # Summary
    should_fire_passed = sum(1 for r in results if r.should_fire and r.passed)
    should_fire_total = sum(1 for r in results if r.should_fire)
    should_not_passed = sum(1 for r in results if not r.should_fire and r.passed)
    should_not_total = sum(1 for r in results if not r.should_fire)
    total = should_fire_passed + should_not_passed

    print("=" * 60)
    print(f"RESULTS: {total}/{len(results)}")
    print(f"  Should-fire:     {should_fire_passed}/{should_fire_total}")
    print(f"  Should-NOT-fire: {should_not_passed}/{should_not_total}")
    print("=" * 60)

    return {
        "timestamp": datetime.now().isoformat(),
        "probe_results": results,
        "should_fire_passed": should_fire_passed,
        "should_fire_total": should_fire_total,
        "should_not_passed": should_not_passed,
        "should_not_total": should_not_total,
        "total_passed": total,
        "total_probes": len(results),
    }


# ── HTML Report ──────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_report(results: Dict[str, Any], output_path: Path) -> str:
    ts = results["timestamp"]
    sf = results["should_fire_passed"]
    sft = results["should_fire_total"]
    sn = results["should_not_passed"]
    snt = results["should_not_total"]
    total = results["total_passed"]
    total_probes = results["total_probes"]
    probes: List[ProbeResult] = results["probe_results"]

    score_color = "#34d399" if total == total_probes else ("#fbbf24" if total >= total_probes - 2 else "#fb7185")
    sf_color = "#34d399" if sf == sft else ("#fbbf24" if sf >= sft - 1 else "#fb7185")
    sn_color = "#34d399" if sn == snt else ("#fbbf24" if sn >= snt - 1 else "#fb7185")

    rows = ""
    details = ""
    for p in probes:
        badge = "FIRE" if p.should_fire else "QUIET"
        badge_cls = "badge-fire" if p.should_fire else "badge-quiet"
        status_cls = "row-pass" if p.passed else "row-fail"
        status = "PASS" if p.passed else "FAIL"

        regex_str = _esc(json.dumps(p.regex_slots)) if p.regex_slots else "—"
        cloud_str = _esc(json.dumps(p.cloud_slots)) if p.cloud_slots else "—"

        rows += f"""
        <tr class="{status_cls}">
          <td><strong>{p.probe_id}</strong></td>
          <td><span class="badge {badge_cls}">{badge}</span></td>
          <td>{_esc(p.target_slot or '—')}</td>
          <td class="mono">{regex_str}</td>
          <td class="mono">{cloud_str}</td>
          <td><strong>{status}</strong></td>
          <td>{_esc(p.diagnosis)}</td>
        </tr>"""

        details += f"""
        <div class="detail-card {'detail-pass' if p.passed else 'detail-fail'}">
          <h3>{p.probe_id}: {_esc(p.description)}</h3>
          <div class="detail-meta">
            <span>Style: {p.message_style}</span>
            <span>Cloud: {p.cloud_latency_ms:.0f}ms</span>
            <span class="{'pass-tag' if p.passed else 'fail-tag'}">{status}</span>
          </div>
          <div class="msg-block">{_esc(p.message)}</div>
          <div class="detail-section">
            <strong>Regex:</strong> <code>{regex_str}</code><br>
            <strong>Cloud:</strong> <code>{cloud_str}</code><br>
            <strong>Merged:</strong> <code>{_esc(json.dumps(p.all_extracted_slots))}</code>
          </div>
          <div class="detail-section"><strong>Diagnosis:</strong> {_esc(p.diagnosis)}</div>
        </div>"""

    seed_rows = ""
    for f in SEED_FACTS:
        seed_rows += f"<tr><td>{_esc(f['slot'])}</td><td>{_esc(f['value'])}</td><td class='mono'>{_esc(f['normalized'])}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Contradiction Pipeline Lab — Standalone</title>
<style>
:root {{ --bg:#121210; --bg-raised:rgba(255,255,255,0.03); --text:#c8c4bc; --text-dim:#8a8680;
  --text-faint:#4a4540; --border:rgba(255,255,255,0.06); --accent:#818cf8; --green:#34d399;
  --red:#fb7185; --amber:#fbbf24; --mono:'IBM Plex Mono','Cascadia Code',monospace; --sans:'Inter',sans-serif; }}
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.7;padding:40px 20px; }}
.shell {{ max-width:1100px;margin:0 auto; }}
.hero {{ text-align:center;padding:60px 0 40px; }}
.hero h1 {{ font-size:2.4em;font-weight:800; }}
.grad {{ background:linear-gradient(135deg,var(--accent),#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent; }}
.sub {{ color:var(--text-dim);font-size:0.9em;margin-top:8px; }}
.meta {{ font-family:var(--mono);font-size:0.75em;color:var(--text-faint);margin-top:16px; }}
.stat-row {{ display:flex;gap:16px;justify-content:center;margin:30px 0;flex-wrap:wrap; }}
.stat-card {{ background:var(--bg-raised);border:1px solid var(--border);border-radius:12px;padding:20px 28px;text-align:center;min-width:140px; }}
.stat-value {{ font-size:2em;font-weight:800;font-family:var(--mono); }}
.stat-label {{ font-size:0.72em;color:var(--text-dim);margin-top:4px;text-transform:uppercase;letter-spacing:1px; }}
.section {{ margin:40px 0; }}
.section h2 {{ font-size:1.3em;margin-bottom:16px; }}
.accent-line {{ width:40px;height:3px;background:var(--accent);border-radius:2px;margin-bottom:12px; }}
table {{ width:100%;border-collapse:collapse;font-size:0.82em; }}
th {{ text-align:left;padding:10px 12px;color:var(--text-dim);border-bottom:1px solid var(--border);font-weight:600;text-transform:uppercase;font-size:0.85em; }}
td {{ padding:10px 12px;border-bottom:1px solid var(--border); }}
.mono {{ font-family:var(--mono);font-size:0.85em; }}
.row-pass td:first-child {{ border-left:3px solid var(--green); }}
.row-fail td:first-child {{ border-left:3px solid var(--red); }}
.row-fail td {{ background:rgba(251,113,133,0.04); }}
.badge {{ font-size:0.7em;font-weight:700;letter-spacing:1px;padding:3px 8px;border-radius:4px; }}
.badge-fire {{ background:rgba(251,113,133,0.15);color:var(--red); }}
.badge-quiet {{ background:rgba(52,211,153,0.15);color:var(--green); }}
.pass-tag {{ color:var(--green);font-weight:700; }}
.fail-tag {{ color:var(--red);font-weight:700; }}
.detail-card {{ background:var(--bg-raised);border:1px solid var(--border);border-radius:12px;padding:24px;margin:16px 0; }}
.detail-fail {{ border-left:3px solid var(--red); }}
.detail-pass {{ border-left:3px solid var(--green); }}
.detail-card h3 {{ font-size:1em;margin-bottom:12px; }}
.detail-meta {{ display:flex;gap:16px;flex-wrap:wrap;font-size:0.78em;color:var(--text-dim);margin-bottom:16px; }}
.detail-section {{ margin:12px 0;font-size:0.88em; }}
.msg-block {{ background:rgba(0,0,0,0.3);border-radius:8px;padding:14px;margin:8px 0;font-size:0.88em;color:var(--text-dim);white-space:pre-wrap;word-break:break-word; }}
</style></head><body><div class="shell">
<div class="hero">
  <h1>Contradiction Pipeline <span class="grad">Lab</span></h1>
  <p class="sub">Standalone — no backend, no Ollama, no generation pipeline</p>
  <p class="meta">Run: {_esc(ts)}</p>
</div>
<div class="stat-row">
  <div class="stat-card"><div class="stat-value" style="color:{score_color}">{total}/{total_probes}</div><div class="stat-label">Overall</div></div>
  <div class="stat-card"><div class="stat-value" style="color:{sf_color}">{sf}/{sft}</div><div class="stat-label">Should-Fire</div></div>
  <div class="stat-card"><div class="stat-value" style="color:{sn_color}">{sn}/{snt}</div><div class="stat-label">Should-NOT-Fire</div></div>
</div>
<div class="section"><div class="accent-line"></div><h2>Seed Facts</h2>
<div style="overflow-x:auto;"><table><thead><tr><th>Slot</th><th>Value</th><th>Normalized</th></tr></thead><tbody>{seed_rows}</tbody></table></div></div>
<div class="section"><div class="accent-line"></div><h2>Results</h2>
<div style="overflow-x:auto;"><table><thead><tr><th>ID</th><th>Expect</th><th>Slot</th><th>Regex</th><th>Cloud</th><th>Result</th><th>Diagnosis</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<div class="section"><div class="accent-line"></div><h2>Probe Details</h2>{details}</div>
<div style="text-align:center;padding:40px 0 20px;font-size:0.7em;color:var(--text-faint);">Contradiction Pipeline Lab &middot; Standalone &middot; {_esc(ts)}</div>
</div></body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    results = run_lab()

    ts_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = Path(f"docs/labs/contradiction-pipeline-lab-{ts_str}.html")
    latest_path = Path("docs/labs/contradiction-pipeline-lab-latest.html")

    path = generate_report(results, report_path)
    generate_report(results, latest_path)
    print(f"\nReport: {path}")
    print(f"Latest: {latest_path}")

    # Save raw JSON
    artifact_dir = Path("artifacts/contradiction_pipeline_lab")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / f"results_{ts_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        raw = {k: v for k, v in results.items() if k != "probe_results"}
        raw["probe_results"] = [asdict(p) for p in results["probe_results"]]
        json.dump(raw, f, indent=2, default=str)
    print(f"Raw JSON: {json_path}")

    sys.exit(0 if results["total_passed"] == results["total_probes"] else 1)


if __name__ == "__main__":
    main()
