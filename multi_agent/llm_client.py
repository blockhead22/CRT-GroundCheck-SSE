"""
LLM Client Integration
Supports both API-based models (OpenAI, Anthropic) and local models (Ollama, LM Studio)
"""

import os
import json
from typing import Optional, Dict, Any, List
from enum import Enum


class LLMProvider(Enum):
    """Available LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    MOCK = "mock"  # For testing without real LLM


class LLMClient:
    """
    Unified interface for different LLM providers
    
    Usage:
        # OpenAI
        client = LLMClient(provider=LLMProvider.OPENAI, model="gpt-4")
        
        # Anthropic (Claude)
        client = LLMClient(provider=LLMProvider.ANTHROPIC, model="claude-3-sonnet")
        
        # Local Ollama
        client = LLMClient(provider=LLMProvider.OLLAMA, model="codellama:7b")
        
        # Generate
        response = client.generate("Write a Python function to...")
    """
    
    def __init__(
        self, 
        provider: LLMProvider = LLMProvider.MOCK,
        model: str = "default",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ):
        """
        Initialize LLM client
        
        Args:
            provider: Which LLM provider to use
            model: Model name/identifier
            api_key: API key (if needed)
            base_url: Base URL for API (for local models)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key or self._get_api_key(provider)
        self.base_url = base_url or self._get_default_base_url(provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize provider-specific client
        self.client = self._initialize_client()
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text from prompt
        
        Args:
            prompt: User prompt
            system_prompt: System/instruction prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
        
        Returns:
            Generated text
        """
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        if self.provider == LLMProvider.OPENAI:
            return self._generate_openai(prompt, system_prompt, temperature, max_tokens)
        
        elif self.provider == LLMProvider.ANTHROPIC:
            return self._generate_anthropic(prompt, system_prompt, temperature, max_tokens)
        
        elif self.provider == LLMProvider.OLLAMA:
            return self._generate_ollama(prompt, system_prompt, temperature, max_tokens)
        
        elif self.provider == LLMProvider.LMSTUDIO:
            return self._generate_lmstudio(prompt, system_prompt, temperature, max_tokens)
        
        elif self.provider == LLMProvider.MOCK:
            return self._generate_mock(prompt, system_prompt)
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def generate_code(
        self,
        instruction: str,
        context: Optional[str] = None,
        language: str = "python"
    ) -> str:
        """
        Generate code with appropriate prompting
        
        Args:
            instruction: What code to generate
            context: Additional context (existing code, requirements)
            language: Programming language
        
        Returns:
            Generated code
        """
        system_prompt = f"""You are an expert {language} programmer.
Generate clean, well-documented code following best practices.
Do not include explanatory text, only code.
"""
        
        user_prompt = f"Instruction: {instruction}"
        if context:
            user_prompt += f"\n\nContext:\n{context}"
        
        return self.generate(user_prompt, system_prompt, temperature=0.3)
    
    def analyze_code(
        self,
        code: str,
        analysis_type: str = "general"
    ) -> str:
        """
        Analyze code for patterns, issues, improvements
        
        Args:
            code: Code to analyze
            analysis_type: Type of analysis (general, security, performance, boundaries)
        
        Returns:
            Analysis results
        """
        prompts = {
            "general": "Analyze this code and identify any issues, improvements, or patterns.",
            "security": "Analyze this code for security vulnerabilities.",
            "performance": "Analyze this code for performance issues.",
            "boundaries": "Analyze this code for any forbidden patterns: outcome measurement, persistent learning, confidence scoring, truth filtering, explanation ranking."
        }
        
        system_prompt = "You are a code analysis expert. Provide concise, actionable insights."
        user_prompt = f"{prompts.get(analysis_type, prompts['general'])}\n\n```\n{code}\n```"
        
        return self.generate(user_prompt, system_prompt, temperature=0.2)
    
    def _initialize_client(self):
        """Initialize provider-specific client"""
        if self.provider == LLMProvider.OPENAI:
            try:
                import openai
                if hasattr(openai, 'OpenAI'):
                    return openai.OpenAI(api_key=self.api_key)
                else:
                    print("⚠️  Old OpenAI package version. Upgrade: pip install --upgrade openai")
                    return None
            except ImportError:
                print("⚠️  OpenAI package not installed. Run: pip install openai")
                return None
        
        elif self.provider == LLMProvider.ANTHROPIC:
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                print("⚠️  Anthropic package not installed. Run: pip install anthropic")
                return None
        
        elif self.provider in (LLMProvider.OLLAMA, LLMProvider.LMSTUDIO):
            # Use requests for local models
            return None  # No special client needed
        
        else:
            return None
    
    def _generate_openai(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        """Generate using OpenAI API"""
        if not self.client:
            return f"[MOCK OpenAI] Generated response for: {prompt[:50]}..."
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[ERROR] OpenAI generation failed: {e}"
    
    def _generate_anthropic(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        """Generate using Anthropic (Claude) API"""
        if not self.client:
            return f"[MOCK Anthropic] Generated response for: {prompt[:50]}..."
        
        try:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content[0].text
        except Exception as e:
            return f"[ERROR] Anthropic generation failed: {e}"
    
    def _generate_ollama(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        """Generate using local Ollama"""
        try:
            import requests
            
            url = f"{self.base_url}/api/generate"
            
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            return response.json()["response"]
        
        except Exception as e:
            return f"[ERROR] Ollama generation failed: {e}\nMake sure Ollama is running: ollama serve"
    
    def _generate_lmstudio(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        """Generate using LM Studio local server"""
        try:
            import requests
            
            url = f"{self.base_url}/v1/chat/completions"
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            return response.json()["choices"][0]["message"]["content"]
        
        except Exception as e:
            return f"[ERROR] LM Studio generation failed: {e}\nMake sure LM Studio server is running"
    
    def _generate_mock(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Mock generation for testing without LLM"""
        return f"""[MOCK LLM Response]
Prompt: {prompt[:100]}...
System: {system_prompt[:50] if system_prompt else 'None'}...

This is a mock response. To use real LLM, set provider to OPENAI, ANTHROPIC, OLLAMA, or LMSTUDIO.
"""
    
    def _get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """Get API key from environment"""
        env_vars = {
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY"
        }
        
        env_var = env_vars.get(provider)
        if env_var:
            return os.getenv(env_var)
        return None
    
    def _get_default_base_url(self, provider: LLMProvider) -> str:
        """Get default base URL for provider"""
        defaults = {
            LLMProvider.OLLAMA: "http://localhost:11434",
            LLMProvider.LMSTUDIO: "http://localhost:1234"
        }
        return defaults.get(provider, "")


class LLMPool:
    """
    Pool of LLM clients for different purposes
    
    Usage:
        pool = LLMPool()
        pool.add("code", LLMClient(provider=LLMProvider.OPENAI, model="gpt-4"))
        pool.add("analysis", LLMClient(provider=LLMProvider.OLLAMA, model="codellama:7b"))
        
        # Agents can request specific LLM
        response = pool.get("code").generate("Write a function...")
    """
    
    def __init__(self):
        self.clients: Dict[str, LLMClient] = {}
    
    def add(self, name: str, client: LLMClient):
        """Add LLM client to pool"""
        self.clients[name] = client
    
    def get(self, name: str) -> Optional[LLMClient]:
        """Get LLM client by name"""
        return self.clients.get(name)
    
    def list_clients(self) -> List[str]:
        """List available clients"""
        return list(self.clients.keys())
    
    @classmethod
    def create_default_pool(cls) -> 'LLMPool':
        """
        Create default pool with common configurations
        
        Priority order:
        1. Try OpenAI (if API key available)
        2. Try local Ollama
        3. Fall back to mock
        """
        pool = cls()
        
        # Try OpenAI first
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                client = LLMClient(
                    provider=LLMProvider.OPENAI,
                    model="gpt-4",
                    temperature=0.3
                )
                if client.client:  # Successfully initialized
                    pool.add("code", client)
                    pool.add("analysis", LLMClient(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        temperature=0.2
                    ))
                    pool.add("docs", LLMClient(
                        provider=LLMProvider.OPENAI,
                        model="gpt-3.5-turbo",
                        temperature=0.4
                    ))
            except Exception as e:
                print(f"⚠️  Failed to initialize OpenAI client: {e}")
                openai_key = None  # Fall through to next option
        
        # Try Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and not openai_key:
            pool.add("code", LLMClient(
                provider=LLMProvider.ANTHROPIC,
                model="claude-3-sonnet-20240229",
                temperature=0.3
            ))
            pool.add("analysis", LLMClient(
                provider=LLMProvider.ANTHROPIC,
                model="claude-3-sonnet-20240229",
                temperature=0.2
            ))
        
        # Try local Ollama
        if not openai_key and not anthropic_key:
            try:
                import requests
                # Check if Ollama is running
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    if models:
                        # Use first available model
                        model_name = models[0]["name"]
                        pool.add("code", LLMClient(
                            provider=LLMProvider.OLLAMA,
                            model=model_name,
                            temperature=0.3
                        ))
                        pool.add("analysis", LLMClient(
                            provider=LLMProvider.OLLAMA,
                            model=model_name,
                            temperature=0.2
                        ))
            except:
                pass
        
        # Fallback to mock if nothing available
        if not pool.clients:
            pool.add("code", LLMClient(provider=LLMProvider.MOCK))
            pool.add("analysis", LLMClient(provider=LLMProvider.MOCK))
            pool.add("docs", LLMClient(provider=LLMProvider.MOCK))
        
        return pool
