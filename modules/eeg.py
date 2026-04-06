"""modules/eeg.py — EEG Assessment (Live recording + Manual entry)"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime
from database import save_eeg_signal, get_eeg_signals, get_eeg_sessions

try:
    import serial_reader as sr
    _SERIAL_AVAILABLE = True
except Exception:
    sr = None
    _SERIAL_AVAILABLE = False

REFRESH = 3   # seconds between auto-refresh


# ── Interpretation helpers ────────────────────────────────────────────────────
def _tbr_interp(tbr: float) -> tuple:
    if tbr < 1.5:   return "Normal",    "#2e7d32", "TBR within normal range."
    if tbr < 2.5:   return "Elevated",  "#f57f17", "Slightly elevated — mild inattention possible."
    if tbr < 3.5:   return "High",      "#e65100", "High ratio — moderate ADHD tendency."
    return               "Very High", "#c62828", "Very high ratio — strong ADHD indicator (TBR ≥ 3.5)."


def _att_label(val: int) -> tuple:
    if val >= 70:  return "High Focus",    "#2e7d32"
    if val >= 40:  return "Moderate",      "#f57f17"
    return               "Low Attention",  "#c62828"


# ── Chart renderer ────────────────────────────────────────────────────────────
def _draw_charts(df: pd.DataFrame, key_prefix: str = "eeg"):
    if df.empty:
        return

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
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_main")

    col1, col2 = st.columns(2)
    with col1:
        fb = go.Figure()
        fb.add_trace(go.Scatter(x=x, y=df["low_beta"],  name="Low β",
                                line=dict(color="#e65100", width=2)))
        fb.add_trace(go.Scatter(x=x, y=df["high_beta"], name="High β",
                                line=dict(color="#ff8f00", width=2)))
        fb.update_layout(title="Beta Waves", height=220, paper_bgcolor="white",
                         plot_bgcolor="#f8fafc", font=dict(family="Inter", size=11),
                         margin=dict(t=35, b=20, l=40, r=10))
        st.plotly_chart(fb, use_container_width=True, key=f"{key_prefix}_beta")
    with col2:
        fg = go.Figure()
        fg.add_trace(go.Scatter(x=x, y=df["low_gamma"], name="Low γ",
                                line=dict(color="#558b2f", width=2)))
        fg.add_trace(go.Scatter(x=x, y=df["mid_gamma"], name="Mid γ",
                                line=dict(color="#8bc34a", width=2)))
        fg.update_layout(title="Gamma Waves", height=220, paper_bgcolor="white",
                         plot_bgcolor="#f8fafc", font=dict(family="Inter", size=11),
                         margin=dict(t=35, b=20, l=40, r=10))
        st.plotly_chart(fg, use_container_width=True, key=f"{key_prefix}_gamma")


def _show_session(pid: int, sid: str, key_prefix: str = "eeg"):
    """Load a session and render metrics + charts."""
    rows = get_eeg_signals(pid, sid, limit=300)
    if not rows:
        st.info("No data for this session.")
        return
    df     = pd.DataFrame(rows)
    latest = df.iloc[-1]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Signal Quality",  f"{int(latest['quality'])}%")
    m2.metric("Attention",       f"{int(latest['attention'])}%")
    m3.metric("Meditation",      f"{int(latest['meditation'])}%")
    m4.metric("Theta/Beta",      f"{latest['theta_beta_ratio']:.2f}")
    m5.metric("Samples",         len(df))

    tbr_avg              = df["theta_beta_ratio"].mean()
    tbr_lbl, tbr_c, tbd = _tbr_interp(tbr_avg)
    att_avg              = df["attention"].mean()
    att_lbl, _           = _att_label(int(att_avg))

    st.markdown(f"""
    <div style="background:#f8fafc;border-left:5px solid {tbr_c};
                padding:12px 18px;border-radius:8px;margin:8px 0;">
        <b>TBR Interpretation:</b>
        <span style="color:{tbr_c};font-weight:700;margin-left:8px;">
            {tbr_lbl} (avg {tbr_avg:.2f})
        </span><br>
        <small>{tbd}</small><br>
        <small>Avg Attention: <b>{att_avg:.0f}%</b> — {att_lbl}</small>
    </div>
    """, unsafe_allow_html=True)

    _draw_charts(df, key_prefix)

    with st.expander("Raw EEG Data (latest 20 rows)"):
        show_cols = ["recorded_at","quality","attention","meditation",
                     "delta","theta","low_alpha","high_alpha",
                     "low_beta","high_beta","low_gamma","mid_gamma","theta_beta_ratio"]
        st.dataframe(df[show_cols].tail(20).iloc[::-1],
                     use_container_width=True, hide_index=True)


# ── Main render ───────────────────────────────────────────────────────────────
def render_eeg():
    st.markdown('<h2 class="page-title">🧠 EEG Assessment</h2>', unsafe_allow_html=True)

    patient = st.session_state.get("current_patient")
    if not patient:
        st.warning("Please select a patient from the sidebar first.")
        return

    pid  = patient["id"]
    name = patient["name"]

    tab_live, tab_manual, tab_history = st.tabs([
        "📡 Live Recording", "✏️ Manual Entry", "📊 Session History"
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Live EEG Recording (hardware serial reader)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_live:
        if not _SERIAL_AVAILABLE:
            st.warning(
                "Live EEG recording is not available in this environment "
                "(serial hardware / pyserial not detected). "
                "Use the **Manual Entry** tab to enter EEG values recorded during a session."
            )
        else:
            st.info(f"Patient: **{name}** | Serial Port: COM6 @ 9600 baud")

            ctrl_col, stat_col = st.columns(2)
            with ctrl_col:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown("#### Recording Controls")
                recording = sr.is_running()
                if not recording:
                    if st.button("▶ Start EEG Recording", use_container_width=True,
                                  key="live_start"):
                        session_id = datetime.now().strftime("EEG_%Y%m%d_%H%M%S")
                        st.session_state["eeg_session_id"] = session_id
                        st.session_state["eeg_patient_id"] = pid
                        sr.start(pid, session_id)
                        st.success(f"Recording started — Session: {session_id}")
                        st.rerun()
                else:
                    if st.button("⏹ Stop Recording", use_container_width=True,
                                  key="live_stop"):
                        sr.stop()
                        st.success("Recording stopped.")
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with stat_col:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown("#### Status")
                status = sr.get_status()
                if sr.is_running():
                    st.success(f"🔴 LIVE — {status['samples']} samples")
                else:
                    st.info("⏸ Not recording")
                if status["last_error"]:
                    st.error(f"Error: {status['last_error']}")
                st.markdown('</div>', unsafe_allow_html=True)

            sessions = get_eeg_sessions(pid)
            if not sessions:
                if sr.is_running():
                    st.info("Waiting for first samples… auto-refreshing.")
                    time.sleep(REFRESH)
                    st.rerun()
                else:
                    st.info("No EEG data yet. Press Start to begin recording.")
            else:
                labels = {
                    f"{s['session_id']}  ({s['samples']} samples, "
                    f"avg attn {round(s['avg_attention'] or 0)}%)": s["session_id"]
                    for s in sessions
                }
                active_sid = st.session_state.get("eeg_session_id")
                default_i  = next((i for i, sid in enumerate(labels.values())
                                   if sid == active_sid), 0)
                sel_lbl    = st.selectbox("View Session", list(labels.keys()),
                                           index=default_i, key="live_sess_sel")
                sel_sid    = labels[sel_lbl]
                _show_session(pid, sel_sid, "live")

                if sr.is_running() and sel_sid == st.session_state.get("eeg_session_id"):
                    st.caption(f"Auto-refreshing every {REFRESH}s…")
                    time.sleep(REFRESH)
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — Manual EEG Entry
    # ══════════════════════════════════════════════════════════════════════════
    with tab_manual:
        st.markdown(f"""
        <div class="card">
            <b>Patient:</b> {name} &nbsp;|&nbsp;
            <b>ID:</b> {patient.get('patient_uid') or '#'+str(pid)}<br>
            <small style="color:#64748b;">
                Enter the EEG values recorded during the session.
                Each submission is saved as one sample in a named session.
                Submit multiple readings to build a session timeline.
            </small>
        </div>
        """, unsafe_allow_html=True)

        # Session management
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            existing_sessions = get_eeg_sessions(pid)
            manual_sessions   = [s["session_id"] for s in existing_sessions
                                  if s["session_id"].startswith("MAN_")]
            session_options   = ["Create new session"] + manual_sessions
            sess_choice       = st.selectbox("Session", session_options,
                                              key="man_sess_choice")

        with col_s2:
            st.markdown("<br>", unsafe_allow_html=True)
            if sess_choice == "Create new session":
                session_id = datetime.now().strftime("MAN_%Y%m%d_%H%M%S")
                st.caption(f"New: `{session_id}`")
            else:
                session_id = sess_choice
                st.caption(f"Adding to: `{session_id}`")

        st.markdown("---")
        st.markdown("#### Enter EEG Values")

        with st.form("manual_eeg_form"):
            # ── Row 1: Core metrics ──────────────────────────────────────────
            st.markdown("**Core Metrics**")
            r1c1, r1c2, r1c3 = st.columns(3)
            quality    = r1c1.number_input("Signal Quality (%)",    0, 100, 80,
                                            help="Headset signal quality 0–100")
            attention  = r1c2.number_input("Attention (%)",         0, 100, 50,
                                            help="eSense Attention score 0–100")
            meditation = r1c3.number_input("Meditation (%)",        0, 100, 40,
                                            help="eSense Meditation score 0–100")

            st.markdown("**Brainwave Power (µV²)** — enter raw power values")

            # ── Row 2: Slow waves ─────────────────────────────────────────────
            st.markdown("<small style='color:#64748b;'>Slow waves</small>",
                        unsafe_allow_html=True)
            r2c1, r2c2 = st.columns(2)
            delta = r2c1.number_input("Delta (δ)",  0, 2_000_000, 250_000, step=1_000,
                                       help="Deep sleep / slow-wave power")
            theta = r2c2.number_input("Theta (θ)",  0, 2_000_000, 120_000, step=1_000,
                                       help="Drowsiness / inattention indicator")

            # ── Row 3: Alpha ──────────────────────────────────────────────────
            st.markdown("<small style='color:#64748b;'>Alpha waves</small>",
                        unsafe_allow_html=True)
            r3c1, r3c2 = st.columns(2)
            low_alpha  = r3c1.number_input("Low Alpha (8–10 Hz)",   0, 2_000_000, 60_000, step=1_000)
            high_alpha = r3c2.number_input("High Alpha (10–12 Hz)", 0, 2_000_000, 50_000, step=1_000)

            # ── Row 4: Beta ───────────────────────────────────────────────────
            st.markdown("<small style='color:#64748b;'>Beta waves — focus & alertness</small>",
                        unsafe_allow_html=True)
            r4c1, r4c2 = st.columns(2)
            low_beta   = r4c1.number_input("Low Beta (12–21 Hz)",  0, 2_000_000, 30_000, step=1_000)
            high_beta  = r4c2.number_input("High Beta (21–30 Hz)", 0, 2_000_000, 20_000, step=1_000)

            # ── Row 5: Gamma ──────────────────────────────────────────────────
            st.markdown("<small style='color:#64748b;'>Gamma waves — cognitive processing</small>",
                        unsafe_allow_html=True)
            r5c1, r5c2 = st.columns(2)
            low_gamma  = r5c1.number_input("Low Gamma (30–40 Hz)", 0, 2_000_000, 8_000, step=500)
            mid_gamma  = r5c2.number_input("Mid Gamma (40–100 Hz)",0, 2_000_000, 5_000, step=500)

            notes = st.text_area("Session Notes (optional)",
                                  placeholder="e.g. Patient was calm, eyes open, baseline reading…",
                                  height=60)

            submitted = st.form_submit_button("💾 Save EEG Reading", use_container_width=True)

        if submitted:
            # Compute TBR live so the doctor sees it immediately
            beta_total = max(low_beta + high_beta, 1)
            tbr        = round(theta / beta_total, 4)
            tbr_lbl, tbr_c, tbr_desc = _tbr_interp(tbr)
            att_lbl, att_c            = _att_label(attention)

            data = {
                "quality":    quality,
                "attention":  attention,
                "meditation": meditation,
                "delta":      delta,
                "theta":      theta,
                "lowAlpha":   low_alpha,
                "highAlpha":  high_alpha,
                "lowBeta":    low_beta,
                "highBeta":   high_beta,
                "lowGamma":   low_gamma,
                "midGamma":   mid_gamma,
            }
            save_eeg_signal(pid, session_id, data)

            # Immediate interpretation feedback
            st.success(f"Reading saved to session `{session_id}`")

            st.markdown(f"""
            <div style="background:#f0f4f8;border-radius:12px;padding:16px 20px;margin-top:12px;">
                <h4 style="margin:0 0 12px;color:#0f172a;">Instant Interpretation</h4>
                <div style="display:flex;gap:16px;flex-wrap:wrap;">
                    <div style="flex:1;min-width:160px;background:white;border-radius:8px;
                                padding:12px;border-top:3px solid {att_c};">
                        <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                                    font-weight:600;">Attention</div>
                        <div style="font-size:1.6rem;font-weight:800;color:{att_c};">{attention}%</div>
                        <div style="font-size:0.8rem;color:#374151;">{att_lbl}</div>
                    </div>
                    <div style="flex:1;min-width:160px;background:white;border-radius:8px;
                                padding:12px;border-top:3px solid {tbr_c};">
                        <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                                    font-weight:600;">Theta/Beta Ratio</div>
                        <div style="font-size:1.6rem;font-weight:800;color:{tbr_c};">{tbr:.2f}</div>
                        <div style="font-size:0.8rem;color:#374151;">{tbr_lbl}</div>
                    </div>
                    <div style="flex:2;min-width:200px;background:white;border-radius:8px;
                                padding:12px;border-top:3px solid #1565c0;">
                        <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                                    font-weight:600;">Clinical Note</div>
                        <div style="font-size:0.88rem;color:#374151;margin-top:4px;">{tbr_desc}</div>
                    </div>
                </div>
                {"<div style='margin-top:10px;color:#64748b;font-size:0.82rem;'>"
                 + f"<b>Notes:</b> {notes}</div>" if notes else ""}
            </div>
            """, unsafe_allow_html=True)

        # ── Preview current session data ──────────────────────────────────────
        if sess_choice != "Create new session":
            st.markdown("---")
            st.markdown(f"#### Session Preview: `{session_id}`")
            _show_session(pid, session_id, "man_preview")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — Session History
    # ══════════════════════════════════════════════════════════════════════════
    with tab_history:
        sessions = get_eeg_sessions(pid)
        if not sessions:
            st.info("No EEG sessions recorded for this patient yet.")
            return

        st.markdown(f"#### All EEG Sessions — {name}")
        sdf = pd.DataFrame(sessions)
        sdf["avg_attention"]    = sdf["avg_attention"].apply(lambda x: f"{x:.0f}%" if x else "—")
        sdf["avg_tbr"]          = sdf["avg_tbr"].apply(lambda x: f"{x:.2f}" if x else "—")
        sdf["type"]             = sdf["session_id"].apply(
            lambda s: "Manual" if s.startswith("MAN_") else "Live"
        )
        display = sdf[["session_id","type","started_at","samples","avg_attention","avg_tbr"]]
        display.columns = ["Session ID","Type","Started","Samples","Avg Attention","Avg TBR"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        # Drill into any session
        st.markdown("---")
        labels = {f"{s['session_id']} ({s['samples']} samples)": s["session_id"]
                  for s in sessions}
        sel = st.selectbox("View session detail", list(labels.keys()),
                            key="hist_sess_sel")
        _show_session(pid, labels[sel], "hist")
