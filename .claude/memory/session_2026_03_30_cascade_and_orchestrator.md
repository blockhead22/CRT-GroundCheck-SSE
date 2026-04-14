# Session 2026-03-30: Cascade Paper Fixes, BDG Wiring, Orchestrator Launch

## Cascade Paper Math Audit + Fixes
Full audit of all theorems in `papers/cascade_complexity/cascade_paper.md`:
- **Definition 3.5**: Added MAX aggregation rule for multi-parent nodes
- **Theorem 4.1**: Added L=1 tightness clarification
- **Theorem 4.3**: Renamed to "Per-Node Cascade Damping", added Corollary 4.3.1 (graph-wide bound d·ρ < 1)
- **Theorem 4.4**: Reframed as "Iterated Cascade Instability" with new Definition 4.4.1
- **Conjecture 4.5**: Swapped vertex cover for MLA reduction, consistent with appendix
- **Proposition 5.4**: Demoted to Conjecture, fake proof removed
- **Section 6.3**: DeGroot comparison corrected (per-node vs graph-wide)
- **Section 7.5**: NEW — full production BDG results (599 nodes, 4976 edges, three cascades)
- **Section 7.6**: NEW — firewall experiment (four strategies, phase transition finding)
- Abstract + intro updated to reflect all changes

## Real BDG Analysis
Built `papers/cascade_complexity/real_bdg.py` — loads production DB, computes similarity edges, runs cascades.
- 599 nodes, ~4700 RELATED_TO edges, density 0.014
- Cascades affect 64% of graph from any high-degree source
- Per-node damping works (ρ^j decay confirmed), graph-wide total 60x above per-path bound
- d·ρ ≈ 4.7 >> 1, so graph-wide convergence fails
- Firewalls ineffective individually; complete vertex cut needed for containment

## BeliefDependencyGraph Class
Built in `personal_agent/memory_graph.py` — the class the paper's Appendix A references now actually exists.
- Cascade propagation, firewall support, cycle detection, instability analysis
- All 5 original experiments pass
- SUPPORTS edge type added to EdgeType enum

## LiveBDG + Cascade Wiring (PRODUCTION)
Built `LiveBDG` singleton in `memory_graph.py`:
- Lazy builds from production DB on first use (~0.2s, 615+ nodes)
- Incremental updates on memory store and contradiction detection
- Thread-safe via RLock

Wired into production:
- `_record_and_cascade()` replaces all 12 `record_contradiction()` call sites in crt_rag.py
- Background daemon thread runs cascade propagation after each contradiction
- Trust updates applied to affected downstream nodes (CASCADE_TRUST_FACTOR=0.3)
- Cascade metadata stored on ledger entries
- `[BDG]`, `[BDG_CASCADE]`, `[BDG_CASCADE_TRUST]` logging

## Provisional Authority Gate (PRODUCTION)
New user assertions stored as `authority=provisional`, excluded from retrieval, promoted to `confirmed` after contradiction detection passes. Prevents same-turn self-citation.
- crt_rag.py: assertion stored as provisional
- crt_memory.py: `exclude_authorities={"provisional"}` in retrieve_memories
- crt_rag.py: promoted after contradiction check passes
- routes/chat.py: slot_exclusivity demotion blocked when provisional memory exists

## System Integrity Fixes (PRODUCTION)
1. **Time awareness**: Current datetime injected into system prompt (routes/chat.py)
2. **last_accessed/last_updated**: New columns, updated on retrieval and trust change (crt_memory.py)
3. **Profile trust gate**: Blocks profile update when high-trust memory disagrees (crt_rag.py)
4. **Stop auto-resolving**: Removed profile_sync_audit auto-resolve, contradictions stay OPEN (crt_rag.py)
5. **Real memory IDs**: Profile contradictions look up actual memory_id from memory_facts (crt_rag.py)
6. **Retrieval prefix stripping**: "Aether," stripped before embedding query (crt_memory.py)

## Bug Fixes
- `_logger` typo in crt_ledger.py update_contradiction_metadata
- NLI critic hard_fail on conversational messages (confidence=0.0 with no contradictions → PASS)
- Profile gate logs OPEN contradictions when blocked
- `[PIPELINE_ENTRY]` logging added for generation mode visibility
- Orange memory trust restored after demotion damage

## Cookie-Opus Orchestrator (NEW)
Built `personal_agent/cookie_orchestrator.py`:
- **Provider abstraction**: `BrainProvider` base class with `CookieBrain`, `AnthropicBrain`, `OpenAIBrain`, `OllamaBrain`
- **Factory**: `get_brain("cookie")` returns the right provider
- **Orchestrator class**: Brain-agnostic loop — context → JSON decision → tool execution → repeat
- **7 tools**: file_read, file_write (sandboxed), dir_list, search_code, memory_recall, web_search, shell_exec
- **Sandbox**: file_write only in `D:/AI_round2/workspace/`, dangerous shell commands blocked
- **Retry logic**: Up to 3 retries on empty/timeout cookie responses

### Proven capabilities:
- File read + structured JSON analysis
- Memory recall + trust score reasoning
- Multi-step filesystem navigation
- Code writing from mathematical theorems (first-try correct)
- Full debug loop (read → identify bugs → fix → execute → verify)
- Multi-turn conversation continuity

### Wired into pipeline:
- routes/chat.py: orchestrator path added after agent loop gate
- Keyword detection for tool-needing queries classified as conversational
- History loaded from session DB before run, response stored after
- SSE events mapped: thinking → agent_thinking_token, tool_call → tool_start+tool_result, response → token

## Known Issues (carry forward)
- **Cookie session flapping**: Empty responses occasionally, retry handles most cases
- **Keyword-based orchestrator routing**: Hack for testing, needs real intent classification
- **helloworld.txt in project root**: file_write through agent loop (not orchestrator) isn't sandboxed
- **NLI hard_fail on new threads**: First message sometimes triggers false contradiction disclosure
- **Profile ↔ memory drift**: Profile DB still has stale values, trust gate blocks updates but doesn't fix historical data
- **PATCH storm on startup**: Still present
- **Governance OpenAI waste**: Slot classifier still calls OpenAI on every message
- **Stale "Nick works third shift"**: Never corrected

## Architecture State
- Cookie Opus = brain (planning, reasoning, decisions via JSON)
- GPT-4o-mini = cheap tool executor (existing agent loop, function calling)
- llama3.2 = intent routing (unreliable, needs replacement)
- Cloud Claude = response generation (conversational path)
- Local Ollama = fallback generation

## Orchestrator Refinements (Late Session)
- **Code fence parser fix**: Backticks inside JSON content (markdown code blocks) were matched as code fence wrappers, destroying the JSON. Fix: only strip fences that start at beginning of response (`text.startswith`)
- **Literal newline fix**: Cookie SSE parser delivers literal newlines in long content. Fix: `chr(10)` → `chr(92)+chr(110)` replacement before JSON parse
- **Shell cwd fix**: Read-only commands (cat, head, grep, sed) now run from PROJECT_ROOT, write commands from SANDBOX_DIR
- **Time pressure**: Orchestrator warns Cookie when nearing iteration limit, forcing a response
- **Retry logic**: Up to 3 retries on empty/timeout Cookie responses
- **File read limit**: Bumped to 30k chars

## Code Intelligence Agent
Built `personal_agent/code_intel.py` with 4 modes:
- **file_map**: Full class/method map with line numbers, params, dependencies (tested on crt_critic.py — 7 iterations, 68s)
- **trace**: Find all callers/callees across codebase (tested update_trust — found 5 callers across 2 files)
- **detect**: Bug detection (found 5 real issues in crt_critic.py: swallowed exception, broad catches, lazy load, O(n²), dead import)
- **full_audit**: Combines map + trace + detect

Chat.py stress test: Orchestrator navigated 6,883-line file using grep+sed, wrote 1,815-char audit to workspace/chat_audit.md. Identified 4 endpoints, full request flow, generation modes, memory hooks, flagged monolith as #1 concern.

## Next Session: CRT-Governed Agent Execution
**THE BIG IDEA**: Apply CRT to the orchestrator loop itself. Not code validation — belief validation on agent behavior.

### What to build:
1. **Intent as belief**: Store the user's objective as a provisional belief. Track confidence.
2. **Step alignment check**: Before each tool call, verify it aligns with the stored intent.
3. **Step contradiction check**: After each result, check if it contradicts any prior step's conclusions.
4. **Verification tracking**: Did the agent actually verify its work? (ran code, checked output, etc.)
5. **Completion calibration**: Agent's claimed confidence vs actual outcome.
6. **Persistent intent log**: Runs persist — partial completions resumable.

### What to measure:
- Drift rate per task type
- Verification gap (claimed done vs actually verified)
- Contradiction patterns between steps
- Completion calibration (agent confidence vs user satisfaction)
- Which reasoning patterns produce stable vs fragile execution

### The thesis:
The agent develops **self-model beliefs about its own execution patterns** through earned trust, not hardcoding. After N runs: "I drift on long code tasks, I under-verify, I'm overconfident about completion — here's the evidence." First formal epistemic model of agentic behavior. Publishable.

### Key architectural decision:
**Don't split chat and coding**. Cookie is the only brain for everything. Simple messages → Cookie responds directly (~3s). Complex tasks → Cookie enters the CRT-governed tool loop. No separate intent router needed — Cookie IS the router.

## Layer 1: Run Log Measurement (SHIPPED)
Built `personal_agent/agent_run_log.py`:
- **RunLog** dataclass: captures intent, steps, drift events, verification, completion, timing, tool usage
- **RunStep** dataclass: per-step action, tool, args, reasoning, result, verification flag, alignment score
- **DriftEvent** dataclass: when agent changes direction without reasoning
- **RunLogDB**: SQLite persistence to `personal_agent/agent_runs.db`
- **Analytics**: success rate, avg iterations, drift rate, verification rate, tool frequency, confidence calibration

Wired into orchestrator — every run auto-captured. Tested with 4 runs:
- 100% success rate, 0% drift, 8.3% verification rate
- Avg 2.2 iterations, 9s total, brain dominates (8.99s vs 8ms tools)
- Verification heuristic: detects file_read-after-file_write, shell_exec with test runners, search_code after write, dir_list after write

### Key Insight: Epistemic Intent Routing
Run log data can replace heuristic intent routing with earned beliefs:
- After N runs, the system knows "messages with 'read' + file path → needs tools 95%"
- Confidence calibration: "when I say 0.9, actual success is 0.6" = belief/speech gap for agent behavior
- Tool selection becomes trust-weighted: "verify after write → 95% success vs 60% without"
- The same CRT framework for memory trust applies to routing/execution patterns
- No fine-tuning needed — beliefs earned through evidence accumulation

### Roadmap:
1. ~~Layer 1: Measurement~~ (DONE — RunLog, SQLite, analytics)
2. ~~Layer 2: Alignment scoring~~ (DONE — cosine sim intent vs reasoning, live drift warnings)
3. ~~Layer 3: Contradiction detection~~ (DONE — live: double file write, same-tool failure. Post-run: reasoning similarity + conflicting outcomes)
4. Layer 4: Epistemic routing (needs 50+ runs for meaningful patterns)
5. Layer 5: Self-model beliefs ("I under-verify, I drift on long tasks")
6. Cookie as sole brain (remove intent router entirely)
7. Telegram channel (same pipeline, captures cross-channel data)

## Files Modified This Session
- `papers/cascade_complexity/cascade_paper.md` — math fixes + real data sections
- `papers/cascade_complexity/real_bdg.py` — NEW: production BDG analysis
- `papers/cascade_complexity/damping_analysis.py` — NEW: generated by orchestrator
- `personal_agent/memory_graph.py` — BeliefDependencyGraph + LiveBDG + SUPPORTS edge
- `personal_agent/crt_rag.py` — cascade wiring, provisional gate, profile trust gate, auto-resolve removal
- `personal_agent/crt_memory.py` — last_accessed/updated columns, prefix stripping, BDG notify
- `personal_agent/crt_ledger.py` — _logger typo fix
- `personal_agent/crt_critic.py` — NLI hard_fail fix
- `personal_agent/cookie_orchestrator.py` — NEW: orchestrator + provider abstraction
- `personal_agent/test_orchestrator.py` — NEW: test harness
- `personal_agent/code_intel.py` — NEW: code intelligence agent (file_map, trace, detect, full_audit)
- `routes/chat.py` — pipeline entry logging, time awareness, provisional demotion block, orchestrator wiring, keyword gate
- `workspace/chat_audit.md` — generated: chat.py architecture audit
- `workspace/test.md` — generated: test markdown with code blocks
- `workspace/hello.txt` — generated: basic write test
- `workspace/lines.txt` — generated: multiline write test
