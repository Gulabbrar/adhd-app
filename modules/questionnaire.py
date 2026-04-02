"""modules/questionnaire.py — ADHD Behavioral Questionnaire"""
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from database import save_questionnaire, get_questionnaires

# ── DSM-5 Based 18-Item ADHD Questionnaire ────────────────────────────────────
INATTENTION_QUESTIONS = [
    "Fails to give close attention to details or makes careless mistakes in work/activities.",
    "Has difficulty sustaining attention in tasks or leisure activities.",
    "Does not seem to listen when spoken to directly.",
    "Does not follow through on instructions; fails to finish tasks.",
    "Has difficulty organizing tasks and activities.",
    "Avoids or is reluctant to engage in tasks requiring sustained mental effort.",
    "Loses things necessary for tasks (keys, tools, documents, phone).",
    "Is easily distracted by unrelated stimuli or thoughts.",
    "Is forgetful in daily activities and routines.",
]

HYPERACTIVITY_QUESTIONS = [
    "Fidgets with hands/feet or squirms in seat.",
    "Leaves seat in situations where remaining seated is expected.",
    "Runs about or climbs in situations where it is inappropriate.",
    "Is unable to play or engage in leisure activities quietly.",
    "Is 'on the go' or acts as if 'driven by a motor'.",
    "Talks excessively.",
    "Blurts out answers before questions have been completed.",
    "Has difficulty waiting their turn.",
    "Interrupts or intrudes on others (conversations, games, activities).",
]

SCALE = {0: "Never", 1: "Rarely", 2: "Sometimes", 3: "Often", 4: "Very Often"}
SCALE_COLORS = {0: "#2e7d32", 1: "#558b2f", 2: "#f57f17", 3: "#e65100", 4: "#c62828"}


def _score_to_risk(total: int, inatt: int, hyper: int) -> str:
    """Classify ADHD risk based on total score and DSM-5 criteria."""
    # DSM-5: ≥6 items scoring ≥2 in a domain is clinically significant
    # Using score thresholds here for simplicity
    if total >= 48:
        return "High Risk"
    elif total >= 24:
        return "Moderate Risk"
    else:
        return "Low Risk"


def _risk_color(risk: str) -> str:
    return {"High Risk": "#c62828", "Moderate Risk": "#f57f17", "Low Risk": "#2e7d32"}.get(risk, "#1565c0")


def render_questionnaire():
    st.markdown('<h2 class="page-title">📋 ADHD Questionnaire</h2>', unsafe_allow_html=True)

    patient = st.session_state.get("current_patient")
    if not patient:
        st.warning("Please select a patient from the sidebar first.")
        return

    pid  = patient["id"]
    name = patient["name"]

    tab_take, tab_history = st.tabs(["Take Assessment", "History"])

    # ── Tab 1: Assessment Form ──────────────────────────────────────────────
    with tab_take:
        st.markdown(f"""
        <div class="card">
        <b>Patient:</b> {name}<br>
        <b>Instructions:</b> Rate each behaviour on a 0–4 scale based on how often it occurs.<br>
        <small>0=Never &nbsp; 1=Rarely &nbsp; 2=Sometimes &nbsp; 3=Often &nbsp; 4=Very Often</small>
        </div>
        """, unsafe_allow_html=True)

        responses: dict = {}

        with st.form("adhd_form"):
            # ── Inattention Domain ──────────────────────────────────────────
            st.markdown("### Part A — Inattention")
            st.markdown(
                "<div style='display:flex;gap:8px;margin-bottom:4px;padding-left:4px;'>"
                + "".join(
                    f"<span style='flex:1;text-align:center;font-size:0.72rem;font-weight:600;"
                    f"color:{SCALE_COLORS[v]};'>{SCALE[v]}</span>"
                    for v in SCALE
                )
                + "</div>",
                unsafe_allow_html=True,
            )
            for i, q in enumerate(INATTENTION_QUESTIONS, start=1):
                st.markdown(f"""<div class="q-card">
                    <span class="q-num">A{i}</span> {q}</div>""", unsafe_allow_html=True)
                val = st.radio(
                    f"A{i}",
                    options=list(SCALE.keys()),
                    format_func=lambda v: SCALE[v],
                    horizontal=True,
                    key=f"inatt_{i}",
                    label_visibility="collapsed",
                )
                responses[f"inatt_{i}"] = val

            st.markdown("---")

            # ── Hyperactivity/Impulsivity Domain ───────────────────────────
            st.markdown("### Part B — Hyperactivity / Impulsivity")
            st.markdown(
                "<div style='display:flex;gap:8px;margin-bottom:4px;padding-left:4px;'>"
                + "".join(
                    f"<span style='flex:1;text-align:center;font-size:0.72rem;font-weight:600;"
                    f"color:{SCALE_COLORS[v]};'>{SCALE[v]}</span>"
                    for v in SCALE
                )
                + "</div>",
                unsafe_allow_html=True,
            )
            for i, q in enumerate(HYPERACTIVITY_QUESTIONS, start=1):
                st.markdown(f"""<div class="q-card">
                    <span class="q-num">B{i}</span> {q}</div>""", unsafe_allow_html=True)
                val = st.radio(
                    f"B{i}",
                    options=list(SCALE.keys()),
                    format_func=lambda v: SCALE[v],
                    horizontal=True,
                    key=f"hyper_{i}",
                    label_visibility="collapsed",
                )
                responses[f"hyper_{i}"] = val

            submitted = st.form_submit_button("Submit Assessment", use_container_width=True)

        if submitted:
            inatt_score = sum(responses[f"inatt_{i}"] for i in range(1, 10))
            hyper_score = sum(responses[f"hyper_{i}"] for i in range(1, 10))
            total_score = inatt_score + hyper_score
            risk_level  = _score_to_risk(total_score, inatt_score, hyper_score)
            session_id  = st.session_state.get("eeg_session_id",
                            datetime.now().strftime("QST_%Y%m%d_%H%M%S"))

            save_questionnaire(pid, session_id, responses,
                               total_score, inatt_score, hyper_score, risk_level)

            risk_color = _risk_color(risk_level)

            st.markdown(f"""
            <div style="background:{risk_color}18;border:2px solid {risk_color};
                        border-radius:12px;padding:20px;text-align:center;margin-top:16px;">
                <div style="font-size:2rem;font-weight:800;color:{risk_color};">{risk_level}</div>
                <div style="font-size:1rem;color:#333;margin-top:4px;">
                    Total Score: <b>{total_score}/72</b> &nbsp;|&nbsp;
                    Inattention: <b>{inatt_score}/36</b> &nbsp;|&nbsp;
                    Hyperactivity: <b>{hyper_score}/36</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Score Radar ─────────────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            fig = go.Figure()
            inatt_vals = [responses[f"inatt_{i}"] for i in range(1, 10)]
            hyper_vals = [responses[f"hyper_{i}"] for i in range(1, 10)]
            cats = [f"A{i}" for i in range(1, 10)] + [f"A1"]

            fig.add_trace(go.Scatterpolar(
                r=inatt_vals + [inatt_vals[0]],
                theta=cats, name="Inattention",
                fill="toself", line=dict(color="#1565c0", width=2),
            ))
            fig.add_trace(go.Scatterpolar(
                r=hyper_vals + [hyper_vals[0]],
                theta=[f"B{i}" for i in range(1, 10)] + ["B1"],
                name="Hyperactivity",
                fill="toself", line=dict(color="#c62828", width=2),
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(range=[0, 4])),
                paper_bgcolor="white", height=360,
                font=dict(family="Inter", size=11),
                legend=dict(bgcolor="white"),
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True, key="q_radar")

            # ── Interpretation ──────────────────────────────────────────────
            st.markdown(f"""
            <div class="card">
            <b>Clinical Interpretation:</b><br>
            {'✅ Inattention symptoms are within normal range.' if inatt_score < 18 else '⚠️ Elevated inattention symptoms detected.'}
            {'✅ Hyperactivity/Impulsivity within normal range.' if hyper_score < 18 else '⚠️ Elevated hyperactivity/impulsivity detected.'}
            <br><small>DSM-5 threshold: ≥5 items scoring ≥2 in a domain is clinically significant.</small>
            </div>
            """, unsafe_allow_html=True)

    # ── Tab 2: History ──────────────────────────────────────────────────────
    with tab_history:
        history = get_questionnaires(pid)
        if not history:
            st.info("No questionnaire history for this patient yet.")
            return

        import pandas as pd
        hdf = pd.DataFrame(history)[["session_id","total_score","inatt_score","hyper_score","risk_level","assessed_at"]]
        hdf.columns = ["Session", "Total", "Inattention", "Hyperactivity", "Risk Level", "Date"]
        st.dataframe(hdf, use_container_width=True, hide_index=True)

        # ── Score Trend ─────────────────────────────────────────────────────
        if len(history) > 1:
            fdf = pd.DataFrame(history).sort_values("assessed_at")
            fig_t = go.Figure()
            fig_t.add_trace(go.Scatter(x=fdf["assessed_at"], y=fdf["inatt_score"],
                                        name="Inattention", mode="lines+markers",
                                        line=dict(color="#1565c0", width=2)))
            fig_t.add_trace(go.Scatter(x=fdf["assessed_at"], y=fdf["hyper_score"],
                                        name="Hyperactivity", mode="lines+markers",
                                        line=dict(color="#c62828", width=2)))
            fig_t.update_layout(
                title="Score Trend Over Time",
                yaxis=dict(range=[0, 36], title="Score"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=280,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_t, use_container_width=True, key="q_trend")
