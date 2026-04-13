"""routes.chat — chat API package.

Split from the monolithic routes/chat.py into submodules:
    _constants.py      — module-level state, compiled regexes, pattern tuples
    _pipeline.py       — pipeline status/event emission, ResponseControlState
    _history.py        — history/continuity/follow-up functions
    _personal_facts.py — fact slot extraction and provenance
    _introspection.py  — self-referential, reflection, broad recall
    _expansion.py      — response expansion/continuation
    _preferences.py    — mood, verbosity, formatting, confirmation
    _special.py        — web search, architecture, workplan, docs, MCP, feedback
    _routing.py        — model selection, capability rerouting
    _governance.py     — local-only mode, cloud governance, bridge sync
    _endpoints.py      — the 4 API endpoints (send, stream, intent, feedback)
"""

# The router is the only thing external code needs at package level
from ._endpoints import router  # noqa: F401

# Re-export commonly accessed internals for backward compatibility
# (code that did `from routes.chat import _pipeline_event_queue` etc.)
from ._constants import (  # noqa: F401
    _pipeline_status_queue,
    _pipeline_event_queue,
    _EXPAND_TRIGGERS,
    _CONTINUITY_FOLLOWUP_HINTS,
    _PENDING_FOLLOWUP_SHORTCUTS,
    _GROUNDCHECK_BRIDGE_LOCK,
    _GROUNDCHECK_BRIDGE_LAST_SYNC,
    _TASKING_INTERVAL_SECONDS,
    _TASKING_LAST_RUN,
    _TASKING_LOCK,
    _CONTRADICTION_CAVEAT_RE,
)

from ._pipeline import (  # noqa: F401
    _safe_print,
    _emit_pipeline_status,
    _emit_pipeline_event,
    ResponseControlState,
    _control_status_lines,
    _env_bool,
    _answer_has_contradiction_caveat,
)

from ._history import (  # noqa: F401
    _load_recent_history_messages,
    _looks_like_follow_up,
    _augment_query_with_continuity,
    _augment_query_with_pending_followup,
    _history_answer_is_weak,
    _resolve_pending_followup_context,
    _resolve_personal_history_reference,
)

from ._personal_facts import (  # noqa: F401
    _is_meta_provenance_followup,
    _answer_recent_slot_provenance,
    _answer_personal_fact_bundle,
    _extract_personal_fact_bundle_slots,
)

from ._introspection import (  # noqa: F401
    _is_self_referential_question,
    _is_user_reflection_question,
    _is_broad_recall_request,
    _answer_self_referential,
    _answer_user_reflection,
    _answer_broad_recall,
)

from ._preferences import (  # noqa: F401
    _is_confirmation_yes,
    _is_confirmation_no,
)

from ._special import (  # noqa: F401
    _classify_and_store_feedback,
    _post_answer_quick_check,
    _build_loop_acknowledgment,
)

from ._governance import (  # noqa: F401
    _maybe_sync_groundcheck_bridge,
    _is_strict_local_only_mode,
    _is_cloud_governance_allowed,
)

from ._routing import (  # noqa: F401
    _capability_reroute,
    _route_model_for_request,
)

from ._endpoints import (  # noqa: F401
    chat_send,
    chat_stream,
    chat_intent,
    chat_feedback,
)
