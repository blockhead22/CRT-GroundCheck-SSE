---
name: project_pipeline_optimization
description: CRT pipeline latency analysis and optimization plan. 15-phase pipeline profiled. 5 actionable wins identified. Target 3-5x speedup without removing epistemic work.
type: project
---

## Pipeline Latency Profile (March 2026)

**Typical request: ~1.5s. Worst case: ~5.3s. LLM generation = 77% of total.**

15 phases traced from `/api/chat/send` through `CRTEnhancedRAG.query()`. Key files:
- Entry: `routes/chat.py:2269` (chat_send)
- Engine: `personal_agent/crt_rag.py:4147` (CRTEnhancedRAG.query)
- Reasoning: `personal_agent/reasoning.py:210` (ReasoningEngine.reason)
- LLM: `personal_agent/litellm_client.py` (UnifiedLLMClient)
- Gates: `personal_agent/crt_core.py` (CRTMath.check_reconstruction_gates_v2)

### Non-LLM Overhead Breakdown
- Session/DB: 15ms
- Classification: 20ms
- Memory analysis: 30ms
- Gate check: 15ms
- Intent routing: 10ms
- Memory retrieval (vector search): 80ms
- Context assembly: 20ms
- Post-gen analysis: 50ms
- Reconstruction gates: 20ms
- Contradiction detection: 80ms
- Calibration + return: 20ms
- **Total non-LLM: ~360ms** (epistemic overhead: ~200ms of this)

## 5 Optimization Wins (Decided)

### 1. Ollama MLX Update (Mac M2) — FREE, 1 min
Ollama shipped MLX backend 2026-03-30. 93% faster decode (58→112 tok/s), 57% faster prefill. Just `ollama update`.

### 2. Pin Model + Static System Prompt Prefix — FREE, 30 min
`OLLAMA_KEEP_ALIVE=-1` keeps model loaded. Move all dynamic content to END of system prompt so prefix is byte-identical across turns. Measured: 962ms→54ms prefill (17.7x) when KV cache hits.

### 3. Replace Intent Routing LLM with Fine-Tuned Classifier — 2-3 days
ModernBERT or DistilBERT, trained on run log data (Layer 1). 200-400ms → 5-50ms (10-40x faster). Export via ONNX.

### 4. Parallelize Independent Phases — 1 day
Phases 1-5 are all independent. asyncio.gather() saves ~65ms. Background contradiction detection (Phase 12) after response sent saves 80-300ms off critical path.

### 5. Speculative Decoding — 1 day setup
llama.cpp server with Qwen2.5-0.5B draft model for 8B target. 1.5-2x generation speedup, zero quality loss. Ollama doesn't support yet — use llama.cpp server directly with OpenAI-compatible API.

## Target: 1500ms → 300-500ms typical (3-5x improvement)

## Other Findings
- ExLlamaV2: 2x faster than llama.cpp on NVIDIA GPU (GPTQ quant)
- ik_llama.cpp fork: 1.38x speedup over mainline llama.cpp
- Used RTX 3090 ($700-900): best value GPU for local inference (24GB VRAM)
- Q4_K_M: sweet spot quant for routing/classification
- Model2Vec: 500x faster embeddings than sentence-transformers (quality tradeoff)
- Semantic caching: cache by cosine similarity threshold (0.92) for repeated queries

## Key Principle
CRT epistemic overhead is ~200ms. That's the cost of honesty. Don't optimize it away. Optimize the plumbing (LLM calls, DB queries, routing) so the epistemic work becomes a smaller % of total time.
