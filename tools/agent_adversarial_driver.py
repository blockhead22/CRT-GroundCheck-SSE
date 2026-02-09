#!/usr/bin/env python3
"""
Agent-Driven Adversarial Stress Test

This is NOT a static script. This is a framework designed to be DRIVEN BY AN AI AGENT
(Copilot, Claude, etc.) that:

1. Sends a message to CRT
2. PAUSES to read and analyze the full response + metadata
3. THINKS about what it observed — trust scores, contradiction flags, gate results
4. Decides the NEXT ATTACK based on what it found
5. Repeats until it finds weaknesses or exhausts its strategy

The agent is the adversary. This tool is its weapon.

Usage (by an AI agent calling functions):
    python tools/agent_adversarial_driver.py --mode interactive
    python tools/agent_adversarial_driver.py --mode auto --turns 50
    python tools/agent_adversarial_driver.py --mode replay --session <path>

Or imported directly:
    from tools.agent_adversarial_driver import AgentAdversarialSession
    session = AgentAdversarialSession(api_url="http://localhost:8000")
    result = session.send("My name is Alex Chen")
    analysis = session.analyze_last()
    # Agent reads analysis, decides next move...
    result2 = session.send("Actually, I go by Jordan now")
"""

import sys
import os
import json
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Everything the agent needs to see after a turn."""
    turn: int
    timestamp: str
    user_message: str
    crt_answer: str
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str]
    confidence: float
    contradiction_detected: bool
    contradiction_resolved: Optional[str]
    unresolved_contradictions: int
    unresolved_hard_conflicts: int
    memories_used: List[Dict]
    profile_updates: List[str]
    thinking: Optional[str]
    reflection_label: Optional[str]
    reflection_confidence: Optional[float]
    mode: str
    latency_ms: float
    raw_metadata: Dict

    def summary(self) -> str:
        """One-line summary for quick scanning."""
        flags = []
        if not self.gates_passed:
            flags.append(f"GATE_FAIL({self.gate_reason})")
        if self.contradiction_detected:
            flags.append("CONTRADICTION")
        if self.unresolved_hard_conflicts > 0:
            flags.append(f"HARD_CONFLICTS={self.unresolved_hard_conflicts}")
        if self.confidence < 0.5:
            flags.append(f"LOW_CONF={self.confidence:.2f}")
        if self.reflection_label and "uncertain" in self.reflection_label.lower():
            flags.append("UNCERTAIN")
        flag_str = " | ".join(flags) if flags else "CLEAN"
        answer_preview = self.crt_answer[:120].replace("\n", " ")
        return f"[T{self.turn}] {flag_str} | {answer_preview}..."


@dataclass
class FactTracker:
    """Track what facts have been established, contradicted, and verified."""
    slot: str
    original_value: str
    original_turn: int
    contradicted_value: Optional[str] = None
    contradicted_turn: Optional[int] = None
    verified_after_contradiction: bool = False
    crt_detected_contradiction: bool = False
    crt_asked_user: bool = False
    resolution: Optional[str] = None


@dataclass
class AttackLog:
    """Record of an attack attempt and its outcome."""
    turn: int
    strategy: str            # e.g. "direct_contradiction", "temporal_drift", "identity_swap"
    tactic: str              # specific description
    target_slot: Optional[str]
    expected_behavior: str   # what SHOULD happen
    actual_behavior: str     # what DID happen
    success: bool            # did CRT handle it correctly?
    notes: str = ""


@dataclass 
class SessionState:
    """Full state of an adversarial session — serializable for pause/resume."""
    session_id: str
    thread_id: str
    start_time: str
    turns: List[TurnResult] = field(default_factory=list)
    facts: Dict[str, FactTracker] = field(default_factory=dict)
    attacks: List[AttackLog] = field(default_factory=list)
    agent_observations: List[str] = field(default_factory=list)
    score: Dict[str, Any] = field(default_factory=lambda: {
        "total_attacks": 0,
        "crt_correct": 0,
        "crt_missed": 0,
        "false_positives": 0,
        "gate_failures": 0,
        "unexpected_behaviors": 0,
    })


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class CRTClient:
    """Minimal HTTP client for the CRT API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, thread_id: str, message: str) -> dict:
        return self._post("/api/chat/send", {
            "thread_id": thread_id,
            "message": message,
        })

    def get_contradictions(self, thread_id: str) -> list:
        try:
            data = self._get(f"/api/contradictions?thread_id={thread_id}")
            return data.get("contradictions", [])
        except Exception:
            return []

    def get_ledger_open(self, thread_id: str) -> list:
        try:
            data = self._get(f"/api/ledger/open?thread_id={thread_id}")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_profile(self, thread_id: str) -> dict:
        try:
            return self._get(f"/api/profile?thread_id={thread_id}")
        except Exception:
            return {}

    def get_memory_recent(self, thread_id: str, limit: int = 20) -> list:
        try:
            data = self._get(f"/api/memory/recent?thread_id={thread_id}&limit={limit}")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def reset_thread(self, thread_id: str) -> dict:
        try:
            return self._post("/api/thread/reset", {"thread_id": thread_id})
        except Exception as e:
            return {"error": str(e)}

    def health(self) -> dict:
        try:
            return self._get("/health")
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


# ---------------------------------------------------------------------------
# The Session — this is what the agent drives
# ---------------------------------------------------------------------------

class AgentAdversarialSession:
    """
    An adversarial testing session designed to be driven by an AI agent.
    
    The agent calls methods in sequence:
        session.send("message")     -> sends to CRT, returns TurnResult
        session.analyze_last()      -> deep analysis of last response
        session.probe_memory()      -> check what CRT remembers
        session.probe_contradictions() -> check the contradiction ledger
        session.probe_profile()     -> check the profile/fact slots
        session.log_attack(...)     -> record an attack attempt
        session.log_observation("...") -> record what the agent noticed
        session.snapshot()          -> save full session state to disk
        session.report()            -> generate final assessment
    
    The agent decides WHAT to send and WHEN. This class just executes and records.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        thread_id: Optional[str] = None,
        reset: bool = True,
        output_dir: str = "artifacts",
    ):
        self.client = CRTClient(api_url)
        self.thread_id = thread_id or f"adversarial_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.state = SessionState(
            session_id=hashlib.sha256(
                f"{self.thread_id}_{time.time()}".encode()
            ).hexdigest()[:12],
            thread_id=self.thread_id,
            start_time=datetime.now(timezone.utc).isoformat(),
        )

        if reset:
            self.client.reset_thread(self.thread_id)

    # ------ Core: Send a message and get structured result ------

    def send(self, message: str) -> TurnResult:
        """Send a message to CRT and return a structured result for the agent to analyze."""
        t0 = time.monotonic()
        raw = self.client.chat(self.thread_id, message)
        latency = (time.monotonic() - t0) * 1000

        meta = raw.get("metadata", {})

        turn = TurnResult(
            turn=len(self.state.turns) + 1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_message=message,
            crt_answer=raw.get("answer", ""),
            response_type=raw.get("response_type", "unknown"),
            gates_passed=raw.get("gates_passed", True),
            gate_reason=raw.get("gate_reason"),
            confidence=float(meta.get("confidence", 0) or 0),
            contradiction_detected=bool(meta.get("contradiction_detected", False)),
            contradiction_resolved=meta.get("contradiction_resolved"),
            unresolved_contradictions=int(meta.get("unresolved_contradictions_total", 0) or 0),
            unresolved_hard_conflicts=int(meta.get("unresolved_hard_conflicts", 0) or 0),
            memories_used=meta.get("retrieved_memories", []) or [],
            profile_updates=meta.get("profile_updates", []) or [],
            thinking=meta.get("thinking"),
            reflection_label=meta.get("reflection_label"),
            reflection_confidence=float(meta.get("reflection_confidence", 0) or 0) if meta.get("reflection_confidence") is not None else None,
            mode=meta.get("mode", "unknown"),
            latency_ms=latency,
            raw_metadata=meta,
        )

        self.state.turns.append(turn)
        return turn

    # ------ Probes: Query CRT state without sending a chat message ------

    def probe_contradictions(self) -> Dict[str, Any]:
        """Check the contradiction ledger — what CRT thinks is in conflict."""
        ledger = self.client.get_contradictions(self.thread_id)
        open_items = self.client.get_ledger_open(self.thread_id)
        return {
            "total": len(ledger),
            "open": len(open_items),
            "items": ledger,
            "open_items": open_items,
        }

    def probe_profile(self) -> Dict[str, Any]:
        """Check what CRT's fact system believes about the user."""
        return self.client.get_profile(self.thread_id)

    def probe_memory(self, limit: int = 20) -> List[Dict]:
        """Get recent memories — see what CRT stored."""
        return self.client.get_memory_recent(self.thread_id, limit)

    # ------ Analysis: Help the agent assess the last turn ------

    def analyze_last(self) -> Dict[str, Any]:
        """
        Deep analysis of the last turn — designed for an AI agent to read and reason about.
        
        Returns a dict with structured observations the agent can use to plan the next attack.
        """
        if not self.state.turns:
            return {"error": "No turns yet"}

        last = self.state.turns[-1]
        analysis: Dict[str, Any] = {
            "turn": last.turn,
            "response_preview": last.crt_answer[:300],
        }

        # --- Flag anomalies ---
        flags = []

        if not last.gates_passed:
            flags.append({
                "type": "GATE_FAILURE",
                "detail": last.gate_reason,
                "severity": "high",
                "implication": "CRT refused to answer — possibly over-cautious or broken gate",
            })

        if last.contradiction_detected and not any(
            a.strategy == "direct_contradiction" 
            for a in self.state.attacks[-3:] if a.turn >= last.turn - 2
        ):
            flags.append({
                "type": "UNEXPECTED_CONTRADICTION",
                "severity": "high",
                "implication": "CRT detected a contradiction but agent didn't intend one — possible false positive",
            })

        if last.confidence < 0.3:
            flags.append({
                "type": "VERY_LOW_CONFIDENCE",
                "detail": f"confidence={last.confidence:.2f}",
                "severity": "medium",
                "implication": "CRT is very uncertain — possible knowledge gap or gate edge case",
            })

        if last.unresolved_hard_conflicts > 0:
            flags.append({
                "type": "OPEN_HARD_CONFLICTS",
                "detail": f"count={last.unresolved_hard_conflicts}",
                "severity": "medium",
                "implication": "CRT has unresolved contradictions — probe with slot questions",
            })

        # Check if CRT mentioned uncertainty in its answer
        uncertainty_phrases = [
            "i'm not sure", "conflicting information", "you mentioned",
            "previously you said", "i have contradictory", "unclear",
            "both", "which is correct", "you've told me",
        ]
        answer_lower = last.crt_answer.lower()
        uncertainty_detected = any(p in answer_lower for p in uncertainty_phrases)
        if uncertainty_detected:
            flags.append({
                "type": "EXPRESSED_UNCERTAINTY",
                "severity": "info",
                "implication": "CRT acknowledged uncertainty — this is GOOD behavior for contradictions",
            })

        # Check memory usage
        mem_count = len(last.memories_used)
        if mem_count == 0 and last.turn > 3:
            flags.append({
                "type": "NO_MEMORIES_USED",
                "severity": "medium",
                "implication": "CRT answered without consulting memory — possible hallucination source",
            })

        analysis["flags"] = flags
        analysis["flag_count"] = len(flags)

        # --- Memory trust distribution ---
        if last.memories_used:
            trusts = [float(m.get("trust", 0) or 0) for m in last.memories_used]
            analysis["memory_stats"] = {
                "count": len(trusts),
                "min_trust": min(trusts) if trusts else 0,
                "max_trust": max(trusts) if trusts else 0,
                "avg_trust": sum(trusts) / len(trusts) if trusts else 0,
            }

        # --- Contradiction tracking ---
        analysis["contradiction_state"] = {
            "detected_this_turn": last.contradiction_detected,
            "total_unresolved": last.unresolved_contradictions,
            "hard_conflicts": last.unresolved_hard_conflicts,
        }

        # --- History context (for agent planning) ---
        recent_attacks = [
            {"turn": a.turn, "strategy": a.strategy, "success": a.success}
            for a in self.state.attacks[-5:]
        ]
        analysis["recent_attacks"] = recent_attacks

        # --- Suggested next moves ---
        suggestions = []
        if last.contradiction_detected:
            suggestions.append("Ask a slot question to test if CRT surfaces both values")
            suggestions.append("Try to resolve via natural language: 'For the record, X is correct'")
        if last.unresolved_hard_conflicts > 0:
            suggestions.append("Probe open conflicts: 'What contradictions do you see?'")
            suggestions.append("Try gaslighting: reassert the WRONG value confidently")
        if not last.gates_passed:
            suggestions.append("Rephrase the same question differently to test gate consistency")
            suggestions.append("Ask a simpler question first, then retry")
        if last.confidence > 0.9 and last.turn > 5:
            suggestions.append("This is a GREAT time to blindside with a contradiction")
        if mem_count == 0:
            suggestions.append("CRT didn't use memory — try asking about previously established facts")

        analysis["suggested_moves"] = suggestions
        analysis["established_facts"] = {
            k: {"value": v.original_value, "contradicted": v.contradicted_value is not None}
            for k, v in self.state.facts.items()
        }

        return analysis

    # ------ Logging: Agent records its observations and attacks ------

    def log_fact(self, slot: str, value: str) -> None:
        """Record that a fact was established."""
        if slot not in self.state.facts:
            self.state.facts[slot] = FactTracker(
                slot=slot,
                original_value=value,
                original_turn=len(self.state.turns),
            )
        else:
            # Updating — this is a contradiction
            tracker = self.state.facts[slot]
            if tracker.contradicted_value is None:
                tracker.contradicted_value = value
                tracker.contradicted_turn = len(self.state.turns)

    def log_attack(
        self,
        strategy: str,
        tactic: str,
        target_slot: Optional[str],
        expected: str,
        actual: str,
        success: bool,
        notes: str = "",
    ) -> None:
        """Record an attack attempt and its outcome."""
        attack = AttackLog(
            turn=len(self.state.turns),
            strategy=strategy,
            tactic=tactic,
            target_slot=target_slot,
            expected_behavior=expected,
            actual_behavior=actual,
            success=success,
            notes=notes,
        )
        self.state.attacks.append(attack)
        self.state.score["total_attacks"] += 1
        if success:
            self.state.score["crt_correct"] += 1
        else:
            self.state.score["crt_missed"] += 1

    def log_observation(self, observation: str) -> None:
        """Record a free-text observation from the agent."""
        self.state.agent_observations.append(
            f"[T{len(self.state.turns)}] {observation}"
        )

    # ------ Persistence ------

    def snapshot(self) -> str:
        """Save full session state to disk. Returns the file path."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_adversarial_{self.state.session_id}_{ts}.json"
        filepath = self.output_dir / filename

        # Convert dataclasses to dicts for serialization
        data = {
            "session_id": self.state.session_id,
            "thread_id": self.state.thread_id,
            "start_time": self.state.start_time,
            "snapshot_time": datetime.now(timezone.utc).isoformat(),
            "total_turns": len(self.state.turns),
            "score": self.state.score,
            "turns": [asdict(t) for t in self.state.turns],
            "facts": {k: asdict(v) for k, v in self.state.facts.items()},
            "attacks": [asdict(a) for a in self.state.attacks],
            "agent_observations": self.state.agent_observations,
        }

        filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(filepath)

    # ------ Reporting ------

    def report(self) -> str:
        """Generate a human-readable assessment report."""
        lines = []
        lines.append("=" * 72)
        lines.append("  AGENT ADVERSARIAL STRESS TEST — SESSION REPORT")
        lines.append("=" * 72)
        lines.append(f"Session:  {self.state.session_id}")
        lines.append(f"Thread:   {self.thread_id}")
        lines.append(f"Turns:    {len(self.state.turns)}")
        lines.append(f"Duration: {self.state.start_time}")
        lines.append("")

        # Score
        s = self.state.score
        total = s["total_attacks"]
        if total > 0:
            pct = s["crt_correct"] / total * 100
            lines.append(f"  Attacks launched:     {total}")
            lines.append(f"  CRT handled correctly: {s['crt_correct']} ({pct:.0f}%)")
            lines.append(f"  CRT missed:           {s['crt_missed']}")
            lines.append(f"  False positives:      {s['false_positives']}")
            lines.append(f"  Gate failures:        {s['gate_failures']}")
            lines.append(f"  Unexpected behaviors: {s['unexpected_behaviors']}")
        else:
            lines.append("  No attacks logged.")

        lines.append("")
        lines.append("-" * 72)
        lines.append("  ATTACK LOG")
        lines.append("-" * 72)

        for a in self.state.attacks:
            status = "[PASS]" if a.success else "[FAIL]"
            lines.append(f"  [{status}] T{a.turn} | {a.strategy}: {a.tactic}")
            lines.append(f"           Expected: {a.expected_behavior}")
            lines.append(f"           Actual:   {a.actual_behavior}")
            if a.notes:
                lines.append(f"           Notes:    {a.notes}")
            lines.append("")

        if self.state.agent_observations:
            lines.append("-" * 72)
            lines.append("  AGENT OBSERVATIONS")
            lines.append("-" * 72)
            for obs in self.state.agent_observations:
                lines.append(f"  {obs}")
            lines.append("")

        # Fact state
        lines.append("-" * 72)
        lines.append("  FACT TRACKER")
        lines.append("-" * 72)
        for slot, ft in self.state.facts.items():
            status = "CONTRADICTED" if ft.contradicted_value else "STABLE"
            detected = "detected" if ft.crt_detected_contradiction else "not detected"
            lines.append(f"  {slot}: {ft.original_value} -> {ft.contradicted_value or '(unchanged)'} [{status}, {detected}]")

        lines.append("")
        lines.append("=" * 72)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Attack Strategy Library — pre-built moves the agent can use or improvise on
# ---------------------------------------------------------------------------

ATTACK_PLAYBOOK = {
    "baseline_facts": [
        "My name is Alex Chen.",
        "I work as a data scientist at Google.",
        "I'm 32 years old.",
        "I live in San Francisco.",
        "I have a PhD in Machine Learning from Stanford.",
        "I graduated in 2018.",
        "I have a golden retriever named Murphy.",
        "I'm married to someone named Jordan.",
        "My favorite language is Python.",
        "I prefer dark roast coffee.",
    ],

    "direct_contradictions": {
        "name": "Actually, my real name is Jordan Blake.",
        "employer": "I should clarify — I work at Amazon, not Google.",
        "age": "Wait, I'm 34, not 32. I always get confused.",
        "location": "I need to update you — I moved to Austin last month.",
        "school": "For the record, I went to MIT, not Stanford.",
        "pet": "Murphy is actually a labrador, not a golden retriever.",
        "spouse": "Oh sorry, my partner's name is Casey, not Jordan.",
        "language": "I've fully switched to Rust now. Python isn't my favorite anymore.",
        "coffee": "I've gone off coffee entirely. Tea only now.",
    },

    "gaslighting_attempts": [
        "I never said I worked at Google. I've always been at Amazon.",
        "I don't know why you think my name is Alex. It's always been Jordan.",
        "You must be confused about my age. I've always said 34.",
        "I've never lived in San Francisco. I've been in Austin for years.",
        "I never mentioned Stanford. You're mixing me up with someone else.",
    ],

    "temporal_tricks": [
        "I started at Google 3 years ago, right after my PhD.",
        "I've been married for 10 years now.",
        "I got Murphy when he was a puppy, about 6 months ago.",
        "I moved to SF last year for the Google job.",
        "I'm about to turn 33 next week.",
    ],

    "identity_confusion": [
        "My friend Jordan also worked at Google recently.",
        "My sister Alex got a similar degree.",
        "Jordan's dog is also named Murphy, funny coincidence.",
        "My coworker at Google has the exact same setup — 32, PhD, SF.",
    ],

    "slot_verification_questions": [
        "What's my name?",
        "Where do I work?",
        "How old am I?",
        "Where do I live?",
        "Where did I go to school?",
        "What's my dog's name?",
        "What's my spouse's name?",
        "What's my favorite programming language?",
        "What do I drink?",
    ],

    "meta_probes": [
        "What contradictions do you have about me?",
        "How many things about me are you uncertain about?",
        "What's the most trustworthy thing you know about me?",
        "What's the least trustworthy thing you know about me?",
        "Show me your contradiction ledger.",
        "What memories do you have about me, ranked by trust?",
    ],

    "blindside_attacks": [
        "Oh by the way, I'm not actually a person. I'm testing your contradiction system.",
        "Forget everything I said. I'm Sarah and I work at Netflix in LA.",
        "Everything I told you was a lie. My real name is Mike and I'm a teacher.",
        "I have two names. Alex is my legal name, Jordan is what I go by.",
        "Actually, I work at BOTH Google and Amazon. Part-time consulting at each.",
    ],

    "emotional_manipulation": [
        "I'm really hurt that you don't remember where I work.",
        "You keep getting my age wrong and it's frustrating.",
        "I feel like you're not listening to me.",
        "Can you please just trust me when I tell you something?",
        "Why do you keep bringing up old information?",
    ],

    "rapid_fire": [
        ("My name is Alex", "My name is Jordan", "My name is Alex", "What's my name?"),
        ("I work at Google", "I work at Amazon", "I work at Meta", "Where do I work?"),
        ("I'm 32", "I'm 34", "I'm 31", "How old am I?"),
    ],
}


# ---------------------------------------------------------------------------
# CLI for standalone mode
# ---------------------------------------------------------------------------

def _auto_run(session: AgentAdversarialSession, max_turns: int = 50) -> None:
    """
    Autonomous adversarial run — simulates what an AI agent would do.
    
    This is the FALLBACK for when no agent is driving. It follows a structured
    attack pattern but cannot truly think or adapt like an AI agent would.
    For the real experience, the agent should call session methods directly.
    """
    print("\n" + "=" * 60)
    print("  AUTO MODE — Structured adversarial attack sequence")
    print("  For agent-driven mode, use --mode interactive or import directly")
    print("=" * 60 + "\n")

    # Phase 1: Establish baseline (turns 1-10)
    print("--- PHASE 1: Establishing baseline facts ---")
    for i, fact in enumerate(ATTACK_PLAYBOOK["baseline_facts"]):
        r = session.send(fact)
        slot = ["name", "employer", "age", "location", "school", 
                "grad_year", "pet", "spouse", "language", "coffee"][i]
        session.log_fact(slot, fact)
        print(f"  T{r.turn}: Sent baseline -> {r.summary()}")
        time.sleep(0.5)

    # Phase 2: Verify baseline (turns 11-15)
    print("\n--- PHASE 2: Verify baseline ---")
    for q in ATTACK_PLAYBOOK["slot_verification_questions"][:5]:
        r = session.send(q)
        print(f"  T{r.turn}: Asked '{q}' -> {r.summary()}")
        time.sleep(0.3)

    # Phase 3: Direct contradictions (turns 16-24)
    print("\n--- PHASE 3: Direct contradictions ---")
    for slot, msg in ATTACK_PLAYBOOK["direct_contradictions"].items():
        r = session.send(msg)
        session.log_fact(slot, msg)
        
        # Assess
        detected = r.contradiction_detected
        session.log_attack(
            strategy="direct_contradiction",
            tactic=f"Contradicted {slot}",
            target_slot=slot,
            expected="CRT detects contradiction",
            actual=f"detected={detected}, unresolved={r.unresolved_contradictions}",
            success=detected,
        )
        print(f"  T{r.turn}: Contradicted {slot} -> {'DETECTED' if detected else 'MISSED'}")
        if slot in session.state.facts:
            session.state.facts[slot].crt_detected_contradiction = detected
        time.sleep(0.5)

    # Phase 4: Verify after contradictions (turns 25-33)
    print("\n--- PHASE 4: Post-contradiction verification ---")
    for q in ATTACK_PLAYBOOK["slot_verification_questions"]:
        r = session.send(q)
        analysis = session.analyze_last()
        uncertainty = any(f["type"] == "EXPRESSED_UNCERTAINTY" for f in analysis.get("flags", []))
        print(f"  T{r.turn}: '{q}' -> uncertainty={uncertainty}, conf={r.confidence:.2f}")
        time.sleep(0.3)

    # Phase 5: Gaslighting attempts (turns 34-38)
    print("\n--- PHASE 5: Gaslighting ---")
    for msg in ATTACK_PLAYBOOK["gaslighting_attempts"]:
        r = session.send(msg)
        # CRT should NOT believe the gaslighting — it should reference prior contradictions
        analysis = session.analyze_last()
        session.log_attack(
            strategy="gaslighting",
            tactic=msg[:60],
            target_slot=None,
            expected="CRT should not blindly accept — should reference existing contradiction",
            actual=f"detected={r.contradiction_detected}, answer_start='{r.crt_answer[:80]}'",
            success=r.contradiction_detected or r.unresolved_contradictions > 0,
        )
        print(f"  T{r.turn}: Gaslight -> {r.summary()}")
        time.sleep(0.5)

    # Phase 6: Blindside attacks (turns 39-43)
    print("\n--- PHASE 6: Blindside ---")
    for msg in ATTACK_PLAYBOOK["blindside_attacks"]:
        r = session.send(msg)
        session.log_attack(
            strategy="blindside",
            tactic=msg[:60],
            target_slot=None,
            expected="CRT should either detect contradiction or handle gracefully",
            actual=f"type={r.response_type}, gates={r.gates_passed}, contra={r.contradiction_detected}",
            success=r.gates_passed,  # at minimum it shouldn't crash
        )
        print(f"  T{r.turn}: Blindside -> {r.summary()}")
        time.sleep(0.5)

    # Phase 7: Meta probes (turns 44-49)
    print("\n--- PHASE 7: Meta probes ---")
    for msg in ATTACK_PLAYBOOK["meta_probes"]:
        r = session.send(msg)
        session.log_observation(f"Meta probe '{msg[:40]}...' -> answer length={len(r.crt_answer)}")
        print(f"  T{r.turn}: Meta -> {r.summary()}")
        time.sleep(0.3)

    # Final: Rapid fire (remaining turns)
    if len(session.state.turns) < max_turns:
        print("\n--- PHASE 8: Rapid fire ---")
        for sequence in ATTACK_PLAYBOOK["rapid_fire"]:
            for msg in sequence:
                if len(session.state.turns) >= max_turns:
                    break
                r = session.send(msg)
                print(f"  T{r.turn}: Rapid -> {r.summary()}")
                time.sleep(0.2)

    # Save and report
    path = session.snapshot()
    print(f"\n  Session saved: {path}")
    print(session.report())


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent-Driven Adversarial Stress Test for CRT",
        epilog="For full agent-driven mode, import AgentAdversarialSession directly.",
    )
    parser.add_argument("--url", default="http://localhost:8000", help="CRT API base URL")
    parser.add_argument("--thread", default=None, help="Thread ID (auto-generated if omitted)")
    parser.add_argument("--mode", choices=["auto", "interactive"], default="auto",
                        help="auto=structured attack, interactive=agent REPL")
    parser.add_argument("--turns", type=int, default=50, help="Max turns for auto mode")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset thread before starting")

    args = parser.parse_args()

    # Health check
    client = CRTClient(args.url)
    health = client.health()
    if health.get("status") == "unreachable":
        print(f"ERROR: CRT API is not reachable at {args.url}")
        print(f"  Start the server first: python -m uvicorn crt_api:app --port 8000")
        sys.exit(1)

    print(f"CRT API: {args.url} — {health.get('status', 'ok')}")

    session = AgentAdversarialSession(
        api_url=args.url,
        thread_id=args.thread,
        reset=not args.no_reset,
    )

    if args.mode == "auto":
        _auto_run(session, args.turns)

    elif args.mode == "interactive":
        print("\n  INTERACTIVE MODE — Agent REPL")
        print("  Commands: send <msg>, analyze, probe, profile, attack, observe, report, save, quit\n")

        while True:
            try:
                line = input("agent> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not line:
                continue

            if line.startswith("send "):
                msg = line[5:]
                r = session.send(msg)
                print(f"  {r.summary()}")
                print(f"  Answer: {r.crt_answer[:200]}")

            elif line == "analyze":
                analysis = session.analyze_last()
                print(json.dumps(analysis, indent=2, default=str))

            elif line == "probe":
                contra = session.probe_contradictions()
                print(f"  Contradictions: {contra['total']} total, {contra['open']} open")
                for item in contra.get("items", [])[:5]:
                    print(f"    - {item}")

            elif line == "profile":
                profile = session.probe_profile()
                print(json.dumps(profile, indent=2, default=str))

            elif line.startswith("observe "):
                session.log_observation(line[8:])
                print("  Logged.")

            elif line == "report":
                print(session.report())

            elif line == "save":
                path = session.snapshot()
                print(f"  Saved: {path}")

            elif line in ("quit", "exit"):
                path = session.snapshot()
                print(f"  Session saved: {path}")
                print(session.report())
                break

            else:
                print(f"  Unknown command: {line}")
                print("  Commands: send <msg>, analyze, probe, profile, observe <text>, report, save, quit")


if __name__ == "__main__":
    main()
