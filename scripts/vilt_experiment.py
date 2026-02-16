"""
VILT: Verification-In-the-Loop Training
========================================

Wire GroundCheck contradiction detection directly into the training
gradient. When the model generates text that contradicts known facts,
the supervised loss is AMPLIFIED — scaled by CRT trust score.

Architecture:
  1. Forward pass → supervised loss (teacher forcing)
  2. Generate from model (no_grad, fast greedy decode)
  3. Pipe generation through GroundCheck.verify() against fact ledger
  4. If contradictions found → loss *= (1 + penalty * trust)
  5. Backprop the amplified loss

The key insight: GroundCheck's contradiction score acts as a DYNAMIC
LOSS MULTIPLIER. When the model would hallucinate, the gradient
becomes proportionally stronger. Trust scores from CRT gate how
aggressively the correction is applied.
"""

import sys
import time
import json
import torch
import torch.nn.functional as F
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "groundcheck"))

from personal_agent.dnnt.model import DNNTMicroTransformer
from personal_agent.dnnt.tokenizer_bpe import SentencePieceTokenizer
from groundcheck import GroundCheck, Memory


# ==============================================================
#  FACT LEDGER — the ground truth the model must respect
# ==============================================================

FACT_LEDGER = [
    Memory(id="f1", text="FACT: name = Nick",          trust=0.95),
    Memory(id="f2", text="FACT: location = Wisconsin",  trust=0.92),
    Memory(id="f3", text="FACT: occupation = freelance full-stack developer", trust=0.90),
    Memory(id="f4", text="FACT: favorite_language = Python", trust=0.85),
    Memory(id="f5", text="FACT: project = CRT-GroundCheck-SSE", trust=0.88),
    Memory(id="f6", text="FACT: framework = React",     trust=0.80),
    Memory(id="f7", text="FACT: framework = FastAPI",   trust=0.80),
    Memory(id="f8", text="FACT: editor = VS Code",      trust=0.82),
]

TEST_QUERIES = [
    {"query": "What is my name?",  "facts": ["name=Nick (trust=0.95)"],
     "expected_slot": "name",      "expected": "Nick"},
    {"query": "Where do I live?",  "facts": ["location=Wisconsin (trust=0.92)"],
     "expected_slot": "location",  "expected": "Wisconsin"},
    {"query": "What do I do?",     "facts": ["occupation=freelance full-stack developer (trust=0.90)"],
     "expected_slot": "occupation","expected": "developer"},
    {"query": "What is gravity?",  "facts": [],
     "expected_slot": None,        "expected": None},
    {"query": "What is an API?",   "facts": [],
     "expected_slot": None,        "expected": None},
]

TRAINING_EXAMPLES = [
    {"query": "What is my name?",
     "facts": ["name=Nick (trust=0.95)", "location=Wisconsin (trust=0.92)"],
     "target": " I need to recall the user's name from the facts.</think>\n<response>Your name is Nick.</response>"},
    {"query": "Where do I live?",
     "facts": ["location=Wisconsin (trust=0.92)", "name=Nick (trust=0.95)"],
     "target": " The user is asking about their location.</think>\n<response>You live in Wisconsin.</response>"},
    {"query": "What do I do for work?",
     "facts": ["occupation=freelance full-stack developer (trust=0.90)", "name=Nick (trust=0.95)"],
     "target": " Looking at the facts about the user's occupation.</think>\n<response>You are a freelance full-stack developer.</response>"},
    {"query": "What is my favorite programming language?",
     "facts": ["favorite_language=Python (trust=0.85)", "name=Nick (trust=0.95)"],
     "target": " The user wants to know their preferred language.</think>\n<response>Your favorite programming language is Python.</response>"},
    {"query": "What editor do I use?",
     "facts": ["editor=VS Code (trust=0.82)", "name=Nick (trust=0.95)"],
     "target": " Checking the facts for editor information.</think>\n<response>You use VS Code.</response>"},
    {"query": "What is my main project?",
     "facts": ["project=CRT-GroundCheck-SSE (trust=0.88)"],
     "target": " The user's main project from the facts.</think>\n<response>Your main project is CRT-GroundCheck-SSE.</response>"},
    {"query": "What is gravity?",
     "facts": [],
     "target": " This is a general knowledge question about physics.</think>\n<response>Gravity is a fundamental force that attracts objects with mass toward each other.</response>"},
    {"query": "What is an API?",
     "facts": [],
     "target": " This is a technical question about software.</think>\n<response>An API is a set of rules and protocols that allows different software applications to communicate.</response>"},
]


# ==============================================================
#  VILT CONFIG & TRAINER
# ==============================================================

@dataclass
class VILTConfig:
    contradiction_weight: float = 0.5  # max loss multiplier boost
    trust_scale: bool = True           # gate penalty by CRT trust
    learning_rate: float = 5e-5
    num_steps: int = 100
    log_every: int = 10
    eval_every: int = 25
    gen_max_tokens: int = 128
    gen_temperature: float = 0.7


class VILTTrainer:
    """Verification-In-the-Loop Training."""

    def __init__(self, model, tokenizer, fact_ledger, config=None, device="cpu"):
        self.model = model.to(device)
        self.tokenizer = tokenizer
        self.verifier = GroundCheck()
        self.fact_ledger = fact_ledger
        self.config = config or VILTConfig()
        self.device = device
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.config.learning_rate, weight_decay=0.01
        )

    def _format_prompt(self, query, facts=None):
        facts_str = "\n".join(f"- {f}" for f in (facts or [])) or "(no facts)"
        return f"<query>{query}</query>\n<facts>\n{facts_str}\n</facts>\n<think>"

    @torch.no_grad()
    def _generate(self, query, facts=None):
        """Fast greedy generation (no gradients)."""
        self.model.eval()
        prompt = self._format_prompt(query, facts)
        tokens = self.tokenizer.encode(prompt, add_special_tokens=True)
        input_ids = torch.tensor([tokens], device=self.device)
        response_close = self.tokenizer.special_tokens.get("</response>")
        stop_tokens = [t for t in [response_close] if t is not None]
        output_ids = self.model.generate(
            input_ids,
            max_new_tokens=self.config.gen_max_tokens,
            temperature=self.config.gen_temperature,
            stop_tokens=stop_tokens,
        )
        generated = output_ids[0, len(tokens) :].tolist()
        return self.tokenizer.decode(generated)

    @staticmethod
    def _extract_response(text):
        if "<response>" in text:
            resp = text.split("<response>")[-1]
            if "</response>" in resp:
                resp = resp.split("</response>")[0]
            return resp.strip()
        return text.strip()

    def _verify_and_score(self, response):
        """Run GroundCheck → return (contradiction_score, info_dict)."""
        if not response or len(response.strip()) < 3:
            return 0.0, {"passed": True, "hallucinations": [], "trust": 0.0}
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
            "contradicted": report.contradicted_claims,
            "n_issues": n_issues,
            "trust": trust,
            "score": score,
        }

    # ── THE CORE NOVELTY ──────────────────────────────────────
    def train_step(self, query, facts, target):
        """
        1. Teacher-forced supervised loss
        2. Generate → GroundCheck verify
        3. loss *= (1 + contradiction_weight * contradiction_score)
        4. Backprop the AMPLIFIED gradient
        """
        self.model.train()
        self.optimizer.zero_grad()

        # ─ supervised forward ─
        prompt = self._format_prompt(query, facts)
        full = prompt + target
        tokens = self.tokenizer.encode(full, add_special_tokens=True)
        mx = self.model.config.max_seq_length
        pad_id = self.tokenizer.special_tokens.get("<pad>", 0)
        tokens = tokens[:mx] if len(tokens) > mx else tokens + [pad_id] * (mx - len(tokens))
        inp = torch.tensor([tokens[:-1]], device=self.device)
        lbl = torch.tensor([tokens[1:]], device=self.device)
        _, sup_loss = self.model(inp, lbl)

        # ─ generate + verify (no_grad, fast) ─
        gen = self._generate(query, facts)
        resp = self._extract_response(gen)
        cs, info = self._verify_and_score(resp)

        # ─ VILT amplification ─
        multiplier = 1.0 + self.config.contradiction_weight * cs
        vilt_loss = sup_loss * multiplier

        # ─ backprop ─
        vilt_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        return {
            "sup_loss": float(sup_loss.detach()),
            "cs": cs,
            "mult": multiplier,
            "vilt_loss": float(vilt_loss.detach()),
            "gc_pass": info["passed"],
            "hallu": info["hallucinations"],
            "resp": resp[:100] if resp else "(empty)",
        }

    def evaluate(self):
        results = []
        for t in TEST_QUERIES:
            gen = self._generate(t["query"], t.get("facts"))
            resp = self._extract_response(gen)
            report = self.verifier.verify(
                resp if resp else "(empty)", self.fact_ledger, mode="strict"
            )
            correct = False
            if t["expected"] and t["expected_slot"]:
                correct = t["expected"].lower() in resp.lower() if resp else False
            elif t["expected_slot"] is None:
                correct = report.passed
            results.append({
                "q": t["query"], "resp": resp[:80] if resp else "(empty)",
                "pass": report.passed, "ok": correct,
                "hallu": report.hallucinations[:3],
            })
        acc = sum(1 for r in results if r["ok"]) / len(results)
        gc = sum(1 for r in results if r["pass"]) / len(results)
        return {"results": results, "accuracy": acc, "gc_pass": gc}


# ==============================================================
#  MAIN
# ==============================================================

def main():
    print("=" * 70)
    print("  VILT: Verification-In-the-Loop Training")
    print("  GroundCheck x CRT Trust -> Training Gradient")
    print("=" * 70)

    model_dir = ROOT / "models" / "dnnt_v2"

    # ── load model (prefer model/ which trained longer) ──
    print("\n[1] Loading DNNT model...")
    for sub in ["model", "best_model"]:
        cfg = model_dir / sub / "config.json"
        if cfg.exists():
            model = DNNTMicroTransformer.load(str(model_dir / sub))
            print(f"    Loaded from {sub}/ ({model.n_params:,} params)")
            break
    else:
        print("    ERROR: no model"); return

    print("\n[2] Loading tokenizer...")
    tok_path = model_dir / "tokenizer_assets" / "tokenizer_sentencepiece.model"
    tokenizer = SentencePieceTokenizer(str(tok_path))
    print(f"    Vocab: {tokenizer.vocab_size}")

    print(f"\n[3] Fact ledger: {len(FACT_LEDGER)} facts")
    for m in FACT_LEDGER:
        print(f"    {m.text}  (trust={m.trust})")

    cfg = VILTConfig(num_steps=100, learning_rate=5e-5, contradiction_weight=0.5)
    trainer = VILTTrainer(model, tokenizer, FACT_LEDGER, cfg)

    # ── baseline ──
    print("\n[4] Pre-VILT baseline...")
    pre = trainer.evaluate()
    print(f"    Accuracy: {pre['accuracy']:.0%}   GC Pass: {pre['gc_pass']:.0%}")
    for r in pre["results"]:
        tag = "OK" if r["ok"] else "  "
        gc = "P" if r["pass"] else "F"
        print(f"    [{tag}][{gc}] {r['q'][:35]:35s} -> {r['resp'][:50]}")

    # ── train ──
    print(f"\n{'='*70}")
    print(f"  VILT TRAINING: {cfg.num_steps} steps   LR={cfg.learning_rate}  CW={cfg.contradiction_weight}")
    print(f"{'='*70}")

    t0 = time.time()
    logs = []
    for step in range(1, cfg.num_steps + 1):
        ex = TRAINING_EXAMPLES[(step - 1) % len(TRAINING_EXAMPLES)]
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
            el = time.time() - t0
            print(f"\n  Step {step:3d}  ({el:.0f}s)")
            print(f"    sup={sl:.4f}  cs={cs:.3f}  mult={ml:.3f}  vilt={vl:.4f}")
            print(f"    GC pass={gp:.0%}  hallu/step={nh:.1f}")
            print(f"    \"{ex['query']}\" -> \"{r['resp'][:60]}\"")
            if r["hallu"]:
                print(f"    ! {r['hallu'][:3]}")

        if step % cfg.eval_every == 0:
            ev = trainer.evaluate()
            print(f"\n  -- EVAL step {step} --  acc={ev['accuracy']:.0%}  gc={ev['gc_pass']:.0%}")
            for rr in ev["results"]:
                tag = "OK" if rr["ok"] else "  "
                gc = "P" if rr["pass"] else "F"
                print(f"    [{tag}][{gc}] {rr['q'][:30]:30s} -> {rr['resp'][:50]}")

    total = time.time() - t0

    # ── final ──
    print(f"\n{'='*70}")
    print(f"  VILT COMPLETE  {total:.0f}s ({total/60:.1f} min)")
    print(f"{'='*70}")

    post = trainer.evaluate()
    print(f"\n  BEFORE -> AFTER:")
    print(f"    Accuracy:   {pre['accuracy']:.0%} -> {post['accuracy']:.0%}")
    print(f"    GC Pass:    {pre['gc_pass']:.0%} -> {post['gc_pass']:.0%}")
    for pr, po in zip(pre["results"], post["results"]):
        a = "OK" if pr["ok"] else "  "
        b = "OK" if po["ok"] else "  "
        d = ""
        if pr["ok"] != po["ok"]:
            d = " <- IMPROVED!" if po["ok"] else " <- REGRESSED"
        print(f"\n    [{a}]->[{b}] {pr['q']}{d}")
        print(f"      before: {pr['resp'][:60]}")
        print(f"      after:  {po['resp'][:60]}")

    # ── gradient twist over time ──
    gc_t, cs_t = [], []
    for i in range(0, len(logs), 10):
        c = logs[i : i + 10]
        gc_t.append(sum(1 for x in c if x["gc_pass"]) / len(c))
        cs_t.append(sum(x["cs"] for x in c) / len(c))
    print(f"\n  GRADIENT TWIST OVER TIME:")
    print(f"    GC Pass:        {' -> '.join(f'{x:.0%}' for x in gc_t)}")
    print(f"    Contradiction:  {' -> '.join(f'{x:.3f}' for x in cs_t)}")

    # ── save ──
    metrics = {
        "pre_accuracy": pre["accuracy"], "post_accuracy": post["accuracy"],
        "pre_gc_pass": pre["gc_pass"], "post_gc_pass": post["gc_pass"],
        "total_time_s": total, "num_steps": cfg.num_steps,
        "gc_pass_over_time": gc_t, "contradiction_over_time": cs_t,
        "config": {"cw": cfg.contradiction_weight, "lr": cfg.learning_rate,
                   "trust_scale": cfg.trust_scale},
    }
    mp = model_dir / "vilt_metrics.json"
    with open(mp, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Metrics -> {mp}")

    vd = model_dir / "vilt_model"
    model.save(str(vd))
    tokenizer.save(str(vd / "tokenizer.json"))
    print(f"  Model  -> {vd}")


if __name__ == "__main__":
    main()
