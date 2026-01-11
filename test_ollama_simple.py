import pytest


pytest.skip("integration script; requires optional 'ollama' package", allow_module_level=True)


import ollama

print("Testing Ollama...")
response = ollama.chat(
    model='mistral:latest',
    messages=[{'role': 'user', 'content': 'Say hello in 5 words or less.'}]
)
print("Success!")
print(response['message']['content'])
