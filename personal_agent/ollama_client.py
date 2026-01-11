"""Ollama LLM client for CRT.

This integration is optional. The rest of the repo (tests, heuristic tooling)
should remain usable even when the `ollama` Python package isn't installed.
"""

import os
from typing import Optional, Dict, List, Any

try:
    import ollama  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    ollama = None  # type: ignore[assignment]


class OllamaClient:
    """Client for Ollama local LLM."""
    
    def __init__(self, model: str = "llama3.2:latest"):
        """
        Initialize Ollama client.
        
        Popular models:
        - llama3.2:latest (3B): Fast and efficient
        - mistral:latest: Good for chat
        - deepseek-r1:8b: Reasoning-focused
        - codellama: Good for code
        """
        self.model = model

        if ollama is None:
            raise ModuleNotFoundError(
                "Optional dependency 'ollama' is not installed. Install with: pip install ollama"
            )

        # Default request timeout so the UI/test harness can't hang forever.
        # Can be overridden via env var OLLAMA_TIMEOUT_SECONDS.
        timeout_s = None
        try:
            env = os.getenv("OLLAMA_TIMEOUT_SECONDS", "")
            timeout_s = float(env) if env else 120.0
        except Exception:
            timeout_s = 120.0

        # Use a dedicated client instance so we can pass timeout/settings.
        # The underlying ollama Python client forwards kwargs to httpx.Client.
        try:
            self._client = ollama.Client(timeout=timeout_s)  # type: ignore[union-attr]
        except Exception:
            self._client = None
        self._verify_model()
    
    def _verify_model(self):
        """Check if model is available."""
        try:
            # Try to list models - don't fail if this doesn't work
            if self._client is not None and hasattr(self._client, "list"):
                self._client.list()
            else:
                ollama.list()  # type: ignore[union-attr]
            # If we get here, Ollama is running
        except:
            # Silently continue - we'll find out when we try to generate
            pass
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
            max_tokens: Max tokens to generate
            temperature: Sampling temperature (0-1)
            stream: Whether to stream response
        
        Returns:
            Generated text
        """
        messages = []
        
        if system:
            messages.append({
                'role': 'system',
                'content': system
            })
        
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        try:
            chat_fn = self._client.chat if (self._client is not None and hasattr(self._client, "chat")) else ollama.chat  # type: ignore[union-attr]

            response = chat_fn(
                model=self.model,
                messages=messages,
                options={
                    'num_predict': max_tokens,
                    'temperature': temperature
                },
                stream=stream
            )
            
            if stream:
                # Return generator for streaming
                return response
            else:
                return response['message']['content']
        
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower():
                return f"[Ollama connection error: Is Ollama running? Try: ollama serve]"
            elif "not found" in error_msg.lower():
                return f"[Model '{self.model}' not found. Try: ollama pull {self.model}]"
            else:
                return f"[Ollama error: {e}]"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """
        Chat with message history.
        
        Args:
            messages: List of {'role': 'user'|'assistant', 'content': str}
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
        
        Returns:
            Generated response
        """
        try:
            chat_fn = self._client.chat if (self._client is not None and hasattr(self._client, "chat")) else ollama.chat  # type: ignore[union-attr]

            response = chat_fn(
                model=self.model,
                messages=messages,
                options={
                    'num_predict': max_tokens,
                    'temperature': temperature
                }
            )
            return response['message']['content']
        except Exception as e:
            return f"[Ollama error: {e}]"
    
    def extract_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract user intent from query.
        
        Returns:
            {
                'intent': str,
                'entities': List[str],
                'importance': float (0-1)
            }
        """
        prompt = f"""Analyze this user query and extract:
1. The main intent (what they want)
2. Any important entities or facts
3. Importance score (0-1, how important to remember this)

Query: "{query}"

Respond in this format:
Intent: <intent>
Entities: <comma-separated entities>
Importance: <0.0-1.0>"""
        
        response = self.generate(prompt, max_tokens=200, temperature=0.3)
        
        # Parse response
        intent_data = {
            'intent': 'unknown',
            'entities': [],
            'importance': 0.5
        }
        
        try:
            for line in response.split('\n'):
                if line.startswith('Intent:'):
                    intent_data['intent'] = line.replace('Intent:', '').strip()
                elif line.startswith('Entities:'):
                    entities_str = line.replace('Entities:', '').strip()
                    intent_data['entities'] = [e.strip() for e in entities_str.split(',') if e.strip()]
                elif line.startswith('Importance:'):
                    importance_str = line.replace('Importance:', '').strip()
                    try:
                        intent_data['importance'] = float(importance_str)
                    except:
                        pass
        except:
            pass
        
        return intent_data


# Global instance
_global_client: Optional[OllamaClient] = None


def get_ollama_client(model: str = "llama3.2:latest") -> OllamaClient:
    """Get or create global Ollama client."""
    global _global_client
    if ollama is None:
        raise ModuleNotFoundError(
            "Optional dependency 'ollama' is not installed. Install with: pip install ollama"
        )
    if _global_client is None or _global_client.model != model:
        _global_client = OllamaClient(model)
    return _global_client
