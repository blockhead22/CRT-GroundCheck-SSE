#!/usr/bin/env python3
"""
Simple Ollama Chat Demo
Run: python demo_ollama_chat.py
"""

import ollama

def main():
    print("=" * 60)
    print("Simple Ollama Chat Demo")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the conversation\n")
    
    # Chat history
    messages = []
    
    while True:
        # Get user input
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        # Add user message to history
        messages.append({
            'role': 'user',
            'content': user_input
        })
        
        # Get response from Ollama
        try:
            response = ollama.chat(
                model='llama3.2',  # or 'llama2', 'mistral', etc.
                messages=messages
            )
            
            assistant_message = response['message']['content']
            
            # Add assistant response to history
            messages.append({
                'role': 'assistant',
                'content': assistant_message
            })
            
            print(f"\nAssistant: {assistant_message}\n")
            
        except Exception as e:
            print(f"\nError: {e}")
            print("Make sure Ollama is running: ollama serve\n")
            break

if __name__ == "__main__":
    main()