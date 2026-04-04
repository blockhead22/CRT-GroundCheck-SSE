#!/usr/bin/env python3
"""
vilt-chat: Interactive CLI for VILT-trained models.
====================================================

Loads a base model + LoRA adapters trained with VILT, then runs an
interactive chat loop with real-time GroundCheck verification against
your fact ledger.

Usage:
    python scripts/vilt_chat.py                              # defaults
    python scripts/vilt_chat.py --facts data/my_facts.json   # custom facts
    python scripts/vilt_chat.py --adapter models/vilt_smollm/final_lora
    python scripts/vilt_chat.py --model HuggingFaceTB/SmolLM-135M
"""

import sys
import json
import argparse
import time
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "groundcheck"))

from groundcheck import GroundCheck, Memory

# ── defaults ──────────────────────────────────────────────────
DEFAULT_MODEL = "HuggingFaceTB/SmolLM-135M"
DEFAULT_ADAPTER = ROOT / "models" / "vilt_smollm" / "best_lora"
DEFAULT_FACTS = ROOT / "data" / "vilt_facts.json"


def load_facts(path: Path) -> list[Memory]:
    with open(path) as f:
        data = json.load(f)
    return [Memory(id=d["id"], text=d["text"], trust=d["trust"]) for d in data["facts"]]


def format_prompt(query: str, facts: list[str]) -> str:
    facts_str = "\n".join(f"- {f}" for f in facts) or "(no facts)"
    return (
        f"### Facts:\n{facts_str}\n\n"
        f"### Question:\n{query}\n\n"
        f"### Answer:\n"
    )


def build_fact_strings(memories: list[Memory]) -> list[str]:
    """Convert Memory objects → readable fact strings for the prompt."""
    out = []
    for m in memories:
        # Parse "FACT: key = value" → "key=value (trust=X.XX)"
        text = m.text
        if text.startswith("FACT: "):
            text = text[6:]
        key_val = text.replace(" = ", "=")
        out.append(f"{key_val} (trust={m.trust})")
    return out


def main():
    parser = argparse.ArgumentParser(
        description="VILT Chat — interactive fact-grounded inference with GroundCheck verification"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Base model name or path (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--adapter", default=str(DEFAULT_ADAPTER),
        help=f"Path to LoRA adapter directory (default: {DEFAULT_ADAPTER})"
    )
    parser.add_argument(
        "--facts", default=str(DEFAULT_FACTS),
        help=f"Path to facts JSON file (default: {DEFAULT_FACTS})"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=96,
        help="Max tokens to generate (default: 96)"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature (default: 0.7)"
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip GroundCheck verification"
    )
    parser.add_argument(
        "--cpu", action="store_true",
        help="Force CPU (default: use CUDA if available)"
    )
    args = parser.parse_args()

    device = "cpu" if args.cpu else ("cuda" if torch.cuda.is_available() else "cpu")

    # ── load facts ────────────────────────────────────────────
    facts_path = Path(args.facts)
    if not facts_path.exists():
        print(f"ERROR: Facts file not found: {facts_path}")
        sys.exit(1)
    memories = load_facts(facts_path)
    fact_strings = build_fact_strings(memories)

    # ── load model + adapter ──────────────────────────────────
    adapter_path = Path(args.adapter)
    has_adapter = adapter_path.exists() and (adapter_path / "adapter_config.json").exists()

    print("=" * 60)
    print("  VILT Chat")
    print("=" * 60)
    print(f"  Model:    {args.model}")
    if has_adapter:
        print(f"  Adapter:  {adapter_path}")
    else:
        print(f"  Adapter:  (none — running base model)")
    print(f"  Facts:    {facts_path.name} ({len(memories)} facts)")
    print(f"  Device:   {device}")
    print(f"  Verify:   {'OFF' if args.no_verify else 'ON (GroundCheck)'}")
    print()

    t0 = time.time()
    print("  Loading model...", end="", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model)

    if has_adapter:
        model = PeftModel.from_pretrained(model, str(adapter_path))
        model = model.merge_and_unload()  # merge LoRA for faster inference

    model = model.to(device)
    model.eval()
    print(f" done ({time.time() - t0:.1f}s)")

    if not args.no_verify:
        verifier = GroundCheck()
    else:
        verifier = None

    if device == "cuda":
        vram = torch.cuda.memory_allocated() / 1024**3
        print(f"  VRAM:     {vram:.2f} GB")

    print(f"\n  Loaded {len(memories)} facts:")
    for m in memories:
        slot = m.text.replace("FACT: ", "")
        print(f"    {slot}  (trust={m.trust})")

    print(f"\n{'─' * 60}")
    print("  Type a question, or:")
    print("    /facts         — show loaded facts")
    print("    /verify <text> — verify arbitrary text against facts")
    print("    /quit          — exit")
    print(f"{'─' * 60}\n")

    # ── chat loop ─────────────────────────────────────────────
    while True:
        try:
            query = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not query:
            continue

        # ── commands ──
        if query.lower() in ("/quit", "/exit", "/q"):
            print("Bye!")
            break

        if query.lower() == "/facts":
            print(f"\n  {len(memories)} facts loaded:")
            for m in memories:
                slot = m.text.replace("FACT: ", "")
                print(f"    {slot}  (trust={m.trust})")
            print()
            continue

        if query.lower().startswith("/verify "):
            text = query[8:].strip()
            if verifier and text:
                report = verifier.verify(text, memories, mode="strict")
                status = "PASS" if report.passed else "FAIL"
                print(f"\n  [{status}]  \"{text}\"")
                if report.hallucinations:
                    print(f"    Hallucinations: {report.hallucinations}")
                if report.contradicted_claims:
                    print(f"    Contradictions: {report.contradicted_claims}")
                if report.passed:
                    print(f"    No issues found.")
                print()
            else:
                print("  Verification is off or no text provided.\n")
            continue

        # ── generate ──
        prompt = format_prompt(query, fact_strings)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        t0 = time.time()
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_tokens,
                temperature=args.temperature,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )

        gen_ids = output_ids[0, inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(gen_ids, skip_special_tokens=True)

        # Clean: take first coherent chunk (stop at double newline or repeated text)
        if "\n\n" in response:
            response = response.split("\n\n")[0]
        response = response.strip()
        gen_ms = (time.time() - t0) * 1000

        # ── verify ──
        gc_line = ""
        if verifier and response:
            report = verifier.verify(response, memories, mode="strict")
            if report.passed:
                gc_line = "  [GC: PASS]"
            else:
                issues = []
                if report.hallucinations:
                    issues.append(f"hallucinations={report.hallucinations}")
                if report.contradicted_claims:
                    issues.append(f"contradictions={report.contradicted_claims}")
                gc_line = f"  [GC: FAIL — {'; '.join(issues)}]"

        # ── display ──
        print(f"\nBot> {response}")
        timing = f"({gen_ms:.0f}ms)"
        print(f"     {timing}{gc_line}\n")


if __name__ == "__main__":
    main()
