"""Unified Streamlit app for CRT.

Run:
    streamlit run crt_app.py

This launches a single Streamlit server with pages for:
- Chat (crt_chat_gui.py)
- Dashboard (crt_dashboard.py)

We intentionally keep the existing pages intact and execute them via runpy,
so they can still be launched standalone.
"""

from __future__ import annotations

import streamlit as st


st.set_page_config(
    page_title="CRT",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("# 🧠 CRT")
st.caption("Unified app: Chat + Dashboard (single Streamlit server).")

st.info(
    "Use the sidebar page selector to open **Chat** or **Dashboard**. "
    "If you previously ran `crt_chat_gui.py` and `crt_dashboard.py` on separate ports, "
    "this replaces that with one app."
)

with st.expander("Quick start", expanded=True):
    st.markdown(
        """
- Start Ollama: `ollama serve`
- Pull a model (example): `ollama pull llama3.2`
- Launch CRT: `streamlit run crt_app.py`

Tips:
- Chat DB paths can be edited in the Chat sidebar.
- Dashboard tools use their own controls inside the Dashboard page.
"""
    )

st.markdown("---")
st.markdown(
    "If you want to run pages standalone, you still can: `streamlit run crt_chat_gui.py` or `streamlit run crt_dashboard.py`."
)
