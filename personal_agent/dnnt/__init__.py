"""
DNNT (Dynamic Neuromorphic Neuro-Transformer)
=============================================
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
from .model import (
    DNNTMicroTransformer,
    DNNTConfig,
    SimpleTokenizer,
    expand_model_vocab,
    MicroTransformer,
    MicroTransformerConfig,
)
from .trainer import ReasoningTrainer
from .inference import ReasoningInference
from .trust_gate import TrustGate, TrustGateConfig
from .tokenizer_bpe import SentencePieceTokenizer, create_tokenizer, load_tokenizer
from .train_tokenizer import collect_tokenizer_corpus, train_and_save_tokenizer
from .background_learning import (
    BackgroundLearningConfig,
    BackgroundLearningState,
    DNNTBackgroundLearner,
    run_background_learning_once,
    run_background_learning_forever,
)

__all__ = [
    'DataExtractor',
    'TrainingExample', 
    'DNNTMicroTransformer',
    'DNNTConfig',
    'MicroTransformer',
    'MicroTransformerConfig',
    'SimpleTokenizer',
    'expand_model_vocab',
    'ReasoningTrainer',
    'ReasoningInference',
    'TrustGate',
    'TrustGateConfig',
    'SentencePieceTokenizer',
    'create_tokenizer',
    'load_tokenizer',
    'collect_tokenizer_corpus',
    'train_and_save_tokenizer',
    'BackgroundLearningConfig',
    'BackgroundLearningState',
    'DNNTBackgroundLearner',
    'run_background_learning_once',
    'run_background_learning_forever',
]
