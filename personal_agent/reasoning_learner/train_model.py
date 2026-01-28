#!/usr/bin/env python
"""
Train the Reasoning Pattern Learner

Usage:
    python -m personal_agent.reasoning_learner.train_model --synthetic 1000 --epochs 20

This will:
1. Generate synthetic training examples
2. Extract real examples from your reasoning trace databases
3. Train a micro-transformer to mimic LLM thinking patterns
4. Save the model for inference
"""

import argparse
import torch
from pathlib import Path

from .trainer import quick_train, ReasoningTrainer, TrainingConfig
from .model import MicroTransformer, MicroTransformerConfig, SimpleTokenizer
from .synthetic_generator import SyntheticGenerator
from .data_extractor import DataExtractor


def main():
    parser = argparse.ArgumentParser(description='Train the Reasoning Pattern Learner')
    parser.add_argument('--synthetic', type=int, default=500, help='Number of synthetic examples to generate')
    parser.add_argument('--epochs', type=int, default=10, help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=16, help='Batch size')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--hidden-dim', type=int, default=256, help='Hidden dimension')
    parser.add_argument('--layers', type=int, default=4, help='Number of transformer layers')
    parser.add_argument('--output-dir', type=str, default='models/reasoning_learner', help='Output directory')
    parser.add_argument('--no-gpu', action='store_true', help='Disable GPU')
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("REASONING PATTERN LEARNER - TRAINING")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Synthetic examples: {args.synthetic}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Learning rate: {args.lr}")
    print(f"  Hidden dim: {args.hidden_dim}")
    print(f"  Layers: {args.layers}")
    print(f"  Output: {args.output_dir}")
    print(f"  GPU: {'Disabled' if args.no_gpu else 'Auto'}")
    
    # Check GPU
    device = 'cpu' if args.no_gpu else ('cuda' if torch.cuda.is_available() else 'cpu')
    if device == 'cuda':
        print(f"\n  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    print("\n" + "-" * 70)
    
    # Generate data
    print("\n1. Preparing training data...")
    
    # Synthetic data
    print("   Generating synthetic examples...")
    generator = SyntheticGenerator()
    synthetic_examples = generator.generate_batch(args.synthetic)
    print(f"   Generated {len(synthetic_examples)} synthetic examples")
    
    # Real data from databases
    print("   Extracting real examples from databases...")
    extractor = DataExtractor()
    real_examples = extractor.extract_all()
    print(f"   Extracted {len(real_examples)} real examples")
    
    # Combine and shuffle
    import random
    all_examples = synthetic_examples + real_examples
    random.shuffle(all_examples)
    
    # Split
    split_idx = int(len(all_examples) * 0.9)
    train_examples = all_examples[:split_idx]
    val_examples = all_examples[split_idx:]
    
    print(f"\n   Total: {len(all_examples)} examples")
    print(f"   Train: {len(train_examples)}")
    print(f"   Val:   {len(val_examples)}")
    
    # Create model
    print("\n2. Initializing model...")
    
    model_config = MicroTransformerConfig(
        vocab_size=8000,
        hidden_dim=args.hidden_dim,
        num_layers=args.layers,
        num_heads=4,
        max_seq_length=512,
        dropout=0.1,
    )
    
    model = MicroTransformer(model_config)
    tokenizer = SimpleTokenizer()
    
    print(f"   Parameters: {model.n_params:,}")
    print(f"   Size: ~{model.n_params * 4 / 1024 / 1024:.1f} MB")
    
    # Training config
    steps_per_epoch = max(1, len(train_examples) // args.batch_size)
    max_steps = steps_per_epoch * args.epochs
    
    train_config = TrainingConfig(
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_steps=max_steps,
        save_every=max(100, max_steps // 5),
        eval_every=max(50, max_steps // 10),
        log_every=10,
        device=device,
        mixed_precision=(device == 'cuda'),
        output_dir=args.output_dir,
    )
    
    # Create trainer
    print(f"\n3. Starting training...")
    print(f"   Max steps: {max_steps}")
    print(f"   Device: {device}")
    
    trainer = ReasoningTrainer(
        config=train_config,
        tokenizer=tokenizer,
        train_examples=train_examples,
        val_examples=val_examples,
        model=model,
    )
    
    # Resume if specified
    if args.resume:
        print(f"   Resuming from: {args.resume}")
        trainer.load_checkpoint(args.resume)
    
    # Train
    trainer.train()
    
    # Test
    print("\n4. Testing generation...")
    
    test_cases = [
        ("What is my name?", ["name=Nick (0.95)"]),
        ("What is 7 + 5?", []),
        ("Hello!", ["name=Nick (0.95)"]),
        ("What's my favorite color?", ["favorite_color=blue (0.85)"]),
    ]
    
    for query, facts in test_cases:
        print(f"\n   Query: {query}")
        print(f"   Facts: {facts}")
        thinking, response = trainer.generate_sample(query, facts)
        print(f"   Thinking: {thinking[:80]}..." if len(thinking) > 80 else f"   Thinking: {thinking}")
        print(f"   Response: {response}")
    
    print("\n" + "=" * 70)
    print("Training complete!")
    print(f"\nModel saved to: {args.output_dir}/model")
    print(f"Best model at:  {args.output_dir}/best_model")
    print("\nTo use in your API:")
    print("  from personal_agent.reasoning_learner import ReasoningInference")
    print(f"  engine = ReasoningInference('{args.output_dir}/model')")
    print("  result = engine.generate('What is my name?', ['name=Nick'])")
    print("=" * 70)


if __name__ == "__main__":
    main()
