"""CRT API Server (simplified for bug challenge)"""
import os
from dotenv import load_dotenv

# Load .env file — this sets PORT=8123
load_dotenv(override=True)

PORT = int(os.getenv("PORT", "8000"))

def start_server():
    """Start uvicorn on the configured port."""
    print(f"[BACKEND] Starting on port {PORT}")
    # uvicorn.run(app, host="127.0.0.1", port=PORT)

if __name__ == "__main__":
    start_server()
