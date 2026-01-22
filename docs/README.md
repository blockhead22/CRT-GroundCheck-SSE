# GroundCheck Documentation

This directory contains documentation for the GroundCheck project, including the research paper and experimental artifacts.

## Directory Structure

```
docs/
├── paper/                    # Research paper
│   ├── sections/            # Paper sections (markdown)
│   │   ├── 01_abstract.md
│   │   ├── 02_introduction.md
│   │   ├── 03_related_work.md
│   │   ├── 04_method.md
│   │   ├── 05_groundingbench.md
│   │   ├── 06_experiments.md
│   │   ├── 07_discussion.md
│   │   └── 08_conclusion.md
│   ├── figures/             # Paper figures
│   │   └── README.md
│   ├── tables/              # Paper tables
│   │   └── README.md
│   ├── references.bib       # Bibliography
│   └── main.tex            # LaTeX template
│
├── experiments/             # Experimental artifacts
│   ├── results/            # Raw experimental results
│   ├── analysis/           # Analysis documents
│   │   ├── comparison_table.md
│   │   ├── error_analysis.md
│   │   └── ablation_studies.md
│   ├── figures/            # Generated figures
│   └── README.md
│
└── README.md               # This file
```

## Paper Sections

The paper is organized into 8 sections, each in a separate markdown file for easy editing:

1. **Abstract** - Overview and key results
2. **Introduction** - Problem statement and contribution
3. **Related Work** - Comparison with existing methods
4. **Method** - GroundCheck algorithm details
5. **GroundingBench** - Benchmark description and statistics
6. **Experiments** - Experimental setup, results, and analysis
7. **Discussion** - Implications, limitations, and future work
8. **Conclusion** - Summary and final thoughts

## Key Results

### Main Finding

**GroundCheck achieves 90% accuracy on contradiction handling vs ~30% for existing methods (3x improvement)**

### Performance Comparison

| System | Overall | Contradictions | Latency | Cost |
|--------|---------|----------------|---------|------|
| GroundCheck | 76% | **90%** | <10ms | $0 |
| SelfCheckGPT | 82% | 30% | ~2.5s | $0.015 |
| CoVe | 79% | 35% | ~3.0s | $0.020 |
| Vanilla RAG | 45% | 0% | <1ms | $0 |

### Why This Matters

Existing grounding verification methods assume retrieved context is internally consistent. This assumption breaks down in long-term memory systems where:
- User facts change over time (job, location, preferences)
- Medical records evolve with new diagnoses
- Legal cases update as new evidence emerges

GroundCheck is the first system to explicitly handle contradictions in retrieved context.

## Experimental Artifacts

### Results Directory
Contains raw experimental results in JSON format:
- `baseline_comparison.json` - Full results for all systems
- Individual system results files

### Analysis Directory
Contains detailed analysis:
- `comparison_table.md` - Performance comparison across all categories
- `error_analysis.md` - Breakdown of errors by system and category
- `ablation_studies.md` - Impact of each component

### Figures Directory
Placeholder for paper figures (to be generated)

## Building the Paper

### From Markdown
The paper sections are in markdown format for easy editing and review.

### LaTeX Compilation
To generate PDF:

```bash
cd docs/paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

**Note:** You'll need to manually insert the markdown content into the LaTeX template.

## Contributing

When updating the paper:
1. Edit the relevant markdown file in `sections/`
2. Keep the LaTeX template in sync
3. Update references in `references.bib` as needed
4. Regenerate figures if data changes

## Citation

```bibtex
@article{groundcheck2024,
  title={GroundCheck: Contradiction-Aware Grounding Verification for Long-Term AI Memory Systems},
  author={Anonymous},
  journal={arXiv preprint},
  year={2024}
}
```

## License

MIT License - See LICENSE file for details

## Contact

For questions about the paper or experiments, please open an issue in the repository.
