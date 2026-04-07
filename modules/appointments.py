"""modules/appointments.py — Appointment booking & management"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database import (
    get_user_patient, book_appointment,
    get_appointments, update_appointment_status
)


def _status_badge(status: str) -> str:
    colors = {
        "booked":    ("#dbeafe", "#1d4ed8"),
        "completed": ("#dcfce7", "#15803d"),
        "cancelled": ("#fee2e2", "#b91c1c"),
    }
    bg, fg = colors.get(status, ("#f3f4f6", "#374151"))
    labels = {"booked": "Booked", "completed": "Completed", "cancelled": "Cancelled"}
    label  = labels.get(status, status.title())
    return (f'<span style="background:{bg};color:{fg};padding:3px 12px;'
            f'border-radius:50px;font-size:0.75rem;font-weight:600;">{label}</span>')


def render_appointments():
    st.markdown('<h2 class="page-title">Appointments</h2>', unsafe_allow_html=True)

    user    = st.session_state.user
    role    = user.get("role")
    is_pat  = role == "patient"

    # Determine patient context
    if is_pat:
        patient = get_user_patient(user["id"])
        if not patient:
            st.error("No patient profile linked to your account.")
            return
        pid = patient["id"]
        patient_name = patient["name"]
    else:
        # Clinician / admin: pick any patient
        from database import get_patients
        patients = get_patients()
        if not patients:
            st.info("No patients registered.")
            return
        opts = {f"{p['name']} — {p.get('patient_uid','') or '#'+str(p['id'])}": p
                for p in patients}
        sel  = st.selectbox("Patient", list(opts.keys()))
        patient = opts[sel]
        pid  = patient["id"]
        patient_name = patient["name"]

    # ── Layout ─────────────────────────────────────────────────────────────────
    col_book, col_list = st.columns([1, 1.6])

    # ── Book Appointment ───────────────────────────────────────────────────────
    with col_book:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Book New Appointment")

        min_date = date.today() + timedelta(days=1)
        max_date = date.today() + timedelta(days=90)

        with st.form("book_appt_form"):
            appt_date = st.date_input(
                "Appointment Date",
                value=min_date,
                min_value=min_date,
                max_value=max_date
            )
            time_slots = [
                "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
                "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM",
                "02:00 PM", "02:30 PM", "03:00 PM", "03:30 PM",
                "04:00 PM", "04:30 PM", "05:00 PM",
            ]
            appt_time = st.selectbox("Time Slot", time_slots)
            reason    = st.text_area("Reason / Notes", placeholder="e.g. Follow-up consultation", height=80)

            submitted = st.form_submit_button("Confirm Booking", use_container_width=True)

        if submitted:
            result = book_appointment(
                patient_id=pid,
                user_id=user["id"],
                appt_date=str(appt_date),
                appt_time=appt_time,
                reason=reason.strip(),
            )
            st.success(f"Appointment booked successfully!")
            st.markdown(f"""
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:16px;margin-top:10px;">
                <p style="margin:0;font-size:0.9rem;color:#166534;">
                    <strong>Date:</strong> {appt_date}&nbsp;&nbsp;
                    <strong>Time:</strong> {appt_time}<br>
                    <strong>Your Token Number:</strong>
                    <code style="font-size:1rem;background:#dcfce7;padding:3px 10px;
                    border-radius:6px;color:#15803d;">{result['token']}</code>
                </p>
                <p style="margin:8px 0 0;font-size:0.8rem;color:#4ade80;">
                    Please keep this token number for reference on your appointment day.
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Appointments List ──────────────────────────────────────────────────────
    with col_list:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"#### Appointments — {patient_name}")

        appts = get_appointments(pid)
        if not appts:
            st.info("No appointments found.")
        else:
            upcoming  = [a for a in appts if a["status"] == "booked"]
            past      = [a for a in appts if a["status"] != "booked"]

            if upcoming:
                st.markdown("**Upcoming**")
                for a in upcoming:
                    cols = st.columns([3, 2, 1])
                    cols[0].markdown(
                        f"**{a['appt_date']}** at {a['appt_time']}<br>"
                        f"<small style='color:#64748b;'>Token: `{a['token']}`</small>",
                        unsafe_allow_html=True
                    )
                    cols[1].markdown(_status_badge(a["status"]), unsafe_allow_html=True)
                    if not is_pat:
                        with cols[2]:
                            if st.button("✓ Done", key=f"done_{a['id']}"):
                                update_appointment_status(a["id"], "completed")
                                st.rerun()
                    else:
                        if cols[2].button("Cancel", key=f"cancel_{a['id']}"):
                            update_appointment_status(a["id"], "cancelled")
                            st.rerun()

                st.markdown("---")

            if past:
                st.markdown("**Past Appointments**")
                pdf = pd.DataFrame(past)[["token","appt_date","appt_time","reason","status"]]
                pdf.columns = ["Token","Date","Time","Reason","Status"]
                st.dataframe(pdf, use_container_width=True, hide_index=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Admin: All appointments overview ───────────────────────────────────────
    if not is_pat:
        st.markdown("---")
        st.markdown("#### All Appointments Overview")
        all_appts = get_appointments()
        if all_appts:
            adf = pd.DataFrame(all_appts)[[
                "patient_name","patient_uid","token","appt_date","appt_time","reason","status","created_at"
            ]]
            adf.columns = ["Patient","UID","Token","Date","Time","Reason","Status","Booked On"]
            st.dataframe(adf, use_container_width=True, hide_index=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total",     len(all_appts))
            c2.metric("Upcoming",  sum(1 for a in all_appts if a["status"] == "booked"))
            c3.metric("Completed", sum(1 for a in all_appts if a["status"] == "completed"))
