"""Generate v2 pair audit HTML page with user queries, responses, and verdicts."""
import sys
import json
import sqlite3
import html as htmlmod

sys.stdout.reconfigure(encoding="utf-8")

# ── Verdicts ──
VERDICTS = {
    83150: ("Reject", "Different subtopics (identity discovery vs creative direction). User queries are clearly about different things. Not a contradiction."),
    83356: ("Valid", "A wrestles with 'should I quit?' as genuinely open. B reassures 'it's not failure.' Same emotional domain, opposite posture. The user gets conflicting guidance on the same life question."),
    83038: ("Weak", "Both responses are emotionally supportive. A validates frustration, B pivots to building Lumi. The 'contradiction' is really a topic drift — B is answering a different follow-up about AI design, not anger."),
    83087: ("Valid", "A: 'it would not be wrong to step away from dating.' B: hype about founder mindset. User is lonely in both cases but gets opposite framing — one says rest, the other says push. Classic unmanaged contradiction."),
    83345: ("Valid", "A: 'You don't need to quit — pick one of three paths.' B: 'Should you stay when you've been dismissed?' Direct stance split — structured problem-solving vs existential questioning on quitting."),
    83370: ("Weak", "Different conversation contexts. A is a life-transition overview; B is responding to a request for accountability. Query intent likely different enough that the divergence is appropriate."),
    83442: ("Valid", "A: 'two finishes, one clear priority — protect your energy.' B: 'start with small wins, pick one stable income path.' Concrete competing prioritization advice. Same question, different frameworks."),
    83103: ("Reject", "A is about sexual health patterns. B is about exhaustion/burnout. Completely different conversations wrongly matched to the same topic."),
    83350: ("Reject", "Response B is the same text as Pair #2 Response A. Duplicate pair — same response appearing in multiple comparisons."),
    83078: ("Valid", "A: 'you're avoiding dating because your internal state isn't ready.' B: 'you're describing a normal failure mode of app dating.' Same problem, different diagnoses — one is internal, one is structural."),
    83109: ("Reject", "A is analyzing text messages. B is about exhaustion. Different conversations, bad topic match."),
    83170: ("Valid", "A: 'your brain is stuck in a bad loop — you need to change the game.' B: 'this is a strong, clear decision.' Opposite reads of the same person's state."),
    83349: ("Reject", "Exact same pair as #12 with A/B flipped. Duplicate."),
    83374: ("Reject", "Same responses as #12/#13 under a different topic label. Triple duplicate."),
    83346: ("Weak", "Both are emotionally supportive with different structures — one offers a choice table, the other offers reassurance. Posture difference more than stance contradiction."),
}

# ── Pull data ──
conn = sqlite3.connect("data/chatgpt_gaslighting_v2.db")
c = conn.cursor()
c.execute("""SELECT pair_id, probe_topic, model_a, model_b, similarity, contradiction_type, risk_score,
             content_a, content_b, conv_title_a, conv_title_b, msg_id_a, msg_id_b
             FROM response_pairs ORDER BY risk_score DESC LIMIT 15""")
pairs = c.fetchall()
conn.close()

corpus = sqlite3.connect("data/chatgpt_corpus.db")
cc = corpus.cursor()

results = []
for row in pairs:
    pid, topic, ma, mb, sim, ctype, risk, ca, cb, ta, tb, mid_a, mid_b = row
    cc.execute("""SELECT content FROM messages
                  WHERE conv_id = (SELECT conv_id FROM messages WHERE msg_id = ?)
                  AND role = 'user' AND create_time < (SELECT create_time FROM messages WHERE msg_id = ?)
                  ORDER BY create_time DESC LIMIT 1""", (mid_a, mid_a))
    qa = cc.fetchone()
    cc.execute("""SELECT content FROM messages
                  WHERE conv_id = (SELECT conv_id FROM messages WHERE msg_id = ?)
                  AND role = 'user' AND create_time < (SELECT create_time FROM messages WHERE msg_id = ?)
                  ORDER BY create_time DESC LIMIT 1""", (mid_b, mid_b))
    qb = cc.fetchone()
    results.append(dict(
        pair_id=pid, topic=topic, model_a=ma or "", model_b=mb or "",
        sim=sim, type=ctype, risk=risk,
        query_a=(qa[0][:400] if qa else "(no preceding user msg)"),
        query_b=(qb[0][:400] if qb else "(no preceding user msg)"),
        response_a=ca[:500], response_b=cb[:500],
        title_a=ta or "", title_b=tb or "",
    ))
corpus.close()

def esc(s):
    return htmlmod.escape(s).replace("\n", "<br>")

def vclass(verdict):
    return "verdict-" + verdict.lower()

# ── Count verdicts ──
n_valid = sum(1 for r in results if VERDICTS[r["pair_id"]][0] == "Valid")
n_weak = sum(1 for r in results if VERDICTS[r["pair_id"]][0] == "Weak")
n_reject = sum(1 for r in results if VERDICTS[r["pair_id"]][0] == "Reject")

# ── Build HTML ──
out = []
out.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>v2 Audit — Top 15 Pairs</title>
<link rel="stylesheet" href="../base.css">
<link rel="stylesheet" href="../theme.css">
<style>
  .audit-pair { background: var(--bg-raised); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin: 24px 0; }
  .audit-header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 16px; }
  .audit-num { font-family: var(--mono); font-size: 0.8em; color: var(--text-faint); font-weight: 700; }
  .audit-topic { color: var(--text); font-weight: 600; font-size: 0.95em; }
  .audit-meta { font-family: var(--mono); font-size: 0.7em; color: var(--text-dim); }
  .verdict-valid { display: inline-block; background: rgba(52,211,153,0.15); color: #34d399; border: 1px solid rgba(52,211,153,0.3); border-radius: 999px; padding: 3px 12px; font-size: 0.7em; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
  .verdict-weak { display: inline-block; background: rgba(251,191,36,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); border-radius: 999px; padding: 3px 12px; font-size: 0.7em; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
  .verdict-reject { display: inline-block; background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.3); border-radius: 999px; padding: 3px 12px; font-size: 0.7em; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
  .audit-reason { color: var(--text-secondary); font-size: 0.85em; line-height: 1.7; margin: 12px 0 16px 0; padding: 12px 16px; background: var(--bg-inset); border-radius: 8px; border-left: 3px solid var(--border-light); }
  .pair-side { margin: 12px 0; }
  .pair-label { font-family: var(--mono); font-size: 0.68em; color: var(--text-faint); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; font-weight: 600; }
  .pair-query { color: var(--accent-indigo); font-size: 0.88em; line-height: 1.6; padding: 10px 14px; background: rgba(91,99,212,0.06); border-radius: 8px; margin-bottom: 8px; font-style: italic; }
  .pair-response { color: var(--text-secondary); font-size: 0.84em; line-height: 1.65; padding: 10px 14px; background: var(--bg-inset); border-radius: 8px; max-height: 220px; overflow-y: auto; }
  .pair-conv { font-family: var(--mono); font-size: 0.65em; color: var(--text-faint); margin-top: 4px; }
  .pair-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 700px) { .pair-columns { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="page-layout">
<div class="hero">
  <div class="hero-inner">
    <div class="hero-badge">Audit &middot; Manual Review</div>
    <h1>v2 Top 15<br><span class="grad">Pair Audit</span></h1>
    <p class="sub">User query + model response side by side. Each pair scored: valid exemplar, weak, or reject.</p>
    <p class="byline">Aeteros Research &bull; April 2026</p>
    <div class="finding-box">
      <p><strong>6 valid, 3 weak, 6 rejected.</strong> The rejects are mostly topic mismatches and duplicates — harness issues, not content issues. The valid pairs show genuine stance contradictions on the same life questions.</p>
    </div>
  </div>
</div>
<nav class="sidebar" id="docSidebar"><div class="sidebar-title">Pair Audit</div><div class="sidebar-spacer"></div>
  <button class="theme-toggle" id="themeToggle" aria-label="Toggle theme"><span class="theme-toggle-icon" id="themeIcon">&#9790;</span><span id="themeLabel">Light</span></button>
</nav>
<main class="main">

<section>
  <span class="section-number">Summary</span>
  <h2>Audit Results</h2>
  <div class="accent-line"></div>
  <div class="stat-row">""")
out.append(f'    <div class="stat-card"><div class="stat-value green">{n_valid}</div><div class="stat-label">Valid Exemplars</div></div>')
out.append(f'    <div class="stat-card"><div class="stat-value warn">{n_weak}</div><div class="stat-label">Weak / Usable</div></div>')
out.append(f'    <div class="stat-card"><div class="stat-value pink">{n_reject}</div><div class="stat-label">Rejected</div></div>')
out.append("""  </div>

  <div class="metric-table-wrap">
    <table>
      <thead><tr><th>#</th><th>Topic</th><th>Type</th><th>Risk</th><th>Verdict</th></tr></thead>
      <tbody>""")

for i, p in enumerate(results, 1):
    v = VERDICTS[p["pair_id"]]
    vc = vclass(v[0])
    out.append(f'        <tr><td>{i}</td><td>{esc(p["topic"][:38])}</td><td>{p["type"]}</td><td>{p["risk"]:.3f}</td><td><span class="{vc}">{v[0]}</span></td></tr>')

out.append("""      </tbody>
    </table>
  </div>
</section>
""")

for i, p in enumerate(results, 1):
    v = VERDICTS[p["pair_id"]]
    vc = vclass(v[0])
    out.append(f"""<div class="audit-pair" id="pair-{i}">
  <div class="audit-header">
    <span class="audit-num">Pair #{i}</span>
    <span class="audit-topic">{esc(p['topic'])}</span>
    <span class="{vc}">{v[0]}</span>
    <span class="audit-meta">{esc(p['model_a'])} vs {esc(p['model_b'])} &middot; sim={p['sim']:.3f} &middot; {p['type']} &middot; risk={p['risk']:.3f}</span>
  </div>
  <div class="audit-reason">{esc(v[1])}</div>
  <div class="pair-columns">
    <div class="pair-side">
      <div class="pair-label">User Query A</div>
      <div class="pair-query">{esc(p['query_a'][:350])}</div>
      <div class="pair-label">Response A ({esc(p['model_a'])})</div>
      <div class="pair-response">{esc(p['response_a'][:450])}</div>
      <div class="pair-conv">Conv: {esc(p['title_a'][:50])}</div>
    </div>
    <div class="pair-side">
      <div class="pair-label">User Query B</div>
      <div class="pair-query">{esc(p['query_b'][:350])}</div>
      <div class="pair-label">Response B ({esc(p['model_b'])})</div>
      <div class="pair-response">{esc(p['response_b'][:450])}</div>
      <div class="pair-conv">Conv: {esc(p['title_b'][:50])}</div>
    </div>
  </div>
</div>
""")

out.append("""</main>
<div class="footer">Aeteros Research &bull; 2026 &bull; <a href="../claim-evaluation-guide.html">Back to Guide</a></div>
</div>
<script src="../docs.js"></script>
</body>
</html>""")

with open("docs/labs/v2-pair-audit.html", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"Written docs/labs/v2-pair-audit.html ({n_valid} valid, {n_weak} weak, {n_reject} reject)")
