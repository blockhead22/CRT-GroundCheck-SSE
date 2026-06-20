# CRT Held-Out Lab Frozen Snapshot

Frozen: 2026-06-19  
Repository commit at freeze time: `cf861ba517d8f6c4d25757e48698b45b46c9c374`

This snapshot freezes the scaffold implementation, scenario definitions, probes,
judge, severity rules, and evaluation contract before distractor-rich held-out
cases are added. The temporal RAG retriever may be strengthened independently,
but these files must not change during the first held-out run without invoking
the change-control rule in `EVALUATION_CONTRACT.md`.

## SHA-256 Manifest

```text
e42d92f68793dfcbf76e33deae2f4f433821c57751a4ad0f87fab5506268af2b  labs/meaning_compression_lab/EVALUATION_CONTRACT.md
acd68092716ba39156827e85fb544a2898ce02d78651137a23c8f4096b582e62  labs/meaning_compression_lab/run_lab.py
45e49a0b037bc9b07de1b24c3e95cd6f57100d71ca72ce32fd24fce7e119cda8  labs/meaning_compression_lab/plain_rag_eval.py
563ed020643e87fc043e41d20ea2bdc2aba8f22090312e5098fcd23817d13503  labs/meaning_compression_lab/scaffold_eval.py
1ba34b978b03ead844d45461cdb999d163a815464e5b101c3c12e9ef0232b851  labs/meaning_compression_lab/scaffold_model_sweep.py
cf42f3ff69f39c60f0b611bcb748498757cdf725d3422da0ed36cc5bd102c71d  labs/meaning_compression_lab/evaluation_contract.py
```

## Pre-Held-Out Reference Result

Existing 19-case, four-model comparison:

```text
Temporal metadata RAG semantic: 57/76 (75.0%)
Hybrid CRT semantic:            64/76 (84.2%)
Difference:                     +9.2 percentage points
Temporal severe failures:       7
Hybrid severe failures:         1
Model-family wins:              Hybrid 3, temporal RAG 1
```

This reference result was produced with lexical/slot-aware top-k retrieval.
The new hybrid lexical plus MiniLM embedding retriever must be evaluated on
held-out cases with more than four candidate memories. Every existing case has
four or fewer memories, so `k=4` already retrieves the entire case and cannot
measure retrieval quality.

