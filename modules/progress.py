"""modules/progress.py — Patient Progress Tracking"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from database import (get_patients, get_eeg_sessions, get_eeg_signals,
                       get_questionnaires, get_emotion_logs, get_activity_results)


def render_progress():
    st.markdown('<h2 class="page-title">Patient Progress Report</h2>', unsafe_allow_html=True)

    patients = get_patients()
    if not patients:
        st.info("No patients registered yet.")
        return

    # Patient selector (can be different from sidebar selection)
    options = {f"{p['name']} (ID {p['id']})": p["id"] for p in patients}
    selected = st.selectbox("Select Patient", list(options.keys()))
    pid = options[selected]
    patient = next(p for p in patients if p["id"] == pid)

    st.markdown(f"""
    <div class="card">
    <b>Name:</b> {patient['name']} &nbsp;|&nbsp;
    <b>Age:</b> {patient['age']} &nbsp;|&nbsp;
    <b>Gender:</b> {patient['gender']} &nbsp;|&nbsp;
    <b>Registered:</b> {patient['created_at']}
    </div>
    """, unsafe_allow_html=True)

    tab_eeg, tab_q, tab_emo, tab_act = st.tabs([
        "EEG Trends", "Questionnaire History", "Emotion Patterns", "Activity Performance"
    ])

    # ── EEG Trends ───────────────────────────────────────────────────────────
    with tab_eeg:
        sessions = get_eeg_sessions(pid)
        if not sessions:
            st.info("No EEG sessions recorded for this patient.")
        else:
            sdf = pd.DataFrame(sessions)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Sessions", len(sdf))
            col2.metric("Avg Attention",  f"{sdf['avg_attention'].mean():.0f}%")
            col3.metric("Avg Theta/Beta", f"{sdf['avg_tbr'].mean():.2f}")

            # Session attention trend
            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(
                x=sdf["started_at"], y=sdf["avg_attention"],
                name="Avg Attention %", mode="lines+markers",
                line=dict(color="#1565c0", width=2),
                marker=dict(size=7),
            ))
            fig_s.add_trace(go.Scatter(
                x=sdf["started_at"], y=sdf["avg_tbr"],
                name="Theta/Beta Ratio", mode="lines+markers",
                line=dict(color="#c62828", width=2, dash="dot"),
                marker=dict(size=7), yaxis="y2"
            ))
            fig_s.add_hline(y=2.89, line_dash="dash", line_color="#f57f17",
                            annotation_text="TBR Threshold")
            fig_s.update_layout(
                title="EEG Session Summary Trends",
                yaxis=dict(title="Attention %", range=[0, 100]),
                yaxis2=dict(title="Theta/Beta Ratio", overlaying="y", side="right"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=320,
                font=dict(family="Inter", size=11),
                legend=dict(bgcolor="white", bordercolor="#e2e8f0", borderwidth=1),
                margin=dict(t=40, b=20, l=40, r=40),
            )
            st.plotly_chart(fig_s, use_container_width=True, key="prg_eeg")

            # Detailed view of a selected session
            st.markdown("---")
            session_opts = {s["session_id"]: s["session_id"] for s in sessions}
            sel_session  = st.selectbox("Detailed Session View", list(session_opts.keys()))
            sig = get_eeg_signals(pid, sel_session, limit=300)
            if sig:
                df = pd.DataFrame(sig)
                fig_d = make_subplots(rows=1, cols=2,
                                      subplot_titles=("Attention & Meditation", "Theta/Beta Ratio"))
                x = df["recorded_at"]
                fig_d.add_trace(go.Scatter(x=x, y=df["attention"],  name="Attention",
                                           line=dict(color="#1565c0")), row=1, col=1)
                fig_d.add_trace(go.Scatter(x=x, y=df["meditation"], name="Meditation",
                                           line=dict(color="#00897b")), row=1, col=1)
                fig_d.add_trace(go.Scatter(x=x, y=df["theta_beta_ratio"], name="TBR",
                                           line=dict(color="#c62828")), row=1, col=2)
                fig_d.update_layout(height=300, paper_bgcolor="white", plot_bgcolor="#f8fafc",
                                    font=dict(family="Inter", size=11),
                                    margin=dict(t=40, b=20, l=40, r=20))
                st.plotly_chart(fig_d, use_container_width=True, key="prg_eeg_detail")

    # ── Questionnaire History ─────────────────────────────────────────────────
    with tab_q:
        qs = get_questionnaires(pid)
        if not qs:
            st.info("No questionnaire results for this patient.")
        else:
            qdf = pd.DataFrame(qs).sort_values("assessed_at")
            col1, col2 = st.columns(2)
            col1.metric("Assessments",  len(qdf))
            col2.metric("Latest Risk",  qdf.iloc[-1]["risk_level"])

            fig_q = go.Figure()
            fig_q.add_trace(go.Scatter(x=qdf["assessed_at"], y=qdf["inatt_score"],
                                        name="Inattention", mode="lines+markers",
                                        line=dict(color="#1565c0", width=2)))
            fig_q.add_trace(go.Scatter(x=qdf["assessed_at"], y=qdf["hyper_score"],
                                        name="Hyperactivity", mode="lines+markers",
                                        line=dict(color="#c62828", width=2)))
            fig_q.add_trace(go.Scatter(x=qdf["assessed_at"], y=qdf["total_score"],
                                        name="Total", mode="lines+markers",
                                        line=dict(color="#f57f17", width=2, dash="dot")))
            fig_q.add_hline(y=48, line_dash="dash", line_color="#c62828",
                            annotation_text="High Risk (48)")
            fig_q.add_hline(y=24, line_dash="dash", line_color="#f57f17",
                            annotation_text="Moderate Risk (24)")
            fig_q.update_layout(
                title="Questionnaire Score History",
                yaxis=dict(range=[0, 72], title="Score"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=320,
                font=dict(family="Inter", size=11),
                legend=dict(bgcolor="white"),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_q, use_container_width=True, key="prg_q")

            st.dataframe(qdf[["session_id","total_score","inatt_score",
                                "hyper_score","risk_level","assessed_at"]].iloc[::-1],
                         use_container_width=True, hide_index=True)

    # ── Emotion Patterns ──────────────────────────────────────────────────────
    with tab_emo:
        emos = get_emotion_logs(pid)
        if not emos:
            st.info("No emotion data for this patient.")
        else:
            edf = pd.DataFrame(emos)
            dom_counts = edf["dominant_emotion"].value_counts()

            col1, col2 = st.columns([1, 1])
            ECOLS = {"happy":"#2e7d32","neutral":"#1565c0","sad":"#4527a0",
                     "angry":"#c62828","fear":"#e65100","surprise":"#f57f17"}
            with col1:
                fig_ep = go.Figure(go.Pie(
                    labels=dom_counts.index, values=dom_counts.values,
                    hole=0.4,
                    marker=dict(colors=[ECOLS.get(e,"#999") for e in dom_counts.index]),
                ))
                fig_ep.update_layout(title="Emotion Distribution", paper_bgcolor="white",
                                     height=280, font=dict(family="Inter", size=11),
                                     margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig_ep, use_container_width=True, key="prg_emo_pie")

            with col2:
                if len(edf) > 2:
                    fig_et = go.Figure()
                    for emo, color in ECOLS.items():
                        if emo in edf.columns:
                            fig_et.add_trace(go.Scatter(
                                x=edf["logged_at"], y=edf[emo] * 100,
                                name=emo, line=dict(color=color, width=1.5)
                            ))
                    fig_et.update_layout(title="Emotion Trend (%)", height=280,
                                          paper_bgcolor="white", plot_bgcolor="#f8fafc",
                                          font=dict(family="Inter", size=11),
                                          margin=dict(t=40, b=20, l=40, r=10))
                    st.plotly_chart(fig_et, use_container_width=True, key="prg_emo_trend")

    # ── Activity Performance ──────────────────────────────────────────────────
    with tab_act:
        acts = get_activity_results(pid)
        if not acts:
            st.info("No activity data for this patient.")
        else:
            adf = pd.DataFrame(acts)
            avg_by_act = adf.groupby("activity_name")[["accuracy","attention_score"]].mean().reset_index()

            fig_a = go.Figure()
            for _, row in avg_by_act.iterrows():
                fig_a.add_trace(go.Bar(
                    name=row["activity_name"],
                    x=["Accuracy %", "Attention %"],
                    y=[row["accuracy"], row["attention_score"]],
                ))
            fig_a.update_layout(
                barmode="group", title="Activity Performance Summary",
                yaxis=dict(range=[0, 105], title="%"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=300,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_a, use_container_width=True, key="prg_act")

            st.dataframe(adf[["activity_name","accuracy","completion_time",
                               "error_rate","attention_score","completed_at"]].iloc[::-1],
                         use_container_width=True, hide_index=True)
