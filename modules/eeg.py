"""modules/eeg.py — Live EEG Assessment"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime
import serial_reader as sr
from database import get_eeg_signals, get_eeg_sessions

REFRESH = 3   # seconds between auto-refresh


def _tbr_interpretation(tbr: float) -> tuple:
    """Return (label, color, description) for Theta/Beta Ratio."""
    if tbr < 1.5:
        return "Normal",    "#2e7d32", "Theta/Beta ratio is within normal range."
    elif tbr < 2.5:
        return "Elevated",  "#f57f17", "Slightly elevated ratio — mild inattention possible."
    elif tbr < 3.5:
        return "High",      "#e65100", "High ratio — moderate ADHD tendency suggested."
    else:
        return "Very High", "#c62828", "Very high ratio — strong ADHD indicator (TBR ≥ 3.5)."


def _attention_label(val: int) -> tuple:
    if val >= 70:  return "High Focus",   "#2e7d32"
    if val >= 40:  return "Moderate",     "#f57f17"
    return                "Low Attention", "#c62828"


def _draw_charts(df: pd.DataFrame):
    """Render 4-panel brainwave chart + individual metric charts."""
    if df.empty:
        return

    # ── Combined brainwave chart ──────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Attention & Meditation", "Theta / Beta Ratio",
                        "Delta & Theta Waves",    "Alpha Waves"),
        vertical_spacing=0.14, horizontal_spacing=0.1,
    )

    x = df["recorded_at"]

    fig.add_trace(go.Scatter(x=x, y=df["attention"],  name="Attention",
                             line=dict(color="#1565c0", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["meditation"], name="Meditation",
                             line=dict(color="#00897b", width=2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=df["theta_beta_ratio"], name="TBR",
                             line=dict(color="#c62828", width=2)), row=1, col=2)
    fig.add_hline(y=2.89, line_dash="dash", line_color="#f57f17",
                  annotation_text="ADHD Threshold (2.89)", row=1, col=2)

    fig.add_trace(go.Scatter(x=x, y=df["delta"], name="Delta",
                             line=dict(color="#4527a0", width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["theta"], name="Theta",
                             line=dict(color="#7b1fa2", width=1.5)), row=2, col=1)

    fig.add_trace(go.Scatter(x=x, y=df["low_alpha"],  name="Low α",
                             line=dict(color="#0288d1", width=1.5)), row=2, col=2)
    fig.add_trace(go.Scatter(x=x, y=df["high_alpha"], name="High α",
                             line=dict(color="#26c6da", width=1.5)), row=2, col=2)

    fig.update_layout(
        height=420, paper_bgcolor="white", plot_bgcolor="#f8fafc",
        font=dict(family="Inter", size=11),
        legend=dict(bgcolor="white", bordercolor="#e2e8f0", borderwidth=1),
        margin=dict(t=50, b=20, l=40, r=20),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e2e8f0")
    st.plotly_chart(fig, use_container_width=True, key="eeg_main_chart")

    # ── Beta & Gamma row ──────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        fb = go.Figure()
        fb.add_trace(go.Scatter(x=x, y=df["low_beta"],  name="Low β",  line=dict(color="#e65100", width=2)))
        fb.add_trace(go.Scatter(x=x, y=df["high_beta"], name="High β", line=dict(color="#ff8f00", width=2)))
        fb.update_layout(title="Beta Waves", height=220, paper_bgcolor="white",
                         plot_bgcolor="#f8fafc", font=dict(family="Inter", size=11),
                         margin=dict(t=35, b=20, l=40, r=10))
        fb.update_xaxes(showgrid=False)
        st.plotly_chart(fb, use_container_width=True, key="eeg_beta")
    with col2:
        fg = go.Figure()
        fg.add_trace(go.Scatter(x=x, y=df["low_gamma"], name="Low γ",  line=dict(color="#558b2f", width=2)))
        fg.add_trace(go.Scatter(x=x, y=df["mid_gamma"], name="Mid γ",  line=dict(color="#8bc34a", width=2)))
        fg.update_layout(title="Gamma Waves", height=220, paper_bgcolor="white",
                         plot_bgcolor="#f8fafc", font=dict(family="Inter", size=11),
                         margin=dict(t=35, b=20, l=40, r=10))
        fg.update_xaxes(showgrid=False)
        st.plotly_chart(fg, use_container_width=True, key="eeg_gamma")


def render_eeg():
    st.markdown('<h2 class="page-title">🧠 EEG Assessment</h2>', unsafe_allow_html=True)

    patient = st.session_state.get("current_patient")
    if not patient:
        st.warning("Please select a patient from the sidebar first.")
        return

    pid  = patient["id"]
    name = patient["name"]

    st.info(f"Patient: **{name}** | Serial Port: COM6 @ 9600 baud")

    # ── Controls ───────────────────────────────────────────────────────────────
    ctrl_col, stat_col = st.columns([2, 2])
    with ctrl_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Recording Controls")
        recording = sr.is_running()

        if not recording:
            if st.button("▶ Start EEG Recording", use_container_width=True):
                session_id = datetime.now().strftime("EEG_%Y%m%d_%H%M%S")
                st.session_state["eeg_session_id"] = session_id
                st.session_state["eeg_patient_id"] = pid
                sr.start(pid, session_id)
                st.success(f"Recording started — Session: {session_id}")
                st.rerun()
        else:
            if st.button("⏹ Stop EEG Recording", use_container_width=True):
                sr.stop()
                st.success("Recording stopped.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with stat_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Status")
        status = sr.get_status()
        if recording:
            st.success(f"🔴 **LIVE** — {status['samples']} samples recorded")
        else:
            st.info("⏸ Not recording")
        if status["last_error"]:
            st.error(f"Error: {status['last_error']}")
        if status["connected"]:
            st.caption("COM6 connected")
        elif status["last_error"]:
            st.caption("Reconnecting…")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Session Selector ───────────────────────────────────────────────────────
    sessions = get_eeg_sessions(pid)
    if not sessions:
        if recording:
            st.info("Waiting for first EEG samples… Page refreshes automatically.")
            time.sleep(REFRESH)
            st.rerun()
        else:
            st.info("No EEG data for this patient yet. Press **Start** to begin recording.")
        return

    session_labels = {
        f"{s['session_id']}  ({s['samples']} samples, avg attention {round(s['avg_attention'] or 0)}%)": s["session_id"]
        for s in sessions
    }
    default_idx = 0
    active_sid  = st.session_state.get("eeg_session_id")
    if active_sid:
        for i, sid in enumerate(session_labels.values()):
            if sid == active_sid:
                default_idx = i
                break

    selected_label = st.selectbox("View Session", list(session_labels.keys()), index=default_idx)
    selected_sid   = session_labels[selected_label]

    # ── Load & Display ─────────────────────────────────────────────────────────
    rows = get_eeg_signals(pid, selected_sid, limit=300)
    if not rows:
        st.info("No data for this session yet.")
        return

    df = pd.DataFrame(rows)
    latest = df.iloc[-1]

    # ── Latest Reading Metrics ─────────────────────────────────────────────────
    st.markdown("#### Latest Reading")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Signal Quality", f"{int(latest['quality'])}%")

    att_label, att_color = _attention_label(int(latest["attention"]))
    m2.metric("Attention",  f"{int(latest['attention'])}%")
    m3.metric("Meditation", f"{int(latest['meditation'])}%")
    m4.metric("Theta/Beta", f"{latest['theta_beta_ratio']:.2f}")
    m5.metric("Samples",    len(df))

    # TBR Interpretation
    tbr_avg    = df["theta_beta_ratio"].mean()
    tbr_label, tbr_color, tbr_desc = _tbr_interpretation(tbr_avg)
    att_avg    = df["attention"].mean()
    att_lbl, _ = _attention_label(int(att_avg))

    st.markdown(f"""
    <div style="background:#f8fafc;border-left:5px solid {tbr_color};
                padding:12px 18px;border-radius:8px;margin:8px 0;">
        <b>Theta/Beta Ratio Interpretation:</b>
        <span style="color:{tbr_color};font-weight:700;margin-left:8px;">{tbr_label} (avg {tbr_avg:.2f})</span><br>
        <small>{tbr_desc}</small><br>
        <small>Average Attention: <b>{att_avg:.0f}%</b> — {att_lbl}</small>
    </div>
    """, unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("#### Brainwave Charts")
    _draw_charts(df)

    # ── Raw Data ──────────────────────────────────────────────────────────────
    with st.expander("View Raw EEG Data (latest 20 rows)"):
        show_cols = ["recorded_at","quality","attention","meditation",
                     "delta","theta","low_alpha","high_alpha",
                     "low_beta","high_beta","low_gamma","mid_gamma","theta_beta_ratio"]
        st.dataframe(df[show_cols].tail(20).iloc[::-1], use_container_width=True, hide_index=True)

    # ── Auto-refresh while recording ──────────────────────────────────────────
    if recording and selected_sid == st.session_state.get("eeg_session_id"):
        st.caption(f"Auto-refreshing every {REFRESH}s…")
        time.sleep(REFRESH)
        st.rerun()
