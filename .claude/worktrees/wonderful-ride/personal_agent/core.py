"""
Personal Learning Agent - Core

THIS IS PHASE D+: Full learning, adaptation, and growth.

Key Differences from SSE:
- SSE: Shows contradictions, never resolves them
- Agent: Uses contradictions to offer different approaches
- SSE: Stateless, no memory
- Agent: Learns and remembers everything
- SSE: No user modeling
- Agent: Builds detailed understanding of you

This is experimental. This is local. This is yours.
"""

import os
import json
from typing import List, Dict, Optional, Any
from pathlib import Path

from sse import SSEClient
from .memory import MemorySystem


class PersonalAgent:
    """
    Your personal learning agent that uses SSE for honesty.
    
    Phase D+ Features (intentional):
    - Learns your preferences
    - Remembers what works
    - Tracks patterns in your thinking
    - Uses contradictions to offer alternatives
    - Grows with you over time
    
    Example:
        agent = PersonalAgent(llm_api_key="...")
        agent.index_knowledge("my_notes.txt")
        response = agent.chat("Tell me about sleep")
        # Agent uses SSE to find contradictions
        # Shows you multiple approaches based on what it's learned
    """
    
    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_provider: str = "openai",  # or "anthropic", "local"
        memory_path: str = "personal_agent/memory.db"
    ):
        """
        Initialize your personal agent.
        
        Args:
            llm_api_key: API key for GPT/Claude (or None for local)
            llm_provider: "openai", "anthropic", or "local"
            memory_path: Where to store persistent memory
        """
        # Memory system (Phase D+ - learns and persists)
        self.memory = MemorySystem(memory_path)
        
        # SSE clients for different knowledge bases
        self.knowledge_indices: Dict[str, SSEClient] = {}
        
        # LLM setup
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        
        if llm_provider == "openai" and self.llm_api_key:
            try:
                from openai import OpenAI
                self.llm = OpenAI(api_key=self.llm_api_key)
            except ImportError:
                print("Warning: openai package not installed. Install with: pip install openai")
                self.llm = None
        elif llm_provider == "anthropic" and self.llm_api_key:
            try:
                from anthropic import Anthropic
                self.llm = Anthropic(api_key=self.llm_api_key)
            except ImportError:
                print("Warning: anthropic package not installed. Install with: pip install anthropic")
                self.llm = None
        else:
            # Local mode - would use Ollama or similar
            self.llm = None
            print("Warning: No LLM configured. Set llm_api_key or use local model.")
        
        # Conversation context (Phase D+ - state persistence)
        self.conversation_history: List[Dict[str, str]] = []
    
    def index_knowledge(self, file_path: str, index_name: str = "main"):
        """
        Index a document with SSE for contradiction detection.
        
        Args:
            file_path: Path to document
            index_name: Name for this knowledge base
        """
        output_dir = f"personal_agent/indices/{index_name}"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Run SSE compression
        cmd = f'python -m sse.cli compress --input "{file_path}" --out "{output_dir}"'
        os.system(cmd)
        
        # Load the index
        index_path = f"{output_dir}/index.json"
        if os.path.exists(index_path):
            self.knowledge_indices[index_name] = SSEClient(index_path)
            print(f"✓ Indexed {file_path} as '{index_name}'")
        else:
            print(f"✗ Failed to index {file_path}")
    
    def find_contradictions_in_knowledge(
        self,
        topic: str,
        index_name: str = "main"
    ) -> List[Dict]:
        """
        Use SSE to find contradictions about a topic.
        
        This is Phase C (observation) - SSE finds contradictions.
        What the agent DOES with them is Phase D+ (learning).
        """
        if index_name not in self.knowledge_indices:
            return []
        
        client = self.knowledge_indices[index_name]
        return client.find_contradictions_about(topic)
    
    def _build_system_prompt(self) -> str:
        """
        Build system prompt using learned preferences.
        
        Phase D+ violation: Uses learned user model.
        """
        stats = self.memory.get_stats()
        
        # Get learned preferences
        communication_style = self.memory.get_preference("communication_style")
        interests = self.memory.get_preference("main_interests")
        
        prompt = f"""You are a personal learning agent. You remember conversations and learn patterns.

Your relationship with this user:
- Total conversations: {stats['conversations']}
- Preferences learned: {stats['preferences_learned']}
- Contradictions resolved: {stats['contradictions_resolved']}
"""
        
        if communication_style:
            prompt += f"\nCommunication style preference: {communication_style['value']}\n"
        
        if interests:
            prompt += f"\nMain interests: {interests['value']}\n"
        
        prompt += """
When you find contradictions (via SSE), offer multiple approaches:
1. Present both sides clearly
2. Explain the context for each
3. Suggest different ways to think about it
4. Ask which resonates more

Learn from their choices. Adapt to their thinking style.
"""
        
        return prompt
    
    def chat(self, user_message: str, index_name: str = "main") -> str:
        """
        Main chat interface with learning and contradiction checking.
        
        Phase D+ Features:
        - Remembers conversation history
        - Learns from user's choices
        - Uses contradictions to offer alternatives
        - Adapts approach based on what works
        """
        if not self.llm:
            return "No LLM configured. Please set API key or use local model."
        
        # Add to conversation history (Phase D+ - memory)
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Check for contradictions in knowledge base (Phase C - SSE observation)
        contradictions = []
        if index_name in self.knowledge_indices:
            contradictions = self.find_contradictions_in_knowledge(
                user_message,
                index_name
            )
        
        # Build context with recent memory (Phase D+ - learning)
        recent_convs = self.memory.get_recent_conversations(limit=5)
        context = "\n".join([
            f"User: {c['user_message']}\nAgent: {c['agent_response']}"
            for c in recent_convs
        ])
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        
        # Add context if available
        if context:
            messages.append({
                "role": "system",
                "content": f"Recent conversation history:\n{context}"
            })
        
        # Add contradiction info if found
        if contradictions:
            contra_text = f"Found {len(contradictions)} contradictions about this topic:\n"
            for i, c in enumerate(contradictions[:3], 1):  # Limit to 3
                contra_text += f"\n{i}. Contradiction between claims\n"
            
            messages.append({
                "role": "system",
                "content": f"{contra_text}\nPresent multiple approaches based on these contradictions."
            })
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Generate response
        if self.llm_provider == "openai":
            response = self.llm.chat.completions.create(
                model="gpt-4o-mini",  # or gpt-4
                messages=messages
            )
            agent_response = response.choices[0].message.content
        elif self.llm_provider == "anthropic":
            response = self.llm.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=messages[0]["content"],
                messages=[m for m in messages[1:] if m["role"] != "system"]
            )
            agent_response = response.content[0].text
        else:
            agent_response = "Local LLM not yet implemented"
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": agent_response
        })
        
        # Store in memory (Phase D+ - outcome measurement)
        self.memory.store_conversation(
            user_message=user_message,
            agent_response=agent_response,
            context=context,
            contradictions=contradictions,
            approach="contradiction-aware" if contradictions else "direct"
        )
        
        return agent_response
    
    def learn_from_feedback(self, was_helpful: bool, aspect: Optional[str] = None):
        """
        Explicit learning from user feedback.
        
        Phase D+ violation: Outcome measurement and model updates.
        This is how the agent improves.
        """
        if not self.conversation_history:
            return
        
        last_user_msg = self.conversation_history[-2]["content"] if len(self.conversation_history) >= 2 else ""
        last_agent_msg = self.conversation_history[-1]["content"]
        
        # Record strategy outcome
        self.memory.record_strategy_outcome(
            situation=last_user_msg[:100],  # Truncate for storage
            approach=last_agent_msg[:200],
            outcome="helpful" if was_helpful else "not_helpful",
            success_score=1.0 if was_helpful else 0.0
        )
        
        # Learn preference if aspect mentioned
        if aspect and was_helpful:
            self.memory.learn_preference(
                key=f"prefers_{aspect}",
                value="yes",
                confidence=0.8
            )
    
    def show_contradictions(self, topic: str, index_name: str = "main") -> str:
        """
        Show contradictions about a topic with multiple interpretations.
        
        Uses SSE (Phase C) to find contradictions.
        Uses Agent (Phase D+) to offer approaches.
        """
        if index_name not in self.knowledge_indices:
            return f"No knowledge index '{index_name}' found."
        
        client = self.knowledge_indices[index_name]
        contradictions = client.find_contradictions_about(topic)
        
        if not contradictions:
            return f"No contradictions found about '{topic}'"
        
        output = f"Found {len(contradictions)} contradiction(s) about '{topic}':\n\n"
        
        for i, contra in enumerate(contradictions, 1):
            output += f"--- Contradiction {i} ---\n"
            output += client.format_contradiction(contra)
            output += "\n\n"
            
            # Agent offers approaches (Phase D+)
            output += "Different ways to think about this:\n"
            output += "1. Both could be true in different contexts\n"
            output += "2. One might be more recent/updated information\n"
            output += "3. They might be using different definitions\n"
            output += "4. This might reflect evolving understanding\n\n"
        
        return output
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about what the agent has learned."""
        return self.memory.get_stats()
    
    def reset_conversation(self):
        """Clear conversation history (but keep long-term memory)."""
        self.conversation_history = []
    
    def export_memory(self, output_path: str):
        """Export all learned memory to JSON."""
        stats = self.get_memory_stats()
        recent = self.memory.get_recent_conversations(limit=50)
        
        export_data = {
            "stats": stats,
            "recent_conversations": recent,
            "knowledge_indices": list(self.knowledge_indices.keys())
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Memory exported to {output_path}")
