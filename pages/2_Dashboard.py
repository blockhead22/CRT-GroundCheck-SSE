"""CRT Dashboard (multipage wrapper).

This page runs the existing `crt_dashboard.py` inside the Streamlit multipage app.
"""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "crt_dashboard.py"), run_name="__main__")
