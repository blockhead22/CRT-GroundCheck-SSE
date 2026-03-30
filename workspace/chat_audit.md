# routes/chat.py Architecture Audit

## Endpoints (4)
| Line | Route | Purpose |
|------|-------|--------|
| 2169 | POST /send | Main chat handler |
| 4926 | POST /stream | Streaming variant |
| 6604 | POST /intent | Intent classification |
| 6724 | POST /feedback | User feedback |

## Request Flow
1. **Auth** → resolve_user_id from header, set `_request_user_id` context
2. **Classify** → Pattern-match into request_kind (meta_provenance, architecture_explanation, contradiction_inventory, etc.)
3. **Delegate Check** → `should_delegate_to_openclaw()` for agentic tasks
4. **Engine Query** → CRT engine processes with gates_passed/gate_reason tracking
5. **Response Build** → `_build_final_response()` with control_state metadata

## Generation Modes
- `cloud_openai` (default) - Remote LLM via litellm_client
- `local_ollama` - Local inference
- `deterministic` - No LLM, pattern-match + data lookup (<500ms target)

## Memory Hooks
- `episodic_memory.get_episodic_manager()` - Preference/verbosity retrieval
- `memory_bridge.sync_groundcheck_to_memory()` - GroundCheck→memory sync
- `crt_memory._request_user_id` - Context var for write attribution
- `GovernanceLayer` - Tiered access control (imported conditionally)

## Decision Points
- ~20 `_is_*_request()` classifiers via regex patterns
- Openclaw delegation gate (lines 2392-2430)
- Gates passed/failed propagated through response metadata

## Top 3 Code Quality Concerns
1. **Monolith** - 6883 lines, single file mixes routing/business logic/LLM dispatch/memory
2. **Complexity** - 866 conditional/exception blocks; high cyclomatic complexity
3. **Regex sprawl** - Request classification via 20+ compiled regex patterns (lines 800-1400) - brittle, hard to test

*Recommendation: Extract classifiers, LLM dispatch, and memory ops into separate modules.*