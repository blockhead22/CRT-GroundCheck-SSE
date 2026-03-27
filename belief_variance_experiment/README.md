# Belief Variance Experiment

Maps LLM "belief topology" by sampling the same questions hundreds of times across different temperatures. The key novel metric is **belief susceptibility** (dH/dT) -- the rate of semantic entropy increase as temperature rises, borrowed from statistical mechanics.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
```

## Usage

```bash
# 1. Run the experiment (~$15-30 with gpt-4o-mini, 100k API calls)
python runner.py

# 2. Analyze results (runs offline, embeds with sentence-transformers)
python analyze.py

# 3. Generate markdown report with figures
python report.py
```

## What it measures

- **200 prompts** across 5 domains: factual settled, factual contested, opinion/aesthetic, moral clear, moral ambiguous
- **5 temperatures**: 0.0, 0.3, 0.7, 1.0, 1.5
- **100 repetitions** per prompt per temperature (100,000 total samples)

## Key metrics

| Metric | Description |
|--------|-------------|
| Semantic entropy H(T) | Entropy over DBSCAN clusters of embedded responses |
| Susceptibility dH/dT | Linear regression slope of entropy vs temperature |
| Multi-modality | Number of distinct semantic clusters |
| Held contradictions | Prompts with 2+ large clusters at T=1.0 |
| Phase transitions | Discontinuous entropy jumps between temperatures |
| Phrasing sensitivity | Jensen-Shannon divergence between alternate phrasings |

## Output

Results land in `results/`:
- `raw/` -- JSONL files per prompt per temperature
- `embeddings/` -- cached sentence embeddings (.npy)
- `analysis/` -- JSON metrics
- `figures/` -- matplotlib visualizations
- `REPORT.md` -- full analysis report

## Options

```bash
python runner.py --model gpt-4o --reps 50 --max-concurrent 30
python runner.py --yes  # skip confirmation
python analyze.py --embedding-model all-mpnet-base-v2  # use a different embedder
python analyze.py --force-embed  # recompute all embeddings
```
