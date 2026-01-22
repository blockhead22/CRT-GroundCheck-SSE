"""GroundCheck - Verify that LLM outputs are grounded in retrieved context.

GroundCheck is a lightweight library for verifying that generated text from LLMs
is factually grounded in provided context/memories. It detects hallucinations by
extracting claims and checking if they are supported by retrieved information.

Example:
    >>> from groundcheck import GroundCheck, Memory
    >>> 
    >>> verifier = GroundCheck()
    >>> memories = [Memory(id="m1", text="User works at Microsoft")]
    >>> 
    >>> result = verifier.verify("You work at Amazon", memories)
    >>> print(result.passed)  # False
    >>> print(result.hallucinations)  # ["Amazon"]
"""

__version__ = "0.1.0"

from .types import Memory, VerificationReport, ExtractedFact
from .verifier import GroundCheck
from .fact_extractor import extract_fact_slots

# Neural extraction and semantic matching (optional)
try:
    from .neural_extractor import HybridFactExtractor, NeuralExtractionResult
    from .semantic_matcher import SemanticMatcher
    from .semantic_contradiction import SemanticContradictionDetector, ContradictionResult
    _NEURAL_AVAILABLE = True
except ImportError:
    _NEURAL_AVAILABLE = False
    HybridFactExtractor = None
    NeuralExtractionResult = None
    SemanticMatcher = None
    SemanticContradictionDetector = None
    ContradictionResult = None

__all__ = [
    "GroundCheck",
    "Memory",
    "VerificationReport",
    "ExtractedFact",
    "extract_fact_slots",
    "HybridFactExtractor",
    "NeuralExtractionResult",
    "SemanticMatcher",
    "SemanticContradictionDetector",
    "ContradictionResult",
]
