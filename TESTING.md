# Testing

## Fast, deterministic suite (recommended)

Runs the stable unit/integration tests under the `tests/` folder.

- `D:/AI_round2/.venv/Scripts/python.exe -m pytest -q tests`

This is the suite we keep green for regression.

## CRT-specific regressions

- `D:/AI_round2/.venv/Scripts/python.exe -m pytest -q tests/test_crt_claim_contradictions.py`

These tests validate:
- questions do not create contradictions
- conflicting assertions (name/employer) do create ledger entries
- reinforcements do not create contradictions

## Stress tests (LLM-backed)

These scripts talk to a live Ollama model, so they are slower and can be non-deterministic.

- Fast-ish smoke run (no sleep, fewer turns):
	- `D:/AI_round2/.venv/Scripts/python.exe crt_stress_test.py --turns 12 --sleep 0`

- Default 30-turn run (writes per-run DBs under `artifacts/`):
	- `D:/AI_round2/.venv/Scripts/python.exe crt_stress_test.py --turns 30`

Both `crt_stress_test.py` and `crt_stress_test_clean.py` support:
- `--model` (default: `llama3.2:latest`)
- `--turns` (default: 30)
- `--sleep` (default: 0.2)
- `--artifacts-dir`
- `--memory-db` / `--ledger-db` (override per-run DB paths)

## Top-level scripts

This repo contains some `test_*.py` files at the repo root that are more like ad-hoc scripts and may depend on generated artifacts or a running Ollama model.

If you run `pytest` without restricting to `tests/`, those scripts may be collected. Some are guarded to skip when required artifacts are missing.

## Notes

- Some tests emit DeprecationWarnings related to `datetime.utcnow()` usage in SSE code; they do not currently fail tests.
