# Phase 3 Integration Guide
## Overview
This guide shows how to integrate the Phase 3 policy classifier into your CRT system.
The policy classifier predicts the best resolution action (OVERRIDE, PRESERVE, ASK_USER) for belief updates.

## Quick Start
### 1. Load the Model
```python
import joblib

# Load trained XGBoost policy classifier
policy_model = joblib.load('belief_revision/models/policy_xgboost.pkl')
```

### 2. Extract Features
```python
def extract_policy_features(belief_update):
    """
    Extract features from belief update.
    
    Args:
        belief_update: dict with:
            - old_value: str
            - new_value: str
            - query: str (user's statement)
            - slot: str (e.g., 'employer', 'location')
            - time_delta_days: int
            - confidence_old: float
            - confidence_new: float
            - category: str (from Phase 2 classifier)
    
    Returns:
        dict: Feature dictionary
    """
    # See belief_revision/scripts/phase3_integration_example.py
    # for full implementation
    ...
```

### 3. Make Predictions
```python
import numpy as np

def predict_resolution_action(belief_update, model):
    # Extract features
    features = extract_policy_features(belief_update)
    
    # Convert to feature vector (21 features)
    X = prepare_feature_vector(features)
    
    # Predict
    action_id = model.predict(X)[0]
    action = decode_action(action_id)  # 0→OVERRIDE, 1→PRESERVE, 2→ASK_USER
    
    # Get confidence
    confidence = model.predict_proba(X)[0].max()
    
    return action, confidence
```

## Example Predictions

### Example 1: Job change after 2 months
```python
belief_update = {
    'old_value': 'I work at Google',
    'new_value': 'I work at Amazon',
    'query': 'I work at Amazon',
    'slot': 'employer',
    'category': 'REVISION',
    'time_delta_days': 60,
    'confidence_old': 0.95,
    'confidence_new': 0.92
}

# Learned Policy Prediction
action, confidence = predict_resolution_action(belief_update)
# Result: action='PRESERVE', confidence=0.753

# Baseline Heuristic (for comparison)
baseline_action = baseline_heuristic(belief_update)
# Result: action='OVERRIDE'
```
**Learned Model**: `PRESERVE` (confidence: 75.3%)
**Baseline**: `OVERRIDE`
*Note: Learned model overrides baseline due to contextual signals.*

### Example 2: Adding hobby detail
```python
belief_update = {
    'old_value': 'I like hiking',
    'new_value': 'I like hiking and photography',
    'query': 'I also like photography',
    'slot': 'hobby',
    'category': 'REFINEMENT',
    'time_delta_days': 14,
    'confidence_old': 0.88,
    'confidence_new': 0.9
}

# Learned Policy Prediction
action, confidence = predict_resolution_action(belief_update)
# Result: action='PRESERVE', confidence=0.995

# Baseline Heuristic (for comparison)
baseline_action = baseline_heuristic(belief_update)
# Result: action='PRESERVE'
```
**Learned Model**: `PRESERVE` (confidence: 99.5%)
**Baseline**: `PRESERVE`

### Example 3: Explicit correction
```python
belief_update = {
    'old_value': 'I live in Seattle',
    'new_value': 'I live in Portland',
    'query': 'Actually, I meant I live in Portland',
    'slot': 'location',
    'category': 'REVISION',
    'time_delta_days': 1,
    'confidence_old': 0.8,
    'confidence_new': 0.95
}

# Learned Policy Prediction
action, confidence = predict_resolution_action(belief_update)
# Result: action='OVERRIDE', confidence=0.782

# Baseline Heuristic (for comparison)
baseline_action = baseline_heuristic(belief_update)
# Result: action='OVERRIDE'
```
**Learned Model**: `OVERRIDE` (confidence: 78.2%)
**Baseline**: `OVERRIDE`

### Example 4: Contradictory statement (low confidence)
```python
belief_update = {
    'old_value': 'I use Python',
    'new_value': 'I've never used Python',
    'query': 'I've never used Python',
    'slot': 'skill',
    'category': 'CONFLICT',
    'time_delta_days': 5,
    'confidence_old': 0.92,
    'confidence_new': 0.65
}

# Learned Policy Prediction
action, confidence = predict_resolution_action(belief_update)
# Result: action='ASK_USER', confidence=0.996

# Baseline Heuristic (for comparison)
baseline_action = baseline_heuristic(belief_update)
# Result: action='ASK_USER'
```
**Learned Model**: `ASK_USER` (confidence: 99.6%)
**Baseline**: `ASK_USER`

### Example 5: Age update (temporal)
```python
belief_update = {
    'old_value': 'I am 29 years old',
    'new_value': 'I am 30 years old',
    'query': 'I just turned 30',
    'slot': 'age',
    'category': 'TEMPORAL',
    'time_delta_days': 365,
    'confidence_old': 0.98,
    'confidence_new': 0.98
}

# Learned Policy Prediction
action, confidence = predict_resolution_action(belief_update)
# Result: action='OVERRIDE', confidence=0.992

# Baseline Heuristic (for comparison)
baseline_action = baseline_heuristic(belief_update)
# Result: action='OVERRIDE'
```
**Learned Model**: `OVERRIDE` (confidence: 99.2%)
**Baseline**: `OVERRIDE`

## Integration into CRT System
### Step 1: Add to Belief Update Pipeline
```python
# In your CRT belief update handler
def handle_belief_update(old_belief, new_belief, context):
    # 1. Detect belief update
    belief_update = detect_update(old_belief, new_belief, context)
    
    # 2. Classify update type (Phase 2)
    category = classify_belief_update(belief_update)
    belief_update['category'] = category
    
    # 3. Predict resolution action (Phase 3) ← NEW
    action, confidence = predict_resolution_action(belief_update)
    
    # 4. Execute action
    if action == 'OVERRIDE':
        # Replace old belief with new
        ledger.update_belief(belief_update['slot'], new_belief)
    elif action == 'PRESERVE':
        # Keep both in ledger
        ledger.add_belief(belief_update['slot'], new_belief, preserve_old=True)
    elif action == 'ASK_USER':
        # Request clarification
        return ask_user_for_clarification(belief_update)
```

### Step 2: Handle Low Confidence
```python
# If model confidence is low, fall back to asking user
CONFIDENCE_THRESHOLD = 0.7

action, confidence = predict_resolution_action(belief_update)

if confidence < CONFIDENCE_THRESHOLD:
    # Not confident enough, ask user
    action = 'ASK_USER'
```

### Step 3: Log Decisions for Improvement
```python
# Log all policy decisions for later analysis
log_policy_decision({
    'belief_update': belief_update,
    'predicted_action': action,
    'confidence': confidence,
    'user_feedback': None  # Fill in later if user disagrees
})
```

## Performance Summary
- **Test Accuracy**: 75.3% (XGBoost model)
- **Improvement over Baseline**: +13.9 percentage points
- **All Actions F1 Score**: ≥ 0.80 ✓
- **Inference Time**: <1ms per prediction

## Files Required
1. **Model**: `belief_revision/models/policy_xgboost.pkl` (or Random Forest)
2. **Feature Extractor**: Copy from `belief_revision/scripts/phase3_integration_example.py`
3. **Constants**: Import CORRECTION_WORDS, TEMPORAL_WORDS, slot type definitions

## Next Steps
1. Integrate into your CRT dialogue manager
2. Monitor prediction accuracy in production
3. Collect user feedback on policy decisions
4. Retrain model periodically with new data

## Support
See `PHASE3_SUMMARY.md` for detailed results and evaluation metrics.
