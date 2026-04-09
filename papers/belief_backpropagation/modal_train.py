"""CRT Adapter Training on Modal (A100)

Uploads training data, trains QLoRA adapter on Phi-3 3.8B,
downloads the adapter back. ~45 min on A100, ~$2.70.

Usage:
  1. First: python papers/belief_backpropagation/modal_prep_data.py
     (prepares training data locally, saves to data/crt_training_data.json)
  2. Then: modal run papers/belief_backpropagation/modal_train.py
     (uploads data, trains on A100, downloads adapter)
"""

import modal
import os

app = modal.App("crt-adapter-training")

# Docker image with all dependencies
training_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "transformers",
        "peft",
        "trl",
        "bitsandbytes",
        "datasets",
        "accelerate",
        "numpy",
        "huggingface_hub",
    )
)

# Persistent volume for model cache
volume = modal.Volume.from_name("crt-model-cache", create_if_missing=True)


@app.function(
    image=training_image,
    gpu="A100",
    timeout=7200,
    volumes={"/cache": volume},
)
def train_adapter(training_data: list, config: dict) -> bytes:
    """Train QLoRA adapter on A100. Returns adapter as tar bytes."""

    import json
    import time
    import numpy as np
    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    print(f"Training examples: {len(training_data)}")

    model_name = config.get("model", "microsoft/Phi-3-mini-4k-instruct")
    epochs = config.get("epochs", 3)
    batch_size = config.get("batch_size", 4)
    lr = config.get("lr", 2e-4)
    lora_r = config.get("lora_r", 16)
    max_length = config.get("max_length", 512)

    # Build dataset
    dataset = Dataset.from_list([{"text": ex["text"]} for ex in training_data])

    # Load model in 4-bit
    print(f"\nLoading {model_name} in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=False,
        attn_implementation="eager",
        cache_dir="/cache/models",
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=False,
        cache_dir="/cache/models",
    )
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print(f"VRAM after load: {torch.cuda.memory_allocated()/(1024**3):.1f} GB")

    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_r * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["o_proj", "qkv_proj", "gate_up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable: {trainable:,} / {total:,} ({trainable/total:.2%})")

    # Train
    output_dir = "/tmp/crt-adapter"
    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=lr,
        logging_steps=25,
        save_strategy="epoch",
        bf16=True,
        max_length=max_length,
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
    trainer.train()
    elapsed = time.time() - t0
    print(f"\nTraining complete in {elapsed/60:.1f} minutes")

    # Save
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Test
    print("\n=== TESTING ===")
    model.eval()
    test_prompts = [
        "What do I do for work?",
        "What is my favorite color?",
        "What is my name?",
        "What am I building?",
        "Do I like coffee?",
        "Where do I live?",
        "What do you know about me?",
    ]

    for q in test_prompts:
        prompt = f"<|user|>\n{q}<|end|>\n<|assistant|>\n"
        ids = tokenizer.encode(prompt, return_tensors="pt").to("cuda")
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
        print(f"Q: {q}")
        print(f"A: {resp[:200]}")
        print()

    # Package adapter as tar
    import tarfile
    import io

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        tar.add(output_dir, arcname="crt-adapter")
    tar_bytes = tar_buffer.getvalue()
    print(f"Adapter package: {len(tar_bytes) / (1024*1024):.1f} MB")

    # Persist to volume too
    import shutil
    volume_path = "/cache/adapters/phi3-crt-latest"
    if os.path.exists(volume_path):
        shutil.rmtree(volume_path)
    shutil.copytree(output_dir, volume_path)
    print(f"Adapter saved to volume: {volume_path}")

    return tar_bytes


@app.local_entrypoint()
def main():
    import json

    data_path = r"D:\AI_round2\data\crt_training_data.json"

    if not os.path.exists(data_path):
        print(f"Training data not found at {data_path}")
        print("Run: python papers/belief_backpropagation/modal_prep_data.py first")
        return

    print(f"Loading training data from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        training_data = json.load(f)

    print(f"Loaded {len(training_data)} examples")

    config = {
        "model": "microsoft/Phi-3-mini-4k-instruct",
        "epochs": 3,
        "batch_size": 4,
        "lr": 2e-4,
        "lora_r": 16,
        "max_length": 512,
    }

    print("Submitting training job to Modal (A100)...")
    adapter_bytes = train_adapter.remote(training_data, config)

    # Save adapter locally
    output_path = r"D:\AI_round2\models\phi3-crt-adapter-modal.tar.gz"
    with open(output_path, "wb") as f:
        f.write(adapter_bytes)
    print(f"\nAdapter downloaded: {output_path} ({len(adapter_bytes)/(1024*1024):.1f} MB)")

    # Extract
    import tarfile
    import io
    extract_path = r"D:\AI_round2\models\phi3-crt-adapter-modal"
    with tarfile.open(fileobj=io.BytesIO(adapter_bytes), mode="r:gz") as tar:
        tar.extractall(extract_path)
    print(f"Extracted to: {extract_path}")
