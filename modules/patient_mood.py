"""modules/patient_mood.py — Daily mood & wellbeing tracker for patients"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_user_patient, add_mood_log, get_mood_logs, get_mood_streak

# ── Mood palette ───────────────────────────────────────────────────────────────
MOODS = {
    "😄 Happy":       ("happy",      "#2e7d32", "😄"),
    "😌 Calm":        ("calm",       "#1565c0", "😌"),
    "😤 Irritable":   ("irritable",  "#e65100", "😤"),
    "😰 Anxious":     ("anxious",    "#f57f17", "😰"),
    "😢 Sad":         ("sad",        "#4527a0", "😢"),
    "🎯 Focused":     ("focused",    "#00695c", "🎯"),
    "😴 Tired":       ("tired",      "#546e7a", "😴"),
    "😵 Overwhelmed": ("overwhelmed","#c62828", "😵"),
}

MOOD_COLOR = {v[0]: v[1] for v in MOODS.values()}
MOOD_EMOJI = {v[0]: v[2] for v in MOODS.values()}


def _score_color(score: int) -> str:
    if score >= 8:   return "#2e7d32"
    if score >= 6:   return "#558b2f"
    if score >= 4:   return "#f57f17"
    if score >= 2:   return "#e65100"
    return "#c62828"


def _already_logged_today(logs: list) -> bool:
    today = str(date.today())
    return any(str(l.get("logged_at", ""))[:10] == today for l in logs)


# ── Main render ────────────────────────────────────────────────────────────────
def render_patient_mood():
    st.markdown('<h2 class="page-title">Mood Tracker</h2>', unsafe_allow_html=True)

    user    = st.session_state.user
    patient = get_user_patient(user["id"])
    if not patient:
        st.error("Patient profile not found.")
        return

    pid    = patient["id"]
    logs   = get_mood_logs(pid, limit=90)
    streak = get_mood_streak(pid)

    # ── KPI strip ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Day Streak 🔥",    f"{streak} day{'s' if streak != 1 else ''}")
    c2.metric("Total Check-ins",  len(logs))
    if logs:
        avg_mood = round(sum(l["mood_score"] for l in logs) / len(logs), 1)
        avg_enrg = round(sum(l["energy_level"] for l in logs) / len(logs), 1)
        c3.metric("Avg Mood",     f"{avg_mood}/10")
        c4.metric("Avg Energy",   f"{avg_enrg}/10")
    else:
        c3.metric("Avg Mood",     "—")
        c4.metric("Avg Energy",   "—")

    st.markdown("<br>", unsafe_allow_html=True)

    tab_checkin, tab_face, tab_history, tab_insights = st.tabs([
        "✏️ Daily Check-in", "📸 Facial Analysis", "📅 History", "💡 Insights"
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Daily check-in
    # ══════════════════════════════════════════════════════════════════════════
    with tab_checkin:
        already_done = _already_logged_today(logs)

        if already_done:
            today_log = next(l for l in logs if str(l["logged_at"])[:10] == str(date.today()))
            lbl   = today_log.get("mood_label", "")
            score = today_log.get("mood_score", 5)
            rc    = _score_color(score)
            emoji = MOOD_EMOJI.get(lbl, "😐")
            st.markdown(f"""
            <div style="background:{rc}18;border:2px solid {rc};border-radius:14px;
                        padding:20px;text-align:center;margin-bottom:16px;">
                <div style="font-size:2.5rem;">{emoji}</div>
                <div style="font-size:1.3rem;font-weight:700;color:{rc};">
                    Today's check-in done!
                </div>
                <div style="color:#374151;margin-top:6px;">
                    Mood: <b>{score}/10</b> &nbsp;|&nbsp;
                    Energy: <b>{today_log.get('energy_level',5)}/10</b> &nbsp;|&nbsp;
                    Sleep: <b>{today_log.get('sleep_hours',7):.1f} hrs</b>
                </div>
                {f'<div style="color:#64748b;font-size:0.85rem;margin-top:6px;">'
                 f'"{today_log.get("notes","")}"</div>'
                 if today_log.get("notes") else ""}
            </div>
            """, unsafe_allow_html=True)
            st.info("You've already logged your mood today. Come back tomorrow!")

        else:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"#### How are you feeling today, {patient['name'].split()[0]}?")

            # Mood picker — radio so selection state is always visible
            st.markdown("**Select your mood:**")
            mood_label_list = list(MOODS.keys())
            chosen_label = st.radio(
                "Mood",
                mood_label_list,
                index=0,
                horizontal=True,
                label_visibility="collapsed",
                key="mood_radio_pick",
            )
            chosen_key = MOODS[chosen_label][0]
            chosen_color = MOODS[chosen_label][1]
            chosen_emoji = MOODS[chosen_label][2]
            # Show a colour-coded confirmation strip
            st.markdown(f"""
            <div style="background:{chosen_color}18;border-left:4px solid {chosen_color};
                        border-radius:6px;padding:6px 14px;margin:6px 0 12px;
                        font-size:0.9rem;font-weight:600;color:{chosen_color};">
                {chosen_emoji} {chosen_label.split(' ',1)[1].title()} selected
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            with st.form("mood_checkin_form"):
                c1, c2, c3 = st.columns(3)
                mood_score   = c1.slider("Mood Score",   1, 10, 6,
                                          help="1 = Very bad, 10 = Excellent")
                energy_level = c2.slider("Energy Level", 1, 10, 6,
                                          help="1 = Exhausted, 10 = Very energetic")
                sleep_hours  = c3.slider("Sleep Last Night (hrs)", 0.0, 12.0, 7.0, step=0.5)

                # Symptoms checklist
                st.markdown("**Any of these today? (optional)**")
                sym_cols = st.columns(4)
                sym_opts = ["Hard to focus", "Restless", "Forgetful",
                            "Impulsive", "Mood swings", "Procrastinating",
                            "Low motivation", "Stressed"]
                selected_syms = []
                for i, sym in enumerate(sym_opts):
                    if sym_cols[i % 4].checkbox(sym, key=f"sym_{i}"):
                        selected_syms.append(sym)

                notes = st.text_area("Notes / Reflections",
                                      placeholder="How was your day? Any triggers or wins?",
                                      height=80)

                submitted = st.form_submit_button("Save Today's Check-in",
                                                   use_container_width=True)

            if submitted:
                mood_label = st.session_state.get("selected_mood") or "neutral"
                note_full  = notes.strip()
                if selected_syms:
                    note_full = f"Symptoms: {', '.join(selected_syms)}. " + note_full

                add_mood_log(
                    patient_id=pid,
                    user_id=user["id"],
                    mood_score=mood_score,
                    energy_level=energy_level,
                    sleep_hours=sleep_hours,
                    mood_label=mood_label,
                    notes=note_full,
                )
                st.session_state.selected_mood = None
                st.success("Mood logged! Keep it up — consistency is key.")
                st.balloons()
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — Facial Analysis (DeepFace)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_face:
        st.markdown("""
        <div class="card">
            <b>📸 Facial Emotion Detection</b><br>
            <small style="color:#64748b;">
                Take a photo and the AI will detect your facial emotion using DeepFace.
                The result is saved to your mood log automatically.
            </small>
        </div>
        """, unsafe_allow_html=True)

        EMOTION_COLORS = {
            "happy":    "#2e7d32", "neutral": "#1565c0", "sad":     "#4527a0",
            "angry":    "#c62828", "fear":    "#e65100", "surprise":"#f57f17",
            "disgust":  "#6a1b9a",
        }
        EMOTION_EMOJI = {
            "happy": "😄", "neutral": "😐", "sad": "😢",
            "angry": "😠", "fear":    "😨", "surprise": "😲", "disgust": "🤢",
        }
        ADHD_NOTES = {
            "happy":    "Positive engagement — low stress indicator.",
            "neutral":  "Neutral/baseline emotional state.",
            "sad":      "Low affect — may reflect frustration or disengagement.",
            "angry":    "Frustration/irritability — common under cognitive load.",
            "fear":     "Anxiety detected — high stress state.",
            "surprise": "Heightened alertness or distraction.",
            "disgust":  "Task/situation aversion detected.",
        }

        col_cam, col_result = st.columns([1, 1])

        with col_cam:
            img_data = st.camera_input("Take a photo",
                                        label_visibility="collapsed")
            if img_data:
                if st.button("Analyse Emotion", use_container_width=True,
                              key="face_analyse_btn"):
                    with st.spinner("Detecting facial emotion…"):
                        try:
                            from deepface import DeepFace
                            import numpy as np
                            from PIL import Image
                            import io

                            img  = Image.open(io.BytesIO(img_data.getvalue())).convert("RGB")
                            arr  = np.array(img)
                            res  = DeepFace.analyze(arr, actions=["emotion"],
                                                     enforce_detection=False, silent=True)
                            if isinstance(res, list):
                                res = res[0]
                            emotions  = res.get("emotion", {})
                            dominant  = res.get("dominant_emotion", "neutral")
                            total_e   = sum(emotions.values()) or 1
                            norm      = {k: round(v / total_e, 4) for k, v in emotions.items()}
                            st.session_state["face_result"] = {
                                "dominant": dominant, "scores": norm
                            }
                            # Auto-save to mood_logs
                            # Map DeepFace emotion → mood_label used in mood_logs
                            emo_to_mood = {
                                "happy": "happy", "neutral": "calm", "sad": "sad",
                                "angry": "irritable", "fear": "anxious",
                                "surprise": "happy", "disgust": "overwhelmed",
                            }
                            mood_lbl = emo_to_mood.get(dominant, "calm")
                            add_mood_log(
                                patient_id=pid,
                                user_id=user["id"],
                                mood_score={"happy":9,"neutral":6,"sad":3,
                                            "angry":3,"fear":3,"surprise":7,
                                            "disgust":2}.get(dominant, 5),
                                energy_level=5,
                                sleep_hours=7.0,
                                mood_label=mood_lbl,
                                notes=f"[DeepFace] dominant emotion: {dominant}",
                            )
                            st.success(f"Emotion detected and saved to mood log!")
                        except ImportError:
                            st.error("DeepFace not installed. "
                                     "Run: `pip install deepface tf-keras`")
                        except Exception as e:
                            st.warning(f"Detection failed: {e}")

        with col_result:
            result = st.session_state.get("face_result")
            if result:
                dom   = result["dominant"]
                color = EMOTION_COLORS.get(dom, "#1565c0")
                emoji = EMOTION_EMOJI.get(dom, "😐")
                note  = ADHD_NOTES.get(dom, "")

                st.markdown(f"""
                <div style="background:{color}18;border:2px solid {color};
                            border-radius:12px;padding:20px;text-align:center;">
                    <div style="font-size:3rem;">{emoji}</div>
                    <div style="font-size:1.6rem;font-weight:800;color:{color};margin-top:6px;">
                        {dom.capitalize()}
                    </div>
                    <div style="font-size:0.85rem;color:#555;margin-top:6px;">{note}</div>
                </div>
                """, unsafe_allow_html=True)

                scores = result["scores"]
                fig = go.Figure(go.Bar(
                    x=list(scores.keys()),
                    y=[v * 100 for v in scores.values()],
                    marker_color=[EMOTION_COLORS.get(k,"#1565c0") for k in scores],
                    text=[f"{v*100:.1f}%" for v in scores.values()],
                    textposition="outside",
                ))
                fig.update_layout(
                    yaxis=dict(range=[0, 110], title="%"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc",
                    height=260, font=dict(family="Inter", size=11),
                    margin=dict(t=10, b=20, l=40, r=10),
                )
                st.plotly_chart(fig, use_container_width=True, key="face_bar")
            else:
                st.markdown("""
                <div style="text-align:center;padding:40px;color:#94a3b8;">
                    <div style="font-size:3rem;">📷</div>
                    <p>Take a photo and click <b>Analyse Emotion</b><br>
                    to see your facial emotion breakdown here.</p>
                </div>
                """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — History
    # ══════════════════════════════════════════════════════════════════════════
    with tab_history:
        if not logs:
            st.info("No mood logs yet. Start your first check-in!")
        else:
            df = pd.DataFrame(logs)
            df["date"]  = pd.to_datetime(df["logged_at"]).dt.date
            df["day"]   = pd.to_datetime(df["logged_at"]).dt.strftime("%b %d")
            df_sorted   = df.sort_values("logged_at")

            # ── Mood + Energy trend ────────────────────────────────────────────
            st.markdown("#### Mood & Energy Over Time")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_sorted["day"], y=df_sorted["mood_score"],
                name="Mood", mode="lines+markers",
                line=dict(color="#1565c0", width=2.5),
                marker=dict(size=8,
                            color=df_sorted["mood_score"],
                            colorscale="RdYlGn",
                            cmin=1, cmax=10,
                            showscale=False),
                fill="tozeroy", fillcolor="rgba(21,101,192,0.06)",
            ))
            fig.add_trace(go.Scatter(
                x=df_sorted["day"], y=df_sorted["energy_level"],
                name="Energy", mode="lines+markers",
                line=dict(color="#f57f17", width=1.5, dash="dot"),
                marker=dict(size=6),
            ))
            fig.add_hline(y=5, line_dash="dash", line_color="#94a3b8",
                          annotation_text="Midpoint")
            fig.update_layout(
                yaxis=dict(range=[0, 11], title="Score (1–10)"),
                paper_bgcolor="white", plot_bgcolor="white",
                height=280, font=dict(family="Inter", size=11),
                legend=dict(bgcolor="white", bordercolor="#e2e8f0", borderwidth=1),
                margin=dict(t=20, b=20, l=40, r=20),
            )
            st.plotly_chart(fig, use_container_width=True, key="mood_trend")

            # ── Sleep trend ────────────────────────────────────────────────────
            st.markdown("#### Sleep Hours")
            fig_s = go.Figure(go.Bar(
                x=df_sorted["day"].tolist()[-14:],
                y=df_sorted["sleep_hours"].tolist()[-14:],
                marker_color=[
                    "#2e7d32" if h >= 7 else "#f57f17" if h >= 5 else "#c62828"
                    for h in df_sorted["sleep_hours"].tolist()[-14:]
                ],
                text=[f"{h:.1f}h" for h in df_sorted["sleep_hours"].tolist()[-14:]],
                textposition="outside",
            ))
            fig_s.add_hline(y=7, line_dash="dash", line_color="#2e7d32",
                            annotation_text="Recommended 7h")
            fig_s.update_layout(
                yaxis=dict(range=[0, 14], title="Hours"),
                paper_bgcolor="white", plot_bgcolor="#f8fafc",
                height=220, font=dict(family="Inter", size=11),
                margin=dict(t=20, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_s, use_container_width=True, key="sleep_chart")

            # ── Log table ──────────────────────────────────────────────────────
            st.markdown("#### Check-in History")
            display = df[["logged_at","mood_label","mood_score",
                           "energy_level","sleep_hours","notes"]].copy()
            display.columns = ["Date","Mood","Mood/10","Energy/10","Sleep hrs","Notes"]
            display["Date"] = display["Date"].str[:16]
            display["Mood"] = display["Mood"].apply(
                lambda x: f"{MOOD_EMOJI.get(x,'😐')} {x.title()}" if x else "—"
            )
            st.dataframe(display.iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — Insights
    # ══════════════════════════════════════════════════════════════════════════
    with tab_insights:
        if len(logs) < 3:
            st.info("Log your mood for at least 3 days to unlock personalised insights.")
        else:
            df = pd.DataFrame(logs)

            col1, col2 = st.columns(2)

            # ── Mood distribution donut ────────────────────────────────────────
            with col1:
                st.markdown("#### Mood Distribution")
                counts = df["mood_label"].value_counts().reset_index()
                counts.columns = ["mood", "count"]
                fig_pie = go.Figure(go.Pie(
                    labels=[f"{MOOD_EMOJI.get(m,'😐')} {m.title()}" for m in counts["mood"]],
                    values=counts["count"],
                    hole=0.45,
                    marker=dict(colors=[MOOD_COLOR.get(m,"#999") for m in counts["mood"]]),
                    textinfo="label+percent",
                ))
                fig_pie.update_layout(
                    paper_bgcolor="white", height=280,
                    font=dict(family="Inter", size=11),
                    showlegend=False,
                    margin=dict(t=10, b=10, l=10, r=10),
                )
                st.plotly_chart(fig_pie, use_container_width=True, key="mood_pie")

            # ── Best / worst day pattern ───────────────────────────────────────
            with col2:
                st.markdown("#### Mood by Day of Week")
                df["dow"] = pd.to_datetime(df["logged_at"]).dt.day_name()
                order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                dow_avg = df.groupby("dow")["mood_score"].mean().reindex(order).dropna()

                fig_dow = go.Figure(go.Bar(
                    x=dow_avg.index.tolist(),
                    y=dow_avg.values.tolist(),
                    marker_color=[_score_color(int(v)) for v in dow_avg.values],
                    text=[f"{v:.1f}" for v in dow_avg.values],
                    textposition="outside",
                ))
                fig_dow.update_layout(
                    yaxis=dict(range=[0, 11], title="Avg Mood"),
                    paper_bgcolor="white", plot_bgcolor="#f8fafc",
                    height=280, font=dict(family="Inter", size=11),
                    margin=dict(t=20, b=20, l=40, r=10),
                )
                st.plotly_chart(fig_dow, use_container_width=True, key="mood_dow")

            # ── Sleep vs Mood correlation ──────────────────────────────────────
            st.markdown("#### Sleep vs Mood Correlation")
            fig_cor = go.Figure(go.Scatter(
                x=df["sleep_hours"].tolist(),
                y=df["mood_score"].tolist(),
                mode="markers",
                marker=dict(
                    size=10,
                    color=df["mood_score"].tolist(),
                    colorscale="RdYlGn",
                    cmin=1, cmax=10,
                    showscale=True,
                    colorbar=dict(title="Mood"),
                ),
                text=df["mood_label"].tolist(),
            ))
            fig_cor.update_layout(
                xaxis_title="Sleep Hours",
                yaxis_title="Mood Score",
                yaxis=dict(range=[0, 11]),
                xaxis=dict(range=[0, 13]),
                paper_bgcolor="white", plot_bgcolor="#f8fafc",
                height=260, font=dict(family="Inter", size=11),
                margin=dict(t=20, b=20, l=40, r=20),
            )
            st.plotly_chart(fig_cor, use_container_width=True, key="sleep_mood_scatter")

            # ── Personalised tip ───────────────────────────────────────────────
            avg_mood  = df["mood_score"].mean()
            avg_sleep = df["sleep_hours"].mean()
            best_day  = dow_avg.idxmax() if not dow_avg.empty else "—"
            worst_day = dow_avg.idxmin() if not dow_avg.empty else "—"
            top_mood  = df["mood_label"].mode().iloc[0] if len(df) > 0 else "—"

            tips = []
            if avg_sleep < 6.5:
                tips.append("💤 Your average sleep is below 6.5 hours. Better sleep strongly "
                             "improves ADHD symptoms — try a consistent bedtime routine.")
            if avg_mood < 5:
                tips.append("🧠 Your average mood score is below 5. Consider speaking with "
                             "your clinician about adjusting your management plan.")
            if top_mood in ("anxious", "overwhelmed", "irritable"):
                tips.append(f"⚠️ Your most frequent mood is **{top_mood}**. "
                             "Breathing exercises and short movement breaks can help regulate this.")
            if not tips:
                tips.append("✅ Your mood patterns look stable. Keep up your current routine!")

            st.markdown(f"""
            <div class="card" style="margin-top:8px;">
                <b>💡 Your Personalised Insights</b><br><br>
                <table style="width:100%;border-collapse:collapse;">
                    <tr>
                        <td style="padding:4px 8px;color:#64748b;">Best day of week</td>
                        <td style="padding:4px 8px;font-weight:600;">{best_day}</td>
                        <td style="padding:4px 8px;color:#64748b;">Most common mood</td>
                        <td style="padding:4px 8px;font-weight:600;">{MOOD_EMOJI.get(top_mood,'😐')} {top_mood.title()}</td>
                    </tr>
                    <tr>
                        <td style="padding:4px 8px;color:#64748b;">Avg sleep</td>
                        <td style="padding:4px 8px;font-weight:600;">{avg_sleep:.1f} hrs</td>
                        <td style="padding:4px 8px;color:#64748b;">Avg mood</td>
                        <td style="padding:4px 8px;font-weight:600;">{avg_mood:.1f}/10</td>
                    </tr>
                </table>
                <hr style="border-color:#e2e8f0;margin:12px 0;">
                {"<br>".join(f'<p style="margin:4px 0;color:#374151;">{t}</p>' for t in tips)}
            </div>
            """, unsafe_allow_html=True)
