"""
LLM-Based Fact Extractor for CRT System.

Uses language models to extract structured facts from unstructured text.
This complements the regex-based extraction in fact_slots.py by handling
open-world facts that don't fit predefined patterns.

Design:
- Uses cheap models (gpt-4o-mini or similar) with JSON schema enforcement
- Returns confidence scores for each extracted fact
- Preserves evidence spans for auditability
- Falls back gracefully when LLM is unavailable
"""

from __future__ import annotations

import json
import logging
import time
import re
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from .fact_tuples import FactTuple, FactTupleSet, FactAction

logger = logging.getLogger(__name__)

# Default extraction prompt template
DEFAULT_EXTRACTION_PROMPT = """Extract facts from this text as JSON tuples.

Text: "{text}"

Return a JSON object with a "facts" array. Each fact should have:
- entity: who/what the fact is about (use "User" for first-person statements)
- attribute: what property (use snake_case, e.g., "employment_status", "favorite_color")
- value: the value
- action: "add" (new fact), "update" (changing fact), "deprecate" (no longer true), or "deny" (explicitly false)
- confidence: 0.0-1.0 (how certain is this fact based on the text)
- evidence_span: exact quote from text supporting this fact

Examples:
"I'm effectively resigning from Google to join a startup in Seattle."
{{
  "facts": [
    {{"entity": "User", "attribute": "employment_status", "value": "resigning", "action": "update", "confidence": 0.78, "evidence_span": "I'm effectively resigning"}},
    {{"entity": "User", "attribute": "employer", "value": "Google", "action": "deprecate", "confidence": 0.71, "evidence_span": "resigning from Google"}},
    {{"entity": "User", "attribute": "next_employer_type", "value": "startup", "action": "add", "confidence": 0.66, "evidence_span": "join a startup"}},
    {{"entity": "User", "attribute": "location", "value": "Seattle", "action": "update", "confidence": 0.73, "evidence_span": "in Seattle"}}
  ]
}}

"My favorite hobby is pottery but I used to do woodworking."
{{
  "facts": [
    {{"entity": "User", "attribute": "hobby", "value": "pottery", "action": "add", "confidence": 0.85, "evidence_span": "favorite hobby is pottery"}},
    {{"entity": "User", "attribute": "former_hobby", "value": "woodworking", "action": "add", "confidence": 0.72, "evidence_span": "used to do woodworking"}}
  ]
}}

Now extract facts from the input text. Return ONLY valid JSON with a "facts" array."""


@dataclass
class LLMConfig:
    """Configuration for LLM-based extraction."""
    model: str = "gpt-4o-mini"
    temperature: float = 0.1  # Low temperature for more deterministic output
    max_tokens: int = 1024
    timeout: float = 30.0
    max_retries: int = 2
    prompt_template: str = DEFAULT_EXTRACTION_PROMPT


class LLMFactExtractor:
    """
    Extract structured facts from text using language models.
    
    This class provides LLM-based fact extraction that handles open-world facts
    beyond the predefined regex patterns. It uses a structured JSON output format
    to ensure consistent, parseable results.
    
    Attributes:
        config: LLM configuration settings
        llm_client: OpenAI-compatible client (optional)
        
    Example:
        >>> extractor = LLMFactExtractor()
        >>> tuples = extractor.extract_tuples("I work at Microsoft in Seattle")
        >>> for t in tuples:
        ...     print(f"{t.entity}.{t.attribute} = {t.value}")
        User.employer = Microsoft
        User.location = Seattle
    """
    
    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize the LLM fact extractor.
        
        Args:
            config: LLM configuration (uses defaults if not provided)
            llm_client: OpenAI-compatible client. If not provided, will attempt
                       to create one using environment variables.
        """
        self.config = config or LLMConfig()
        self._llm_client = llm_client
        self._fallback_extractor: Optional[Callable] = None
        self._auth_failed = False  # Track persistent auth failures
        
    @property
    def llm_client(self):
        """Lazy-load the LLM client."""
        if self._llm_client is None:
            self._llm_client = self._create_client()
        return self._llm_client
    
    def _create_client(self) -> Optional[Any]:
        """Create OpenAI client from environment."""
        try:
            import openai
            return openai.OpenAI()
        except ImportError:
            logger.warning("OpenAI package not installed. LLM extraction unavailable.")
            return None
        except Exception as e:
            logger.warning(f"Failed to create OpenAI client: {e}")
            return None
    
    def set_fallback_extractor(self, extractor: Callable[[str], List[FactTuple]]) -> None:
        """
        Set a fallback extractor to use when LLM is unavailable.
        
        Args:
            extractor: Function that takes text and returns list of FactTuples
        """
        self._fallback_extractor = extractor
    
    def extract_tuples(self, text: str) -> List[FactTuple]:
        """
        Extract fact tuples from text using LLM.
        
        Args:
            text: Input text to extract facts from
            
        Returns:
            List of FactTuple objects representing extracted facts
        """
        if not text or not text.strip():
            return []
        
        # Skip LLM extraction if we've had persistent auth failures
        if self._auth_failed:
            return self._try_fallback(text)
        
        # Try LLM extraction
        if self.llm_client is not None:
            try:
                return self._extract_with_llm(text)
            except Exception as e:
                error_str = str(e).lower()
                # Mark auth failure to avoid repeated attempts
                if "401" in error_str or "authentication" in error_str or "api key" in error_str:
                    logger.warning(f"LLM extraction disabled due to auth failure: {e}")
                    self._auth_failed = True
                else:
                    logger.warning(f"LLM extraction failed: {e}")
        
        return self._try_fallback(text)
    
    def _try_fallback(self, text: str) -> List[FactTuple]:
        """Try fallback extractor if available."""
        # Fall back to alternative extractor if available
        if self._fallback_extractor is not None:
            try:
                return self._fallback_extractor(text)
            except Exception as e:
                logger.warning(f"Fallback extraction failed: {e}")
        
        # Return empty list if all extraction methods fail
        logger.debug("No extraction method available, returning empty list")
        return []
    
    def _extract_with_llm(self, text: str) -> List[FactTuple]:
        """Extract facts using the LLM API."""
        prompt = self.config.prompt_template.format(text=text)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                
                content = response.choices[0].message.content
                return self._parse_llm_response(content, text)
                
            except Exception as e:
                error_str = str(e).lower()
                # Don't retry on authentication errors - they will never succeed
                if "401" in error_str or "authentication" in error_str or "api key" in error_str:
                    logger.warning(f"LLM extraction failed (auth error, not retrying): {e}")
                    raise
                
                if attempt < self.config.max_retries:
                    logger.debug(f"LLM extraction attempt {attempt + 1} failed: {e}")
                    time.sleep(1.0 * (attempt + 1))  # Exponential backoff
                else:
                    raise
        
        return []
    
    def _parse_llm_response(self, content: str, source_text: str) -> List[FactTuple]:
        """
        Parse LLM JSON response into FactTuple objects.
        
        Args:
            content: JSON string from LLM
            source_text: Original text (for timestamp/metadata)
            
        Returns:
            List of validated FactTuple objects
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            # Try to extract JSON from response if wrapped in markdown
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return []
            else:
                return []
        
        facts_data = data.get("facts", [])
        if not isinstance(facts_data, list):
            return []
        
        tuples = []
        timestamp = time.time()
        
        for fact_data in facts_data:
            if not isinstance(fact_data, dict):
                continue
            
            try:
                # Map action string to enum
                action_str = fact_data.get("action", "add").lower()
                action_map = {
                    "add": FactAction.ADD,
                    "update": FactAction.UPDATE,
                    "deprecate": FactAction.DEPRECATE,
                    "deny": FactAction.DENY,
                }
                action = action_map.get(action_str, FactAction.ADD)
                
                tuple_obj = FactTuple(
                    entity=fact_data.get("entity", "User"),
                    attribute=fact_data.get("attribute", ""),
                    value=fact_data.get("value", ""),
                    action=action,
                    confidence=float(fact_data.get("confidence", 0.5)),
                    evidence_span=fact_data.get("evidence_span", ""),
                    timestamp=timestamp,
                    source="llm_extraction",
                    metadata={"source_text_length": len(source_text)},
                )
                
                # Validate: skip tuples with missing required fields
                if tuple_obj.attribute and tuple_obj.value:
                    tuples.append(tuple_obj)
                    
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid fact data: {e}")
                continue
        
        return tuples
    
    def extract_tuple_set(self, text: str) -> FactTupleSet:
        """
        Extract facts and return as a FactTupleSet.
        
        Args:
            text: Input text to extract facts from
            
        Returns:
            FactTupleSet containing all extracted facts
        """
        tuples = self.extract_tuples(text)
        return FactTupleSet(
            tuples=tuples,
            source_text=text,
            extraction_timestamp=time.time(),
            extraction_method="llm",
        )


class LocalLLMFactExtractor(LLMFactExtractor):
    """
    LLM Fact Extractor using local models (e.g., Ollama).
    
    This variant uses locally-hosted LLMs for extraction, which is useful
    for privacy-sensitive deployments or environments without internet access.
    
    Example:
        >>> extractor = LocalLLMFactExtractor(model="llama3.2")
        >>> tuples = extractor.extract_tuples("I work at Acme Corp")
    """
    
    def __init__(
        self,
        model: str = "llama3.2",
        **kwargs
    ):
        """
        Initialize local LLM extractor.
        
        Args:
            model: Name of the Ollama model to use
            **kwargs: Additional arguments passed to parent
        """
        config = LLMConfig(model=model)
        super().__init__(config=config, **kwargs)
        self.model = model
    
    def _create_client(self) -> Optional[Any]:
        """Create Ollama client."""
        try:
            from .ollama_client import OllamaClient
            return OllamaClient(model=self.model)
        except ImportError:
            logger.warning("Ollama client not available.")
            return None
        except Exception as e:
            logger.warning(f"Failed to create Ollama client: {e}")
            return None
    
    def _extract_with_llm(self, text: str) -> List[FactTuple]:
        """Extract facts using local Ollama model."""
        if self.llm_client is None:
            return []
        
        prompt = self.config.prompt_template.format(text=text)
        
        try:
            # OllamaClient.generate returns a string, not a dict
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,  # Low temperature for deterministic output
            )
            
            # Response is the generated text
            return self._parse_llm_response(response, text)
            
        except Exception as e:
            logger.warning(f"Local LLM extraction failed: {e}")
            return []


def create_regex_fallback_extractor():
    """
    Create a fallback extractor using existing regex-based extraction.
    
    This allows the LLM extractor to gracefully degrade to regex extraction
    when the LLM is unavailable.
    
    Returns:
        Function that converts regex ExtractedFacts to FactTuples
    """
    from .fact_slots import extract_fact_slots
    
    def extractor(text: str) -> List[FactTuple]:
        facts = extract_fact_slots(text)
        tuples = []
        
        for slot, fact in facts.items():
            tuple_obj = FactTuple(
                entity="User",
                attribute=slot,
                value=str(fact.value),
                action=FactAction.ADD,
                confidence=0.9,  # High confidence for regex matches
                evidence_span=text[:100] if len(text) > 100 else text,
                source="regex_extraction",
            )
            tuples.append(tuple_obj)
        
        return tuples
    
    return extractor
