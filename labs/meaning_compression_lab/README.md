# Meaning Compression Lab

Offline toy lab for testing one concrete claim:

> Meaning-preserving compression should keep deterministic layered structure,
> not merely reconstruct the original text.

See `STATUS.md` for the current evidence snapshot and `ROADMAP.md` for the
proof plan and next priorities.

The lab compares several representations across five deterministic scenarios:

- identity flip
- employer correction
- provisional/social authority boundary
- locked policy constraint
- concern/preference preservation

An optional adversarial starter pack adds ten harder fixture scenarios:

- provisional/social favorite color contradicted by later confirmed user fact
- answer-style preference revision
- current project flip and reversion
- stale location correction
- destructive-command locked policy
- previous-value history question
- contradiction-status question
- multi-fact correction
- model-generated identity contamination
- tool-inferred location noise

It can also replay a real CRT SQLite memory DB by reading the persisted
`memories` and `memory_facts` tables. That path is for checking whether actual
`CRTMemorySystem.store_memory(...)` writes can be reduced into the same
deterministic meaning-state schema.

Reports include an evidence label per scenario:

- `fixture`: hand-authored deterministic lab fixture
- `crt_db_replay`: scenario reconstructed from persisted CRT SQLite rows

The DB replay path uses persisted `memory_facts` for user facts. Locked
force-push policy replay is intentionally narrow: it projects only the existing
lab claim, `Never force push to main`, from a locked `ops` memory row. It is not
a general policy parser.

Each scenario compares:

- full transcript
- naive summary
- slot-only state
- CRT-style compressed state
- damaged CRT variants

The primary score is structural. The lab reduces the source event stream into a
canonical meaning state, projects each compressed representation into that same
schema, and checks deterministic invariants:

- current facts
- history/supersession
- preserved contradictions
- authority boundaries
- policy locks
- volatility
- reaction policy
- bit-level flags

Projection/behavior checks are secondary sanity checks. The headline result is
the aggregate structural score and meaning density across scenarios.

Behavior bridge tests live outside this toy lab. They verify that the same CRT
claims govern user-visible RAG answers:

```bash
python -m pytest tests/test_crt_rag_behavior_bridge.py -q
```

Baseline comparison:

```bash
python labs/meaning_compression_lab/baseline_eval.py
python labs/meaning_compression_lab/baseline_eval.py --include-adversarial
```

This compares CRT governed state against latest-only slots, naive summary, and
a plain-retrieval-style projection. It is a structural baseline, not a full
external RAG implementation.

Plain-RAG answer comparison:

```bash
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated --include-adversarial
python labs/meaning_compression_lab/plain_rag_eval.py --mode ollama --model qwen2.5:7b-instruct
```

The simulated mode is deterministic. The Ollama mode is empirical and depends
on the installed local model, so treat it as a lab run rather than a unit test.

Meaning scaffold comparison:

```bash
python labs/meaning_compression_lab/scaffold_eval.py
python labs/meaning_compression_lab/scaffold_eval.py --include-adversarial
python labs/meaning_compression_lab/scaffold_eval.py --mode ollama --model qwen2.5:7b-instruct --include-adversarial
python labs/meaning_compression_lab/scaffold_model_sweep.py --models qwen2.5:7b-instruct phi3:3.8b llama3.2:latest mistral:latest
```

This compares raw transcript fragments against compact compressed meaning
fragments. It is the first explicit test of whether the LLM-facing scaffold can
carry answer behavior without replaying the full transcript. The default mode
is deterministic and offline. Ollama mode asks the local model to answer from
raw retrieved memory text and then from compressed scaffold text.

The model sweep repeats the Ollama scaffold comparison across multiple local
executors and reports whether the scaffold advantage survives model changes.

Run:

```bash
python labs/meaning_compression_lab/run_lab.py
python labs/meaning_compression_lab/run_lab.py --include-adversarial
```

Replay an actual CRT DB as an extra scenario:

```bash
python labs/meaning_compression_lab/run_lab.py --crt-db path/to/crt.db --thread-id lab-thread
```

The script is deterministic, uses only the Python standard library, and writes a
timestamped JSON result under `labs/meaning_compression_lab/results/`.
