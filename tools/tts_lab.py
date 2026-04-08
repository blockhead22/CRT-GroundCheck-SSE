"""
TTS Lab — StyleTTS2 voice synthesis experiments
================================================
Standalone lab. Not integrated into main pipeline.

Tests:
  1. Basic inference — generate speech from text, verify GPU works
  2. Style vector inspection — extract and visualize the 256-dim style space
  3. CRT-to-prosody mapping — map belief states to prosody parameters
  4. A/B comparison — same text, different "epistemic moods"

Usage:
  python tools/tts_lab.py                    # run all tests
  python tools/tts_lab.py --test basic       # just basic inference
  python tools/tts_lab.py --test style       # style vector analysis
  python tools/tts_lab.py --test crt         # CRT prosody mapping
  python tools/tts_lab.py --test ab          # A/B mood comparison

Output goes to: tools/tts_lab_output/
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import torch

OUTPUT_DIR = Path(__file__).parent / "tts_lab_output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_model():
    """Load StyleTTS2 with default LibriTTS checkpoint."""
    print("Loading StyleTTS2 (first run downloads ~1.5GB of checkpoints)...")
    t0 = time.time()
    from styletts2 import tts as styletts2_tts

    # Monkey-patch the phonemizer to strip pipe characters that gruut emits
    # but TextCleaner doesn't have in its symbol set (Windows issue)
    original_phonemize = styletts2_tts.StyleTTS2.__init__
    engine = styletts2_tts.StyleTTS2()

    # Wrap phonemize to strip unsupported chars
    _orig_phonemize = engine.phoneme_converter.phonemize
    def _clean_phonemize(text, **kwargs):
        result = _orig_phonemize(text, **kwargs)
        # Strip chars not in the TextCleaner symbol set
        from styletts2.text_utils import dicts
        return ''.join(c for c in result if c in dicts)
    engine.phoneme_converter.phonemize = _clean_phonemize

    elapsed = time.time() - t0
    print(f"Model loaded in {elapsed:.1f}s on {engine.device}")
    return engine


# ---------------------------------------------------------------------------
# Test 1: Basic inference
# ---------------------------------------------------------------------------
def test_basic(engine):
    """Generate a simple sentence and save WAV."""
    print("\n=== TEST 1: Basic Inference ===")
    text = "Hello, I am Aether. I remember what I believe, and I believe what I remember."
    out_path = str(OUTPUT_DIR / "basic_test.wav")

    t0 = time.time()
    audio = engine.inference(text, output_wav_file=out_path)
    elapsed = time.time() - t0

    duration_s = len(audio) / 24000
    print(f"  Generated {duration_s:.2f}s of audio in {elapsed:.2f}s")
    print(f"  RTF (real-time factor): {elapsed / duration_s:.2f}x")
    print(f"  Saved to: {out_path}")
    return audio


# ---------------------------------------------------------------------------
# Test 2: Style vector inspection
# ---------------------------------------------------------------------------
def test_style(engine):
    """Extract style vectors, analyze the 256-dim space."""
    print("\n=== TEST 2: Style Vector Inspection ===")

    # Generate with default voice, capture style
    from cached_path import cached_path
    from styletts2.tts import DEFAULT_TARGET_VOICE_URL
    default_voice = cached_path(DEFAULT_TARGET_VOICE_URL)
    ref_s = engine.compute_style(default_voice)

    style_np = ref_s.cpu().numpy().flatten()
    timbre = style_np[:128]   # ref_s[:, :128] — voice identity
    prosody = style_np[128:]  # ref_s[:, 128:] — rhythm/pitch/energy

    print(f"  Style vector shape: {style_np.shape}")
    print(f"  Timbre  (dims 0-127):  mean={timbre.mean():.4f}, std={timbre.std():.4f}, range=[{timbre.min():.4f}, {timbre.max():.4f}]")
    print(f"  Prosody (dims 128-255): mean={prosody.mean():.4f}, std={prosody.std():.4f}, range=[{prosody.min():.4f}, {prosody.max():.4f}]")

    # Save for later analysis
    np.save(str(OUTPUT_DIR / "default_style_vector.npy"), style_np)

    # Show which dimensions have highest variance (most expressive)
    print(f"\n  Top 5 prosody dims by magnitude:")
    prosody_mag = np.abs(prosody)
    top_dims = np.argsort(prosody_mag)[-5:][::-1]
    for d in top_dims:
        print(f"    dim {d + 128}: {prosody[d]:.4f}")

    return ref_s


# ---------------------------------------------------------------------------
# Test 3: CRT-to-prosody mapping
# ---------------------------------------------------------------------------

# Simulated CRT belief states
CRT_STATES = {
    "confident": {
        "trust": 0.95,
        "volatility": 0.05,
        "contradiction_count": 0,
        "drift": 0.02,
        "description": "High trust, stable, no contradictions"
    },
    "uncertain": {
        "trust": 0.45,
        "volatility": 0.30,
        "contradiction_count": 2,
        "drift": 0.15,
        "description": "Low trust, moderate volatility, active contradictions"
    },
    "conflicted": {
        "trust": 0.60,
        "volatility": 0.60,
        "contradiction_count": 5,
        "drift": 0.40,
        "description": "Medium trust but high volatility, many contradictions"
    },
    "drifting": {
        "trust": 0.70,
        "volatility": 0.20,
        "contradiction_count": 1,
        "drift": 0.55,
        "description": "Decent trust but significant drift detected"
    },
}


def crt_to_prosody_params(state: dict) -> dict:
    """
    Map CRT epistemic state => StyleTTS2 inference parameters.

    The key insight: StyleTTS2 exposes alpha (timbre blend), beta (prosody blend),
    embedding_scale (emotional intensity), and diffusion_steps (sample diversity).
    We can also directly perturb the style vector.

    Mapping logic:
    - High trust => lower alpha (stick closer to reference voice = assertive)
    - High volatility => higher diffusion_steps (more variation = instability)
    - Contradictions => higher embedding_scale (more emotional/emphatic)
    - Drift => higher beta (prosody diverges from reference = uncertainty)
    """
    trust = state["trust"]
    volatility = state["volatility"]
    contradictions = state["contradiction_count"]
    drift = state["drift"]

    # alpha: timbre stability (0 = pure reference, 1 = pure predicted)
    # confident speech stays close to reference voice
    alpha = 0.1 + 0.4 * (1 - trust)  # range: 0.1 (confident) to 0.5 (uncertain)

    # beta: prosody divergence from reference
    # drifting beliefs => prosody diverges (sounds less certain)
    beta = 0.3 + 0.5 * drift  # range: 0.3 (stable) to 0.8 (drifting)

    # embedding_scale: emotional intensity
    # contradictions increase emphasis/emotional charge
    contradiction_factor = min(contradictions / 5, 1.0)
    embedding_scale = 0.5 + 1.5 * contradiction_factor  # range: 0.5 (calm) to 2.0 (emphatic)

    # diffusion_steps: sample diversity / instability
    # volatile states get more diverse sampling
    diffusion_steps = max(3, int(3 + 12 * volatility))  # range: 3 (stable) to 15 (volatile)

    return {
        "alpha": round(alpha, 3),
        "beta": round(beta, 3),
        "embedding_scale": round(embedding_scale, 3),
        "diffusion_steps": diffusion_steps,
    }


def test_crt(engine):
    """Generate the same sentence with different CRT states."""
    print("\n=== TEST 3: CRT-to-Prosody Mapping ===")

    text = "I believe this information is accurate based on what I have observed."
    results = {}

    for name, state in CRT_STATES.items():
        params = crt_to_prosody_params(state)
        print(f"\n  [{name}] {state['description']}")
        print(f"    trust={state['trust']}, vol={state['volatility']}, contradictions={state['contradiction_count']}, drift={state['drift']}")
        print(f"    => alpha={params['alpha']}, beta={params['beta']}, embed_scale={params['embedding_scale']}, steps={params['diffusion_steps']}")

        out_path = str(OUTPUT_DIR / f"crt_{name}.wav")
        t0 = time.time()
        audio = engine.inference(
            text,
            output_wav_file=out_path,
            alpha=params["alpha"],
            beta=params["beta"],
            embedding_scale=params["embedding_scale"],
            diffusion_steps=params["diffusion_steps"],
        )
        elapsed = time.time() - t0
        duration_s = len(audio) / 24000

        results[name] = {
            "state": state,
            "params": params,
            "audio_duration_s": round(duration_s, 2),
            "generation_time_s": round(elapsed, 2),
            "audio_rms": round(float(np.sqrt(np.mean(audio ** 2))), 6),
            "audio_peak": round(float(np.max(np.abs(audio))), 6),
            "wav_file": out_path,
        }
        print(f"    Generated {duration_s:.2f}s in {elapsed:.2f}s | RMS={results[name]['audio_rms']:.4f}")

    # Save results
    results_path = str(OUTPUT_DIR / "crt_mapping_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to: {results_path}")
    return results


# ---------------------------------------------------------------------------
# Test 4: A/B comparison — same text, contrasting moods
# ---------------------------------------------------------------------------
def test_ab(engine):
    """Side-by-side: confident vs uncertain delivery of the same content."""
    print("\n=== TEST 4: A/B Mood Comparison ===")

    sentences = [
        "The data clearly shows a strong correlation between these variables.",
        "I'm not entirely sure, but there might be a pattern here.",
        "This contradicts what we observed yesterday, which is interesting.",
    ]

    moods = {
        "assertive": {"alpha": 0.1, "beta": 0.3, "embedding_scale": 0.8, "diffusion_steps": 3},
        "hesitant":  {"alpha": 0.4, "beta": 0.7, "embedding_scale": 1.5, "diffusion_steps": 10},
    }

    for i, text in enumerate(sentences):
        print(f"\n  Sentence {i+1}: \"{text[:60]}...\"" if len(text) > 60 else f"\n  Sentence {i+1}: \"{text}\"")
        for mood_name, params in moods.items():
            out_path = str(OUTPUT_DIR / f"ab_s{i+1}_{mood_name}.wav")
            t0 = time.time()
            audio = engine.inference(text, output_wav_file=out_path, **params)
            elapsed = time.time() - t0
            duration_s = len(audio) / 24000
            print(f"    {mood_name:10s} => {duration_s:.2f}s audio, {elapsed:.2f}s gen | {out_path}")

    print(f"\n  Compare the WAV pairs to hear the difference.")


# ---------------------------------------------------------------------------
# Test 5: Direct style vector manipulation (the real hack)
# ---------------------------------------------------------------------------
def test_style_hack(engine):
    """Directly manipulate the 256-dim style vector to shift prosody."""
    print("\n=== TEST 5: Direct Style Vector Manipulation ===")

    # Get baseline style
    from cached_path import cached_path
    from styletts2.tts import DEFAULT_TARGET_VOICE_URL
    default_voice = cached_path(DEFAULT_TARGET_VOICE_URL)
    ref_s = engine.compute_style(default_voice)

    text = "I have carefully considered all available evidence before reaching this conclusion."

    # Baseline
    out_path = str(OUTPUT_DIR / "hack_baseline.wav")
    audio_base = engine.inference(text, ref_s=ref_s, output_wav_file=out_path)
    print(f"  Baseline: {len(audio_base)/24000:.2f}s => {out_path}")

    # Manipulation: boost prosody dimensions (dims 128-255)
    perturbations = {
        "prosody_boost": (128, 256, 0.5),   # add energy to prosody half
        "prosody_dampen": (128, 256, -0.3),  # reduce prosody (monotone)
        "timbre_shift": (0, 128, 0.4),       # shift voice character
        "full_noise": (0, 256, 0.2),         # add noise everywhere (instability)
    }

    for name, (start, end, scale) in perturbations.items():
        modified_s = ref_s.clone()
        noise = torch.randn(end - start).to(engine.device) * scale
        modified_s[0, start:end] += noise

        out_path = str(OUTPUT_DIR / f"hack_{name}.wav")
        audio = engine.inference(text, ref_s=modified_s, output_wav_file=out_path)
        print(f"  {name:20s}: {len(audio)/24000:.2f}s => {out_path}")

    print(f"\n  Listen to the differences — prosody_dampen should sound flatter,")
    print(f"  prosody_boost more expressive, full_noise more unstable.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="TTS Lab — StyleTTS2 experiments")
    parser.add_argument("--test", choices=["basic", "style", "crt", "ab", "hack", "all"], default="all")
    args = parser.parse_args()

    engine = load_model()

    tests = {
        "basic": test_basic,
        "style": test_style,
        "crt": test_crt,
        "ab": test_ab,
        "hack": test_style_hack,
    }

    if args.test == "all":
        for name, fn in tests.items():
            fn(engine)
    else:
        tests[args.test](engine)

    print(f"\n{'='*60}")
    print(f"All output in: {OUTPUT_DIR}")
    print(f"Play WAV files to hear the results.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
