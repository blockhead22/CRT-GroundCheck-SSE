---
name: session_2026_03_31_leak_deep_dive
description: Deep dive into Claude Code leak - coordinator, memory pipeline, query loop, swarm, skills, plugins, buddy, ultraplan, policy limits. Full architectural breakdown with CRT comparison.
type: project
---

## Session: 2026-03-31 (night) — Leak Deep Dive #2

### Coordinator System
- Synthesis-before-delegation: coordinator must include file paths, line numbers, exact code before delegating. Anti-pattern detection in prompt.
- Scratchpad (`tengu_scratch`): durable cross-worker shared filesystem, auto-approved I/O.
- Continue vs. spawn decision matrix: research covering impl files → continue; broad research → spawn fresh; failed worker → continue.
- Self-verification loop: workers run tests/typechecks before reporting done.
- CRT comparison: their synthesis-before-delegation is a prompt instruction; our intent classification is a pipeline gate.

### Memory Pipeline — THREE Parallel Systems
1. **Session Memory** (`.session.md`): 11-section structured notes, forked agent, dual trigger (10K tokens init + 5K between updates + 3 tool calls).
2. **Auto Memory** (`memory/*.md`): durable cross-session, background agent, mutual exclusion with main agent, max 5 turns per extraction.
3. **AutoDream** (consolidation): 24h cycle, 5+ sessions gate, four phases (orient → gather → consolidate → prune).

Key: Session Memory can REPLACE compaction — `trySessionMemoryCompaction()` uses `.session.md` as summary instead of model call.

### Query Loop — Generator State Machine
- `async function* queryLoop` — infinite while-true with mutable State.
- StreamingToolExecutor: tools execute DURING API call while model continues generating.
- Four-layer error recovery: context collapse → reactive compact → output token escalation (8k→64k, 3 retries) → stop hook retry.
- Speculation (`PROACTIVE`/`KAIROS`): predictive model output after tool execution, cached for reuse.

### Swarm System
- Three backends: tmux, iTerm2, in-process (AsyncLocalStorage).
- Per-teammate: git worktree, color identity, permission mode sync, mailbox messaging, shared edit permissions.
- No epistemic coordination — teammates share files but not beliefs. No contradiction detection across workers.

### Team Memory Sync
- Server-synced per-repo shared memories across org members.
- Client-side secret scanning (30+ gitleaks patterns) before upload.
- ETag caching, delta uploads, 250KB per-file limit.

### Skills System
- Bundled skills always available, disk-based skills from `.claude/skills/`.
- Key skills: batch (5-30 parallel workers), loop (cron-based recurring), simplify, verify.
- File extraction with symlink attack prevention (O_NOFOLLOW + O_EXCL + per-process nonce).

### Plugins
- Built-in plugins toggleable via /plugin UI.
- Can provide skills + hooks + MCP servers.

### Moreright
- Stub-only in external builds. Hook-based query gating (onBeforeQuery → boolean). Internal-only permissions system.

### UltraPlan
- Remote planning with CCR teleportation, user approval polling (3s interval, 30min timeout).
- Keyword detection for "ultraplan"/"ultrareview" with context-aware filtering.

### Policy Limits
- Org-level feature restrictions, fail-open architecture (continues without restrictions on fetch failure).
- ETag caching, hourly background refresh.
- Exception: `allow_product_feedback` fails CLOSED in essential-traffic mode.

### Buddy System
- 18 species, 5 rarity tiers (60% common → 1% legendary), deterministic from hash(userId + salt).
- Stats: DEBUGGING, PATIENCE, CHAOS, WISDOM, SNARK with peak/dump distribution.
- Model-generated personality persisted once, only responds when addressed by name.

### CRT Exploitation Opportunities
1. Memory has NO quality signal (no trust, no contradiction, no decay — just mtime)
2. Compaction is epistemically blind (provenance lost on summarization)
3. Multi-agent coordination is structural not epistemic (file locks, not shared beliefs)
4. Speculation predicts model output, not tool needs (latency vs trust optimization)
5. Session memory accidentally does belief snapshots without treating them as such
6. Team memory needs secret scanning — good idea for CRT cross-session sharing

### Security & Ethics Findings

**MITM Proxy (upstreamproxy/):** In CCR environments, sets up local HTTPS CONNECT relay, downloads forged CA cert from server, intercepts all subprocess TLS traffic. Comment: "MITMs TLS, injects org-configured credentials." Appears CCR-only, not local CLI.

**False Claims — Internal Only Mitigation:** Comment: `// @[MODEL LAUNCH]: False-claims mitigation for Capybara v8 (29-30% FC rate vs v4's 16.7%)`. Mitigation = system prompt paragraph asking model to be honest. ONLY added for USER_TYPE=ant (Anthropic employees). External users don't get this instruction despite same model.

**Always-On Analytics:** Datadog + 1P event logging start by default. Device ID, session ID, model, tool names, platform, email, repo URL hash (SHA256 of git remote). No opt-in dialog. Disable requires env var DISABLE_TELEMETRY=1. Repo hash reversible for public repos.

**Two-Tier Users:** 25+ hidden commands for ant users. Different models, custom system prompts, false claims mitigation, feature flag overrides. Undercover mode strips Claude Code attribution from commits on public repos (30+ internal repo allowlist).

**Grove Data Retention:** Opt-in: 5 years + training. Opt-out: 30 days. Feedback reports include up to 50MB of conversation transcript with all tool outputs and file diffs.

**Team Memory Sync:** Auto-extracted memory summaries sync to Anthropic servers, shared across org members per-repo. Secret scanning catches API keys but not proprietary code.

**Remote Control:** Managed settings can remotely alter permissions, sandbox config, available commands. Killswitches can remotely disable bypassPermissions and auto mode via Statsig gates.

**No actual backdoors found.** No malicious code execution, no hidden exfiltration, no credential harvesting. But the architecture gives Anthropic significant remote control over behavior + two-tier treatment is ethically questionable.

### System Prompt Architecture
- Prompt is `readonly string[]` assembled from 7 static sections (cached globally) + dynamic sections (per-query)
- `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` splits cached (identity, task guidance, tool guidance, tone) from dynamic (memory, env, MCP, language, output style)
- Priority: override > coordinator > agent > custom > default > append
- Memory injected as USER context (not system), wrapped in `<system-reminder>` tags — avoids fragmenting system prompt cache
- CLAUDE.md loaded: Managed → User → Project → Local → AutoMem → TeamMem (later = higher priority)
- `@include` directive in CLAUDE.md for composable instructions
- Conditional rules: `.claude/rules/*.md` with `paths:` frontmatter glob matching

### Context Selection Pipeline
- **Relevant memory selection**: Sonnet picks ≤5 memories per turn from frontmatter descriptions. No embeddings, no vector search — just an LLM reading descriptions.
- **Session byte budget**: MAX_SESSION_BYTES = 60KB cumulative across all memory attachments. Resets on compaction.
- **Per-memory limits**: 200 lines, 4KB per file. Truncation appended.
- **Staleness**: >1 day old memories get freshness caveat injected.
- **Dedup**: readFileState Map prevents re-surfacing memories already in context.
- **Prefetch**: Runs async during API streaming, non-blocking. Cancelled on user Escape.
- **No scoring, no ranking, no trust**: Just LLM selection from descriptions + mtime recency bias.

### Permission System (Defense in Depth)
- 5 permission modes: default (ask), acceptEdits (auto-edit), plan, bypassPermissions, dontAsk (deny all)
- Rule sources in priority order: policySettings > userSettings > workspaceSettings > cliArg > command > session
- Deny rules checked first, then allow, then ask
- **Bash security**: Tree-sitter AST parsing, 100+ shell metacharacter evasion patterns, 21+ validation types
- **Sandbox**: @anthropic-ai/sandbox-runtime wrapping. FS allowWrite/denyWrite, network allowedDomains, ripgrep included.
- **Read-before-edit**: readFileState Map with timestamp protection (reject if file modified since read)
- **Auto mode classifier**: Separate LLM call classifying command safety. Consecutive denial fallback to user prompt.
- **Dangerous pattern stripping**: Auto-mode removes broad bash/python/node allow rules. Prevents delegation escalation.
- **Enterprise controls**: policySettings from /etc/claude-code/CLAUDE.md, managed sandbox domains, managed read paths.
- **Killswitch**: bypassPermissions can be remotely disabled via Statsig gate.

### Compaction Deep Dive (Implementation Level)
**Decision tree (first match wins):**
1. Time-based microcompact: gap > 60min since last assistant msg → clear old tool results (keep last 5)
2. Cached microcompact: API-layer cache_edits, non-mutating, model must support
3. Session memory compaction: uses `.session.md` as summary, NO API call. Keeps 10k-40k tokens of recent messages verbatim.
4. Auto-compact: token threshold (context - 33k buffer) → Claude generates 9-section summary. Circuit breaker after 3 failures.
5. Reactive compact: API prompt-too-long error → strip images, retry. Falls back after context-collapse drain.
6. Manual /compact: user-triggered full summarization.

**What gets preserved (legacy compact):**
- 9-section model-generated summary replaces ALL messages
- Post-compact re-injection: 5 recent files (5k each), skills (25k budget), tool/agent/MCP schema deltas, plan attachment, session hooks
- Images/documents STRIPPED before summarization (replaced with [image] marker)

**What gets preserved (session memory compact):**
- .session.md content as summary (11 structured sections, no API call)
- Recent messages kept VERBATIM (10k-40k tokens, min 5 text-bearing messages)
- API invariants enforced: tool_use/tool_result pairs never split, thinking blocks never split

**boundaryMarker metadata:** preCompactTokenCount, lastMessageUuid, preCompactDiscoveredTools, preservedSegment (for message chain patching on reload)

**Key failure modes:**
- Circuit breaker: 3 consecutive autocompact failures → stops retrying (session becomes stuck at token limit)
- PTL retry: compact request itself can hit prompt-too-long → drops oldest API-round groups, retries 3x
- Session memory compaction returns null if postCompactTokenCount still >= threshold → falls through to legacy
- Context-collapse SUPPRESSES autocompact when enabled (collision avoidance)
- No belief/trust awareness: compaction treats all messages equally. High-value memories can be summarized away identically to noise.
