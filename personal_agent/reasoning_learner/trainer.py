"""
Trainer - Training loop for the micro-transformer with GPU support
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import random

from .model import MicroTransformer, MicroTransformerConfig, SimpleTokenizer
from .data_extractor import TrainingExample


@dataclass
class TrainingConfig:
    """Training configuration."""
    # Data
    batch_size: int = 16
    max_seq_length: int = 512
    
    # Optimization
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    warmup_steps: int = 100
    max_steps: int = 10000
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    
    # Checkpointing
    save_every: int = 500
    eval_every: int = 100
    log_every: int = 10
    
    # Device
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    mixed_precision: bool = True
    
    # Paths
    output_dir: str = 'models/reasoning_learner'
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)


class ReasoningDataset(Dataset):
    """Dataset for reasoning pattern learning."""
    
    def __init__(
        self, 
        examples: List[TrainingExample],
        tokenizer: SimpleTokenizer,
        max_length: int = 512
    ):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __len__(self) -> int:
        return len(self.examples)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        example = self.examples[idx]
        
        # Format as training sequence
        text = example.to_training_format()
        
        # Tokenize
        tokens = self.tokenizer.encode(text, add_special_tokens=True)
        
        # Truncate or pad
        if len(tokens) > self.max_length:
            tokens = tokens[:self.max_length]
        else:
            tokens = tokens + [self.tokenizer.special_tokens['<pad>']] * (self.max_length - len(tokens))
            
        # Input and target (shifted by 1)
        input_ids = torch.tensor(tokens[:-1], dtype=torch.long)
        labels = torch.tensor(tokens[1:], dtype=torch.long)
        
        return {
            'input_ids': input_ids,
            'labels': labels,
        }


class ReasoningTrainer:
    """Trainer for the micro-transformer."""
    
    def __init__(
        self,
        config: TrainingConfig,
        tokenizer: SimpleTokenizer,
        train_examples: List[TrainingExample],
        val_examples: Optional[List[TrainingExample]] = None,
        model: Optional[MicroTransformer] = None,
    ):
        self.config = config
        self.tokenizer = tokenizer
        
        # Create model if not provided
        if model is None:
            model_config = MicroTransformerConfig(vocab_size=tokenizer.vocab_size)
            model = MicroTransformer(model_config)
        
        self.model = model.to(self.config.device)
        
        # Datasets
        self.train_dataset = ReasoningDataset(train_examples, tokenizer, self.config.max_seq_length)
        self.val_dataset = ReasoningDataset(val_examples, tokenizer, self.config.max_seq_length) if val_examples else None
        
        # DataLoaders
        self.train_loader = DataLoader(
            self.train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=True if self.config.device == 'cuda' else False,
        )
        
        if self.val_dataset:
            self.val_loader = DataLoader(
                self.val_dataset,
                batch_size=self.config.batch_size,
                shuffle=False,
                num_workers=0,
            )
        
        # Optimizer
        self.optimizer = AdamW(
            model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            betas=(0.9, 0.95),
        )
        
        # Scheduler
        self.scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=self.config.max_steps,
            eta_min=self.config.learning_rate / 10,
        )
        
        # Mixed precision
        self.scaler = None
        if self.config.mixed_precision and self.config.device == 'cuda':
            try:
                self.scaler = torch.cuda.amp.GradScaler()
            except:
                self.scaler = None
        
        # Tracking
        self.global_step = 0
        self.best_val_loss = float('inf')
        self.train_losses = []
        self.val_losses = []
        
        # Setup output dir
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        
    def train_step(self, batch: Dict[str, torch.Tensor]) -> float:
        """Single training step."""
        self.model.train()
        
        input_ids = batch['input_ids'].to(self.config.device)
        labels = batch['labels'].to(self.config.device)
        
        # Mixed precision forward
        if self.scaler:
            with torch.cuda.amp.autocast():
                _, loss = self.model(input_ids, labels)
            
            # Backward
            self.scaler.scale(loss).backward()
            
            if (self.global_step + 1) % self.config.gradient_accumulation_steps == 0:
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.optimizer.zero_grad()
                self.scheduler.step()
        else:
            _, loss = self.model(input_ids, labels)
            loss.backward()
            
            if (self.global_step + 1) % self.config.gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                self.optimizer.step()
                self.optimizer.zero_grad()
                self.scheduler.step()
                
        return loss.item()
    
    @torch.no_grad()
    def evaluate(self) -> float:
        """Evaluate on validation set."""
        if not self.val_dataset:
            return 0.0
            
        self.model.eval()
        total_loss = 0
        num_batches = 0
        
        for batch in self.val_loader:
            input_ids = batch['input_ids'].to(self.config.device)
            labels = batch['labels'].to(self.config.device)
            
            _, loss = self.model(input_ids, labels)
            total_loss += loss.item()
            num_batches += 1
            
        return total_loss / max(num_batches, 1)
    
    def save_checkpoint(self, path: str, is_best: bool = False):
        """Save model checkpoint."""
        checkpoint = {
            'step': self.global_step,
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'scheduler_state': self.scheduler.state_dict(),
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss,
        }
        
        torch.save(checkpoint, path)
        
        # Save model separately for easy loading
        self.model.save(str(Path(path).parent / 'model'))
        self.tokenizer.save(str(Path(path).parent / 'model' / 'tokenizer.json'))
        
        if is_best:
            self.model.save(str(Path(path).parent / 'best_model'))
            self.tokenizer.save(str(Path(path).parent / 'best_model' / 'tokenizer.json'))
    
    def load_checkpoint(self, path: str):
        """Load checkpoint."""
        checkpoint = torch.load(path, map_location=self.config.device)
        
        self.global_step = checkpoint['step']
        self.model.load_state_dict(checkpoint['model_state'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state'])
        self.train_losses = checkpoint['train_losses']
        self.val_losses = checkpoint['val_losses']
        self.best_val_loss = checkpoint['best_val_loss']
        
    def train(self):
        """Main training loop."""
        print(f"Starting training on {self.config.device}")
        print(f"Model parameters: {self.model.n_params:,}")
        print(f"Training examples: {len(self.train_dataset)}")
        print(f"Validation examples: {len(self.val_dataset) if self.val_dataset else 0}")
        print(f"Batch size: {self.config.batch_size}")
        print(f"Max steps: {self.config.max_steps}")
        print("-" * 50)
        
        start_time = time.time()
        running_loss = 0
        num_batches = 0
        
        # Training loop
        epoch = 0
        while self.global_step < self.config.max_steps:
            epoch += 1
            
            for batch in self.train_loader:
                loss = self.train_step(batch)
                running_loss += loss
                num_batches += 1
                self.global_step += 1
                
                # Logging
                if self.global_step % self.config.log_every == 0:
                    avg_loss = running_loss / num_batches
                    lr = self.scheduler.get_last_lr()[0]
                    elapsed = time.time() - start_time
                    steps_per_sec = self.global_step / elapsed
                    
                    print(f"Step {self.global_step:5d} | Loss: {avg_loss:.4f} | LR: {lr:.2e} | {steps_per_sec:.1f} steps/s")
                    
                    self.train_losses.append((self.global_step, avg_loss))
                    running_loss = 0
                    num_batches = 0
                
                # Evaluation
                if self.global_step % self.config.eval_every == 0 and self.val_dataset:
                    val_loss = self.evaluate()
                    self.val_losses.append((self.global_step, val_loss))
                    
                    is_best = val_loss < self.best_val_loss
                    if is_best:
                        self.best_val_loss = val_loss
                        
                    print(f"         | Val Loss: {val_loss:.4f} {'*' if is_best else ''}")
                
                # Checkpointing
                if self.global_step % self.config.save_every == 0:
                    ckpt_path = Path(self.config.output_dir) / f'checkpoint_{self.global_step}.pt'
                    self.save_checkpoint(str(ckpt_path), is_best=(self.val_dataset and val_loss == self.best_val_loss))
                    print(f"         | Saved checkpoint to {ckpt_path}")
                
                if self.global_step >= self.config.max_steps:
                    break
                    
        # Final save
        final_path = Path(self.config.output_dir) / 'checkpoint_final.pt'
        self.save_checkpoint(str(final_path))
        
        total_time = time.time() - start_time
        print("-" * 50)
        print(f"Training complete! Total time: {total_time/60:.1f} minutes")
        print(f"Final checkpoint: {final_path}")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        
    @torch.no_grad()
    def generate_sample(self, query: str, facts: List[str], max_tokens: int = 256) -> Tuple[str, str]:
        """Generate a sample response for debugging."""
        self.model.eval()
        
        # Format input
        facts_str = "\n".join(f"- {f}" for f in facts) if facts else "(no facts)"
        prompt = f"<query>{query}</query>\n<facts>\n{facts_str}\n</facts>\n<think>"
        
        # Tokenize
        tokens = self.tokenizer.encode(prompt, add_special_tokens=True)
        input_ids = torch.tensor([tokens], device=self.config.device)
        
        # Generate
        output_ids = self.model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            temperature=0.7,
            stop_tokens=[self.tokenizer.special_tokens['</response>']],
        )
        
        # Decode
        output_text = self.tokenizer.decode(output_ids[0].tolist())
        
        # Extract thinking and response
        thinking = ""
        response = ""
        
        if "<think>" in output_text and "</think>" in output_text:
            start = output_text.index("<think>") + len("<think>")
            end = output_text.index("</think>")
            thinking = output_text[start:end].strip()
            
        if "<response>" in output_text and "</response>" in output_text:
            start = output_text.index("<response>") + len("<response>")
            end = output_text.index("</response>")
            response = output_text[start:end].strip()
        elif "<response>" in output_text:
            start = output_text.index("<response>") + len("<response>")
            response = output_text[start:].strip()
            
        return thinking, response


def quick_train(
    num_synthetic: int = 500,
    num_epochs_equivalent: int = 10,
    use_gpu: bool = True,
):
    """Quick training function for testing."""
    from .synthetic_generator import SyntheticGenerator
    from .data_extractor import DataExtractor
    
    print("=" * 60)
    print("REASONING PATTERN LEARNER - TRAINING")
    print("=" * 60)
    
    # Generate synthetic data
    print("\n1. Generating synthetic training data...")
    generator = SyntheticGenerator()
    synthetic_examples = generator.generate_batch(num_synthetic)
    print(f"   Generated {len(synthetic_examples)} synthetic examples")
    
    # Try to extract real data
    print("\n2. Extracting real training data from databases...")
    extractor = DataExtractor()
    real_examples = extractor.extract_all()
    print(f"   Extracted {len(real_examples)} real examples")
    
    # Combine
    all_examples = synthetic_examples + real_examples
    random.shuffle(all_examples)
    
    # Split train/val
    split_idx = int(len(all_examples) * 0.9)
    train_examples = all_examples[:split_idx]
    val_examples = all_examples[split_idx:]
    
    print(f"\n   Total: {len(all_examples)} examples")
    print(f"   Train: {len(train_examples)} examples")
    print(f"   Val: {len(val_examples)} examples")
    
    # Initialize model
    print("\n3. Initializing model...")
    config = MicroTransformerConfig(
        vocab_size=8000,
        hidden_dim=256,
        num_layers=4,
        num_heads=4,
        max_seq_length=512,
    )
    model = MicroTransformer(config)
    tokenizer = SimpleTokenizer()
    
    print(f"   Parameters: {model.n_params:,}")
    print(f"   Size: ~{model.n_params * 4 / 1024 / 1024:.1f} MB")
    
    # Training config
    device = 'cuda' if use_gpu and torch.cuda.is_available() else 'cpu'
    steps_per_epoch = len(train_examples) // 16
    max_steps = steps_per_epoch * num_epochs_equivalent
    
    train_config = TrainingConfig(
        batch_size=16,
        learning_rate=3e-4,
        max_steps=max_steps,
        save_every=max(100, max_steps // 5),
        eval_every=max(50, max_steps // 20),
        log_every=10,
        device=device,
        mixed_precision=(device == 'cuda'),
        output_dir='models/reasoning_learner',
    )
    
    print(f"\n4. Training on {device}...")
    print(f"   Max steps: {max_steps}")
    print(f"   ~{num_epochs_equivalent} epochs")
    
    # Train
    trainer = ReasoningTrainer(model, tokenizer, train_examples, val_examples, train_config)
    trainer.train()
    
    # Test generation
    print("\n5. Testing generation...")
    test_queries = [
        ("What is my name?", ["name=Nick (0.95)"]),
        ("What is 5 + 3?", []),
        ("Hello!", ["name=Nick (0.95)"]),
    ]
    
    for query, facts in test_queries:
        print(f"\n   Query: {query}")
        print(f"   Facts: {facts}")
        thinking, response = trainer.generate_sample(query, facts)
        print(f"   Thinking: {thinking[:100]}...")
        print(f"   Response: {response}")
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print(f"Model saved to: {train_config.output_dir}")
    print("=" * 60)
    
    return trainer


if __name__ == "__main__":
    quick_train(num_synthetic=500, num_epochs_equivalent=10)
