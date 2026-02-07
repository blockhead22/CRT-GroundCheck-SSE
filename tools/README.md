# Tools

Testing, validation, and operational utilities for CRT-GroundCheck-SSE.

---

## Stress Tests

| Tool | What It Tests | Requires |
|------|--------------|----------|
| `adversarial_crt_challenge.py` | 7-phase adversarial contradiction testing (35 turns) | Offline (no Ollama) |
| `crt_stress_test.py` | Full 30-turn memory + trust analysis | Ollama + API server |
| `adaptive_stress_test.py` | Reactive adversarial conversation (40-80 turns) | API server |
| `full_stress_test.py` | Extended suite: memory, contradictions, gates, NL resolution, DB integrity | API server |
| `quick_stress_test.py` | Fast subset validation | API server |
| `nl_resolution_stress_test.py` | Natural language resolution patterns | API server |
| `stress_test_runner.py` | Comprehensive runner with metrics collection | API server |
| `crt_adaptive_stress_test.py` | CRT-specific adaptive testing | API server |

### Quick Commands

```bash
# Offline adversarial test (no server needed)
python tools/adversarial_crt_challenge.py --turns 35

# Full stress test (start Ollama + API first)
ollama serve
python crt_api.py &
python tools/crt_stress_test.py --turns 30 --print-every 5

# Quick validation
python tools/quick_stress_test.py
```

---

## Calibration & Training

| Tool | Purpose |
|------|---------|
| `calibrate_thresholds.py` | Calibrate contradiction detection thresholds → `artifacts/calibrated_thresholds.json` |
| `calibration_dataset.py` | Generate calibration datasets |
| `train_response_classifier.py` | Train response quality classifier (v1) |
| `train_response_classifier_v2.py` | Train response classifier (v2, improved) |
| `bootstrap_training_data.py` | Generate training data from existing conversations |
| `crt_learn_train.py` | Train CRT learned model |
| `crt_learn_eval.py` | Evaluate learned model |
| `crt_learn_make_eval_set.py` | Generate evaluation dataset |
| `crt_learn_publish.py` | Publish trained model to production |

---

## Inspection & Debugging

| Tool | Purpose |
|------|---------|
| `crt_dashboard.py` | CRT system dashboard |
| `crt_control_panel.py` | Runtime control panel |
| `crt_reflect.py` | Trigger manual reflection pass |
| `crt_response_eval.py` | Evaluate individual turn responses |
| `db_integrity_check.py` | Check database integrity |
| `sse_inspector.py` | Inspect SSE index contents |
| `sse_multi_cli.py` | Multi-document SSE CLI |
| `verify_evidence.py` | Verify evidence packet integrity |
| `validate_two_tier_integration.py` | Validate two-tier fact system |

---

## Detection Tests

| Tool | Purpose |
|------|---------|
| `run_detection_test.py` | Run contradiction detection test suite |
| `run_gate_test.py` | Run reconstruction gate tests |
| `run_resolution_test.py` | Run resolution pattern tests |
| `quick_validation_test.py` | Quick validation of core functionality |

---

## Analysis

| Tool | Purpose |
|------|---------|
| `analyze_stress_test_session.py` | Analyze JSONL stress test output for patterns |
| `crt_learn_eval.py` | Evaluate model performance |
