"""modules/emotion.py — Webcam Facial Emotion Monitoring"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from database import save_emotion_log, get_emotion_logs

EMOTION_COLORS = {
    "happy":   "#2e7d32",
    "neutral": "#1565c0",
    "sad":     "#4527a0",
    "angry":   "#c62828",
    "fear":    "#e65100",
    "surprise":"#f57f17",
    "disgust": "#6a1b9a",
}

EMOTION_ADHD_NOTES = {
    "happy":    "Positive engagement — low stress indicator.",
    "neutral":  "Neutral expression — baseline state.",
    "sad":      "Low affect detected — may reflect frustration or disengagement.",
    "angry":    "Frustration/irritability — common in ADHD under cognitive load.",
    "fear":     "Anxiety detected — high stress during task.",
    "surprise": "Heightened alertness or distraction.",
    "disgust":  "Task aversion detected.",
}


def _analyze_image(img_bytes) -> dict | None:
    """Run DeepFace analysis on captured image bytes."""
    try:
        from deepface import DeepFace
        import numpy as np
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img)
        result = DeepFace.analyze(arr, actions=["emotion"],
                                   enforce_detection=False, silent=True)
        if isinstance(result, list):
            result = result[0]
        emotions = result.get("emotion", {})
        dominant = result.get("dominant_emotion", "neutral")
        # Normalize to 0–1
        total = sum(emotions.values()) or 1
        normalized = {k: round(v / total, 4) for k, v in emotions.items()}
        return {"dominant": dominant, "scores": normalized}
    except ImportError:
        st.error("DeepFace is not installed. Run: `pip install deepface tf-keras`")
        return None
    except Exception as e:
        st.warning(f"Emotion detection failed: {e}")
        return None


def render_emotion():
    st.markdown('<h2 class="page-title">Emotion Monitoring</h2>', unsafe_allow_html=True)

    patient = st.session_state.get("current_patient")
    if not patient:
        st.warning("Please select a patient from the sidebar first.")
        return

    pid  = patient["id"]
    name = patient["name"]

    session_id = st.session_state.get("eeg_session_id",
                  datetime.now().strftime("EMO_%Y%m%d_%H%M%S"))

    tab_capture, tab_logs = st.tabs(["Capture Emotion", "Emotion Log"])

    # ── Tab 1: Live Capture ──────────────────────────────────────────────────
    with tab_capture:
        st.markdown(f"""
        <div class="card">
        <b>Patient:</b> {name} &nbsp;|&nbsp; <b>Session:</b> {session_id}<br>
        <small>Capture the patient's facial expression during the assessment.
        Each capture is stored with a timestamp.</small>
        </div>
        """, unsafe_allow_html=True)

        col_cam, col_result = st.columns([1, 1])

        with col_cam:
            st.markdown("#### 📸 Webcam Capture")
            img_data = st.camera_input("Take a photo for emotion analysis",
                                        label_visibility="collapsed")

            if img_data:
                if st.button("Analyze Emotion", use_container_width=True):
                    with st.spinner("Analyzing facial expression…"):
                        result = _analyze_image(img_data.getvalue())
                    if result:
                        st.session_state["last_emotion"] = result
                        save_emotion_log(pid, session_id,
                                         result["dominant"], result["scores"])
                        st.success("Emotion logged successfully.")

        with col_result:
            st.markdown("#### Analysis Result")
            last = st.session_state.get("last_emotion")
            if last:
                dom   = last["dominant"]
                color = EMOTION_COLORS.get(dom, "#1565c0")
                note  = EMOTION_ADHD_NOTES.get(dom, "")

                st.markdown(f"""
                <div style="background:{color}18;border:2px solid {color};
                            border-radius:12px;padding:20px;text-align:center;">
                    <div style="font-size:2.5rem;">
                        {"😊" if dom=="happy" else "😐" if dom=="neutral" else
                         "😢" if dom=="sad"   else "😠" if dom=="angry"   else
                         "😨" if dom=="fear"  else "😲" if dom=="surprise" else "🤢"}
                    </div>
                    <div style="font-size:1.5rem;font-weight:800;color:{color};margin-top:6px;">
                        {dom.capitalize()}
                    </div>
                    <div style="font-size:0.85rem;color:#555;margin-top:6px;">{note}</div>
                </div>
                """, unsafe_allow_html=True)

                # Bar chart of emotion scores
                scores = last["scores"]
                fig = go.Figure(go.Bar(
                    x=list(scores.keys()),
                    y=[v * 100 for v in scores.values()],
                    marker_color=[EMOTION_COLORS.get(k, "#1565c0") for k in scores],
                    text=[f"{v*100:.1f}%" for v in scores.values()],
                    textposition="outside",
                ))
                fig.update_layout(
                    title="Emotion Confidence Scores (%)",
                    yaxis=dict(range=[0, 110], title="%"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc", height=280,
                    font=dict(family="Inter", size=11),
                    margin=dict(t=40, b=20, l=40, r=20),
                )
                st.plotly_chart(fig, use_container_width=True, key="emo_bar")
            else:
                st.info("Capture an image and click **Analyze Emotion** to see results here.")

    # ── Tab 2: Emotion Log ───────────────────────────────────────────────────
    with tab_logs:
        logs = get_emotion_logs(pid)
        if not logs:
            st.info("No emotion logs recorded for this patient yet.")
            return

        df = pd.DataFrame(logs)

        # Summary pie
        dom_counts = df["dominant_emotion"].value_counts().reset_index()
        dom_counts.columns = ["emotion", "count"]

        col1, col2 = st.columns([1, 1])
        with col1:
            fig_pie = go.Figure(go.Pie(
                labels=dom_counts["emotion"],
                values=dom_counts["count"],
                hole=0.4,
                marker=dict(colors=[EMOTION_COLORS.get(e,"#1565c0") for e in dom_counts["emotion"]]),
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                title="Dominant Emotion Distribution",
                paper_bgcolor="white", height=280,
                font=dict(family="Inter", size=11),
                margin=dict(t=40, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="emo_pie")

        with col2:
            if len(df) > 2:
                fig_line = go.Figure()
                for emo, color in EMOTION_COLORS.items():
                    if emo in df.columns:
                        fig_line.add_trace(go.Scatter(
                            x=df["logged_at"], y=df[emo] * 100,
                            name=emo, mode="lines",
                            line=dict(color=color, width=1.5),
                        ))
                fig_line.update_layout(
                    title="Emotion Scores Over Time (%)",
                    yaxis=dict(title="%"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc", height=280,
                    font=dict(family="Inter", size=11),
                    margin=dict(t=40, b=20, l=40, r=10),
                )
                st.plotly_chart(fig_line, use_container_width=True, key="emo_trend")

        # Table
        show = ["logged_at","dominant_emotion","happy","neutral","sad","angry","fear","surprise"]
        avail = [c for c in show if c in df.columns]
        st.dataframe(df[avail].iloc[::-1].reset_index(drop=True),
                     use_container_width=True, hide_index=True)
