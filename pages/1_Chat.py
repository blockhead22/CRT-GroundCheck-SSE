"""CRT Chat (multipage wrapper).

This page runs the existing `crt_chat_gui.py` inside the Streamlit multipage app.
"""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "crt_chat_gui.py"), run_name="__main__")
