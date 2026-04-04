"""
VILT Pretrained: Verification-In-the-Loop Training on SmolLM-135M
=================================================================

Same VILT technique proven on DNNT, now applied to a real pretrained
model with actual language understanding. Uses LoRA for parameter-
efficient fine-tuning. Everything else is identical:

  1. Forward pass → supervised loss (teacher forcing)
  2. Generate from model (no_grad, fast greedy decode)
  3. Pipe generation through GroundCheck.verify() against fact ledger
  4. If contradictions found → loss *= (1 + penalty * trust)
  5. Backprop the amplified loss through LoRA adapters only

Model: HuggingFaceTB/SmolLM-135M  (~135M params, ~270MB)
LoRA: rank=16, alpha=32, ~0.5M trainable params
GPU:  RTX 3060 12GB — fits easily
"""

import sys
import time
import json
import random
import torch

# Free speedup on fixed-size inputs
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

from pathlib import Path
from dataclasses import dataclass

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "groundcheck"))

from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, TaskType
from groundcheck import GroundCheck, Memory


# ==============================================================
#  DATA LOADING — facts and queries from shared JSON files
# ==============================================================

DATA_DIR = ROOT / "data"

def load_facts(path=None):
    """Load fact ledger from JSON → list[Memory]."""
    p = Path(path) if path else DATA_DIR / "vilt_facts.json"
    with open(p) as f:
        data = json.load(f)
    return [Memory(id=d["id"], text=d["text"], trust=d["trust"]) for d in data["facts"]]

def load_test_queries(path=None):
    """Load test queries from JSON."""
    p = Path(path) if path else DATA_DIR / "vilt_test_queries.json"
    with open(p) as f:
        data = json.load(f)
    return data["queries"]


FACT_LEDGER = load_facts()
TEST_QUERIES = load_test_queries()

# Training examples — plain-text targets for pretrained models.
# These match the generic facts in data/vilt_facts.json.
TRAINING_EXAMPLES = [
    # ── identity (8) ──
    {"query": "What is my name?",
     "facts": ["name=Alex (trust=0.95)", "location=Denver (trust=0.92)"],
     "target": "Based on the facts provided, your name is Alex."},
    {"query": "Where do I live?",
     "facts": ["location=Denver (trust=0.92)", "name=Alex (trust=0.95)"],
     "target": "You live in Denver."},
    {"query": "What do I do for work?",
     "facts": ["occupation=data engineer (trust=0.90)", "name=Alex (trust=0.95)"],
     "target": "You are a data engineer."},
    {"query": "What is my favorite programming language?",
     "facts": ["favorite_language=Rust (trust=0.85)", "name=Alex (trust=0.95)"],
     "target": "Your favorite programming language is Rust."},
    {"query": "What editor do I use?",
     "facts": ["editor=Neovim (trust=0.82)", "name=Alex (trust=0.95)"],
     "target": "You use Neovim as your editor."},
    {"query": "What is my main project?",
     "facts": ["project=DataForge (trust=0.88)"],
     "target": "Your main project is DataForge."},
    {"query": "What is gravity?",
     "facts": [],
     "target": "Gravity is a fundamental force that attracts objects with mass toward each other."},
    {"query": "What is an API?",
     "facts": [],
     "target": "An API is a set of rules and protocols that allows different software applications to communicate."},
    # ── preferences (8) ──
    {"query": "What do I like to drink?",
     "facts": ["favorite_drink=espresso (trust=0.78)", "name=Alex (trust=0.95)"],
     "target": "Your favorite drink is espresso."},
    {"query": "What do I hate?",
     "facts": ["pet_peeve=meetings (trust=0.75)", "name=Alex (trust=0.95)"],
     "target": "You hate meetings."},
    {"query": "What OS do I use?",
     "facts": ["os=Linux (trust=0.88)", "name=Alex (trust=0.95)"],
     "target": "You use Linux."},
    {"query": "What database do I prefer?",
     "facts": ["database=DuckDB (trust=0.82)", "name=Alex (trust=0.95)"],
     "target": "You prefer DuckDB."},
    {"query": "How many years of experience do I have?",
     "facts": ["experience_years=8 (trust=0.85)", "occupation=data engineer (trust=0.90)"],
     "target": "You have 8 years of experience."},
    {"query": "What is my hobby?",
     "facts": ["hobby=rock climbing (trust=0.90)", "name=Alex (trust=0.95)"],
     "target": "Your hobby is rock climbing."},
    {"query": "Do I have pets?",
     "facts": ["pet=two cats (trust=0.88)", "name=Alex (trust=0.95)"],
     "target": "Yes, you have two cats."},
    {"query": "What cloud provider do I use?",
     "facts": ["cloud=AWS (trust=0.70)", "os=Linux (trust=0.88)"],
     "target": "You use AWS."},
]


# ==============================================================
#  CONFIG
# ==============================================================

MODEL_NAME = "HuggingFaceTB/SmolLM-135M"

@dataclass
class VILTConfig:
    contradiction_weight: float = 0.5
    trust_scale: bool = True
    learning_rate: float = 2e-4       # higher LR for LoRA
    num_steps: int = 200              # pretrained model learns faster
    log_every: int = 10
    eval_every: int = 25
    gen_max_tokens: int = 64
    gen_temperature: float = 0.7
    # ── anti-gaming ──
    brevity_weight: float = 0.3
    min_response_tokens: int = 5
    expected_response_tokens: int = 20
    curriculum_switch_step: int = 80
    early_stop_acc: float = 0.75
    early_stop_gc: float = 0.80
    early_stop_patience: int = 2
    # ── LoRA ──
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05


# ==============================================================
#  VILT TRAINER (HuggingFace version)
# ==============================================================

class VILTPretrainedTrainer:
    """VILT on a HuggingFace causal LM with LoRA."""

    def __init__(self, model, tokenizer, fact_ledger, config=None, device="cpu"):
        self.model = model
        self.tokenizer = tokenizer
        self.verifier = GroundCheck()
        self.fact_ledger = fact_ledger
        self.config = config or VILTConfig()
        self.device = device

        # Only optimize LoRA params
        trainable = [p for p in model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(
            trainable, lr=self.config.learning_rate, weight_decay=0.01
        )

    def _format_prompt(self, query, facts=None):
        facts_str = "\n".join(f"- {f}" for f in (facts or [])) or "(no facts)"
        return (
            f"### Facts:\n{facts_str}\n\n"
            f"### Question:\n{query}\n\n"
            f"### Answer:\n"
        )

    @torch.no_grad()
    def _generate(self, query, facts=None):
        """Fast greedy generation."""
        self.model.eval()
        prompt = self._format_prompt(query, facts)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.config.gen_max_tokens,
            temperature=self.config.gen_temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        # Decode only the generated part (after the prompt)
        gen_ids = output_ids[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(gen_ids, skip_special_tokens=True)

    def _verify_and_score(self, response):
        """Run GroundCheck → return (contradiction_score, info_dict)."""
        if not response or len(response.strip()) < 3:
            return 0.0, {"passed": True, "hallucinations": [], "out_of_scope": [], "trust": 0.0}
        report = self.verifier.verify(response, self.fact_ledger, mode="strict")
        n_issues = len(report.hallucinations) + len(report.contradicted_claims)

        trust = 0.0
        if self.config.trust_scale and n_issues > 0:
            if report.contradiction_details:
                all_t = []
                for d in report.contradiction_details:
                    all_t.extend(d.trust_scores)
                trust = max(all_t) if all_t else 0.8
            else:
                trust = sum(m.trust for m in self.fact_ledger) / len(self.fact_ledger)

        score = min(n_issues, 3) / 3.0 * trust if n_issues > 0 else 0.0
        return score, {
            "passed": report.passed,
            "hallucinations": report.hallucinations,
            "out_of_scope": getattr(report, 'out_of_scope', []),
            "contradicted": report.contradicted_claims,
            "n_issues": n_issues,
            "trust": trust,
            "n_grounded": len(report.facts_supported),
            "n_oos": len(getattr(report, 'facts_out_of_scope', {})),
            "confidence": report.confidence,
        }

    def train_step(self, query, facts, target):
        """
        VILT core loop:
        1. Teacher-forced supervised loss on target
        2. Generate freely → GroundCheck
        3. Amplify loss if contradictions found
        4. Backprop through LoRA adapters
        """
        self.model.train()
        self.optimizer.zero_grad()

        # ─ supervised forward (teacher forcing) ─
        prompt = self._format_prompt(query, facts)
        full_text = prompt + target
        encoding = self.tokenizer(
            full_text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)

        input_ids = encoding["input_ids"]
        # Labels: mask the prompt portion with -100
        prompt_ids = self.tokenizer(prompt, return_tensors="pt")["input_ids"]
        prompt_len = prompt_ids.shape[1]
        labels = input_ids.clone()
        labels[0, :prompt_len] = -100  # don't compute loss on prompt

        outputs = self.model(input_ids=input_ids, labels=labels)
        sup_loss = outputs.loss

        # ─ generate + verify (no_grad, fast) ─
        gen = self._generate(query, facts)
        # Clean up: take first sentence/line only
        resp = gen.split("\n")[0].strip() if gen else ""
        cs, info = self._verify_and_score(resp)

        # ─ LENGTH PENALTY ─
        resp_tokens = len(self.tokenizer.encode(resp)) if resp else 0
        if resp_tokens < self.config.min_response_tokens:
            brevity_penalty = self.config.brevity_weight
        elif resp_tokens < self.config.expected_response_tokens:
            ratio = resp_tokens / self.config.expected_response_tokens
            brevity_penalty = self.config.brevity_weight * (1.0 - ratio)
        else:
            brevity_penalty = 0.0

        # ─ VILT amplification ─
        boost = min(1.0, self.config.contradiction_weight * cs)
        multiplier = 1.0 + boost + brevity_penalty
        multiplier = min(multiplier, 2.0)  # hard cap
        vilt_loss = sup_loss * multiplier

        # ─ backprop ─
        vilt_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        return {
            "sup_loss": float(sup_loss.detach()),
            "cs": cs,
            "mult": multiplier,
            "brevity": brevity_penalty,
            "resp_tokens": resp_tokens,
            "vilt_loss": float(vilt_loss.detach()),
            "gc_pass": info["passed"],
            "hallu": info["hallucinations"],
            "contradicted": info.get("contradicted", []),
            "n_issues": info.get("n_issues", 0),
            "resp": resp[:120] if resp else "(empty)",
        }

    def evaluate(self):
        results = []
        for t in TEST_QUERIES:
            gen = self._generate(t["query"], t.get("facts"))
            resp = gen.split("\n")[0].strip() if gen else ""
            report = self.verifier.verify(
                resp if resp else "(empty)", self.fact_ledger, mode="strict"
            )
            oos = getattr(report, 'out_of_scope', [])
            scope = t.get("scope", "in-scope")

            # Determine correctness based on query type
            correct = False
            expected_slot = t.get("expected_slot")
            expected = t.get("expected")
            if expected_slot == "multi":
                correct = all(
                    v.lower() in resp.lower() for v in expected
                ) if resp and expected else False
            elif expected_slot == "mixed":
                correct = all(
                    v.lower() in resp.lower() for v in expected
                ) if resp and expected else False
            elif expected and expected_slot:
                correct = expected.lower() in resp.lower() if resp else False
            elif expected_slot is None:
                correct = report.passed

            results.append({
                "q": t["query"],
                "resp": resp[:100] if resp else "(empty)",
                "pass": report.passed,
                "ok": correct,
                "hallu": report.hallucinations[:3],
                "oos": oos[:3],
                "scope": scope,
                "n_grounded": len(report.facts_supported),
                "n_oos": len(getattr(report, 'facts_out_of_scope', {})),
                "confidence": report.confidence,
            })
        n = len(results)
        acc = sum(1 for r in results if r["ok"]) / n
        gc = sum(1 for r in results if r["pass"]) / n
        n_grounded = sum(r["n_grounded"] for r in results)
        n_oos = sum(r["n_oos"] for r in results)
        n_hallu = sum(len(r["hallu"]) for r in results)
        return {
            "results": results,
            "accuracy": acc,
            "gc_pass": gc,
            "total_grounded": n_grounded,
            "total_oos": n_oos,
            "total_hallu": n_hallu,
        }


# ==============================================================
#  MAIN
# ==============================================================

def main():
    print("=" * 70)
    print("  VILT Pretrained: SmolLM-135M + LoRA + GroundCheck")
    print("  Same VILT technique, real language model")
    print("=" * 70)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── load model ──
    print(f"\n[1] Loading {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,  # full precision, model is small
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    total_params = sum(p.numel() for p in model.parameters())
    print(f"    Base model: {total_params:,} params")
    print(f"    Device: {device}")

    # ── apply LoRA ──
    print("\n[2] Applying LoRA adapters...")
    cfg = VILTConfig()
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.lora_rank,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model = model.to(device)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    print(f"    Trainable:  {trainable_params:,} ({trainable_params/total_params:.1%})")
    print(f"    Frozen:     {frozen_params:,}")

    if device == "cuda":
        print(f"    GPU: {torch.cuda.get_device_name(0)}")
        mem = torch.cuda.memory_allocated() / 1024**3
        print(f"    VRAM used: {mem:.2f} GB")

    # ── fact ledger ──
    print(f"\n[3] Fact ledger: {len(FACT_LEDGER)} facts")
    for m in FACT_LEDGER:
        print(f"    {m.text}  (trust={m.trust})")

    # ── trainer ──
    trainer = VILTPretrainedTrainer(model, tokenizer, FACT_LEDGER, cfg, device=device)

    # ── baseline ──
    print("\n[4] Pre-VILT baseline (zero-shot)...")
    pre = trainer.evaluate()
    print(f"    Accuracy: {pre['accuracy']:.0%}   GC Pass: {pre['gc_pass']:.0%}")
    print(f"    Grounded: {pre['total_grounded']}   Out-of-scope: {pre['total_oos']}   Hallucinated: {pre['total_hallu']}")
    for r in pre["results"]:
        tag = "OK" if r["ok"] else "  "
        gc = "P" if r["pass"] else "F"
        oos_tag = f" [OOS:{r['n_oos']}]" if r["n_oos"] > 0 else ""
        print(f"    [{tag}][{gc}]{oos_tag} {r['q'][:35]:35s} -> {r['resp'][:55]}")

    # ── train ──
    print(f"\n{'='*70}")
    print(f"  VILT PRETRAINED TRAINING")
    print(f"  Model: {MODEL_NAME} + LoRA r={cfg.lora_rank}")
    print(f"  Steps: {cfg.num_steps}  LR={cfg.learning_rate}  CW={cfg.contradiction_weight}")
    print(f"  Anti-gaming: brevity_w={cfg.brevity_weight}  min_tok={cfg.min_response_tokens}")
    print(f"  Curriculum: switch at step {cfg.curriculum_switch_step}")
    print(f"  Early stop: acc>={cfg.early_stop_acc:.0%} AND gc>={cfg.early_stop_gc:.0%} for {cfg.early_stop_patience} evals")
    print(f"{'='*70}")

    old_examples = TRAINING_EXAMPLES[:8]
    new_examples = TRAINING_EXAMPLES[8:]

    t0 = time.time()
    logs = []
    early_stop_counter = 0
    stopped_early = False
    best_acc = 0.0

    for step in range(1, cfg.num_steps + 1):
        # ── CURRICULUM SCHEDULING ──
        if step <= cfg.curriculum_switch_step:
            ex = TRAINING_EXAMPLES[(step - 1) % len(TRAINING_EXAMPLES)]
        else:
            if random.random() < 0.75:
                ex = new_examples[(step - 1) % len(new_examples)]
            else:
                ex = old_examples[(step - 1) % len(old_examples)]

        r = trainer.train_step(ex["query"], ex["facts"], ex["target"])
        logs.append(r)

        if step % cfg.log_every == 0:
            recent = logs[-cfg.log_every:]
            sl = sum(x["sup_loss"] for x in recent) / len(recent)
            cs = sum(x["cs"] for x in recent) / len(recent)
            ml = sum(x["mult"] for x in recent) / len(recent)
            vl = sum(x["vilt_loss"] for x in recent) / len(recent)
            gp = sum(1 for x in recent if x["gc_pass"]) / len(recent)
            nh = sum(len(x["hallu"]) for x in recent) / len(recent)
            bp = sum(x["brevity"] for x in recent) / len(recent)
            rt = sum(x["resp_tokens"] for x in recent) / len(recent)
            el = time.time() - t0
            phase = "curriculum" if step > cfg.curriculum_switch_step else "uniform"
            print(f"\n  Step {step:3d}  ({el:.0f}s) [{phase}]")
            print(f"    sup={sl:.4f}  cs={cs:.3f}  mult={ml:.3f}  vilt={vl:.4f}")
            print(f"    GC pass={gp:.0%}  hallu/step={nh:.1f}  brevity={bp:.3f}  avg_tok={rt:.0f}")
            print(f"    \"{ex['query'][:40]}\" -> \"{r['resp'][:70]}\"")
            if r["hallu"]:
                print(f"    ! hallu: {r['hallu'][:3]}")

            triggered = [x for x in recent if x["cs"] > 0]
            if triggered:
                avg_cs = sum(x["cs"] for x in triggered) / len(triggered)
                print(f"    triggers: {len(triggered)}/{len(recent)} steps  avg_cs={avg_cs:.3f}")

        if step % cfg.eval_every == 0:
            ev = trainer.evaluate()
            print(f"\n  -- EVAL step {step} --  acc={ev['accuracy']:.0%}  gc={ev['gc_pass']:.0%}  grounded={ev['total_grounded']} oos={ev['total_oos']} hallu={ev['total_hallu']}")
            for rr in ev["results"]:
                tag = "OK" if rr["ok"] else "  "
                gc_tag = "P" if rr["pass"] else "F"
                oos_tag = f" [OOS:{rr['n_oos']}]" if rr["n_oos"] > 0 else ""
                print(f"    [{tag}][{gc_tag}]{oos_tag} {rr['q'][:30]:30s} -> {rr['resp'][:55]}")

            if ev["accuracy"] > best_acc:
                best_acc = ev["accuracy"]
                # Save best LoRA adapters
                save_dir = ROOT / "models" / "vilt_smollm" / "best_lora"
                save_dir.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(str(save_dir))
                print(f"    ** New best accuracy: {best_acc:.0%} — saved LoRA")

            # ── EARLY STOPPING ──
            if ev["accuracy"] >= cfg.early_stop_acc and ev["gc_pass"] >= cfg.early_stop_gc:
                early_stop_counter += 1
                print(f"    ** Early stop criteria met ({early_stop_counter}/{cfg.early_stop_patience})")
                if early_stop_counter >= cfg.early_stop_patience:
                    print(f"\n  EARLY STOP at step {step}!  acc={ev['accuracy']:.0%}  gc={ev['gc_pass']:.0%}")
                    stopped_early = True
                    break
            else:
                early_stop_counter = 0

    actual_steps = len(logs)
    total = time.time() - t0

    # ── final ──
    print(f"\n{'='*70}")
    stop_reason = f"EARLY STOP at step {actual_steps}" if stopped_early else f"COMPLETED {actual_steps} steps"
    print(f"  VILT PRETRAINED {stop_reason}  {total:.0f}s ({total/60:.1f} min)")
    print(f"{'='*70}")

    post = trainer.evaluate()
    print(f"\n  BEFORE -> AFTER:")
    print(f"    Accuracy:   {pre['accuracy']:.0%} -> {post['accuracy']:.0%}  (best={best_acc:.0%})")
    print(f"    GC Pass:    {pre['gc_pass']:.0%} -> {post['gc_pass']:.0%}")
    print(f"    Grounded:   {pre['total_grounded']} -> {post['total_grounded']}")
    print(f"    Out-of-scope: {pre['total_oos']} -> {post['total_oos']}")
    print(f"    Hallucinated: {pre['total_hallu']} -> {post['total_hallu']}")
    for pr, po in zip(pre["results"], post["results"]):
        a = "OK" if pr["ok"] else "  "
        b = "OK" if po["ok"] else "  "
        d = ""
        if pr["ok"] != po["ok"]:
            d = " <- IMPROVED!" if po["ok"] else " <- REGRESSED"
        print(f"\n    [{a}]->[{b}] {pr['q']}{d}")
        print(f"      before: {pr['resp'][:70]}")
        print(f"      after:  {po['resp'][:70]}")

    # ── gradient twist ──
    gc_t, cs_t, bp_t = [], [], []
    for i in range(0, len(logs), 10):
        c = logs[i : i + 10]
        gc_t.append(sum(1 for x in c if x["gc_pass"]) / len(c))
        cs_t.append(sum(x["cs"] for x in c) / len(c))
        bp_t.append(sum(x["brevity"] for x in c) / len(c))

    print(f"\n  GRADIENT TWIST OVER TIME:")
    print(f"    GC Pass:        {' -> '.join(f'{x:.0%}' for x in gc_t)}")
    print(f"    Contradiction:  {' -> '.join(f'{x:.3f}' for x in cs_t)}")
    print(f"    Brevity:        {' -> '.join(f'{x:.3f}' for x in bp_t)}")

    # ── save metrics ──
    save_dir = ROOT / "models" / "vilt_smollm"
    save_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "version": "pretrained_v1",
        "model": MODEL_NAME,
        "lora_rank": cfg.lora_rank,
        "trainable_params": trainable_params,
        "total_params": total_params,
        "pre_accuracy": pre["accuracy"], "post_accuracy": post["accuracy"],
        "best_accuracy": best_acc,
        "pre_gc_pass": pre["gc_pass"], "post_gc_pass": post["gc_pass"],
        "pre_grounded": pre["total_grounded"], "post_grounded": post["total_grounded"],
        "pre_oos": pre["total_oos"], "post_oos": post["total_oos"],
        "pre_hallu": pre["total_hallu"], "post_hallu": post["total_hallu"],
        "n_test_queries": len(TEST_QUERIES),
        "total_time_s": total, "num_steps": actual_steps,
        "stopped_early": stopped_early,
        "gc_pass_over_time": gc_t, "contradiction_over_time": cs_t,
        "brevity_over_time": bp_t,
        "config": {
            "cw": cfg.contradiction_weight, "lr": cfg.learning_rate,
            "trust_scale": cfg.trust_scale, "brevity_weight": cfg.brevity_weight,
            "curriculum_switch_step": cfg.curriculum_switch_step,
        },
    }
    mp = save_dir / "vilt_metrics.json"
    with open(mp, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Metrics -> {mp}")

    # Save final LoRA
    final_dir = save_dir / "final_lora"
    final_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"  LoRA adapters -> {final_dir}")


if __name__ == "__main__":
    main()
