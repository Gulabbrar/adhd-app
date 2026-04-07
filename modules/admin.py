"""modules/admin.py — Admin Panel"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import (get_patients, add_patient, update_patient, delete_patient,
                       get_dashboard_stats, get_reports, get_conn)


def _export_csv(df: pd.DataFrame, label: str, filename: str):
    st.download_button(f"⬇ {label}", data=df.to_csv(index=False).encode(),
                       file_name=filename, mime="text/csv")


def render_admin():
    st.markdown('<h2 class="page-title">Admin Panel</h2>', unsafe_allow_html=True)

    # Restrict to admin role
    user = st.session_state.get("user", {})
    if user.get("role") != "admin":
        st.error("Access denied. Admin role required.")
        return

    tab_pts, tab_users, tab_stats, tab_export = st.tabs([
        "Patient Management", "User Management", "Usage Statistics", "Export Data"
    ])

    # ── Patient Management ─────────────────────────────────────────────────────
    with tab_pts:
        patients = get_patients()

        # Add patient form
        with st.expander("➕ Add New Patient", expanded=False):
            with st.form("add_patient_form"):
                c1, c2, c3 = st.columns(3)
                name   = c1.text_input("Full Name *")
                age    = c2.number_input("Age", 3, 100, 10)
                gender = c3.selectbox("Gender", ["Male","Female","Other"])
                c4, c5 = st.columns(2)
                email = c4.text_input("Email")
                phone = c5.text_input("Phone")
                notes = st.text_area("Clinical Notes", height=60)
                if st.form_submit_button("Add Patient", use_container_width=True):
                    if name.strip():
                        new_id = add_patient(name.strip(), age, gender, email, phone, notes)
                        st.success(f"Patient '{name}' added with ID {new_id}")
                        st.rerun()
                    else:
                        st.error("Name is required.")

        if not patients:
            st.info("No patients registered.")
        else:
            # Patients table
            pdf = pd.DataFrame(patients)[["id","name","age","gender","email","phone","created_at"]]
            pdf.columns = ["ID","Name","Age","Gender","Email","Phone","Registered"]
            st.markdown(f"**{len(pdf)} patients registered**")
            st.dataframe(pdf, use_container_width=True, hide_index=True)

            # Edit / Delete
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                pt_opts = {f"{p['name']} (ID {p['id']})": p for p in patients}
                selected = st.selectbox("Select patient to edit / delete", list(pt_opts.keys()))
                pt = pt_opts[selected]
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑 Delete Patient", use_container_width=True):
                    delete_patient(pt["id"])
                    # Clear sidebar selection if same patient
                    if st.session_state.get("current_patient", {}).get("id") == pt["id"]:
                        st.session_state.current_patient = None
                    st.success(f"Deleted patient {pt['name']}.")
                    st.rerun()

            with st.form("edit_patient_form"):
                st.markdown(f"**Editing: {pt['name']}**")
                c1, c2, c3 = st.columns(3)
                new_name   = c1.text_input("Name",   value=pt["name"])
                new_age    = c2.number_input("Age",  min_value=3, max_value=100, value=pt["age"] or 10)
                new_gender = c3.selectbox("Gender",  ["Male","Female","Other"],
                                          index=["Male","Female","Other"].index(pt["gender"])
                                          if pt["gender"] in ["Male","Female","Other"] else 0)
                c4, c5 = st.columns(2)
                new_email = c4.text_input("Email", value=pt["email"] or "")
                new_phone = c5.text_input("Phone", value=pt["phone"] or "")
                new_notes = st.text_area("Notes", value=pt["notes"] or "", height=60)
                if st.form_submit_button("Save Changes", use_container_width=True):
                    update_patient(pt["id"], new_name, new_age, new_gender,
                                   new_email, new_phone, new_notes)
                    st.success("Patient updated.")
                    st.rerun()

    # ── User Management ────────────────────────────────────────────────────────
    with tab_users:
        with get_conn() as conn:
            users = [dict(r) for r in conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY id"
            ).fetchall()]
        udf = pd.DataFrame(users)
        st.dataframe(udf, use_container_width=True, hide_index=True)

        with st.expander("➕ Add User"):
            with st.form("add_user_form"):
                c1, c2, c3 = st.columns(3)
                uname = c1.text_input("Username")
                upwd  = c2.text_input("Password", type="password")
                urole = c3.selectbox("Role", ["clinician","admin"])
                if st.form_submit_button("Add User"):
                    if uname and upwd:
                        from database import register_user
                        result = register_user(
                            username=uname.strip(),
                            email="",
                            password=upwd,
                            role=urole,
                        )
                        if result["ok"]:
                            st.success(f"User '{uname}' created.")
                            st.rerun()
                        else:
                            st.error(result["error"])
                    else:
                        st.warning("Username and password are required.")

    # ── Usage Statistics ───────────────────────────────────────────────────────
    with tab_stats:
        stats = get_dashboard_stats()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Patients",    stats["total_patients"])
        c2.metric("Total Assessments", stats["total_assessments"])
        c3.metric("EEG Sessions",      stats["total_eeg"])

        rd = stats["risk_distribution"]
        if rd:
            col1, col2 = st.columns(2)
            with col1:
                labels = [r["risk_level"] for r in rd]
                values = [r["count"]      for r in rd]
                cmap   = {"High Risk":"#c62828","Moderate Risk":"#f57f17","Low Risk":"#2e7d32"}
                fig_r  = go.Figure(go.Pie(
                    labels=labels, values=values, hole=0.4,
                    marker=dict(colors=[cmap.get(l,"#1565c0") for l in labels]),
                ))
                fig_r.update_layout(title="Risk Distribution", paper_bgcolor="white",
                                    height=280, font=dict(family="Inter", size=11),
                                    margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig_r, use_container_width=True, key="adm_pie")

            with col2:
                with get_conn() as conn:
                    trend = [dict(r) for r in conn.execute("""
                        SELECT DATE(assessed_at) as day, COUNT(*) as count
                        FROM questionnaire_results
                        GROUP BY day ORDER BY day DESC LIMIT 14
                    """).fetchall()]
                if trend:
                    tdf = pd.DataFrame(trend)
                    fig_t = go.Figure(go.Bar(
                        x=tdf["day"], y=tdf["count"],
                        marker_color="#1565c0",
                        text=tdf["count"], textposition="outside"
                    ))
                    fig_t.update_layout(title="Assessments per Day (last 14 days)",
                                        yaxis_title="Count",
                                        paper_bgcolor="white", plot_bgcolor="#f8fafc",
                                        height=280, font=dict(family="Inter", size=11),
                                        margin=dict(t=40, b=20, l=40, r=10))
                    st.plotly_chart(fig_t, use_container_width=True, key="adm_trend")

    # ── Export Data ────────────────────────────────────────────────────────────
    with tab_export:
        st.markdown("#### Export All Data")

        with get_conn() as conn:
            all_patients = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM patients").fetchall()])
            all_eeg      = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM eeg_signals LIMIT 10000").fetchall()])
            all_q        = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM questionnaire_results").fetchall()])
            all_emo      = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM emotion_logs").fetchall()])
            all_act      = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM activity_results").fetchall()])
            all_reports  = pd.DataFrame([dict(r) for r in conn.execute(
                "SELECT * FROM assessment_reports").fetchall()])

        cols = st.columns(3)
        if not all_patients.empty:
            cols[0].download_button("⬇ Patients",       all_patients.to_csv(index=False).encode(),
                                    "patients.csv", "text/csv")
        if not all_eeg.empty:
            cols[1].download_button("⬇ EEG Signals",    all_eeg.to_csv(index=False).encode(),
                                    "eeg_signals.csv", "text/csv")
        if not all_q.empty:
            cols[2].download_button("⬇ Questionnaires", all_q.to_csv(index=False).encode(),
                                    "questionnaires.csv", "text/csv")
        cols2 = st.columns(3)
        if not all_emo.empty:
            cols2[0].download_button("⬇ Emotion Logs",  all_emo.to_csv(index=False).encode(),
                                     "emotion_logs.csv", "text/csv")
        if not all_act.empty:
            cols2[1].download_button("⬇ Activities",    all_act.to_csv(index=False).encode(),
                                     "activities.csv", "text/csv")
        if not all_reports.empty:
            cols2[2].download_button("⬇ Reports",       all_reports.to_csv(index=False).encode(),
                                     "reports.csv", "text/csv")
