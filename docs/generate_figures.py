"""Generate dark-themed publication figures for experiments.html"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path('D:/AI_round2/docs/figures')
OUT.mkdir(exist_ok=True)

# Dark theme
plt.rcParams.update({
    'figure.facecolor': '#060814',
    'axes.facecolor': '#0a0e1a',
    'text.color': '#c0c8e0',
    'axes.labelcolor': '#8a90b0',
    'xtick.color': '#5a6080',
    'ytick.color': '#5a6080',
    'axes.edgecolor': '#1a1f35',
    'grid.color': '#151a2e',
    'grid.alpha': 0.5,
    'font.family': 'sans-serif',
    'font.size': 11,
})

COLORS = {
    'qwen': '#f472b6',
    'mistral': '#34d399',
    'deepseek': '#fbbf24',
    'indigo': '#818cf8',
    'purple': '#c084fc',
}

DOMAINS = ['factual_settled', 'factual_contested', 'moral_ambiguous', 'moral_clear', 'opinion_aesthetic']
DOMAIN_SHORT = ['fact_settled', 'fact_contested', 'moral_ambig', 'moral_clear', 'opinion']

# ========== Load data ==========
sweep = {}
for model, fname in [('qwen', 'qwen3_14b'), ('mistral', 'mistral_latest'), ('deepseek', 'deepseek-r1_8b')]:
    sweep[model] = json.load(open(f'D:/AI_round2/belief_variance_experiment/results/analysis/robustness_sweep_{fname}.json'))

density = {}
for model, fname in [('qwen', 'qwen3_14b'), ('mistral', 'mistral_latest'), ('deepseek', 'deepseek-r1_8b')]:
    density[model] = json.load(open(f'D:/AI_round2/belief_variance_experiment/results/density_analysis/{fname}_density.json'))

# ========== 1. Cross-model spread growth grouped bar ==========
fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(DOMAINS))
width = 0.25

# Average spread_growth across all 16 configs
for i, (model, color, label) in enumerate([
    ('qwen', COLORS['qwen'], 'Qwen3:14b'),
    ('mistral', COLORS['mistral'], 'Mistral 7B'),
    ('deepseek', COLORS['deepseek'], 'DeepSeek-R1:8b'),
]):
    vals = []
    for domain in DOMAINS:
        config_vals = [sweep[model][k][domain]['mean_spread_growth'] for k in sweep[model]]
        vals.append(np.mean(config_vals))
    bars = ax.bar(x + i*width - width, vals, width, label=label, color=color, alpha=0.85, edgecolor='none')
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003, f'{v:.3f}',
                ha='center', va='bottom', fontsize=7.5, color=color, fontweight='bold')

ax.set_xticks(x)
ax.set_xticklabels(DOMAIN_SHORT, fontsize=10)
ax.set_ylabel('Spread Growth (T=0 → T=1.5)', fontsize=11)
ax.set_title('Cross-Model Spread Growth by Domain', fontsize=14, color='#fff', fontweight='bold', pad=16)
ax.legend(loc='upper right', framealpha=0.3, edgecolor='#1a1f35')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 0.32)
fig.tight_layout()
fig.savefig(OUT / 'cross_model_spread.png', dpi=150, facecolor='#060814')
plt.close()
print('OK: cross_model_spread.png')

# ========== 2. Robustness heatmap (spread_growth across 16 configs) ==========
fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
for ax, (model, label, color) in zip(axes, [
    ('qwen', 'Qwen3:14b', COLORS['qwen']),
    ('mistral', 'Mistral 7B', COLORS['mistral']),
    ('deepseek', 'DeepSeek-R1:8b', COLORS['deepseek']),
]):
    configs = list(sweep[model].keys())
    matrix = np.zeros((len(DOMAINS), len(configs)))
    for j, cfg in enumerate(configs):
        for i, domain in enumerate(DOMAINS):
            matrix[i, j] = sweep[model][cfg][domain]['mean_spread_growth']

    im = ax.imshow(matrix, aspect='auto', cmap='RdYlBu_r', vmin=0, vmax=0.30,
                   interpolation='nearest')
    ax.set_title(label, color=color, fontsize=12, fontweight='bold', pad=10)
    ax.set_yticks(range(len(DOMAINS)))
    ax.set_yticklabels(DOMAIN_SHORT, fontsize=8)
    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels([f'C{i+1}' for i in range(len(configs))], fontsize=6, rotation=45)
    ax.set_xlabel('Config', fontsize=9)

cbar = fig.colorbar(im, ax=axes, shrink=0.8, pad=0.02)
cbar.set_label('Spread Growth', color='#8a90b0', fontsize=10)
cbar.ax.tick_params(colors='#5a6080')
fig.suptitle('Robustness Sweep: Spread Growth Across 16 Analyzer Configurations',
             color='#fff', fontsize=13, fontweight='bold', y=1.02)
fig.tight_layout()
fig.savefig(OUT / 'robustness_heatmap.png', dpi=150, facecolor='#060814', bbox_inches='tight')
plt.close()
print('OK: robustness_heatmap.png')

# ========== 3. Three-metric radar/profile per model ==========
fig, axes = plt.subplots(1, 3, figsize=(14, 5))
for ax, (model, label, color) in zip(axes, [
    ('qwen', 'Qwen3:14b', COLORS['qwen']),
    ('mistral', 'Mistral 7B', COLORS['mistral']),
    ('deepseek', 'DeepSeek-R1:8b', COLORS['deepseek']),
]):
    tmt = density[model].get('three_metric_table', {})
    domains_present = [d for d in DOMAINS if d in tmt]
    spreads = [tmt[d]['mean_spread_growth'] for d in domains_present]
    modes = [tmt[d]['mean_mode_count'] for d in domains_present]
    template_sims = [tmt[d]['mean_template_similarity'] for d in domains_present]

    x_pos = np.arange(len(domains_present))
    ax.bar(x_pos - 0.2, spreads, 0.2, color=color, alpha=0.9, label='Spread')
    ax.bar(x_pos, [m/5 for m in modes], 0.2, color=COLORS['indigo'], alpha=0.7, label='Modes/5')
    ax.bar(x_pos + 0.2, [1-t for t in template_sims], 0.2, color=COLORS['purple'], alpha=0.7, label='1-TemplateSim')

    ax.set_xticks(x_pos)
    ax.set_xticklabels([DOMAIN_SHORT[DOMAINS.index(d)] for d in domains_present], fontsize=7, rotation=30)
    ax.set_title(label, color=color, fontsize=12, fontweight='bold', pad=10)
    ax.set_ylim(0, 0.35)
    ax.grid(axis='y', alpha=0.3)
    if ax == axes[0]:
        ax.legend(fontsize=7, loc='upper right', framealpha=0.3, edgecolor='#1a1f35')

fig.suptitle('Three Metrics: Spread, Mode Count, Template Diversity',
             color='#fff', fontsize=13, fontweight='bold', y=1.02)
fig.tight_layout()
fig.savefig(OUT / 'three_metrics.png', dpi=150, facecolor='#060814', bbox_inches='tight')
plt.close()
print('OK: three_metrics.png')

# ========== 4. Domain inversion scatter (Qwen vs Mistral vs DeepSeek) ==========
fig, ax = plt.subplots(figsize=(8, 8))

# Average spread per domain per model
model_spreads = {}
for model in ['qwen', 'mistral', 'deepseek']:
    model_spreads[model] = {}
    for domain in DOMAINS:
        vals = [sweep[model][k][domain]['mean_spread_growth'] for k in sweep[model]]
        model_spreads[model][domain] = np.mean(vals)

# Scatter: Qwen factual spread vs Qwen moral spread for each domain
# Actually: plot each domain as a point with (factual_rank, moral_rank) per model
domain_colors = ['#818cf8', '#c084fc', '#f472b6', '#34d399', '#fbbf24']
for i, domain in enumerate(DOMAINS):
    qwen_v = model_spreads['qwen'][domain]
    mistral_v = model_spreads['mistral'][domain]
    deepseek_v = model_spreads['deepseek'][domain]

    ax.scatter(qwen_v, mistral_v, s=120, c=domain_colors[i], zorder=5, edgecolors='#fff', linewidth=0.5)
    ax.scatter(qwen_v, deepseek_v, s=120, c=domain_colors[i], zorder=5, marker='D', edgecolors='#fff', linewidth=0.5)

    # Label
    ax.annotate(DOMAIN_SHORT[i], (qwen_v, mistral_v), textcoords="offset points",
                xytext=(8, 5), fontsize=8, color=domain_colors[i])

# Diagonal line
ax.plot([0, 0.3], [0, 0.3], '--', color='#3a3f5c', alpha=0.5, linewidth=1)
ax.set_xlabel('Qwen3 Spread Growth', fontsize=11, color=COLORS['qwen'])
ax.set_ylabel('Spread Growth', fontsize=11)
ax.set_title('Domain Inversion: Where Each Model Is Fragile',
             color='#fff', fontsize=13, fontweight='bold', pad=16)
ax.grid(alpha=0.3)
ax.set_xlim(0, 0.28)
ax.set_ylim(0, 0.28)

# Custom legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#8a90b0', markersize=8, label='○ = Mistral'),
    Line2D([0], [0], marker='D', color='w', markerfacecolor='#8a90b0', markersize=8, label='◇ = DeepSeek'),
]
ax.legend(handles=legend_elements, loc='upper left', framealpha=0.3, edgecolor='#1a1f35', fontsize=9)
ax.text(0.22, 0.02, 'Above diagonal = more fragile\nthan Qwen3 in this domain',
        fontsize=7.5, color='#5a6080', style='italic')

fig.tight_layout()
fig.savefig(OUT / 'domain_inversion.png', dpi=150, facecolor='#060814')
plt.close()
print('OK: domain_inversion.png')

# ========== 5. Cascade firewall effectiveness curve ==========
fig, ax = plt.subplots(figsize=(10, 5))
# From cascade paper Section 7.6
firewalls = [0, 5, 10, 20, 53]
nodes_affected = [385, 383, 382, 361, 54]
impact = [110.7, 90.6, 88.1, 77.5, 31.2]
pct_ring = [0, 5/53*100, 10/53*100, 20/53*100, 100]

ax2 = ax.twinx()
l1 = ax.plot(pct_ring, nodes_affected, '-o', color=COLORS['indigo'], linewidth=2.5,
             markersize=8, label='Nodes affected', zorder=5)
l2 = ax2.plot(pct_ring, impact, '-s', color=COLORS['qwen'], linewidth=2.5,
              markersize=8, label='Total impact', zorder=5)

ax.fill_between(pct_ring, nodes_affected, alpha=0.08, color=COLORS['indigo'])
ax2.fill_between(pct_ring, impact, alpha=0.08, color=COLORS['qwen'])

ax.set_xlabel('% of Depth-1 Ring Used as Firewalls', fontsize=11)
ax.set_ylabel('Nodes Affected', fontsize=11, color=COLORS['indigo'])
ax2.set_ylabel('Total Impact', fontsize=11, color=COLORS['qwen'])
ax.set_title('Cascade Firewall Effectiveness — Phase Transition',
             color='#fff', fontsize=13, fontweight='bold', pad=16)

# Annotate the phase transition
ax.annotate('Phase transition:\n38% ring → 30% reduction\n100% ring → 86% reduction',
            xy=(75, 200), fontsize=8, color='#8a90b0', style='italic',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#0a0e1a', edgecolor='#1a1f35'))

ax.grid(alpha=0.3)
lines = l1 + l2
labels = [l.get_label() for l in lines]
ax.legend(lines, labels, loc='center right', framealpha=0.3, edgecolor='#1a1f35')

fig.tight_layout()
fig.savefig(OUT / 'firewall_curve.png', dpi=150, facecolor='#060814')
plt.close()
print('OK: firewall_curve.png')

# ========== 6. KL divergence heatmap ==========
fig, ax = plt.subplots(figsize=(7, 6))
kl_data = np.array([
    [0.000, 0.154, 4.221, 0.000, 9.139],
    [0.154, 0.000, 3.738, 0.000, 8.889],
    [4.221, 3.738, 0.000, 0.000, 0.293],
    [0.000, 0.000, 0.000, 0.000, 0.000],
    [9.139, 8.889, 0.293, 0.000, 0.000],
])
im = ax.imshow(kl_data, cmap='magma_r', interpolation='nearest')
ax.set_xticks(range(5))
ax.set_xticklabels(DOMAIN_SHORT, fontsize=8, rotation=35, ha='right')
ax.set_yticks(range(5))
ax.set_yticklabels(DOMAIN_SHORT, fontsize=8)

# Annotate cells
for i in range(5):
    for j in range(5):
        v = kl_data[i, j]
        color = '#fff' if v > 4 else '#c0c8e0' if v > 0.5 else '#5a6080'
        ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=8, color=color, fontweight='bold')

cbar = fig.colorbar(im, shrink=0.8)
cbar.set_label('KL Divergence', color='#8a90b0', fontsize=10)
cbar.ax.tick_params(colors='#5a6080')
ax.set_title('Cross-Domain KL Divergence (Qwen3)',
             color='#fff', fontsize=13, fontweight='bold', pad=16)
fig.tight_layout()
fig.savefig(OUT / 'kl_heatmap.png', dpi=150, facecolor='#060814')
plt.close()
print('OK: kl_heatmap.png')

print('\nAll 6 dark-themed figures generated.')
