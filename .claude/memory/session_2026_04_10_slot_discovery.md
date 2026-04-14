---
name: session_2026_04_10_slot_discovery
description: Slot name discovery shipped (production heartbeat + legal case study + GPT log mining). Aether self-contradiction moment. GBrain competitive scan.
type: project
---

# Session 2026-04-10: Slot Discovery & Competitive Scan

## Slot Name Discovery — New Capability (3 implementations)

### 1. Production Heartbeat Integration
- **personal_agent/slot_name_discovery.py** — Auto-discovers slot names from memory text patterns during heartbeat
- Extracts frame patterns ("I go to X for coffee" -> `coffee_shop` slot)
- Maintains `slot_candidates` table, promotes when evidence threshold hit (3+ hits, 2+ unique values)
- Called from `heartbeat_executor.py` via `run_name_discovery_pass()`

### 2. Legal Case Study (Adnan Syed)
- **labs/case_study/adnan_syed/slot_bootstrapper.py** — Zero-LLM slot discovery from legal evidence
- Found 24 domain slots (e.g., `trunk_pop_location`, `burial_time`, `cell_tower_claim`)
- `case_loader.py` updated to call `bootstrap_slots()` and build hybrid extractor
- Results in `discovered_slots.json`

### 3. GPT Log Mining
- **labs/coherence_decay/bootstrap_gpt_logs.py** — Slot discovery against 25,726 production messages
- Found 300+ frame patterns (`belief` 311x, `consumption`, `desire`, `learning`)
- Filters against known hardcoded slots
- Results in `gpt_slot_discovery.json`

**Key insight**: Domain adaptation = slot bootstrapping. Architecture generalizes, vocabulary doesn't. Auto-discovery at 39% precision is good enough as a candidate pipeline.

## Aether Self-Contradiction Moment

Asked "What is the biggest contradiction you hold?" — Aether produced a genuinely sharp response:

> "I'm a system designed to distrust unearned confidence, running on confidence I didn't earn."

Identified the bootstrapping paradox (trust scores are handed, not earned from Aether's perspective), the audit gap (can't introspect own weights), and the three-option framing (radical skepticism vs blind acceptance vs CRT's visible-and-contestable scores). Fidelity mirror flagged gate fail.

## GBrain Competitive Scan (garrytan/gbrain)

Garry Tan's "mini-AGI brain" — actually a markdown-to-Postgres indexer with pgvector search. Supabase backend, OpenAI embeddings, MCP integration.

**One good idea**: "Compiled truth + timeline" pattern — current understanding above `---`, immutable evidence trail below. Clean separation.

**What it lacks vs CRT**: No contradiction detection, no trust scores, no earned beliefs, no epistemic governance, no belief/speech separation, no cascade dynamics, no slot discovery, no drift measurement, no self-audit. It's a retrieval layer, not a reasoning layer. A filing cabinet an LLM can search.

**Assessment**: Well-packaged RAG pipeline. "Brain" framing is marketing. The gap between GBrain and CRT is the gap between "find the relevant document" and "do I actually believe this."
