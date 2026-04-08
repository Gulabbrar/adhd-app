"""modules/home.py — Home Dashboard"""
import streamlit as st
import plotly.graph_objects as go
from database import get_dashboard_stats, get_patients, get_conn, _exec


def render_home():
    st.markdown('<h2 class="page-title">Dashboard Overview</h2>', unsafe_allow_html=True)

    stats = get_dashboard_stats()

    # ── KPI Metrics ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with get_conn() as _c:
        total_reports = _exec(_c, "SELECT COUNT(*) as c FROM assessment_reports").fetchone()["c"]

    c1.metric("Total Patients",    stats["total_patients"])
    c2.metric("Assessments Done",  stats["total_assessments"])
    c3.metric("EEG Sessions",      stats["total_eeg"])
    c4.metric("Reports Generated", total_reports)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1])

    # ── Risk Distribution Pie ─────────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### ADHD Risk Distribution")
        rd = stats["risk_distribution"]
        if rd:
            labels = [r["risk_level"] for r in rd]
            values = [r["count"]      for r in rd]
            color_map = {
                "Low Risk":      "#2e7d32",
                "Moderate Risk": "#f57f17",
                "High Risk":     "#c62828",
            }
            colors = [color_map.get(l, "#1565c0") for l in labels]
            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.45,
                marker=dict(colors=colors),
                textinfo="label+percent",
            ))
            fig.update_layout(
                paper_bgcolor="white", showlegend=True, height=280,
                margin=dict(t=10, b=10, l=10, r=10),
                font=dict(family="Inter", size=12),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No questionnaire data yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Recent Patients ────────────────────────────────────────────────────────
    with col_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Recent Patients")
        patients = get_patients()
        if patients:
            import pandas as pd
            pdf = pd.DataFrame(patients[:8])[["id","name","age","gender","created_at"]]
            pdf.columns = ["ID", "Name", "Age", "Gender", "Registered"]
            st.dataframe(pdf, use_container_width=True, hide_index=True)
        else:
            st.info("No patients registered yet. Add one from the sidebar.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    # ── Recent EEG Sessions ────────────────────────────────────────────────────
    with col_a:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Recent EEG Sessions")
        sessions = stats["recent_sessions"]
        if sessions:
            import pandas as pd
            sdf = pd.DataFrame(sessions)
            sdf.columns = ["Session ID", "Patient", "Started At", "Samples"]
            st.dataframe(sdf, use_container_width=True, hide_index=True)
        else:
            st.info("No EEG sessions recorded yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Recent Questionnaires ──────────────────────────────────────────────────
    with col_b:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Recent Questionnaire Results")
        rq = stats["recent_questionnaires"]
        if rq:
            import pandas as pd
            qdf = pd.DataFrame(rq)[["patient_name", "total_score", "risk_level", "assessed_at"]]
            qdf.columns = ["Patient", "Score", "Risk Level", "Date"]
            st.dataframe(qdf, use_container_width=True, hide_index=True)
        else:
            st.info("No questionnaire results yet.")
        st.markdown('</div>', unsafe_allow_html=True)
