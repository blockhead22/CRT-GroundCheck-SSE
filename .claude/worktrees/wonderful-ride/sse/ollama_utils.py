import requests
import json
from typing import Optional, Dict, Any


class OllamaClient:
    """Client for local Ollama instance."""
    
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 30):
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
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
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
