from pathlib import Path
import sys

# Ensure repo root is importable when running from artifacts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client


def main() -> None:
    art = Path("artifacts")
    art.mkdir(exist_ok=True)

    mem = art / "regression_memory.db"
    led = art / "regression_ledger.db"
    for p in (mem, led):
        if p.exists():
            p.unlink()

    ollama = get_ollama_client("llama3.2:latest")
    rag = CRTEnhancedRAG(memory_db=str(mem), ledger_db=str(led), llm_client=ollama)

    print("open0", len(rag.ledger.get_open_contradictions(limit=100)))
    rag.query("Hello. My name is Sarah.")
    print("open1", len(rag.ledger.get_open_contradictions(limit=100)))
    rag.query("What's my name?")
    print("open2", len(rag.ledger.get_open_contradictions(limit=100)))
    rag.query("Actually, my name is Emily.")
    print("open3", len(rag.ledger.get_open_contradictions(limit=100)))


if __name__ == "__main__":
    main()
