"""Experiment B: CRT Fine-Tune on Phi-3 3.8B with QLoRA

Trust-weighted fine-tuning. High-trust conversation examples get more
weight in the loss function. The model learns to prefer trusted knowledge.

Hardware: RTX 3060 12GB — Phi-3 in 4-bit = ~4GB, LoRA adapter = ~100MB,
leaves room for batch size 2 with gradient accumulation.

Run: python papers/belief_backpropagation/crt_phi3_finetune.py
"""

import sys
sys.path.insert(0, r"D:\AI_round2")

import json
import os
import time
import sqlite3
import numpy as np
import torch
from datasets import Dataset

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_PATH = r"D:\AI_round2\models\phi3-mini"
OUTPUT_PATH = r"D:\AI_round2\models\phi3-crt-adapter"

print(f"Device: {DEVICE}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")


# ===================================================================
# Step 1: Extract training data
# ===================================================================

def extract_pairs(max_pairs=2000):
    """Extract user->assistant pairs from GPT exports."""
    pairs = []
    for i in range(13):
        f = f"data/chatgpt_export/conversations-{i:03d}.json"
        if not os.path.exists(f):
            continue
        data = json.load(open(f, encoding="utf-8"))
        for conv in data:
            msgs = []
            for node in conv.get("mapping", {}).values():
                msg = node.get("message")
                if not msg:
                    continue
                role = msg.get("author", {}).get("role", "")
                parts = msg.get("content", {}).get("parts", [])
                text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
                if text and len(text) > 15 and role in ("user", "assistant"):
                    msgs.append((role, text[:400]))
            for j in range(len(msgs) - 1):
                if msgs[j][0] == "user" and msgs[j+1][0] == "assistant":
                    pairs.append({"user": msgs[j][1], "assistant": msgs[j+1][1]})
                    if len(pairs) >= max_pairs:
                        return pairs
    return pairs


def load_trust_map():
    conn = sqlite3.connect(r"D:\AI_round2\personal_agent\crt_memory_shared.db")
    rows = conn.execute("SELECT text, trust FROM memories WHERE deprecated=0 AND text IS NOT NULL").fetchall()
    conn.close()
    return {t[:200].lower(): tr for t, tr in rows}


def compute_trust(text, trust_map):
    text_lower = text[:200].lower()
    if text_lower in trust_map:
        return trust_map[text_lower]
    best = 0.5
    text_words = set(text_lower.split())
    for mem, trust in trust_map.items():
        mem_words = set(mem.split())
        if len(mem_words) < 3:
            continue
        overlap = len(mem_words & text_words) / max(len(mem_words), 1)
        if overlap > 0.4:
            best = max(best, trust)
    return best


# ===================================================================
# Step 2: Format for Phi-3 chat template
# ===================================================================

def format_for_phi3(pair, trust_score):
    """Format as Phi-3 instruct template with trust context."""
    # Phi-3 uses <|user|> <|assistant|> <|end|> format
    text = f"<|user|>\n{pair['user']}<|end|>\n<|assistant|>\n{pair['assistant']}<|end|>"
    return {"text": text, "trust": trust_score}


# ===================================================================
# Step 3: Custom trainer with trust-weighted loss
# ===================================================================

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig


def main():
    print("=" * 70)
    print("EXPERIMENT B: CRT Fine-Tune (Phi-3 3.8B + QLoRA)")
    print("=" * 70)

    # Extract data
    print("\nStep 1: Extracting conversation pairs...")
    pairs = extract_pairs(max_pairs=2000)
    print(f"  {len(pairs)} pairs extracted")

    # Compute trust
    print("\nStep 2: Computing trust weights...")
    trust_map = load_trust_map()
    trust_scores = [compute_trust(p["assistant"], trust_map) for p in pairs]
    print(f"  Mean trust: {np.mean(trust_scores):.3f}")
    print(f"  High trust (>0.7): {sum(1 for t in trust_scores if t > 0.7)}")
    print(f"  Low trust (<0.3): {sum(1 for t in trust_scores if t < 0.3)}")

    # Format training data
    print("\nStep 3: Formatting training data...")
    formatted = [format_for_phi3(p, t) for p, t in zip(pairs, trust_scores)]

    # Split into trust-weighted: oversample high-trust, undersample low-trust
    # This is simpler than custom loss and works with standard trainers
    weighted_data = []
    for item in formatted:
        trust = item["trust"]
        # High trust (>0.7): include 3x
        # Medium trust (0.3-0.7): include 1x
        # Low trust (<0.3): include 0.3x (30% chance)
        if trust > 0.7:
            weighted_data.extend([item] * 3)
        elif trust > 0.3:
            weighted_data.append(item)
        else:
            if np.random.random() < 0.3:
                weighted_data.append(item)

    print(f"  Original: {len(formatted)} examples")
    print(f"  Trust-weighted: {len(weighted_data)} examples (high-trust oversampled)")

    dataset = Dataset.from_list([{"text": d["text"]} for d in weighted_data])

    # Load model in 4-bit
    print("\nStep 4: Loading Phi-3 in 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # Patch config to avoid RoPE scaling KeyError with custom model code
    from transformers import AutoConfig
    config = AutoConfig.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if hasattr(config, 'rope_scaling') and config.rope_scaling is None:
        config.rope_scaling = None  # ensure it's actually None not {}

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        config=config,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=False,  # use native transformers Phi-3 support
        attn_implementation="eager",
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print(f"  Model loaded. Memory: {torch.cuda.memory_allocated()/(1024**3):.1f} GB")

    # Prepare for QLoRA
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,  # rank
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["o_proj", "qkv_proj", "gate_up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({trainable/total:.2%})")

    # Training config
    print("\nStep 5: Training...")
    training_args = SFTConfig(
        output_dir=OUTPUT_PATH,
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=25,
        save_strategy="epoch",
        bf16=True,
        max_length=512,
        warmup_steps=50,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed/60:.1f} minutes")

    # Save adapter
    model.save_pretrained(OUTPUT_PATH)
    tokenizer.save_pretrained(OUTPUT_PATH)
    adapter_size = sum(
        os.path.getsize(os.path.join(OUTPUT_PATH, f))
        for f in os.listdir(OUTPUT_PATH)
        if f.endswith((".safetensors", ".bin"))
    )
    print(f"  Adapter saved to {OUTPUT_PATH} ({adapter_size/(1024**2):.1f} MB)")

    # Test
    print("\n" + "=" * 70)
    print("TESTING: CRT-adapted Phi-3")
    print("=" * 70)

    model.eval()
    test_prompts = [
        "<|user|>\nWhat do I do for work?<|end|>\n<|assistant|>\n",
        "<|user|>\nWhat is my favorite color?<|end|>\n<|assistant|>\n",
        "<|user|>\nWhat is my name?<|end|>\n<|assistant|>\n",
        "<|user|>\nWhat am I building?<|end|>\n<|assistant|>\n",
        "<|user|>\nDo I like coffee?<|end|>\n<|assistant|>\n",
    ]

    for prompt in test_prompts:
        input_ids = tokenizer.encode(prompt, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            output = model.generate(
                input_ids,
                max_new_tokens=80,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
            )
        response = tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True)
        query = prompt.split("<|user|>\n")[1].split("<|end|>")[0]
        print(f"  Q: {query}")
        print(f"  A: {response[:200]}")
        print()


if __name__ == "__main__":
    main()
