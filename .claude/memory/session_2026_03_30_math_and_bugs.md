# Session 2026-03-30: Math Audit + Bug Sprint

## Math Topics (CONTINUE NEXT SESSION)

### Cascade Paper Audit — specific gaps found
Full paper read. Problem audit by theorem:

**Tight / clean:**
- Theorem 4.1 (Depth Bound): correct, tightness example assumes impact-preserving function (state explicitly)
- Theorem 4.2 (Width): correct result, proof counts paths not nodes — fix argument, O(min(d^k, n)) survives
- Proposition 5.1, 5.2, 5.3: all clean

**Has real gaps:**
- Theorem 4.3 (Convergence): multi-parent impact aggregation is UNDEFINED in Definition 3.5. If impacts sum (vs max), geometric decay breaks. Proof only works for single-path propagation. Also: ρ = L·w_max is not a spectral radius — DeGroot analogy is suggestive, not formal.
- Theorem 4.4 (Instability): MAJOR CONTRADICTION — Definition 3.5 defines C(r) as a SET (no re-visitation). Instability proof requires cycle re-traversal (k traversals). These are incompatible. Fix: reframe instability as property of *iterated* cascades, not a single cascade event.
- Conjecture 4.5 (NP-hardness): Paper uses Minimum Weighted Vertex Cover reduction (wrong direction/encoding). np_hardness_proof.md appendix uses MLA (more promising but incomplete). Paper and appendix are inconsistent — pick one.
- Proposition 5.4 (Fisher Priority): Submodularity asserted not proven. Greedy (1-1/e) approximation applies to maximization, not minimization. "Proof sketch" is fake.

**Priority fixes before submission:**
1. Theorem 4.4 — reframe as iterated cascades
2. Definition 3.5 — add one line specifying multi-parent impact aggregation (max vs sum)
3. Proposition 5.4 — demote to Conjecture or actually prove it
4. Conjecture 4.5 — pick MLA (appendix) over vertex cover (paper body), acknowledge as open

### Validation Discussion
- All paper empirical illustrations are CONSTRUCTED examples (circular — designed to fit formulas)
- Real validation: run cascade modules on production memory DB (604 memories in shared.db + contradiction ledger)
- Research modules (memory_splats.py, info_geometry.py, memory_graph.py, predictive_contradiction.py) exist in personal_agent/ but NOT wired into production (crt_api.py has zero imports)
- GPT/robustness data (Qwen3/Mistral/DeepSeek variance sweep) = validates immune agents paper, NOT cascade paper
- Cascade paper validation source = Aether's own production memory DB

### Key Insight: Math ↔ Production Pipeline Connection
The cascade math formalizes the existing simple/better contradiction pipeline:
- "Simple" (cosine 0.3-0.6 range check) → replaced by overlap integral (same role, richer geometry)
- "Better" (NLI confirmation) → unchanged, still the expensive accurate step
- New layer: CASCADE — after NLI confirms contradiction at node A, propagate to dependent nodes B/C/D (currently nothing does this in production)
- Predictive contradiction → overlap TREND over time, not static snapshot

### Research Modules Status
| Module | Claim | Production? | Reality |
|--------|-------|-------------|---------|
| memory_splats.py | Gaussian beliefs with uncertainty shape | No | Works standalone; sigma needs update loop to be useful |
| info_geometry.py | Fisher-Rao distance (3.16x validated) | No | Real improvement IF sigma values are meaningful |
| memory_graph.py | BDG with typed edges, cascade propagation | No | Actual production value — cascade on real memory graph |
| predictive_contradiction.py | Trajectory-based future conflict detection | No | Needs trajectory history that doesn't exist yet |

**Next session todo:** Play with connecting memory_graph.py to real production DB and running propagate_cascade() on a real revision event. Would give genuine empirical results for the paper.

---

## Bug Fixes Shipped This Session

### qwen3:14b → llama3.2 revert
- qwen3:14b OOMs on Mac M2 even at 4k context (kIOGPUCommandBufferCallbackErrorOutOfMemory)
- Reverted CRT_OLLAMA_MODEL and all model_roles in crt_runtime_config.json back to llama3.2
- num_ctx hardcoded 8192 → 4096 in both litellm_client.py paths (_build_local_params + _ollama_direct_tool_call)

### Intent pre-filter expansions
Added to _CONVERSATIONAL_PREFIXES in llm_intent_router.py:
- Memory-state questions: "what do you know about me", "who am i", "based on what you know", etc.
- Casual fact updates: "i sold ", "btw ", "fyi ", "just so you know", "oh and ", etc.
These prevent agent loop + web search from firing on personal memory questions and casual corrections.

### Route cache purged
- Cleared all desktop_action entries (re-poisoned by "I sold the minolta btw")

### Generation mode
- User switched to cloud_claude (claude-opus-4-5) via settings
- Local gen (llama3.2) still available as fallback when M2 is online

### Agent loop bypass for memory-only intents (routes/chat.py)
Added `_MEMORY_ONLY_INTENTS = {"broad_recall", "system_info", "inquiry_queue"}` exclusion to AGENT_LOOP_GATE condition. These intents now go straight to legacy path (direct memory retrieval) instead of the agent tool loop. Root cause: llama3.2 in the loop was calling web_search and shell_exec after getting memory results, contaminating answers with celebrity "Nick Block" results and trying to `ls -l /home/nick/Photography/`.

Also added pre-filter prefixes for:
- "list everything you know", "in a long response", "what about me personally"
- "i sold ", "btw ", "fyi ", "just so you know", "oh and ", etc. (casual corrections)

## Remaining Issues (carry forward)
- PATCH storm: 4x PATCH /api/auth/settings fires on startup — different source than number inputs (not yet identified)
- generation_source=unknown still appears in some paths
- Retrieval: "Aether, X" prefix not stripped before embedding query (causes "Aether, I'm tired" to score high for "Aether, what is important to you?")
- Governance slot classifier calls OpenAI on every message including confirmed-conversational (pre_filter) — wasted spend
- Stale memory: "Nick works third shift" never corrected (cookie Claude claimed to update without tool access)
