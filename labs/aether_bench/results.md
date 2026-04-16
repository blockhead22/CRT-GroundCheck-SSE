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

## Brain: `ollama_coder14b`

| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |
|---|---|---|---|---|---|---|---|---|
| cold | 18 | 283 | 258 | 0.19 | 0.0 | 0.0 | 40196 | 0 |
| warm | 18 | 448 | 386 | 0.00 | 0.0 | 0.0 | 17264 | 0 |

**Paired (n=18)** — t on tokens (cold−warm): -4.056 · sign test correctness: warm-better=0, cold-better=5, ties=13

## Brain: `ollama_qwen14b`

| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |
|---|---|---|---|---|---|---|---|---|
| cold | 19 | 606 | 549 | 0.13 | 0.0 | 0.0 | 36439 | 0 |
| warm | 19 | 1421 | 1446 | 0.18 | 0.8 | 0.8 | 63843 | 0 |

**Paired (n=18)** — t on tokens (cold−warm): -8.167 · sign test correctness: warm-better=3, cold-better=3, ties=12
