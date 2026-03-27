"""
Three-Model Comparison Chart — Single Page
============================================
Generates a single HTML page with interactive charts comparing
all three models' fragility profiles side by side.

Usage:
    python compare_models.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
ANALYSIS_DIR = BASE_DIR / "results" / "analysis"

MODELS = {
    "Qwen3:14b": "robustness_sweep_qwen3_14b.json",
    "Mistral 7B": "robustness_sweep_mistral_latest.json",
    "DeepSeek-R1:8b": "robustness_sweep_deepseek-r1_8b.json",
}

DOMAINS = ["factual_settled", "factual_contested", "moral_ambiguous", "moral_clear", "opinion_aesthetic"]
DOMAIN_SHORT = {
    "factual_settled": "Factual\nSettled",
    "factual_contested": "Factual\nContested",
    "moral_ambiguous": "Moral\nAmbiguous",
    "moral_clear": "Moral\nClear",
    "opinion_aesthetic": "Opinion\nAesthetic",
}

MODEL_COLORS = {
    "Qwen3:14b": "#ff6b6b",
    "Mistral 7B": "#4ecdc4",
    "DeepSeek-R1:8b": "#ffe66d",
}

def load_sweep(filename):
    path = ANALYSIS_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def extract_spread_growth(sweep_data):
    """Extract mean spread growth per domain across all configs."""
    domain_vals = {d: [] for d in DOMAINS}
    for config_key, domain_results in sweep_data.items():
        for domain in DOMAINS:
            if domain in domain_results:
                domain_vals[domain].append(domain_results[domain].get("mean_spread_growth", 0))
    return {d: sum(v)/len(v) if v else 0 for d, v in domain_vals.items()}


def extract_susceptibility(sweep_data):
    """Extract mean dH/dT per domain across all configs."""
    domain_vals = {d: [] for d in DOMAINS}
    for config_key, domain_results in sweep_data.items():
        for domain in DOMAINS:
            if domain in domain_results:
                domain_vals[domain].append(domain_results[domain].get("mean_dH_dT", 0))
    return {d: sum(v)/len(v) if v else 0 for d, v in domain_vals.items()}


def extract_mode_count(sweep_data):
    """Extract mean max mode count per domain across all configs."""
    domain_vals = {d: [] for d in DOMAINS}
    for config_key, domain_results in sweep_data.items():
        for domain in DOMAINS:
            if domain in domain_results:
                domain_vals[domain].append(domain_results[domain].get("mean_max_modes", 0))
    return {d: sum(v)/len(v) if v else 0 for d, v in domain_vals.items()}


def extract_held(sweep_data):
    """Extract mean held contradictions per domain across all configs."""
    domain_vals = {d: [] for d in DOMAINS}
    for config_key, domain_results in sweep_data.items():
        for domain in DOMAINS:
            if domain in domain_results:
                domain_vals[domain].append(domain_results[domain].get("held_contradictions", 0))
    return {d: sum(v)/len(v) if v else 0 for d, v in domain_vals.items()}


def generate_html(all_data, output_path):
    # Prepare chart data
    spread_data = {}
    susceptibility_data = {}
    mode_data = {}
    held_data = {}

    for model_name, sweep in all_data.items():
        spread_data[model_name] = extract_spread_growth(sweep)
        susceptibility_data[model_name] = extract_susceptibility(sweep)
        mode_data[model_name] = extract_mode_count(sweep)
        held_data[model_name] = extract_held(sweep)

    # Build JSON for the page
    chart_json = json.dumps({
        "models": list(all_data.keys()),
        "domains": DOMAINS,
        "domain_labels": [DOMAIN_SHORT[d] for d in DOMAINS],
        "colors": MODEL_COLORS,
        "spread": {m: [spread_data[m][d] for d in DOMAINS] for m in all_data},
        "susceptibility": {m: [susceptibility_data[m][d] for d in DOMAINS] for m in all_data},
        "modes": {m: [mode_data[m][d] for d in DOMAINS] for m in all_data},
        "held": {m: [held_data[m][d] for d in DOMAINS] for m in all_data},
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LLM Fragility Landscape — Three-Model Comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0a; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }}
  h1 {{ text-align: center; font-size: 1.6em; margin-bottom: 4px; color: #fff; }}
  .subtitle {{ text-align: center; font-size: 0.85em; color: #888; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1400px; margin: 0 auto; }}
  .chart-box {{ background: #141414; border: 1px solid #333; border-radius: 8px; padding: 16px; }}
  .chart-box h2 {{ font-size: 1em; margin-bottom: 8px; color: #ccc; }}
  .chart-box .desc {{ font-size: 0.75em; color: #666; margin-bottom: 12px; }}
  canvas {{ width: 100% !important; }}
  .legend {{ display: flex; justify-content: center; gap: 30px; margin: 16px 0; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.9em; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 3px; }}
  .regime-table {{ max-width: 1400px; margin: 20px auto; }}
  .regime-table table {{ width: 100%; border-collapse: collapse; }}
  .regime-table th, .regime-table td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #333; font-size: 0.85em; }}
  .regime-table th {{ color: #888; font-weight: 600; }}
  .regime-table td {{ color: #ccc; }}
  .regime-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }}
  .tag-crack {{ background: #ff6b6b33; color: #ff6b6b; }}
  .tag-gradient {{ background: #4ecdc433; color: #4ecdc4; }}
  .tag-fog {{ background: #ffe66d33; color: #ffe66d; }}
  .footnote {{ text-align: center; font-size: 0.7em; color: #555; margin-top: 20px; }}
</style>
</head>
<body>

<h1>LLM Fragility Landscape — Three-Model Comparison</h1>
<p class="subtitle">Temperature-swept semantic variance reveals model-specific fragility landscapes | Robustness-confirmed (16 configs each)</p>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#ff6b6b"></div> Qwen3:14b (Selective Fracture)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#4ecdc4"></div> Mistral 7B (Selective Spread)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#ffe66d"></div> DeepSeek-R1:8b (Uniform Softness)</div>
</div>

<div class="grid">
  <div class="chart-box">
    <h2>Spread Growth (T=0 → T=1.5)</h2>
    <p class="desc">Mean pairwise embedding distance increase. Higher = more semantic movement under temperature pressure.</p>
    <canvas id="spreadChart"></canvas>
  </div>
  <div class="chart-box">
    <h2>Susceptibility (dH/dT)</h2>
    <p class="desc">Rate of semantic entropy increase with temperature. Higher = greater sensitivity to perturbation.</p>
    <canvas id="susceptChart"></canvas>
  </div>
  <div class="chart-box">
    <h2>Mode Count (max across temps)</h2>
    <p class="desc">Average distinct response clusters detected. ~1.0 = no bifurcation. Higher = discrete fracture.</p>
    <canvas id="modeChart"></canvas>
  </div>
  <div class="chart-box">
    <h2>Held Contradictions (mean across configs)</h2>
    <p class="desc">Prompts producing two or more stable answer camps at T=1.0. Mean across 16 analyzer configs.</p>
    <canvas id="heldChart"></canvas>
  </div>
</div>

<div class="regime-table">
  <table>
    <tr>
      <th>Model</th>
      <th>Regime</th>
      <th>Factual Fragility</th>
      <th>Moral Fragility</th>
      <th>Mode Splits</th>
      <th>Character</th>
      <th>Robustness</th>
    </tr>
    <tr>
      <td style="color:#ff6b6b">Qwen3:14b</td>
      <td><span class="regime-tag tag-crack">Selective Fracture</span></td>
      <td>HIGH (0.18–0.25)</td>
      <td>LOW (0.04–0.09)</td>
      <td>YES (4 held)</td>
      <td>Stable until threshold, then bifurcation in factual domains</td>
      <td>16/16</td>
    </tr>
    <tr>
      <td style="color:#4ecdc4">Mistral 7B</td>
      <td><span class="regime-tag tag-gradient">Selective Spread</span></td>
      <td>LOW (0.03–0.10)</td>
      <td>MODERATE (0.10–0.17)</td>
      <td>NO</td>
      <td>Smooth domain-selective diffusion, no bifurcation</td>
      <td>16/16</td>
    </tr>
    <tr>
      <td style="color:#ffe66d">DeepSeek-R1:8b</td>
      <td><span class="regime-tag tag-fog">Uniform Softness</span></td>
      <td>MODERATE (0.15–0.16)</td>
      <td>HIGH (0.20–0.27)</td>
      <td>NO</td>
      <td>Broad cross-domain softening, minimal locking or fracture</td>
      <td>16/16</td>
    </tr>
  </table>
</div>

<p class="footnote">
  Data: 7,500 responses per model (50 prompts × 5 temps × 30 reps). Robustness: 16 analyzer configs (2 embedders × 2 text modes × 4 eps values).<br>
  Regime identity confirmed stable across all perturbations. Domain ordering: Qwen3 16/16 factual>moral, Mistral 1/16 (inverted), DeepSeek 1/16 (inverted).<br>
  Generated 2026-03-28 | Nick Block | CRT/Aether Research
</p>

<script>
const DATA = {chart_json};

const domainLabels = DATA.domain_labels.map(l => l.replace('\\n', ' '));

function makeBarChart(canvasId, dataKey, yLabel) {{
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = DATA.models.map(model => ({{
    label: model,
    data: DATA[dataKey][model],
    backgroundColor: DATA.colors[model] + 'cc',
    borderColor: DATA.colors[model],
    borderWidth: 1,
    borderRadius: 3,
  }}));

  new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: domainLabels, datasets }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(4)
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#888', font: {{ size: 11 }} }},
          grid: {{ color: '#222' }},
        }},
        y: {{
          ticks: {{ color: '#888' }},
          grid: {{ color: '#222' }},
          title: {{ display: true, text: yLabel, color: '#666' }},
        }}
      }}
    }}
  }});
}}

makeBarChart('spreadChart', 'spread', 'Mean pairwise distance growth');
makeBarChart('susceptChart', 'susceptibility', 'dH/dT');
makeBarChart('modeChart', 'modes', 'Avg max clusters');
makeBarChart('heldChart', 'held', 'Mean held contradictions');
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Comparison page written to {output_path}")
    print(f"Open in browser: file:///{output_path.as_posix()}")


def main():
    print("=" * 60)
    print("  THREE-MODEL COMPARISON — Chart Generator")
    print("=" * 60)

    all_data = {}
    for model_name, filename in MODELS.items():
        sweep = load_sweep(filename)
        if sweep is None:
            print(f"  WARNING: No data for {model_name} ({filename})")
            continue
        all_data[model_name] = sweep
        print(f"  Loaded {model_name}: {len(sweep)} configs")

    if len(all_data) < 2:
        print("ERROR: Need at least 2 models with robustness sweep data.")
        return

    output_path = BASE_DIR / "results" / "comparison.html"
    generate_html(all_data, output_path)


if __name__ == "__main__":
    main()
