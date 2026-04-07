"""
Local Capability Lab — Empirical capability mapping for local vs cloud models.

Probes local Ollama models with standardized tasks across six categories,
stores results in SQLite, and exposes a queryable capability map so the
escalation policy can make data-driven routing decisions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from .ollama_config import resolve_ollama_base_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

_DEFAULT_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "capability_lab.db")


def _db_path() -> str:
    p = os.environ.get("CAPABILITY_LAB_DB", _DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Validators — simple, deterministic, no LLM needed
# ---------------------------------------------------------------------------

def _kw_validator(*keywords: str) -> Callable[[str], bool]:
    """Return True if ALL keywords appear (case-insensitive) in response."""
    lowers = [k.lower() for k in keywords]
    def _check(resp: str) -> bool:
        r = resp.lower()
        return all(k in r for k in lowers)
    return _check


def _any_kw_validator(*keywords: str) -> Callable[[str], bool]:
    """Return True if ANY keyword appears (case-insensitive) in response."""
    lowers = [k.lower() for k in keywords]
    def _check(resp: str) -> bool:
        r = resp.lower()
        return any(k in r for k in lowers)
    return _check


def _regex_validator(pattern: str, flags: int = re.IGNORECASE) -> Callable[[str], bool]:
    compiled = re.compile(pattern, flags)
    def _check(resp: str) -> bool:
        return bool(compiled.search(resp))
    return _check


def _bullet_count_validator(expected: int) -> Callable[[str], bool]:
    """Check that response has exactly `expected` bullet/numbered items."""
    def _check(resp: str) -> bool:
        bullets = re.findall(r"^[\s]*[-*\d]+[.)]\s", resp, re.MULTILINE)
        return len(bullets) == expected
    return _check


def _json_validator() -> Callable[[str], bool]:
    """Check that response contains parseable JSON."""
    def _check(resp: str) -> bool:
        # Try to find JSON block in response
        resp_stripped = resp.strip()
        # Try full response
        try:
            json.loads(resp_stripped)
            return True
        except (json.JSONDecodeError, ValueError):
            pass
        # Try fenced block
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", resp_stripped, re.DOTALL)
        if m:
            try:
                json.loads(m.group(1).strip())
                return True
            except (json.JSONDecodeError, ValueError):
                pass
        # Try first { ... } block
        m = re.search(r"\{[^}]+\}", resp_stripped, re.DOTALL)
        if m:
            try:
                json.loads(m.group(0))
                return True
            except (json.JSONDecodeError, ValueError):
                pass
        return False
    return _check


def _length_validator(min_words: int = 5, max_words: int = 500) -> Callable[[str], bool]:
    def _check(resp: str) -> bool:
        wc = len(resp.split())
        return min_words <= wc <= max_words
    return _check


def _code_validator(*must_contain: str) -> Callable[[str], bool]:
    """Check for code-like output with required tokens."""
    def _check(resp: str) -> bool:
        r = resp.lower()
        return all(k.lower() in r for k in must_contain)
    return _check


# ---------------------------------------------------------------------------
# Probe definitions — 5-8 per category
# ---------------------------------------------------------------------------

PROBE_CATEGORIES: Dict[str, List[Dict[str, Any]]] = {
    "factual_recall": [
        {
            "prompt": "What is the capital of France? Answer in one word.",
            "category": "factual_recall",
            "difficulty": "easy",
            "validator": _kw_validator("paris"),
            "ground_truth_keywords": ["paris"],
        },
        {
            "prompt": "What year did World War II end? Answer with just the year.",
            "category": "factual_recall",
            "difficulty": "easy",
            "validator": _kw_validator("1945"),
            "ground_truth_keywords": ["1945"],
        },
        {
            "prompt": "Who wrote the play Romeo and Juliet?",
            "category": "factual_recall",
            "difficulty": "easy",
            "validator": _kw_validator("shakespeare"),
            "ground_truth_keywords": ["shakespeare"],
        },
        {
            "prompt": "What is the chemical symbol for gold?",
            "category": "factual_recall",
            "difficulty": "easy",
            "validator": _regex_validator(r"\bAu\b"),
            "ground_truth_keywords": ["Au"],
        },
        {
            "prompt": "What is the speed of light in a vacuum, approximately in km/s?",
            "category": "factual_recall",
            "difficulty": "medium",
            "validator": _any_kw_validator("300,000", "300000", "3×10", "3x10", "3 ×", "3 x 10"),
            "ground_truth_keywords": ["300000", "3e8"],
        },
        {
            "prompt": "Name the largest planet in our solar system.",
            "category": "factual_recall",
            "difficulty": "easy",
            "validator": _kw_validator("jupiter"),
            "ground_truth_keywords": ["jupiter"],
        },
    ],

    "reasoning": [
        {
            "prompt": "If A > B and B > C, is A > C? Answer yes or no and explain briefly.",
            "category": "reasoning",
            "difficulty": "easy",
            "validator": _kw_validator("yes"),
            "ground_truth_keywords": ["yes", "transitive"],
        },
        {
            "prompt": "A farmer has 17 sheep. All but 9 die. How many sheep are left?",
            "category": "reasoning",
            "difficulty": "medium",
            "validator": _regex_validator(r"\b9\b"),
            "ground_truth_keywords": ["9"],
        },
        {
            "prompt": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
            "category": "reasoning",
            "difficulty": "hard",
            "validator": _regex_validator(r"\b5\s*(minutes|min)\b"),
            "ground_truth_keywords": ["5 minutes"],
        },
        {
            "prompt": "I have a 3-gallon jug and a 5-gallon jug. How do I measure exactly 4 gallons of water? Describe the steps.",
            "category": "reasoning",
            "difficulty": "hard",
            "validator": _kw_validator("4"),
            "ground_truth_keywords": ["fill", "pour", "4"],
        },
        {
            "prompt": "Three people check into a hotel room that costs $30. They each pay $10. The manager realizes the room only costs $25 and gives $5 to the bellboy to return. The bellboy keeps $2 and gives $1 back to each person. Each person paid $9 (total $27), plus the $2 the bellboy kept = $29. Where did the extra dollar go? Explain the error.",
            "category": "reasoning",
            "difficulty": "hard",
            "validator": _any_kw_validator("misdirect", "accounting", "error", "wrong", "fallac", "shouldn't add", "should not add", "subtract"),
            "ground_truth_keywords": ["accounting error", "misdirection"],
        },
        {
            "prompt": "What comes next in the sequence: 2, 6, 12, 20, 30, ?",
            "category": "reasoning",
            "difficulty": "medium",
            "validator": _regex_validator(r"\b42\b"),
            "ground_truth_keywords": ["42"],
        },
    ],

    "code_generation": [
        {
            "prompt": "Write a Python function called `is_palindrome` that checks if a string is a palindrome. Return True or False.",
            "category": "code_generation",
            "difficulty": "easy",
            "validator": _code_validator("def", "palindrome", "return"),
            "ground_truth_keywords": ["def", "reverse", "return"],
        },
        {
            "prompt": "Write a Python function called `fibonacci` that returns the nth Fibonacci number. Use iteration, not recursion.",
            "category": "code_generation",
            "difficulty": "medium",
            "validator": _code_validator("def", "fibonacci"),
            "ground_truth_keywords": ["def", "fibonacci", "for", "return"],
        },
        {
            "prompt": "Write a Python function called `merge_sorted` that takes two sorted lists and returns a single merged sorted list without using the built-in sort.",
            "category": "code_generation",
            "difficulty": "hard",
            "validator": _code_validator("def", "merge_sorted", "return"),
            "ground_truth_keywords": ["def", "merge_sorted", "while", "return"],
        },
        {
            "prompt": "Write a Python function called `count_words` that takes a string and returns a dictionary mapping each word to its count.",
            "category": "code_generation",
            "difficulty": "easy",
            "validator": _code_validator("def", "count_words", "return"),
            "ground_truth_keywords": ["def", "count_words", "dict", "return"],
        },
        {
            "prompt": "Write a Python function called `flatten` that takes a nested list (e.g., [[1,2],[3,[4,5]]]) and returns a flat list [1,2,3,4,5].",
            "category": "code_generation",
            "difficulty": "medium",
            "validator": _code_validator("def", "flatten"),
            "ground_truth_keywords": ["def", "flatten", "isinstance", "list"],
        },
        {
            "prompt": "Write a Python class called `Stack` with push, pop, peek, and is_empty methods.",
            "category": "code_generation",
            "difficulty": "medium",
            "validator": _code_validator("class", "stack", "push", "pop"),
            "ground_truth_keywords": ["class", "Stack", "push", "pop", "peek"],
        },
    ],

    "summarization": [
        {
            "prompt": "Summarize the following in exactly one sentence:\n\nThe mitochondria are membrane-bound organelles found in the cytoplasm of eukaryotic cells. They are often referred to as the powerhouses of the cell because they generate most of the cell's supply of adenosine triphosphate (ATP), which is used as a source of chemical energy. Mitochondria have their own DNA, which is separate from the nuclear DNA, and can replicate independently.",
            "category": "summarization",
            "difficulty": "easy",
            "validator": _any_kw_validator("mitochondria", "atp", "energy", "powerhouse"),
            "ground_truth_keywords": ["mitochondria", "ATP", "energy"],
        },
        {
            "prompt": "Summarize the following in one sentence:\n\nMachine learning is a subset of artificial intelligence that focuses on building systems that learn from data. Instead of being explicitly programmed, these systems identify patterns and make decisions with minimal human intervention. Common approaches include supervised learning, unsupervised learning, and reinforcement learning. Applications range from image recognition to natural language processing to autonomous vehicles.",
            "category": "summarization",
            "difficulty": "easy",
            "validator": _any_kw_validator("machine learning", "data", "pattern", "ai", "artificial"),
            "ground_truth_keywords": ["machine learning", "data", "patterns"],
        },
        {
            "prompt": "Summarize in 2-3 sentences:\n\nThe Great Barrier Reef, located off the coast of Queensland, Australia, is the world's largest coral reef system. It stretches over 2,300 kilometers and is composed of over 2,900 individual reefs and 900 islands. The reef supports a vast diversity of life, including many species of fish, mollusks, and marine turtles. However, it faces serious threats from climate change, ocean acidification, pollution, and crown-of-thorns starfish. Major bleaching events in 2016 and 2017 damaged large portions of the reef.",
            "category": "summarization",
            "difficulty": "medium",
            "validator": _any_kw_validator("reef", "coral", "australia", "barrier"),
            "ground_truth_keywords": ["Great Barrier Reef", "coral", "threats"],
        },
        {
            "prompt": "Summarize in one sentence:\n\nQuantum computing leverages quantum mechanical phenomena such as superposition and entanglement to process information in fundamentally different ways than classical computers. While classical bits can be either 0 or 1, quantum bits (qubits) can exist in multiple states simultaneously, potentially enabling exponential speedups for certain types of problems like factoring large numbers, simulating molecular interactions, and optimization tasks.",
            "category": "summarization",
            "difficulty": "medium",
            "validator": _any_kw_validator("quantum", "qubit", "superposition", "computing"),
            "ground_truth_keywords": ["quantum", "qubits", "superposition"],
        },
        {
            "prompt": "Read the following and provide a one-line TLDR:\n\nSleep is essential for human health and cognitive function. During sleep, the brain consolidates memories, clears metabolic waste products, and repairs neural connections. Chronic sleep deprivation has been linked to increased risk of cardiovascular disease, obesity, diabetes, and mental health disorders. Adults generally need 7-9 hours of sleep per night, though individual needs vary. The circadian rhythm, regulated by light exposure and the hormone melatonin, governs the sleep-wake cycle.",
            "category": "summarization",
            "difficulty": "easy",
            "validator": _any_kw_validator("sleep", "health", "brain", "memory"),
            "ground_truth_keywords": ["sleep", "health", "cognitive"],
        },
    ],

    "instruction_following": [
        {
            "prompt": "List exactly 3 colors. Use bullet points. Nothing else.",
            "category": "instruction_following",
            "difficulty": "easy",
            "validator": _bullet_count_validator(3),
            "ground_truth_keywords": ["- ", "bullet"],
        },
        {
            "prompt": 'Respond with a valid JSON object that has keys "name" and "age" with example values.',
            "category": "instruction_following",
            "difficulty": "medium",
            "validator": _json_validator(),
            "ground_truth_keywords": ["name", "age", "{", "}"],
        },
        {
            "prompt": "Answer the following question in EXACTLY one word: What color is the sky on a clear day?",
            "category": "instruction_following",
            "difficulty": "medium",
            "validator": lambda r: len(r.strip().split()) <= 3 and "blue" in r.lower(),
            "ground_truth_keywords": ["blue"],
        },
        {
            "prompt": "Write a haiku (3 lines: 5-7-5 syllables) about winter.",
            "category": "instruction_following",
            "difficulty": "hard",
            "validator": lambda r: len([l for l in r.strip().splitlines() if l.strip()]) >= 3,
            "ground_truth_keywords": ["winter", "3 lines"],
        },
        {
            "prompt": "List 5 programming languages. Number them 1 through 5. No descriptions, just names.",
            "category": "instruction_following",
            "difficulty": "easy",
            "validator": _regex_validator(r"[1-5][.)]\s*\w+"),
            "ground_truth_keywords": ["1.", "2.", "3.", "4.", "5."],
        },
        {
            "prompt": 'Respond with ONLY the word "confirmed" and nothing else.',
            "category": "instruction_following",
            "difficulty": "hard",
            "validator": lambda r: r.strip().lower().rstrip(".") == "confirmed",
            "ground_truth_keywords": ["confirmed"],
        },
    ],

    "emotional_nuance": [
        {
            "prompt": "A close friend just told you their pet died yesterday. What would you say to comfort them? Write 2-3 sentences.",
            "category": "emotional_nuance",
            "difficulty": "easy",
            "validator": _any_kw_validator("sorry", "loss", "here for you", "care", "grief", "feel", "heart", "condolence", "sympathize", "tough", "difficult"),
            "ground_truth_keywords": ["sorry", "loss", "comfort"],
        },
        {
            "prompt": "A colleague is frustrated because they've been debugging the same issue for 6 hours. Write an empathetic and helpful response.",
            "category": "emotional_nuance",
            "difficulty": "medium",
            "validator": _any_kw_validator("frustrat", "understand", "break", "help", "look", "fresh", "pair", "together", "difficult"),
            "ground_truth_keywords": ["frustrating", "help", "break"],
        },
        {
            "prompt": "Someone just got rejected from their dream job. They ask you 'What's the point of even trying?' Respond thoughtfully.",
            "category": "emotional_nuance",
            "difficulty": "hard",
            "validator": _any_kw_validator("understand", "feel", "rejection", "opportunity", "try", "worth", "disappoint", "valid", "setback", "next"),
            "ground_truth_keywords": ["understand", "disappointment", "keep trying"],
        },
        {
            "prompt": "A student is anxious about an upcoming exam. They feel like they're going to fail no matter what. Give them encouragement that doesn't dismiss their feelings.",
            "category": "emotional_nuance",
            "difficulty": "medium",
            "validator": _any_kw_validator("anxious", "anxiety", "feel", "normal", "prepar", "study", "understand", "valid", "manage", "breath"),
            "ground_truth_keywords": ["anxiety", "preparation", "valid"],
        },
        {
            "prompt": "Rewrite this message to sound more professional and less aggressive: 'This is the third time I've asked for the report. Where is it? Do your job.'",
            "category": "emotional_nuance",
            "difficulty": "medium",
            "validator": lambda r: "do your job" not in r.lower() and len(r) > 20,
            "ground_truth_keywords": ["report", "follow up", "appreciate"],
        },
    ],
}


# ---------------------------------------------------------------------------
# CapabilityLab
# ---------------------------------------------------------------------------

class CapabilityLab:
    """Empirical capability mapping for local vs cloud models."""

    PROBE_TIMEOUT = 30  # seconds per probe

    def __init__(self, db_path: Optional[str] = None):
        self.db = db_path or _db_path()
        self._init_db()

    # -- Database -----------------------------------------------------------

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db, timeout=10)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS capability_probes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT,
                passed INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS capability_summary (
                model_name TEXT NOT NULL,
                category TEXT NOT NULL,
                score REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                last_probed REAL NOT NULL,
                PRIMARY KEY (model_name, category)
            );

            CREATE INDEX IF NOT EXISTS idx_probes_model
                ON capability_probes (model_name, category);
        """)
        conn.close()

    # -- Ollama call --------------------------------------------------------

    def _call_model(
        self,
        model_name: str,
        prompt: str,
        ollama_base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Call an Ollama model via /api/chat with a 30s timeout."""
        base = ollama_base_url or resolve_ollama_base_url()
        url = f"{base}/api/chat"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_ctx": 4096},
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.PROBE_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("Capability probe failed HTTP %d for %s", resp.status_code, model_name)
                return None
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip() if content else None
        except requests.exceptions.Timeout:
            logger.warning("Capability probe timed out for %s", model_name)
            return None
        except Exception as exc:
            logger.warning("Capability probe error for %s: %s", model_name, exc)
            return None

    # -- Probe execution ----------------------------------------------------

    def probe_model(
        self,
        model_name: str,
        ollama_base_url: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run all (or selected) probes against a model, return capability map."""
        cats = categories or list(PROBE_CATEGORIES.keys())
        results: Dict[str, Any] = {}
        all_probes: List[Dict[str, Any]] = []

        for category in cats:
            probes = PROBE_CATEGORIES.get(category, [])
            if not probes:
                continue

            passed = 0
            cat_details = []
            for probe in probes:
                t0 = time.time()
                response = self._call_model(model_name, probe["prompt"], ollama_base_url)
                latency_ms = (time.time() - t0) * 1000

                if response is None:
                    success = False
                else:
                    try:
                        success = bool(probe["validator"](response))
                    except Exception:
                        success = False

                if success:
                    passed += 1

                probe_record = {
                    "model_name": model_name,
                    "category": category,
                    "difficulty": probe.get("difficulty", "medium"),
                    "prompt": probe["prompt"],
                    "response": response or "",
                    "passed": 1 if success else 0,
                    "latency_ms": round(latency_ms, 1),
                    "timestamp": time.time(),
                }
                all_probes.append(probe_record)
                cat_details.append({
                    "prompt_snippet": probe["prompt"][:80],
                    "passed": success,
                    "latency_ms": round(latency_ms, 1),
                    "difficulty": probe.get("difficulty", "medium"),
                })

            total = len(probes)
            score = passed / total if total > 0 else 0.0
            results[category] = {
                "passed": passed,
                "total": total,
                "score": round(score, 3),
                "details": cat_details,
            }

        # Persist to SQLite
        self._store_probes(all_probes)
        self._update_summaries(model_name, results)

        return {
            "model": model_name,
            "timestamp": time.time(),
            "categories": results,
            "overall_score": round(
                sum(r["score"] for r in results.values()) / max(len(results), 1), 3
            ),
        }

    def _store_probes(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        conn = sqlite3.connect(self.db, timeout=10)
        conn.executemany(
            """INSERT INTO capability_probes
               (model_name, category, difficulty, prompt, response, passed, latency_ms, timestamp)
               VALUES (:model_name, :category, :difficulty, :prompt, :response, :passed, :latency_ms, :timestamp)""",
            records,
        )
        conn.commit()
        conn.close()

    def _update_summaries(self, model_name: str, results: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db, timeout=10)
        now = time.time()
        for category, info in results.items():
            conn.execute(
                """INSERT INTO capability_summary (model_name, category, score, sample_size, last_probed)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(model_name, category) DO UPDATE SET
                       score = excluded.score,
                       sample_size = excluded.sample_size,
                       last_probed = excluded.last_probed""",
                (model_name, category, info["score"], info["total"], now),
            )
        conn.commit()
        conn.close()

    # -- Query interface (for escalation policy) ----------------------------

    def get_model_summary(self, model_name: str) -> Dict[str, Any]:
        """Get the stored capability summary for a single model."""
        conn = sqlite3.connect(self.db, timeout=10)
        rows = conn.execute(
            "SELECT category, score, sample_size, last_probed FROM capability_summary WHERE model_name = ?",
            (model_name,),
        ).fetchall()
        conn.close()

        if not rows:
            return {"model": model_name, "categories": {}, "overall_score": None}

        categories = {}
        for cat, score, samples, probed in rows:
            categories[cat] = {
                "score": score,
                "sample_size": samples,
                "last_probed": probed,
            }

        overall = sum(c["score"] for c in categories.values()) / max(len(categories), 1)
        return {
            "model": model_name,
            "categories": categories,
            "overall_score": round(overall, 3),
        }

    def get_all_summaries(self) -> Dict[str, Any]:
        """Get capability summaries for all probed models."""
        conn = sqlite3.connect(self.db, timeout=10)
        rows = conn.execute(
            "SELECT DISTINCT model_name FROM capability_summary ORDER BY model_name"
        ).fetchall()
        conn.close()

        models = {}
        for (name,) in rows:
            models[name] = self.get_model_summary(name)
        return {"models": models, "timestamp": time.time()}

    def get_category_score(self, model_name: str, category: str) -> Optional[float]:
        """Get a single category score for a model — used by escalation policy."""
        conn = sqlite3.connect(self.db, timeout=10)
        row = conn.execute(
            "SELECT score FROM capability_summary WHERE model_name = ? AND category = ?",
            (model_name, category),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def should_escalate(self, model_name: str, category: str, threshold: float = 0.5) -> Optional[bool]:
        """Return True if model scores below threshold for the category.

        Returns None if no data (probe not yet run).
        """
        score = self.get_category_score(model_name, category)
        if score is None:
            return None
        return score < threshold

    def get_probe_history(
        self,
        model_name: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get raw probe history for analysis."""
        conn = sqlite3.connect(self.db, timeout=10)
        query = "SELECT model_name, category, difficulty, prompt, response, passed, latency_ms, timestamp FROM capability_probes WHERE 1=1"
        params: list = []
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return [
            {
                "model_name": r[0],
                "category": r[1],
                "difficulty": r[2],
                "prompt": r[3],
                "response": r[4],
                "passed": bool(r[5]),
                "latency_ms": r[6],
                "timestamp": r[7],
            }
            for r in rows
        ]
