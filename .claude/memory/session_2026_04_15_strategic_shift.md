---
name: session_2026_04_15_strategic_shift
description: Strategic shift day — drop the shell, focus the substrate. MCP service shipped. Three converging framings, roadmap, and TPU priorities for the limited window.
type: session
date: 2026-04-15
originSessionId: 687eb415-8a05-49fd-922f-f876d7150297
---
# Session 2026-04-15: The Shift

Coffee-shop carry document. Working notes, not pitch deck.

---

## What happened today

1. **Identified the actual waste.** Re-discovery of the codebase every session is ~40% of token spend. Politeness tokens are a rounding error. Rebuilding mental models from scratch every morning is the real fuel sink.

2. **Shipped the MCP server with 32 tools.** Merged `aether_mcp_server.py` + `crt_mcp_server.py` into one. Added 7 differentiator tools that nobody else exposes:
   - `aether_fidelity` (grade a draft against belief state)
   - `aether_lineage` (why do I believe this)
   - `aether_cascade_preview` (dry-run a trust change)
   - `aether_session_diff` (what changed since last connect)
   - `aether_done_shape` (suggest success/absence criteria for a task)
   - `aether_done_check` (validate response against criteria)
   - `aether_sanction` (pre-action governance gate)

3. **Made the strategic call: drop the shell.** The Electron app, the harness work, the desktop UX — stays as personal tool, not product. Cannot win against Claude Code / Cursor on shell features. The substrate is the differentiated layer.

4. **Surfaced three converging framings** for the same infrastructure underneath. Same code, three different audiences and pitches.

---

## The Shift (one paragraph)

Stop competing on the shell. Stop spiraling on UI. The substrate is where a year of work compounds — contradiction math, BDG cascade, fidelity scoring, done-shape, trust evolution, belief backprop. As "an IDE/desktop AI assistant" all that work reads as one person trying to outship a 100-engineer team. As "the persistent epistemic substrate AI tools should be reporting to" the same work reads as differentiated infrastructure that nobody else is building. Same code. Different framing. Different game.

---

## Three Framings (all sell the same thing)

### Framing 1: Substrate (the developer pitch)
> Aether is a persistent, contradiction-aware belief substrate that lives between your AI tools and the world. It's the thing your AI tools should be reporting to and asking permission from — not a memory store they fetch from.

Audience: developers, MCP-aware tool builders. Pitch: "your AI tools forget every session. We don't."

### Framing 2: PM Substrate (the buyer pitch)
> Aether validates work product against declared "done" criteria, distinguishing claimed-done from validated-done. Tasks marked done that fail validation are surfaced with the specific gap, not a status field.

Audience: engineering managers, team leads, ops. Pitch: "30% of your team's done tasks aren't actually done. We catch them."

Differentiator over Linear/Asana: epistemic backing. Existing PM tools are Trello with extra fields. Aether knows whether the work happened, not just whether the checkbox got clicked. Plus assignees are first-class regardless of human-or-agent.

### Framing 3: Composable Substrates (the protocol pitch)
> Aether is the protocol layer for AI epistemic state across teams and tools. Personal substrate, project substrate, company substrate, community substrate. Federation. Each scope owns its beliefs; clients query across scopes.

Audience: companies, dev tool vendors, eventually a standards body. Pitch: "the standard nobody else can ship — Anthropic is a model vendor, not a neutral protocol layer."

---

## MCP Service: Where it stands

**Live and working** (as of today):
- 32 tools registered in FastMCP
- Backend wraps `crt_api.py` (HTTP) + direct module imports (no API)
- Both `aether_*` and `crt_*` tools in one server
- Registered with Claude Desktop via `claude_desktop_config.json` (after debugging — initial registration in `.claude/settings.json` was wrong location)
- Console script `crt-mcp` still works via shim

**What's missing for production-shippable v1:**
- `pip install aether-mcp` (PyPI publish)
- `aether init` CLI that auto-detects Claude Desktop / VS Code / Cursor and patches their MCP configs
- README that pitches substrate (not memory-MCP)
- First-call experience on empty memory store (currently `aether_search` returns nothing useful)
- Auto-start of backend when MCP server starts (right now requires `npm start` separately)

**Known weakness shipped intentionally:**
- `done_shape` is regex heuristics with documented LLM-fallback as next step
- `done_check` uses cosine+keyword hybrid that under-scores abstract criteria
- Both are good enough to validate the architecture; both want a small trained classifier (TPU job)

---

## Roadmap

### Next 7 days (with limited TPU window)
**Train the highest-leverage small classifiers on TPU.** See TPU section below.

### Next 30 days (substrate v1 ship)
1. **Rediscovery savings lab** — run real comparison: Cold sessions vs Warm (Aether-attached) sessions. Measure tokens, tool calls, time, correctness. Need this chart for any pitch.
2. **PyPI package + `aether init`** — `pip install aether-mcp && aether init` should be a one-liner that lands working tools in Claude Desktop / VS Code / Cursor.
3. **Substrate-positioned README** — "the persistent belief layer your AI tools were missing" — not "another memory MCP."
4. **Empty-state UX** — when memory store is fresh, surface the right onboarding tools to the connected agent so the first interaction feels smart.

### Next 60 days (proof + adoption)
5. **Lab writeup as paper or blog post.** "We measured what AI tools waste rebuilding context." Publish the chart.
6. **Get 5 outside developers to install and use it for a week.** Watch which tools they actually call. Ship signal-driven improvements.
7. **Composable substrates v0** — at least personal + project. The repo can have its own `.aether/` substrate that travels with the codebase.

### Next 90 days (PM substrate or pivot)
8. **Decision point: PM substrate.** If the dev-tool angle has 50+ stars and active feedback, double down on devs. If it's tepid and the PM scenarios resonate when shown to actual engineering managers, pivot to that pitch.
9. **Multi-substrate composition.** Federation across personal/project/company. Auth model. Trust composition policy.

---

## TPU Priorities (only a few days available)

Limited window. Train the things that unblock the substrate's intelligence — every place we currently fake it with regex/heuristic is a candidate. Pick by leverage.

**Tier 1 — must do (highest leverage, smallest model, fastest win):**
1. **Done-check classifier.** `(criterion_text, evidence_text) → filled probability`. Replaces the broken cosine+keyword hybrid. Gates the validation story for the PM substrate. Synthetic + labeled training data. ~30M params is plenty. Probably ~1 day of TPU.

**Tier 2 — high value if time:**
2. **Done-shape classifier.** `task_text → (task_type, success_criteria, absence_criteria)`. Replaces regex heuristics. Calibrated confidence. Trains on labeled examples + synthetic generation from existing 7 patterns expanded to ~30. ~1 day TPU.
3. **Domain-specific embedding fine-tune.** Take MiniLM or BGE base, fine-tune on Nick's corpus + corrections. Better recall, better contradiction adjacency. ~1 day TPU. Improves *every* retrieval-driven tool downstream — multiplier effect.

**Tier 3 — defer unless unexpected time:**
4. Contradiction NLI (currently regex slot extraction + critic).
5. Risk classifier for sanction (currently hardcoded verb lists).
6. Continuation of Phi-3 variance/intent work from session_2026_04_09.

**If only one job runs:** done-check classifier. Period. It's the bottleneck on the validation story, which is the bottleneck on the PM pitch, which is the most concrete buyer-facing wedge.

---

## Open questions to think about at the coffee shop

1. **Which framing leads?** Substrate (dev-tool) is fastest to ship and easiest to demo. PM is the bigger market and clearer buyer. Composable is the longest-horizon moat. Probably lead with substrate, surface PM as a use case once devs are using it. But test the order with 3 trusted humans before committing.

2. **Is the rediscovery-savings number actually big?** Whole pitch leans on this. If Cold vs Warm is only 20% reduction, the dev-tool angle is weaker. If it's 60%+, undeniable. Run the lab before assuming.

3. **What's the smallest possible "first user not Nick"?** One outside dev, installed via pip, used Aether for a week, gives honest feedback. Without that signal, every framing is a hypothesis. With it, the roadmap writes itself.

4. **PM substrate prerequisite question:** does the team substrate need a UI, or can it be CLI + agents-only for v0? The honest answer is probably "needs a thin UI for assignees who aren't devs." Which loops back to the shell question — but for *this* shell, the audience is the PM, not the IDE user. Different game.

5. **What does "Aether for myself" look like in 6 months?** The personal orchestrator that calls/routes between other AIs. Allowed budget. But: should it be MCP-server-driven (clients call it) or standalone (it calls them)? Probably standalone — that's the personal-orchestrator angle. Different shape from the substrate-as-product.

---

## What NOT to do

- Don't polish the Electron app today.
- Don't add more orchestrator features to cookie_orchestrator.py before the substrate ships.
- Don't rebuild the frontend.
- Don't write more `.md` files about why the substrate matters. Build the chart instead.
- Don't ship multi-substrate composition before single-substrate has actual users.
- Don't train the wrong classifier first. Done-check, then done-shape, then embedding. In that order.

---

## One-line carry

> The substrate is the moat. Drop the shell. Train one classifier this week. Run the rediscovery lab. Ship `pip install aether-mcp` next month. Watch what happens.
