"""modules/patient_report.py — Personal ADHD progress report for patients"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import math
from io import BytesIO
from datetime import datetime

from database import (
    get_user_patient, get_questionnaires, get_reports, save_report, add_review
)


# ── Helpers ────────────────────────────────────────────────────────────────────
def _safe(val, default=0.0):
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _risk_color(risk: str) -> str:
    return {"High ADHD Risk": "#c62828",
            "Moderate ADHD Risk": "#f57f17",
            "Low ADHD Risk": "#2e7d32"}.get(risk, "#1565c0")


def _classify(score: float) -> tuple:
    if score >= 60:   return "High ADHD Risk",     "#c62828"
    if score >= 33:   return "Moderate ADHD Risk", "#f57f17"
    return "Low ADHD Risk",  "#2e7d32"


def _gauge(value: float, title: str, color: str) -> go.Figure:
    value = _safe(value)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 13, "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar":  {"color": color},
            "steps": [
                {"range": [0,  33], "color": "#e8f5e9"},
                {"range": [33, 60], "color": "#fff3e0"},
                {"range": [60, 100],"color": "#ffebee"},
            ],
            "threshold": {"line": {"color": "#333", "width": 3},
                          "thickness": 0.75, "value": value},
        },
        number={"suffix": "%", "font": {"size": 26}},
    ))
    fig.update_layout(height=200, paper_bgcolor="white",
                      margin=dict(t=40, b=10, l=20, r=20),
                      font=dict(family="Inter"))
    return fig


# ── Review dialog (Streamlit 1.32+) ──────────────────────────────────────────
@st.dialog("Share Your Feedback")
def _review_dialog(patient_id: int, user_id: int):
    st.markdown(
        "Your assessment report is ready. "
        "We would appreciate your feedback about the platform experience."
    )
    st.markdown("---")
    rating = st.select_slider(
        "Overall Rating",
        options=[1, 2, 3, 4, 5],
        value=5,
        format_func=lambda x: f"{'★' * x}{'☆' * (5 - x)}  ({x}/5)"
    )
    comment = st.text_area(
        "Comments",
        placeholder="Describe your experience with the ADHD assessment process...",
        height=100
    )
    c1, c2 = st.columns(2)
    if c1.button("Submit Feedback", use_container_width=True):
        if comment.strip():
            add_review(patient_id=patient_id, user_id=user_id,
                       rating=rating, comment=comment.strip())
            st.session_state["review_dialog_done"] = True
            st.success("Thank you for your feedback!")
            st.rerun()
        else:
            st.warning("Please write a comment before submitting.")
    if c2.button("Maybe Later", use_container_width=True):
        st.session_state["review_dialog_done"] = True
        st.rerun()


def _pdf_bytes(patient: dict, report: dict) -> bytes:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as C
    from reportlab.lib.units import inch

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(8.5*inch, 11*inch),
                             topMargin=0.75*inch, bottomMargin=0.75*inch,
                             leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("t", parent=styles["Title"],  fontSize=18, spaceAfter=6)
    body_s  = ParagraphStyle("b", parent=styles["Normal"], fontSize=10, spaceAfter=4, leading=14)
    head_s  = ParagraphStyle("h", parent=styles["Heading2"], fontSize=12, spaceAfter=4,
                              textColor=C.HexColor("#1565c0"))
    story = []

    story.append(Paragraph("Personal ADHD Progress Report", title_s))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_s))
    story.append(Spacer(1, 0.15*inch))

    uid  = patient.get("patient_uid") or "—"
    data = [
        ["Name",   patient.get("name",""), "Patient ID", uid],
        ["Age",    str(patient.get("age","")), "Gender", patient.get("gender","")],
    ]
    t = Table(data, colWidths=[1*inch, 2*inch, 1.2*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), C.HexColor("#e3f2fd")),
        ("BACKGROUND", (2,0), (2,-1), C.HexColor("#e3f2fd")),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.5, C.grey),
        ("PADDING",    (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15*inch))

    clf = report.get("final_classification", "")
    rs  = report.get("risk_score", 0)
    col = "#c62828" if "High" in clf else "#f57f17" if "Moderate" in clf else "#2e7d32"

    story.append(Paragraph("ADHD Risk Classification", head_s))
    story.append(Paragraph(
        f"<font color='{col}'><b>{clf}</b></font> "
        f"— Overall Risk Score: {rs:.1f}%",
        body_s
    ))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("Score Breakdown", head_s))
    rows = [["Assessment Component", "Score"]]
    if _safe(report.get("eeg_score", 0)) > 0:
        rows.append(["EEG Assessment",    f"{_safe(report.get('eeg_score',0)):.1f}%"])
    rows.append(["ADHD Questionnaire",    f"{_safe(report.get('questionnaire_score',0)):.1f}%"])
    rows.append(["Emotion Monitoring",    f"{_safe(report.get('emotion_score',0)):.1f}%"])
    rows.append(["Cognitive Activities",  f"{_safe(report.get('activity_score',0)):.1f}%"])

    t2 = Table(rows, colWidths=[3.5*inch, 2*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C.HexColor("#1565c0")),
        ("TEXTCOLOR",  (0,0), (-1,0), C.white),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.5, C.grey),
        ("PADDING",    (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [C.white, C.HexColor("#f0f4f8")]),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.15*inch))

    for heading, key in [
        ("EEG Analysis",               "eeg_interpretation"),
        ("Questionnaire Analysis",     "questionnaire_summary"),
        ("Emotion Monitoring",         "emotion_summary"),
        ("Cognitive Activity",         "activity_summary"),
    ]:
        text = report.get(key, "") or ""
        if text:
            story.append(Paragraph(heading, head_s))
            story.append(Paragraph(text, body_s))
            story.append(Spacer(1, 0.08*inch))

    doc.build(story)
    return buf.getvalue()


# ── Section card renderer ─────────────────────────────────────────────────────
def _section_card(title: str, text: str, border_color: str = "#1565c0"):
    if not text:
        return
    st.markdown(f"""
    <div class="card" style="border-left:4px solid {border_color};margin-bottom:10px;">
        <div style="font-size:0.7rem;text-transform:uppercase;font-weight:700;
                    color:#64748b;letter-spacing:0.6px;margin-bottom:6px;">{title}</div>
        <div style="color:#374151;font-size:0.9rem;line-height:1.6;">{text}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Main render ────────────────────────────────────────────────────────────────
def render_patient_report():
    st.markdown('<h2 class="page-title">My ADHD Assessment Report</h2>',
                unsafe_allow_html=True)

    user    = st.session_state.user
    patient = get_user_patient(user["id"])
    if not patient:
        st.error("Patient profile not found.")
        return

    pid = patient["id"]
    all_reports = get_reports(pid)
    qs          = get_questionnaires(pid)

    # ── Find collaborative reports (generated by clinician, include EEG / multi-modal) ──
    collab_reports = [r for r in all_reports if _safe(r.get("eeg_score", 0)) > 0
                      or (r.get("eeg_interpretation") or "").strip()]

    if not collab_reports and not qs:
        st.warning(
            "No assessment data available yet. "
            "Complete at least one Self-Assessment or ask your clinician to run an evaluation."
        )
        if st.button("Go to Self-Assessment"):
            st.session_state["patient_page"] = "Self-Assessment"
            st.rerun()
        return

    # ── Show review dialog immediately when collaborative report is available ──
    if collab_reports and not st.session_state.get("review_dialog_done"):
        _review_dialog(pid, user["id"])

    tab_collab, tab_self, tab_hist = st.tabs([
        "Collaborative Assessment", "Self-Assessment", "Report History"
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Collaborative Report (Clinician-generated, includes EEG)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_collab:
        if not collab_reports:
            st.info(
                "No clinician-generated report with EEG data is available yet. "
                "Ask your clinician to complete the EEG assessment and generate your collaborative report."
            )
        else:
            latest = collab_reports[0]
            clf    = latest.get("final_classification", "—")
            rc     = _risk_color(clf)
            rs     = _safe(latest.get("risk_score", 0))

            # ── Classification banner ──────────────────────────────────────────
            eeg_s  = _safe(latest.get("eeg_score", 0))
            q_s    = _safe(latest.get("questionnaire_score", 0))
            emo_s  = _safe(latest.get("emotion_score", 0))
            act_s  = _safe(latest.get("activity_score", 0))
            has_eeg = eeg_s > 0

            st.markdown(f"""
            <div style="background:{rc}12;border:2px solid {rc};border-radius:14px;
                        padding:24px;text-align:center;margin-bottom:20px;">
                <div style="font-size:0.72rem;text-transform:uppercase;font-weight:700;
                            color:#64748b;letter-spacing:0.8px;margin-bottom:6px;">
                    Clinician Assessment — {latest.get('generated_at','')[:10]}
                </div>
                <div style="font-size:2rem;font-weight:800;color:{rc};">{clf}</div>
                <div style="color:#374151;margin-top:6px;font-size:0.95rem;">
                    Overall Risk Score: <strong>{rs:.1f}%</strong>
                </div>
                <div style="color:#64748b;margin-top:4px;font-size:0.8rem;">
                    Patient: {patient['name']} &nbsp;|&nbsp;
                    {"EEG · Questionnaire · Emotion · Activity" if has_eeg else "Questionnaire · Emotion · Activity"}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Component gauges ───────────────────────────────────────────────
            if has_eeg:
                g1, g2, g3, g4 = st.columns(4)
                g1.plotly_chart(_gauge(eeg_s,  "EEG",           "#7b1fa2"), use_container_width=True, key="pr_cg0")
                g2.plotly_chart(_gauge(q_s,    "Questionnaire", "#c62828"), use_container_width=True, key="pr_cg1")
                g3.plotly_chart(_gauge(emo_s,  "Emotion",       "#f57f17"), use_container_width=True, key="pr_cg2")
                g4.plotly_chart(_gauge(act_s,  "Activity",      "#2e7d32"), use_container_width=True, key="pr_cg3")
            else:
                g1, g2, g3 = st.columns(3)
                g1.plotly_chart(_gauge(q_s,   "Questionnaire", "#c62828"), use_container_width=True, key="pr_cg1")
                g2.plotly_chart(_gauge(emo_s, "Emotion",       "#f57f17"), use_container_width=True, key="pr_cg2")
                g3.plotly_chart(_gauge(act_s, "Activity",      "#2e7d32"), use_container_width=True, key="pr_cg3")

            st.markdown("---")
            st.markdown("#### Component Analysis")

            _section_card("EEG Neurological Analysis",
                          latest.get("eeg_interpretation", ""), "#7b1fa2")
            _section_card("Questionnaire Analysis",
                          latest.get("questionnaire_summary", ""), "#1565c0")
            _section_card("Emotion Monitoring Analysis",
                          latest.get("emotion_summary", ""), "#f57f17")
            _section_card("Cognitive Activity Analysis",
                          latest.get("activity_summary", ""), "#2e7d32")

            # ── Clinical recommendation ────────────────────────────────────────
            recs = {
                "High ADHD Risk": (
                    "Your assessment results indicate significant ADHD-related indicators. "
                    "A detailed clinical consultation is strongly recommended. "
                    "Discuss medication options, structured therapy, and coping strategies with your doctor."
                ),
                "Moderate ADHD Risk": (
                    "Your results indicate moderate ADHD-related symptoms. "
                    "Regular monitoring and clinician follow-up is advised. "
                    "Behavioural strategies and structured routines can be highly beneficial."
                ),
                "Low ADHD Risk": (
                    "Your results are within the low-risk range. "
                    "Continue healthy routines, adequate sleep, and scheduled check-ins. "
                    "Reassess every 3–6 months or if symptoms change."
                ),
            }
            rec_text = recs.get(clf, "Consult your clinician for personalised guidance.")
            st.markdown(f"""
            <div class="card" style="border-left:4px solid {rc};margin-top:12px;">
                <div style="font-size:0.7rem;text-transform:uppercase;font-weight:700;
                            color:#64748b;letter-spacing:0.6px;margin-bottom:8px;">
                    Clinical Recommendation
                </div>
                <div style="color:#374151;font-size:0.9rem;line-height:1.6;">{rec_text}</div>
            </div>
            """, unsafe_allow_html=True)

            # ── PDF download ──────────────────────────────────────────────────
            st.markdown("---")
            try:
                pdf = _pdf_bytes(patient, latest)
                st.download_button(
                    "Download PDF Report",
                    data=pdf,
                    file_name=(f"ADHD_Report_{patient['name'].replace(' ','_')}"
                               f"_{latest.get('generated_at','')[:10]}.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.info("PDF unavailable — reportlab not installed.")
            except Exception as e:
                st.warning(f"PDF generation failed: {e}")


    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — Self-Assessment Report (questionnaire only)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_self:
        if not qs:
            st.info("No self-assessment completed yet.")
            if st.button("Go to Self-Assessment", key="pr_goto_qa"):
                st.session_state["patient_page"] = "Self-Assessment"
                st.rerun()
        else:
            latest_q = qs[0]
            q_score  = round(_safe(latest_q.get("total_score", 0)) / 72.0 * 100.0, 1)
            risk, rc = _classify(q_score)
            total    = int(_safe(latest_q.get("total_score", 0)))
            inatt    = int(_safe(latest_q.get("inatt_score", 0)))
            hyper    = int(_safe(latest_q.get("hyper_score", 0)))

            st.markdown(f"""
            <div style="background:{rc}12;border:2px solid {rc};border-radius:14px;
                        padding:20px;text-align:center;margin-bottom:20px;">
                <div style="font-size:1.8rem;font-weight:800;color:{rc};">{risk}</div>
                <div style="color:#374151;margin-top:6px;">
                    Risk Score: <strong>{q_score:.1f}%</strong> &nbsp;|&nbsp;
                    Based on {len(qs)} assessment{"s" if len(qs) > 1 else ""}
                </div>
            </div>
            """, unsafe_allow_html=True)

            g1, g2, g3 = st.columns(3)
            g1.plotly_chart(_gauge(q_score,           "Overall Risk", rc),        use_container_width=True, key="pr_sg1")
            g2.plotly_chart(_gauge(inatt / 36 * 100,  "Attention",    "#1565c0"), use_container_width=True, key="pr_sg2")
            g3.plotly_chart(_gauge(hyper / 36 * 100,  "Activity",     "#c62828"), use_container_width=True, key="pr_sg3")

            if len(qs) >= 2:
                st.markdown("#### Progress Over Time")
                df  = pd.DataFrame(qs[::-1])
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["total_score"],
                    name="Total Score", mode="lines+markers",
                    line=dict(color="#0d47a1", width=2.5), marker=dict(size=8),
                ))
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["inatt_score"],
                    name="Attention", mode="lines+markers",
                    line=dict(color="#1976d2", width=1.5, dash="dot"),
                ))
                fig.add_trace(go.Scatter(
                    x=df["assessed_at"], y=df["hyper_score"],
                    name="Activity/Impulse", mode="lines+markers",
                    line=dict(color="#c62828", width=1.5, dash="dot"),
                ))
                fig.add_hrect(y0=48, y1=72, fillcolor="#fee2e2", opacity=0.25, line_width=0)
                fig.add_hrect(y0=24, y1=48, fillcolor="#fef3c7", opacity=0.25, line_width=0)
                fig.add_hrect(y0=0,  y1=24, fillcolor="#dcfce7", opacity=0.25, line_width=0)
                fig.update_layout(
                    yaxis=dict(range=[0, 75], title="Score"),
                    paper_bgcolor="white", plot_bgcolor="white", height=300,
                    font=dict(family="Inter", size=11),
                    legend=dict(bgcolor="white"),
                    margin=dict(t=20, b=20, l=40, r=20),
                )
                st.plotly_chart(fig, use_container_width=True, key="pr_self_trend")

            recs = {
                "High ADHD Risk": (
                    "Your scores suggest significant ADHD symptoms. "
                    "We strongly recommend scheduling a detailed clinical assessment. "
                    "Discuss medication, therapy, and coping strategies with your doctor."
                ),
                "Moderate ADHD Risk": (
                    "Your scores indicate moderate ADHD-related symptoms. "
                    "Regular monitoring and follow-up with your clinician is advised."
                ),
                "Low ADHD Risk": (
                    "Your scores are within the low-risk range. "
                    "Continue healthy routines, adequate sleep, and scheduled check-ins."
                ),
            }
            st.markdown(f"""
            <div class="card" style="border-left:4px solid {rc};margin-top:8px;">
                <div style="font-size:0.7rem;text-transform:uppercase;font-weight:700;
                            color:#64748b;letter-spacing:0.6px;margin-bottom:6px;">
                    Personalised Recommendation
                </div>
                <div style="color:#374151;font-size:0.9rem;">{recs.get(risk, '')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            q_text = (f"Latest questionnaire score: {total}/72 ({latest_q.get('risk_level','')})."
                      f" Attention: {inatt}/36, Activity/Impulse: {hyper}/36.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save Report to My Records", use_container_width=True):
                    session_id = datetime.now().strftime("RPT_%Y%m%d_%H%M%S")
                    save_report(
                        patient_id=pid, session_id=session_id,
                        eeg_interpretation="", questionnaire_summary=q_text,
                        emotion_summary="", activity_summary="",
                        final_classification=risk, risk_score=q_score,
                        eeg_score=0.0, questionnaire_score=q_score,
                        emotion_score=0.0, activity_score=0.0,
                    )
                    st.success("Report saved. View it in the Report History tab.")
                    st.rerun()
            with c2:
                try:
                    report_dict = {
                        "final_classification": risk, "risk_score": q_score,
                        "questionnaire_score": q_score, "questionnaire_summary": q_text,
                    }
                    pdf = _pdf_bytes(patient, report_dict)
                    st.download_button(
                        "Download PDF Report",
                        data=pdf,
                        file_name=(f"ADHD_SelfReport_{patient['name'].replace(' ','_')}"
                                   f"_{datetime.now().strftime('%Y%m%d')}.pdf"),
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except ImportError:
                    st.info("PDF unavailable — reportlab not installed.")
                except Exception as e:
                    st.warning(f"PDF error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — Report History
    # ══════════════════════════════════════════════════════════════════════════
    with tab_hist:
        if not all_reports:
            st.info("No saved reports yet.")
            return

        for r in all_reports:
            rc2 = _risk_color(r.get("final_classification", ""))
            has_e = _safe(r.get("eeg_score", 0)) > 0
            label = (f"{'Collaborative' if has_e else 'Self'} Report"
                     f" — {r['generated_at'][:10]}"
                     f"  |  {r.get('final_classification','—')}"
                     f"  (Risk: {r.get('risk_score',0):.1f}%)")
            with st.expander(label):
                c1, c2 = st.columns(2)
                c1.metric("Risk Score",      f"{r.get('risk_score',0):.1f}%")
                c2.metric("Classification",   r.get("final_classification", "—"))
                if has_e:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("EEG",          f"{_safe(r.get('eeg_score',0)):.1f}%")
                    m2.metric("Questionnaire",f"{_safe(r.get('questionnaire_score',0)):.1f}%")
                    m3.metric("Emotion",      f"{_safe(r.get('emotion_score',0)):.1f}%")
                    m4.metric("Activity",     f"{_safe(r.get('activity_score',0)):.1f}%")
                if r.get("eeg_interpretation"):
                    st.markdown(f"**EEG:** {r['eeg_interpretation']}")
                if r.get("questionnaire_summary"):
                    st.markdown(f"**Questionnaire:** {r['questionnaire_summary']}")
                if r.get("emotion_summary"):
                    st.markdown(f"**Emotion:** {r['emotion_summary']}")
                if r.get("activity_summary"):
                    st.markdown(f"**Activity:** {r['activity_summary']}")

        if len(all_reports) >= 2:
            pf  = pd.DataFrame(all_reports[::-1])
            fig = go.Figure(go.Scatter(
                x=pf["generated_at"], y=pf["risk_score"],
                mode="lines+markers",
                line=dict(color="#c62828", width=2), marker=dict(size=8),
                fill="tozeroy", fillcolor="rgba(198,40,40,0.08)",
            ))
            fig.add_hline(y=60, line_dash="dash", line_color="#c62828",
                          annotation_text="High Risk")
            fig.add_hline(y=33, line_dash="dash", line_color="#f57f17",
                          annotation_text="Moderate")
            fig.update_layout(
                title="Risk Score Trend",
                yaxis=dict(range=[0, 105], title="Risk %"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=280,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig, use_container_width=True, key="pr_hist_trend")
