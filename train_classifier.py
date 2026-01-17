"""
Manual retraining script - trains response classifier on corrected data
"""

import sqlite3
import joblib
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import time

DB_PATH = "personal_agent/active_learning.db"
MODEL_PATH = "models/response_classifier_v1.joblib"

def main():
    print("="*80)
    print("RESPONSE CLASSIFIER TRAINING")
    print("="*80)
    
    # Load corrected data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT question, response_type_actual
        FROM gate_events
        WHERE response_type_actual IS NOT NULL
    """)
    
    data = cursor.fetchall()
    conn.close()
    
    print(f"\n✓ Loaded {len(data)} corrected examples")
    
    if len(data) < 20:
        print("✗ Need at least 20 examples to train")
        return
    
    # Prepare data
    questions = [row[0] for row in data]
    labels = [row[1] for row in data]
    
    # Count classes
    from collections import Counter
    counts = Counter(labels)
    print(f"\n Class distribution:")
    for label, count in counts.items():
        print(f"   {label:15} {count:4} ({count/len(labels)*100:.1f}%)")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        questions, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"\n✓ Train: {len(X_train)} examples")
    print(f"✓ Test:  {len(X_test)} examples")
    
    # Train TF-IDF vectorizer
    print(f"\n⚙ Training TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    
    # Train classifier
    print(f"⚙ Training Logistic Regression...")
    classifier = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    classifier.fit(X_train_vec, y_train)
    
    # Evaluate
    y_pred = classifier.predict(X_test_vec)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n{'='*80}")
    print(f"TRAINING RESULTS")
    print(f"{'='*80}")
    print(f"\n✓ Test Accuracy: {accuracy*100:.1f}%\n")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Save model
    Path(MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        'vectorizer': vectorizer,
        'classifier': classifier,
        'accuracy': accuracy,
        'trained_at': time.time(),
        'training_examples': len(data)
    }, MODEL_PATH)
    
    print(f"✓ Model saved to {MODEL_PATH}")
    
    # Log to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO training_runs 
        (started_at, finished_at, success, model_version, training_examples, validation_accuracy, model_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (time.time(), time.time(), 1, "v1", len(data), accuracy, MODEL_PATH))
    
    cursor.execute("""
        INSERT OR REPLACE INTO model_versions
        (version, created_at, model_path, accuracy, training_examples, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("v1", time.time(), MODEL_PATH, accuracy, len(data), 1))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Training run logged to database")
    print(f"\n{'='*80}")
    print(f"DONE - Restart API to load new model")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
