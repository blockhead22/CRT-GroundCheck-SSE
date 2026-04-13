"""personal_agent.crt_rag — CRT-Enhanced RAG Engine (split package).

The public API is unchanged: ``from personal_agent.crt_rag import CRTEnhancedRAG``
continues to work.  Internally the monolith is split into delegate modules.
"""

from ._engine import CRTEnhancedRAG  # noqa: F401

# Re-export symbols that external code imports from personal_agent.crt_rag
from ._engine import (  # noqa: F401
    MemorySource,
    get_runtime_config,
    _build_gate_explanation,
    _sanitize_identity_pronouns,
    _fisher_rerank,
    _IDENTITY_PRONOUN_FIXES,
    _NL_RESOLUTION_STOPWORDS,
    _UNSTRUCTURED_SLOT_NAME,
    RESOLVED_CONTRADICTION_CONFIDENCE,
    SSE_CONTRADICTION_RESULT,
    _EXTRACTION_STOPWORDS,
    LONGFORM_SUMMARY_MIN_CHARS,
    LONGFORM_SUMMARY_MAX_CHARS,
)
