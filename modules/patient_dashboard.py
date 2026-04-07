"""modules/patient_dashboard.py — Patient-facing personal dashboard"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from database import (
    get_user_patient, get_questionnaires, get_appointments,
    get_reviews, get_review_stats, get_reports
)


# ── Helpers ────────────────────────────────────────────────────────────────────
def _star_html(rating: int) -> str:
    full  = "★" * rating
    empty = "☆" * (5 - rating)
    return f'<span style="color:#f59e0b;font-size:1.1rem;">{full}</span><span style="color:#d1d5db;">{empty}</span>'


def _status_badge(status: str) -> str:
    colors = {
        "booked":    ("#dbeafe", "#1d4ed8"),
        "completed": ("#dcfce7", "#15803d"),
        "cancelled": ("#fee2e2", "#b91c1c"),
    }
    bg, fg = colors.get(status, ("#f3f4f6", "#374151"))
    label  = {"booked": "Booked", "completed": "Completed", "cancelled": "Cancelled"}.get(status, status)
    return (f'<span style="background:{bg};color:{fg};padding:2px 10px;'
            f'border-radius:50px;font-size:0.75rem;font-weight:600;">{label}</span>')


def _risk_badge(risk: str) -> str:
    colors = {
        "High Risk":     ("#fee2e2", "#b91c1c"),
        "Moderate Risk": ("#fef3c7", "#b45309"),
        "Low Risk":      ("#dcfce7", "#15803d"),
    }
    bg, fg = colors.get(risk, ("#f3f4f6", "#374151"))
    return (f'<span style="background:{bg};color:{fg};padding:2px 10px;'
            f'border-radius:50px;font-size:0.75rem;font-weight:600;">{risk}</span>')


# ── Main render ────────────────────────────────────────────────────────────────
def render_patient_dashboard():
    user    = st.session_state.user
    patient = get_user_patient(user["id"])

    if not patient:
        st.error("Patient profile not found. Please contact support.")
        return

    pid         = patient["id"]
    patient_uid = patient.get("patient_uid") or "—"

    # ── Welcome Banner ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d47a1,#1976d2);
                border-radius:14px;padding:24px 28px;margin-bottom:20px;">
        <h2 style="color:white;margin:0 0 4px;font-size:1.4rem;">
            Welcome back, {patient['name']}
        </h2>
        <p style="color:rgba(255,255,255,0.8);margin:0;font-size:0.9rem;">
            Patient ID: <strong style="color:#93c5fd;">{patient_uid}</strong>
            &nbsp;|&nbsp; ADHD Assessment Platform
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI Row ────────────────────────────────────────────────────────────────
    appts       = get_appointments(pid)
    reviews     = get_reviews(pid)
    assessments = get_questionnaires(pid)
    reports     = get_reports(pid)

    upcoming = [a for a in appts if a["status"] == "booked"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patient ID",       patient_uid)
    c2.metric("Assessments Done", len(assessments))
    c3.metric("Appointments",     len(appts))
    c4.metric("Upcoming",         len(upcoming))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_profile, tab_progress, tab_appts, tab_reports = st.tabs([
        "Profile", "Progress", "Appointments", "Reports"
    ])

    # ── Profile Tab ────────────────────────────────────────────────────────────
    with tab_profile:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Personal Information")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            | Field | Value |
            |-------|-------|
            | **Full Name** | {patient['name']} |
            | **Patient ID** | `{patient_uid}` |
            | **Age** | {patient['age'] or '—'} |
            | **Gender** | {patient['gender'] or '—'} |
            """)
        with col2:
            st.markdown(f"""
            | Field | Value |
            |-------|-------|
            | **Email** | {patient['email'] or '—'} |
            | **Phone** | {patient['phone'] or '—'} |
            | **Registered** | {patient['created_at'][:10]} |
            | **Username** | {user['username']} |
            """)

        # Edit profile
        with st.expander("Edit Profile"):
            with st.form("edit_profile_form"):
                c1, c2 = st.columns(2)
                new_phone = c1.text_input("Phone", value=patient.get("phone") or "")
                new_age   = c2.number_input("Age", 3, 120,
                                             value=int(patient["age"]) if patient.get("age") else 18)
                new_notes = st.text_area("Personal Notes", value=patient.get("notes") or "", height=80)
                if st.form_submit_button("Save", use_container_width=True):
                    from database import update_patient
                    update_patient(pid, patient["name"], new_age,
                                   patient.get("gender",""), patient.get("email",""),
                                   new_phone, new_notes)
                    st.success("Profile updated!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Progress Tab ───────────────────────────────────────────────────────────
    with tab_progress:
        if not assessments:
            st.info("No ADHD assessments recorded yet. Complete a questionnaire to see your progress.")
        else:
            latest = assessments[0]
            risk   = latest.get("risk_level", "—")

            # Summary cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Latest Score",        latest.get("total_score", 0))
            col2.metric("Inattention Score",   latest.get("inatt_score", 0))
            col3.metric("Hyperactivity Score", latest.get("hyper_score", 0))

            st.markdown(f'<p>Current Risk Level: {_risk_badge(risk)}</p>',
                        unsafe_allow_html=True)

            if len(assessments) >= 2:
                st.markdown("#### Score Trend")
                df = pd.DataFrame(assessments[::-1])
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["total_score"],
                    name="Total Score", mode="lines+markers",
                    line=dict(color="#1565c0", width=2), marker=dict(size=7)
                ))
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["inatt_score"],
                    name="Inattention", mode="lines+markers",
                    line=dict(color="#c62828", width=1.5, dash="dot")
                ))
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["hyper_score"],
                    name="Hyperactivity", mode="lines+markers",
                    line=dict(color="#f57f17", width=1.5, dash="dot")
                ))
                fig.add_hline(y=48, line_dash="dash", line_color="#c62828",
                              annotation_text="High Risk (48)")
                fig.add_hline(y=24, line_dash="dash", line_color="#f57f17",
                              annotation_text="Moderate (24)")
                fig.update_layout(
                    yaxis=dict(range=[0, 75], title="Score"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc", height=300,
                    font=dict(family="Inter", size=11),
                    legend=dict(bgcolor="white"),
                    margin=dict(t=20, b=20, l=40, r=20),
                )
                st.plotly_chart(fig, use_container_width=True, key="pd_score_trend")
            else:
                st.info("Complete more assessments to see your score trend.")

            # ADHD Progress Report card
            st.markdown("---")
            st.markdown("#### ADHD Progress Report")
            risk_color_map = {
                "High Risk": "#fee2e2", "Moderate Risk": "#fef3c7", "Low Risk": "#dcfce7"
            }
            bg = risk_color_map.get(risk, "#f3f4f6")
            total  = latest.get("total_score", 0)
            pct    = min(int(total / 72 * 100), 100)
            bar_c  = "#c62828" if pct >= 67 else "#f57f17" if pct >= 33 else "#15803d"

            st.markdown(f"""
            <div style="background:{bg};border-radius:12px;padding:20px;margin-top:8px;">
                <h4 style="margin:0 0 12px;color:#0f172a;">Assessment Summary</h4>
                <p style="margin:4px 0;color:#374151;">
                    Based on your latest ADHD questionnaire, your overall score is
                    <strong>{total}/72</strong>, placing you in the
                    <strong>{risk}</strong> category.
                </p>
                <div style="background:#e5e7eb;border-radius:50px;height:10px;margin:14px 0 6px;">
                    <div style="background:{bar_c};width:{pct}%;height:10px;
                                border-radius:50px;transition:width 0.4s;"></div>
                </div>
                <small style="color:#6b7280;">Score: {total}/72 ({pct}%)</small>
                <hr style="border-color:#d1d5db;margin:14px 0 10px;">
                <p style="color:#374151;margin:0;font-size:0.88rem;">
                    <strong>Recommendation:</strong>
                    {"Regular monitoring and therapy sessions are advised."
                      if pct >= 67 else
                      "Continue current management plan and check in with your clinician."
                      if pct >= 33 else
                      "Maintain healthy routines and scheduled follow-ups."}
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ── Appointments Tab ───────────────────────────────────────────────────────
    with tab_appts:
        if not appts:
            st.info("No appointments yet. Book one from the Appointments page.")
        else:
            # Upcoming
            if upcoming:
                st.markdown("#### Upcoming Appointments")
                for a in upcoming[:5]:
                    st.markdown(f"""
                    <div class="card" style="border-left:4px solid #1d4ed8;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <strong style="font-size:1rem;">{a['appt_date']} at {a['appt_time']}</strong><br>
                                <span style="color:#64748b;font-size:0.85rem;">
                                    Token: <code style="background:#f1f5f9;padding:2px 8px;
                                    border-radius:4px;">{a['token']}</code>
                                    &nbsp;|&nbsp; {a.get('reason') or 'General Appointment'}
                                </span>
                            </div>
                            <div>{_status_badge(a['status'])}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # All history
            st.markdown("#### Appointment History")
            adf = pd.DataFrame(appts)[["token","appt_date","appt_time","reason","status","created_at"]]
            adf.columns = ["Token", "Date", "Time", "Reason", "Status", "Booked On"]
            st.dataframe(adf, use_container_width=True, hide_index=True)

    # ── Reports Tab ────────────────────────────────────────────────────────────
    with tab_reports:
        if not reports:
            st.info("No assessment reports generated yet.")
        else:
            for r in reports[:5]:
                with st.expander(
                    f"Report — {r['generated_at'][:10]}  |  Risk Score: {r.get('risk_score',0):.1f}"
                ):
                    c1, c2 = st.columns(2)
                    c1.metric("Risk Score",          f"{r.get('risk_score', 0):.1f}")
                    c2.metric("Classification",       r.get("final_classification") or "—")
                    if r.get("questionnaire_summary"):
                        st.markdown(f"**Questionnaire:** {r['questionnaire_summary']}")
                    if r.get("eeg_interpretation"):
                        st.markdown(f"**EEG:** {r['eeg_interpretation']}")
                    if r.get("activity_summary"):
                        st.markdown(f"**Activities:** {r['activity_summary']}")
