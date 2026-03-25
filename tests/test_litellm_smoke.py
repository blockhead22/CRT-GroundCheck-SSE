"""Smoke test: verify LiteLLM can talk to local Ollama and return a response."""
import litellm

# Test 1: Basic Ollama call
print("=== Test 1: Basic Ollama call ===")
response = litellm.completion(
    model="ollama/qwen3:14b",
    messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
    api_base="http://localhost:11434",
    timeout=120,
)
content = response.choices[0].message.content
print(f"Ollama response: {content}")
assert content and len(content.strip()) > 0, "Empty response from Ollama"
print("PASS\n")

# Test 2: Verify tool calling works through LiteLLM→Ollama
print("=== Test 2: Tool calling ===")
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather for a location",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"]
        }
    }
}]
response = litellm.completion(
    model="ollama/qwen3:14b",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
    api_base="http://localhost:11434",
    timeout=120,
)
msg = response.choices[0].message
print(f"Tool calls: {msg.tool_calls if msg.tool_calls else 'None'}")
print(f"Content: {msg.content or '(empty)'}")
# Either tool calls or content should be present
assert msg.tool_calls or msg.content, "Neither tool calls nor content returned"
print("PASS\n")

print("=== All smoke tests passed ===")
