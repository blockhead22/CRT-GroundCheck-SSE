# Aether Bench Results

## Brain: `stub`

| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |
|---|---|---|---|---|---|---|---|---|
| cold | 6 | 217 | 217 | 0.00 | 0.0 | 0.0 | 0 | 0 |
| warm | 6 | 107 | 107 | 0.00 | 3.0 | 3.0 | 0 | 0 |

**Paired (n=2)** — t on tokens (cold−warm): 3.143 · sign test correctness: warm-better=0, cold-better=0, ties=2

## Brain: `stub>stub2`

| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |
|---|---|---|---|---|---|---|---|---|
| cold | 3 | 313 | 313 | 0.00 | 0.0 | 0.0 | 0 | 0 |
| warm | 3 | 168 | 168 | 0.00 | 4.0 | 4.0 | 0 | 0 |

**Paired (n=1)** — t on tokens (cold−warm): 0.0 · sign test correctness: warm-better=0, cold-better=0, ties=1

## Brain: `ollama_qwen7b`

| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |
|---|---|---|---|---|---|---|---|---|
| cold | 21 | 457 | 497 | 0.12 | 0.0 | 0.0 | 8484 | 2 |
| warm | 39 | 1096 | 827 | 0.15 | 1.4 | 1.4 | 6168 | 2 |

**Paired (n=18)** — t on tokens (cold−warm): -6.464 · sign test correctness: warm-better=4, cold-better=4, ties=10
