---
name: Session 2026-04-01 Strategy & User Belief System
description: Full system audit by Opus, business strategy decided, reversed CRT concept, user_belief system shipped, open/closed split finalized.
type: project
---

## What Happened

1. **Full codebase audit** — Opus investigated the entire system from code (not memory files). 114K lines Python, 26K lines TypeScript/React. Identified all key architectural components, assessed strengths, warnings, and LLM escape risks.

2. **Reversed CRT concept** — the same epistemic system applied to the USER's beliefs instead of the AI's. Every immune agent has a reversed counterpart. Memory splats track user belief landscape. The engine is identical, the subject changes.

3. **Business strategy decided** — governance-as-a-service, not the assistant. 4-phase plan: open source → hosted API → enterprise dashboard → consumer epistemic mirror. See strategy_business_plan.md.

4. **Open/closed split finalized** — framework (immune agents, belief engine, splats, contradiction lifecycle, trust math) goes open. Product (prompts, providers, models, data, UI, integrations) stays closed.

5. **User belief system shipped** — Phase 0 of reversed CRT:
   - `user_belief` kind in crt_memory.py (allowed kinds, type mapping, review defaults, sigma/decay)
   - `classify_assertion_kind()` in belief_classifier.py (13/13 accuracy)
   - `_classify_user_input` updated: belief expressions ("I think", "I believe") now route to assertion path instead of being discarded
   - crt_rag.py assertion storage path routes through belief classifier
   - `BELIEF_EXTRACTION_PROMPT` + `extract_beliefs()` in llm_extractor.py
   - `/api/beliefs` endpoint in routes/memory.py
   - Retrieval kinds updated in routes/chat.py

## Files Modified
- `personal_agent/crt_memory.py` — user_belief in allowed kinds, type map, review defaults
- `personal_agent/belief_classifier.py` — added classify_assertion_kind(), is_user_belief()
- `personal_agent/crt_rag.py` — belief starters in input classifier, belief routing in storage path
- `personal_agent/llm_extractor.py` — BELIEF_EXTRACTION_PROMPT, extract_beliefs()
- `routes/chat.py` — user_belief in retrieval kinds
- `routes/memory.py` — /api/beliefs endpoint

## Key Warnings Identified
- Prompt injection via memory (crafted memories survive governance, influence future responses)
- Tool access via intent classifier misrouting
- Cross-channel injection (Telegram/Discord memories affecting web chat)
- Self-model manipulation (shift execution beliefs to loosen behavior)
- Memory as persistent backdoor (high-trust injected instruction persists through compaction)
- Governance bypass via held contradictions (force system to articulate harmful content as "one side")

## Key Quotes
- "The mouth must never outweigh the self"
- "CRT was built to keep AI honest. Turns out humans need it more."
- "Your AI agent doesn't know what it doesn't know. Ours does."
- "The threat isn't IP theft — it's obscurity."
