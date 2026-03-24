"""Seed Aether's self-knowledge into GroundCheck memory.

Run once (or on startup) to ensure the system has retrievable memories
about its own architecture. These are stored as SYSTEM-source memories
with high trust so they surface when the user asks "how do you work?"
or "how do you know that?"

Idempotent: skips facts that already exist (by text prefix match).
"""

import sys, os, time, logging

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# ── Architecture facts to store ──────────────────────────────────────────
# Each tuple: (text, domain_tags)
SELF_KNOWLEDGE = [
    # Identity
    (
        "I am Aether, a personal AI assistant built on the CRT-GroundCheck architecture. "
        "I run locally on the user's machine using Ollama for LLM inference and GroundCheck for memory.",
        ["system", "identity"],
    ),
    # Memory system
    (
        "My memory system is GroundCheck: a SQLite-backed store where every fact is embedded as a "
        "384-dimensional vector using the all-MiniLM-L6-v2 sentence transformer. Each memory has a "
        "trust score from 0.0 to 1.0 that evolves over time based on reinforcement and contradiction signals.",
        ["system", "memory"],
    ),
    # Retrieval mechanism
    (
        "When the user asks a question, I convert it to a 384-dimensional embedding and compare it "
        "against all stored memories using cosine similarity. The top matching memories are retrieved "
        "and included in my prompt context so I can answer from real stored facts.",
        ["system", "retrieval"],
    ),
    # CRT-as-Critic
    (
        "After I generate an answer, CRT-as-Critic runs GroundCheck.verify() to check my response "
        "against stored memories. This verification takes about 1 millisecond and catches contradictions "
        "between my answer and what I actually know. If I contradict a stored memory, it flags it.",
        ["system", "verification"],
    ),
    # Contradiction ledger
    (
        "When conflicting facts arrive — for example 'I work at Google' followed by 'I work at Microsoft' — "
        "both facts are kept in a contradiction ledger with timestamps and trust scores. Nothing is silently "
        "overwritten. The system tracks open contradictions and can disclose them when relevant.",
        ["system", "contradiction"],
    ),
    # Web search
    (
        "I have a DuckDuckGo web search tool that I can use when I don't have the answer in my memory. "
        "This lets me look up real-time information, current events, and factual questions that aren't "
        "covered by what the user has told me.",
        ["system", "tools"],
    ),
    # Reconstruction gates
    (
        "My answers are scored by reconstruction gates that measure intent-alignment (did I answer the "
        "right question?) and memory-alignment (does my answer match stored facts?). If either score "
        "is too low, the answer is marked as low-confidence 'speech' rather than high-confidence 'belief'.",
        ["system", "gates"],
    ),
    # Heartbeat
    (
        "I have a heartbeat system — a background process that runs on a timer. It periodically runs "
        "trust decay passes (older uncorroborated memories lose trust), reviews contradiction inventory, "
        "audits memory health, and does autonomous maintenance without requiring user interaction.",
        ["system", "heartbeat"],
    ),
    # Trust decay
    (
        "Trust decay is a process where memories that haven't been reinforced gradually lose trust over time. "
        "This means old, unverified facts naturally fade while frequently referenced or recently confirmed "
        "facts maintain high trust scores. The heartbeat system runs this automatically.",
        ["system", "trust"],
    ),
    # LLM
    (
        "My language model is Ollama running llama3.2 locally. All inference happens on the user's machine — "
        "nothing is sent to external APIs. The LLM generates responses, but GroundCheck memory and CRT-as-Critic "
        "ground and verify those responses against stored facts.",
        ["system", "llm"],
    ),
    # How storage happens
    (
        "When the user tells me something, I extract facts from their message, embed the text as a "
        "384-dimensional vector, compute a significance score (novelty, emotion, user-marked importance), "
        "assign an initial trust score based on the source, and store it in my SQLite database.",
        ["system", "storage"],
    ),

    # ── Tool Capabilities (Sprint 12) ────────────────────────────────────
    # These let the conversational pipeline know what tools Aether has,
    # so it can answer "can you do X?" accurately and trigger re-routing.

    # Desktop control
    (
        "I can control the user's desktop using my desktop_action tool. I can open applications, "
        "click on screen elements, type text, scroll, use keyboard shortcuts, and interact with any "
        "visible UI element. I do this through a screenshot-vision-action loop: I take a screenshot, "
        "analyze it with a vision model, decide what to do, execute the action, then verify the result.",
        ["system", "tools", "capability"],
    ),
    # System info
    (
        "I can check the user's system status using my system_info tool. This shows which applications "
        "are currently running, the active window, CPU usage, RAM usage, GPU status, and disk space. "
        "If someone asks 'what apps are open' or 'how's my system doing', I should use this tool.",
        ["system", "tools", "capability"],
    ),
    # File operations
    (
        "I can read and write files on the local filesystem using my file_read and file_write tools. "
        "I can also list directory contents with dir_list and scan project structures with project_scan. "
        "File operations are gated by allowed paths for safety.",
        ["system", "tools", "capability"],
    ),
    # Shell execution
    (
        "I can run shell commands and scripts using my shell_exec tool. This includes git operations "
        "via git_exec. Dangerous commands are blocked, and all shell operations require checkpoint "
        "confirmation from the user.",
        ["system", "tools", "capability"],
    ),
    # Content generation
    (
        "I can generate file content using my generate_content tool. When asked to create a file with "
        "a description like 'create an HTML page with a dark theme', I use an LLM to generate the "
        "actual code and then write it to disk.",
        ["system", "tools", "capability"],
    ),
    # Commitments/reminders
    (
        "I can set reminders and commitments using my create_commitment tool. I understand natural "
        "language time expressions like 'in 5 minutes', 'tomorrow at 9am', 'every weekday at noon'. "
        "I can also list and cancel existing reminders.",
        ["system", "tools", "capability"],
    ),
    # URL fetch
    (
        "I can fetch and read web pages using my fetch_url tool. I can visit URLs, extract content, "
        "and follow instructions found on skill pages.",
        ["system", "tools", "capability"],
    ),
    # Desktop limitations
    (
        "My desktop control has safety limits: I cannot interact with password managers, banking apps, "
        "or enter passwords/credit card numbers. I am rate-limited to prevent runaway automation. "
        "The system tray area is restricted. Moving the mouse to the top-left corner (0,0) aborts all automation.",
        ["system", "tools", "safety"],
    ),
]


def seed_self_knowledge(memory_system, force: bool = False) -> int:
    """Store self-knowledge facts into the memory system.
    
    Args:
        memory_system: A CRTMemorySystem instance
        force: If True, store even if similar text already exists
        
    Returns:
        Number of new memories stored
    """
    from personal_agent.crt_core import MemorySource
    
    existing = memory_system._load_all_memories()
    existing_texts = {m.text.strip().lower() for m in existing}
    
    stored = 0
    for text, domain_tags in SELF_KNOWLEDGE:
        # Skip if a memory with very similar text already exists
        text_lower = text.strip().lower()
        # Check prefix match (first 80 chars) to handle minor edits
        prefix = text_lower[:80]
        if not force and any(et.startswith(prefix) for et in existing_texts):
            logger.debug(f"[SEED] Skipping (already exists): {text[:60]}...")
            continue
        
        mem = memory_system.store_memory(
            text=text,
            confidence=1.0,
            source=MemorySource.SYSTEM,
            context={"type": "self_knowledge", "domain_tags": domain_tags},
            user_marked_important=False,
        )
        # Boost trust to 0.95 for self-knowledge
        if mem and hasattr(mem, 'trust'):
            mem.trust = 0.95
            # Persist the boosted trust
            try:
                memory_system._update_memory_trust(mem.memory_id, 0.95)
            except Exception:
                pass
        
        # Set domain tags
        if mem and hasattr(mem, 'domain_tags'):
            mem.domain_tags = domain_tags
        
        stored += 1
        logger.info(f"[SEED] Stored self-knowledge: {text[:60]}...")
    
    if stored:
        logger.info(f"[SEED] Stored {stored} self-knowledge memories")
    else:
        logger.info("[SEED] All self-knowledge already present, nothing to store")
    
    return stored


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from personal_agent.crt_memory import CRTMemorySystem
    from personal_agent.crt_core import CRTConfig
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "crt_memory.db")
    config = CRTConfig()
    mem_sys = CRTMemorySystem(db_path, config)
    
    count = seed_self_knowledge(mem_sys, force="--force" in sys.argv)
    print(f"Done. Stored {count} new self-knowledge memories.")
