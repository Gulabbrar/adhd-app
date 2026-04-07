"""modules/history.py — Historical Data Browser"""
import streamlit as st
import pandas as pd
import json
from database import (get_patients, get_eeg_signals, get_questionnaires,
                       get_emotion_logs, get_activity_results, get_all_eeg_sessions)


def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def render_history():
    st.markdown('<h2 class="page-title">Historical Data</h2>', unsafe_allow_html=True)

    patients = get_patients()
    if not patients:
        st.info("No patients registered yet.")
        return

    patient_opts = {"All Patients": None}
    patient_opts.update({f"{p['name']} (ID {p['id']})": p["id"] for p in patients})
    selected = st.selectbox("Filter by Patient", list(patient_opts.keys()))
    pid      = patient_opts[selected]

    tab_eeg, tab_q, tab_emo, tab_act = st.tabs([
        "EEG Signals", "Questionnaires", "Emotion Logs", "Activity Results"
    ])

    # ── EEG Data ─────────────────────────────────────────────────────────────
    with tab_eeg:
        if pid:
            rows = get_eeg_signals(pid, limit=500)
        else:
            # Load recent signals across all patients — join by patient_id, not name
            from database import get_conn
            with get_conn() as conn:
                raw = conn.execute("""
                    SELECT e.* FROM eeg_signals e
                    ORDER BY e.recorded_at DESC LIMIT 500
                """).fetchall()
            rows = [dict(r) for r in raw]

        if not rows:
            st.info("No EEG data found.")
        else:
            df = pd.DataFrame(rows)
            st.markdown(f"**{len(df)} records**")
            show = ["recorded_at","quality","attention","meditation","delta","theta",
                    "low_alpha","high_alpha","low_beta","high_beta",
                    "low_gamma","mid_gamma","theta_beta_ratio"]
            avail = [c for c in show if c in df.columns]
            st.dataframe(df[avail].iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
            st.download_button("⬇ Export EEG Data as CSV",
                               data=_to_csv(df[avail]),
                               file_name="eeg_data.csv", mime="text/csv")

    # ── Questionnaire Data ────────────────────────────────────────────────────
    with tab_q:
        from database import get_conn
        with get_conn() as conn:
            if pid:
                rows = conn.execute("""
                    SELECT q.*, p.name as patient_name FROM questionnaire_results q
                    JOIN patients p ON q.patient_id=p.id
                    WHERE q.patient_id=? ORDER BY q.assessed_at DESC
                """, (pid,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT q.*, p.name as patient_name FROM questionnaire_results q
                    JOIN patients p ON q.patient_id=p.id
                    ORDER BY q.assessed_at DESC LIMIT 100
                """).fetchall()
        if not rows:
            st.info("No questionnaire data found.")
        else:
            df = pd.DataFrame([dict(r) for r in rows])
            show = ["patient_name","session_id","total_score","inatt_score",
                    "hyper_score","risk_level","assessed_at"]
            avail = [c for c in show if c in df.columns]
            st.markdown(f"**{len(df)} records**")
            st.dataframe(df[avail].iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
            st.download_button("⬇ Export Questionnaires as CSV",
                               data=_to_csv(df[avail]),
                               file_name="questionnaires.csv", mime="text/csv")

            # Expandable: view full responses for a record
            if len(df) > 0:
                with st.expander("View Full Responses for a Record"):
                    row_idx = st.number_input("Row index (0-based)", 0, len(df)-1, 0)
                    raw_resp = df.iloc[row_idx].get("responses", "{}")
                    try:
                        resp = json.loads(raw_resp)
                        rdf  = pd.DataFrame([{"Question": k, "Score": v}
                                             for k, v in resp.items()])
                        st.dataframe(rdf, use_container_width=True, hide_index=True)
                    except Exception:
                        st.text(raw_resp)

    # ── Emotion Logs ──────────────────────────────────────────────────────────
    with tab_emo:
        from database import get_conn
        with get_conn() as conn:
            if pid:
                rows = conn.execute("""
                    SELECT e.*, p.name as patient_name FROM emotion_logs e
                    JOIN patients p ON e.patient_id=p.id
                    WHERE e.patient_id=? ORDER BY e.logged_at DESC
                """, (pid,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT e.*, p.name as patient_name FROM emotion_logs e
                    JOIN patients p ON e.patient_id=p.id
                    ORDER BY e.logged_at DESC LIMIT 200
                """).fetchall()
        if not rows:
            st.info("No emotion log data found.")
        else:
            df = pd.DataFrame([dict(r) for r in rows])
            show = ["patient_name","logged_at","dominant_emotion",
                    "happy","neutral","sad","angry","fear","surprise"]
            avail = [c for c in show if c in df.columns]
            st.markdown(f"**{len(df)} records**")
            st.dataframe(df[avail].iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
            st.download_button("⬇ Export Emotion Logs as CSV",
                               data=_to_csv(df[avail]),
                               file_name="emotion_logs.csv", mime="text/csv")

    # ── Activity Results ──────────────────────────────────────────────────────
    with tab_act:
        from database import get_conn
        with get_conn() as conn:
            if pid:
                rows = conn.execute("""
                    SELECT a.*, p.name as patient_name FROM activity_results a
                    JOIN patients p ON a.patient_id=p.id
                    WHERE a.patient_id=? ORDER BY a.completed_at DESC
                """, (pid,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT a.*, p.name as patient_name FROM activity_results a
                    JOIN patients p ON a.patient_id=p.id
                    ORDER BY a.completed_at DESC LIMIT 200
                """).fetchall()
        if not rows:
            st.info("No activity results found.")
        else:
            df = pd.DataFrame([dict(r) for r in rows])
            show = ["patient_name","activity_name","accuracy","completion_time",
                    "error_rate","attention_score","completed_at"]
            avail = [c for c in show if c in df.columns]
            st.markdown(f"**{len(df)} records**")
            st.dataframe(df[avail].iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
            st.download_button("⬇ Export Activity Results as CSV",
                               data=_to_csv(df[avail]),
                               file_name="activity_results.csv", mime="text/csv")
