---
name: session_2026_04_12_docs_audit
description: Docs overhaul session - index redesign, full factual audit, terminology renames, whitepaper rewrite, roadmap set
type: project
---

## Session Summary (2-day session, April 12-13 2026)

### Index Redesign
- Hero: [AETEROS] bold caps, italic reverse-slant E, Montserrat font
- Tagline: "AI that remembers what it believes." (replaced "AI driven by meaning" - original was from June 2025 GPT logs)
- Belief/speech viz built (SVG waveform with glow/scanlines) then removed from hero (kept minimal)
- Ch1: cannabis/antidepressant case leads, tension before data
- Ch2: Origin - OG whitepaper quotes, CRT→CORE evolution, four original components
- Ch3: What Was Discovered - four failures, "Mirus became...", core thesis
- Ch4: Research - 6 paper cards including BRG scaffolds + scaffolded exploration
- Ch5: What's Running - prose, no stat boxes
- Ch6: Where It Goes - aeteros-core, governance-as-a-service
- Papers nav: BRG Reasoning Scaffolds + Scaffolded Exploration added to Evidence section

### CRT Name - GROUND TRUTH
- OG whitepaper PDF says **Cognitive-Reflective Transformer** (pages 2, 3, 6, 7)
- Nick initially said "Contradiction Reflective Transformer" - was his evolved memory, not the doc
- All docs now correct

### Whitepaper
- Full rewrite around framing: "set out to solve X, found Y along the way"
- Section-by-section OG whitepaper breakdown with Nick approving each piece
- DNNT: cut. CSR: absorbed (Aether is what CSR described)
- Whitepaper.html kept in docs but removed from nav - accessible by URL, not discoverable
- Nick wants a real PDF whitepaper eventually, not an HTML page

### Terminology Renames (ALL COMPLETE)
- **BDG → BRG** (Belief Relationship Graph) - 149 replacements, 18 files, zero BDG remaining
- **"Belief backpropagation" → "backward influence propagation"** - 9 files
- **"Scaffolded Escape" → "Scaffolded Exploration"** - hero, title, nav, link text
- **5 → 6 immune agents** everywhere, ContinuityAuditor card added with full detail
- **CORE expansion**: "Contradiction-aware Reconciliation and Trust" → "Contradiction, Observation, Revision, Epistemics" (was wrong in 4 files)
- **crt-core → aeteros-core** in nick_paper + about
- **"heartbeat" → "reflection loop"** - 15 replacements, code refs preserved
- **"breathing loop/cycle" → "fidelity mirror"** - 14 replacements, nick_paper historical narrative preserved
- **HTML entities cleaned** - 460 replacements across 25 files (&mdash; &rarr; &ndash; etc)
- **EU AI Act**: Articles 13 + 50 both referenced correctly (13=high-risk auditability, 50=general transparency, both Aug 2026)

### Factual Audit (15 pages audited)
- **index.html** - rewrote, merged whitepaper
- **nick_paper.html** - 9→12 papers, 5→6 agents, crt-core→aeteros-core, Anthropic sandbox claim reframed provider-agnostic, 5 TODOs
- **about.html** - tagline fixed, numbers corrected, MemoryBench removed, university convergence claim removed, 6 TODOs
- **architecture.html** - immune agents corrected (names from codebase), 22,500 claim removed
- **experiments.html** - entities cleaned, 867 memory count removed, dead links fixed
- **immune-agents.html** - 5→6 throughout, ContinuityAuditor card added, all "five"→"six"
- **emotion-governance.html** - CORE expansion fixed, entities cleaned
- **belief-backprop.html** - renamed to backward influence propagation
- **bdg-reasoning-scaffolds.html** - BRG terminology note added, tree walk diagram added
- **glossary.html** - BRG entry updated, CORE expansion fixed, backward influence propagation updated
- **scaffolded_escape_research.html** - language toned down, "scaffold is the capability" section added, network data anonymized
- **continuity-blind.html** - CORE expansion fixed
- **structural-tension.html** - backward influence propagation renamed
- **epistemic-compression.html** - backward influence propagation renamed
- **cascade-complexity.html** - BRG renamed

Pages verified clean (no changes needed): sensitive-domains, cascade-viz, geometric-memory (content), labs, claim-evaluation-guide, variance-probing

### Scaffold Positioning
- Removed all Mythos/Anthropic references from security/capability claims
- Added "The Scaffold Is the Capability" section to scaffolded_escape_research.html
- nick_paper.html: Anthropic sandbox claim → provider-agnostic "frontier models are claiming..."
- index.html: "Anthropic has already identified" → "research has already identified inside frontier models"
- Position: capability lives in the scaffold architecture, not the model parameter count

### Graphics Added
- **geometric-memory.html**: 3 inline SVG diagrams (contradiction overlap, trust evolution states, variance-to-locus pipeline)
- **bdg-reasoning-scaffolds.html**: BRG tree walk diagram (root/branches/leaves with walker indicator)
- **index.html**: belief/speech divergence viz (built then removed from hero for minimal design)
- Hero SVG labels in geometric-memory fixed (were black on dark background, no CSS classes defined)

### Network Data Anonymized
- scaffolded_escape_research.html: all real IPs (192.168.1.x) → 10.0.0.x
- All hostnames anonymized (nickpc→workstation, debra→device-a, nickstv→smarttv, etc)
- Printer model, ISP router model, garage door brand removed
- Docker internal IPs kept (172.17.0.1, 192.168.65.254 - standard defaults)

### Pages Removed/Moved
- why-this-matters.html: restored to docs/ but not in nav (accessible by direct URL)
- claim-evaluation-guide.html: same
- whitepaper.html: same
- _drafts and _private folders cleaned up

### Deploy Infrastructure
- All deploys via `wrangler pages deploy docs/ --project-name=aeteros-research --commit-dirty=true --skip-caching`
- docs.js: Cloudflare clean URL fix (appends .html for nav active state matching)
- base.css: Montserrat font added for hero h1

### Project Board Updated
- **184 done / 39 planned / 14 cold** (was 167/29/14)
- 17 done cards added for this session's work
- 10 planned cards added for roadmap
- BDG→BRG title updated

### Roadmap (New Planned Cards)
| Priority | Card | Project |
|----------|------|---------|
| Urgent | EU AI Act compliance case | business |
| High | Pipeline latency optimization (1.5s→300ms) | aether |
| High | Epistemic motivation prototype | research |
| High | Wire gravity into reflection loop | aether |
| High | Tier 3 governance validation (head-to-head) | research |
| High | Real whitepaper PDF | docs |
| Medium | CogniMap compression product | crt-core |
| Medium | Immune agent ablation study | research |
| Medium | TPU compute: Phi-3 adapter transfer | research |
| Low | Direct emotion vector measurement | research |

### TPU Research Cloud Access
- Google project "aeteros" approved for 30-day free TPU access
- 64x v6e (spot), 64x v5e (spot), 32x v4 (spot+on-demand)
- Priority use: Tier 3 validation at scale (governed vs ungoverned head-to-head)
- Secondary: fine-tune contradiction detector on labeled data, variance probing on more model families

### Competitive Landscape (Discord Observations)
- "Epistemic" is having a moment on Claude Discord
- Everyone building at prompt layer (.md files, system prompts telling Claude to be epistemically careful)
- Nobody building at infrastructure layer (persistent belief state, contradiction tracking, governance)
- Dustinspace: prompt engineering. Ballernovsky: dialogue analysis. Clement: agent orchestration. SirBubbles: reasoning frameworks
- None have: persistent belief state, trust evolution, immune agents, backward influence propagation, production system running 12+ months
- Key insight from Nick: "no one is doing a governed harness with epistemic backbone"

### Key Discussion: Coding Validator Walker
- Same BRG walk mechanism applied to code validation
- Three applications of same architecture: inward (reflection loop), outward (scaffolded exploration), at code (validation walker)
- Main agent generates code + logs intent, walker validates assumptions against actual code
- Maps to 7 categories of non-logic coding problems (resource leaks, error handling, security surfaces, state inconsistency, config drift, API contract violations, silent degradation)
- NOT BUILT YET - future work item

### Key Discussion: Scaffold Security Position
- Frontier model security claims (Mythos etc) attribute capability to the model
- Research shows capability lives in the scaffold/harness
- Real attack surface: persistent directed exploration of misconfigured infrastructure (exposed APIs, no-auth endpoints, IoT devices)
- "The industry gates the model. Nobody gates the scaffold."
- Ring doorbell discussion: same attack surface as everything else on LAN

### Stale Numbers Still Unresolved
- Memory count "867" → DB shows 79,271 rows but that's all entries, not curated beliefs. TODOs in place.
- Feature count "135+" → CHANGELOG shows ~84 major features. Unresolved.
- Both need Nick to decide what number to use

### Git
- Commit cafe85c: initial index redesign
- Commit 2f46970: day 1 consolidation  
- Commit 346b038: day 1 final (scaffold cards, entities, nav links)
- Commit c155a58: day 2 full (BRG rename, backward influence, graphics, anonymization, all terminology)
- All pushed to origin/main
