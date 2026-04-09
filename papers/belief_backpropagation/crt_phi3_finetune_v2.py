"""Experiment B v2: Trust-Weighted Fine-Tune with Belief-Grounded Pairs

Fix from v1: instead of raw conversations, format training data as:
  - Memory-grounded Q&A pairs from production trust scores
  - Fact assertions with trust weighting
  - Correction pairs (old wrong answer → corrected answer)

Uses all available GPT conversation data + production memory trust scores.

Run: python papers/belief_backpropagation/crt_phi3_finetune_v2.py
"""

import sys
sys.path.insert(0, r"D:\AI_round2")
sys.stdout.reconfigure(encoding='utf-8')

import json
import os
import time
import sqlite3
import random
import numpy as np
import torch
from datasets import Dataset

DEVICE = "cuda"
MODEL_PATH = r"D:\AI_round2\models\phi3-mini"
OUTPUT_PATH = r"D:\AI_round2\models\phi3-crt-adapter-v2"

print(f"Device: {DEVICE}")


# ===================================================================
# Step 1: Build belief-grounded training pairs
# ===================================================================

def load_production_memories():
    """Load all active memories with trust scores."""
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute("""
        SELECT text, trust, kind, contradiction_count, access_count
        FROM memories WHERE deprecated=0 AND text IS NOT NULL AND length(text) > 20
    """).fetchall()
    conn.close()
    return [{"text": t, "trust": tr, "kind": k, "contras": c, "access": a}
            for t, tr, k, c, a in rows]


def load_conversation_pairs(max_pairs=20000):
    """Extract user->assistant pairs from all GPT exports."""
    pairs = []
    for i in range(13):
        f = f"data/chatgpt_export/conversations-{i:03d}.json"
        if not os.path.exists(f):
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
        except:
            continue
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
                    msgs.append((role, text[:500]))
            for j in range(len(msgs) - 1):
                if msgs[j][0] == "user" and msgs[j+1][0] == "assistant":
                    pairs.append({"user": msgs[j][1], "assistant": msgs[j+1][1]})
                    if len(pairs) >= max_pairs:
                        return pairs
    return pairs


def build_belief_grounded_dataset(memories, conv_pairs):
    """Build three types of training examples:

    Type 1: Fact assertion — teach the model to state trusted facts
      "Based on what I know: {memory_text}" weighted by trust

    Type 2: Fact Q&A — teach the model to answer from memory
      "Q: {inferred question} A: {memory_text}" weighted by trust

    Type 3: Conversation with trust context — teach conversational style
      but only from high-trust exchanges

    Type 4: Correction pairs — explicitly teach what's wrong vs right
    """
    examples = []

    # Type 1: Fact assertions from high-trust memories
    print("  Building Type 1: Fact assertions...")
    for mem in memories:
        if mem["trust"] < 0.3:
            continue
        text = f"<|user|>\nWhat do you know about this topic?<|end|>\n<|assistant|>\nBased on stored memories (trust {mem['trust']:.2f}): {mem['text']}<|end|>"
        examples.append({"text": text, "trust": mem["trust"]})

    # Type 2: Inferred Q&A from memories
    print("  Building Type 2: Fact Q&A pairs...")
    qa_templates = {
        "user_fact": [
            "What do you know about me?",
            "Tell me what you remember.",
            "What facts do you have stored?",
        ],
        "observation": [
            "What have you observed?",
            "What do you recall from our conversations?",
            "What patterns have you noticed?",
        ],
    }
    for mem in memories:
        if mem["trust"] < 0.2:
            continue
        kind = mem["kind"] or "observation"
        templates = qa_templates.get(kind, qa_templates["observation"])
        q = random.choice(templates)
        text = f"<|user|>\n{q}<|end|>\n<|assistant|>\n{mem['text']}<|end|>"
        examples.append({"text": text, "trust": mem["trust"]})

    # Type 3: High-trust conversation pairs (filtered)
    print("  Building Type 3: Trust-filtered conversations...")
    # Match conversations to memories by word overlap for trust scoring
    mem_words = {}
    for mem in memories:
        words = set(mem["text"][:200].lower().split())
        if len(words) >= 3:
            mem_words[mem["text"][:100]] = (words, mem["trust"])

    conv_count = 0
    for pair in conv_pairs:
        # Score this pair's relevance to trusted memories
        asst_words = set(pair["assistant"][:200].lower().split())
        best_trust = 0.4  # default
        for _, (mw, mt) in mem_words.items():
            overlap = len(mw & asst_words) / max(len(mw), 1)
            if overlap > 0.3:
                best_trust = max(best_trust, mt)

        # Only include conversations that relate to trusted content
        if best_trust >= 0.5 or random.random() < 0.15:  # 15% random for diversity
            text = f"<|user|>\n{pair['user']}<|end|>\n<|assistant|>\n{pair['assistant']}<|end|>"
            examples.append({"text": text, "trust": best_trust})
            conv_count += 1

    print(f"    Included {conv_count} conversation pairs")

    # Type 4: Correction pairs — teach the model what's wrong
    print("  Building Type 4: Correction pairs...")
    contradicted = [m for m in memories if m["contras"] > 0]
    for mem in contradicted:
        # Low trust + contradicted = teach as negative example framing
        text = f"<|user|>\nIs this true: {mem['text']}<|end|>\n<|assistant|>\nThat information has been corrected. Its trust score is {mem['trust']:.2f}, which is low. I would not rely on this without verification.<|end|>"
        examples.append({"text": text, "trust": 0.8})  # high trust on the CORRECTION

    # Oversampling by trust
    print("  Trust-weighting (oversampling)...")
    weighted = []
    for ex in examples:
        t = ex["trust"]
        if t >= 0.8:
            weighted.extend([ex] * 4)
        elif t >= 0.6:
            weighted.extend([ex] * 2)
        elif t >= 0.4:
            weighted.append(ex)
        else:
            if random.random() < 0.2:
                weighted.append(ex)

    random.shuffle(weighted)
    return weighted


# ===================================================================
# Step 2: Train
# ===================================================================

def train():
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    # Build dataset
    print("\n" + "=" * 60)
    print("EXPERIMENT B v2: Belief-Grounded Fine-Tune")
    print("=" * 60)

    print("\nLoading production memories...")
    memories = load_production_memories()
    print(f"  {len(memories)} memories loaded")

    print("\nLoading conversation pairs...")
    conv_pairs = load_conversation_pairs(max_pairs=3000)
    print(f"  {len(conv_pairs)} conversation pairs loaded")

    print("\nBuilding belief-grounded dataset...")
    examples = build_belief_grounded_dataset(memories, conv_pairs)
    print(f"  Total training examples: {len(examples)}")
    print(f"  Trust distribution: mean={np.mean([e['trust'] for e in examples]):.3f}")

    dataset = Dataset.from_list([{"text": e["text"]} for e in examples])

    # Load model
    print("\nLoading Phi-3 in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=False,
        attn_implementation="eager",
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print(f"  VRAM: {torch.cuda.memory_allocated()/(1024**3):.1f} GB")

    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
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

    # Train with checkpoint resume support
    # Saves every 500 steps AND every epoch. If interrupted, resumes from last checkpoint.
    import glob
    resume_from = None
    existing_checkpoints = sorted(glob.glob(os.path.join(OUTPUT_PATH, "checkpoint-*")))
    if existing_checkpoints:
        resume_from = existing_checkpoints[-1]
        print(f"\n  Resuming from checkpoint: {resume_from}")
    else:
        print("\n  Starting fresh (no checkpoint found)")

    print("Training...")
    training_args = SFTConfig(
        output_dir=OUTPUT_PATH,
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=50,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,
        bf16=True,
        max_length=384,
        warmup_steps=100,
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
    trainer.train(resume_from_checkpoint=resume_from)
    elapsed = time.time() - t0
    print(f"\nTraining complete in {elapsed/60:.1f} minutes")

    model.save_pretrained(OUTPUT_PATH)
    tokenizer.save_pretrained(OUTPUT_PATH)
    print(f"Adapter saved to {OUTPUT_PATH}")

    # Test
    print("\n" + "=" * 60)
    print("TESTING: CRT-adapted Phi-3 v2")
    print("=" * 60)

    model.eval()
    test_prompts = [
        "What do I do for work?",
        "What is my favorite color?",
        "What is my name?",
        "What am I building?",
        "Do I like coffee?",
        "Where do I live?",
        "Do I work at a design studio?",
        "What do you know about my health?",
        "Tell me about yourself.",
        "What do you know about me?",
    ]

    for q in test_prompts:
        prompt = f"<|user|>\n{q}<|end|>\n<|assistant|>\n"
        ids = tokenizer.encode(prompt, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            out = model.generate(
                ids,
                max_new_tokens=100,
                temperature=0.5,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
            )
        resp = tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
        print(f"  Q: {q}")
        print(f"  A: {resp[:250]}")
        print()


if __name__ == "__main__":
    train()
