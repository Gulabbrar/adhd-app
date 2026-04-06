"""modules/patient_assessment.py — Self-assessment for patients"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from database import save_questionnaire, get_questionnaires, get_user_patient

# ── DSM-5 18-item questionnaire (patient-friendly phrasing) ───────────────────
INATTENTION_QUESTIONS = [
    "I make careless mistakes or miss details in my work or daily tasks.",
    "I find it hard to keep my attention on tasks or activities for long.",
    "People say I seem to not be listening when they talk to me directly.",
    "I start tasks but struggle to follow through and finish them.",
    "I find it difficult to organize my tasks, schedule, or belongings.",
    "I avoid or put off tasks that need long periods of mental focus.",
    "I frequently lose things I need (keys, phone, documents, etc.).",
    "I get easily distracted by things happening around me.",
    "I forget things in my daily routine (appointments, chores, calls).",
]

HYPERACTIVITY_QUESTIONS = [
    "I fidget with my hands or feet, or squirm when I'm seated.",
    "I get up from my seat in situations where I'm expected to stay seated.",
    "I feel restless or have an urge to move around in calm situations.",
    "I find it hard to do quiet activities like reading or relaxing.",
    "I often feel like I'm always 'on the go' or driven by a motor.",
    "I talk too much in conversations or social situations.",
    "I blurt out answers or finish others' sentences before they finish.",
    "I find it hard to wait for my turn in lines or conversations.",
    "I interrupt others or insert myself into conversations or activities.",
]

SCALE      = {0: "Never", 1: "Rarely", 2: "Sometimes", 3: "Often", 4: "Very Often"}
SCALE_COLS = {0: "#2e7d32", 1: "#558b2f", 2: "#f57f17", 3: "#e65100", 4: "#c62828"}


def _score_to_risk(total: int) -> str:
    if total >= 48:  return "High Risk"
    if total >= 24:  return "Moderate Risk"
    return "Low Risk"


def _risk_color(risk: str) -> str:
    return {"High Risk": "#c62828", "Moderate Risk": "#f57f17",
            "Low Risk": "#2e7d32"}.get(risk, "#1565c0")


def render_patient_assessment():
    st.markdown('<h2 class="page-title">📋 ADHD Self-Assessment</h2>',
                unsafe_allow_html=True)

    user    = st.session_state.user
    patient = get_user_patient(user["id"])
    if not patient:
        st.error("Patient profile not found.")
        return

    pid = patient["id"]

    tab_take, tab_history = st.tabs(["Take Assessment", "My History"])

    # ── Take Assessment ────────────────────────────────────────────────────────
    with tab_take:
        st.markdown(f"""
        <div class="card">
            <b>👤 {patient['name']}</b> &nbsp;|&nbsp;
            <code>{patient.get('patient_uid') or '—'}</code><br><br>
            Answer each question honestly based on how often the behaviour
            has occurred <b>over the past 6 months</b>.<br>
            <small style="color:#64748b;">
                0 = Never &nbsp; 1 = Rarely &nbsp; 2 = Sometimes &nbsp;
                3 = Often &nbsp; 4 = Very Often
            </small>
        </div>
        """, unsafe_allow_html=True)

        responses: dict = {}

        with st.form("patient_adhd_form"):

            # ── Part A — Inattention ───────────────────────────────────────────
            st.markdown("### Part A — Attention & Focus")
            st.markdown(
                "<div style='display:flex;gap:8px;margin-bottom:4px;padding-left:4px;'>"
                + "".join(
                    f"<span style='flex:1;text-align:center;font-size:0.72rem;font-weight:600;"
                    f"color:{SCALE_COLS[v]};'>{SCALE[v]}</span>"
                    for v in SCALE
                )
                + "</div>",
                unsafe_allow_html=True,
            )
            for i, q in enumerate(INATTENTION_QUESTIONS, start=1):
                st.markdown(
                    f'<div class="q-card"><span class="q-num">A{i}</span> {q}</div>',
                    unsafe_allow_html=True,
                )
                responses[f"inatt_{i}"] = st.radio(
                    f"A{i}", options=list(SCALE.keys()),
                    format_func=lambda v: SCALE[v],
                    horizontal=True, key=f"pa_inatt_{i}",
                    label_visibility="collapsed",
                )

            st.markdown("---")

            # ── Part B — Hyperactivity ─────────────────────────────────────────
            st.markdown("### Part B — Activity & Impulse Control")
            st.markdown(
                "<div style='display:flex;gap:8px;margin-bottom:4px;padding-left:4px;'>"
                + "".join(
                    f"<span style='flex:1;text-align:center;font-size:0.72rem;font-weight:600;"
                    f"color:{SCALE_COLS[v]};'>{SCALE[v]}</span>"
                    for v in SCALE
                )
                + "</div>",
                unsafe_allow_html=True,
            )
            for i, q in enumerate(HYPERACTIVITY_QUESTIONS, start=1):
                st.markdown(
                    f'<div class="q-card"><span class="q-num">B{i}</span> {q}</div>',
                    unsafe_allow_html=True,
                )
                responses[f"hyper_{i}"] = st.radio(
                    f"B{i}", options=list(SCALE.keys()),
                    format_func=lambda v: SCALE[v],
                    horizontal=True, key=f"pa_hyper_{i}",
                    label_visibility="collapsed",
                )

            submitted = st.form_submit_button(
                "Submit My Assessment", use_container_width=True
            )

        if submitted:
            inatt_score = sum(responses[f"inatt_{i}"] for i in range(1, 10))
            hyper_score = sum(responses[f"hyper_{i}"] for i in range(1, 10))
            total_score = inatt_score + hyper_score
            risk_level  = _score_to_risk(total_score)
            session_id  = datetime.now().strftime("SELF_%Y%m%d_%H%M%S")

            save_questionnaire(pid, session_id, responses,
                               total_score, inatt_score, hyper_score, risk_level)

            rc = _risk_color(risk_level)
            pct = int(total_score / 72 * 100)

            # ── Result banner ──────────────────────────────────────────────────
            st.markdown(f"""
            <div style="background:{rc}18;border:2px solid {rc};border-radius:14px;
                        padding:24px;text-align:center;margin-top:16px;">
                <div style="font-size:2rem;font-weight:800;color:{rc};">{risk_level}</div>
                <div style="font-size:1rem;color:#333;margin-top:6px;">
                    Total Score: <b>{total_score}/72</b> &nbsp;|&nbsp;
                    Attention: <b>{inatt_score}/36</b> &nbsp;|&nbsp;
                    Activity: <b>{hyper_score}/36</b>
                </div>
                <div style="background:#e5e7eb;border-radius:50px;height:10px;margin:14px auto;max-width:300px;">
                    <div style="background:{rc};width:{pct}%;height:10px;border-radius:50px;"></div>
                </div>
                <small style="color:#6b7280;">Your score: {total_score}/72 ({pct}%)</small>
            </div>
            """, unsafe_allow_html=True)

            # ── Radar chart ────────────────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 1])
            with col1:
                inatt_vals = [responses[f"inatt_{i}"] for i in range(1, 10)]
                hyper_vals = [responses[f"hyper_{i}"] for i in range(1, 10)]
                cats_a     = [f"A{i}" for i in range(1, 10)] + ["A1"]
                cats_b     = [f"B{i}" for i in range(1, 10)] + ["B1"]

                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=inatt_vals + [inatt_vals[0]], theta=cats_a,
                    name="Attention", fill="toself",
                    line=dict(color="#1565c0", width=2),
                ))
                fig.add_trace(go.Scatterpolar(
                    r=hyper_vals + [hyper_vals[0]], theta=cats_b,
                    name="Activity/Impulse", fill="toself",
                    line=dict(color="#c62828", width=2),
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(range=[0, 4])),
                    paper_bgcolor="white", height=300,
                    font=dict(family="Inter", size=11),
                    legend=dict(bgcolor="white"),
                    margin=dict(t=20, b=20, l=20, r=20),
                )
                st.plotly_chart(fig, use_container_width=True, key="pa_radar")

            with col2:
                # Domain bar comparison
                fig2 = go.Figure(go.Bar(
                    x=["Attention (A)", "Activity/Impulse (B)"],
                    y=[inatt_score, hyper_score],
                    marker_color=["#1565c0", "#c62828"],
                    text=[f"{inatt_score}/36", f"{hyper_score}/36"],
                    textposition="outside",
                ))
                fig2.add_hline(y=18, line_dash="dash", line_color="#f57f17",
                               annotation_text="Mid threshold")
                fig2.update_layout(
                    yaxis=dict(range=[0, 42], title="Score"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc",
                    height=300, font=dict(family="Inter", size=11),
                    margin=dict(t=20, b=20, l=40, r=20),
                )
                st.plotly_chart(fig2, use_container_width=True, key="pa_bar")

            # ── Personalised interpretation ────────────────────────────────────
            top_inatt = sorted(
                range(1, 10),
                key=lambda i: responses[f"inatt_{i}"], reverse=True
            )[:3]
            top_hyper = sorted(
                range(1, 10),
                key=lambda i: responses[f"hyper_{i}"], reverse=True
            )[:3]

            st.markdown(f"""
            <div class="card" style="margin-top:12px;">
                <b>📊 Your Personalised Insights</b><br><br>
                <b>Attention areas to watch:</b><br>
                {"<br>".join(f"&nbsp;&nbsp;• {INATTENTION_QUESTIONS[i-1]}" for i in top_inatt
                             if responses[f'inatt_{i}'] >= 2)}
                <br><br>
                <b>Activity/Impulse areas to watch:</b><br>
                {"<br>".join(f"&nbsp;&nbsp;• {HYPERACTIVITY_QUESTIONS[i-1]}" for i in top_hyper
                             if responses[f'hyper_{i}'] >= 2)}
                <br><br>
                <small style="color:#64748b;">
                    ⚕️ <b>Note:</b> This is a self-screening tool, not a clinical diagnosis.
                    Please share these results with your doctor or clinician.
                </small>
            </div>
            """, unsafe_allow_html=True)

            st.success("Assessment saved! View your trend in the 'My History' tab.")

    # ── History Tab ────────────────────────────────────────────────────────────
    with tab_history:
        history = get_questionnaires(pid)
        if not history:
            st.info("No assessments yet. Take your first assessment above.")
            return

        # Summary metrics
        latest = history[0]
        rc     = _risk_color(latest["risk_level"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Assessments Taken", len(history))
        c2.metric("Latest Total",      f"{latest['total_score']}/72")
        c3.metric("Attention Score",   f"{latest['inatt_score']}/36")
        c4.metric("Activity Score",    f"{latest['hyper_score']}/36")

        st.markdown(f"""
        <div style="background:{rc}18;border-left:4px solid {rc};border-radius:8px;
                    padding:10px 16px;margin:8px 0 16px;">
            <b>Current Risk Level: </b>
            <span style="color:{rc};font-weight:700;">{latest['risk_level']}</span>
            &nbsp;|&nbsp; Last assessed: {latest['assessed_at'][:10]}
        </div>
        """, unsafe_allow_html=True)

        # History table
        hdf = pd.DataFrame(history)[[
            "total_score", "inatt_score", "hyper_score", "risk_level", "assessed_at"
        ]].copy()
        hdf.columns = ["Total", "Attention", "Activity", "Risk Level", "Date"]
        hdf["Date"] = hdf["Date"].str[:16]
        st.dataframe(hdf, use_container_width=True, hide_index=True)

        # Trend chart (shown if 2+ assessments)
        if len(history) >= 2:
            st.markdown("#### My Score Trend")
            df = pd.DataFrame(history[::-1])  # oldest first

            fig_t = go.Figure()
            fig_t.add_trace(go.Scatter(
                x=df["assessed_at"], y=df["total_score"],
                name="Total Score", mode="lines+markers",
                line=dict(color="#0d47a1", width=2.5),
                marker=dict(size=8),
            ))
            fig_t.add_trace(go.Scatter(
                x=df["assessed_at"], y=df["inatt_score"],
                name="Attention", mode="lines+markers",
                line=dict(color="#1976d2", width=1.5, dash="dot"),
                marker=dict(size=6),
            ))
            fig_t.add_trace(go.Scatter(
                x=df["assessed_at"], y=df["hyper_score"],
                name="Activity/Impulse", mode="lines+markers",
                line=dict(color="#c62828", width=1.5, dash="dot"),
                marker=dict(size=6),
            ))
            fig_t.add_hrect(y0=48, y1=72, fillcolor="#fee2e2",
                            opacity=0.3, line_width=0, annotation_text="High Risk Zone")
            fig_t.add_hrect(y0=24, y1=48, fillcolor="#fef3c7",
                            opacity=0.3, line_width=0, annotation_text="Moderate Zone")
            fig_t.add_hrect(y0=0,  y1=24, fillcolor="#dcfce7",
                            opacity=0.3, line_width=0, annotation_text="Low Risk Zone")
            fig_t.update_layout(
                yaxis=dict(range=[0, 75], title="Score"),
                paper_bgcolor="white", plot_bgcolor="white",
                height=320, font=dict(family="Inter", size=11),
                legend=dict(bgcolor="white", bordercolor="#e2e8f0", borderwidth=1),
                margin=dict(t=20, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_t, use_container_width=True, key="pa_trend")

            # Progress message
            first  = history[-1]["total_score"]
            latest_score = history[0]["total_score"]
            diff   = latest_score - first
            if diff < 0:
                st.success(f"Your score improved by {abs(diff)} points since your first assessment.")
            elif diff > 0:
                st.warning(f"Your score has increased by {diff} points since your first assessment. "
                           "Consider discussing this with your clinician.")
            else:
                st.info("Your score is stable since your first assessment.")
