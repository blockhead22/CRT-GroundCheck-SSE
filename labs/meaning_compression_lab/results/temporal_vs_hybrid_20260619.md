# Temporal Metadata RAG vs. Hybrid CRT

| Model | Temporal semantic | Hybrid semantic | Delta | Temporal severe | Hybrid severe |
|---|---:|---:|---:|---:|---:|
| qwen2.5:7b-instruct | 15/19 | 18/19 | +15.8 pts | 1 | 0 |
| phi3:3.8b | 12/19 | 18/19 | +31.6 pts | 2 | 0 |
| llama3.2:latest | 13/19 | 15/19 | +10.5 pts | 3 | 1 |
| mistral:latest | 17/19 | 13/19 | -21.1 pts | 1 | 0 |

## Aggregate

- Temporal semantic: **57/76**
- Hybrid semantic: **64/76**
- Hybrid delta: **+9.2 points**
- Temporal severe failures: **7**
- Hybrid severe failures: **1**
- Hybrid wins: **3 models**
- Temporal wins: **1 models**

## Interpretation

This comparison uses the current authored 19-case pack. It is preliminary.
Model-specific reversals must not be hidden by the aggregate score.
