#!/usr/bin/env python3
"""
ADAPTIVE STRESS TEST - Turn-based reactive adversarial testing

Runs a multi-turn conversation where each user prompt is generated based on 
the model's previous response. Designed to provoke failures in:
- Truth reintroduction after contradiction
- Contradiction inventory honesty
- Gate over-refusal
- Memory drift
- Fallback contamination
- Temporal updates vs conflict handling
"""

import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import urllib.error
import urllib.parse


class AdaptiveStressTest:
    """Reactive adversarial conversation tester"""
    
    def __init__(self, api_base_url: str, thread_id: str, min_turns: int = 40, max_turns: int = 80):
        self.api_base_url = api_base_url.rstrip('/')
        self.thread_id = thread_id
        self.min_turns = min_turns
        self.max_turns = max_turns
        
        # Test state tracking
        self.turn_count = 0
        self.conversation_history = []
        self.introduced_facts = {}  # {fact_key: {value, turn, contradicted_turn}}
        self.contradictions_detected = []
        self.gate_failures = []
        self.phase = "intro"
        self.empty_response_count = 0  # Track consecutive empty responses
        self.raw_payloads_logged = 0  # Log first 3 raw responses for debugging
        
        # Adversarial strategy state
        self.awaiting_contradiction_check = False
        self.last_contradiction_fact = None
        self.temporal_facts = []  # Facts with time dimensions
        
    def api_chat(self, message: str) -> dict:
        """Send message to CRT API and get response"""
        url = f"{self.api_base_url}/api/chat/send"
        payload = {
            "thread_id": self.thread_id,
            "message": message
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                # API returns 'answer' field, not 'response'
                if 'answer' in result and 'response' not in result:
                    result['response'] = result['answer']
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            raise Exception(f"API error {e.code}: {error_body}")
    
    def api_reset_thread(self):
        """Reset thread memory and ledger"""
        url = f"{self.api_base_url}/api/thread/reset"
        payload = {"thread_id": self.thread_id}
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Warning: Thread reset failed: {e}")
            return None
    
    def api_get_contradictions(self) -> list:
        """Get current contradiction ledger"""
        url = f"{self.api_base_url}/api/contradictions?thread_id={self.thread_id}"
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('contradictions', [])
        except Exception as e:
            print(f"Warning: Failed to fetch contradictions: {e}")
            return []
    
    def generate_next_prompt(self, last_response: dict) -> str:
        """Generate next user prompt based on model's last response and test strategy"""
        
        response_text = last_response.get('response', '')
        gated = last_response.get('gated', False)
        
        # Track gate failures
        if gated:
            self.gate_failures.append({
                'turn': self.turn_count,
                'user_message': self.conversation_history[-1]['user'] if self.conversation_history else '',
                'reason': last_response.get('gate_reason', 'unknown')
            })
        
        # Phase progression based on turn count
        if self.turn_count < 10:
            self.phase = "intro"
        elif self.turn_count < 25:
            self.phase = "contradiction"
        elif self.turn_count < 40:
            self.phase = "inventory"
        else:
            self.phase = "adversarial"
        
        # Generate prompt based on phase and conversation state
        if self.phase == "intro":
            return self._intro_phase_prompt()
        elif self.phase == "contradiction":
            return self._contradiction_phase_prompt(response_text)
        elif self.phase == "inventory":
            return self._inventory_phase_prompt(response_text)
        else:
            return self._adversarial_phase_prompt(response_text)
    
    def _intro_phase_prompt(self) -> str:
        """Introduce facts to establish baseline memory"""
        intros = [
            "My name is Alex Chen.",
            "I work as a data scientist at Vertex Analytics.",
            "My favorite programming language is Rust.",
            "I live in Austin, Texas.",
            "I have a golden retriever named Murphy.",
            "My current project is building a recommendation engine.",
            "I graduated from MIT in 2018.",
            "I prefer dark roast coffee.",
            "My weekend hobby is rock climbing.",
            "I'm reading 'Designing Data-Intensive Applications'."
        ]
        
        if self.turn_count < len(intros):
            fact = intros[self.turn_count]
            # Track fact
            fact_key = self._extract_fact_key(fact)
            self.introduced_facts[fact_key] = {
                'value': fact,
                'turn': self.turn_count,
                'contradicted_turn': None
            }
            return fact
        else:
            return "What do you know about me so far?"
    
    def _contradiction_phase_prompt(self, last_response: str) -> str:
        """Introduce contradictions and test detection"""
        
        contradictions = [
            ("name", "Actually, my name is Jordan Chen, not Alex."),
            ("company", "I should clarify - I work at DataCore, not Vertex Analytics."),
            ("language", "I've been rethinking my stance. Python is actually my favorite language now."),
            ("city", "I need to update you - I moved to Denver last month."),
            ("pet", "Sorry, I misspoke earlier. Murphy is a labrador, not a golden retriever."),
            ("project", "My project focus has shifted to real-time anomaly detection systems."),
            ("school", "For the record, I graduated from Stanford, not MIT."),
            ("coffee", "I've switched to light roast lately."),
            ("hobby", "I've taken up trail running instead of climbing."),
            ("book", "I finished that book. Now reading 'The Pragmatic Programmer'.")
        ]
        
        # Introduce contradiction
        if self.turn_count - 10 < len(contradictions):
            fact_key, contradiction = contradictions[self.turn_count - 10]
            if fact_key in self.introduced_facts:
                self.introduced_facts[fact_key]['contradicted_turn'] = self.turn_count
                self.last_contradiction_fact = fact_key
                self.awaiting_contradiction_check = True
            return contradiction
        
        # Ask about contradicted fact to test truth reintroduction
        if self.awaiting_contradiction_check and random.random() < 0.3:
            self.awaiting_contradiction_check = False
            checks = [
                "What's my name?",
                "Where do I work?",
                "What's my favorite programming language?",
                "Which city do I live in?",
                "Tell me about my pet.",
                "What project am I working on?",
                "Where did I go to school?",
                "What kind of coffee do I like?",
                "What's my main hobby?",
                "What book am I reading?"
            ]
            return random.choice(checks)
        
        return "Can you summarize what you know about me?"
    
    def _inventory_phase_prompt(self, last_response: str) -> str:
        """Test contradiction inventory honesty"""
        
        inventory_checks = [
            "List all the contradictions you've detected in our conversation.",
            "What facts about me are you uncertain about?",
            "Show me all the times I changed my mind about something.",
            "What's the current status of contradictions you're tracking?",
            "Are there any unresolved conflicts in what I've told you?",
            "Walk me through your contradiction ledger.",
            "What information about me has conflicting versions?",
            "Tell me about any inconsistencies you've noticed."
        ]
        
        # Inject temporal updates
        if random.random() < 0.2:
            temporal = [
                "I used to work remotely, but now I'm in-office 3 days a week.",
                "I previously lived in Seattle from 2015-2022, then moved.",
                "My old role was backend engineer, my current role is data scientist.",
                "I switched from Java to Rust in 2020.",
                "Murphy is 3 years old now, got him as a puppy in 2023."
            ]
            return random.choice(temporal)
        
        # Adversarial paraphrase (same fact, different wording)
        if random.random() < 0.2:
            paraphrases = [
                "So just to confirm, Jordan Chen is my full name.",
                "I'm employed by DataCore corporation.",
                "Python is the language I prefer for development.",
                "Denver, Colorado is where I'm based.",
                "My dog Murphy is a labrador retriever."
            ]
            return random.choice(paraphrases)
        
        return random.choice(inventory_checks)
    
    def _adversarial_phase_prompt(self, last_response: str) -> str:
        """Advanced adversarial tests"""
        
        adversarial = [
            # Source separation test
            "If you had to guess my age based only on what I've told you, what would it be?",
            
            # Gate pressure (harmless conversational)
            "How's your day going?",
            "What's the weather like?",
            
            # Meta-questions
            "How confident are you in the facts you know about me?",
            "Which pieces of information about me are you most certain about?",
            "What would you need to verify to be 100% sure about my background?",
            
            # Drift test
            "Remind me, what's my dog's name and breed?",
            "Which company am I currently employed at?",
            "What programming language do I use most often?",
            
            # Fallback contamination
            "What's the best way to learn Rust?",
            "Tell me about data science career paths.",
            
            # Truth reintroduction trap
            "Just to double-check: I work at Vertex Analytics, right?",
            "My name is Alex Chen, correct?",
            "I'm still in Austin, aren't I?"
        ]
        
        return random.choice(adversarial)
    
    def _extract_fact_key(self, fact: str) -> str:
        """Extract fact category from statement"""
        if "name" in fact.lower():
            return "name"
        elif "work" in fact.lower() or "analytics" in fact.lower() or "datacore" in fact.lower():
            return "company"
        elif "language" in fact.lower() or "rust" in fact.lower() or "python" in fact.lower():
            return "language"
        elif "live" in fact.lower() or "austin" in fact.lower() or "denver" in fact.lower():
            return "city"
        elif "dog" in fact.lower() or "murphy" in fact.lower() or "retriever" in fact.lower():
            return "pet"
        elif "project" in fact.lower():
            return "project"
        elif "graduated" in fact.lower() or "mit" in fact.lower() or "stanford" in fact.lower():
            return "school"
        elif "coffee" in fact.lower():
            return "coffee"
        elif "hobby" in fact.lower() or "climbing" in fact.lower() or "running" in fact.lower():
            return "hobby"
        elif "reading" in fact.lower() or "book" in fact.lower():
            return "book"
        return f"unknown_{self.turn_count}"
    
    def run(self, output_dir: Path):
        """Execute the adaptive stress test"""
        
        print("\n" + "="*80)
        print(" ADAPTIVE STRESS TEST - REACTIVE ADVERSARIAL CONVERSATION ".center(80, "="))
        print("="*80)
        print(f"\nThread ID: {self.thread_id}")
        print(f"Target turns: {self.min_turns}-{self.max_turns}")
        print(f"API Base: {self.api_base_url}")
        print()
        
        # Reset thread
        print("Resetting thread...")
        self.api_reset_thread()
        time.sleep(0.5)
        
        # Create output files
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        jsonl_path = output_dir / f"adaptive_stress_run.{run_id}.jsonl"
        report_path = output_dir / f"adaptive_stress_report.{run_id}.md"
        
        jsonl_file = open(jsonl_path, 'w', encoding='utf-8')
        
        # Initial prompt
        user_message = "Hello, I'd like to have a conversation with you."
        
        # Main test loop
        while self.turn_count < self.max_turns:
            self.turn_count += 1
            
            print(f"\n{'='*80}")
            print(f" TURN {self.turn_count} | Phase: {self.phase.upper()} ".center(80, "="))
            print(f"{'='*80}")
            print(f"\nUser: {user_message}")
            
            # Send to API
            try:
                response = self.api_chat(user_message)
                
                # Log raw payload for first 3 turns
                if self.raw_payloads_logged < 3:
                    print(f"\n{'='*80}")
                    print(f" RAW API RESPONSE (Turn {self.turn_count}) ".center(80, "="))
                    print(f"{'='*80}")
                    print(json.dumps(response, indent=2)[:500])
                    print(f"{'='*80}\n")
                    self.raw_payloads_logged += 1
                
                response_text = response.get('response', '')
                gated = response.get('gated', False)
                
                # VALIDITY CHECK: Abort if assistant output is empty for 2 consecutive turns
                if not response_text or response_text.strip() == '':
                    self.empty_response_count += 1
                    print(f"\n⚠️  WARNING: Empty assistant response (count: {self.empty_response_count})")
                    
                    if self.empty_response_count >= 2:
                        print(f"\n{'='*80}")
                        print(" RUN ABORTED - INVALID ".center(80, "="))
                        print(f"{'='*80}")
                        print(f"\nReason: EMPTY_ASSISTANT_OUTPUT")
                        print(f"Empty responses: {self.empty_response_count} consecutive turns")
                        print(f"Last API response keys: {list(response.keys())}")
                        print(f"\nThis run is invalid and cannot be used for analysis.")
                        print(f"Check API field mapping (looking for 'response', found: {list(response.keys())})")
                        print(f"{'='*80}\n")
                        
                        # Write abort record to JSONL
                        abort_log = {
                            'turn': self.turn_count,
                            'phase': self.phase,
                            'abort_reason': 'EMPTY_ASSISTANT_OUTPUT',
                            'empty_response_count': self.empty_response_count,
                            'api_response_keys': list(response.keys()),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        jsonl_file.write(json.dumps(abort_log) + '\n')
                        jsonl_file.close()
                        
                        return {
                            'jsonl_path': str(jsonl_path),
                            'report_path': None,
                            'turns_completed': self.turn_count,
                            'status': 'ABORTED',
                            'abort_reason': 'EMPTY_ASSISTANT_OUTPUT'
                        }
                else:
                    self.empty_response_count = 0  # Reset on successful response
                
                print(f"\nAssistant (gated={gated}): {response_text[:200]}...")
                
                # Log to JSONL
                turn_log = {
                    'turn': self.turn_count,
                    'phase': self.phase,
                    'user': user_message,
                    'assistant': response_text,
                    'gated': gated,
                    'gate_reason': response.get('gate_reason'),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                jsonl_file.write(json.dumps(turn_log) + '\n')
                jsonl_file.flush()
                
                # Track conversation
                self.conversation_history.append({
                    'turn': self.turn_count,
                    'user': user_message,
                    'assistant': response_text,
                    'gated': gated
                })
                
                # Small delay
                time.sleep(0.05)
                
                # Generate next prompt
                user_message = self.generate_next_prompt(response)
                
            except Exception as e:
                print(f"\n❌ ERROR on turn {self.turn_count}: {e}")
                turn_log = {
                    'turn': self.turn_count,
                    'phase': self.phase,
                    'user': user_message,
                    'error': str(e),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                jsonl_file.write(json.dumps(turn_log) + '\n')
                jsonl_file.flush()
                
                # Stop on repeated errors
                if self.turn_count > 5:
                    print(f"\nStopping test due to error.")
                    break
                
                user_message = "Let me try again."
        
        jsonl_file.close()
        
        # Fetch final contradictions
        final_contradictions = self.api_get_contradictions()
        
        # Generate report
        self._generate_report(report_path, jsonl_path, final_contradictions)
        
        return {
            'jsonl_path': str(jsonl_path),
            'report_path': str(report_path),
            'turns_completed': self.turn_count,
            'gate_failures': len(self.gate_failures),
            'contradictions_tracked': len(self.introduced_facts),
            'contradictions_detected': len(final_contradictions)
        }
    
    def _generate_report(self, report_path: Path, jsonl_path: Path, contradictions: list):
        """Generate human-readable stress test report"""
        
        # Analyze conversation
        total_turns = len(self.conversation_history)
        gated_turns = sum(1 for t in self.conversation_history if t.get('gated', False))
        gate_pass_rate = ((total_turns - gated_turns) / total_turns * 100) if total_turns > 0 else 0
        
        # Find truth reintroduction failures
        reintroduction_failures = []
        for turn in self.conversation_history:
            user_msg = turn['user'].lower()
            assistant_msg = turn['assistant'].lower()
            
            # Check if user asked about a contradicted fact
            for fact_key, fact_data in self.introduced_facts.items():
                if fact_data['contradicted_turn'] is not None and turn['turn'] > fact_data['contradicted_turn']:
                    # Check if assistant reintroduced the old value
                    old_value = fact_data['value'].lower()
                    if any(word in assistant_msg for word in old_value.split() if len(word) > 3):
                        reintroduction_failures.append({
                            'turn': turn['turn'],
                            'fact_key': fact_key,
                            'old_value': fact_data['value'],
                            'user': turn['user'],
                            'assistant': turn['assistant'][:200]
                        })
        
        # Top 5 gate failures
        top_gate_failures = sorted(self.gate_failures, key=lambda x: x['turn'])[:5]
        
        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# CRT Adaptive Stress Test Report\n\n")
            f.write(f"**Run Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"**Thread ID**: {self.thread_id}\n")
            f.write(f"**JSONL Log**: {jsonl_path.name}\n\n")
            
            f.write("## Summary Statistics\n\n")
            f.write(f"- **Total Turns**: {total_turns}\n")
            f.write(f"- **Gated Turns**: {gated_turns}\n")
            f.write(f"- **Gate Pass Rate**: {gate_pass_rate:.1f}%\n")
            f.write(f"- **Facts Introduced**: {len(self.introduced_facts)}\n")
            f.write(f"- **Facts Contradicted**: {sum(1 for f in self.introduced_facts.values() if f['contradicted_turn'] is not None)}\n")
            f.write(f"- **Contradictions Detected by System**: {len(contradictions)}\n")
            f.write(f"- **Truth Reintroduction Failures**: {len(reintroduction_failures)}\n\n")
            
            f.write("## Contradiction Ledger\n\n")
            if contradictions:
                f.write(f"System detected {len(contradictions)} contradictions:\n\n")
                for i, c in enumerate(contradictions[:10], 1):
                    f.write(f"{i}. **{c.get('claim_a_text', 'N/A')[:100]}** vs **{c.get('claim_b_text', 'N/A')[:100]}**\n")
                    f.write(f"   - Status: {c.get('status', 'unknown')}\n")
                    f.write(f"   - Confidence: {c.get('confidence', 0):.2f}\n\n")
            else:
                f.write("*No contradictions detected by system*\n\n")
            
            f.write("## Truth Reintroduction Failures\n\n")
            if reintroduction_failures:
                f.write(f"Found {len(reintroduction_failures)} instances where the system may have reintroduced contradicted values:\n\n")
                for fail in reintroduction_failures[:5]:
                    f.write(f"### Turn {fail['turn']} - {fail['fact_key']}\n\n")
                    f.write(f"**Old (contradicted) value**: {fail['old_value']}\n\n")
                    f.write(f"**User**: {fail['user']}\n\n")
                    f.write(f"**Assistant**: {fail['assistant']}...\n\n")
            else:
                f.write("*No obvious truth reintroduction failures detected*\n\n")
            
            f.write("## Top 5 Gate Failures\n\n")
            if top_gate_failures:
                for fail in top_gate_failures:
                    f.write(f"### Turn {fail['turn']}\n\n")
                    f.write(f"**User**: {fail['user_message']}\n\n")
                    f.write(f"**Reason**: {fail['reason']}\n\n")
            else:
                f.write("*No gate failures*\n\n")
            
            f.write("## Phase Breakdown\n\n")
            f.write(f"- **Intro** (Turns 1-10): Fact introduction\n")
            f.write(f"- **Contradiction** (Turns 11-25): Contradiction injection & detection\n")
            f.write(f"- **Inventory** (Turns 26-40): Meta-queries & inventory honesty\n")
            f.write(f"- **Adversarial** (Turns 41+): Advanced adversarial tests\n\n")
        
        print(f"\n✅ Report written to: {report_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/adaptive_stress_test.py <thread_id> [min_turns] [max_turns]")
        print("\nExample:")
        print("  python tools/adaptive_stress_test.py adaptive_test_001 40 80")
        sys.exit(1)
    
    thread_id = sys.argv[1]
    min_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    max_turns = int(sys.argv[3]) if len(sys.argv) > 3 else 80
    
    api_base_url = "http://127.0.0.1:8123"
    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tester = AdaptiveStressTest(api_base_url, thread_id, min_turns, max_turns)
    results = tester.run(output_dir)
    
    print("\n" + "="*80)
    print(" TEST COMPLETE ".center(80, "="))
    print("="*80)
    print(f"\nJSONL Log: {results['jsonl_path']}")
    print(f"Report: {results['report_path']}")
    print(f"Turns: {results['turns_completed']}")
    print(f"Gate Failures: {results['gate_failures']}")
    print(f"Contradictions Detected: {results['contradictions_detected']}")
    print()


if __name__ == "__main__":
    main()
