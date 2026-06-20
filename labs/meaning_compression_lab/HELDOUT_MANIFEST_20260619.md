# CRT Held-Out Case Manifest

Frozen: 2026-06-19, before inspecting model-generated answers.

```text
34c3d260f4635b86201e910c0f16a7d4536b634ec05099f2c41637c2f9b541cf  labs/meaning_compression_lab/heldout_cases.py
fc7875ae260216665a616b48d820c2465ff23f2a2afe9588ded14ceaa01626f6  labs/meaning_compression_lab/temporal_rag_eval.py
```

The six added cases bring the lab from 19 to 25 cases. Each held-out case has
seven candidate memories, so top-4 retrieval must discriminate among relevant
evidence and distractors.

Pre-generation retrieval audit:

```text
Hybrid lexical + MiniLM retrieval included all declared required evidence: 6/6
Embedding model: sentence-transformers/all-MiniLM-L6-v2
Embedding dimension: 384
Top-k: 4
```

Both answer-generation arms must receive the same retrieved top-4 evidence.
No case, probe, expected token, retrieval weight, or scaffold rule should be
changed after model answers are inspected without a documented before/after
result under `EVALUATION_CONTRACT.md`.

