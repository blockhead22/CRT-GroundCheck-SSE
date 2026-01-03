from sse.ollama_utils import OllamaClient


def test_ollama_client_init():
    client = OllamaClient()
    assert client.base_url == "http://localhost:11434"
    assert client.timeout == 30


def test_ollama_client_cache():
    client = OllamaClient()
    # Mock a cached response
    client._cache[("mistral", "test prompt", "")] = "test response"
    
    # Should return from cache without making a request
    result = client.generate("mistral", "test prompt")
    assert result == "test response"
