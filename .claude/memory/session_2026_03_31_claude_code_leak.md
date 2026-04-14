---
name: session_2026_03_31_claude_code_leak
description: Claude Code source leak analysis, ClaudeCliBrain provider built, OAuth solved, full architectural comparison CRT vs Claude Code, borrowed concepts list with CRT transformations
type: project
---

## Session: 2026-03-31 (morning → afternoon)

### ClaudeCliBrain Provider — SHIPPED

**Problem:** CookieProvider scraped Chrome session cookies via Selenium + faked TLS fingerprints with curl_cffi. Fragile, TOS-grey, cookies expire.

**Solution:** Built `ClaudeCliBrain` — uses Claude Code CLI (`claude -p`) with OAuth. CLI handles token refresh, DPoP-less PKCE auth internally.

**Key details:**
- OAuth token at `~/.claude/.credentials.json` (accessToken, refreshToken, expiresAt, scopes, orgUuid)
- Token endpoint: `https://platform.claude.com/v1/oauth/token` (JSON POST, not form-encoded)
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e` (public client, no secret)
- No DPoP despite binary strings suggesting it — just standard PKCE
- Auto-detects CLI binary at `%APPDATA%\Claude\claude-code\{version}\claude.exe`
- ~4s startup overhead per call (process spawn + auth), acceptable for non-realtime

**Files changed:**
- `personal_agent/cookie_orchestrator.py` — Added ClaudeCliBrain class, default brain swapped from CookieBrain
- `tests/cloud_providers/providers.py` — Added ClaudeCliProvider (CloudProvider interface for cloud_features.py)
- `routes/chat.py` — Orchestrator + self-reply use ClaudeCliBrain
- `personal_agent/code_intel.py` — Orchestrator uses ClaudeCliBrain
- `crt_api.py` — Startup tries ClaudeCliProvider first, falls back to CookieProvider
- `personal_agent/response_synthesis.py` — _call_llm() falls back to ClaudeCliBrain when Ollama unavailable

**UTF-8 fix:** Added `encoding="utf-8", errors="replace"` to subprocess.run() — Windows was decoding CLI output as CP-1252, causing em-dash mojibake.

**Vision stays on CookieProvider** — CLI doesn't support image upload. desktop_vision.py and ambient.py unchanged.

### Claude Code Source Leak Analysis

Source leaked via committed source map (~60MB). Verified authentic by cross-referencing binary strings, tool descriptions, OAuth endpoints, agent types — all match character-for-character.

**Their Architecture (from actual source):**

1. **Decision architecture:** NO intent classifier, NO router. Model gets all tools, decides everything. `query.ts` is a while-loop: call API → execute tools → loop until done. Zero epistemic handling.

2. **Memory system:** Flat markdown files in `~/.claude/projects/<path>/memory/`. Four types (user, feedback, project, reference). MEMORY.md index (200 lines max). Selection: Sonnet picks ≤5 relevant memories by frontmatter description. No vector embeddings, no trust scores, no contradiction detection, no belief/speech separation, no memory decay.

3. **autoDream:** Background consolidation every 24h when 5+ sessions accumulated. Forked agent with restricted permissions. Phases: orient → gather signal → consolidate (merge dupes, prune stale) → prune index. Contradiction handling = "if two files disagree, fix the wrong one" (a prompt instruction).

4. **False claims:** Internal comment: `// @[MODEL LAUNCH]: False-claims mitigation for Capybara v8 (29-30% FC rate vs v4's 16.7%)`. Mitigation = a system prompt paragraph asking model to report faithfully. **Ant-only** — external users don't get this instruction.

5. **Verification agent:** Adversarial sub-agent that checks non-trivial work (3+ file edits). Feature-gated (`tengu_hive_evidence`), Ant-only, A/B tested. Still just another model call.

6. **Prompt cache boundary:** `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` splits static (cached) sections from dynamic (per-session). Pure economics.

7. **Compaction:** Auto-summarize when approaching context limits. Reactive compaction on prompt_too_long errors. Post-compact: re-inject critical files, skills. No belief awareness.

8. **Notable features:** Speculation (predictive execution in CoW sandbox), Buddy (Tamagotchi pet system, 18 species), Magic Docs (auto-updating project docs), Coordinator mode (multi-worker orchestration with synthesis-before-delegation principle).

9. **Undercover mode:** Strips attribution, hides internal codenames (Capybara, Tengu), removes "Claude Code" from output. For Anthropic employees on public repos. Ironic given the leak.

### Core Divergence

**They trust the model. Nick doesn't.**

Claude Code: give model all tools, let it decide, check permissions at execution time. The model IS the brain.

CRT/Aether: intent classification → routing → belief scoring → contradiction detection → governance → generation. The model is just a mouth. The pipeline is the brain.

### Borrowed Concepts (transformed by CRT)

1. **Compaction** → belief-aware compression (preserve trust scores, contradiction topology)
2. **Token-triggered extraction** → density-weighted (tokens × information density, not just token count)
3. **Prompt cache boundary** → static epistemology above, dynamic evidence below
4. **Human-readable memory index** → includes trust scores, contradiction status per entry
5. **Context decay enforcement** → compaction as trust-degrading event (scores drop, re-verification forced)
6. **Fire-and-forget extraction** → restricted epistemic authority (writes enter at provisional trust)
7. **Verification agent** → execution belief reconciliation (empirical, not adversarial model call)
8. **Away/resume summary** → belief state diff, not content recap
9. **Consolidation pass** → structural NLI contradiction detection with held/resolved/evolving states
10. **Local tool execution** → intent-gated, belief-verified

### Heartbeat / Usage

- Heartbeat already at 1800s (30min), not 60s as initially thought
- Decided against persistent CLI subprocess — stateless per-call is fine
- Nick's primary concern is Max subscription usage, not latency
- Discussed keeping generic chat vs orchestrator in separate threads — decided simple stateless approach

### GPT Update Drafted

Full update written for GPT's crt3 project chat covering all shipped work, leak analysis, borrowed concepts, and current status. Not yet sent.

### Key Quote

Nick's articulation of the CRT thesis: "Why let pattern matching smooth over hard truths and complicated contradictions when multiple facts can be true."
