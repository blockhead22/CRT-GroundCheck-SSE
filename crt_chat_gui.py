"""
CRT Chat GUI - Streamlit Interface

Interactive chat with CRT system using Ollama.
"""

import streamlit as st
import time
from datetime import datetime
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client


# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="CRT Chat",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        color: #1a1a1a;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        color: #0d47a1;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
        color: #1b5e20;
    }
    .belief-badge {
        background-color: #4caf50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .speech-badge {
        background-color: #ff9800;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .contradiction-badge {
        background-color: #f44336;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    .metadata-box {
        background-color: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 0.3rem;
        padding: 0.5rem;
        margin-top: 0.5rem;
        font-size: 0.85rem;
        color: #333333;
    }
    strong {
        color: #1a1a1a;
    }
    .stExpander {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
    }
    .stMetric {
        color: #1a1a1a;
    }
    .stMarkdown p, .stMarkdown li {
        color: #333333;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Initialize Session State
# ============================================================================

if 'crt_system' not in st.session_state:
    st.session_state.crt_system = None

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'show_metadata' not in st.session_state:
    st.session_state.show_metadata = True

if 'ollama_model' not in st.session_state:
    st.session_state.ollama_model = "llama3.2:latest"


# ============================================================================
# Initialize CRT System
# ============================================================================

@st.cache_resource
def initialize_crt(model_name: str = "llama3.2:latest"):
    """Initialize CRT system with Ollama."""
    try:
        # Initialize Ollama client
        ollama_client = get_ollama_client(model_name)
        
        # Initialize CRT
        rag = CRTEnhancedRAG(llm_client=ollama_client)
        
        return rag, None
    except Exception as e:
        return None, str(e)


# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.markdown("# 🧠 CRT Chat")
    st.markdown("**Cognitive-Reflective Transformer**")
    st.markdown("---")
    
    # Ollama model selection
    st.markdown("### 🤖 LLM Settings")
    
    model_options = ["llama3.2:latest", "mistral:latest", "deepseek-r1:8b", "deepseek-coder:latest", "llava:7b"]
    selected_model = st.selectbox(
        "Ollama Model",
        model_options,
        index=model_options.index(st.session_state.ollama_model) if st.session_state.ollama_model in model_options else 0,
        help="Select which Ollama model to use"
    )
    
    if selected_model != st.session_state.ollama_model:
        st.session_state.ollama_model = selected_model
        st.session_state.crt_system = None  # Force reinit
        st.rerun()
    
    # Display toggle
    st.markdown("### 📊 Display Options")
    st.session_state.show_metadata = st.checkbox(
        "Show CRT Metadata",
        value=st.session_state.show_metadata,
        help="Show trust scores, gates, contradictions"
    )
    
    # System status
    st.markdown("---")
    st.markdown("### 🏥 System Status")
    
    if st.session_state.crt_system:
        try:
            status = st.session_state.crt_system.get_crt_status()
            st.metric("Memories", status['memory_count'])
            st.metric("Open Contradictions", status['contradiction_stats'].get('open', 0))
            
            bs_ratio = status['belief_speech_ratio'].get('ratio', 0)
            st.metric("Belief Ratio", f"{bs_ratio:.0%}")
        except:
            st.info("Stats unavailable")
    
    # Actions
    st.markdown("---")
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 Restart System"):
        st.session_state.crt_system = None
        st.session_state.messages = []
        st.cache_resource.clear()
        st.rerun()
    
    # Philosophy
    st.markdown("---")
    st.markdown("### 🧭 CRT Philosophy")
    st.info("""
    **Memory first, honesty over performance**
    
    • Coherence over time > accuracy
    • Trust evolves with evidence
    • Contradictions preserved
    • Beliefs gated, not guesses
    """)
    
    # Help
    with st.expander("❓ Help"):
        st.markdown("""
        **Getting Started:**
        1. Make sure Ollama is running: `ollama serve`
        2. Pull a model: `ollama pull llama3.2`
        3. Start chatting!
        
        **Features:**
        - ✅ Real AI responses via Ollama
        - ✅ Trust-weighted memory
        - ✅ Contradiction detection
        - ✅ Belief vs speech separation
        
        **Metadata Badges:**
        - 🟢 **BELIEF** - High trust, gates passed
        - 🟠 **SPEECH** - Fallback, gates failed
        - 🔴 **CONTRADICTION** - Conflict detected
        """)


# ============================================================================
# Main Chat Interface
# ============================================================================

# Header
st.markdown('<div class="main-header">🧠 CRT Chat</div>', unsafe_allow_html=True)
st.markdown("**Memory-First AI** • Trust-Weighted Beliefs • Contradiction Tracking")

# Initialize CRT if needed
if st.session_state.crt_system is None:
    with st.spinner(f"Initializing CRT system with {st.session_state.ollama_model}..."):
        rag, error = initialize_crt(st.session_state.ollama_model)
        
        if error:
            st.error(f"Failed to initialize: {error}")
            st.info("""
            **Ollama Setup:**
            
            1. Install Ollama: https://ollama.ai
            2. Start server: `ollama serve`
            3. Pull model: `ollama pull llama3.2`
            4. Refresh this page
            """)
            st.stop()
        else:
            st.session_state.crt_system = rag
            st.success("✅ CRT system ready!")
            time.sleep(0.5)
            st.rerun()

rag = st.session_state.crt_system

# Chat container
chat_container = st.container()

# Display messages
with chat_container:
    for msg in st.session_state.messages:
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You:</strong> {msg['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Assistant message
            badges = []
            
            # Response type badge
            if msg.get('response_type') == 'belief':
                badges.append('<span class="belief-badge">✓ BELIEF</span>')
            else:
                badges.append('<span class="speech-badge">⚠ SPEECH</span>')
            
            # Contradiction badge
            if msg.get('contradiction_detected'):
                badges.append('<span class="contradiction-badge">⚠ CONTRADICTION</span>')
            
            badges_html = ' '.join(badges)
            
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <strong>CRT:</strong> {msg['content']}
                <div style="margin-top: 0.5rem;">{badges_html}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Metadata
            if st.session_state.show_metadata and 'metadata' in msg:
                meta = msg['metadata']
                
                with st.expander("📊 CRT Metadata", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Confidence", f"{meta.get('confidence', 0):.2f}")
                        st.write(f"**Mode:** {meta.get('mode', 'N/A')}")
                    
                    with col2:
                        st.write(f"**Gates Passed:** {'✅' if meta.get('gates_passed') else '❌'}")
                        if not meta.get('gates_passed'):
                            st.write(f"*{meta.get('gate_reason', 'Unknown')}*")
                    
                    with col3:
                        if meta.get('contradiction_detected'):
                            st.write("**⚠️ Contradiction:**")
                            if 'contradiction_entry' in meta:
                                entry = meta['contradiction_entry']
                                st.write(f"Drift: {entry.get('drift_mean', 0):.3f}")
                    
                    # Retrieved memories
                    if meta.get('retrieved_memories'):
                        st.write("**🧠 Retrieved Memories:**")
                        for i, mem in enumerate(meta['retrieved_memories'][:3], 1):
                            st.write(f"{i}. [{mem['source']}] Trust: {mem['trust']:.2f} - {mem['text'][:60]}...")

# Input area
st.markdown("---")

col1, col2 = st.columns([5, 1])

with col1:
    user_input = st.chat_input("Type your message...", key="chat_input")

with col2:
    mark_important = st.checkbox("⭐ Important", help="Mark this as an important memory")

# Process input
if user_input:
    # Add user message
    st.session_state.messages.append({
        'role': 'user',
        'content': user_input
    })
    
    # Get CRT response
    with st.spinner("🤔 Thinking..."):
        try:
            result = rag.query(user_input, user_marked_important=mark_important)
            
            # Add assistant message
            st.session_state.messages.append({
                'role': 'assistant',
                'content': result['answer'],
                'response_type': result['response_type'],
                'contradiction_detected': result['contradiction_detected'],
                'metadata': {
                    'confidence': result['confidence'],
                    'mode': result['mode'],
                    'gates_passed': result['gates_passed'],
                    'gate_reason': result.get('gate_reason'),
                    'contradiction_detected': result['contradiction_detected'],
                    'contradiction_entry': result.get('contradiction_entry'),
                    'retrieved_memories': result.get('retrieved_memories', [])
                }
            })
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.messages.append({
                'role': 'assistant',
                'content': f"Sorry, I encountered an error: {e}",
                'response_type': 'error'
            })
    
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.85rem;">
    🧠 CRT Chat v1.0 | Memory-First AI with Trust-Weighted Beliefs
</div>
""", unsafe_allow_html=True)
