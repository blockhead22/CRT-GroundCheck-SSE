"""
Reasoning Pattern Learner
=========================
A micro-transformer that learns to generate responses by mimicking LLM thinking patterns.

Novel approach: Instead of just learning (query → response), we learn (query, facts → thinking → response)
This allows a tiny model to follow reasoning patterns learned from a larger model.

Components:
- DataExtractor: Pull training data from reasoning_traces DB
- SyntheticGenerator: Bootstrap training with synthetic examples
- MicroTransformer: ~2M param model that runs on CPU/GPU
- Trainer: Training loop with checkpointing
- ReasoningInference: Runtime inference with LLM fallback
"""

from .data_extractor import DataExtractor, TrainingExample
from .model import MicroTransformer, MicroTransformerConfig, SimpleTokenizer
from .trainer import ReasoningTrainer
from .inference import ReasoningInference

__all__ = [
    'DataExtractor',
    'TrainingExample', 
    'MicroTransformer',
    'MicroTransformerConfig',
    'SimpleTokenizer',
    'ReasoningTrainer',
    'ReasoningInference',
]
