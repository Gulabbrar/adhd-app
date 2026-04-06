"""modules/patient_report.py — Personal ADHD progress report for patients"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import math
from io import BytesIO
from datetime import datetime

from database import (
    get_user_patient, get_questionnaires, get_reports, save_report
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

    # Patient info
    uid   = patient.get("patient_uid") or "—"
    data  = [
        ["Name",       patient.get("name",""), "Patient ID", uid],
        ["Age",        str(patient.get("age","")), "Gender", patient.get("gender","")],
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

    clf  = report.get("final_classification", "")
    rs   = report.get("risk_score", 0)
    col  = "#c62828" if "High" in clf else "#f57f17" if "Moderate" in clf else "#2e7d32"

    story.append(Paragraph("ADHD Risk Classification", head_s))
    story.append(Paragraph(
        f"<font color='#{col.lstrip('#')}'><b>{clf}</b></font> "
        f"— Overall Risk Score: {rs:.1f}%",
        body_s
    ))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("Score Breakdown", head_s))
    td = [
        ["Assessment Type", "Score"],
        ["ADHD Questionnaire", f"{report.get('questionnaire_score',0):.1f}%"],
    ]
    t2 = Table(td, colWidths=[3.5*inch, 2*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C.HexColor("#1565c0")),
        ("TEXTCOLOR",  (0,0), (-1,0), C.white),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.5, C.grey),
        ("PADDING",    (0,0), (-1,-1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph("Analysis", head_s))
    story.append(Paragraph(report.get("questionnaire_summary", "No data."), body_s))

    doc.build(story)
    return buf.getvalue()


# ── Main render ────────────────────────────────────────────────────────────────
def render_patient_report():
    st.markdown('<h2 class="page-title">📄 My ADHD Progress Report</h2>',
                unsafe_allow_html=True)

    user    = st.session_state.user
    patient = get_user_patient(user["id"])
    if not patient:
        st.error("Patient profile not found.")
        return

    pid = patient["id"]
    qs  = get_questionnaires(pid)

    if not qs:
        st.warning(
            "You have no assessment data yet. "
            "Please complete at least one ADHD Self-Assessment first."
        )
        if st.button("Go to Self-Assessment"):
            st.session_state["patient_page"] = "📋 Self-Assessment"
            st.rerun()
        return

    tab_gen, tab_hist = st.tabs(["Generate Report", "Past Reports"])

    # ── Generate ────────────────────────────────────────────────────────────────
    with tab_gen:
        latest = qs[0]
        q_score = round(_safe(latest.get("total_score", 0)) / 72.0 * 100.0, 1)
        risk, rc = _classify(q_score)

        total = int(_safe(latest.get("total_score", 0)))
        inatt = int(_safe(latest.get("inatt_score", 0)))
        hyper = int(_safe(latest.get("hyper_score", 0)))

        q_text = (
            f"Latest questionnaire score: {total}/72 ({latest.get('risk_level','')})."
            f" Attention: {inatt}/36, Activity/Impulse: {hyper}/36."
        )

        st.markdown(f"""
        <div style="background:{rc}18;border:2px solid {rc};border-radius:14px;
                    padding:20px;text-align:center;margin-bottom:20px;">
            <div style="font-size:1.8rem;font-weight:800;color:{rc};">{risk}</div>
            <div style="color:#374151;margin-top:6px;">
                Overall Risk Score: <b>{q_score:.1f}%</b> &nbsp;|&nbsp;
                Based on {len(qs)} assessment{"s" if len(qs)>1 else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

        g1, g2, g3 = st.columns(3)
        g1.plotly_chart(_gauge(q_score,  "Overall Risk",   rc),        use_container_width=True, key="pr_g1")
        g2.plotly_chart(_gauge(inatt / 36 * 100, "Attention",  "#1565c0"), use_container_width=True, key="pr_g2")
        g3.plotly_chart(_gauge(hyper / 36 * 100, "Activity",   "#c62828"), use_container_width=True, key="pr_g3")

        # Progress over time
        if len(qs) >= 2:
            st.markdown("#### Your Progress Over Time")
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
            st.plotly_chart(fig, use_container_width=True, key="pr_trend")

        # Interpretation card
        recs = {
            "High ADHD Risk":     (
                "Your scores suggest significant ADHD symptoms. "
                "We strongly recommend scheduling a detailed clinical assessment. "
                "Discuss medication, therapy, and coping strategies with your doctor."
            ),
            "Moderate ADHD Risk": (
                "Your scores indicate moderate ADHD-related symptoms. "
                "Regular monitoring and follow-up with your clinician is advised. "
                "Behavioural strategies and structured routines can be very helpful."
            ),
            "Low ADHD Risk":      (
                "Your scores are within the low-risk range. "
                "Continue healthy routines, adequate sleep, and scheduled check-ins. "
                "Reassess every 3–6 months or if symptoms change."
            ),
        }
        st.markdown(f"""
        <div class="card" style="margin-top:8px;">
            <b>📋 Personalised Recommendation</b><br><br>
            <span style="color:#374151;">{recs.get(risk, '')}</span>
        </div>
        """, unsafe_allow_html=True)

        # Save & PDF
        st.markdown("---")
        col_save, col_pdf = st.columns(2)

        with col_save:
            if st.button("Save Report to My Records", use_container_width=True):
                session_id = datetime.now().strftime("RPT_%Y%m%d_%H%M%S")
                save_report(
                    patient_id=pid,
                    session_id=session_id,
                    eeg_interpretation="",
                    questionnaire_summary=q_text,
                    emotion_summary="",
                    activity_summary="",
                    final_classification=risk,
                    risk_score=q_score,
                    eeg_score=0.0,
                    questionnaire_score=q_score,
                    emotion_score=0.0,
                    activity_score=0.0,
                )
                st.success("Report saved! View it in the 'Past Reports' tab.")
                st.rerun()

        with col_pdf:
            try:
                report_dict = {
                    "final_classification": risk,
                    "risk_score": q_score,
                    "questionnaire_score": q_score,
                    "questionnaire_summary": q_text,
                }
                pdf = _pdf_bytes(patient, report_dict)
                st.download_button(
                    "⬇ Download PDF Report",
                    data=pdf,
                    file_name=f"ADHD_Report_{patient['name'].replace(' ','_')}"
                              f"_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.info("PDF unavailable — reportlab not installed.")
            except Exception as e:
                st.warning(f"PDF error: {e}")

    # ── Past Reports ────────────────────────────────────────────────────────────
    with tab_hist:
        past = get_reports(pid)
        if not past:
            st.info("No saved reports yet. Generate and save one from the 'Generate Report' tab.")
            return

        for r in past:
            rc2 = _risk_color(r.get("final_classification", ""))
            with st.expander(
                f"📄  {r['generated_at'][:10]}  —  {r.get('final_classification','—')}"
                f"  (Risk: {r.get('risk_score',0):.1f}%)"
            ):
                c1, c2 = st.columns(2)
                c1.metric("Risk Score",    f"{r.get('risk_score',0):.1f}%")
                c2.metric("Classification", r.get("final_classification", "—"))
                if r.get("questionnaire_summary"):
                    st.markdown(f"**Assessment:** {r['questionnaire_summary']}")

        # Risk trend across saved reports
        if len(past) >= 2:
            pf  = pd.DataFrame(past[::-1])
            fig = go.Figure(go.Scatter(
                x=pf["generated_at"], y=pf["risk_score"],
                mode="lines+markers",
                line=dict(color="#c62828", width=2), marker=dict(size=8),
                fill="tozeroy", fillcolor="rgba(198,40,40,0.08)",
            ))
            fig.add_hline(y=60, line_dash="dash", line_color="#c62828", annotation_text="High Risk")
            fig.add_hline(y=33, line_dash="dash", line_color="#f57f17", annotation_text="Moderate")
            fig.update_layout(
                title="Risk Score Across Saved Reports",
                yaxis=dict(range=[0, 105], title="Risk %"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=280,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig, use_container_width=True, key="pr_hist_trend")
