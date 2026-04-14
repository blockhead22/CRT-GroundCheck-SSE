import requests
import json
from typing import Optional, Dict, Any


class OllamaClient:
    """Client for local Ollama instance."""
    
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout
        self._cache = {}
    
    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate(self, model: str, prompt: str, system: str = "") -> Optional[str]:
        """Generate text using Ollama."""
        cache_key = (model, prompt, system)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Disable thinking mode for qwen3 models — without think:false, qwen3
            # spends all token budget on reasoning and returns empty content.
            _is_qwen3 = "qwen3" in model.lower()
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
            if _is_qwen3:
                payload["think"] = False
            if system:
                payload["system"] = system
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "").strip()
            self._cache[cache_key] = text
            return text
        except Exception as e:
            print(f"[Ollama error: {e}]")
            return None
    
    def clear_cache(self):
        """Clear response cache."""
        self._cache = {}
