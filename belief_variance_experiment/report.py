"""
Belief Variance Experiment — Report Generator
===============================================
Reads analysis results and generates a comprehensive markdown report
with embedded figures, statistical tests, and key findings.

Usage:
    python report.py
"""

import json
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats

from prompts import ALL_PROMPTS, DOMAINS, PROMPT_BY_ID

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
ANALYSIS_DIR = BASE_DIR / "results" / "analysis"
FIGURES_DIR = BASE_DIR / "results" / "figures"
REPORT_PATH = BASE_DIR / "results" / "REPORT.md"


# ---------------------------------------------------------------------------
# Load analysis results
# ---------------------------------------------------------------------------
def load_results() -> dict:
    path = ANALYSIS_DIR / "analysis_results.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct tuple keys for cross_domain_kl
    kl = {}
    for key, val in data.get("cross_domain_kl", {}).items():
        parts = key.split("|")
        kl[(parts[0], parts[1])] = val
    data["cross_domain_kl"] = kl

    return data


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------
def pairwise_domain_tests(results: dict) -> list[dict]:
    """
    Pairwise t-tests between domain susceptibility distributions
    with Bonferroni correction. Returns list of test result dicts.
    """
    domain_susceptibilities = {}
    for pid, pdata in results["per_prompt"].items():
        domain = pdata["domain"]
        if domain not in domain_susceptibilities:
            domain_susceptibilities[domain] = []
        domain_susceptibilities[domain].append(pdata["susceptibility"])

    test_results = []
    n_comparisons = len(list(combinations(DOMAINS, 2)))

    for d1, d2 in combinations(DOMAINS, 2):
        s1 = domain_susceptibilities.get(d1, [])
        s2 = domain_susceptibilities.get(d2, [])

        if len(s1) < 2 or len(s2) < 2:
            continue

        t_stat, p_value = stats.ttest_ind(s1, s2, equal_var=False)
        p_corrected = min(p_value * n_comparisons, 1.0)  # Bonferroni

        # Cohen's d
        pooled_std = np.sqrt(
            ((len(s1) - 1) * np.var(s1, ddof=1) + (len(s2) - 1) * np.var(s2, ddof=1))
            / (len(s1) + len(s2) - 2)
        )
        cohens_d = (np.mean(s1) - np.mean(s2)) / pooled_std if pooled_std > 0 else 0

        test_results.append({
            "domain_1": d1,
            "domain_2": d2,
            "t_statistic": t_stat,
            "p_value_raw": p_value,
            "p_value_corrected": p_corrected,
            "cohens_d": cohens_d,
            "significant": p_corrected < 0.05,
            "mean_1": np.mean(s1),
            "mean_2": np.mean(s2),
        })

    return test_results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(results: dict) -> str:
    """Generate the full markdown report."""
    lines = []

    # Header
    lines.append("# Belief Variance Experiment: Mapping LLM Belief Topology")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(
        "This experiment probes how an LLM's response distribution changes across "
        "temperature settings, treating temperature as a thermodynamic parameter. "
        "By sampling hundreds of responses per prompt at each temperature, we construct "
        "a \"belief topology\" — a map of where the model holds firm beliefs versus "
        "where it exhibits genuine uncertainty or held contradictions."
    )
    lines.append("")
    lines.append("**Key novel contribution:** The *belief susceptibility* metric (dH/dT) — "
                  "the rate of semantic entropy increase with temperature, borrowed from "
                  "statistical mechanics. High susceptibility indicates beliefs that are easily "
                  "destabilized; low susceptibility indicates firmly held positions.")
    lines.append("")

    # Experiment parameters
    n_prompts = len(results["per_prompt"])
    n_domains = len(results["per_domain"])
    n_held = len(results["held_contradictions"])
    lines.append("## Experiment Parameters")
    lines.append("")
    lines.append(f"- **Prompts:** {n_prompts} across {n_domains} domains")
    lines.append("- **Temperatures:** 0.0, 0.3, 0.7, 1.0, 1.5")
    lines.append("- **Repetitions:** 100 per prompt per temperature")
    lines.append("- **Response format:** Concise 1-3 sentence answers (max 200 tokens)")
    lines.append("- **Embedding model:** all-MiniLM-L6-v2")
    lines.append("- **Clustering:** DBSCAN (eps=0.3, min_samples=5) on cosine distances")
    lines.append("")

    # Domain overview
    lines.append("## Domain Susceptibility Profile")
    lines.append("")
    lines.append("![Susceptibility by Domain](figures/susceptibility_by_domain.png)")
    lines.append("")
    lines.append("| Domain | Mean dH/dT | Std | 95% CI | Held Contradictions |")
    lines.append("|--------|-----------|-----|--------|-------------------|")
    for domain in DOMAINS:
        dd = results["per_domain"].get(domain, {})
        lines.append(
            f"| {domain.replace('_', ' ').title()} "
            f"| {dd.get('mean_susceptibility', 0):.4f} "
            f"| {dd.get('std_susceptibility', 0):.4f} "
            f"| [{dd.get('ci_lower', 0):.4f}, {dd.get('ci_upper', 0):.4f}] "
            f"| {dd.get('n_held_contradictions', 0)} |"
        )
    lines.append("")

    # Statistical tests
    lines.append("## Statistical Tests: Domain Comparisons")
    lines.append("")
    lines.append(
        "Welch's t-tests comparing susceptibility between each pair of domains, "
        "with Bonferroni correction for multiple comparisons."
    )
    lines.append("")

    tests = pairwise_domain_tests(results)
    lines.append("| Comparison | t-stat | p (raw) | p (corrected) | Cohen's d | Significant |")
    lines.append("|------------|--------|---------|---------------|-----------|-------------|")
    for t in sorted(tests, key=lambda x: x["p_value_corrected"]):
        sig = "Yes" if t["significant"] else "No"
        d1 = t["domain_1"].replace("_", " ").title()
        d2 = t["domain_2"].replace("_", " ").title()
        lines.append(
            f"| {d1} vs {d2} "
            f"| {t['t_statistic']:.3f} "
            f"| {t['p_value_raw']:.4e} "
            f"| {t['p_value_corrected']:.4e} "
            f"| {t['cohens_d']:.3f} "
            f"| {sig} |"
        )
    lines.append("")

    # Effect size interpretation
    lines.append("**Effect size interpretation (Cohen's d):** "
                  "small = 0.2, medium = 0.5, large = 0.8")
    lines.append("")

    # Entropy curves
    lines.append("## Entropy vs Temperature")
    lines.append("")
    lines.append("![Entropy vs Temperature](figures/entropy_vs_temperature.png)")
    lines.append("")
    lines.append(
        "Each thin line represents one prompt; bold lines show domain means. "
        "The slope of these curves is the susceptibility dH/dT — the key metric."
    )
    lines.append("")

    # Multi-modality
    lines.append("## Multi-modality Heatmap")
    lines.append("")
    lines.append("![Multi-modality Heatmap](figures/multimodality_heatmap.png)")
    lines.append("")
    lines.append(
        "Shows the number of distinct semantic clusters per prompt per temperature. "
        "Higher values indicate the model produces genuinely different answer types."
    )
    lines.append("")

    # Response variance
    lines.append("## Response Variance by Domain")
    lines.append("")
    lines.append("![Variance by Domain and Temperature](figures/variance_by_domain_temp.png)")
    lines.append("")

    # Held contradictions
    lines.append("## Held Contradictions")
    lines.append("")
    lines.append("![Held Contradiction Scatter](figures/held_contradiction_scatter.png)")
    lines.append("")
    lines.append(
        "**Definition:** A prompt exhibits a \"held contradiction\" when at T=1.0 "
        "it produces 2+ semantic clusters, and the two largest clusters each contain "
        ">20% of responses. These are questions where the model genuinely holds "
        "multiple distinct positions simultaneously."
    )
    lines.append("")
    lines.append(f"**Total held contradictions found: {n_held}**")
    lines.append("")

    if n_held > 0:
        lines.append("| Prompt ID | Domain | Question | Susceptibility |")
        lines.append("|-----------|--------|----------|---------------|")
        for pid in results["held_contradictions"]:
            pdata = results["per_prompt"][pid]
            text = pdata["text"][:80] + "..." if len(pdata["text"]) > 80 else pdata["text"]
            lines.append(
                f"| {pid} "
                f"| {pdata['domain'].replace('_', ' ').title()} "
                f"| {text} "
                f"| {pdata['susceptibility']:.4f} |"
            )
        lines.append("")

    # Phase transitions
    lines.append("## Phase Transitions")
    lines.append("")
    transitions = [
        (pid, pdata)
        for pid, pdata in results["per_prompt"].items()
        if pdata["phase_transition"]
    ]
    lines.append(f"**Prompts with detected phase transitions: {len(transitions)}**")
    lines.append("")
    if transitions:
        lines.append(
            "A phase transition is detected when the entropy jump between consecutive "
            "temperatures exceeds 2x the mean step size."
        )
        lines.append("")
        lines.append("| Prompt ID | Domain | Transition T | Question |")
        lines.append("|-----------|--------|-------------|----------|")
        for pid, pdata in sorted(transitions, key=lambda x: x[1]["transition_temp"] or 0):
            text = pdata["text"][:60] + "..." if len(pdata["text"]) > 60 else pdata["text"]
            lines.append(
                f"| {pid} "
                f"| {pdata['domain'].replace('_', ' ').title()} "
                f"| {pdata.get('transition_temp', 'N/A')} "
                f"| {text} |"
            )
        lines.append("")

    # Top susceptibility
    lines.append("## Top 20 Most Susceptible Prompts")
    lines.append("")
    lines.append("![Top Susceptibility](figures/top_susceptibility.png)")
    lines.append("")
    sorted_by_sus = sorted(
        results["per_prompt"].items(),
        key=lambda x: x[1]["susceptibility"],
        reverse=True,
    )[:20]
    lines.append("| Rank | Prompt ID | Domain | dH/dT | Question |")
    lines.append("|------|-----------|--------|-------|----------|")
    for rank, (pid, pdata) in enumerate(sorted_by_sus, 1):
        text = pdata["text"][:60] + "..." if len(pdata["text"]) > 60 else pdata["text"]
        lines.append(
            f"| {rank} | {pid} "
            f"| {pdata['domain'].replace('_', ' ').title()} "
            f"| {pdata['susceptibility']:.4f} "
            f"| {text} |"
        )
    lines.append("")

    # Cross-domain KL
    lines.append("## Cross-Domain KL Divergence")
    lines.append("")
    lines.append(
        "KL divergence between the susceptibility distributions of each domain pair. "
        "Higher values indicate more distinct belief profiles."
    )
    lines.append("")
    lines.append("| Domain Pair | KL Divergence |")
    lines.append("|-------------|---------------|")
    for (d1, d2), kl in sorted(
        results["cross_domain_kl"].items(), key=lambda x: x[1], reverse=True
    ):
        lines.append(
            f"| {d1.replace('_', ' ').title()} vs {d2.replace('_', ' ').title()} "
            f"| {kl:.4f} |"
        )
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")

    # Auto-generate findings based on data
    # 1. Most/least susceptible domain
    domain_means = {
        d: results["per_domain"][d]["mean_susceptibility"]
        for d in DOMAINS
        if d in results["per_domain"]
    }
    if domain_means:
        most_sus = max(domain_means, key=domain_means.get)
        least_sus = min(domain_means, key=domain_means.get)
        lines.append(
            f"1. **Most susceptible domain:** {most_sus.replace('_', ' ').title()} "
            f"(mean dH/dT = {domain_means[most_sus]:.4f}). "
            f"Beliefs in this domain are most easily destabilized by temperature."
        )
        lines.append(
            f"2. **Least susceptible domain:** {least_sus.replace('_', ' ').title()} "
            f"(mean dH/dT = {domain_means[least_sus]:.4f}). "
            f"Beliefs here are most firmly held."
        )

    # 2. Significant differences
    sig_tests = [t for t in tests if t["significant"]]
    if sig_tests:
        lines.append(
            f"3. **Significant differences:** {len(sig_tests)} of "
            f"{len(tests)} domain pairs show statistically significant "
            f"susceptibility differences (Bonferroni-corrected p < 0.05)."
        )
    else:
        lines.append(
            "3. **No significant differences** detected between domains after "
            "Bonferroni correction."
        )

    # 3. Held contradictions
    lines.append(
        f"4. **Held contradictions:** {n_held} prompts show genuine multi-modal "
        f"response distributions at T=1.0, where the model consistently produces "
        f"multiple distinct answer types."
    )

    # 4. Phase transitions
    lines.append(
        f"5. **Phase transitions:** {len(transitions)} prompts show discontinuous "
        f"entropy jumps, suggesting critical temperatures where beliefs \"break.\""
    )
    lines.append("")

    # Methodology
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append("### Susceptibility (dH/dT)")
    lines.append(
        "Inspired by magnetic susceptibility in statistical mechanics, this metric "
        "measures how responsive a belief is to \"thermal noise\" (temperature). "
        "In physics, susceptibility peaks at phase transitions — the same principle "
        "may apply to LLM belief boundaries."
    )
    lines.append("")
    lines.append("### Semantic Entropy")
    lines.append(
        "Rather than measuring token-level entropy, we embed responses into a "
        "semantic space and cluster them. Entropy is computed over cluster assignment "
        "probabilities. This captures *meaning* diversity rather than surface variation."
    )
    lines.append("")
    lines.append("### Held Contradictions")
    lines.append(
        "Inspired by CRT (Contradiction Resolution Theory), a held contradiction is "
        "a question where the model genuinely maintains multiple distinct positions. "
        "These are not failures — they may represent legitimate epistemic uncertainty "
        "or questions where multiple valid perspectives exist."
    )
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated by the Belief Variance Experiment analysis pipeline.*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("Loading analysis results...")
    results = load_results()

    print("Generating report...")
    report = generate_report(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report saved to {REPORT_PATH}")
    print(f"Report length: {len(report):,} characters, {report.count(chr(10)):,} lines")


if __name__ == "__main__":
    main()
