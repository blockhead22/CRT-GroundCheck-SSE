# Active Learning Architecture

**Goal:** Build a continuous learning pipeline that improves ML models from production data without manual labeling overhead.

**Philosophy:** Start deterministic, collect feedback, learn incrementally, deploy safely.

---

## Overview

The active learning pipeline enables the CRT + GroundCheck system to:
1. Collect interaction data automatically
2. Gather user feedback with minimal friction
3. Train models on labeled examples
4. Deploy improved models with A/B testing
5. Continuously monitor and update

**Key Principle:** Users provide implicit and explicit feedback through corrections, confirmations, and usage patterns.

---

## Phase 1: Data Collection Pipeline (Month 1-2)

### 1.1 Interaction Logging

**What to Log:**

```python
@dataclass
class InteractionLog:
    """Complete record of a single user interaction."""
    
    # Core identifiers
    interaction_id: str
    user_id: str  # Hashed for privacy
    timestamp: datetime
    
    # Input
    query: str
    retrieved_memories: List[Memory]
    
    # System processing
    extracted_facts: Dict[str, ExtractedFact]
    detected_contradictions: List[ContradictionDetail]
    trust_scores: Dict[str, float]
    
    # Output
    generated_text: str
    verification_result: VerificationReport
    applied_policy: Optional[str]
    
    # Feedback (populated later)
    user_feedback: Optional[UserFeedback] = None
    correction: Optional[str] = None
    
    # Metadata
    model_versions: Dict[str, str]  # Which models were used
    latencies: Dict[str, float]  # Component latencies
    experiment_group: Optional[str]  # A/B test assignment
```

**Implementation:**

```python
class InteractionLogger:
    """Logs all system interactions for training data collection."""
    
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self._create_tables()
    
    def log_interaction(
        self,
        query: str,
        memories: List[Memory],
        output: str,
        verification: VerificationReport,
        metadata: Dict
    ) -> str:
        """Log interaction and return interaction_id."""
        
        interaction_id = str(uuid.uuid4())
        
        log_entry = {
            'interaction_id': interaction_id,
            'user_id': self._hash_user_id(metadata.get('user_id')),
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'memories': json.dumps([m.to_dict() for m in memories]),
            'output': output,
            'verification': json.dumps(verification.to_dict()),
            'metadata': json.dumps(metadata)
        }
        
        self.db.execute(
            """
            INSERT INTO interactions 
            (interaction_id, user_id, timestamp, query, memories, 
             output, verification, metadata)
            VALUES (:interaction_id, :user_id, :timestamp, :query, 
                    :memories, :output, :verification, :metadata)
            """,
            log_entry
        )
        self.db.commit()
        
        return interaction_id
    
    def update_feedback(
        self,
        interaction_id: str,
        feedback: UserFeedback
    ):
        """Add user feedback to existing interaction."""
        
        self.db.execute(
            """
            UPDATE interactions 
            SET user_feedback = ?, feedback_timestamp = ?
            WHERE interaction_id = ?
            """,
            (json.dumps(feedback.to_dict()), datetime.now().isoformat(), interaction_id)
        )
        self.db.commit()
```

**Privacy Considerations:**
- Hash user IDs (SHA-256)
- Anonymize PII in logs (replace names with placeholders)
- Implement data retention policy (90 days)
- GDPR compliance: Allow data deletion

---

### 1.2 Component-Specific Logging

**Fact Extraction Logs:**

```python
@dataclass
class FactExtractionLog:
    text: str
    extracted_facts: Dict[str, ExtractedFact]
    extractor_version: str
    confidence_scores: Dict[str, float]
    latency_ms: float
    
    # Ground truth (populated from corrections)
    true_facts: Optional[Dict[str, ExtractedFact]] = None
```

**Contradiction Detection Logs:**

```python
@dataclass
class ContradictionLog:
    memories: List[Memory]
    detected_contradictions: List[ContradictionDetail]
    detector_version: str
    
    # Ground truth (from user feedback)
    true_contradictions: Optional[List[ContradictionDetail]] = None
    false_positives: Optional[List[str]] = None  # Flagged but not real
```

**Trust Score Logs:**

```python
@dataclass
class TrustScoreLog:
    memory: Memory
    predicted_trust: float
    actual_trust: float  # Current value
    
    # Validation signal
    was_corrected: bool  # Did user correct this?
    time_until_update: Optional[int]  # Days until changed
```

**Policy Decision Logs:**

```python
@dataclass
class PolicyDecisionLog:
    contradiction: ContradictionDetail
    context: Dict
    applied_policy: str  # PREFER_NEWER, REQUIRE_DISCLOSURE, etc.
    
    # User feedback
    was_correct: Optional[bool] = None
    preferred_policy: Optional[str] = None
```

---

## Phase 2: User Feedback Collection (Month 1-3)

### 2.1 Implicit Feedback

**User Corrections:**

When a user corrects information, we learn:
- Fact extraction: Original was wrong, correction is right
- Trust scores: Memory that was corrected had inflated trust
- Contradictions: If correction creates conflict, original handling was poor

```python
class ImplicitFeedbackCollector:
    """Extracts training signals from user corrections."""
    
    def process_correction(
        self,
        original_query: str,
        original_output: str,
        correction: str,
        interaction_id: str
    ):
        """Extract training labels from user correction."""
        
        # Extract facts from correction (ground truth)
        true_facts = extract_fact_slots(correction)
        
        # Get original extraction
        interaction = self.db.get_interaction(interaction_id)
        original_facts = interaction.extracted_facts
        
        # Generate training example
        training_example = {
            'text': original_query,
            'predicted_facts': original_facts,
            'true_facts': true_facts,
            'type': 'correction',
            'timestamp': datetime.now().isoformat()
        }
        
        self.training_db.add_example('fact_extraction', training_example)
        
        # Update trust scores
        for memory in interaction.retrieved_memories:
            if self._was_used_in_output(memory, original_output):
                # This memory led to incorrect output
                self._mark_memory_untrusted(memory.id)
```

**Confirmation Signals:**

When a user confirms information (e.g., "Yes, that's correct"), we learn:
- Fact extraction was accurate
- Trust scores should increase
- Policy decisions were appropriate

```python
def process_confirmation(self, interaction_id: str):
    """Extract positive training signals from confirmation."""
    
    interaction = self.db.get_interaction(interaction_id)
    
    # Mark as positive example
    training_example = {
        'text': interaction.query,
        'predicted_facts': interaction.extracted_facts,
        'true_facts': interaction.extracted_facts,  # Confirmed correct
        'type': 'confirmation',
        'timestamp': datetime.now().isoformat()
    }
    
    self.training_db.add_example('fact_extraction', training_example)
    
    # Boost trust scores
    for memory in interaction.retrieved_memories:
        self._boost_memory_trust(memory.id)
```

---

### 2.2 Explicit Feedback UI

**Feedback Widget:**

```python
@dataclass
class FeedbackWidget:
    """UI component for collecting user feedback."""
    
    def render_after_response(self, interaction_id: str):
        """Show feedback options after system response."""
        
        return {
            'type': 'feedback_widget',
            'interaction_id': interaction_id,
            'options': [
                {
                    'id': 'thumbs_up',
                    'label': '👍 Correct',
                    'action': 'confirm'
                },
                {
                    'id': 'thumbs_down',
                    'label': '👎 Incorrect',
                    'action': 'request_correction'
                },
                {
                    'id': 'disclosure_flag',
                    'label': '⚠️ Should have disclosed',
                    'action': 'flag_missing_disclosure'
                },
                {
                    'id': 'skip',
                    'label': 'Skip',
                    'action': 'no_feedback'
                }
            ]
        }
    
    def render_correction_form(self):
        """Show correction form when user flags incorrect output."""
        
        return {
            'type': 'correction_form',
            'fields': [
                {
                    'name': 'what_was_wrong',
                    'type': 'select',
                    'options': [
                        'Wrong fact',
                        'Missing disclosure',
                        'Hallucination',
                        'Other'
                    ]
                },
                {
                    'name': 'correct_answer',
                    'type': 'text',
                    'placeholder': 'What should the answer be?'
                }
            ]
        }
```

**Contradiction Feedback:**

```python
def render_contradiction_feedback(
    self,
    contradiction: ContradictionDetail,
    applied_policy: str
):
    """Collect feedback on contradiction handling."""
    
    return {
        'type': 'contradiction_feedback',
        'message': f'We found conflicting information about {contradiction.slot}:',
        'values': contradiction.values,
        'timestamps': contradiction.timestamps,
        'applied_policy': applied_policy,
        'question': 'Was this handled correctly?',
        'options': [
            {
                'label': '✓ Correct - disclosure was appropriate',
                'value': 'correct'
            },
            {
                'label': '✗ Should not have disclosed (too minor)',
                'value': 'over_disclosure'
            },
            {
                'label': '⚠️ Should have disclosed (but didn\'t)',
                'value': 'under_disclosure'
            },
            {
                'label': 'Wrong value chosen',
                'value': 'wrong_resolution'
            }
        ]
    }
```

**Sampling Strategy:**

Don't ask for feedback on every interaction (annoying).

```python
class FeedbackSampler:
    """Smart sampling for feedback requests."""
    
    def should_request_feedback(
        self,
        interaction: InteractionLog,
        user_feedback_count: int
    ) -> bool:
        """Decide whether to show feedback UI."""
        
        # Always ask for first 5 interactions (onboarding)
        if user_feedback_count < 5:
            return True
        
        # High-priority cases (always ask)
        if interaction.detected_contradictions:
            return True
        
        if interaction.verification_result.passed == False:
            return True
        
        # Random sampling (10% of normal interactions)
        if random.random() < 0.1:
            return True
        
        # Model uncertainty (low confidence predictions)
        if any(conf < 0.7 for conf in interaction.confidence_scores.values()):
            return True
        
        return False
```

---

## Phase 3: Training Pipeline (Month 3-6)

### 3.1 Data Preparation

**Training Dataset Builder:**

```python
class TrainingDatasetBuilder:
    """Builds training datasets from logged interactions."""
    
    def build_fact_extraction_dataset(
        self,
        min_examples: int = 1000
    ) -> Dataset:
        """Build dataset for fact extraction model."""
        
        # Get interactions with corrections or confirmations
        examples = self.db.query(
            """
            SELECT text, predicted_facts, true_facts, feedback_type
            FROM training_examples
            WHERE component = 'fact_extraction'
            AND true_facts IS NOT NULL
            ORDER BY timestamp DESC
            """
        )
        
        if len(examples) < min_examples:
            raise ValueError(f"Need {min_examples} examples, have {len(examples)}")
        
        # Split: 80% train, 10% validation, 10% test
        train_size = int(0.8 * len(examples))
        val_size = int(0.1 * len(examples))
        
        return {
            'train': examples[:train_size],
            'val': examples[train_size:train_size+val_size],
            'test': examples[train_size+val_size:]
        }
    
    def build_trust_score_dataset(self):
        """Build dataset for trust score prediction."""
        
        # Get memories that were later corrected or confirmed
        examples = self.db.query(
            """
            SELECT memory_id, features, was_corrected, time_until_update
            FROM trust_score_examples
            WHERE (was_corrected IS NOT NULL OR time_until_update IS NOT NULL)
            """
        )
        
        # Label: 1.0 if never corrected, decays based on time_until_update
        for ex in examples:
            if ex['was_corrected']:
                ex['true_trust'] = 0.3  # Low trust (was wrong)
            elif ex['time_until_update']:
                # Trust decays based on how long it stayed valid
                days = ex['time_until_update']
                ex['true_trust'] = min(1.0, 0.5 + (days / 365) * 0.5)
            else:
                ex['true_trust'] = 0.9  # High trust (still valid)
        
        return examples
    
    def build_policy_dataset(self):
        """Build dataset for policy learning."""
        
        # Get contradiction decisions with user feedback
        examples = self.db.query(
            """
            SELECT contradiction, context, applied_policy, 
                   was_correct, preferred_policy
            FROM policy_decisions
            WHERE was_correct IS NOT NULL
            """
        )
        
        # Label: preferred_policy if provided, else applied_policy if correct
        for ex in examples:
            if ex['preferred_policy']:
                ex['label'] = ex['preferred_policy']
            elif ex['was_correct']:
                ex['label'] = ex['applied_policy']
            else:
                # Policy was wrong, need to infer correct one
                ex['label'] = self._infer_correct_policy(ex)
        
        return examples
```

---

### 3.2 Model Training

**Training Manager:**

```python
class ModelTrainingManager:
    """Manages model training pipeline."""
    
    def train_fact_extractor(self, dataset):
        """Train or fine-tune fact extraction model."""
        
        # Load base model
        model = AutoModelForTokenClassification.from_pretrained(
            "dslim/bert-base-NER"
        )
        
        # Fine-tune on our data
        trainer = Trainer(
            model=model,
            args=TrainingArguments(
                output_dir='./models/fact_extractor',
                num_train_epochs=3,
                per_device_train_batch_size=16,
                evaluation_strategy="epoch",
                save_strategy="epoch",
                load_best_model_at_end=True,
                metric_for_best_model="f1"
            ),
            train_dataset=dataset['train'],
            eval_dataset=dataset['val'],
            compute_metrics=self._compute_ner_metrics
        )
        
        trainer.train()
        
        # Evaluate on test set
        test_results = trainer.evaluate(dataset['test'])
        
        # Save if better than baseline
        if test_results['f1'] > self.baseline_metrics['fact_extraction_f1']:
            trainer.save_model('./models/fact_extractor/best')
            return True
        else:
            print("New model not better than baseline")
            return False
    
    def train_trust_model(self, dataset):
        """Train trust score prediction model."""
        
        # Simple neural network
        model = TrustScoreNN(input_dim=10, hidden_dim=64, output_dim=1)
        
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()
        
        # Training loop
        for epoch in range(50):
            train_loss = self._train_epoch(
                model, dataset['train'], optimizer, criterion
            )
            val_loss = self._validate(model, dataset['val'], criterion)
            
            print(f"Epoch {epoch}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")
            
            # Early stopping
            if self._should_stop(val_loss):
                break
        
        # Evaluate on test set
        test_mse = self._evaluate(model, dataset['test'], criterion)
        
        # Save if better than baseline
        if test_mse < self.baseline_metrics['trust_score_mse']:
            torch.save(model.state_dict(), './models/trust_model/best.pth')
            return True
        else:
            return False
    
    def train_policy_classifier(self, dataset):
        """Train policy recommendation classifier."""
        
        # Random Forest (interpretable, fast)
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        
        X_train, y_train = dataset['train']['features'], dataset['train']['labels']
        X_val, y_val = dataset['val']['features'], dataset['val']['labels']
        
        model.fit(X_train, y_train)
        
        # Evaluate
        val_accuracy = model.score(X_val, y_val)
        
        # Save if better than baseline (random/rule-based)
        if val_accuracy > 0.7:
            joblib.dump(model, './models/policy_classifier/best.pkl')
            return True
        else:
            return False
```

---

### 3.3 Continuous Learning

**Automated Retraining:**

```python
class ContinuousLearner:
    """Automatically retrain models when new data is available."""
    
    def __init__(self, schedule: str = 'weekly'):
        self.schedule = schedule
        self.min_new_examples = 1000
    
    def check_and_retrain(self, component: str):
        """Check if retraining is needed and execute."""
        
        # Count new examples since last training
        new_examples = self.db.count_new_examples(
            component=component,
            since=self.last_training_date[component]
        )
        
        if new_examples < self.min_new_examples:
            print(f"Not enough new examples ({new_examples}/{self.min_new_examples})")
            return
        
        print(f"Retraining {component} with {new_examples} new examples")
        
        # Build dataset
        dataset = self.dataset_builder.build_dataset(component)
        
        # Train new model
        success = self.trainer.train(component, dataset)
        
        if success:
            # Deploy to A/B test
            self.deploy_to_ab_test(component)
        else:
            print(f"New model not better, keeping current version")
    
    def run_scheduled_retraining(self):
        """Run on schedule (weekly, monthly, etc.)."""
        
        for component in ['fact_extraction', 'trust_scores', 'policy']:
            try:
                self.check_and_retrain(component)
            except Exception as e:
                self.alert(f"Retraining failed for {component}: {e}")
```

---

## Phase 4: A/B Testing and Deployment (Month 4-8)

### 4.1 A/B Testing Framework

**Experiment Manager:**

```python
class ABTestManager:
    """Manages A/B tests for ML model deployment."""
    
    def create_experiment(
        self,
        name: str,
        component: str,
        model_version: str,
        traffic_percentage: float = 0.1
    ):
        """Create new A/B test experiment."""
        
        experiment = {
            'id': str(uuid.uuid4()),
            'name': name,
            'component': component,
            'control_version': self.current_versions[component],
            'treatment_version': model_version,
            'traffic_percentage': traffic_percentage,
            'start_date': datetime.now(),
            'status': 'running'
        }
        
        self.db.save_experiment(experiment)
        return experiment['id']
    
    def assign_user_to_group(self, user_id: str, experiment_id: str) -> str:
        """Assign user to control or treatment group."""
        
        # Deterministic assignment based on user_id hash
        hash_value = int(hashlib.sha256(
            f"{user_id}:{experiment_id}".encode()
        ).hexdigest(), 16)
        
        experiment = self.db.get_experiment(experiment_id)
        
        # Assign to treatment with traffic_percentage probability
        if (hash_value % 100) < (experiment['traffic_percentage'] * 100):
            return 'treatment'
        else:
            return 'control'
    
    def get_model_version(self, component: str, user_id: str) -> str:
        """Get model version for user based on active experiments."""
        
        # Check if user is in any active experiment
        active_experiments = self.db.get_active_experiments(component)
        
        for exp in active_experiments:
            group = self.assign_user_to_group(user_id, exp['id'])
            if group == 'treatment':
                return exp['treatment_version']
        
        # Default to control (current production version)
        return self.current_versions[component]
```

**Metrics Collection:**

```python
class ABTestMetrics:
    """Collect and analyze A/B test metrics."""
    
    def record_interaction(
        self,
        user_id: str,
        experiment_id: str,
        group: str,
        metrics: Dict[str, float]
    ):
        """Record metrics for an interaction."""
        
        self.db.execute(
            """
            INSERT INTO ab_test_results
            (experiment_id, user_id, group, timestamp, metrics)
            VALUES (?, ?, ?, ?, ?)
            """,
            (experiment_id, user_id, group, datetime.now(), json.dumps(metrics))
        )
    
    def analyze_experiment(self, experiment_id: str) -> Dict:
        """Analyze experiment results."""
        
        # Get metrics for both groups
        control_metrics = self._get_group_metrics(experiment_id, 'control')
        treatment_metrics = self._get_group_metrics(experiment_id, 'treatment')
        
        # Statistical significance test
        results = {}
        for metric_name in control_metrics.keys():
            results[metric_name] = {
                'control_mean': np.mean(control_metrics[metric_name]),
                'treatment_mean': np.mean(treatment_metrics[metric_name]),
                'improvement': self._calculate_improvement(
                    control_metrics[metric_name],
                    treatment_metrics[metric_name]
                ),
                'p_value': self._t_test(
                    control_metrics[metric_name],
                    treatment_metrics[metric_name]
                ),
                'sample_size_control': len(control_metrics[metric_name]),
                'sample_size_treatment': len(treatment_metrics[metric_name])
            }
        
        return results
    
    def should_deploy(self, experiment_id: str) -> bool:
        """Decide whether to deploy treatment to production."""
        
        results = self.analyze_experiment(experiment_id)
        
        # Deployment criteria:
        # 1. Statistically significant improvement (p < 0.05)
        # 2. Positive improvement on primary metric
        # 3. No regression on secondary metrics
        # 4. Sufficient sample size (>1000 per group)
        
        primary_metric = 'accuracy'
        
        if results[primary_metric]['sample_size_treatment'] < 1000:
            return False
        
        if results[primary_metric]['p_value'] > 0.05:
            return False
        
        if results[primary_metric]['improvement'] < 0:
            return False
        
        # Check for regressions
        for metric_name, metric_data in results.items():
            if metric_name == 'latency':
                # Allow up to 20% latency increase
                if metric_data['improvement'] > 0.2:
                    return False
        
        return True
```

---

### 4.2 Gradual Rollout

**Deployment Strategy:**

```python
class GradualRollout:
    """Gradually increase traffic to new model version."""
    
    def __init__(self):
        self.rollout_schedule = [0.1, 0.25, 0.5, 0.75, 1.0]
        self.check_interval_hours = 24
    
    def start_rollout(self, experiment_id: str):
        """Begin gradual rollout."""
        
        for traffic_pct in self.rollout_schedule:
            # Update traffic percentage
            self.ab_test_manager.update_traffic(experiment_id, traffic_pct)
            
            print(f"Rolled out to {traffic_pct*100}% of traffic")
            
            # Wait for data collection
            time.sleep(self.check_interval_hours * 3600)
            
            # Check metrics
            metrics = self.ab_test_metrics.analyze_experiment(experiment_id)
            
            # Stop if regression detected
            if self._has_regression(metrics):
                print("Regression detected, rolling back")
                self.rollback(experiment_id)
                return False
        
        # Full rollout successful
        self.promote_to_production(experiment_id)
        return True
    
    def _has_regression(self, metrics: Dict) -> bool:
        """Check if metrics show regression."""
        
        # Check key metrics
        if metrics['accuracy']['improvement'] < -0.05:
            return True
        
        if metrics['latency']['improvement'] > 0.3:
            return True
        
        if metrics['user_satisfaction']['improvement'] < -0.1:
            return True
        
        return False
```

---

## Phase 5: Monitoring and Maintenance

### 5.1 Production Monitoring

**Model Performance Monitor:**

```python
class ProductionMonitor:
    """Monitor model performance in production."""
    
    def track_predictions(
        self,
        model_name: str,
        prediction: Any,
        ground_truth: Optional[Any] = None
    ):
        """Track model predictions and compare to ground truth when available."""
        
        # Log prediction
        self.prediction_log.append({
            'model': model_name,
            'timestamp': datetime.now(),
            'prediction': prediction,
            'ground_truth': ground_truth
        })
        
        # Update metrics
        if ground_truth:
            self.accuracy_tracker.update(model_name, prediction, ground_truth)
        
        # Check for drift
        if self._detect_drift(model_name):
            self.alert(f"Drift detected in {model_name}")
    
    def _detect_drift(self, model_name: str) -> bool:
        """Detect distribution drift in predictions."""
        
        # Get recent predictions
        recent = self.prediction_log.get_recent(model_name, days=7)
        baseline = self.prediction_log.get_baseline(model_name)
        
        # Compare distributions (KL divergence)
        drift_score = self._calculate_drift(recent, baseline)
        
        return drift_score > self.drift_threshold
```

**Alert System:**

```python
class AlertSystem:
    """Alert on model performance issues."""
    
    def check_alerts(self):
        """Check for alert conditions."""
        
        for model_name in self.monitored_models:
            # Accuracy drop
            current_accuracy = self.metrics.get_accuracy(model_name, days=1)
            baseline_accuracy = self.metrics.get_accuracy(model_name, days=30)
            
            if current_accuracy < baseline_accuracy - 0.1:
                self.send_alert(
                    f"Accuracy dropped for {model_name}: "
                    f"{current_accuracy:.2%} (baseline: {baseline_accuracy:.2%})"
                )
            
            # Latency spike
            current_latency = self.metrics.get_latency_p95(model_name, hours=1)
            if current_latency > self.latency_threshold:
                self.send_alert(
                    f"Latency spike for {model_name}: {current_latency:.0f}ms"
                )
            
            # Error rate
            error_rate = self.metrics.get_error_rate(model_name, hours=1)
            if error_rate > 0.05:
                self.send_alert(
                    f"High error rate for {model_name}: {error_rate:.2%}"
                )
```

---

## Summary

### Timeline

**Month 1-2:** Infrastructure setup
- Logging system deployed
- Feedback UI implemented
- Data collection active

**Month 3-4:** First model (Trust Scores)
- 10K+ training examples collected
- Model trained and evaluated
- A/B test deployed (10% traffic)
- Gradual rollout if successful

**Month 5-6:** Second model (Fact Extraction)
- Fine-tune on collected data
- Hybrid implementation
- Deploy and monitor

**Month 7-8:** Third model (Policy Learning)
- Train on feedback data
- Deploy personalized policies
- Monitor user satisfaction

**Month 9+:** Continuous improvement
- Weekly retraining
- Ongoing A/B tests
- Model updates based on performance

### Key Success Factors

1. **Start collecting data immediately** (don't wait for models)
2. **Make feedback frictionless** (one-click, contextual)
3. **Use implicit signals** (corrections, confirmations)
4. **A/B test everything** (never deploy without validation)
5. **Monitor closely** (detect regressions early)
6. **Kill bad models** (don't keep models that don't improve metrics)

### Expected Outcomes

- **Training data:** 50K+ labeled examples after 6 months
- **Model improvements:** 3-4 production models deployed
- **User satisfaction:** +25% from personalization
- **Continuous learning:** Weekly model updates from production data
