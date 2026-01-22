# LangChain Integration Guide

**Add CRT contradiction tracking to your LangChain applications**

---

## Overview

This guide shows how to integrate CRT's contradiction tracking and disclosure verification into LangChain-based chatbots and agents.

---

## Installation

```bash
pip install langchain langchain-community groundcheck
```

---

## Basic Integration

### 1. Create CRT Memory Wrapper

```python
from langchain.memory import ConversationBufferMemory
from groundcheck import GroundCheck, Memory
from typing import List, Dict

class CRTMemory:
    """LangChain-compatible memory with CRT verification"""
    
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.verifier = GroundCheck()
        self.memories: List[Memory] = []
        self.buffer = ConversationBufferMemory(return_messages=True)
    
    def add_user_message(self, text: str):
        """Store user message and extract facts"""
        # Store in conversation buffer
        self.buffer.chat_memory.add_user_message(text)
        
        # Extract and store as CRT memory
        memory = Memory(
            id=f"m{len(self.memories)}",
            text=text,
            timestamp=time.time()
        )
        self.memories.append(memory)
    
    def add_ai_message(self, text: str):
        """Verify AI message for contradictions before storing"""
        # Verify against existing memories
        result = self.verifier.verify(text, self.memories)
        
        if result.requires_disclosure:
            # Add disclosure to response
            text = result.expected_disclosure
            print(f"⚠️ Disclosure added: {text}")
        
        # Store in conversation buffer
        self.buffer.chat_memory.add_ai_message(text)
        return text
    
    def get_messages(self):
        """Get conversation history"""
        return self.buffer.chat_memory.messages
```

### 2. Use in LangChain Chain

```python
from langchain.chains import ConversationChain
from langchain_community.llms import Ollama

# Initialize LLM
llm = Ollama(model="llama3.2")

# Initialize CRT memory
crt_memory = CRTMemory(thread_id="demo-thread")

# Create chain (note: we handle memory manually for verification)
chain = ConversationChain(
    llm=llm,
    verbose=True
)

def chat_with_crt(user_input: str) -> str:
    """Send message with CRT verification"""
    # Add user message to CRT memory
    crt_memory.add_user_message(user_input)
    
    # Get conversation history
    history = "\n".join([
        f"{m.type}: {m.content}"
        for m in crt_memory.get_messages()
    ])
    
    # Generate response
    response = chain.predict(input=user_input, history=history)
    
    # Verify and add AI message (with disclosure if needed)
    verified_response = crt_memory.add_ai_message(response)
    
    return verified_response

# Example usage
print(chat_with_crt("I work at Microsoft"))
# Output: "Got it! I'll remember you work at Microsoft."

print(chat_with_crt("I work at Amazon now"))
# Output: "⚠️ Contradiction detected! ..."

print(chat_with_crt("Where do I work?"))
# Output: "You work at Amazon (changed from Microsoft)."
```

---

## Advanced: RAG with CRT

### Using LangChain's Retriever

```python
from langchain.vectorstores import FAISS
from langchain.embeddings import OllamaEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainFilter

class CRTRAGChain:
    """RAG chain with CRT contradiction checking"""
    
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.verifier = GroundCheck()
        
        # Initialize embeddings and vector store
        self.embeddings = OllamaEmbeddings(model="llama3.2")
        self.vectorstore = FAISS.from_texts([], self.embeddings)
        
        # Initialize LLM
        self.llm = Ollama(model="llama3.2")
    
    def add_memory(self, text: str):
        """Add text to vector store and CRT memory"""
        # Add to vector store for retrieval
        self.vectorstore.add_texts([text])
        
        # Could also track in CRT memory list if needed
    
    def query(self, question: str, k: int = 5) -> str:
        """Query with retrieval and contradiction checking"""
        # Retrieve relevant memories
        docs = self.vectorstore.similarity_search(question, k=k)
        
        # Convert to CRT Memory objects
        memories = [
            Memory(id=f"m{i}", text=doc.page_content)
            for i, doc in enumerate(docs)
        ]
        
        # Generate answer using LLM + retrieved context
        context = "\n".join([doc.page_content for doc in docs])
        prompt = f"""Context: {context}

Question: {question}

Answer based on the context:"""
        
        answer = self.llm.predict(prompt)
        
        # Verify for contradictions
        result = self.verifier.verify(answer, memories)
        
        if result.requires_disclosure:
            answer = result.expected_disclosure
            print(f"⚠️ Disclosure added to answer")
        
        return answer

# Example usage
rag = CRTRAGChain(thread_id="rag-demo")

# Add knowledge
rag.add_memory("User works at Microsoft")
rag.add_memory("User works at Amazon")  # Contradiction!

# Query
answer = rag.query("Where does the user work?")
print(answer)
# Expected: Answer with disclosure about the contradiction
```

---

## Integration with LangChain Agents

```python
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

def create_crt_tool():
    """Create a LangChain tool for CRT memory operations"""
    
    def verify_statement(statement: str) -> str:
        """Verify a statement against known facts"""
        verifier = GroundCheck()
        # Load memories from your storage
        memories = load_memories()
        
        result = verifier.verify(statement, memories)
        
        if result.contradictions:
            return f"⚠️ Contradiction detected: {result.expected_disclosure}"
        return "✅ Statement verified, no contradictions"
    
    return Tool(
        name="CRT_Verifier",
        func=verify_statement,
        description="Verify statements for contradictions against known facts. Use this before making claims about user information."
    )

# Create agent with CRT tool
tools = [
    create_crt_tool(),
    # ... other tools
]

agent = create_react_agent(
    llm=Ollama(model="llama3.2"),
    tools=tools,
    prompt=PromptTemplate.from_template("""You are a helpful assistant with access to CRT verification.
Always verify user information using the CRT_Verifier tool before making claims.

Tools: {tools}

Question: {input}
Thought: {agent_scratchpad}""")
)

executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Use the agent
result = executor.invoke({"input": "Where does the user work?"})
print(result)
```

---

## Best Practices

### 1. Always Verify Before Responding

```python
def safe_respond(user_input: str, memories: List[Memory]) -> str:
    """Generate response with automatic verification"""
    verifier = GroundCheck()
    
    # Generate initial response
    response = llm.predict(user_input)
    
    # Verify
    result = verifier.verify(response, memories)
    
    # Use disclosure if needed
    return result.expected_disclosure if result.requires_disclosure else response
```

### 2. Track Memory Sources

```python
class TrackedMemory(Memory):
    """Memory with source tracking for better debugging"""
    
    def __init__(self, text: str, source: str = "user_stated"):
        super().__init__(
            id=generate_id(),
            text=text,
            metadata={"source": source, "timestamp": time.time()}
        )
```

### 3. Handle Edge Cases

```python
def robust_verify(statement: str, memories: List[Memory]) -> str:
    """Verification with error handling"""
    verifier = GroundCheck()
    
    try:
        result = verifier.verify(statement, memories)
        return result.expected_disclosure if result.requires_disclosure else statement
    except Exception as e:
        logger.error(f"CRT verification failed: {e}")
        # Fallback: add a generic disclaimer
        return f"{statement} (Note: Could not verify against memory)"
```

---

## Complete Example

See [examples/langchain_demo/](../../examples/langchain_demo/) for a complete working example with:
- LangChain + CRT integration
- Vector store for retrieval
- Agent with CRT verification tool
- Web interface

---

## Troubleshooting

### Memory Not Persisting

**Problem:** Memories lost between sessions

**Solution:** Use persistent storage
```python
import json

def save_memories(memories: List[Memory], path: str):
    with open(path, 'w') as f:
        json.dump([m.dict() for m in memories], f)

def load_memories(path: str) -> List[Memory]:
    with open(path, 'r') as f:
        data = json.load(f)
        return [Memory(**m) for m in data]
```

### Slow Performance

**Problem:** Verification takes too long

**Solution:** Batch verification or cache results
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_verify(statement: str, memories_hash: int):
    # verification logic
    pass
```

---

## Next Steps

- See [Custom RAG Integration](./custom_rag_integration.md) for more advanced patterns
- Check [examples/langchain_demo/](../../examples/langchain_demo/) for complete code
- Read [API Reference](./api_reference.md) for full CRT API documentation
