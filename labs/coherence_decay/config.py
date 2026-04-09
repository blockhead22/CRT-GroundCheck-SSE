"""Coherence Decay Experiment — Configuration"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LAB_DIR = Path(__file__).parent
PROMPTS_DIR = LAB_DIR / "prompts"
RESULTS_DIR = LAB_DIR / "results"
RAW_DIR = RESULTS_DIR / "raw"
CHARTS_DIR = RESULTS_DIR / "charts"

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---------------------------------------------------------------------------
# Models — tiers
# ---------------------------------------------------------------------------
MODELS = {
    "local_small": {
        "name": "llama3.2:latest",
        "params": "3B",
        "provider": "ollama",
        "supports_logprobs": True,
    },
    "local_medium": {
        "name": "gemma3:latest",
        "params": "4B",
        "provider": "ollama",
        "supports_logprobs": True,
    },
    "local_large": {
        "name": "qwen3:14b",
        "params": "14B",
        "provider": "ollama",
        "supports_logprobs": True,
    },
    "cloud": {
        "name": "gpt-4o-mini",
        "params": "~8B?",
        "provider": "openai",
        "supports_logprobs": True,
    },
}

# ---------------------------------------------------------------------------
# Generation strategies (levels)
# ---------------------------------------------------------------------------
STRATEGIES = {
    "L0_free_500": {
        "description": "Free-run 500 tokens, no intervention",
        "max_tokens": 500,
        "burst_size": None,  # No burst — single generation
        "reanchor": False,
        "entropy_check": False,
        "contradiction_check": False,
    },
    "L1_free_200": {
        "description": "Free-run 200 tokens",
        "max_tokens": 200,
        "burst_size": None,
        "reanchor": False,
        "entropy_check": False,
        "contradiction_check": False,
    },
    "L2_burst_50": {
        "description": "50-token bursts, re-anchor between",
        "max_tokens": 500,
        "burst_size": 50,
        "reanchor": True,
        "entropy_check": False,
        "contradiction_check": False,
    },
    "L3_burst_25_entropy": {
        "description": "25-token bursts, re-anchor + entropy check",
        "max_tokens": 500,
        "burst_size": 25,
        "reanchor": True,
        "entropy_check": True,
        "contradiction_check": False,
    },
    "L4_full_scaffold": {
        "description": "25-token bursts, re-anchor + entropy + contradiction",
        "max_tokens": 500,
        "burst_size": 25,
        "reanchor": True,
        "entropy_check": True,
        "contradiction_check": True,
    },
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers, same for all

# Entropy thresholds
ENTROPY_HIGH_THRESHOLD = 2.5     # Flag span as uncertain above this
ENTROPY_RERUN_THRESHOLD = 3.0    # Trigger re-generation above this

# Temperature for all runs (deterministic-ish)
TEMPERATURE = 0.3

# Domains
DOMAINS = ["programming", "narrative", "memory"]
