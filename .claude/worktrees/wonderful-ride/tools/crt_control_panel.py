"""CRT Control Panel (local-first)

A Streamlit app that complements `crt_dashboard.py` by adding:
- onboarding UI
- policy/config toggles
- safe editing of `crt_runtime_config.json`

Run:
    streamlit run crt_control_plane.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.runtime_config import get_runtime_config, load_runtime_config
from personal_agent.onboarding import get_onboarding_questions, store_onboarding_answer


PROJECT_ROOT = Path(__file__).resolve().parent


def _default_config_path() -> Path:
    # Mirrors runtime_config.py behavior: repo-root crt_runtime_config.json.
    return (PROJECT_ROOT / "crt_runtime_config.json").resolve()


def _load_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config_file(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@st.cache_resource
def _get_crt() -> CRTEnhancedRAG:
    return CRTEnhancedRAG(memory_db="personal_agent/crt_memory.db", ledger_db="personal_agent/crt_ledger.db")


def _section_toggle(cfg: Dict[str, Any], section: str, label: str, default: bool = True) -> bool:
    sec = cfg.get(section)
    current = default
    if isinstance(sec, dict) and "enabled" in sec:
        current = bool(sec.get("enabled"))
    return st.toggle(label, value=current, key=f"toggle_{section}")


def render_home(crt: CRTEnhancedRAG) -> None:
    st.title("CRT Control Panel")
    st.caption("Local-first control system for a truthful personal AI.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Memories", crt.memory.get_memory_count())
    with col2:
        st.metric("Open contradictions", crt.ledger.get_unresolved_count())
    with col3:
        st.metric("Runtime config", "crt_runtime_config.json")

    st.markdown("### What this UI is for")
    st.write(
        "Use this to configure CRT safely, onboard user facts/preferences, and keep an audit-friendly separation "
        "between stable personal facts and low-trust research notes."
    )


def render_onboarding(crt: CRTEnhancedRAG) -> None:
    st.header("Onboarding")

    runtime_cfg = get_runtime_config()
    questions = get_onboarding_questions(runtime_cfg)

    if not questions:
        st.info("No onboarding questions configured. Edit crt_runtime_config.json to enable.")
        return

    st.write("These answers are stored as `FACT:` / `PREF:` entries with high confidence.")

    with st.form("onboarding_form"):
        answers: Dict[str, str] = {}
        for q in questions:
            slot = q["slot"]
            kind = q["kind"]
            prompt = q["prompt"]
            answers[slot] = st.text_input(f"{prompt}", value="", key=f"ob_{slot}")

        submitted = st.form_submit_button("Save onboarding answers")

    if submitted:
        stored = 0
        for q in questions:
            slot = q["slot"]
            kind = q["kind"]
            val = (answers.get(slot) or "").strip()
            if not val:
                continue
            store_onboarding_answer(crt, slot=slot, value=val, kind=kind, important=True)
            stored += 1

        if stored:
            st.success(f"Saved {stored} item(s) to memory.")
        else:
            st.info("Nothing to store (all blank).")


def render_policies() -> None:
    st.header("Policies & Runtime Config")

    config_path = _default_config_path()
    file_obj = _load_config_file(config_path)

    st.caption(f"Editing: {config_path}")

    st.subheader("Common toggles")
    # Read effective runtime config (defaults merged) so toggles reflect reality.
    effective = load_runtime_config(str(config_path))

    proven_enabled = _section_toggle(effective, "provenance", "Provenance footer enabled")
    world_check_enabled = bool(((effective.get("provenance") or {}).get("world_check") or {}).get("enabled", False))
    world_check_enabled = st.toggle("Provenance world_check enabled", value=world_check_enabled, key="toggle_world_check")

    assistant_profile_enabled = _section_toggle(effective, "assistant_profile", "assistant_profile gate enabled")
    user_named_ref_enabled = _section_toggle(effective, "user_named_reference", "user_named_reference gate enabled")
    conflict_warning_enabled = _section_toggle(effective, "conflict_warning", "conflict_warning enabled")
    onboarding_enabled = _section_toggle(effective, "onboarding", "onboarding enabled")

    if st.button("Save toggles to crt_runtime_config.json"):
        # Update file_obj minimally; keep unrelated keys.
        file_obj.setdefault("provenance", {}).update({"enabled": proven_enabled})
        file_obj.setdefault("provenance", {}).setdefault("world_check", {}).update({"enabled": world_check_enabled})
        file_obj.setdefault("assistant_profile", {}).update({"enabled": assistant_profile_enabled})
        file_obj.setdefault("user_named_reference", {}).update({"enabled": user_named_ref_enabled})
        file_obj.setdefault("conflict_warning", {}).update({"enabled": conflict_warning_enabled})
        file_obj.setdefault("onboarding", {}).update({"enabled": onboarding_enabled})
        _save_config_file(config_path, file_obj)
        st.success("Saved.")

    st.subheader("Raw JSON")
    raw = config_path.read_text(encoding="utf-8") if config_path.exists() else "{}\n"
    edited = st.text_area("crt_runtime_config.json", value=raw, height=360)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Validate JSON"):
            try:
                json.loads(edited)
                st.success("Valid JSON.")
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    with col_b:
        if st.button("Save raw JSON"):
            try:
                obj = json.loads(edited)
                _save_config_file(config_path, obj)
                st.success("Saved raw JSON.")
            except Exception as e:
                st.error(f"Save failed: {e}")


def render_integrations() -> None:
    st.header("Integrations")
    st.markdown("### Browser bridge")
    st.write(
        "A local-only Tampermonkey + WebSocket bridge is available for read-only research workflows. "
        "See BROWSER_BRIDGE_README.md."
    )


def main() -> None:
    st.set_page_config(page_title="CRT Control Panel", layout="wide")

    crt = _get_crt()

    page = st.sidebar.radio(
        "Navigate",
        ["Home", "Onboarding", "Policies", "Integrations"],
        index=0,
    )

    if page == "Home":
        render_home(crt)
    elif page == "Onboarding":
        render_onboarding(crt)
    elif page == "Policies":
        render_policies()
    elif page == "Integrations":
        render_integrations()


if __name__ == "__main__":
    main()
