# Aether GPT Archive Namespace Split Proposal

**Date:** 2026-07-09  
**Status:** Proposal (read-only research; no substrate / workbench.db mutation)  
**Corpus:** ChatGPT export  
`C:\Users\block\Downloads\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea`  
**Stance:** Results over purity theater. Personality risk accepted. Archive is evidence, not truth. Memories are earned.

---

## Summary (1 page)

Aether already knows how to treat GPT archive material as **review-only candidates** with role-separated authority (`user_claim_candidate` vs `assistant_interpretation_candidate`). What it does **not** yet do is give those candidates durable **namespace homes** so answers can be driven by edges and held tension instead of either (a) empty memory or (b) polluted `user:` slots and canned personal lore.

This proposal adds a three-way authority split:

| Namespace | What lives there | Authority | Answer weight |
| --- | --- | --- | ---: |
| `user:` | User-authored claims, prefs, beliefs | `user_stated` → confirm | Highest for personal facts |
| `gpt_inherited:` | Assistant-authored interpretations, inferred lore, GPT “memory” style claims | `assistant_inherited` | Low; never silent-overwrite of `user:` |
| `system:` | Aether self-model / self_tension / governance | system / operator | Meta answers only |

**Results-now path (dual mode):**

1. **Lab seed_provisional** — bulk-seed both namespaces from the dump into an isolated fixture substrate so Workbench/sidecar can answer with edges + tension **this week**. Provisional = queryable, marked low-trust, not production-confirmed.
2. **Production confirm** — same extractors, same candidates, but durable promotion only through Workbench review (existing archive import safety contract).

The dump is large enough to seed a real personal belief graph without months of live dogfood: **1,275 conversations**, **~96,980 messages**, roles ≈ assistant 42% / user 30% / tool 17% / system 12%. Prior body-aware probe already produced 30 user claim candidates + 10 assistant interpretation candidates from only 30 conversations. Open-claim extraction (`open_claims.py`) plus role split is the way to scale that without a closed slot phonebook and without hardcoding leukemia/orange.

**Hard rules that survive the personality risk:**

- Do **not** promote assistant invent into `user:` as truth.
- Do **not** hardcode medical or aesthetic lore (leukemia, orange-as-meaning, etc.).
- Do **not** collapse multi-value prefs into a single polluted string (`a problem. Dr. Pepper`).
- Do **not** auto-confirm health claims from archive.

**Why this proves the HTML/docs stack:** Mirus intake stays review-gated; Holden/fidelity-style rendering answers from governed evidence not GPT voice transplant; held disposition keeps multi-value and user/assistant tension open; slot-coverage/drift labs already proved closed extractors miss 95% of user turns and contaminate the 5% they see — so open claims + namespace authority is the product response, not more templates.

**One-week eng slice:** extend archive probe with namespace tagging → write provisional fixture under `aether-core/.eval-runs/` and `labs/` → wire answer path to prefer `user:` confirmed, then held multi-value, then `gpt_inherited` as “historical/assistant-view,” with edges and tension packets. Pass criteria below.

---

## 1. Dump facts

### 1.1 Source identity

| Field | Value |
| --- | --- |
| Export root | `...\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea` |
| Manifest | `export_manifest.json` v1; `export_files` ≈ 3,970 entries |
| Conversation shards | `conversations-000.json` … `conversations-012.json` (13 files) |
| Other | `chat.html` (~628 MB viewer), UUID conversation media folders, `file-*` attachments, `dalle-generations/` |
| Scan artifact (same path, dry-run) | `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_phase17.json` |

### 1.2 Quantitative sketch (actual dump scan)

Grounded in the dry-run scanner (`scripts/chatgpt_archive_scan.py`) against **this exact export path**. Message bodies were **not** ingested; counts walk `mapping` → `message` → `author.role` / `content.content_type` only.

| Metric | Count |
| --- | ---: |
| Conversation files | 13 |
| Conversations total | **1,275** (100×12 + 75 in `012`) |
| Mapping nodes | 98,255 |
| Messages (nodes with a message object) | **96,980** |
| Earliest create | 2025-02-27 |
| Latest update | 2026-03-27 |
| Flagged `is_archived` | 949 |

**Role distribution (messages):**

| Role | Count | Share |
| --- | ---: | ---: |
| `assistant` | 40,841 | 42.1% |
| `user` | 28,647 | 29.5% |
| `tool` | 16,151 | 16.7% |
| `system` | 11,341 | 11.7% |

**Content types (top):** `text` 71,194 · `tether_quote` 7,354 · `multimodal_text` 4,742 · `thoughts` 3,686 · `code` 3,164 · `reasoning_recap` 2,338 · `tether_browsing_display` 1,936 · `execution_output` 1,757 · `user_editable_context` 724.

**Models (conversations, top):** `gpt-4o` 643 · `gpt-5` 149 · `gpt-5-2` 149 · `gpt-5-2-thinking` 83 · plus o-series / mini variants.

**Title-category proxy buckets** (metadata only; not body truth):

| Category | Conversations |
| --- | ---: |
| uncategorized | 1,000 |
| aether_ai | 125 |
| coding_project | 63 |
| creative_voice | 28 |
| spiral_depth | 27 |
| personal_history | 26 |
| motivation_support | 15 |
| business_admin | 13 |

**Shard sizes (bytes):** 000≈58.5M · 001≈79.6M · 002≈89.2M · 003≈148.6M (largest) · 004≈46.9M · 005≈78.2M · 006≈36.8M · 007≈26.0M · 008≈10.9M · 009≈23.6M · 010≈26.0M · 011≈33.6M · 012≈21.4M.

### 1.3 Cross-check from corpus labs (same dump path)

| Lab | Finding | Path |
| --- | --- | --- |
| Slot coverage | ~**1,235** convs, **26,049** user turns; **94.92%** produce **zero** closed-slot tags | `docs/labs/slot-coverage-gpt-corpus.html` |
| Slot drift | Of the 5% that fire, many tags are contaminated (prose nouns / code identifiers as pets, locations, hobbies) | `docs/labs/slot-drift-gpt-corpus.html` |
| Body-aware fact probe (N=30 convs) | 30 user claims, 10 assistant interpretations, 30 assistant support styles, 11 contradictions/evolutions — all review-only | `.eval-runs/chatgpt_archive_fact_probe_20260625_*` |

Coverage lab conversation count is slightly lower than the full scan (1,235 vs 1,275) because the bench path filters empty / non-usable trees; both refer to this export.

### 1.4 Schema notes (ChatGPT export shape)

Top level of each shard: JSON **array of conversation objects**.

Per conversation (keys observed / used by scanners):

| Key | Role |
| --- | --- |
| `id` / `conversation_id` | Stable UUID for evidence receipts |
| `title` | Human title (category proxy only) |
| `create_time` / `update_time` | Unix epoch floats |
| `default_model_slug` / `model_slug` | Model label |
| `is_archived` / `is_starred` / `is_deleted` / `is_do_not_remember` | Flags |
| `mapping` | Dict of node_id → tree node |

Per mapping node:

```text
mapping[node_id] = {
  "id": ...,
  "parent": node_id | null,
  "children": [node_id, ...],
  "message": null | {
    "id": ...,
    "author": { "role": "user"|"assistant"|"tool"|"system", "name": ..., "metadata": ... },
    "content": {
      "content_type": "text"|...,
      "parts": [ str | multimodal objects, ... ]
    },
    "create_time": ...,
    "metadata": { ... }
  }
}
```

**Extraction rules for this proposal:**

- User candidates: `author.role == "user"` and `content.parts` text only.
- GPT-inherited candidates: `author.role == "assistant"`; **never** write to `user:`.
- Skip / low priority: `tool`, `system`, and non-text content types unless specifically mining code/project context.
- Evidence receipt always includes `conversation_id`, `title`, `message_id` (when present), `evidence_hash`, short preview — matching `archive_import.REQUIRED_CANDIDATE_FIELDS`.

### 1.5 Sample titles (illustrative from prior probes / categories)

Not exhaustive; shows domain mix for seed prioritization:

- Thread Assessment Deep Dive (spiral / correction language; Walmart two-weeks evolution)
- Aether / CRT / memory / governance project threads (`aether_ai` bucket)
- Motivation / confidence / walking support threads
- Client / hosting / business admin
- Creative / dork / voice play
- Personal history phrasing (sensitive; review-heavy)

Title is **never** enough to confirm a memory (`chatgpt_archive_scan` support candidates already enforce this).

---

## 2. Authority split table

### 2.1 Namespaces

Today (`aether/substrate/slots.py` `Namespace`): `user`, `code`, `session`, `project`, `meta`.  
Self-tension already surfaces as **`system:self_tension`** in sidecar / Mirus (`self_model.py`, `mirus_governed_discovery.py`, continuity handoff 2026-07-09).

**Proposed first-class personal/archive split:**

| Namespace | Source of claims | Authority labels | Trust band (provisional seed) | Can become confirmed fact? | Silent overwrite of others? |
| --- | --- | --- | --- | --- | --- |
| `user:` | User turns only; explicit self-statements | `user_stated` → after review `user_confirmed` | 0.55–0.95 after confirm; 0.35–0.55 provisional | Yes, via Memory confirm/correct | No (contradiction / held / supersedes only) |
| `gpt_inherited:` (alias display: `assistant:`) | Assistant turns; GPT memory-style summaries; interpretive “you seem…” | `assistant_inherited` / existing `assistant_inferred_low_authority`, `assistant_style_low_authority` | Cap ≤ 0.45 seed; ≤ 0.55 after human “useful reflection” accept | **No** as user profile fact. May become `system`/`project` reflection or support stance | **Never** writes into `user:` |
| `system:` | Aether self-model, self_tension, governance spine, operator policy | `system_self` / operator | Separate; not personal biography | Yes for self-model slots only | Never rewrites user biography |

**Naming recommendation:** store durable keys as `gpt_inherited:<label>` in substrate; expose UI label “Assistant / GPT inherited.” Keep `assistant:` as an accepted alias in query code for readability. Do not invent a fourth personal namespace in v1.

### 2.2 Candidate types mapped to namespaces

Extends existing `CANDIDATE_POLICIES` in `aether/sidecar/archive_import.py` (do not invent a parallel schema):

| Candidate type | source_role | authority (existing) | Target namespace | Durable route |
| --- | --- | --- | --- | --- |
| `user_claim_candidate` | user | `user_stated` | `user:` (slot or open label) | memory_confirm_or_correct |
| `project_context_candidate` | user | `user_stated_usage` | `user:` or `project:` | memory or reflection |
| `contradiction_or_evolution_candidate` | user | user_* | edges on `user:` (and vs `gpt_inherited:`) | memory_contradiction_review |
| `semantic_vocabulary_candidate` | user | `user_stated_usage` | support store (not belief fact) | support_pattern_review |
| `support_pattern_candidate` | user | `user_stated_usage` | support store | support_pattern_review |
| `assistant_interpretation_candidate` | assistant | `assistant_inferred_low_authority` | **`gpt_inherited:`** (not user) | reflection_review only |
| `assistant_support_response_candidate` | assistant | `assistant_style_low_authority` | support style draft / `gpt_inherited:` style nodes | support_pattern_review; never profile fact |

### 2.3 Edge model (cross-namespace)

Reuse / extend substrate edge vocabulary. Minimum set for archive seed:

| Edge rel | From → To | Meaning | Answer effect |
| --- | --- | --- | --- |
| `supports` | claim A → claim B | Evidence strengthens B | Raise stability of B when A is trusted |
| `tensions_with` | claim A ↔ claim B | Same topic, incompatible or multi-value friction | Held disposition; do not collapse |
| `alias_of` | open label ↔ slot | Same referent, different surface | Join retrieval without merging authority |
| `derived_from` | claim → evidence receipt / message | Provenance | Trace, not truth |
| `supersedes` | newer user claim → older user claim | Explicit correction | Prefer newer in `user:` only |
| `interprets` (new, optional) | `gpt_inherited` → `user` | Assistant gloss of user claim | Show as interpretation layer; never as fact |

**Overwrite law:**

```text
gpt_inherited never replaces user current state.
user can tensions_with or supersede other user states.
user vs gpt_inherited conflict => disposition=held, edge=tensions_with.
system:self_tension never stores personal medical/aesthetic lore.
```

### 2.4 Answer precedence (personality with guardrails)

When the user asks a personal question:

1. **Confirmed `user:`** states (highest).
2. **Held multi-value / multi-state `user:`** (render both; no single-winner polish).
3. **Provisional `user:`** seed (say “from archive candidate, not confirmed”).
4. **`gpt_inherited:`** (say “GPT/assistant previously framed it as… historical only”).
5. **Unknown** — ask / open claim, do not invent.

This is Holden-style fidelity: render what the graph holds, not what the model would invent about Nick.

---

## 3. Pipeline for results now

### 3.1 Recommended first-pass size

| Pass | Scope | Goal | ETA |
| --- | --- | --- | --- |
| **P0 smoke** | 30 conversations (already done spiral/support probe) | Schema + role split golden fixtures | Done / refresh |
| **P1 seed** | **150–250 conversations** prioritized by title keywords: aether_ai, personal_history, spiral_depth, motivation_support, favorite/identity language | Dense enough graph for dogfood answers | 1–2 days |
| **P2 bulk lab** | Full 1,275 conversations; user turns only for open claims; assistant sample cap (e.g. 2k assistant turns or keyword-gated) | Coverage stats + provisional fixture | 2–3 days |
| **P3 production review** | Same candidates, no bulk confirm | Workbench queue + human confirm | ongoing |

**Why not full assistant body extract on day 1:** 40k assistant messages are mostly code/help noise; keyword + reply-to-user-claim windows yield better `gpt_inherited` signal (matches fact_probe design).

### 3.2 Extract steps

```text
ChatGPT export
  -> load conversations-*.json (limit N)
  -> walk mapping; emit ArchiveMessage{role, text, conversation_id, title, create_time}
  -> branch by role
        user      -> open_claims.extract (labels induced, not closed phonebook)
                  -> also auto_ingest.extract_facts for high-precision slots (optional dual)
                  -> tag namespace=user, authority=user_stated, status=candidate
        assistant -> interpretation / style extractors (existing fact_probe signals)
                  -> tag namespace=gpt_inherited, authority=assistant_inherited, status=candidate
        tool/system -> skip or project-only later
  -> normalize via archive_import.normalize_archive_candidate
  -> build ClaimGraph edges: supports / tensions_with / derived_from / alias_of
  -> dual sink:
        seed_provisional -> isolated substrate fixture (lab)
        confirm queue   -> Workbench review packets (production)
```

**User path detail:** `aether/memory/open_claims.py` — multi-facet claims, multi-value split (Dr. Pepper + iced coffee), concern asides stripped from preference values. Status default `candidate`. No closed `user:cgvhd` registry.

**Assistant path detail:** reuse `chatgpt_archive_fact_probe.py` signals (`you seem`, `you tend`, interpretive language) and support structure. Cap confidence. Force `can_be_confirmed_fact_after_review=False` for profile facts (already true for `assistant_interpretation_candidate`).

### 3.3 Dual mode: seed_provisional vs confirm

| Mode | Who runs it | Writes | Trust | Use |
| --- | --- | --- | --- | --- |
| **seed_provisional** | Lab script into **temp** `.aether` / fixture JSON under `.eval-runs` or `labs/` | Provisional slot states + edges + evidence receipts | Low; `provisional=true`, `confirmed_fact=false` | Dogfood answers **now** with edges + tension; personality risk accepted |
| **confirm** | Human in Workbench Memory / Reflect | Durable confirmed only after accept | Normal trust ladder | Production substrate |

**seed_provisional safety contract (must encode in fixture metadata):**

```json
{
  "mode": "seed_provisional",
  "memory_write_allowed_on_live": false,
  "target": "isolated_fixture_only",
  "assistant_profile_facts_auto_confirmed": false,
  "user_namespace_from_user_role_only": true,
  "gpt_inherited_never_writes_user": true,
  "health_claims_auto_confirm": false,
  "batch_id_required": true
}
```

Note: existing `archive_bootstrap.py` `personal_fast_bootstrap` already auto-accepts some support/reflection paths and can write user slots from user_claim facts when fact extract succeeds. **This proposal treats that as too aggressive for production** but acceptable only on isolated fixtures if every write is tagged `source=archive_seed_provisional` and namespace-correct. Prefer **provisional states** over `correct_slot` confirmed semantics for lab seed.

### 3.4 Where results show up for “answers now”

1. Isolated substrate loaded by sidecar test harness / Workbench pointed at fixture dir.
2. Tension packet on personal questions: Side A = user provisional multi-value, Side B = gpt_inherited gloss, Forbidden collapse = single favorite drink string, Allowed synthesis = list + concern edge.
3. Direct recall path: confirmed user first; else provisional user with banner; else gpt_inherited framed as archive/assistant.

---

## 4. Anti-patterns (non-negotiable)

| Anti-pattern | Why it fails | Correct behavior |
| --- | --- | --- |
| Promote assistant invent as user truth | GPT “you seem…” and memory summaries become fake biography | Land in `gpt_inherited:` only; edge `interprets` / `tensions_with` |
| Hardcode leukemia / orange / medical lore | Personality theater; medical liability; breaks “memories earned” | If present in archive, **source-bound evidence + review**; never seed as confirmed; health = sensitive boundary (`AETHER_CURRENT_STATE` archive health fixes) |
| Collapse multi-value | `a problem. Dr. Pepper` pollution; lost iced coffee | Open multi-value claims; concern as separate claim; edge between them |
| Closed slot phonebook only | Slot coverage: 95% of user turns invisible | Open claims + optional slot alias |
| Title-only memory writes | Titles are not evidence | Title buckets = prioritization only |
| Bulk confirm into live `~/.aether` | Pollutes production the way favorite_drink did | Isolated fixture first; live only via review |
| Transplant GPT voice (Lumi/Nova/Holden style) as Aether identity | Already a v2 archive trap | Support style candidates ≠ identity truth |
| Auto medical advice from archive | Explicit dogfood boundary | Source-bound hits only; no path recommendations |

Documented pollution precedents (`AETHER_CURRENT_STATE`, mining pass):

- `user:favorite_drink = a problem. Dr. Pepper`
- `user:occupation = biggest flaw`
- Archive medical search overclaim / refusal composition bugs (fixed toward source-bound)

---

## 5. How this proves the HTML / docs stack

| Proposal piece | Docs / lab artifact | What it proves |
| --- | --- | --- |
| Role-separated extract | `archive_import.py` policies; mining pass 2026-07-01 | Archive → candidates, not memory |
| `user:` confirm ladder | `MEMORY_LIFECYCLE.md`; Mirus intake section of `AETHER_CURRENT_STATE` | Soft signals stay review-only until confirmation |
| Open claims / no phonebook | `open_claims.py`; `SLOT_DISCOVERY.md` (structure emerges) | Design law: no hardcoded life topics |
| Multi-value + concern edges | favorite_drink dogfood fixes; open_claims list split | Compression of prefs without pollution |
| `gpt_inherited` low authority | `assistant_interpretation_candidate`; architecture.html source authority | Holden fidelity: do not store model speech as user belief |
| Held disposition across namespaces | `structural-tension.html` (TENSION action = hold); disposition simplex | Contradiction as signal; firewall against premature resolve |
| Tension packet answers | governed synthesis / tension packet labs; `meaning-compression-crt.html` patterns; continuity tension-drive handoff | Render held sides, not flatten |
| Slot coverage / drift | `labs/slot-coverage-gpt-corpus.html`, `slot-drift-gpt-corpus.html` | Why closed extract + bulk ingest is false confidence |
| Contradiction pipeline | `labs/contradiction-pipeline-lab-latest.html` | Write-path detection needs better claims, not only templates |
| Geometric / Beta trust | `geometric-memory.html` | Provisional seed starts high variance; confirm earns tight trust |
| Belief synthesis later | `BELIEF_SYNTHESIS.md` | Thematic “who am I” from weighted graph, not one slot |
| System self model | `system:self_tension`; `self_model.py` | Clean separation: Aether’s tensions ≠ Nick’s biography |
| Archive as evidence | Away dogfood 2026-07-08; runplan lanes A/B/C | document_search + boundary language already product-shaped |
| Mirus belief map | `AETHER_MIRUS_BELIEF_MAP_LAB_2026-07-07` | Weighted nodes + support/contradiction edges + review proposals is the same graph this seed fills |

**CRT one-liner this implements:** archive intake is Mirus (measure + candidate); answer composition is Holden (fidelity render from evidence); unresolved multi-source personal facts stay **held tension**, not resolved fiction.

---

## 6. Immediate next eng steps (ordered, ~1 week)

| Day | Step | Script / artifact | Pass criteria |
| --- | ---: | --- | --- |
| 0 | Freeze dump path + re-run dry scan for 2026-07-09 stamp | `python scripts/chatgpt_archive_scan.py <export> --output .eval-runs/chatgpt_archive_scan_20260709.json --max-examples 5` | Counts match §1 within noise; 0 body ingest |
| 1 | Extend fact probe: emit `namespace` + `authority=assistant_inherited` field on each candidate; dual lists | `scripts/chatgpt_archive_fact_probe.py` (+ thin wrapper `scripts/chatgpt_archive_namespace_split_probe.py` if cleaner) | For every candidate: user→`user`, assistant→`gpt_inherited`; schema validates via `normalize_archive_candidate` (extend policy authorities if needed) |
| 1–2 | Open-claim pass on user turns only for P1 (150–250 convs) | New: `scripts/chatgpt_archive_open_claim_seed.py` writing `.eval-runs/namespace_split_open_claims_p1_20260709.json` | ≥ N user claims with multi-value preserved; 0 assistant text under `user:`; health-like labels flagged `sensitive=true` |
| 2 | Edge builder: same-label multi-value `tensions_with` or multi-state; user vs gpt_inherited `tensions_with` / `interprets`; `derived_from` evidence | Same seed script or `labs/namespace_split_graph_build.py` | Golden fixture includes Dr. Pepper + iced coffee style multi-value **without** `a problem.` collapse |
| 2–3 | **seed_provisional** into isolated substrate | `scripts/archive_namespace_seed_provisional.py` → `aether-core/.eval-runs/fixtures/namespace_split_substrate_20260709/` **or** `aether-core/labs/namespace_split/` | Fixture loads; live `~/.aether` untouched; every state has provenance batch_id |
| 3 | Answer-path smoke (TestClient / harness) | Reuse `sidecar_harness_dogfood.py` / `run_disposition_fixture_eval.py` patterns; new cases in `tests/` | Prompts: favorite drink → multi-value or review, not polluted single; medical archive → boundary; “what did GPT think about me?” → gpt_inherited framing |
| 4 | Wire tension packet for personal multi-source | Character/governance spine: Side A user, Side B gpt_inherited | `held_tension_score` style checks pass on 3 scripted cases; no silent memory writes |
| 4–5 | Production path remains review-only | Reuse `archive_import` review packets → Workbench | Confirm mode: 0 auto confirm on live; candidates appear in Memory/Reflect queues |
| 5 | Optional P2 bulk user-only open claims on full 1,275 | Same scripts, larger limit; output `.eval-runs/namespace_split_open_claims_full_20260709.json` | Coverage report: claims/turn rate >> 5% closed-slot rate; still 0 assistant in user |
| 5–7 | Dogfood pack | Extend archive_prompt_mining / away dogfood with namespace-aware expected routes | 0 writes; answers cite namespace; polluted-slot regression still green |

### 6.1 Recommended fixture / output paths

```text
D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260709.json
D:\AI_round2\aether-core\.eval-runs\namespace_split_open_claims_p1_20260709.json
D:\AI_round2\aether-core\.eval-runs\namespace_split_gpt_inherited_p1_20260709.json
D:\AI_round2\aether-core\.eval-runs\namespace_split_graph_p1_20260709.json
D:\AI_round2\aether-core\.eval-runs\fixtures\namespace_split_substrate_20260709\
D:\AI_round2\aether-core\labs\namespace_split\README.md          # only if eng wants; not required by this proposal
D:\AI_round2\labs\meaning_compression_lab\results\namespace_split_answer_smoke_20260709.json
```

### 6.2 Pass / fail bar (week end)

**Pass if all true:**

1. Isolated provisional substrate answers ≥3 personal probes using graph evidence (not empty, not canned leukemia/orange hardcode).
2. Zero assistant-origin claims under `user:` in fixture audit.
3. Multi-value preference case remains multi-value or held tension (not single collapsed string).
4. Live production substrate and `workbench.db` unchanged by seed scripts.
5. Existing archive dogfood / polluted-slot tests still pass.
6. Sensitive health candidates never `confirmed_fact=true` in provisional seed.

**Fail if any:**

- Assistant interpretation lands as confirmed user fact.
- Hardcoded personal lore appears in answer path without graph evidence.
- Seed script mutates `C:\Users\block\.aether\` by default.

### 6.3 Code touch list (minimal)

| Area | Change |
| --- | --- |
| `aether/substrate/slots.py` | Add `GPT_INHERITED = "gpt_inherited"` to `Namespace` (or accept string namespace without enum break) |
| `aether/sidecar/archive_import.py` | Allow `assistant_inherited` authority; attach `namespace` field on normalize |
| `aether/memory/open_claims.py` | Optional `source_namespace` meta; keep extract pure |
| `scripts/chatgpt_archive_fact_probe.py` | Emit namespace; optional open_claims merge for user |
| New seed script | Provisional apply to fixture only |
| Answer / meta / character | Precedence order §2.4 + tension packet sides |
| Tests | Namespace audit + multi-value + no live write |

---

## 7. Sample quantitative sketch (worked)

### 7.1 Full dump (metadata scan)

```text
conversations:     1,275
messages:         96,980
user:             28,647  (29.5%)
assistant:        40,841  (42.1%)
tool:             16,151  (16.7%)
system:           11,341  (11.7%)
span:             2025-02 → 2026-03
```

### 7.2 Closed-slot ceiling (same corpus, body lab)

```text
user turns scored:          26,049
zero slot tags:             24,725  (94.9%)
nonzero slot turns:          1,324  ( 5.1%)
=> closed phonebook alone cannot seed a belief substrate
```

### 7.3 Body-aware role-separated probe (N=30 conversations)

```text
user turns read:     220
assistant turns read: 220
user_claim_candidate:                 30
assistant_interpretation_candidate:   10
assistant_support_response_candidate: 30
semantic_vocabulary_candidate:        18
support_pattern_candidate:            11
project_context_candidate:            17
contradiction_or_evolution:           11  (in bootstrap report)
memory auto-accept from claims:        0  (bootstrap plan: facts not slot-matched)
```

**Linear extrapolation (order-of-magnitude only, not a promise):**

| Scale | User claim-ish candidates | Assistant interpretation-ish |
| --- | ---: | ---: |
| 30 conv (measured) | ~30 | ~10 |
| 200 conv P1 | ~100–250 | ~40–80 (keyword-gated) |
| 1,275 full + open claims | thousands of open labels; quality filter required | sample, don’t bulk |

Open claims will produce **more** raw candidates than slot extract; the win is recall. Precision comes from namespace tags, confidence caps, sensitive flags, and review/provisional status — not from pretending 95% empty is fine.

### 7.4 Pollution / multi-value sketch (known live failure modes to encode as fixtures)

| Input surface | Bad system behavior | Namespace-split target |
| --- | --- | --- |
| “My favorite drinks are a problem. Dr. Pepper and iced coffee” | `user:favorite_drink=a problem. Dr. Pepper` | two preference claims + concern claim; multi-state or multi-value |
| Assistant: “you seem drawn to orange because of …” | silent user: lore | `gpt_inherited:…` + `interprets` edge; held vs user favorite_color if any |
| Archive medical narrative | confirmed diagnosis memory | evidence receipt only; sensitive; no confirm |

---

## 8. Grounding references (do not reinvent)

| Document / code | Use |
| --- | --- |
| `docs/plans/AETHER_ARCHIVE_PROMPT_MINING_PASS_2026-07-01.md` | Candidate inventory, traps, medical boundary, Mirus/Holden prompts |
| `docs/plans/AETHER_ARCHIVE_PROMPT_PACK_RUNPLAN_2026-07-01.md` | Live vs isolated lanes; polluted slot expected behavior |
| `docs/plans/AETHER_CURRENT_STATE.md` | favorite_drink pollution, archive routing, Mirus confirm, health archive fixes |
| `docs/plans/AETHER_AWAY_DOGFOOD_ARCHIVE_PROMPTS_2026-07-08.md` | Read-only archive dogfood contract |
| `docs/MEMORY_LIFECYCLE.md` | Extract → trust → deprecation |
| `docs/BELIEF_SYNTHESIS.md` | Later synthesis over graph |
| `docs/SLOT_DISCOVERY.md` | Exclusive/additive/temporal without hardcode forever |
| `docs/labs/slot-coverage-gpt-corpus.html` | 95% blind closed extract |
| `docs/labs/slot-drift-gpt-corpus.html` | Contaminated 5% |
| `docs/labs/contradiction-pipeline-lab-latest.html` | Write-path contradiction chain |
| `docs/structural-tension.html` | Held tension as measurement |
| `docs/geometric-memory.html` | Uncertainty as structure; earned confidence |
| `docs/architecture.html` | Source authority; Holden fidelity mirror lineage |
| `aether/sidecar/archive_import.py` | Role/authority policies |
| `aether/sidecar/archive_bootstrap.py` | Bootstrap plan (use carefully; isolated only) |
| `aether/memory/open_claims.py` | Open multi-facet induction |
| `scripts/chatgpt_archive_scan.py` | Dry-run inventory |
| `scripts/chatgpt_archive_fact_probe.py` | Body-aware role split |
| `.eval-runs/chatgpt_archive_scan_20260624_phase17.json` | Dump counts for this export |
| `.eval-runs/chatgpt_archive_fact_probe_20260625_*.json` | Candidate examples |

---

## 9. Decision ask (for Nick)

1. **Accept `gpt_inherited` as first-class namespace** (not only reflection text in Workbench DB)? **Recommend: yes** — otherwise assistant invent keeps leaking into `user:` under pressure for “results now.”
2. **Accept seed_provisional isolated personality** for a week of dogfood (low trust, marked, edges-driven)? **Recommend: yes** — purity-only review queues will not fill answers this week.
3. **Reject** hardcoding medical/aesthetic lore even if it makes answers sound “deeper”? **Recommend: reject hardcode** — depth must come from earned edges.

---

## 10. Out of scope (this proposal)

- Mutating live `substrate.json` / `workbench.db`
- Full multimodal / audio transcript mining
- Automatic medical timeline construction
- Replacing Mirus review with auto-confirm
- Shipping GPT voice as Aether identity

---

*End of proposal. Read-write limited to this document only.*
