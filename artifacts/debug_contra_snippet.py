import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


def main() -> None:
    # Use temp-on-disk DBs (':memory:' makes separate DBs per sqlite connection)
    art = Path("artifacts")
    art.mkdir(exist_ok=True)
    mem_db = art / "debug_mem.db"
    led_db = art / "debug_led.db"
    for p in (mem_db, led_db):
        if p.exists():
            p.unlink()

    rag = CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())

    print("facts1", extract_fact_slots("My name is Sarah."))
    print("facts2", extract_fact_slots("Actually, my name is Emily."))

    out1 = rag.query("My name is Sarah.")
    print("after1 entry", out1["contradiction_entry"], "open", len(rag.ledger.get_open_contradictions(limit=100)))

    out2 = rag.query("Actually, my name is Emily.")
    print("after2 entry", out2["contradiction_entry"], "open", len(rag.ledger.get_open_contradictions(limit=100)), "detected", out2["contradiction_detected"])


if __name__ == "__main__":
    main()
