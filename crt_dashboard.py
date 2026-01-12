"""
CRT System Dashboard

Streamlit-based visualization for the CRT (Cognitive-Reflective Transformer) system.

Features:
1. Trust Evolution Viewer - Real-time trust trajectories
2. Contradiction Dashboard - Ledger entries and conflicts
3. Belief vs Speech Monitor - Gate statistics
4. Memory Explorer - Search and filter memories
5. CRT Health Dashboard - System metrics

Usage:
    streamlit run crt_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sqlite3
import json
import shutil
from pathlib import Path
import glob

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_memory import CRTMemorySystem, MemoryItem
from personal_agent.crt_ledger import ContradictionLedger, ContradictionEntry
from personal_agent.crt_core import MemorySource, SSEMode
from personal_agent.artifact_store import (
    now_iso_utc,
    validate_payload_against_schema,
    write_promotion_apply_result,
    write_promotion_decisions,
)
from personal_agent.promotion_apply import apply_promotions


def _find_learned_model_artifacts(base_dir: Path) -> List[Path]:
    patterns = [
        str(base_dir / "**" / "learned_suggestions*.joblib"),
    ]
    out: List[Path] = []
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            try:
                out.append(Path(p))
            except Exception:
                continue
    out = [p for p in out if p.exists() and p.is_file()]
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def _load_learned_model_meta(model_path: Path) -> Optional[Dict[str, Any]]:
    try:
        meta_path = model_path.with_suffix(".meta.json")
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_learned_model_eval(model_path: Path) -> Optional[Dict[str, Any]]:
    try:
        eval_path = model_path.with_suffix(".eval.json")
        if not eval_path.exists():
            return None
        return json.loads(eval_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def render_learned_model_tracking() -> None:
    st.header("🧠 Learned Model (Suggestions)")
    st.caption("Tracks evolution of the learned suggestion-only model (joblib + sidecar metadata).")

    artifacts_root = st.text_input("Artifacts root", value="artifacts", key="learned_model_artifacts_root")
    base_dir = Path(artifacts_root).resolve()
    if not base_dir.exists():
        st.warning(f"Artifacts directory does not exist: {base_dir}")
        return

    models = _find_learned_model_artifacts(base_dir)
    if not models:
        st.info("No learned model artifacts found yet (expected files like artifacts/learned_suggestions.*.joblib).")
        return

    selected = st.selectbox(
        "Select model artifact",
        models,
        format_func=lambda p: str(Path(p).as_posix()),
    )
    model_path = Path(selected)
    meta = _load_learned_model_meta(model_path)
    ev = _load_learned_model_eval(model_path)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Selected Model")
        st.write(f"Path: {model_path}")
        st.write(f"Modified: {datetime.fromtimestamp(model_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        if meta:
            st.json(meta)
        else:
            st.info("No sidecar metadata found for this model (expected *.meta.json). Re-train to generate it.")

        if ev:
            st.subheader("Latest Eval")
            st.json(ev.get("metrics") if isinstance(ev, dict) else ev)
        else:
            st.info("No eval artifact found for this model (expected *.eval.json). Run crt_learn_eval.py to generate it.")

    with col2:
        st.subheader("Quick Stats")
        if meta and isinstance(meta.get("examples"), dict):
            ex = meta.get("examples") or {}
            st.metric("Examples", int(ex.get("count") or 0))
            acc = ex.get("train_accuracy")
            st.metric("Train acc", f"{float(acc):.3f}" if acc is not None else "N/A")
            lc = ex.get("label_counts") or {}
            if isinstance(lc, dict) and lc:
                st.write("Label counts")
                st.json(lc)
        if ev and isinstance(ev.get("metrics"), dict):
            m = ev.get("metrics") or {}
            eacc = m.get("accuracy")
            st.metric("Eval acc", f"{float(eacc):.3f}" if eacc is not None else "N/A")
            pr = m.get("prefer_latest_rate_pred")
            st.metric("Prefer-latest rate", f"{float(pr):.1%}" if pr is not None else "N/A")

    # Timeline view from available meta files
    rows: List[Dict[str, Any]] = []
    for p in models:
        m = _load_learned_model_meta(p) or {}
        e = _load_learned_model_eval(p) or {}
        ex = m.get("examples") if isinstance(m.get("examples"), dict) else {}
        metrics = e.get("metrics") if isinstance(e.get("metrics"), dict) else {}
        rows.append(
            {
                "path": str(p.as_posix()),
                "mtime": datetime.fromtimestamp(p.stat().st_mtime),
                "examples": int((ex or {}).get("count") or 0),
                "train_accuracy": (ex or {}).get("train_accuracy"),
                "eval_accuracy": (metrics or {}).get("accuracy"),
                "prefer_latest_rate_pred": (metrics or {}).get("prefer_latest_rate_pred"),
                "sha256": (m.get("out_sha256") if isinstance(m, dict) else None),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        st.subheader("Timeline")
        df_sorted = df.sort_values("mtime")
        st.dataframe(df_sorted, use_container_width=True)
        try:
            fig = px.line(df_sorted, x="mtime", y="examples", title="Training examples over time")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

        # Eval plot (if present)
        try:
            if "eval_accuracy" in df_sorted.columns:
                df_eval = df_sorted.dropna(subset=["eval_accuracy"])
                if not df_eval.empty:
                    fig2 = px.line(df_eval, x="mtime", y="eval_accuracy", title="Eval accuracy over time")
                    st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            pass

        # Prefer-latest rate plot (if present)
        try:
            if "prefer_latest_rate_pred" in df_sorted.columns:
                df_pr = df_sorted.dropna(subset=["prefer_latest_rate_pred"])
                if not df_pr.empty:
                    fig3 = px.line(
                        df_pr,
                        x="mtime",
                        y="prefer_latest_rate_pred",
                        title="Prefer-latest prediction rate over time",
                    )
                    st.plotly_chart(fig3, use_container_width=True)
        except Exception:
            pass

    st.subheader("Compare Two Models")
    col_a, col_b = st.columns(2)
    with col_a:
        left = st.selectbox("Left", models, index=0, key="learned_model_left", format_func=lambda p: str(Path(p).as_posix()))
    with col_b:
        right = st.selectbox(
            "Right",
            models,
            index=(1 if len(models) > 1 else 0),
            key="learned_model_right",
            format_func=lambda p: str(Path(p).as_posix()),
        )

    if left and right:
        lm = _load_learned_model_meta(Path(left)) or {}
        rm = _load_learned_model_meta(Path(right)) or {}
        le = _load_learned_model_eval(Path(left)) or {}
        re = _load_learned_model_eval(Path(right)) or {}
        l_ex = lm.get("examples") if isinstance(lm.get("examples"), dict) else {}
        r_ex = rm.get("examples") if isinstance(rm.get("examples"), dict) else {}
        l_metrics = le.get("metrics") if isinstance(le.get("metrics"), dict) else {}
        r_metrics = re.get("metrics") if isinstance(re.get("metrics"), dict) else {}

        st.write("Diff (high level)")
        st.write(
            {
                "examples": {
                    "left": int((l_ex or {}).get("count") or 0),
                    "right": int((r_ex or {}).get("count") or 0),
                },
                "train_accuracy": {
                    "left": (l_ex or {}).get("train_accuracy"),
                    "right": (r_ex or {}).get("train_accuracy"),
                },
                "eval_accuracy": {
                    "left": (l_metrics or {}).get("accuracy"),
                    "right": (r_metrics or {}).get("accuracy"),
                },
                "prefer_latest_rate_pred": {
                    "left": (l_metrics or {}).get("prefer_latest_rate_pred"),
                    "right": (r_metrics or {}).get("prefer_latest_rate_pred"),
                },
                "sha256": {
                    "left": lm.get("out_sha256"),
                    "right": rm.get("out_sha256"),
                },
            }
        )

        # Per-slot accuracy diffs (from eval artifacts)
        l_by_slot = (l_metrics or {}).get("by_slot") if isinstance((l_metrics or {}).get("by_slot"), dict) else {}
        r_by_slot = (r_metrics or {}).get("by_slot") if isinstance((r_metrics or {}).get("by_slot"), dict) else {}
        if l_by_slot and r_by_slot:
            common = sorted(set(l_by_slot.keys()) & set(r_by_slot.keys()))
            slot_rows: List[Dict[str, Any]] = []
            for slot in common:
                la = (l_by_slot.get(slot) or {}).get("accuracy")
                ra = (r_by_slot.get(slot) or {}).get("accuracy")
                lc = int((l_by_slot.get(slot) or {}).get("count") or 0)
                rc = int((r_by_slot.get(slot) or {}).get("count") or 0)
                if la is None or ra is None:
                    continue
                slot_rows.append(
                    {
                        "slot": slot,
                        "left_count": lc,
                        "right_count": rc,
                        "left_acc": float(la),
                        "right_acc": float(ra),
                        "delta_acc": float(ra) - float(la),
                    }
                )
            if slot_rows:
                df_slots = pd.DataFrame(slot_rows)
                df_slots["abs_delta"] = df_slots["delta_acc"].abs()
                df_slots = df_slots.sort_values("abs_delta", ascending=False).drop(columns=["abs_delta"]).head(30)
                st.subheader("Per-slot accuracy deltas (top 30 by |Δ|)")
                st.dataframe(df_slots, use_container_width=True)
        else:
            st.info("Per-slot compare requires eval artifacts for both models.")

        # Confusion matrix compare
        l_cm = (l_metrics or {}).get("confusion_matrix")
        r_cm = (r_metrics or {}).get("confusion_matrix")
        l_labels = (l_metrics or {}).get("labels")
        r_labels = (r_metrics or {}).get("labels")
        if isinstance(l_cm, list) and isinstance(r_cm, list) and isinstance(l_labels, list) and isinstance(r_labels, list):
            if l_labels == r_labels and l_cm and r_cm:
                st.subheader("Confusion Matrix (Compare)")
                normalize = st.checkbox("Normalize rows", value=False, key="learned_model_cm_normalize")

                def _normalize_cm(cm: List[List[int]]) -> List[List[float]]:
                    out: List[List[float]] = []
                    for row in cm:
                        s = float(sum(row) or 0.0)
                        if s <= 0:
                            out.append([0.0 for _ in row])
                        else:
                            out.append([float(v) / s for v in row])
                    return out

                def _plot_cm(title: str, labels: List[str], cm_vals: Any) -> "go.Figure":
                    fig = go.Figure(
                        data=
                        [
                            go.Heatmap(
                                z=cm_vals,
                                x=labels,
                                y=labels,
                                colorscale="Blues",
                                hovertemplate="true=%{y}<br>pred=%{x}<br>value=%{z}<extra></extra>",
                            )
                        ]
                    )
                    fig.update_layout(
                        title=title,
                        xaxis_title="Predicted",
                        yaxis_title="True",
                        height=350,
                        margin=dict(l=50, r=20, t=50, b=50),
                    )
                    return fig

                l_cm_vals = _normalize_cm(l_cm) if normalize else l_cm
                r_cm_vals = _normalize_cm(r_cm) if normalize else r_cm

                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(_plot_cm("Left", l_labels, l_cm_vals), use_container_width=True)
                with c2:
                    st.plotly_chart(_plot_cm("Right", r_labels, r_cm_vals), use_container_width=True)
            else:
                st.info("Confusion-matrix compare requires both evals to have the same label set.")
        else:
            st.info("Confusion-matrix compare requires eval artifacts for both models.")


# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="CRT System Dashboard",
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
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .trust-high {
        color: #2ecc71;
        font-weight: bold;
    }
    .trust-medium {
        color: #f39c12;
        font-weight: bold;
    }
    .trust-low {
        color: #e74c3c;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Initialize CRT System
# ============================================================================

@st.cache_resource
def get_crt_system():
    """Initialize and cache CRT system."""
    memory_db = "personal_agent/crt_memory.db"
    ledger_db = "personal_agent/crt_ledger.db"
    
    # Ensure databases exist
    Path("personal_agent").mkdir(exist_ok=True)
    
    return CRTEnhancedRAG(memory_db=memory_db, ledger_db=ledger_db)


# ============================================================================
# Data Loading Functions
# ============================================================================

def load_memories(crt_system: CRTEnhancedRAG) -> List[MemoryItem]:
    """Load all memories from the system."""
    conn = sqlite3.connect(crt_system.memory.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT memory_id, vector_json, text, timestamp, confidence, trust, 
               source, sse_mode, context_json, tags_json, thread_id
        FROM memories
        ORDER BY timestamp DESC
    """)
    
    memories = []
    for row in cursor.fetchall():
        memory = MemoryItem(
            memory_id=row[0],
            vector=np.array(json.loads(row[1])),
            text=row[2],
            timestamp=row[3],
            confidence=row[4],
            trust=row[5],
            source=MemorySource(row[6]),
            sse_mode=SSEMode(row[7]),
            context=json.loads(row[8]) if row[8] else None,
            tags=json.loads(row[9]) if row[9] else None,
            thread_id=row[10]
        )
        memories.append(memory)
    
    conn.close()
    return memories


def load_trust_history(crt_system: CRTEnhancedRAG, memory_id: Optional[str] = None) -> pd.DataFrame:
    """Load trust evolution history."""
    conn = sqlite3.connect(crt_system.memory.db_path)
    
    if memory_id:
        query = "SELECT * FROM trust_log WHERE memory_id = ? ORDER BY timestamp"
        df = pd.read_sql_query(query, conn, params=(memory_id,))
    else:
        query = "SELECT * FROM trust_log ORDER BY timestamp"
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    return df


def load_contradictions(crt_system: CRTEnhancedRAG) -> List[ContradictionEntry]:
    """Load all contradictions from ledger."""
    conn = sqlite3.connect(crt_system.ledger.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, 
               drift_reason, confidence_delta, status, query, summary,
               resolution_timestamp, resolution_method, merged_memory_id
        FROM contradictions
        ORDER BY timestamp DESC
    """)
    
    contradictions = []
    for row in cursor.fetchall():
        entry = ContradictionEntry(
            ledger_id=row[0],
            timestamp=row[1],
            old_memory_id=row[2],
            new_memory_id=row[3],
            drift_mean=row[4],
            drift_reason=row[5],
            confidence_delta=row[6],
            status=row[7],
            query=row[8],
            summary=row[9],
            resolution_timestamp=row[10],
            resolution_method=row[11],
            merged_memory_id=row[12]
        )
        contradictions.append(entry)
    
    conn.close()
    return contradictions


def load_belief_speech_stats(crt_system: CRTEnhancedRAG) -> pd.DataFrame:
    """Load belief vs speech statistics."""
    conn = sqlite3.connect(crt_system.memory.db_path)
    df = pd.read_sql_query("SELECT * FROM belief_speech ORDER BY timestamp DESC", conn)
    conn.close()
    
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    return df


def load_reflection_queue(crt_system: CRTEnhancedRAG) -> pd.DataFrame:
    """Load pending reflections."""
    conn = sqlite3.connect(crt_system.ledger.db_path)
    df = pd.read_sql_query("""
        SELECT * FROM reflection_queue 
        WHERE processed = 0 
        ORDER BY timestamp DESC
    """, conn)
    conn.close()
    
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    return df


# ============================================================================
# Trust Evolution Viewer
# ============================================================================

def render_trust_evolution(crt_system: CRTEnhancedRAG):
    """Render trust evolution visualization."""
    st.header("📈 Trust Evolution Viewer")
    
    memories = load_memories(crt_system)
    
    if not memories:
        st.info("No memories found. Add some memories to see trust evolution.")
        return
    
    # Trust distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Current Trust Distribution")
        trust_scores = [m.trust for m in memories]
        
        fig = go.Figure(data=[go.Histogram(
            x=trust_scores,
            nbinsx=20,
            marker_color='#1f77b4'
        )])
        fig.update_layout(
            xaxis_title="Trust Score",
            yaxis_title="Count",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Trust Statistics")
        st.metric("Average Trust", f"{np.mean(trust_scores):.3f}")
        st.metric("Median Trust", f"{np.median(trust_scores):.3f}")
        st.metric("High Trust (>0.7)", sum(1 for t in trust_scores if t > 0.7))
        st.metric("Low Trust (<0.3)", sum(1 for t in trust_scores if t < 0.3))
    
    # Trust evolution over time
    st.subheader("Trust Evolution Over Time")
    
    trust_history = load_trust_history(crt_system)
    
    if not trust_history.empty:
        # Select specific memories to track
        memory_ids = trust_history['memory_id'].unique()
        
        if len(memory_ids) > 10:
            st.info(f"Showing trust evolution for up to 10 most recent memories (total: {len(memory_ids)})")
            selected_ids = memory_ids[:10]
        else:
            selected_ids = memory_ids
        
        fig = go.Figure()
        
        for mem_id in selected_ids:
            mem_data = trust_history[trust_history['memory_id'] == mem_id]
            fig.add_trace(go.Scatter(
                x=mem_data['datetime'],
                y=mem_data['new_trust'],
                mode='lines+markers',
                name=f"...{mem_id[-8:]}",
                hovertemplate=f"<b>Memory {mem_id[-8:]}</b><br>" +
                              "Time: %{x}<br>" +
                              "Trust: %{y:.3f}<br>" +
                              "<extra></extra>"
            ))
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Trust Score",
            yaxis_range=[0, 1],
            height=400,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trust history available yet. Memories will evolve as you interact with the system.")


# ============================================================================
# Contradiction Dashboard
# ============================================================================

def render_contradiction_dashboard(crt_system: CRTEnhancedRAG):
    """Render contradiction dashboard."""
    st.header("⚠️ Contradiction Dashboard")
    
    contradictions = load_contradictions(crt_system)
    
    if not contradictions:
        st.success("No contradictions detected yet!")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(contradictions)
    resolved = sum(1 for c in contradictions if c.status == "resolved")
    open_count = total - resolved
    avg_drift = np.mean([c.drift_mean for c in contradictions]) if contradictions else 0
    
    with col1:
        st.metric("Total Contradictions", total)
    with col2:
        st.metric("Open", open_count, delta=f"-{resolved} resolved")
    with col3:
        st.metric("Resolved", resolved)
    with col4:
        st.metric("Avg Drift Score", f"{avg_drift:.3f}")
    
    # Contradiction timeline
    st.subheader("Contradiction Timeline")
    
    df_contradictions = pd.DataFrame([{
        'id': c.ledger_id[-8:],
        'drift': c.drift_mean,
        'timestamp': datetime.fromtimestamp(c.timestamp),
        'status': 'Resolved' if c.status == 'resolved' else 'Open',
        'old_memory': c.old_memory_id[-8:],
        'new_memory': c.new_memory_id[-8:]
    } for c in contradictions])
    
    fig = px.scatter(
        df_contradictions,
        x='timestamp',
        y='drift',
        color='status',
        size=[10] * len(df_contradictions),
        hover_data=['id', 'old_memory', 'new_memory'],
        color_discrete_map={'Open': '#e74c3c', 'Resolved': '#2ecc71'}
    )
    fig.update_layout(
        xaxis_title="Detection Time",
        yaxis_title="Drift Score",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Contradiction list
    st.subheader("Recent Contradictions")
    
    show_resolved = st.checkbox("Show resolved contradictions", value=False)
    
    display_contradictions = contradictions if show_resolved else [c for c in contradictions if c.status != "resolved"]
    
    for c in display_contradictions[:10]:
        status_color = "🟢" if c.status == "resolved" else "🔴"
        
        with st.expander(f"{status_color} {c.ledger_id[-12:]} - Drift: {c.drift_mean:.3f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Old Memory:**", c.old_memory_id[-12:])
                st.write("**New Memory:**", c.new_memory_id[-12:])
            
            with col2:
                st.write("**Detected:**", datetime.fromtimestamp(c.timestamp).strftime("%Y-%m-%d %H:%M"))
                if c.status == "resolved" and c.resolution_timestamp:
                    st.write("**Resolved:**", datetime.fromtimestamp(c.resolution_timestamp).strftime("%Y-%m-%d %H:%M"))
                    st.write("**Method:**", c.resolution_method or "N/A")
            
            if c.summary:
                st.write("**Summary:**", c.summary)
            if c.query:
                st.write("**Query:**", c.query)


# ============================================================================
# Belief vs Speech Monitor
# ============================================================================

def render_belief_speech_monitor(crt_system: CRTEnhancedRAG):
    """Render belief vs speech monitoring."""
    st.header("💭 Belief vs Speech Monitor")
    
    stats = load_belief_speech_stats(crt_system)
    
    if stats.empty:
        st.info("No belief/speech data yet. Interact with the system to see statistics.")
        return
    
    # Summary metrics
    total_queries = len(stats)
    beliefs = stats['is_belief'].sum()
    speeches = total_queries - beliefs
    belief_ratio = beliefs / total_queries if total_queries > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Queries", total_queries)
    with col2:
        st.metric("Beliefs", beliefs, help="Passed intent + memory gates")
    with col3:
        st.metric("Speeches", speeches, help="Fallback responses")
    with col4:
        st.metric("Belief Ratio", f"{belief_ratio:.1%}")
    
    # Pie chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Belief vs Speech Distribution")
        
        fig = go.Figure(data=[go.Pie(
            labels=['Beliefs', 'Speeches'],
            values=[beliefs, speeches],
            marker_colors=['#2ecc71', '#e74c3c'],
            hole=0.4
        )])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Statistics")
        
        st.write(f"**Entries recorded:** {total_queries}")
        st.write(f"**Belief sources:** {len(stats[stats['is_belief'] == 1])}")
        st.write(f"**Speech sources:** {len(stats[stats['is_belief'] == 0])}")
        
        if beliefs > 0:
            avg_trust_beliefs = stats[stats['is_belief'] == 1]['trust_avg'].mean()
            st.metric("Avg Trust (Beliefs)", f"{avg_trust_beliefs:.3f}" if not pd.isna(avg_trust_beliefs) else "N/A")
    
    # Timeline
    st.subheader("Belief vs Speech Over Time")
    
    if len(stats) > 1:
        fig = go.Figure()
        
        # Cumulative belief ratio
        cumulative_beliefs = stats['is_belief'].cumsum()
        cumulative_total = range(1, len(stats) + 1)
        cumulative_ratio = [b / t for b, t in zip(cumulative_beliefs, cumulative_total)]
        
        fig.add_trace(go.Scatter(
            x=stats['datetime'],
            y=cumulative_ratio,
            mode='lines',
            name='Cumulative Belief Ratio',
            line=dict(color='#3498db', width=2)
        ))
        
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray",
                     annotation_text="50% Belief Ratio")
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Belief Ratio",
            yaxis_range=[0, 1],
            height=400,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# Memory Explorer
# ============================================================================

def render_memory_explorer(crt_system: CRTEnhancedRAG):
    """Render memory exploration interface."""
    st.header("🔍 Memory Explorer")
    
    memories = load_memories(crt_system)
    
    if not memories:
        st.info("No memories found. Add some memories to explore.")
        return
    
    # Search and filter
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_query = st.text_input("Search memories", placeholder="Enter search text...")
    
    with col2:
        source_filter = st.multiselect(
            "Source",
            options=[s.value for s in MemorySource],
            default=[]
        )
    
    with col3:
        min_trust = st.slider("Min Trust", 0.0, 1.0, 0.0, 0.1)
    
    # Filter memories
    filtered_memories = memories
    
    if search_query:
        filtered_memories = [m for m in filtered_memories if search_query.lower() in m.text.lower()]
    
    if source_filter:
        filtered_memories = [m for m in filtered_memories if m.source.value in source_filter]
    
    filtered_memories = [m for m in filtered_memories if m.trust >= min_trust]
    
    # Display count
    st.write(f"**Showing {len(filtered_memories)} of {len(memories)} memories**")
    
    # Sort options
    sort_by = st.selectbox("Sort by", ["Timestamp (newest)", "Timestamp (oldest)", "Trust (high)", "Trust (low)", "Confidence"])
    
    if sort_by == "Timestamp (newest)":
        filtered_memories.sort(key=lambda m: m.timestamp, reverse=True)
    elif sort_by == "Timestamp (oldest)":
        filtered_memories.sort(key=lambda m: m.timestamp)
    elif sort_by == "Trust (high)":
        filtered_memories.sort(key=lambda m: m.trust, reverse=True)
    elif sort_by == "Trust (low)":
        filtered_memories.sort(key=lambda m: m.trust)
    elif sort_by == "Confidence":
        filtered_memories.sort(key=lambda m: m.confidence, reverse=True)
    
    # Display memories
    for memory in filtered_memories[:50]:  # Limit to 50 for performance
        trust_class = "trust-high" if memory.trust > 0.7 else ("trust-medium" if memory.trust > 0.4 else "trust-low")
        
        with st.expander(f"{memory.text[:100]}..." if len(memory.text) > 100 else memory.text):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Trust:** <span class='{trust_class}'>{memory.trust:.3f}</span>", unsafe_allow_html=True)
                st.write(f"**Confidence:** {memory.confidence:.3f}")
            
            with col2:
                st.write(f"**Source:** {memory.source.value}")
                st.write(f"**SSE Mode:** {memory.sse_mode.value}")
            
            with col3:
                timestamp_str = datetime.fromtimestamp(memory.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                st.write(f"**Created:** {timestamp_str}")
                st.write(f"**ID:** ...{memory.memory_id[-12:]}")
            
            st.write(f"**Full Text:** {memory.text}")
            
            if memory.tags:
                st.write(f"**Tags:** {', '.join(memory.tags)}")
            
            # Show trust history for this memory
            if st.checkbox(f"Show trust history", key=f"trust_{memory.memory_id}"):
                trust_hist = load_trust_history(crt_system, memory.memory_id)
                if not trust_hist.empty:
                    st.dataframe(trust_hist[['datetime', 'old_trust', 'new_trust', 'reason']], use_container_width=True)


# ============================================================================
# CRT Health Dashboard
# ============================================================================

def render_health_dashboard(crt_system: CRTEnhancedRAG):
    """Render system health overview."""
    st.header("🏥 CRT System Health")
    
    memories = load_memories(crt_system)
    contradictions = load_contradictions(crt_system)
    reflections = load_reflection_queue(crt_system)
    
    # System metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Memories", len(memories))
    
    with col2:
        open_contradictions = sum(1 for c in contradictions if c.status != "resolved")
        st.metric("Open Contradictions", open_contradictions)
    
    with col3:
        st.metric("Pending Reflections", len(reflections))
    
    with col4:
        if memories:
            avg_trust = np.mean([m.trust for m in memories])
            st.metric("Avg Trust", f"{avg_trust:.3f}")
        else:
            st.metric("Avg Trust", "N/A")
    
    # Volatility score
    st.subheader("System Volatility")
    
    if memories and contradictions:
        # Calculate volatility as ratio of open contradictions to total memories
        volatility = open_contradictions / len(memories) if len(memories) > 0 else 0
        
        volatility_color = "#2ecc71" if volatility < 0.1 else ("#f39c12" if volatility < 0.3 else "#e74c3c")
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=volatility * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Volatility Score (%)"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': volatility_color},
                'steps': [
                    {'range': [0, 10], 'color': "#d5f4e6"},
                    {'range': [10, 30], 'color': "#fef5e7"},
                    {'range': [30, 100], 'color': "#fadbd8"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 30
                }
            }
        ))
        
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        if volatility > 0.3:
            st.warning("⚠️ High volatility detected! Consider triggering reflections to resolve contradictions.")
        elif volatility > 0.1:
            st.info("ℹ️ Moderate volatility. System is adapting to new information.")
        else:
            st.success("✅ Low volatility. System is stable.")
    
    # Memory coherence
    st.subheader("Memory Coherence")
    
    if memories:
        # Calculate coherence as average trust of memories
        coherence = np.mean([m.trust for m in memories])
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=coherence,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Coherence Score"},
                gauge={
                    'axis': {'range': [0, 1]},
                    'bar': {'color': "#3498db"},
                    'steps': [
                        {'range': [0, 0.3], 'color': "#fadbd8"},
                        {'range': [0.3, 0.7], 'color': "#fef5e7"},
                        {'range': [0.7, 1], 'color': "#d5f4e6"}
                    ]
                }
            ))
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Source distribution
            source_counts = {}
            for m in memories:
                source_counts[m.source.value] = source_counts.get(m.source.value, 0) + 1
            
            fig = go.Figure(data=[go.Bar(
                x=list(source_counts.keys()),
                y=list(source_counts.values()),
                marker_color='#3498db'
            )])
            fig.update_layout(
                title="Memory Sources",
                xaxis_title="Source",
                yaxis_title="Count",
                height=250
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent activity
    st.subheader("Recent Activity")
    
    if memories:
        recent_memories = sorted(memories, key=lambda m: m.timestamp, reverse=True)[:5]
        
        st.write("**Latest Memories:**")
        for m in recent_memories:
            time_str = datetime.fromtimestamp(m.timestamp).strftime("%Y-%m-%d %H:%M")
            st.write(f"- [{time_str}] {m.text[:80]}..." if len(m.text) > 80 else f"- [{time_str}] {m.text}")


# ============================================================================
# Promotion Approvals
# ============================================================================


def _find_proposal_artifacts(base_dir: Path) -> List[Path]:
    patterns = [
        str(base_dir / "**" / "promotions" / "proposals.*.json"),
    ]
    out: List[Path] = []
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            try:
                out.append(Path(p))
            except Exception:
                continue
    # Newest first by mtime.
    out = [p for p in out if p.exists() and p.is_file()]
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def _find_decisions_artifacts(base_dir: Path) -> List[Path]:
    patterns = [
        str(base_dir / "**" / "approvals" / "decisions.*.json"),
    ]
    out: List[Path] = []
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            try:
                out.append(Path(p))
            except Exception:
                continue
    out = [p for p in out if p.exists() and p.is_file()]
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def _render_apply_results(results: List[Dict[str, Any]]) -> None:
    if not results:
        st.info("No results to display.")
        return
    applied = sum(1 for r in results if r.get("action") == "applied")
    skipped = sum(1 for r in results if r.get("action") == "skipped")
    errors = sum(1 for r in results if r.get("action") == "error")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Applied", applied)
    with col2:
        st.metric("Skipped", skipped)
    with col3:
        st.metric("Errors", errors)
    st.dataframe(pd.DataFrame(results), use_container_width=True)


def render_promotion_approvals() -> None:
    st.header("✅ Promotion Approvals")
    st.caption("Review promotion proposals artifacts and record approve/reject decisions (does not change memories yet).")

    artifacts_root = st.text_input("Artifacts root", value="artifacts")
    base_dir = Path(artifacts_root).resolve()
    if not base_dir.exists():
        st.warning(f"Artifacts directory does not exist: {base_dir}")
        return

    proposal_files = _find_proposal_artifacts(base_dir)
    if not proposal_files:
        st.info("No proposals found yet. Run propose_promotions to generate artifacts under an artifacts directory.")
        return

    selected = st.selectbox(
        "Select proposals artifact",
        proposal_files,
        format_func=lambda p: str(Path(p).as_posix()),
    )
    proposals_path = Path(selected)

    try:
        proposals_payload = json.loads(proposals_path.read_text(encoding="utf-8"))
        validate_payload_against_schema(proposals_payload, "crt_promotion_proposals.v1.schema.json")
    except Exception as e:
        st.error(f"Failed to load/validate proposals: {e}")
        return

    metadata = proposals_payload.get("metadata") or {}
    proposals = proposals_payload.get("proposals") or []

    st.subheader("Artifact Metadata")
    st.json(metadata)
    st.write(f"Proposals: {len(proposals)}")

    st.subheader("Proposals")
    if proposals:
        rows = []
        for p in proposals:
            mem = p.get("memory") or {}
            rows.append(
                {
                    "proposal_id": p.get("id"),
                    "status": p.get("status"),
                    "kind": mem.get("kind"),
                    "key": mem.get("key"),
                    "value_text": (mem.get("value_text") or "")[:120],
                    "trust": mem.get("trust"),
                    "confidence": mem.get("confidence"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.subheader("Decisions")
    decisions: List[Dict[str, Any]] = []

    for idx, p in enumerate(proposals):
        proposal_id = str(p.get("id") or f"proposal-{idx}")
        mem = p.get("memory") or {}
        default_key = f"decision__{proposal_id}"
        reason_key = f"reason__{proposal_id}"
        if default_key not in st.session_state:
            st.session_state[default_key] = "defer"
        if reason_key not in st.session_state:
            st.session_state[reason_key] = ""

        with st.expander(f"{proposal_id} → {mem.get('key')} = {mem.get('value_text')}", expanded=False):
            st.json(p)
            st.radio(
                "Decision",
                options=["defer", "approved", "rejected"],
                key=default_key,
                horizontal=True,
            )
            st.text_input("Reason (optional)", key=reason_key)

        decisions.append(
            {
                "proposal_id": proposal_id,
                "decision": st.session_state[default_key],
                "decided_at": now_iso_utc(),
                "reason": (st.session_state[reason_key] or None),
            }
        )

    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        if st.button("Save decisions artifact", type="primary"):
            source_job_id = metadata.get("source_job_id")
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_dir = base_dir / "approvals"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"decisions.{source_job_id or 'unknown'}.{ts}.json"

            payload = {
                "metadata": {
                    "version": "v1",
                    "generated_at": now_iso_utc(),
                    "source_proposals_path": str(proposals_path),
                    "source_job_id": source_job_id,
                    "notes": None,
                },
                "decisions": decisions,
            }

            try:
                write_promotion_decisions(out_path, payload)
                st.session_state["last_written_decisions_path"] = str(out_path)
                st.success(f"Wrote decisions: {out_path}")
            except Exception as e:
                st.error(f"Failed to write decisions: {e}")

    with save_col2:
        st.caption("This records your decision as an artifact. Next milestone is applying approved items into a controlled memory lane with audit trail.")

    st.markdown("---")
    st.subheader("Apply (Dry-run / Sandbox / Real)")
    st.caption(
        "Dry-run shows what would be written; sandbox apply is recommended first. "
        "Real apply writes to the selected DB and is gated behind an explicit confirmation."
    )

    decisions_files = _find_decisions_artifacts(base_dir)
    default_decisions: Optional[Path] = None
    last_written = st.session_state.get("last_written_decisions_path")
    if last_written:
        try:
            p = Path(str(last_written))
            if p.exists() and p.is_file():
                default_decisions = p
        except Exception:
            default_decisions = None
    if default_decisions is None and decisions_files:
        default_decisions = decisions_files[0]

    if not default_decisions:
        st.info("No decisions artifact found yet. Save decisions above to enable apply actions.")
        return

    selected_decisions = st.selectbox(
        "Select decisions artifact",
        decisions_files or [default_decisions],
        index=(0 if not decisions_files else max(0, (decisions_files.index(default_decisions) if default_decisions in decisions_files else 0))),
        format_func=lambda p: str(Path(p).as_posix()),
    )
    decisions_path = Path(selected_decisions)

    # Choose memory DB defaults conservatively.
    proposals_meta = proposals_payload.get("metadata") or {}
    default_memory_db = str(proposals_meta.get("memory_db") or "artifacts/crt_live_memory.db")
    memory_db = st.text_input("Target memory DB (real)", value=default_memory_db)

    sandbox_db_default = str((base_dir / "sandboxes" / f"sandbox_{Path(memory_db).stem}.db").as_posix())
    sandbox_db = st.text_input("Sandbox memory DB", value=sandbox_db_default)

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        if st.button("Create/refresh sandbox DB"):
            try:
                src = Path(memory_db)
                dst = Path(sandbox_db)
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not src.exists() or not src.is_file():
                    raise FileNotFoundError(f"Target DB not found: {src}")
                shutil.copy2(src, dst)
                st.success(f"Sandbox ready: {dst}")
            except Exception as e:
                st.error(f"Failed to create sandbox: {e}")

    with col_b:
        if st.button("Dry-run apply (target DB)"):
            try:
                apply_payload, results = apply_promotions(
                    memory_db=str(memory_db),
                    proposals_path=proposals_path,
                    decisions_path=decisions_path,
                    dry_run=True,
                )
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                source_job_id = metadata.get("source_job_id") or "unknown"
                out_dir = base_dir / "apply_results"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"apply_result.{source_job_id}.{ts}.dry_run.json"
                write_promotion_apply_result(out_path, apply_payload)
                st.success(f"Dry-run complete. Wrote apply-result: {out_path}")
                _render_apply_results(results)
            except Exception as e:
                st.error(f"Dry-run failed: {e}")

    with col_c:
        st.caption("Sandbox apply is the recommended next step after saving decisions.")

    if st.button("Apply to sandbox DB", type="primary"):
        try:
            sb = Path(sandbox_db)
            if not sb.exists() or not sb.is_file():
                raise FileNotFoundError("Sandbox DB not found. Click 'Create/refresh sandbox DB' first.")
            apply_payload, results = apply_promotions(
                memory_db=str(sb),
                proposals_path=proposals_path,
                decisions_path=decisions_path,
                dry_run=False,
            )
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            source_job_id = metadata.get("source_job_id") or "unknown"
            out_dir = base_dir / "apply_results"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"apply_result.{source_job_id}.{ts}.sandbox.json"
            write_promotion_apply_result(out_path, apply_payload)
            st.success(f"Applied to sandbox. Wrote apply-result: {out_path}")
            _render_apply_results(results)
        except Exception as e:
            st.error(f"Sandbox apply failed: {e}")

    with st.expander("Danger zone: Apply to real DB", expanded=False):
        st.warning("This writes to the target DB. Prefer sandbox-first.")
        confirm = st.checkbox("I understand this will write to the target DB", value=False)
        typed = st.text_input("Type APPLY to confirm", value="")
        if st.button("Apply to target DB", disabled=not (confirm and typed.strip().upper() == "APPLY")):
            try:
                apply_payload, results = apply_promotions(
                    memory_db=str(memory_db),
                    proposals_path=proposals_path,
                    decisions_path=decisions_path,
                    dry_run=False,
                )
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                source_job_id = metadata.get("source_job_id") or "unknown"
                out_dir = base_dir / "apply_results"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"apply_result.{source_job_id}.{ts}.real.json"
                write_promotion_apply_result(out_path, apply_payload)
                st.success(f"Applied to target DB. Wrote apply-result: {out_path}")
                _render_apply_results(results)
            except Exception as e:
                st.error(f"Real apply failed: {e}")


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main dashboard application."""
    
    # Sidebar navigation
    st.sidebar.markdown("# 🧠 CRT Dashboard")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        [
            "🏥 System Health",
            "📈 Trust Evolution",
            "⚠️ Contradictions",
            "💭 Belief vs Speech",
            "🔍 Memory Explorer",
            "✅ Promotion Approvals",
            "🧠 Learned Model"
        ]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About CRT")
    st.sidebar.info("""
    **Cognitive-Reflective Transformer**
    
    Philosophy:
    - Memory first, honesty over performance
    - Coherence over time > single-query accuracy
    - Trust evolves slowly with evidence
    - Contradictions preserved, not overwritten
    """)
    
    # Initialize system
    try:
        crt_system = get_crt_system()
    except Exception as e:
        st.error(f"Failed to initialize CRT system: {e}")
        st.stop()
    
    # Main content
    st.markdown('<div class="main-header">CRT System Dashboard</div>', unsafe_allow_html=True)
    st.markdown("**Cognitive-Reflective Transformer** - Memory-first AI with trust-weighted beliefs")
    st.markdown("---")
    
    # Route to selected page
    if page == "🏥 System Health":
        render_health_dashboard(crt_system)
    elif page == "📈 Trust Evolution":
        render_trust_evolution(crt_system)
    elif page == "⚠️ Contradictions":
        render_contradiction_dashboard(crt_system)
    elif page == "💭 Belief vs Speech":
        render_belief_speech_monitor(crt_system)
    elif page == "🔍 Memory Explorer":
        render_memory_explorer(crt_system)
    elif page == "✅ Promotion Approvals":
        render_promotion_approvals()
    elif page == "🧠 Learned Model":
        render_learned_model_tracking()
    
    # Footer
    st.markdown("---")
    st.markdown(f"*CRT Dashboard v1.0 | Session: {crt_system.session_id}*")


if __name__ == "__main__":
    main()
