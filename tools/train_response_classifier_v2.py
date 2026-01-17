"""
Response Type Classifier Trainer V2

Trains a response-type classifier for CRT's learned gate system.

Input: JSONL file with training examples
Output: Trained sklearn model (joblib)

Response types:
- factual: Direct factual queries (What is my X?)
- explanatory: Synthesis/explanation requests (How/Why questions)
- conversational: Chat/acknowledgment
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report


def extract_manual_features(text: str) -> Dict:
    """Extract manual linguistic features from text."""
    text_lower = text.lower().strip()
    words = text.split()
    
    question_words = ['what', 'where', 'when', 'who', 'how', 'why', 'which', 'whose', 'whom']
    imperative_words = ['tell', 'show', 'explain', 'describe', 'list', 'give']
    
    return {
        'text': text,
        'has_question_word': int(any(w in text_lower for w in question_words)),
        'starts_with_question': int(words[0].lower() in question_words if words else 0),
        'starts_with_imperative': int(words[0].lower() in imperative_words if words else 0),
        'has_you_your': int(any(w in text_lower for w in ['you', 'your', "you're", 'yours'])),
        'has_question_mark': int('?' in text),
        'word_count': len(words),
        'avg_word_length': sum(len(w) for w in words) / max(len(words), 1),
        'question_word_count': sum(1 for w in words if w.lower() in question_words),
    }


class ResponseTypeClassifierModel:
    """Response type classifier combining TF-IDF + manual features."""
    
    def __init__(self):
        self.tfidf = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2,
        )
        self.classifier = LogisticRegression(
            max_iter=1000,
            class_weight='balanced',
            random_state=42,
        )
        self.classes_ = None
    
    def fit(self, X: List[Dict], y: List[str]):
        """Train the classifier."""
        texts = [x['text'] for x in X]
        manual_features = np.array([
            [
                x['has_question_word'],
                x['starts_with_question'],
                x['starts_with_imperative'],
                x['has_you_your'],
                x['has_question_mark'],
                x['word_count'],
                x['avg_word_length'],
                x['question_word_count'],
            ]
            for x in X
        ])
        
        tfidf_features = self.tfidf.fit_transform(texts)
        combined_features = np.hstack([
            tfidf_features.toarray(),
            manual_features,
        ])
        
        self.classifier.fit(combined_features, y)
        self.classes_ = self.classifier.classes_
        return self
    
    def predict(self, X: List[Dict]) -> np.ndarray:
        """Predict response types."""
        texts = [x['text'] for x in X]
        manual_features = np.array([
            [
                x['has_question_word'],
                x['starts_with_question'],
                x['starts_with_imperative'],
                x['has_you_your'],
                x['has_question_mark'],
                x['word_count'],
                x['avg_word_length'],
                x['question_word_count'],
            ]
            for x in X
        ])
        
        tfidf_features = self.tfidf.transform(texts)
        combined_features = np.hstack([
            tfidf_features.toarray(),
            manual_features,
        ])
        
        return self.classifier.predict(combined_features)
    
    def predict_proba(self, X: List[Dict]) -> np.ndarray:
        """Predict probabilities for each class."""
        texts = [x['text'] for x in X]
        manual_features = np.array([
            [
                x['has_question_word'],
                x['starts_with_question'],
                x['starts_with_imperative'],
                x['has_you_your'],
                x['has_question_mark'],
                x['word_count'],
                x['avg_word_length'],
                x['question_word_count'],
            ]
            for x in X
        ])
        
        tfidf_features = self.tfidf.transform(texts)
        combined_features = np.hstack([
            tfidf_features.toarray(),
            manual_features,
        ])
        
        return self.classifier.predict_proba(combined_features)


class ResponseTypeClassifier:
    """High-level wrapper for easy prediction."""
    
    def __init__(self, model):
        self.model = model
    
    def predict(self, questions):
        """Predict response types for questions (string or list)."""
        if isinstance(questions, str):
            questions = [questions]
        
        features = [extract_manual_features(q) for q in questions]
        predictions = self.model.predict(features)
        
        return predictions.tolist() if len(questions) > 1 else predictions[0]
    
    def predict_proba(self, questions):
        """Predict probabilities for each response type."""
        if isinstance(questions, str):
            questions = [questions]
        
        features = [extract_manual_features(q) for q in questions]
        return self.model.predict_proba(features)


def main():
    parser = argparse.ArgumentParser(description="Train response type classifier")
    parser.add_argument("--input", type=Path, default=Path("training_data/bootstrap_v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("models/response_classifier.joblib"))
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()
    
    # Load training data
    print(f"Loading training data from {args.input}...")
    examples = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    
    print(f"Total examples: {len(examples)}")
    
    # Extract features and labels
    X = [extract_manual_features(ex['question']) for ex in examples]
    y = [ex['response_type'] for ex in examples]
    
    # Label distribution
    from collections import Counter
    label_counts = Counter(y)
    print("Label distribution:")
    for label, count in sorted(label_counts.items()):
        pct = 100 * count / len(y)
        print(f"  {label}: {count} ({pct:.1f}%)")
    
    # Train/val split
    print("\nExtracting features...")
    X_train, X_val, y_train, y_val = train_test_split(
        X, y,
        test_size=args.test_size,
        random_state=42,
        stratify=y,
    )
    
    # Train classifier
    print("Training classifier...")
    model = ResponseTypeClassifierModel()
    model.fit(X_train, y_train)
    
    # Evaluate
    train_preds = model.predict(X_train)
    val_preds = model.predict(X_val)
    
    train_acc = (train_preds == np.array(y_train)).mean()
    val_acc = (val_preds == np.array(y_val)).mean()
    
    print(f"\nTraining accuracy: {train_acc:.3f}")
    print(f"Validation accuracy: {val_acc:.3f}")
    
    print("\nValidation Classification Report:")
    print(classification_report(y_val, val_preds))
    
    # Wrap and save
    classifier = ResponseTypeClassifier(model)
    
    print(f"Saving model to {args.output}...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, args.output)
    print(f"✓ Model saved to {args.output}")
    
    # Test predictions
    print("\nTest predictions:")
    test_questions = [
        "What is my name?",
        "How does memory work?",
        "Thanks for the help!",
    ]
    for q in test_questions:
        pred = classifier.predict(q)
        print(f"  '{q}' → {pred}")


if __name__ == "__main__":
    main()
