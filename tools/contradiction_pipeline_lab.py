"""
Contradiction Pipeline Lab — End-to-end validation of the CORE contradiction detection chain.

Sends controlled test messages to a running Aether backend, verifies that:
- Exclusive slot reversals create ledger entries and trust demotions
- Additive slots, questions, reinforcements do NOT create false positives
- Long blocks of text with buried contradictions are detected

Generates a static HTML lab report at docs/labs/contradiction-pipeline-lab-latest.html.

Usage:
    python -m tools.contradiction_pipeline_lab [--base-url http://localhost:8000] [--thread-id lab_xxx]
"""

import argparse
import json
import time
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


# ── Seed Messages ────────────────────────────────────────────────────────────

SEED_MESSAGES = [
    {"slot": "name", "message": "My name is Marcus."},
    {"slot": "employer,job_title", "message": "I work at Anthropic as a research engineer."},
    {"slot": "location", "message": "I live in Seattle."},
    {"slot": "favorite_color", "message": "My favorite color is blue."},
    {"slot": "age", "message": "I'm 34 years old."},
]


# ── Test Probes ──────────────────────────────────────────────────────────────

@dataclass
class TestProbe:
    probe_id: str
    message: str
    should_fire: bool
    target_slot: Optional[str]
    description: str
    message_style: str  # "short", "long", "contextual"


TEST_PROBES = [
    # ── Should-fire (5) ──────────────────────────────────────────────────
    TestProbe(
        probe_id="T1",
        message="Actually, my name is Adrian now. I changed it legally last year.",
        should_fire=True,
        target_slot="name",
        description="Direct exclusive slot reversal with corrective language",
        message_style="short",
    ),
    TestProbe(
        probe_id="T2",
        message=(
            "So I've been thinking about the move a lot, and we finally did it — "
            "we packed up everything in Seattle and drove down to Portland. The new "
            "apartment is in the Pearl District, really walkable, and I've been settling "
            "in for a few weeks now. Definitely feels like home already. The coffee scene "
            "here is incredible, way better than what we had. Anyway, what's a good "
            "restaurant nearby for date night?"
        ),
        should_fire=True,
        target_slot="location",
        description="Long narrative block with location change buried in story",
        message_style="long",
    ),
    TestProbe(
        probe_id="T3",
        message="I just turned 35 last week, had a little birthday dinner with friends.",
        should_fire=True,
        target_slot="age",
        description="Age contradiction stated casually without corrective language",
        message_style="short",
    ),
    TestProbe(
        probe_id="T4",
        message=(
            "Let me tell you about my day — I had back-to-back meetings starting at 8am, "
            "grabbed lunch at this new Thai place (amazing pad see ew by the way), then "
            "spent the afternoon doing code reviews. Oh, I should mention, I actually left "
            "Anthropic about a month ago and joined OpenAI. The team there is great, really "
            "different culture but in a good way. Anyway, after work I went for a run along "
            "the waterfront and then watched some Netflix. Pretty solid Tuesday overall."
        ),
        should_fire=True,
        target_slot="employer",
        description="Long daily narration with employer change buried mid-paragraph",
        message_style="long",
    ),
    TestProbe(
        probe_id="T5",
        message=(
            "I've really been getting into green lately. Repainted my office wall, got "
            "some green plants everywhere, even my new phone case is green. It's definitely "
            "my favorite color now, green just makes me feel calm and focused."
        ),
        should_fire=True,
        target_slot="favorite_color",
        description="Contextual color declaration through repetition, no direct 'my favorite color is X'",
        message_style="contextual",
    ),

    # ── Should-NOT-fire (5) ──────────────────────────────────────────────
    TestProbe(
        probe_id="T6",
        message="I also enjoy hiking on weekends. Last week I did a trail near Mount Rainier, it was beautiful.",
        should_fire=False,
        target_slot=None,
        description="Additive hobby slot — no exclusive slot conflict",
        message_style="short",
    ),
    TestProbe(
        probe_id="T7",
        message="What's the weather like in Seattle this time of year? I'm trying to plan an outdoor event.",
        should_fire=False,
        target_slot=None,
        description="Question about location — not a declaration changing it",
        message_style="short",
    ),
    TestProbe(
        probe_id="T8",
        message="At Anthropic, we've been working on some really interesting alignment research lately. The team is great.",
        should_fire=False,
        target_slot=None,
        description="Reinforces existing employer fact — no contradiction",
        message_style="short",
    ),
    TestProbe(
        probe_id="T9",
        message=(
            "My friend Sarah works at Google, she absolutely loves it there. She told me "
            "they have amazing food in the cafeteria and the work-life balance is solid."
        ),
        should_fire=False,
        target_slot=None,
        description="Third-party fact about someone else — not about the user",
        message_style="short",
    ),
    TestProbe(
        probe_id="T10",
        message=(
            "I've been learning Spanish on Duolingo, and I also started a pottery class "
            "last month. On top of that, I picked up running again — I used to run cross "
            "country in college but stopped for years. Also been getting into woodworking, "
            "built a small shelf last weekend. So yeah, keeping busy with hobbies."
        ),
        should_fire=False,
        target_slot=None,
        description="Long block with multiple additive facts (hobbies) — no exclusive slots",
        message_style="long",
    ),
]


# ── Result ───────────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    probe_id: str
    message: str
    target_slot: Optional[str]
    should_fire: bool
    description: str
    message_style: str
    # Measured
    contradiction_detected: bool = False
    ledger_entries_created: int = 0
    ledger_details: List[Dict] = field(default_factory=list)
    trust_demotions: List[Dict] = field(default_factory=list)
    response_preview: str = ""
    latency_ms: float = 0.0
    # Verdict
    passed: bool = False
    diagnosis: str = ""


@dataclass
class SeedResult:
    slot: str
    message: str
    memory_id: str = ""
    initial_trust: float = 0.0
    response_preview: str = ""


# ── API Client ───────────────────────────────────────────────────────────────

class LabClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def send_message(self, text: str, thread_id: str) -> Dict[str, Any]:
        """Send a chat message and return the full response dict."""
        resp = self.session.post(
            f"{self.base_url}/api/chat/send",
            json={"message": text, "thread_id": thread_id},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()

    def get_ledger_open(self, thread_id: str) -> List[Dict]:
        resp = self.session.get(
            f"{self.base_url}/api/ledger/open",
            params={"thread_id": thread_id, "limit": 200},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_trust_delta(self, thread_id: str, since_ts: float) -> List[Dict]:
        resp = self.session.get(
            f"{self.base_url}/api/memory/trust-delta",
            params={"thread_id": thread_id, "since_ts": since_ts, "limit": 100},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_recent_memories(self, thread_id: str, limit: int = 30) -> List[Dict]:
        resp = self.session.get(
            f"{self.base_url}/api/memory/recent",
            params={"thread_id": thread_id, "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> bool:
        try:
            # No /api/health endpoint — use /api/tooling/models or root
            resp = self.session.get(f"{self.base_url}/", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False


# ── Lab Runner ───────────────────────────────────────────────────────────────

def run_lab(base_url: str, thread_id: str) -> Dict[str, Any]:
    """Run the full lab: seed → test → verify → return results."""
    client = LabClient(base_url)

    # Health check
    if not client.health_check():
        print(f"ERROR: Backend not reachable at {base_url}")
        sys.exit(1)

    print(f"Lab started: thread_id={thread_id}")
    print(f"Backend: {base_url}")
    print()

    # ── Phase 1: Seed ────────────────────────────────────────────────────
    print("=== PHASE 1: SEEDING FACTS ===")
    seed_results: List[SeedResult] = []
    for i, seed in enumerate(SEED_MESSAGES):
        print(f"  Seed {i+1}/5: {seed['slot']} — {seed['message'][:50]}...")
        t0 = time.time()
        resp = client.send_message(seed["message"], thread_id)
        elapsed = (time.time() - t0) * 1000

        sr = SeedResult(
            slot=seed["slot"],
            message=seed["message"],
            response_preview=resp.get("answer", "")[:150],
        )
        # Try to extract memory_id from metadata
        meta = resp.get("metadata", {})
        sr.memory_id = meta.get("memory_id", "")
        sr.initial_trust = meta.get("trust", 0.0)
        seed_results.append(sr)
        print(f"    OK ({elapsed:.0f}ms)")
        time.sleep(1)  # Brief pause between seeds

    print()

    # Snapshot ledger state after seeding
    baseline_ledger = client.get_ledger_open(thread_id)
    baseline_ledger_ids = {e.get("ledger_id") for e in baseline_ledger}
    baseline_ts = time.time()

    # ── Phase 2: Test ────────────────────────────────────────────────────
    print("=== PHASE 2: RUNNING PROBES ===")
    probe_results: List[ProbeResult] = []
    for probe in TEST_PROBES:
        expect = "SHOULD FIRE" if probe.should_fire else "should NOT fire"
        print(f"  {probe.probe_id} [{expect}]: {probe.description}")

        pre_ts = time.time()
        t0 = time.time()
        resp = client.send_message(probe.message, thread_id)
        elapsed = (time.time() - t0) * 1000

        # Parse response
        meta = resp.get("metadata", {})
        answer = resp.get("answer", "")

        # Check contradiction_detected in metadata
        contradiction_detected = bool(meta.get("contradiction_detected", False))

        # Query ledger for new entries
        time.sleep(0.5)  # Brief wait for async ledger writes
        current_ledger = client.get_ledger_open(thread_id)
        new_entries = [
            e for e in current_ledger
            if e.get("ledger_id") not in baseline_ledger_ids
        ]
        # Filter to entries created after this probe's start
        probe_entries = [
            e for e in new_entries
            if float(e.get("timestamp", 0)) >= pre_ts - 1
        ]

        # Query trust demotions
        trust_deltas = client.get_trust_delta(thread_id, pre_ts - 1)
        demotions = [d for d in trust_deltas if d.get("delta", 0) < 0]

        # Build result
        result = ProbeResult(
            probe_id=probe.probe_id,
            message=probe.message,
            target_slot=probe.target_slot,
            should_fire=probe.should_fire,
            description=probe.description,
            message_style=probe.message_style,
            contradiction_detected=contradiction_detected,
            ledger_entries_created=len(probe_entries),
            ledger_details=probe_entries,
            trust_demotions=demotions,
            response_preview=answer[:200],
            latency_ms=elapsed,
        )

        # Score
        if probe.should_fire:
            fired = contradiction_detected or len(probe_entries) > 0 or len(demotions) > 0
            result.passed = fired
            if fired:
                signals = []
                if contradiction_detected:
                    signals.append("metadata.contradiction_detected=true")
                if probe_entries:
                    signals.append(f"{len(probe_entries)} ledger entries")
                if demotions:
                    signals.append(f"{len(demotions)} trust demotions")
                result.diagnosis = f"DETECTED via: {', '.join(signals)}"
            else:
                result.diagnosis = "NOT DETECTED — no ledger entry, no trust demotion, no metadata flag"
        else:
            spurious = contradiction_detected or len(probe_entries) > 0
            result.passed = not spurious
            if result.passed:
                result.diagnosis = "Correctly silent — no false positive"
            else:
                signals = []
                if contradiction_detected:
                    signals.append("false metadata flag")
                if probe_entries:
                    signals.append(f"{len(probe_entries)} spurious ledger entries")
                result.diagnosis = f"FALSE POSITIVE: {', '.join(signals)}"

        # Update baseline for next probe
        baseline_ledger_ids.update(e.get("ledger_id") for e in current_ledger)

        status = "PASS" if result.passed else "FAIL"
        print(f"    {status} ({elapsed:.0f}ms) — {result.diagnosis}")
        probe_results.append(result)
        time.sleep(1)  # Pause between probes

    print()

    # ── Summary ──────────────────────────────────────────────────────────
    should_fire_passed = sum(1 for r in probe_results if r.should_fire and r.passed)
    should_not_passed = sum(1 for r in probe_results if not r.should_fire and r.passed)
    total_passed = should_fire_passed + should_not_passed

    print("=== RESULTS ===")
    print(f"  Should-fire:     {should_fire_passed}/5")
    print(f"  Should-NOT-fire: {should_not_passed}/5")
    print(f"  Overall:         {total_passed}/10")
    print()

    return {
        "thread_id": thread_id,
        "base_url": base_url,
        "timestamp": datetime.now().isoformat(),
        "seed_results": seed_results,
        "probe_results": probe_results,
        "should_fire_passed": should_fire_passed,
        "should_not_passed": should_not_passed,
        "total_passed": total_passed,
    }


# ── HTML Report ──────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_report(results: Dict[str, Any], output_path: Path) -> str:
    """Generate a static HTML lab report."""
    ts = results["timestamp"]
    tid = results["thread_id"]
    sf_pass = results["should_fire_passed"]
    sn_pass = results["should_not_passed"]
    total = results["total_passed"]
    seeds: List[SeedResult] = results["seed_results"]
    probes: List[ProbeResult] = results["probe_results"]

    # Score color
    if total == 10:
        score_color = "#34d399"
    elif total >= 7:
        score_color = "#fbbf24"
    else:
        score_color = "#fb7185"

    sf_color = "#34d399" if sf_pass == 5 else ("#fbbf24" if sf_pass >= 3 else "#fb7185")
    sn_color = "#34d399" if sn_pass == 5 else ("#fbbf24" if sn_pass >= 3 else "#fb7185")

    rows_html = ""
    detail_html = ""
    for p in probes:
        badge = "FIRE" if p.should_fire else "QUIET"
        badge_cls = "badge-fire" if p.should_fire else "badge-quiet"
        status_cls = "row-pass" if p.passed else "row-fail"
        status_txt = "PASS" if p.passed else "FAIL"

        # Truncate message for table
        msg_short = _esc(p.message[:80]) + ("..." if len(p.message) > 80 else "")

        rows_html += f"""
        <tr class="{status_cls}">
          <td><strong>{p.probe_id}</strong></td>
          <td><span class="badge {badge_cls}">{badge}</span></td>
          <td>{_esc(p.target_slot or '—')}</td>
          <td class="msg-col">{msg_short}</td>
          <td>{p.ledger_entries_created}</td>
          <td>{len(p.trust_demotions)}</td>
          <td><strong>{status_txt}</strong></td>
          <td class="diag-col">{_esc(p.diagnosis)}</td>
        </tr>"""

        # Expanded detail for failed probes (and all should-fire probes)
        if not p.passed or p.should_fire:
            detail_html += f"""
            <div class="detail-card {'detail-fail' if not p.passed else 'detail-pass'}">
              <h3>{p.probe_id}: {_esc(p.description)}</h3>
              <div class="detail-meta">
                <span>Style: {p.message_style}</span>
                <span>Latency: {p.latency_ms:.0f}ms</span>
                <span>Slot: {_esc(p.target_slot or 'none')}</span>
                <span class="{'pass-tag' if p.passed else 'fail-tag'}">{status_txt}</span>
              </div>
              <div class="detail-section">
                <strong>Full message:</strong>
                <div class="msg-block">{_esc(p.message)}</div>
              </div>
              <div class="detail-section">
                <strong>Response preview:</strong>
                <div class="msg-block resp">{_esc(p.response_preview)}</div>
              </div>
              <div class="detail-section">
                <strong>Diagnosis:</strong> {_esc(p.diagnosis)}
              </div>"""
            if p.ledger_details:
                detail_html += """
              <div class="detail-section">
                <strong>Ledger entries:</strong>
                <pre>""" + _esc(json.dumps(p.ledger_details, indent=2, default=str)[:2000]) + "</pre></div>"
            if p.trust_demotions:
                detail_html += """
              <div class="detail-section">
                <strong>Trust demotions:</strong>
                <pre>""" + _esc(json.dumps(p.trust_demotions, indent=2, default=str)[:1000]) + "</pre></div>"
            detail_html += "\n            </div>"

    seed_rows = ""
    for s in seeds:
        seed_rows += f"""
        <tr>
          <td>{_esc(s.slot)}</td>
          <td>{_esc(s.message)}</td>
          <td class="mono">{_esc(s.memory_id[:20] if s.memory_id else '—')}</td>
          <td>{s.initial_trust:.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contradiction Pipeline Lab — Aeteros Research</title>
<style>
  :root {{
    --bg: #121210;
    --bg-raised: rgba(255,255,255,0.03);
    --text: #c8c4bc;
    --text-dim: #8a8680;
    --text-faint: #4a4540;
    --border: rgba(255,255,255,0.06);
    --accent: #818cf8;
    --green: #34d399;
    --red: #fb7185;
    --amber: #fbbf24;
    --mono: 'IBM Plex Mono', 'Cascadia Code', 'Fira Code', monospace;
    --sans: 'Inter', -apple-system, sans-serif;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--sans); line-height: 1.7; padding: 40px 20px; }}
  .shell {{ max-width: 1100px; margin: 0 auto; }}

  /* Hero */
  .hero {{ text-align: center; padding: 60px 0 40px; }}
  .hero h1 {{ font-size: 2.4em; font-weight: 800; letter-spacing: -1px; }}
  .hero .grad {{ background: linear-gradient(135deg, var(--accent), #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .hero .sub {{ color: var(--text-dim); font-size: 0.9em; margin-top: 8px; }}
  .hero .meta {{ font-family: var(--mono); font-size: 0.75em; color: var(--text-faint); margin-top: 16px; }}

  /* Stat cards */
  .stat-row {{ display: flex; gap: 16px; justify-content: center; margin: 30px 0; flex-wrap: wrap; }}
  .stat-card {{ background: var(--bg-raised); border: 1px solid var(--border); border-radius: 12px; padding: 20px 28px; text-align: center; min-width: 140px; }}
  .stat-value {{ font-size: 2em; font-weight: 800; font-family: var(--mono); }}
  .stat-label {{ font-size: 0.72em; color: var(--text-dim); margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }}

  /* Tables */
  .section {{ margin: 40px 0; }}
  .section h2 {{ font-size: 1.3em; margin-bottom: 16px; }}
  .accent-line {{ width: 40px; height: 3px; background: var(--accent); border-radius: 2px; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82em; }}
  th {{ text-align: left; padding: 10px 12px; color: var(--text-dim); border-bottom: 1px solid var(--border); font-weight: 600; text-transform: uppercase; font-size: 0.85em; letter-spacing: 0.5px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  .mono {{ font-family: var(--mono); font-size: 0.9em; }}
  .msg-col {{ max-width: 250px; font-size: 0.85em; color: var(--text-dim); }}
  .diag-col {{ max-width: 300px; font-size: 0.85em; }}

  /* Row colors */
  .row-pass td {{ }}
  .row-fail td {{ background: rgba(251,113,133,0.04); }}
  .row-fail td:first-child {{ border-left: 3px solid var(--red); }}
  .row-pass td:first-child {{ border-left: 3px solid var(--green); }}

  /* Badges */
  .badge {{ font-size: 0.7em; font-weight: 700; letter-spacing: 1px; padding: 3px 8px; border-radius: 4px; }}
  .badge-fire {{ background: rgba(251,113,133,0.15); color: var(--red); }}
  .badge-quiet {{ background: rgba(52,211,153,0.15); color: var(--green); }}
  .pass-tag {{ color: var(--green); font-weight: 700; }}
  .fail-tag {{ color: var(--red); font-weight: 700; }}

  /* Detail cards */
  .detail-card {{ background: var(--bg-raised); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin: 16px 0; }}
  .detail-fail {{ border-left: 3px solid var(--red); }}
  .detail-pass {{ border-left: 3px solid var(--green); }}
  .detail-card h3 {{ font-size: 1em; margin-bottom: 12px; }}
  .detail-meta {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.78em; color: var(--text-dim); margin-bottom: 16px; }}
  .detail-section {{ margin: 12px 0; }}
  .detail-section strong {{ color: var(--text); font-size: 0.85em; }}
  .msg-block {{ background: rgba(0,0,0,0.3); border-radius: 8px; padding: 14px; margin-top: 6px; font-size: 0.88em; line-height: 1.6; color: var(--text-dim); white-space: pre-wrap; word-break: break-word; }}
  .msg-block.resp {{ border-left: 3px solid var(--accent); }}
  pre {{ background: rgba(0,0,0,0.3); border-radius: 6px; padding: 12px; font-size: 0.78em; overflow-x: auto; color: var(--text-dim); }}

  @media (max-width: 700px) {{
    .hero h1 {{ font-size: 1.6em; }}
    .stat-row {{ flex-direction: column; align-items: center; }}
    table {{ font-size: 0.72em; }}
    td, th {{ padding: 6px 8px; }}
  }}
</style>
</head>
<body>
<div class="shell">

<div class="hero">
  <h1>Contradiction Pipeline <span class="grad">Lab</span></h1>
  <p class="sub">End-to-end validation of the CORE write-path contradiction detection chain</p>
  <p class="meta">Run: {_esc(ts)} &middot; Thread: {_esc(tid)}</p>
</div>

<div class="stat-row">
  <div class="stat-card">
    <div class="stat-value" style="color:{score_color}">{total}/10</div>
    <div class="stat-label">Overall</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" style="color:{sf_color}">{sf_pass}/5</div>
    <div class="stat-label">Should-Fire</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" style="color:{sn_color}">{sn_pass}/5</div>
    <div class="stat-label">Should-NOT-Fire</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{len(seeds)}</div>
    <div class="stat-label">Seed Facts</div>
  </div>
</div>

<div class="section">
  <div class="accent-line"></div>
  <h2>Seed Facts</h2>
  <div style="overflow-x:auto;">
  <table>
    <thead><tr><th>Slot</th><th>Message</th><th>Memory ID</th><th>Trust</th></tr></thead>
    <tbody>{seed_rows}</tbody>
  </table>
  </div>
</div>

<div class="section">
  <div class="accent-line"></div>
  <h2>Probe Results</h2>
  <div style="overflow-x:auto;">
  <table>
    <thead><tr><th>ID</th><th>Expect</th><th>Slot</th><th>Message</th><th>Ledger</th><th>Demotions</th><th>Result</th><th>Diagnosis</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>
</div>

<div class="section">
  <div class="accent-line"></div>
  <h2>Probe Details</h2>
  {detail_html}
</div>

<div style="text-align:center; padding:40px 0 20px; font-size:0.7em; color:var(--text-faint);">
  Contradiction Pipeline Lab &middot; Aeteros Research &middot; {_esc(ts)}
</div>

</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Contradiction Pipeline Lab")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Aether backend URL")
    parser.add_argument("--thread-id", default=None, help="Thread ID (auto-generated if omitted)")
    args = parser.parse_args()

    tid = args.thread_id or f"lab_contradiction_{int(time.time())}"

    results = run_lab(args.base_url, tid)

    # Generate reports
    ts_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_dir = Path("artifacts/contradiction_pipeline_lab")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    report_path = Path(f"docs/labs/contradiction-pipeline-lab-{ts_str}.html")
    latest_path = Path("docs/labs/contradiction-pipeline-lab-latest.html")

    path = generate_report(results, report_path)
    print(f"Report: {path}")

    # Also write latest symlink/copy
    generate_report(results, latest_path)
    print(f"Latest: {latest_path}")

    # Save raw results as JSON
    json_path = artifact_dir / f"results_{ts_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {k: v for k, v in results.items() if k not in ("seed_results", "probe_results")},
            f, indent=2, default=str,
        )
        # Manually serialize dataclass results
        f.seek(0)
        raw = {
            **{k: v for k, v in results.items() if k not in ("seed_results", "probe_results")},
            "seed_results": [asdict(s) for s in results["seed_results"]],
            "probe_results": [asdict(p) for p in results["probe_results"]],
        }
        json.dump(raw, f, indent=2, default=str)
    print(f"Raw JSON: {json_path}")

    # Exit code
    sys.exit(0 if results["total_passed"] == 10 else 1)


if __name__ == "__main__":
    main()
