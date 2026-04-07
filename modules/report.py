"""modules/report.py — Final Cumulative ADHD Assessment Report"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime

from database import (get_patients, get_questionnaires, get_emotion_logs,
                       get_activity_results, save_report, get_reports,
                       get_eeg_signals, get_eeg_sessions)

# ── NaN-safe helper ────────────────────────────────────────────────────────────
import math

def _safe(val, default: float = 0.0) -> float:
    """Convert val to float, returning default for NaN / None / non-numeric."""
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


# ── Scoring Helpers ────────────────────────────────────────────────────────────

def _q_risk_score(questionnaires: list):
    if not questionnaires:
        return 0.0, "No questionnaire data available."
    latest = questionnaires[0]
    total  = _safe(latest.get("total_score", 0))
    inatt  = _safe(latest.get("inatt_score", 0))
    hyper  = _safe(latest.get("hyper_score", 0))
    risk   = latest.get("risk_level", "Unknown") or "Unknown"
    score  = round(total / 72.0 * 100.0, 1)
    return score, (f"Latest questionnaire score: {int(total)}/72 ({risk}). "
                   f"Inattention: {int(inatt)}/36, Hyperactivity: {int(hyper)}/36.")


def _emotion_risk_score(logs: list):
    if not logs:
        return 0.0, "No emotion data available."
    df = pd.DataFrame(logs)

    def _col_mean(col):
        if col not in df.columns:
            return 0.0
        return _safe(pd.to_numeric(df[col], errors='coerce').fillna(0.0).mean())

    neg  = _col_mean("angry") + _col_mean("fear") + _col_mean("sad")
    score = round(min(100.0, neg * 100.0), 1)

    dom_counts = df["dominant_emotion"].value_counts()
    total      = int(dom_counts.sum()) or 1
    stress_n   = int(dom_counts.get("angry", 0)) + int(dom_counts.get("fear", 0))
    stress_pct = round(stress_n / total * 100.0, 1)
    dominant   = str(df["dominant_emotion"].mode().iloc[0]) if len(df) > 0 else "neutral"

    return score, (f"Dominant emotion during assessment: {dominant}. "
                   f"Stress/anxiety indicators: {stress_pct}% of captures. "
                   + ("Elevated emotional reactivity noted." if stress_pct > 30 else
                      "Emotional state within expected range."))


def _activity_risk_score(results: list):
    if not results:
        return 0.0, "No cognitive activity data available."
    df      = pd.DataFrame(results)
    avg_acc = _safe(df["accuracy"].mean())
    avg_att = _safe(df["attention_score"].mean())
    score   = round(max(0.0, 100.0 - (avg_acc * 0.5 + avg_att * 0.5)), 1)
    return score, (f"Average accuracy: {avg_acc:.0f}%, attention: {avg_att:.0f}%. "
                   + ("Performance within normal range." if avg_acc >= 75 else
                      "Cognitive performance below average — suggests attention difficulties."))


def _eeg_risk_score(sessions: list, patient_id: int):
    """
    Compute EEG risk score (0–100) from all sessions.
    Key indicators:
      - Theta/Beta Ratio (TBR): primary ADHD biomarker. Clinical threshold ≥ 2.89.
      - Attention score: low attention → higher risk.
    Returns (score, interpretation_text, summary_dict)
    """
    if not sessions:
        return 0.0, "No EEG data available.", {}

    # Aggregate all signals across all sessions for this patient
    all_signals = get_eeg_signals(patient_id, limit=1000)
    if not all_signals:
        return 0.0, "No EEG signal samples found.", {}

    df = pd.DataFrame(all_signals)

    avg_tbr  = _safe(df["theta_beta_ratio"].mean())
    avg_att  = _safe(df["attention"].mean())
    avg_med  = _safe(df["meditation"].mean())
    avg_thet = _safe(df["theta"].mean())
    avg_beta = _safe((df["low_beta"] + df["high_beta"]).mean())
    avg_alph = _safe((df["low_alpha"] + df["high_alpha"]).mean())
    n_sess   = len(sessions)
    n_samp   = len(df)

    # TBR-based risk: TBR 2.89 = threshold, maps linearly to 0–100 risk
    # TBR 0   → 0% risk, TBR 2.89 → ~50%, TBR 5.78+ → 100%
    tbr_risk = min(100.0, max(0.0, avg_tbr / 5.78 * 100.0))

    # Attention-based risk: 100% attention → 0 risk, 0% attention → 100 risk
    att_risk = max(0.0, 100.0 - avg_att)

    # Combined EEG risk (TBR weighted more heavily as primary biomarker)
    score = round(tbr_risk * 0.65 + att_risk * 0.35, 1)

    # TBR interpretation
    if avg_tbr < 1.5:
        tbr_text = f"Normal (TBR {avg_tbr:.2f}) — within typical range."
    elif avg_tbr < 2.5:
        tbr_text = f"Slightly elevated TBR ({avg_tbr:.2f}) — mild inattention possible."
    elif avg_tbr < 3.5:
        tbr_text = f"High TBR ({avg_tbr:.2f}) — moderate ADHD tendency indicated."
    else:
        tbr_text = f"Very high TBR ({avg_tbr:.2f}) — strong ADHD biomarker (threshold ≥ 2.89)."

    att_text = (
        "Good sustained attention detected." if avg_att >= 65 else
        "Moderate attention levels." if avg_att >= 40 else
        "Low average attention — consistent with ADHD profile."
    )

    interpretation = (
        f"EEG analysis across {n_sess} session(s), {n_samp} samples. "
        f"Average Theta/Beta Ratio: {avg_tbr:.2f}. {tbr_text} "
        f"Average Attention: {avg_att:.0f}%. {att_text} "
        f"Average Meditation: {avg_med:.0f}%."
    )

    summary = {
        "sessions": n_sess, "samples": n_samp,
        "avg_tbr":  avg_tbr, "avg_attention": avg_att,
        "avg_meditation": avg_med,
        "avg_theta": avg_thet, "avg_beta": avg_beta, "avg_alpha": avg_alph,
    }
    return score, interpretation, summary


def _final_classification(risk_score: float) -> tuple[str, str]:
    if risk_score >= 60:
        return "High ADHD Risk",      "#c62828"
    elif risk_score >= 33:
        return "Moderate ADHD Risk",  "#f57f17"
    else:
        return "Low ADHD Risk",       "#2e7d32"


def _build_gauge(score: float, title: str, color: str) -> go.Figure:
    score = _safe(score)          # guard: NaN → 0.0 so Plotly never receives NaN
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
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
                          "thickness": 0.75, "value": score},
        },
        number={"suffix": "%", "font": {"size": 26}},
    ))
    fig.update_layout(height=200, paper_bgcolor="white",
                      margin=dict(t=40, b=10, l=20, r=20),
                      font=dict(family="Inter"))
    return fig


def _pdf_report(patient: dict, report: dict) -> bytes:
    """Generate a simple PDF report using ReportLab."""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import inch

    buf    = BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=(8.5 * inch, 11 * inch),
                                topMargin=0.75*inch, bottomMargin=0.75*inch,
                                leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle("title", parent=styles["Title"],
                                  fontSize=18, spaceAfter=6)
    body_style  = ParagraphStyle("body",  parent=styles["Normal"],
                                  fontSize=10, spaceAfter=4, leading=14)
    head_style  = ParagraphStyle("head",  parent=styles["Heading2"],
                                  fontSize=12, spaceAfter=4, textColor=rl_colors.HexColor("#1565c0"))

    story.append(Paragraph("ADHD Assessment Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Patient info table
    data = [
        ["Patient",  patient.get("name",""), "Age",    str(patient.get("age",""))],
        ["Gender",   patient.get("gender",""), "Session", report.get("session_id","")],
    ]
    t = Table(data, colWidths=[1*inch, 2*inch, 1*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), rl_colors.HexColor("#e3f2fd")),
        ("BACKGROUND", (2,0), (2,-1), rl_colors.HexColor("#e3f2fd")),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.5, rl_colors.grey),
        ("PADDING",    (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15*inch))

    # Final classification
    classification = report.get("final_classification", "")
    risk_score     = report.get("risk_score", 0)
    cls_color      = rl_colors.HexColor(
        "#c62828" if "High" in classification else
        "#f57f17" if "Moderate" in classification else "#2e7d32"
    )
    story.append(Paragraph("Final ADHD Classification", head_style))
    story.append(Paragraph(
        f"<font color='#{('c62828' if 'High' in classification else 'f57f17' if 'Moderate' in classification else '2e7d32')}'>"
        f"<b>{classification}</b></font> — Risk Score: {risk_score:.1f}%",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Score breakdown
    eeg_s = _safe(report.get("eeg_score", 0))
    has_e = eeg_s > 0
    score_data = [["Component", "Score", "Weight"]]
    if has_e:
        score_data += [
            ["EEG Assessment",     f"{eeg_s:.1f}%",                              "30%"],
            ["Questionnaire",      f"{report.get('questionnaire_score',0):.1f}%","35%"],
            ["Emotion Monitoring", f"{report.get('emotion_score',0):.1f}%",      "20%"],
            ["Cognitive Activity", f"{report.get('activity_score',0):.1f}%",     "15%"],
        ]
    else:
        score_data += [
            ["Questionnaire",      f"{report.get('questionnaire_score',0):.1f}%","50%"],
            ["Emotion Monitoring", f"{report.get('emotion_score',0):.1f}%",      "25%"],
            ["Cognitive Activity", f"{report.get('activity_score',0):.1f}%",     "25%"],
        ]
    t2 = Table(score_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rl_colors.HexColor("#1565c0")),
        ("TEXTCOLOR",  (0,0), (-1,0), rl_colors.white),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.5, rl_colors.grey),
        ("PADDING",    (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rl_colors.white, rl_colors.HexColor("#f0f4f8")]),
    ]))
    story.append(Paragraph("Score Breakdown", head_style))
    story.append(t2)
    story.append(Spacer(1, 0.15*inch))

    sections = [
        ("EEG Analysis",                 "eeg_interpretation"),
        ("Questionnaire Analysis",       "questionnaire_summary"),
        ("Emotion Monitoring Analysis",  "emotion_summary"),
        ("Cognitive Activity Analysis",  "activity_summary"),
    ]
    for heading, key in sections:
        text = report.get(key, "") or ""
        if not text:
            continue
        story.append(Paragraph(heading, head_style))
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 0.08*inch))

    doc.build(story)
    return buf.getvalue()


# ── Main Render ────────────────────────────────────────────────────────────────

def render_report():
    st.markdown('<h2 class="page-title">Final ADHD Assessment Report</h2>',
                unsafe_allow_html=True)

    patients = get_patients()
    if not patients:
        st.info("No patients registered yet.")
        return

    pt_opts  = {f"{p['name']} (ID {p['id']})": p for p in patients}
    selected = st.selectbox("Select Patient", list(pt_opts.keys()))
    patient  = pt_opts[selected]
    pid      = patient["id"]

    tab_generate, tab_history = st.tabs(["Generate Report", "Past Reports"])

    # ── Generate ────────────────────────────────────────────────────────────
    with tab_generate:
        session_id = datetime.now().strftime("RPT_%Y%m%d_%H%M%S")
        st.info(f"Compiling data for **{patient['name']}**")

        if st.button("Generate Collaborative Report", use_container_width=True):
            with st.spinner("Analysing all assessment data…"):
                # Load all data
                qs       = get_questionnaires(pid)
                emos     = get_emotion_logs(pid)
                acts     = get_activity_results(pid)
                eeg_sess = get_eeg_sessions(pid)

                # Compute component scores
                q_score,   q_text            = _q_risk_score(qs)
                emo_score, emo_text          = _emotion_risk_score(emos)
                act_score, act_text          = _activity_risk_score(acts)
                eeg_score, eeg_text, eeg_sum = _eeg_risk_score(eeg_sess, pid)

                q_score   = _safe(q_score)
                emo_score = _safe(emo_score)
                act_score = _safe(act_score)
                eeg_score = _safe(eeg_score)

                has_eeg = eeg_score > 0

                # Weights: EEG 30%, Questionnaire 35%, Emotion 20%, Activity 15%
                # If no EEG data redistribute weight to questionnaire
                if has_eeg:
                    weights    = [0.30, 0.35, 0.20, 0.15]
                    scores_raw = [eeg_score, q_score, emo_score, act_score]
                else:
                    weights    = [0.50, 0.25, 0.25]
                    scores_raw = [q_score, emo_score, act_score]

                risk_score = round(sum(w * s for w, s in zip(weights, scores_raw)), 1)
                classification, cls_color = _final_classification(risk_score)

            # Save to DB
            save_report(pid, session_id,
                        eeg_text, q_text, emo_text, act_text,
                        classification, risk_score,
                        eeg_score, q_score, emo_score, act_score)

            # ── Classification banner ────────────────────────────────────────
            st.markdown(f"""
            <div style="background:{cls_color}18;border:3px solid {cls_color};
                        border-radius:16px;padding:24px;text-align:center;margin:16px 0;">
                <div style="font-size:2.2rem;font-weight:900;color:{cls_color};">
                    {classification}
                </div>
                <div style="font-size:1.1rem;color:#333;margin-top:6px;">
                    Overall Risk Score: <b>{risk_score:.1f}%</b>
                </div>
                <div style="font-size:0.85rem;color:#666;margin-top:4px;">
                    Patient: {patient['name']} &nbsp;|&nbsp; Session: {session_id}<br>
                    Weights: {"EEG 30% · " if has_eeg else ""}
                    Questionnaire {"35" if has_eeg else "50"}% ·
                    Emotion {"20" if has_eeg else "25"}% ·
                    Activity {"15" if has_eeg else "25"}%
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Score gauges ─────────────────────────────────────────────────
            if has_eeg:
                g1, g2, g3, g4 = st.columns(4)
                g1.plotly_chart(_build_gauge(eeg_score,  "EEG",          "#7b1fa2"),
                                use_container_width=True, key="rpt_g0")
                g2.plotly_chart(_build_gauge(q_score,    "Questionnaire","#c62828"),
                                use_container_width=True, key="rpt_g1")
                g3.plotly_chart(_build_gauge(emo_score,  "Emotion",      "#f57f17"),
                                use_container_width=True, key="rpt_g2")
                g4.plotly_chart(_build_gauge(act_score,  "Activity",     "#2e7d32"),
                                use_container_width=True, key="rpt_g3")
            else:
                g1, g2, g3 = st.columns(3)
                g1.plotly_chart(_build_gauge(q_score,   "Questionnaire","#c62828"),
                                use_container_width=True, key="rpt_g1")
                g2.plotly_chart(_build_gauge(emo_score, "Emotion",      "#f57f17"),
                                use_container_width=True, key="rpt_g2")
                g3.plotly_chart(_build_gauge(act_score, "Activity",     "#2e7d32"),
                                use_container_width=True, key="rpt_g3")

            # ── EEG detail card ───────────────────────────────────────────────
            if has_eeg:
                tbr_c = ("#c62828" if eeg_sum["avg_tbr"] >= 3.5 else
                          "#e65100" if eeg_sum["avg_tbr"] >= 2.5 else
                          "#f57f17" if eeg_sum["avg_tbr"] >= 1.5 else "#2e7d32")
                st.markdown(f"""
                <div class="card" style="margin-bottom:8px;border-left:4px solid #7b1fa2;">
                    <b>EEG Neurological Analysis</b>
                    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;">
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Sessions</div>
                            <div style="font-size:1.4rem;font-weight:700;color:#0d47a1;">{eeg_sum['sessions']}</div>
                        </div>
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Avg Attention</div>
                            <div style="font-size:1.4rem;font-weight:700;color:#0d47a1;">{eeg_sum['avg_attention']:.0f}%</div>
                        </div>
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Avg TBR</div>
                            <div style="font-size:1.4rem;font-weight:700;color:{tbr_c};">{eeg_sum['avg_tbr']:.2f}</div>
                        </div>
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Avg Meditation</div>
                            <div style="font-size:1.4rem;font-weight:700;color:#0d47a1;">{eeg_sum['avg_meditation']:.0f}%</div>
                        </div>
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Avg Theta</div>
                            <div style="font-size:1.4rem;font-weight:700;color:#0d47a1;">{eeg_sum['avg_theta']:,.0f}</div>
                        </div>
                        <div style="flex:1;min-width:120px;text-align:center;">
                            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">Avg Beta</div>
                            <div style="font-size:1.4rem;font-weight:700;color:#0d47a1;">{eeg_sum['avg_beta']:,.0f}</div>
                        </div>
                    </div>
                    <div style="margin-top:10px;color:#374151;font-size:0.88rem;">{eeg_text}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No EEG data for this patient. Enter EEG readings via the "
                        "**EEG Assessment → Manual Entry** tab to include them in future reports.")

            # Interpretation cards
            sections = [
                ("Questionnaire Analysis",      q_text),
                ("Emotion Monitoring Analysis", emo_text),
                ("Cognitive Activity Analysis", act_text),
            ]
            for title, text in sections:
                st.markdown(f"""
                <div class="card" style="margin-bottom:8px;">
                    <b>{title}</b><br>
                    <span style="color:#333;font-size:0.9rem;">{text}</span>
                </div>
                """, unsafe_allow_html=True)

            # PDF Download
            try:
                report_dict = {
                    "session_id":            session_id,
                    "final_classification":  classification,
                    "risk_score":            risk_score,
                    "eeg_score":             eeg_score,
                    "questionnaire_score":   q_score,
                    "emotion_score":         emo_score,
                    "activity_score":        act_score,
                    "eeg_interpretation":    eeg_text,
                    "questionnaire_summary": q_text,
                    "emotion_summary":       emo_text,
                    "activity_summary":      act_text,
                }
                pdf_bytes = _pdf_report(patient, report_dict)
                st.download_button(
                    "Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"ADHD_Report_{patient['name'].replace(' ','_')}_{session_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.info("Install ReportLab (`pip install reportlab`) to enable PDF export.")
            except Exception as pdf_err:
                st.warning(f"PDF generation failed: {pdf_err}. The on-screen report above is complete.")

            # Signal patient portal to show review after report generation
            st.session_state["review_dialog_done"] = False

    # ── Past Reports ────────────────────────────────────────────────────────
    with tab_history:
        past = get_reports(pid)
        if not past:
            st.info("No reports generated for this patient yet.")
            return
        rdf = pd.DataFrame(past)[["session_id","final_classification","risk_score",
                                    "questionnaire_score","emotion_score","activity_score","generated_at"]]
        rdf.columns = ["Session","Classification","Risk %","Q-Score %","Emotion %","Activity %","Generated"]
        st.dataframe(rdf, use_container_width=True, hide_index=True)

        # Risk trend
        if len(past) > 1:
            pf = pd.DataFrame(past).sort_values("generated_at")
            fig_rt = go.Figure()
            fig_rt.add_trace(go.Scatter(x=pf["generated_at"], y=pf["risk_score"],
                                         name="Risk Score", mode="lines+markers",
                                         line=dict(color="#c62828", width=2)))
            fig_rt.add_hline(y=60, line_dash="dash", line_color="#c62828",
                             annotation_text="High Risk")
            fig_rt.add_hline(y=33, line_dash="dash", line_color="#f57f17",
                             annotation_text="Moderate Risk")
            fig_rt.update_layout(
                title="Risk Score Trend",
                yaxis=dict(range=[0, 105], title="Risk %"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc", height=300,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_rt, use_container_width=True, key="rpt_trend")
