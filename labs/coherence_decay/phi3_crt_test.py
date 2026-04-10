"""Quick test: Run Phi-3 CRT adapter through coherence decay prompts.

Loads the fine-tuned adapter directly via transformers (not Ollama).
Runs L0 (free) and L4-style (burst + reanchor) on memory domain.
"""

import json
import time
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# Paths
BASE_MODEL = r"D:\AI_round2\models\phi3-mini"
ADAPTER = r"D:\AI_round2\models\phi3-crt-adapter-v2"
PROMPTS_FILE = Path(__file__).parent / "prompts" / "memory.json"
OUTPUT_FILE = Path(__file__).parent / "results" / "raw" / "phi3_crt_test.json"


def load_model():
    print("Loading Phi-3 base + CRT adapter...")
    from transformers import AutoConfig

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    # Fix rope_scaling config for this Phi-3 version
    config = AutoConfig.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if hasattr(config, 'rope_scaling') and config.rope_scaling and 'type' not in config.rope_scaling:
        config.rope_scaling['type'] = config.rope_scaling.get('rope_type', 'longrope')

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        config=config,
        dtype=torch.float32,
        device_map="cpu",
        trust_remote_code=True,
        attn_implementation="eager",
    )
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()
    print(f"  Loaded. Parameters: {sum(p.numel() for p in model.parameters()):,}")
    return model, tokenizer


def generate(model, tokenizer, prompt, max_tokens=200):
    """Generate text from the model."""
    inputs = tokenizer(prompt, return_tensors="pt")
    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.3,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    elapsed = time.time() - t0
    # Decode only the new tokens
    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return text, elapsed


def run_l0(model, tokenizer, prompt_data):
    """Free-run: single generation."""
    prompt = prompt_data["prompt"]
    text, elapsed = generate(model, tokenizer, prompt, max_tokens=300)
    return {
        "strategy": "L0_free_run",
        "text": text,
        "tokens": len(text.split()),
        "time_s": round(elapsed, 2),
    }


def run_l4_burst(model, tokenizer, prompt_data):
    """Burst generation: 50-token bursts with re-anchoring."""
    prompt = prompt_data["prompt"]
    full_text = ""
    spans = []
    burst_size = 50
    max_tokens = 300

    total_generated = 0
    while total_generated < max_tokens:
        if full_text:
            # Raw continuation: prompt + prior output
            context = f"{prompt}\n\n{full_text}"
        else:
            context = prompt

        remaining = max_tokens - total_generated
        this_burst = min(burst_size, remaining)

        text, elapsed = generate(model, tokenizer, context, max_tokens=this_burst)
        if not text.strip():
            break

        spans.append({
            "text": text,
            "tokens": len(text.split()),
            "time_s": round(elapsed, 2),
        })
        full_text += text
        total_generated += len(text.split())

    return {
        "strategy": "L4_burst_50",
        "text": full_text,
        "tokens": total_generated,
        "spans": len(spans),
        "time_s": round(sum(s["time_s"] for s in spans), 2),
    }


def score_fidelity(text, prompt_data):
    """Basic keyword fidelity check."""
    text_lower = text.lower()
    facts = prompt_data.get("ground_truth_facts", [])
    if not facts:
        return 0.0
    found = sum(1 for f in facts if f.lower() in text_lower)
    return round(found / len(facts), 3)


def main():
    model, tokenizer = load_model()

    with open(PROMPTS_FILE) as f:
        prompts = json.load(f)["prompts"]

    results = []

    for prompt_data in prompts:
        pid = prompt_data["id"]
        print(f"\n--- {pid} ---")

        # L0
        print(f"  L0 (free-run)...", end=" ", flush=True)
        r0 = run_l0(model, tokenizer, prompt_data)
        r0["prompt_id"] = pid
        r0["fidelity"] = score_fidelity(r0["text"], prompt_data)
        print(f"OK ({r0['tokens']} tokens, {r0['time_s']}s, fidelity={r0['fidelity']})")
        print(f"    Preview: {r0['text'][:120]}...")
        results.append(r0)

        # L4 burst
        print(f"  L4 (burst)...", end=" ", flush=True)
        r4 = run_l4_burst(model, tokenizer, prompt_data)
        r4["prompt_id"] = pid
        r4["fidelity"] = score_fidelity(r4["text"], prompt_data)
        print(f"OK ({r4['tokens']} tokens, {r4['spans']} spans, {r4['time_s']}s, fidelity={r4['fidelity']})")
        print(f"    Preview: {r4['text'][:120]}...")
        results.append(r4)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY: Phi-3 CRT Adapter — Memory Domain")
    print(f"{'='*60}")

    l0_results = [r for r in results if r["strategy"] == "L0_free_run"]
    l4_results = [r for r in results if r["strategy"] == "L4_burst_50"]

    l0_fid = sum(r["fidelity"] for r in l0_results) / len(l0_results)
    l4_fid = sum(r["fidelity"] for r in l4_results) / len(l4_results)

    print(f"  L0 avg fidelity: {l0_fid:.3f}")
    print(f"  L4 avg fidelity: {l4_fid:.3f}")
    print(f"  Delta: {l4_fid - l0_fid:+.3f}")
    print(f"{'='*60}")

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
