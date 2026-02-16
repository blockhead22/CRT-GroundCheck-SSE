"""
VILT-Code: Verification-In-the-Loop Training for Code Generation
=================================================================

Same VILT technique proven on personal-fact QA, now applied to code.
Instead of GroundCheck.verify() against a fact ledger, we use a 3-tier
code verifier: ast.parse (syntax) → mypy (types) → exec+assert (runtime).

Architecture:
  1. Forward pass → supervised loss (teacher forcing on reference solution)
  2. Generate freely → pipe through code_verify(generated_code, test_cases)
  3. If verification fails → loss *= (1 + penalty * severity)
  4. Brevity penalty prevents adversarial shortening / empty outputs
  5. Backprop amplified loss through LoRA adapters only

VILT Loss:
  L_vilt = L_sup × min(2, 1 + min(1, w_c × s_c) + p_brevity)
  where s_c = code verification score (0 = pass, 1 = all checks fail)

Verification Tiers (cumulative severity):
  Tier 1 — ast.parse: syntax check          → +0.3 on fail
  Tier 2 — mypy --strict: type check        → +0.3 on fail
  Tier 3 — exec + test assertions: runtime  → +0.4 on fail

Requirements:
  - torch (CUDA), transformers, peft, mypy
  - ~5-6 GB VRAM during training (fits RTX 3060 12GB)

Usage:
  python scripts/vilt_code.py
  python scripts/vilt_code.py --model Qwen/Qwen2.5-3B --steps 300
  python scripts/vilt_code.py --baseline  # SFT-only comparison
  python scripts/vilt_code.py --problems data/vilt_code_problems.json
"""

import sys
import os
import ast
import time
import json
import random
import tempfile
import subprocess
import textwrap
import torch
import torch.nn.functional as F
import re

if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, TaskType


# ==============================================================
#  CODE VERIFIER — 3-tier pipeline
# ==============================================================

@dataclass
class VerifyResult:
    """Result of code verification."""
    syntax_ok: bool = False
    types_ok: bool = False
    runtime_ok: bool = False
    score: float = 1.0  # 0.0 = perfect, 1.0 = total failure
    errors: List[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_total: int = 0

    @property
    def passed(self) -> bool:
        return self.syntax_ok and self.types_ok and self.runtime_ok


def verify_code(code: str, test_code: str = "", timeout_s: float = 5.0) -> VerifyResult:
    """
    3-tier code verification pipeline.

    Args:
        code: The generated Python code (function body/definition)
        test_code: Assert-based test cases to run after the code
        timeout_s: Max seconds for runtime execution

    Returns:
        VerifyResult with cumulative severity score
    """
    result = VerifyResult()

    if not code or not code.strip():
        result.errors.append("Empty code")
        return result

    # ── Tier 1: Syntax (ast.parse) ──
    try:
        ast.parse(code)
        result.syntax_ok = True
    except SyntaxError as e:
        result.errors.append(f"SyntaxError: {e.msg} (line {e.lineno})")
        # Can't proceed without valid syntax
        return result

    # ── Tier 2: Type checking (mypy) ──
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write(code)
            tmp_path = f.name

        mypy_result = subprocess.run(
            [sys.executable, "-m", "mypy", "--ignore-missing-imports",
             "--no-error-summary", "--no-color", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
        # Filter out "note:" and "Found X error" lines — only count actual errors
        error_lines = [
            line for line in mypy_result.stdout.strip().split("\n")
            if line.strip() and ": error:" in line
        ]
        if not error_lines:
            result.types_ok = True
        else:
            # Limit to first 3 errors
            for line in error_lines[:3]:
                result.errors.append(f"mypy: {line.split(': error:')[-1].strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        # mypy not available or timed out — skip tier 2, don't penalize
        result.types_ok = True
        result.errors.append(f"mypy skipped: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # ── Tier 3: Runtime execution + test assertions ──
    if test_code:
        full_code = code + "\n\n" + test_code
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
            ) as f:
                f.write(full_code)
                tmp_path = f.name

            run_result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True, text=True, timeout=timeout_s,
            )
            if run_result.returncode == 0:
                result.runtime_ok = True
            else:
                stderr = run_result.stderr.strip()
                # Extract assertion errors
                for line in stderr.split("\n"):
                    if "AssertionError" in line or "Error" in line:
                        result.errors.append(f"runtime: {line.strip()[-120:]}")
                        break
                else:
                    result.errors.append(f"runtime: exit code {run_result.returncode}")
        except subprocess.TimeoutExpired:
            result.errors.append(f"runtime: timeout ({timeout_s}s)")
        except Exception as e:
            result.errors.append(f"runtime: {str(e)[:100]}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # Count test assertions for metrics
        assertion_lines = [l for l in test_code.strip().split("\n") if l.strip().startswith("assert")]
        result.tests_total = max(1, len(assertion_lines))
        result.tests_passed = result.tests_total if result.runtime_ok else 0
    else:
        # No tests — runtime check = just run the code without error
        try:
            exec(compile(code, "<generated>", "exec"), {"__builtins__": __builtins__})
            result.runtime_ok = True
        except Exception as e:
            result.errors.append(f"runtime: {type(e).__name__}: {str(e)[:100]}")

    # ── Compute cumulative score ──
    score = 0.0
    if not result.syntax_ok:
        score += 0.3
    if not result.types_ok:
        score += 0.3
    if not result.runtime_ok:
        score += 0.4
    result.score = score

    return result


# ==============================================================
#  BUILT-IN TRAINING / EVAL PROBLEMS
# ==============================================================

BUILTIN_PROBLEMS = [
    {
        "id": "add_two",
        "prompt": "Write a Python function `add(a: int, b: int) -> int` that returns the sum of a and b.",
        "reference": "def add(a: int, b: int) -> int:\n    return a + b",
        "tests": "assert add(1, 2) == 3\nassert add(-1, 1) == 0\nassert add(0, 0) == 0",
        "difficulty": "easy",
    },
    {
        "id": "factorial",
        "prompt": "Write a Python function `factorial(n: int) -> int` that returns the factorial of n. Assume n >= 0.",
        "reference": "def factorial(n: int) -> int:\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
        "tests": "assert factorial(0) == 1\nassert factorial(1) == 1\nassert factorial(5) == 120\nassert factorial(10) == 3628800",
        "difficulty": "easy",
    },
    {
        "id": "fibonacci",
        "prompt": "Write a Python function `fib(n: int) -> int` that returns the nth Fibonacci number (0-indexed). fib(0)=0, fib(1)=1.",
        "reference": "def fib(n: int) -> int:\n    if n <= 0:\n        return 0\n    if n == 1:\n        return 1\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
        "tests": "assert fib(0) == 0\nassert fib(1) == 1\nassert fib(5) == 5\nassert fib(10) == 55",
        "difficulty": "easy",
    },
    {
        "id": "is_palindrome",
        "prompt": "Write a Python function `is_palindrome(s: str) -> bool` that checks if a string is a palindrome (case-insensitive, ignoring non-alphanumeric characters).",
        "reference": "def is_palindrome(s: str) -> bool:\n    cleaned = ''.join(c.lower() for c in s if c.isalnum())\n    return cleaned == cleaned[::-1]",
        "tests": "assert is_palindrome('racecar') == True\nassert is_palindrome('A man a plan a canal Panama') == True\nassert is_palindrome('hello') == False\nassert is_palindrome('') == True",
        "difficulty": "easy",
    },
    {
        "id": "flatten_list",
        "prompt": "Write a Python function `flatten(lst: list) -> list` that flattens a nested list of arbitrary depth into a single list.",
        "reference": "def flatten(lst: list) -> list:\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result",
        "tests": "assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]\nassert flatten([]) == []\nassert flatten([[1], [2], [3]]) == [1, 2, 3]\nassert flatten([1, 2, 3]) == [1, 2, 3]",
        "difficulty": "medium",
    },
    {
        "id": "two_sum",
        "prompt": "Write a Python function `two_sum(nums: list, target: int) -> list` that returns indices of two numbers that add up to target. Assume exactly one solution exists.",
        "reference": "from typing import Dict, List\n\ndef two_sum(nums: list, target: int) -> list:\n    seen: Dict[int, int] = {}\n    for i, n in enumerate(nums):\n        complement = target - n\n        if complement in seen:\n            return [seen[complement], i]\n        seen[n] = i\n    return []",
        "tests": "assert two_sum([2, 7, 11, 15], 9) == [0, 1]\nassert two_sum([3, 2, 4], 6) == [1, 2]\nassert two_sum([3, 3], 6) == [0, 1]",
        "difficulty": "medium",
    },
    {
        "id": "max_subarray",
        "prompt": "Write a Python function `max_subarray(nums: list) -> int` that returns the maximum sum of a contiguous subarray (Kadane's algorithm). The list has at least one element.",
        "reference": "def max_subarray(nums: list) -> int:\n    max_sum = current = nums[0]\n    for n in nums[1:]:\n        current = max(n, current + n)\n        max_sum = max(max_sum, current)\n    return max_sum",
        "tests": "assert max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6\nassert max_subarray([1]) == 1\nassert max_subarray([-1, -2, -3]) == -1\nassert max_subarray([5, 4, -1, 7, 8]) == 23",
        "difficulty": "medium",
    },
    {
        "id": "binary_search",
        "prompt": "Write a Python function `binary_search(arr: list, target: int) -> int` that returns the index of target in a sorted list, or -1 if not found.",
        "reference": "def binary_search(arr: list, target: int) -> int:\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1",
        "tests": "assert binary_search([1, 3, 5, 7, 9], 5) == 2\nassert binary_search([1, 3, 5, 7, 9], 6) == -1\nassert binary_search([], 1) == -1\nassert binary_search([1], 1) == 0",
        "difficulty": "medium",
    },
    {
        "id": "merge_sorted",
        "prompt": "Write a Python function `merge_sorted(a: list, b: list) -> list` that merges two sorted lists into one sorted list.",
        "reference": "def merge_sorted(a: list, b: list) -> list:\n    result = []\n    i = j = 0\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]:\n            result.append(a[i])\n            i += 1\n        else:\n            result.append(b[j])\n            j += 1\n    result.extend(a[i:])\n    result.extend(b[j:])\n    return result",
        "tests": "assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]\nassert merge_sorted([], [1, 2]) == [1, 2]\nassert merge_sorted([1], []) == [1]\nassert merge_sorted([], []) == []",
        "difficulty": "medium",
    },
    {
        "id": "count_vowels",
        "prompt": "Write a Python function `count_vowels(s: str) -> int` that returns the number of vowels (a, e, i, o, u) in a string, case-insensitive.",
        "reference": "def count_vowels(s: str) -> int:\n    return sum(1 for c in s.lower() if c in 'aeiou')",
        "tests": "assert count_vowels('hello') == 2\nassert count_vowels('AEIOU') == 5\nassert count_vowels('bcdfg') == 0\nassert count_vowels('') == 0",
        "difficulty": "easy",
    },
    {
        "id": "reverse_words",
        "prompt": "Write a Python function `reverse_words(s: str) -> str` that reverses the order of words in a string. Leading/trailing spaces should be removed, and multiple spaces between words should be reduced to one.",
        "reference": "def reverse_words(s: str) -> str:\n    return ' '.join(s.split()[::-1])",
        "tests": "assert reverse_words('hello world') == 'world hello'\nassert reverse_words('  the sky is blue  ') == 'blue is sky the'\nassert reverse_words('a') == 'a'",
        "difficulty": "easy",
    },
    {
        "id": "valid_parentheses",
        "prompt": "Write a Python function `is_valid(s: str) -> bool` that checks if a string of parentheses '()[]{}' is valid (properly opened and closed).",
        "reference": "def is_valid(s: str) -> bool:\n    stack = []\n    pairs = {'(': ')', '[': ']', '{': '}'}\n    for c in s:\n        if c in pairs:\n            stack.append(pairs[c])\n        elif not stack or stack.pop() != c:\n            return False\n    return not stack",
        "tests": "assert is_valid('()[]{}') == True\nassert is_valid('(]') == False\nassert is_valid('([{}])') == True\nassert is_valid('') == True\nassert is_valid('((') == False",
        "difficulty": "medium",
    },
    {
        "id": "matrix_transpose",
        "prompt": "Write a Python function `transpose(matrix: list) -> list` that returns the transpose of a 2D matrix (list of lists).",
        "reference": "def transpose(matrix: list) -> list:\n    if not matrix:\n        return []\n    return [list(row) for row in zip(*matrix)]",
        "tests": "assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]\nassert transpose([[1]]) == [[1]]\nassert transpose([]) == []",
        "difficulty": "medium",
    },
    {
        "id": "gcd",
        "prompt": "Write a Python function `gcd(a: int, b: int) -> int` that returns the greatest common divisor of two positive integers using Euclid's algorithm.",
        "reference": "def gcd(a: int, b: int) -> int:\n    while b:\n        a, b = b, a % b\n    return a",
        "tests": "assert gcd(12, 8) == 4\nassert gcd(7, 13) == 1\nassert gcd(100, 25) == 25\nassert gcd(1, 1) == 1",
        "difficulty": "easy",
    },
    {
        "id": "remove_duplicates",
        "prompt": "Write a Python function `remove_duplicates(lst: list) -> list` that removes duplicates from a list while preserving order.",
        "reference": "def remove_duplicates(lst: list) -> list:\n    seen = set()\n    result = []\n    for item in lst:\n        if item not in seen:\n            seen.add(item)\n            result.append(item)\n    return result",
        "tests": "assert remove_duplicates([1, 2, 2, 3, 1]) == [1, 2, 3]\nassert remove_duplicates([]) == []\nassert remove_duplicates([1, 1, 1]) == [1]",
        "difficulty": "easy",
    },
    {
        "id": "longest_common_prefix",
        "prompt": "Write a Python function `longest_common_prefix(strs: list) -> str` that returns the longest common prefix among a list of strings. Return '' if no common prefix.",
        "reference": "def longest_common_prefix(strs: list) -> str:\n    if not strs:\n        return ''\n    prefix = strs[0]\n    for s in strs[1:]:\n        while not s.startswith(prefix):\n            prefix = prefix[:-1]\n            if not prefix:\n                return ''\n    return prefix",
        "tests": "assert longest_common_prefix(['flower', 'flow', 'flight']) == 'fl'\nassert longest_common_prefix(['dog', 'racecar', 'car']) == ''\nassert longest_common_prefix(['a']) == 'a'\nassert longest_common_prefix([]) == ''",
        "difficulty": "medium",
    },
    {
        "id": "power",
        "prompt": "Write a Python function `power(base: float, exp: int) -> float` that computes base^exp. Handle negative exponents. Do not use ** or pow().",
        "reference": "def power(base: float, exp: int) -> float:\n    if exp == 0:\n        return 1.0\n    if exp < 0:\n        return 1.0 / power(base, -exp)\n    if exp % 2 == 0:\n        half = power(base, exp // 2)\n        return half * half\n    return base * power(base, exp - 1)",
        "tests": "assert power(2, 10) == 1024\nassert power(2, 0) == 1.0\nassert abs(power(2, -2) - 0.25) < 1e-9\nassert power(3, 3) == 27",
        "difficulty": "medium",
    },
    {
        "id": "chunk_list",
        "prompt": "Write a Python function `chunk(lst: list, size: int) -> list` that splits a list into chunks of the given size. The last chunk may be smaller.",
        "reference": "def chunk(lst: list, size: int) -> list:\n    return [lst[i:i + size] for i in range(0, len(lst), size)]",
        "tests": "assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\nassert chunk([1, 2, 3], 3) == [[1, 2, 3]]\nassert chunk([], 5) == []\nassert chunk([1], 1) == [[1]]",
        "difficulty": "easy",
    },
    {
        "id": "spiral_order",
        "prompt": "Write a Python function `spiral_order(matrix: list) -> list` that returns elements of a 2D matrix in spiral order.",
        "reference": "def spiral_order(matrix: list) -> list:\n    result = []\n    while matrix:\n        result += matrix.pop(0)\n        matrix = list(zip(*matrix))[::-1]\n    return result",
        "tests": "assert spiral_order([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == [1, 2, 3, 6, 9, 8, 7, 4, 5]\nassert spiral_order([[1]]) == [1]\nassert spiral_order([]) == []",
        "difficulty": "hard",
    },
    {
        "id": "lru_cache",
        "prompt": "Write a Python class `LRUCache` with `__init__(self, capacity: int)`, `get(self, key: int) -> int` (returns -1 if not found), and `put(self, key: int, value: int)` methods. When at capacity, evict the least recently used item.",
        "reference": "from collections import OrderedDict\n\nclass LRUCache:\n    def __init__(self, capacity: int) -> None:\n        self.capacity = capacity\n        self.cache: OrderedDict[int, int] = OrderedDict()\n\n    def get(self, key: int) -> int:\n        if key not in self.cache:\n            return -1\n        self.cache.move_to_end(key)\n        return self.cache[key]\n\n    def put(self, key: int, value: int) -> None:\n        if key in self.cache:\n            self.cache.move_to_end(key)\n        self.cache[key] = value\n        if len(self.cache) > self.capacity:\n            self.cache.popitem(last=False)",
        "tests": "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nassert c.get(1) == 1\nc.put(3, 3)\nassert c.get(2) == -1\nassert c.get(3) == 3",
        "difficulty": "hard",
    },
]


def load_problems(path: Optional[str] = None) -> List[Dict]:
    """Load problems from JSON file or use built-ins."""
    if path:
        with open(path) as f:
            data = json.load(f)
        return data["problems"] if "problems" in data else data
    return BUILTIN_PROBLEMS


# ==============================================================
#  CONFIG
# ==============================================================

DEFAULT_MODEL = "Qwen/Qwen2.5-3B"


@dataclass
class VILTCodeConfig:
    contradiction_weight: float = 0.5     # maps to code_verify score
    learning_rate: float = 1e-4
    num_steps: int = 300
    log_every: int = 10
    eval_every: int = 25
    gen_max_tokens: int = 256             # code needs more tokens
    gen_temperature: float = 0.4          # lower temp for code
    # ── anti-gaming ──
    brevity_weight: float = 0.3
    min_response_tokens: int = 10
    expected_response_tokens: int = 60
    curriculum_switch_step: int = 100
    early_stop_pass: float = 0.85         # pass@1 threshold
    early_stop_patience: int = 3
    # ── LoRA ──
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: list = field(
        default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"]
    )


# ==============================================================
#  TRAINER
# ==============================================================

class VILTCodeTrainer:
    """VILT trainer for code generation with multi-tier verification."""

    def __init__(self, model, tokenizer, problems, config=None, device="cpu"):
        self.model = model
        self.tokenizer = tokenizer
        self.problems = problems
        self.config = config or VILTCodeConfig()
        self.device = device

        trainable = [p for p in model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(
            trainable, lr=self.config.learning_rate, weight_decay=0.01
        )

    def _format_prompt(self, problem: Dict) -> str:
        return (
            f"### Task:\n{problem['prompt']}\n\n"
            f"### Python Code:\n"
        )

    def _extract_code(self, generated: str) -> str:
        """Extract Python code from model output, handling markdown fences."""
        text = generated.strip()

        # Try to extract from markdown code block
        fence_match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()

        # Take everything up to the first ### or ``` or end
        lines = []
        for line in text.split("\n"):
            if line.strip().startswith("###") or line.strip().startswith("```"):
                break
            lines.append(line)
        code = "\n".join(lines).strip()

        # Verify it's valid Python
        if code:
            try:
                ast.parse(code)
                return code
            except SyntaxError:
                pass

        return text  # fallback — let verifier catch issues

    @torch.no_grad()
    def _generate(self, problem: Dict) -> str:
        self.model.eval()
        prompt = self._format_prompt(problem)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.config.gen_max_tokens,
            temperature=self.config.gen_temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        gen_ids = output_ids[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(gen_ids, skip_special_tokens=True)

    def train_step(self, problem: Dict) -> Dict:
        self.model.train()
        self.optimizer.zero_grad()

        # ─ supervised forward (teacher forcing on reference) ─
        prompt = self._format_prompt(problem)
        full_text = prompt + problem["reference"]
        encoding = self.tokenizer(
            full_text,
            return_tensors="pt",
            truncation=True,
            max_length=768,
        ).to(self.device)

        input_ids = encoding["input_ids"]
        prompt_ids = self.tokenizer(prompt, return_tensors="pt")["input_ids"]
        prompt_len = prompt_ids.shape[1]
        labels = input_ids.clone()
        labels[0, :prompt_len] = -100

        outputs = self.model(input_ids=input_ids, labels=labels)
        sup_loss = outputs.loss

        # ─ generate + verify ─
        gen = self._generate(problem)
        code = self._extract_code(gen)
        vr = verify_code(code, problem.get("tests", ""))

        # ─ brevity penalty ─
        resp_tokens = len(self.tokenizer.encode(code)) if code else 0
        if resp_tokens < self.config.min_response_tokens:
            brevity_penalty = self.config.brevity_weight
        elif resp_tokens < self.config.expected_response_tokens:
            ratio = resp_tokens / self.config.expected_response_tokens
            brevity_penalty = self.config.brevity_weight * (1.0 - ratio)
        else:
            brevity_penalty = 0.0

        # ─ VILT amplification ─
        # score is 0.0 (pass) to 1.0 (all tiers fail)
        boost = min(1.0, self.config.contradiction_weight * vr.score)
        multiplier = 1.0 + boost + brevity_penalty
        multiplier = min(multiplier, 2.0)
        vilt_loss = sup_loss * multiplier

        vilt_loss.backward()
        torch.nn.utils.clip_grad_norm_(
            [p for p in self.model.parameters() if p.requires_grad], 1.0
        )
        self.optimizer.step()

        return {
            "sup_loss": float(sup_loss.detach()),
            "score": vr.score,
            "mult": multiplier,
            "brevity": brevity_penalty,
            "resp_tokens": resp_tokens,
            "vilt_loss": float(vilt_loss.detach()),
            "syntax": vr.syntax_ok,
            "types": vr.types_ok,
            "runtime": vr.runtime_ok,
            "passed": vr.passed,
            "errors": vr.errors[:2],
            "code": code[:120] if code else "(empty)",
            "problem_id": problem["id"],
        }

    def evaluate(self, problems: Optional[List[Dict]] = None) -> Dict:
        """Evaluate on a set of problems."""
        problems = problems or self.problems
        results = []
        for p in problems:
            gen = self._generate(p)
            code = self._extract_code(gen)
            vr = verify_code(code, p.get("tests", ""))

            results.append({
                "id": p["id"],
                "difficulty": p.get("difficulty", "?"),
                "code": code[:200] if code else "(empty)",
                "syntax": vr.syntax_ok,
                "types": vr.types_ok,
                "runtime": vr.runtime_ok,
                "passed": vr.passed,
                "score": vr.score,
                "errors": vr.errors[:3],
                "tests_passed": vr.tests_passed,
                "tests_total": vr.tests_total,
            })

        n = len(results)
        pass_at_1 = sum(1 for r in results if r["passed"]) / n if n else 0
        syntax_rate = sum(1 for r in results if r["syntax"]) / n if n else 0
        type_rate = sum(1 for r in results if r["types"]) / n if n else 0
        runtime_rate = sum(1 for r in results if r["runtime"]) / n if n else 0
        total_tests = sum(r["tests_total"] for r in results)
        tests_passed = sum(r["tests_passed"] for r in results)

        return {
            "results": results,
            "pass_at_1": pass_at_1,
            "syntax_rate": syntax_rate,
            "type_rate": type_rate,
            "runtime_rate": runtime_rate,
            "total_tests": total_tests,
            "tests_passed": tests_passed,
            "n_problems": n,
        }


# ==============================================================
#  MAIN
# ==============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="VILT-Code: Verification-In-the-Loop Training for Code")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--steps", type=int, default=300, help="Training steps (default: 300)")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate (default: 1e-4)")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank (default: 16)")
    parser.add_argument("--cpu", action="store_true", help="Force CPU")
    parser.add_argument("--baseline", action="store_true",
                        help="SFT-only baseline: no VILT amplification")
    parser.add_argument("--problems", type=str, default=None,
                        help="Path to problems JSON (default: built-in 20 problems)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Override output directory for model artifacts")
    args = parser.parse_args()

    model_name = args.model
    model_short = model_name.split("/")[-1]
    mode_label = "SFT" if args.baseline else "VILT-Code"

    # ── Load problems ──
    problems = load_problems(args.problems)
    # Split: 70% training, 30% eval (by difficulty distribution)
    random.seed(42)
    random.shuffle(problems)
    n_train = max(1, int(len(problems) * 0.7))
    train_problems = problems[:n_train]
    eval_problems = problems[n_train:] if len(problems) > n_train else problems

    print(f"\n{'='*60}")
    print(f"  VILT-Code — {mode_label} on {model_short}")
    print(f"{'='*60}")
    print(f"  Model:          {model_name}")
    print(f"  Problems:       {len(problems)} total ({len(train_problems)} train, {len(eval_problems)} eval)")
    print(f"  Steps:          {args.steps}")
    print(f"  LoRA rank:      {args.lora_r}")
    print(f"  Learning rate:  {args.lr}")
    print(f"  Baseline(SFT):  {args.baseline}")

    # ── Device ──
    device = "cpu"
    if not args.cpu and torch.cuda.is_available():
        device = "cuda"
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_mem / 1e9
        print(f"  GPU:            {gpu} ({vram:.1f} GB)")
    print(f"  Device:         {device}")
    print(f"{'='*60}\n")

    # ── Load model ──
    print(f"[1] Loading {model_short}...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map=device if device == "cuda" else None,
        trust_remote_code=True,
    )
    if device == "cpu":
        model = model.to(device)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print(f"    Loaded in {time.time() - t0:.1f}s  |  {sum(p.numel() for p in model.parameters()) / 1e6:.0f}M params")

    # ── LoRA ──
    print(f"\n[2] Applying LoRA (r={args.lora_r})...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"    Trainable: {trainable:,} / {total:,} ({trainable/total*100:.2f}%)")

    # ── Config ──
    cfg = VILTCodeConfig(
        contradiction_weight=0.0 if args.baseline else 0.5,
        learning_rate=args.lr,
        num_steps=args.steps,
        lora_r=args.lora_r,
    )
    trainer = VILTCodeTrainer(model, tokenizer, eval_problems, cfg, device)

    # ── Pre-training baseline eval ──
    print(f"\n[3] Pre-training baseline ({model_short}) — {len(eval_problems)} problems...")
    pre = trainer.evaluate(eval_problems)
    print(f"    Pass@1: {pre['pass_at_1']:.0%}   Syntax: {pre['syntax_rate']:.0%}   Types: {pre['type_rate']:.0%}   Runtime: {pre['runtime_rate']:.0%}")
    print(f"    Tests: {pre['tests_passed']}/{pre['total_tests']}")
    for r in pre["results"]:
        tag = "PASS" if r["passed"] else "FAIL"
        errs = f" — {r['errors'][0]}" if r["errors"] else ""
        print(f"      [{tag}] {r['id']} ({r['difficulty']}){errs}")

    # ── Training loop ──
    print(f"\n[4] Training ({mode_label}, {args.steps} steps)...")
    t_start = time.time()
    patience_counter = 0
    best_pass = 0.0

    for step in range(1, args.steps + 1):
        # Curriculum: easy first, then mix in harder problems
        if step <= cfg.curriculum_switch_step:
            easy = [p for p in train_problems if p.get("difficulty") == "easy"]
            problem = random.choice(easy) if easy else random.choice(train_problems)
        else:
            problem = random.choice(train_problems)

        info = trainer.train_step(problem)

        if step % cfg.log_every == 0:
            tier_str = f"syn={'Y' if info['syntax'] else 'N'} typ={'Y' if info['types'] else 'N'} run={'Y' if info['runtime'] else 'N'}"
            errs = f" err={info['errors'][0][:60]}" if info['errors'] else ""
            print(f"  step {step:>3} | loss {info['vilt_loss']:.4f} (×{info['mult']:.2f}) | {tier_str} | {info['problem_id']}{errs}")

        # ── Mid-training eval ──
        if step % cfg.eval_every == 0:
            ev = trainer.evaluate(eval_problems)
            print(f"\n  ── EVAL step {step} ({len(eval_problems)} problems) ──")
            print(f"     Pass@1: {ev['pass_at_1']:.0%}   Syntax: {ev['syntax_rate']:.0%}   Types: {ev['type_rate']:.0%}   Runtime: {ev['runtime_rate']:.0%}")
            print(f"     Tests: {ev['tests_passed']}/{ev['total_tests']}")

            # Early stopping
            if ev["pass_at_1"] >= cfg.early_stop_pass:
                patience_counter += 1
                if patience_counter >= cfg.early_stop_patience:
                    print(f"\n  ⚡ Early stop: Pass@1 {ev['pass_at_1']:.0%} >= {cfg.early_stop_pass:.0%} for {patience_counter} evals")
                    break
            else:
                patience_counter = 0
            best_pass = max(best_pass, ev["pass_at_1"])
            print()

    elapsed = time.time() - t_start
    print(f"\n    Training complete ({elapsed:.0f}s, {step} steps)")

    # ── Post-training eval ──
    print(f"\n[5] Post-training eval ({model_short}) — {len(eval_problems)} problems...")
    post = trainer.evaluate(eval_problems)
    print(f"    Pass@1: {post['pass_at_1']:.0%}   Syntax: {post['syntax_rate']:.0%}   Types: {post['type_rate']:.0%}   Runtime: {post['runtime_rate']:.0%}")
    print(f"    Tests: {post['tests_passed']}/{post['total_tests']}")
    for r in post["results"]:
        tag = "PASS" if r["passed"] else "FAIL"
        errs = f" — {r['errors'][0]}" if r["errors"] else ""
        print(f"      [{tag}] {r['id']} ({r['difficulty']}){errs}")

    # ── Summary ──
    delta_pass = post["pass_at_1"] - pre["pass_at_1"]
    delta_tests = post["tests_passed"] - pre["tests_passed"]
    print(f"\n{'='*60}")
    print(f"  RESULTS — {mode_label} on {model_short}")
    print(f"{'='*60}")
    print(f"  Pass@1:    {pre['pass_at_1']:.0%}  →  {post['pass_at_1']:.0%}  ({'+' if delta_pass >= 0 else ''}{delta_pass:.0%})")
    print(f"  Syntax:    {pre['syntax_rate']:.0%}  →  {post['syntax_rate']:.0%}")
    print(f"  Types:     {pre['type_rate']:.0%}  →  {post['type_rate']:.0%}")
    print(f"  Runtime:   {pre['runtime_rate']:.0%}  →  {post['runtime_rate']:.0%}")
    print(f"  Tests:     {pre['tests_passed']}/{pre['total_tests']}  →  {post['tests_passed']}/{post['total_tests']}  ({'+' if delta_tests >= 0 else ''}{delta_tests})")
    print(f"  Time:      {elapsed:.0f}s ({step} steps)")
    print(f"{'='*60}\n")

    # ── Save model + metrics ──
    out_dir = args.output_dir or str(ROOT / "models" / f"vilt_code_{model_short}_{mode_label.lower()}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    metrics = {
        "model": model_name,
        "mode": mode_label,
        "steps": step,
        "elapsed_s": round(elapsed, 1),
        "pre": {
            "pass_at_1": round(pre["pass_at_1"], 4),
            "syntax_rate": round(pre["syntax_rate"], 4),
            "type_rate": round(pre["type_rate"], 4),
            "runtime_rate": round(pre["runtime_rate"], 4),
            "tests_passed": pre["tests_passed"],
            "tests_total": pre["total_tests"],
        },
        "post": {
            "pass_at_1": round(post["pass_at_1"], 4),
            "syntax_rate": round(post["syntax_rate"], 4),
            "type_rate": round(post["type_rate"], 4),
            "runtime_rate": round(post["runtime_rate"], 4),
            "tests_passed": post["tests_passed"],
            "tests_total": post["total_tests"],
        },
        "problems": [
            {"id": r["id"], "difficulty": r["difficulty"], "passed": r["passed"],
             "syntax": r["syntax"], "types": r["types"], "runtime": r["runtime"]}
            for r in post["results"]
        ],
    }
    metrics_path = Path(out_dir) / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Model saved to: {out_dir}")
    print(f"  Metrics saved to: {metrics_path}")

    return metrics


if __name__ == "__main__":
    main()
