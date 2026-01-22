"""
ML Integration Plan (Pseudocode)

This module provides architectural specifications for integrating ML models
into the GroundCheck system using a hybrid approach.

Philosophy:
- Keep fast rule-based paths for common cases (90%)
- Use ML for edge cases and ambiguous scenarios (10%)
- Maintain backward compatibility
- Enable A/B testing
- Fail safely (fall back to rules)
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# 1. HYBRID FACT EXTRACTOR
# =============================================================================

class ExtractionMethod(Enum):
    """Method used for fact extraction."""
    REGEX = "regex"           # Rule-based patterns
    NEURAL = "neural"         # Neural NER model
    HYBRID = "hybrid"         # Both combined


@dataclass
class ExtractionResult:
    """Result of fact extraction."""
    facts: Dict[str, 'ExtractedFact']
    confidence: float
    method: ExtractionMethod
    latency_ms: float


class HybridFactExtractor:
    """
    Hybrid fact extractor combining rule-based and neural approaches.
    
    Strategy:
    1. Try regex first (fast path, 1ms)
    2. If low confidence, use neural model (slow path, 50ms)
    3. If neural also uncertain, use human-in-the-loop
    
    Performance:
    - 90% of cases: regex only (1ms)
    - 10% of cases: regex + neural (51ms)
    - Average: 0.9 * 1 + 0.1 * 51 = 6ms
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.8,
        use_neural: bool = True,
        model_path: Optional[str] = None
    ):
        """
        Initialize hybrid extractor.
        
        Args:
            confidence_threshold: Minimum confidence to use regex result
            use_neural: Enable neural fallback
            model_path: Path to neural model (None = use default)
        """
        # Always have rule-based extractor
        self.regex_extractor = RegexFactExtractor()
        
        # Optionally load neural model
        self.neural_extractor = None
        if use_neural:
            self.neural_extractor = NeuralFactExtractor(model_path)
        
        self.confidence_threshold = confidence_threshold
        
        # Metrics
        self.stats = {
            'regex_only': 0,
            'neural_fallback': 0,
            'neural_improved': 0
        }
    
    def extract_fact_slots(self, text: str) -> ExtractionResult:
        """
        Extract facts using hybrid approach.
        
        Args:
            text: Input text to extract facts from
            
        Returns:
            ExtractionResult with facts and metadata
        """
        import time
        start = time.time()
        
        # Step 1: Try regex (fast path)
        regex_result = self.regex_extractor.extract_fact_slots(text)
        regex_confidence = self._calculate_confidence(regex_result, text)
        
        # Step 2: If high confidence, use regex result
        if regex_confidence >= self.confidence_threshold:
            self.stats['regex_only'] += 1
            return ExtractionResult(
                facts=regex_result,
                confidence=regex_confidence,
                method=ExtractionMethod.REGEX,
                latency_ms=(time.time() - start) * 1000
            )
        
        # Step 3: Low confidence → Try neural model
        if self.neural_extractor is None:
            # Neural disabled, use regex anyway
            return ExtractionResult(
                facts=regex_result,
                confidence=regex_confidence,
                method=ExtractionMethod.REGEX,
                latency_ms=(time.time() - start) * 1000
            )
        
        self.stats['neural_fallback'] += 1
        
        neural_result = self.neural_extractor.extract_fact_slots(text)
        neural_confidence = neural_result.confidence
        
        # Step 4: Use neural if it's more confident
        if neural_confidence > regex_confidence:
            self.stats['neural_improved'] += 1
            result_facts = neural_result.facts
            final_confidence = neural_confidence
            method = ExtractionMethod.NEURAL
        else:
            # Stick with regex
            result_facts = regex_result
            final_confidence = regex_confidence
            method = ExtractionMethod.HYBRID
        
        return ExtractionResult(
            facts=result_facts,
            confidence=final_confidence,
            method=method,
            latency_ms=(time.time() - start) * 1000
        )
    
    def _calculate_confidence(
        self,
        facts: Dict[str, 'ExtractedFact'],
        text: str
    ) -> float:
        """
        Estimate confidence of regex extraction.
        
        Heuristics:
        - More facts found = higher confidence
        - Facts cover more of text = higher confidence
        - Known patterns = higher confidence
        """
        if not facts:
            return 0.0
        
        # Check coverage (what % of text is covered by facts)
        covered_chars = 0
        for fact in facts.values():
            covered_chars += len(str(fact.value))
        coverage = min(1.0, covered_chars / max(1, len(text)))
        
        # Check fact count (more facts = more confident)
        fact_count_score = min(1.0, len(facts) / 5.0)
        
        # Combine
        confidence = 0.5 * coverage + 0.5 * fact_count_score
        
        return confidence


class NeuralFactExtractor:
    """
    Neural fact extractor using pre-trained NER models.
    
    Models to consider:
    - dslim/bert-base-NER (fastest)
    - dbmdz/bert-large-cased-finetuned-conll03-english (most accurate)
    - Custom fine-tuned model on personal facts domain
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize neural extractor.
        
        Args:
            model_path: Path to model (None = use default)
        """
        # Load pre-trained model
        # Pseudocode - actual implementation would use transformers library
        if model_path:
            self.model = self._load_model(model_path)
        else:
            self.model = self._load_default_model()
        
        # Slot mapping: NER labels → our slot types
        self.label_to_slot = {
            'ORG': 'employer',
            'GPE': 'location',
            'PERSON': 'name',
            'WORK_OF_ART': 'project',
            # ... more mappings
        }
    
    def extract_fact_slots(self, text: str) -> ExtractionResult:
        """
        Extract facts using neural NER model.
        
        Args:
            text: Input text
            
        Returns:
            ExtractionResult with extracted facts
        """
        # Run NER model
        entities = self.model.predict(text)
        
        # Convert entities to fact slots
        facts = {}
        for entity in entities:
            slot = self.label_to_slot.get(entity.label)
            if slot:
                facts[slot] = ExtractedFact(
                    slot=slot,
                    value=entity.text,
                    normalized=entity.text.lower(),
                    confidence=entity.score
                )
        
        # Calculate overall confidence
        avg_confidence = sum(f.confidence for f in facts.values()) / max(1, len(facts))
        
        return ExtractionResult(
            facts=facts,
            confidence=avg_confidence,
            method=ExtractionMethod.NEURAL,
            latency_ms=50  # Approximate
        )


# =============================================================================
# 2. LEARNED TRUST MODEL
# =============================================================================

@dataclass
class TrustFeatures:
    """Features for trust score prediction."""
    age_days: float                  # Days since creation
    confirmation_count: int          # Times confirmed
    source_type: int                 # 0=system, 1=user, 2=external
    contradiction_count: int         # Times contradicted
    slot_importance: int             # 0=low, 1=medium, 2=high
    initial_confidence: float        # Original extraction confidence
    update_frequency: float          # Updates per month
    cross_validation_count: int      # Confirmed by multiple sources
    recency_of_confirmation: float   # Days since last confirmation
    domain_specificity: int          # 0=general, 1=professional, 2=medical


class LearnedTrustModel:
    """
    Neural network for trust score prediction.
    
    Architecture:
    - Input: 10 features
    - Hidden: 64 units (ReLU)
    - Hidden: 32 units (ReLU)
    - Output: 1 unit (Sigmoid) → trust score [0, 1]
    
    Training:
    - Loss: MSE (mean squared error)
    - Optimizer: Adam
    - Labels: Ground truth trust from corrections
    
    Performance:
    - Inference: 1-5ms
    - Accuracy: ~85% (within 0.1 of true trust)
    - Model size: 10MB
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize trust model.
        
        Args:
            model_path: Path to trained model
        """
        if model_path:
            self.model = self._load_model(model_path)
        else:
            # Use rule-based as fallback
            self.model = None
        
        # Rule-based fallback
        self.rule_based_trust = RuleBasedTrustCalculator()
        
        # Blending factor (for gradual rollout)
        self.blend_factor = 0.5  # 50% learned, 50% rule-based
    
    def predict_trust(self, memory: 'Memory') -> float:
        """
        Predict trust score for a memory.
        
        Args:
            memory: Memory object with metadata
            
        Returns:
            Trust score [0, 1]
        """
        # Extract features
        features = self._extract_features(memory)
        
        # Get predictions
        if self.model:
            learned_trust = self.model.predict(features)
        else:
            learned_trust = 0.5  # Neutral if no model
        
        rule_based_trust = self.rule_based_trust.calculate(memory)
        
        # Blend predictions (safety net)
        trust = (
            self.blend_factor * learned_trust +
            (1 - self.blend_factor) * rule_based_trust
        )
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, trust))
    
    def _extract_features(self, memory: 'Memory') -> TrustFeatures:
        """Extract features from memory for prediction."""
        # Calculate features
        age_days = (datetime.now() - memory.timestamp).days
        
        # ... extract other features from memory metadata
        
        return TrustFeatures(
            age_days=age_days,
            confirmation_count=memory.confirmation_count,
            source_type=memory.source.value,
            contradiction_count=memory.contradiction_count,
            slot_importance=self._get_slot_importance(memory.slot),
            initial_confidence=memory.initial_confidence,
            update_frequency=self._calculate_update_frequency(memory),
            cross_validation_count=memory.cross_validations,
            recency_of_confirmation=self._days_since_confirmation(memory),
            domain_specificity=self._get_domain(memory)
        )


# =============================================================================
# 3. HYBRID CONTRADICTION DETECTOR
# =============================================================================

class ContradictionMethod(Enum):
    """Method used for contradiction detection."""
    RULE_BASED = "rule_based"
    NLI = "nli"
    HYBRID = "hybrid"


@dataclass
class ContradictionResult:
    """Result of contradiction detection."""
    is_contradictory: bool
    confidence: float
    method: ContradictionMethod
    explanation: Optional[str] = None


class HybridContradictionDetector:
    """
    Hybrid contradiction detector using rules + NLI.
    
    Strategy:
    1. Use rule-based for obvious cases (same slot, very different values)
    2. Use NLI for edge cases (semantic subsumption, context-dependent)
    3. Cache NLI results for performance
    
    Performance:
    - 95% of cases: rule-based (1ms)
    - 5% of cases: NLI (100ms)
    - Average: 0.95 * 1 + 0.05 * 100 = 6ms
    """
    
    def __init__(
        self,
        use_nli: bool = True,
        similarity_threshold: float = 0.5
    ):
        """
        Initialize hybrid detector.
        
        Args:
            use_nli: Enable NLI for edge cases
            similarity_threshold: Threshold for obvious differences
        """
        # Rule-based detector
        self.rule_based = RuleBasedContradictionDetector()
        
        # NLI model (optional)
        self.nli_model = None
        if use_nli:
            self.nli_model = NLIModel()
        
        self.similarity_threshold = similarity_threshold
        
        # Cache NLI results
        self.nli_cache = {}
    
    def are_contradictory(
        self,
        slot: str,
        value1: str,
        value2: str,
        context: Optional[Dict] = None
    ) -> ContradictionResult:
        """
        Check if two values contradict.
        
        Args:
            slot: Fact slot type
            value1: First value
            value2: Second value
            context: Optional context for decision
            
        Returns:
            ContradictionResult with decision and metadata
        """
        # Step 1: Check if slot is mutually exclusive
        if slot not in MUTUALLY_EXCLUSIVE_SLOTS:
            # Slot allows multiple values (e.g., 'hobby', 'programming_language')
            return ContradictionResult(
                is_contradictory=False,
                confidence=1.0,
                method=ContradictionMethod.RULE_BASED,
                explanation="Slot allows multiple values"
            )
        
        # Step 2: Check if obviously same
        similarity = self._calculate_similarity(value1, value2)
        if similarity > 0.9:
            # Essentially the same value
            return ContradictionResult(
                is_contradictory=False,
                confidence=1.0,
                method=ContradictionMethod.RULE_BASED,
                explanation="Values are very similar"
            )
        
        # Step 3: Check if obviously different
        if similarity < self.similarity_threshold:
            # Clearly different values
            
            # But check for subsumption with NLI (edge case)
            if self.nli_model and self._might_be_subsumption(value1, value2):
                # E.g., "Engineer" vs "Senior Engineer"
                return self._check_with_nli(slot, value1, value2)
            
            return ContradictionResult(
                is_contradictory=True,
                confidence=0.9,
                method=ContradictionMethod.RULE_BASED,
                explanation="Values are clearly different"
            )
        
        # Step 4: Ambiguous case → Use NLI
        if self.nli_model:
            return self._check_with_nli(slot, value1, value2)
        else:
            # No NLI available, fall back to similarity
            return ContradictionResult(
                is_contradictory=similarity < 0.7,
                confidence=0.6,
                method=ContradictionMethod.RULE_BASED,
                explanation="Ambiguous similarity, no NLI available"
            )
    
    def _check_with_nli(
        self,
        slot: str,
        value1: str,
        value2: str
    ) -> ContradictionResult:
        """Use NLI model to check contradiction."""
        # Check cache first
        cache_key = f"{slot}::{value1}::{value2}"
        if cache_key in self.nli_cache:
            return self.nli_cache[cache_key]
        
        # Construct NLI premise and hypothesis
        premise = f"The {slot} is {value1}"
        hypothesis = f"The {slot} is {value2}"
        
        # Run NLI
        nli_result = self.nli_model.predict(premise, hypothesis)
        
        # Interpret results
        if nli_result.label == 'contradiction':
            is_contradictory = True
            confidence = nli_result.score
            explanation = "NLI detected contradiction"
        elif nli_result.label == 'entailment':
            # value2 entails value1 (or vice versa) → not contradiction
            # E.g., "Senior Engineer" entails "Engineer"
            is_contradictory = False
            confidence = nli_result.score
            explanation = "NLI detected entailment (subsumption)"
        else:  # neutral
            # Independent facts, both can be true
            is_contradictory = False
            confidence = nli_result.score
            explanation = "NLI detected neutral (independent facts)"
        
        result = ContradictionResult(
            is_contradictory=is_contradictory,
            confidence=confidence,
            method=ContradictionMethod.NLI,
            explanation=explanation
        )
        
        # Cache result
        self.nli_cache[cache_key] = result
        
        return result


class NLIModel:
    """
    Natural Language Inference model for contradiction detection.
    
    Models to consider:
    - microsoft/deberta-large-mnli (best accuracy, 1.5GB)
    - facebook/bart-large-mnli (good balance, 1.4GB)
    - cross-encoder/nli-deberta-base (fastest, 400MB)
    """
    
    def __init__(self, model_name: str = "microsoft/deberta-large-mnli"):
        """
        Initialize NLI model.
        
        Args:
            model_name: Hugging Face model name
        """
        # Pseudocode - actual implementation uses transformers
        self.model = self._load_nli_model(model_name)
    
    def predict(self, premise: str, hypothesis: str) -> Any:
        """
        Predict NLI relationship.
        
        Args:
            premise: First statement
            hypothesis: Second statement
            
        Returns:
            NLI result with label (contradiction/entailment/neutral) and score
        """
        # Run NLI model
        result = self.model(f"{premise} [SEP] {hypothesis}")
        
        # result.label: 'contradiction', 'entailment', or 'neutral'
        # result.score: confidence [0, 1]
        
        return result


# =============================================================================
# 4. POLICY LEARNER
# =============================================================================

class PolicyType(Enum):
    """Contradiction resolution policies."""
    PREFER_NEWER = "prefer_newer"          # Use most recent value
    REQUIRE_DISCLOSURE = "require_disclosure"  # Must acknowledge old value
    ASK_USER = "ask_user"                  # Let user decide
    MERGE = "merge"                        # Combine values if possible


@dataclass
class PolicyFeatures:
    """Features for policy recommendation."""
    slot_type: str                     # Type of fact
    trust_difference: float            # abs(trust1 - trust2)
    age_difference_days: float         # abs(age1 - age2)
    domain: str                        # medical/personal/professional
    user_correction_rate: float        # How often user corrects this type
    criticality_score: float           # How critical is this fact (0-1)
    value_similarity: float            # How similar are the values
    disclosure_preference: float       # User's disclosure preference
    source_reliability_diff: float     # Difference in source reliability
    regulatory_requirement: bool       # HIPAA/compliance flag


class PolicyLearner:
    """
    Learn contradiction resolution policies from user feedback.
    
    Model: Random Forest Classifier
    - Interpretable (can see feature importance)
    - Fast (5-10ms inference)
    - Handles mixed features (categorical + numerical)
    - Robust to outliers
    
    Training:
    - Labels: User feedback on policy decisions
    - Features: Contradiction + context features
    - Minimum: 5,000 labeled examples
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize policy learner.
        
        Args:
            model_path: Path to trained model
        """
        if model_path:
            self.model = self._load_model(model_path)
        else:
            # Use rule-based as fallback
            self.model = None
        
        # Rule-based fallback
        self.rule_based_policy = RuleBasedPolicyEngine()
        
        # Feature encoder
        self.encoder = PolicyFeatureEncoder()
    
    def recommend_policy(
        self,
        contradiction: 'ContradictionDetail',
        context: Dict
    ) -> PolicyType:
        """
        Recommend policy for handling contradiction.
        
        Args:
            contradiction: Details of contradiction
            context: User/domain context
            
        Returns:
            Recommended policy
        """
        # Extract features
        features = self._extract_features(contradiction, context)
        
        # Get prediction from model
        if self.model:
            # Encode features
            feature_vector = self.encoder.encode(features)
            
            # Predict policy
            policy = self.model.predict(feature_vector)
            confidence = self.model.predict_proba(feature_vector).max()
            
            # If low confidence, use rule-based
            if confidence < 0.7:
                policy = self.rule_based_policy.get_policy(contradiction, context)
        else:
            # No model, use rules
            policy = self.rule_based_policy.get_policy(contradiction, context)
        
        return PolicyType(policy)
    
    def _extract_features(
        self,
        contradiction: 'ContradictionDetail',
        context: Dict
    ) -> PolicyFeatures:
        """Extract features for policy recommendation."""
        # Calculate trust difference
        trust_diff = abs(
            contradiction.trust_scores[0] - contradiction.trust_scores[1]
        )
        
        # Calculate age difference
        age_diff = abs(
            contradiction.timestamps[0] - contradiction.timestamps[1]
        )
        
        # Get domain
        domain = context.get('domain', 'personal')
        
        # ... extract other features
        
        return PolicyFeatures(
            slot_type=contradiction.slot,
            trust_difference=trust_diff,
            age_difference_days=age_diff / 86400,  # Convert seconds to days
            domain=domain,
            user_correction_rate=context.get('correction_rate', 0.0),
            criticality_score=self._get_criticality(contradiction.slot),
            value_similarity=self._calculate_similarity(
                contradiction.values[0],
                contradiction.values[1]
            ),
            disclosure_preference=context.get('disclosure_pref', 0.5),
            source_reliability_diff=self._source_reliability_diff(contradiction),
            regulatory_requirement=domain == 'medical'
        )


# =============================================================================
# 5. DISCLOSURE GENERATOR
# =============================================================================

class DisclosureGenerator:
    """
    Generate natural language disclosure statements.
    
    Model: Fine-tuned T5-base (Seq2Seq)
    - Input: Contradiction details + context
    - Output: Natural disclosure text
    - Model size: 500MB
    - Inference: 50-100ms
    
    Training:
    - Dataset: 1,000+ disclosure examples
    - Fine-tune on disclosure generation task
    - Evaluate on fluency and accuracy
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize disclosure generator.
        
        Args:
            model_path: Path to fine-tuned model
        """
        if model_path:
            self.model = self._load_model(model_path)
        else:
            # Use template-based as fallback
            self.model = None
    
    def generate_disclosure(
        self,
        contradiction: 'ContradictionDetail',
        context: str
    ) -> str:
        """
        Generate natural disclosure statement.
        
        Args:
            contradiction: Details of contradiction
            context: Conversation context
            
        Returns:
            Natural language disclosure
        """
        if self.model:
            # Use neural generation
            prompt = self._create_prompt(contradiction, context)
            disclosure = self.model.generate(prompt)
        else:
            # Fall back to template
            disclosure = self._template_disclosure(contradiction)
        
        return disclosure
    
    def _create_prompt(
        self,
        contradiction: 'ContradictionDetail',
        context: str
    ) -> str:
        """Create prompt for generation."""
        # Format prompt for T5
        prompt = f"""
        Generate natural disclosure for:
        Slot: {contradiction.slot}
        Old value: {contradiction.values[0]} ({contradiction.timestamps[0]})
        New value: {contradiction.values[1]} ({contradiction.timestamps[1]})
        Context: {context}
        
        Disclosure:
        """
        return prompt
    
    def _template_disclosure(
        self,
        contradiction: 'ContradictionDetail'
    ) -> str:
        """Generate disclosure using template."""
        # Simple template fallback
        old_value = contradiction.values[0]
        new_value = contradiction.values[1]
        
        return f"{new_value} (changed from {old_value})"


# =============================================================================
# 6. A/B TESTING FRAMEWORK
# =============================================================================

class ExperimentManager:
    """
    Manage A/B tests for ML model deployment.
    
    Features:
    - Deterministic user assignment
    - Metric tracking per group
    - Statistical significance testing
    - Automatic rollout/rollback
    """
    
    def __init__(self):
        """Initialize experiment manager."""
        self.active_experiments = {}
        self.metrics_tracker = MetricsTracker()
    
    def create_experiment(
        self,
        name: str,
        component: str,
        treatment_version: str,
        traffic_pct: float = 0.1
    ) -> str:
        """
        Create new A/B test.
        
        Args:
            name: Experiment name
            component: Which component to test
            treatment_version: New model version
            traffic_pct: % traffic to treatment (0.0-1.0)
            
        Returns:
            Experiment ID
        """
        exp_id = self._generate_id()
        
        self.active_experiments[exp_id] = {
            'name': name,
            'component': component,
            'treatment': treatment_version,
            'traffic_pct': traffic_pct,
            'start_time': datetime.now(),
            'status': 'running'
        }
        
        return exp_id
    
    def get_version(
        self,
        component: str,
        user_id: str
    ) -> str:
        """
        Get model version for user.
        
        Args:
            component: Component name
            user_id: User identifier
            
        Returns:
            Model version to use
        """
        # Find active experiment for this component
        for exp in self.active_experiments.values():
            if exp['component'] == component and exp['status'] == 'running':
                # Deterministic assignment
                if self._in_treatment_group(user_id, exp):
                    return exp['treatment']
        
        # Default to control (production version)
        return 'control'
    
    def _in_treatment_group(
        self,
        user_id: str,
        experiment: Dict
    ) -> bool:
        """Deterministically assign user to treatment group."""
        # Hash user_id to get consistent random value
        hash_val = hash(f"{user_id}:{experiment['name']}") % 100
        
        # Assign to treatment with traffic_pct probability
        return hash_val < (experiment['traffic_pct'] * 100)


# =============================================================================
# CONSTANTS
# =============================================================================

MUTUALLY_EXCLUSIVE_SLOTS = {
    'employer', 'location', 'name', 'title', 'occupation',
    'coffee', 'hobby', 'favorite_color', 'favorite_food',
    'pet', 'school', 'undergrad_school', 'masters_school',
    'graduation_year', 'project'
}
