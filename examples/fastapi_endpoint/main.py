"""
FastAPI Endpoint with CRT Integration
Demonstrates how to add contradiction tracking to a FastAPI chatbot API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
from datetime import datetime

app = FastAPI(
    title="CRT-Enhanced Chatbot API",
    description="Chatbot API with contradiction tracking and disclosure verification",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
CRT_API_URL = "http://127.0.0.1:8123"

# Request/Response Models
class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    thread_id: str
    message: str
    history: Optional[List[Message]] = []

class ChatResponse(BaseModel):
    answer: str
    response_type: str
    contradiction_detected: bool
    contradictions: Optional[List[Dict[str, Any]]] = []
    retrieved_memories: Optional[List[Dict[str, Any]]] = []
    session_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    crt_connected: bool
    timestamp: datetime

# Health Check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and CRT server health"""
    try:
        # Ping CRT API
        response = requests.get(f"{CRT_API_URL}/health", timeout=2)
        crt_connected = response.status_code == 200
    except:
        crt_connected = False
    
    return HealthResponse(
        status="healthy" if crt_connected else "degraded",
        crt_connected=crt_connected,
        timestamp=datetime.now()
    )

# Chat Endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get a response with CRT verification
    
    The CRT system will:
    1. Extract facts from the message
    2. Check for contradictions against existing memories
    3. Return a response with disclosure if contradictions are found
    """
    try:
        # Forward request to CRT API
        crt_response = requests.post(
            f"{CRT_API_URL}/chat",
            json={
                "threadId": request.thread_id,
                "message": request.message,
                "history": [
                    {"role": m.role, "text": m.content}
                    for m in request.history
                ]
            },
            timeout=30
        )
        crt_response.raise_for_status()
        data = crt_response.json()
        
        # Extract relevant data
        metadata = data.get("metadata", {})
        
        return ChatResponse(
            answer=data["answer"],
            response_type=data.get("response_type", "speech"),
            contradiction_detected=metadata.get("contradiction_detected", False),
            contradictions=extract_contradictions(metadata),
            retrieved_memories=metadata.get("retrieved_memories", []),
            session_id=data.get("session_id")
        )
    
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"CRT service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )

# Contradictions Endpoint
@app.get("/contradictions/{thread_id}")
async def get_contradictions(thread_id: str, status: Optional[str] = None):
    """Get contradiction ledger for a thread"""
    try:
        params = {"threadId": thread_id}
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{CRT_API_URL}/contradictions/open",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"CRT service unavailable: {str(e)}"
        )

# Memories Endpoint
@app.get("/memories/{thread_id}")
async def get_memories(
    thread_id: str,
    limit: int = 50,
    min_trust: float = 0.0
):
    """Get memories for a thread"""
    try:
        response = requests.get(
            f"{CRT_API_URL}/memories/recent",
            params={
                "threadId": thread_id,
                "limit": limit,
                "minTrust": min_trust
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"CRT service unavailable: {str(e)}"
        )

# Profile Endpoint
@app.get("/profile/{thread_id}")
async def get_profile(thread_id: str):
    """Get user profile slots for a thread"""
    try:
        response = requests.get(
            f"{CRT_API_URL}/profile",
            params={"threadId": thread_id},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"CRT service unavailable: {str(e)}"
        )

# Helper Functions
def extract_contradictions(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract contradiction details from metadata"""
    # This would be implemented based on actual CRT response format
    # For now, return a simplified version
    if not metadata.get("contradiction_detected"):
        return []
    
    # Extract from retrieved memories if they have conflicts
    memories = metadata.get("retrieved_memories", [])
    # Group by slot and find conflicts
    # ... implementation details
    
    return []

# Example usage documentation
@app.get("/")
async def root():
    """API documentation and examples"""
    return {
        "name": "CRT-Enhanced Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "POST /chat": {
                "description": "Send a message and get response with CRT verification",
                "example": {
                    "thread_id": "user-123",
                    "message": "Where do I work?",
                    "history": []
                }
            },
            "GET /contradictions/{thread_id}": {
                "description": "Get contradiction ledger for a thread",
                "example": "/contradictions/user-123?status=open"
            },
            "GET /memories/{thread_id}": {
                "description": "Get memories for a thread",
                "example": "/memories/user-123?limit=50&min_trust=0.75"
            },
            "GET /profile/{thread_id}": {
                "description": "Get user profile slots",
                "example": "/profile/user-123"
            }
        },
        "documentation": "/docs",
        "crt_features": [
            "Contradiction detection",
            "Mandatory disclosure",
            "Two-lane memory (stable/candidate)",
            "Trust score tracking",
            "Audit trail",
            "Policy-based conflict resolution"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

"""
Usage:

1. Start CRT API server:
   python crt_api.py

2. Start this FastAPI server:
   python main.py

3. Test endpoints:
   
   # Health check
   curl http://localhost:8000/health
   
   # Send message
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{
       "thread_id": "test-123",
       "message": "I work at Microsoft",
       "history": []
     }'
   
   # Get contradictions
   curl http://localhost:8000/contradictions/test-123
   
   # Get memories
   curl http://localhost:8000/memories/test-123?limit=10

4. View interactive docs:
   Open http://localhost:8000/docs
"""
