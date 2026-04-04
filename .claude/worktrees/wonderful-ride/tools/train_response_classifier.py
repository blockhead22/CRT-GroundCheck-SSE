"""
Response Type Classifier Trainer

Trains a classifier to predict response type (factual/explanatory/conversational)
from question text. Used by gradient gates to select appropriate thresholds.

Model: Simple sklearn pipeline (fast training, small size, good performance)
- TfidfVectorizer for text features
- LogisticRegression for classification
- Can upgrade to DistilBERT later if needed

Training data sources:
1. Bootstrap data (stress test runs)
2. User corrections (active learning)

Usage:
    python tools/train_response_classifier.py --input training_data/bootstrap_v1.jsonl --output models/response_classifier.joblib
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np


def load_training_data(input_file: Path) -> Tuple[List[str], List[str], List[Dict]]:
    """Load training data from JSONL."""
    questions = []
    labels = []
    metadata = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            example = json.loads(line)
            questions.append(example['question'])
            labels.append(example.get('response_type', 'conversational'))
            metadata.append(example)
    
    return questions, labels, metadata


def extract_features(questions: List[str]) -> np.ndarray:
    """
    Extract text features from questions.
    
    Features:
    - TF-IDF on words
    - Question word presence
    - Sentence structure
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler
    
    # TF-IDF features
    vectorizer = TfidfVectorizer(
        max_features=500,
        ngram_range=(1, 2),
        stop_words='english',
        lowercase=True,
    )
    
    tfidf_features = vectorizer.fit_transform(questions)
    
    # Hand-crafted features
    manual_features = []
    for q in questions:
        q_lower = q.lower().strip()
        
        features = [
            1.0 if any(w in q_lower for w in ['what', 'where', 'when', 'who']) else 0.0,
            1.0 if any(w in q_lower for w in ['how', 'why']) else 0.0,
            1.0 if q_lower.split()[0] in ['what', 'where', 'when', 'who', 'how', 'why'] else 0.0,
            1.0 if '?' in q else 0.0,
            1.0 if any(w in q_lower for w in ['my', 'i', 'me']) else 0.0,
            1.0 if any(w in q_lower for w in ['you', 'your']) else 0.0,
            len(q),
            len(q.split()),
        ]
        manual_features.append(features)
    
    manual_features = np.array(manual_features)
    
    # Combine features
    from scipy.sparse import hstack, csr_matrix
    combined = hstack([tfidf_features, csr_matrix(manual_features)])
    
    return combined, vectorizer


def train_classifier(X_train, y_train, X_val, y_val):
    """Train logistic regression classifier."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report
    
    clf = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',
        random_state=42,
        C=1.0,
    )
    
    print("Training classifier...")
    clf.fit(X_train, y_train)
    
    # Evaluate
    train_pred = clf.predict(X_train)
    val_pred = clf.predict(X_val)
    
    train_acc = accuracy_score(y_train, train_pred)
    val_acc = accuracy_score(y_val, val_pred)
    
    print(f"\nTraining accuracy: {train_acc:.3f}")
    print(f"Validation accuracy: {val_acc:.3f}")
    
    print("\nValidation Classification Report:")
    print(classification_report(y_val, val_pred))
    
    return clf, val_acc


def create_pipeline(vectorizer, clf):
    """Create sklearn pipeline for easy prediction."""
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer
    
    # Pipeline: text -> features -> classifier
    class ResponseTypeClassifier:
        def __init__(self, vectorizer, clf):
            self.vectorizer = vectorizer
            self.clf = clf
        
        def predict(self, questions):
            """Predict response types for questions."""
            if isinstance(questions, str):
                questions = [questions]
            
            # Extract TF-IDF
            tfidf = self.vectorizer.transform(questions)
            
            # Extract manual features
            manual_features = []
            for q in questions:
                q_lower = q.lower().strip()
                features = [
                    1.0 if any(w in q_lower for w in ['what', 'where', 'when', 'who']) else 0.0,
                    1.0 if any(w in q_lower for w in ['how', 'why']) else 0.0,
                    1.0 if q_lower.split()[0] in ['what', 'where', 'when', 'who', 'how', 'why'] else 0.0,
                    1.0 if '?' in q else 0.0,
                    1.0 if any(w in q_lower for w in ['my', 'i', 'me']) else 0.0,
                    1.0 if any(w in q_lower for w in ['you', 'your']) else 0.0,
                    len(q),
                    len(q.split()),
                ]
                manual_features.append(features)
            
            from scipy.sparse import hstack, csr_matrix
            X = hstack([tfidf, csr_matrix(manual_features)])
            
            return self.clf.predict(X)
        
        def predict_proba(self, questions):
            """Predict probabilities."""
            if isinstance(questions, str):
                questions = [questions]
            
            tfidf = self.vectorizer.transform(questions)
            manual_features = []
            for q in questions:
                q_lower = q.lower().strip()
                features = [
                    1.0 if any(w in q_lower for w in ['what', 'where', 'when', 'who']) else 0.0,
                    1.0 if any(w in q_lower for w in ['how', 'why']) else 0.0,
                    1.0 if q_lower.split()[0] in ['what', 'where', 'when', 'who', 'how', 'why'] else 0.0,
                    1.0 if '?' in q else 0.0,
                    1.0 if any(w in q_lower for w in ['my', 'i', 'me']) else 0.0,
                    1.0 if any(w in q_lower for w in ['you', 'your']) else 0.0,
                    len(q),
                    len(q.split()),
                ]
                manual_features.append(features)
            
            from scipy.sparse import hstack, csr_matrix
            X = hstack([tfidf, csr_matrix(manual_features)])
            
            return self.clf.predict_proba(X)
    
    return ResponseTypeClassifier(vectorizer, clf)


def main():
    parser = argparse.ArgumentParser(description="Train response type classifier")
    parser.add_argument('--input', type=Path, required=True,
                       help='Input JSONL training data')
    parser.add_argument('--output', type=Path, required=True,
                       help='Output model path (.joblib)')
    parser.add_argument('--val-split', type=float, default=0.2,
                       help='Validation split ratio')
    
    args = parser.parse_args()
    
    print(f"Loading training data from {args.input}...")
    questions, labels, metadata = load_training_data(args.input)
    
    print(f"Total examples: {len(questions)}")
    from collections import Counter
    label_counts = Counter(labels)
    print("Label distribution:")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count} ({count/len(labels)*100:.1f}%)")
    
    # Split train/val
    from sklearn.model_selection import train_test_split
    
    indices = np.arange(len(questions))
    train_idx, val_idx = train_test_split(
        indices, 
        test_size=args.val_split, 
        random_state=42,
        stratify=labels
    )
    
    questions_train = [questions[i] for i in train_idx]
    labels_train = [labels[i] for i in train_idx]
    questions_val = [questions[i] for i in val_idx]
    labels_val = [labels[i] for i in val_idx]
    
    # Extract features
    print("\nExtracting features...")
    X_all, vectorizer = extract_features(questions)
    X_train = X_all[train_idx]
    X_val = X_all[val_idx]
    
    # Train
    clf, val_acc = train_classifier(X_train, labels_train, X_val, labels_val)
    
    # Create pipeline
    pipeline = create_pipeline(vectorizer, clf)
    
    # Save model
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(pipeline, args.output)
    
    print(f"\n✓ Model saved to {args.output}")
    print(f"Validation accuracy: {val_acc:.1%}")
    
    # Test predictions
    print("\nTest predictions:")
    test_questions = [
        "What is my name?",
        "How would you implement a database?",
        "Hello!",
        "Where do I work?",
        "Why is the sky blue?",
    ]
    
    predictions = pipeline.predict(test_questions)
    for q, pred in zip(test_questions, predictions):
        print(f"  {pred:20} | {q}")


if __name__ == '__main__':
    main()
