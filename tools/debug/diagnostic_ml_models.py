"""ML Model Verification Script"""
import pickle
from pathlib import Path

print('=' * 70)
print('ML MODEL VERIFICATION')
print('=' * 70)

# Check if models exist
model_dir = Path('belief_revision/models')
xgb_path = model_dir / 'xgboost.pkl'
policy_path = model_dir / 'policy_xgboost.pkl'

print(f'\nModel directory: {model_dir.absolute()}')
print(f'XGBoost model exists: {xgb_path.exists()}')
print(f'Policy model exists: {policy_path.exists()}')

if xgb_path.exists():
    print(f'XGBoost size: {xgb_path.stat().st_size / 1024:.1f} KB')
else:
    print('ERROR: XGBoost model not found!')

if policy_path.exists():
    print(f'Policy model size: {policy_path.stat().st_size / 1024:.1f} KB')
else:
    print('ERROR: Policy model not found!')

# Try loading models
print('\nAttempting to load models...')

belief_classifier = None
policy_classifier = None

try:
    with open(xgb_path, 'rb') as f:
        belief_classifier = pickle.load(f)
    print('✅ Belief classifier loaded successfully')
    print(f'   Type: {type(belief_classifier)}')
    if hasattr(belief_classifier, 'classes_'):
        print(f'   Classes: {belief_classifier.classes_}')
    if hasattr(belief_classifier, 'n_features_in_'):
        print(f'   Expected features: {belief_classifier.n_features_in_}')
except Exception as e:
    print(f'❌ ERROR loading belief classifier: {e}')
    import traceback
    traceback.print_exc()

try:
    with open(policy_path, 'rb') as f:
        policy_classifier = pickle.load(f)
    print('✅ Policy classifier loaded successfully')
    print(f'   Type: {type(policy_classifier)}')
    if hasattr(policy_classifier, 'classes_'):
        print(f'   Classes: {policy_classifier.classes_}')
    if hasattr(policy_classifier, 'n_features_in_'):
        print(f'   Expected features: {policy_classifier.n_features_in_}')
except Exception as e:
    print(f'❌ ERROR loading policy classifier: {e}')
    import traceback
    traceback.print_exc()

# Test prediction
print('\n' + '=' * 70)
print('TEST PREDICTION WITH DUMMY DATA')
print('=' * 70)

if belief_classifier:
    try:
        import numpy as np
        
        # Create dummy feature vector (18 features from Phase 2)
        dummy_features = np.array([
            0.3, 0.2, 10.0, 0.9, 1, 5, 3, 5, 2, 0, 0, 0, 0, 0, 1, 0.9, 0.85, 0.15
        ]).reshape(1, -1)
        
        print(f'\nDummy feature vector shape: {dummy_features.shape}')
        n_features = belief_classifier.n_features_in_ if hasattr(belief_classifier, 'n_features_in_') else 'unknown'
        print(f'Expected features: {n_features}')
        
        # Predict category
        category_pred = belief_classifier.predict(dummy_features)
        categories = ['REFINEMENT', 'REVISION', 'TEMPORAL', 'CONFLICT']
        print(f'\n✅ Category prediction: {categories[category_pred[0]]}')
        
        # Get probabilities
        if hasattr(belief_classifier, 'predict_proba'):
            proba = belief_classifier.predict_proba(dummy_features)
            print(f'   Confidence: {proba[0].max():.3f}')
            for i, cat in enumerate(categories):
                print(f'   {cat}: {proba[0][i]:.3f}')
        
        print('\n✅ ML models are functional and can make predictions')
        
    except Exception as e:
        print(f'\n❌ ERROR during test prediction: {e}')
        import traceback
        traceback.print_exc()
else:
    print('❌ Cannot test prediction - belief classifier not loaded')
